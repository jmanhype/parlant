import asyncio
import json
from pathlib import Path
from lagom import Container
from typing import Any, Sequence

from emcie.server.core.agents import AgentStore
from emcie.server.core.common import JSONSerializable
from emcie.server.core.guideline_connections import GuidelineConnectionStore
from emcie.server.core.guidelines import Guideline, GuidelineId, GuidelineStore
from emcie.server.guideline_connection_proposer import GuidelineConnectionProposer
from emcie.server.logger import Logger
from emcie.server.utils import md5_checksum


GuidelineSet = str
GuidelineChecksum = str

IndexedGuideline = dict[GuidelineChecksum, GuidelineId]
IndexedGuidelineSets = dict[GuidelineSet, IndexedGuideline]


class GuidelineIndexer:
    def __init__(self, container: Container) -> None:
        self.logger = container[Logger]
        self._guideline_connection_proposer = GuidelineConnectionProposer(self.logger)
        self._guideline_store = container[GuidelineStore]
        self._guideline_connection_store = container[GuidelineConnectionStore]
        self._agent_store = container[AgentStore]

    @staticmethod
    def _guideline_checksum(guideline: Guideline) -> GuidelineChecksum:
        return md5_checksum(f"{guideline.predicate}_{guideline.content}")

    async def should_index(self, indexed_guideline_sets: IndexedGuidelineSets) -> bool:
        for agent in await self._agent_store.list_agents():
            agent_guidelines = await self._guideline_store.list_guidelines(agent.id)

            introduced, _, deleted = self._assess_guideline_modifications(
                agent_guidelines, indexed_guideline_sets.get(agent.id, {})
            )

            if introduced or deleted:
                return True

        return False

    async def index(
        self,
        existing_indexed_guidelines: IndexedGuidelineSets,
    ) -> IndexedGuidelineSets:
        self.logger.info("Guideline indexing started")

        indexed_guideline_sets: IndexedGuidelineSets = dict()

        for agent in await self._agent_store.list_agents():
            agent_guidelines = await self._guideline_store.list_guidelines(agent.id)

            await self._index_guideline_connections(
                agent_guidelines,
                existing_indexed_guidelines.get(agent.id, {}),
            )

            indexed_guideline_sets[agent.id] = {
                self._guideline_checksum(g): g.id for g in agent_guidelines
            }

        self.logger.info("Guideline indexing finished")

        return indexed_guideline_sets

    def _assess_guideline_modifications(
        self,
        guidelines: Sequence[Guideline],
        indexed_guideline_set: IndexedGuideline,
    ) -> tuple[Sequence[Guideline], Sequence[Guideline], IndexedGuideline]:
        introduced_guidelines, existing_guidelines = [], []
        deleted_guidelines = indexed_guideline_set.copy()

        for guideline in guidelines:
            guideline_checksum = self._guideline_checksum(guideline)

            if guideline_checksum in indexed_guideline_set:
                existing_guidelines.append(guideline)
                del deleted_guidelines[guideline_checksum]
            else:
                introduced_guidelines.append(guideline)

        return introduced_guidelines, existing_guidelines, deleted_guidelines

    async def _remove_deleted_guidelines_connections(
        self,
        deleted_guidelines: IndexedGuideline,
    ) -> None:
        for id in deleted_guidelines.values():
            try:
                connections = await self._guideline_connection_store.list_connections(
                    indirect=False, source=id, target=id
                )
                await asyncio.gather(
                    *(self._guideline_connection_store.delete_connection(c.id) for c in connections)
                )
            except ValueError:  # in case connections with the guideline id do not exist
                pass

    async def _index_guideline_connections(
        self,
        guidelines: Sequence[Guideline],
        indexed_guideline_set: IndexedGuideline,
    ) -> None:
        introduced, existsing, deleted = self._assess_guideline_modifications(
            guidelines, indexed_guideline_set
        )

        await self._remove_deleted_guidelines_connections(deleted)

        [
            await self._guideline_connection_store.update_connection(
                source=p.source,
                target=p.target,
                kind=p.kind,
            )
            for p in await self._guideline_connection_proposer.propose_connections(
                introduced_guidelines=introduced, existing_guidelines=existsing
            )
        ]


class Indexer:
    def __init__(
        self,
        index_file: Path,
    ) -> None:
        self._index_file = index_file

    def _read_index_file(self) -> dict[str, Any]:
        if self._index_file.exists() and self._index_file.stat().st_size > 0:
            with open(self._index_file, "r") as f:
                data: dict[str, Any] = json.load(f)
                return data
        return {}

    def _write_index_file(self, indexes: JSONSerializable) -> None:
        with open(self._index_file, "w") as f:
            json.dump(indexes, f, indent=2)

    async def should_index(
        self,
        container: Container,
    ) -> bool:
        guideline_indexer = GuidelineIndexer(container)

        indexed_data = self._read_index_file()

        return await guideline_indexer.should_index(indexed_data.get("guidelines", {}))

    async def index(self, container: Container) -> None:
        guideline_indexer = GuidelineIndexer(container)

        indexed_data = self._read_index_file()

        data = {}
        data["guidelines"] = await guideline_indexer.index(
            existing_indexed_guidelines=indexed_data.get("guidelines", {}),
        )

        self._write_index_file(data)
