from abc import ABC, abstractmethod
import json
from pathlib import Path
from lagom import Container
from typing import Any, Sequence

from emcie.server.core.agents import AgentStore
from emcie.server.core.guideline_connections import GuidelineConnectionStore
from emcie.server.core.guidelines import Guideline, GuidelineId, GuidelineStore
from emcie.server.guideline_connection_proposer import GuidelineConnectionProposer
from emcie.server.logger import Logger


class IndexingRequiredException(Exception):
    def __init__(self) -> None:
        super().__init__("Indexing is required but has been disabled by the --no-index flag.")


class IndexingComponent(ABC):
    @abstractmethod
    async def should_index(self, cached_data: dict[str, Any]) -> bool: ...

    @abstractmethod
    async def index(self, cached_data: dict[str, Any]) -> dict[str, Any]: ...


class GuidelineIndexer(IndexingComponent):
    def __init__(self, container: Container) -> None:
        self.logger = container[Logger]
        self._guideline_proposer = GuidelineConnectionProposer(self.logger)
        self._guideline_store = container[GuidelineStore]
        self._guideline_connection_store = container[GuidelineConnectionStore]
        self._agent_store = container[AgentStore]

    @staticmethod
    def _guideline_checksum(guideline: Guideline) -> str:
        return f"{guideline.predicate}_{guideline.content}"

    async def should_index(self, cached_data: dict[str, Any]) -> bool:
        for agent in await self._agent_store.list_agents():
            agent_guidelines = await self._guideline_store.list_guidelines(agent.id)

            fresh, _, deleted = self._assess_guideline_modifications(agent_guidelines, cached_data)

            if fresh or deleted:
                return True

        return False

    async def index(self, cached_data: dict[str, Any]) -> dict[str, Any]:
        self.logger.info("Guideline indexing started")

        indexed_guidelines = {}

        for agent in await self._agent_store.list_agents():
            agent_guidelines = await self._guideline_store.list_guidelines(agent.id)

            await self._index_guideline_connections(
                agent_guidelines,
                cached_data.get(agent.name, {}),
            )

            indexed_guidelines[agent.name] = {
                self._guideline_checksum(g): g.id for g in agent_guidelines
            }

        self.logger.info("Guideline indexing finished")

        return indexed_guidelines

    def _assess_guideline_modifications(
        self,
        guidelines: Sequence[Guideline],
        cached_guidelines: dict[str, str],
    ) -> tuple[Sequence[Guideline], Sequence[Guideline], dict[str, str]]:
        fresh_guidelines, retained_guidelines = [], []
        deleted_guidelines = cached_guidelines.copy()

        for guideline in guidelines:
            guideline_digest = self._guideline_checksum(guideline)

            if guideline_digest in cached_guidelines:
                retained_guidelines.append(guideline)
                del deleted_guidelines[guideline_digest]
            else:
                fresh_guidelines.append(guideline)

        return fresh_guidelines, retained_guidelines, deleted_guidelines

    async def _remove_deleted_guidelines_connections(
        self,
        deleted_guidelines: dict[str, str],
    ) -> None:
        for id in deleted_guidelines.values():
            try:
                await self._guideline_connection_store.delete_guideline_connections(GuidelineId(id))
            except ValueError:  # in case connections with the guideline id do not exist
                pass

    async def _index_guideline_connections(
        self,
        guidelines: Sequence[Guideline],
        cached_guidelines: dict[str, str],
    ) -> None:
        fresh, retained, deleted = self._assess_guideline_modifications(
            guidelines, cached_guidelines
        )

        await self._remove_deleted_guidelines_connections(deleted)

        [
            await self._guideline_connection_store.update_connection(
                source=p.source,
                target=p.target,
                kind=p.kind,
            )
            for p in await self._guideline_proposer.propose_connections(
                fresh_guidelines=fresh, retained_guidelines=retained
            )
        ]


class Indexer:
    def __init__(
        self,
        cache_file: Path,
        perform_indexing: bool = True,
        force_disable_indexing: bool = False,
    ) -> None:
        self._cache_file = cache_file
        self._perform_indexing = perform_indexing
        self._skip_indexing = force_disable_indexing

    def _read_cache(self) -> dict[str, Any]:
        if self._cache_file.exists() and self._cache_file.stat().st_size > 0:
            with open(self._cache_file, "r") as f:
                data: dict[str, Any] = json.load(f)
                return data
        return {}

    def _write_cache(self, cache_data: dict[str, Any]) -> None:
        with open(self._cache_file, "w") as f:
            json.dump(cache_data, f, indent=2)

    async def index(self, container: Container) -> bool:
        logger = container[Logger]

        if not self._perform_indexing and self._skip_indexing:
            logger.warning("Skipping indexing. This might cause unpredictable behavior.")
            return True

        guideline_indexer = GuidelineIndexer(container)

        current_cache_data = self._read_cache()

        if not self._perform_indexing and await guideline_indexer.should_index(current_cache_data):
            raise IndexingRequiredException()

        data = {}
        data["guidelines"] = await guideline_indexer.index(
            cached_data=current_cache_data.get("guidelines", {}),
        )

        self._write_cache(data)

        return True
