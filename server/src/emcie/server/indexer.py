import json
from pathlib import Path
from lagom import Container
from typing import Any, Sequence

from emcie.server.core.agents import AgentStore
from emcie.server.core.guideline_connections import GuidelineConnectionId, GuidelineConnectionStore
from emcie.server.core.guidelines import Guideline, GuidelineStore
from emcie.server.guideline_connection_proposer import GuidelineConnectionProposer
from emcie.server.logger import Logger


class GuidelineIndexer:
    def __init__(
        self,
        container: Container,
    ) -> None:
        self.logger = container[Logger]

        self._guideline_proposer = GuidelineConnectionProposer(self.logger)
        self._guideline_store = container[GuidelineStore]
        self._guideline_connection_store = container[GuidelineConnectionStore]
        self._agent_store = container[AgentStore]

    def _assess_guideline_modifications(
        self,
        guidelines: Sequence[Guideline],
        cached_guidelines: dict[int, str],
    ) -> tuple[Sequence[Guideline], Sequence[Guideline], dict[int, str]]:
        fresh_guidelines, retained_guidelines = [], []
        deleted_guidelines = cached_guidelines.copy()

        for guideline in guidelines:
            guideline_digest = hash(guideline)

            if guideline_digest in cached_guidelines:
                retained_guidelines.append(guideline)

                del deleted_guidelines[guideline_digest]
            else:
                fresh_guidelines.append(guideline)

        return fresh_guidelines, retained_guidelines, deleted_guidelines

    async def _remove_deleted_guidelines_connections(
            self,
            deleted_guidelines: dict[int, str],
    ) -> None:
        for id in deleted_guidelines.values():
            try:
                await self._guideline_connection_store.delete_connection(GuidelineConnectionId(id))
            except ValueError:  # case that connections with the guideline id are not exists
                pass

    async def _index_guideline_connections(
        self,
        guidelines: Sequence[Guideline],
        cached_guidelines: dict[int, str],
    ) -> None:
        fresh, retained, deleted = self._assess_guideline_modifications(
                guidelines,
                cached_guidelines
            )

        await self._remove_deleted_guidelines_connections(deleted)

        [
            await self._guideline_connection_store.update_connection(
                source=p.source,
                target=p.target,
                kind=p.kind,
            )
            for p in await self._guideline_proposer.propose_connections(
                fresh_guidelines=fresh,
                retained_guidelines=retained
                )
        ]

        return

    async def index(
        self,
        cached_guidelines: dict[str, Any],
    ) -> dict[str, Any]:
        self.logger.info("GuidelineIndexer started")

        indexed_guidelines = {}

        for agent in await self._agent_store.list_agents():
            agent_guidelines = await self._guideline_store.list_guidelines(agent.id)

            await self._index_guideline_connections(
                agent_guidelines,
                cached_guidelines.get(agent.name, {}),
            )

            indexed_guidelines[str(agent.id)] = {
                hash(g): g.id
                for g in agent_guidelines
                }

        return indexed_guidelines


class Indexer:
    def __init__(
        self,
        container: Container,
        cache_file: Path,
    ) -> None:
        self.logger = container[Logger]
        self._cache_file = cache_file
        self._guideline_indexer = GuidelineIndexer(container)

    def _read_cache(self) -> dict[str, Any]:
        if self._cache_file.exists() and self._cache_file.stat().st_size > 0:
            with open(self._cache_file, "r") as f:
                data: dict[str, Any] = json.load(f)
                return data
        return {}

    def _write_cache(self, cache_data: dict[str, Any],) -> None:
        with open(self._cache_file, "w") as f:
            json.dump(cache_data, f, indent=2)

    async def index(self) -> None:
        data = {}

        current_cache_data = self._read_cache()

        data["guidelines"] = await self._guideline_indexer.index(
            cached_guidelines=current_cache_data.get("guidelines", {}),
            )

        self._write_cache(data)
