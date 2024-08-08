from contextlib import asynccontextmanager
import json
from pathlib import Path
import tempfile
from typing import AsyncIterator

from lagom import Container
from pytest import fixture

from emcie.server.core.agents import AgentId, AgentStore
from emcie.server.core.guidelines import GuidelineStore
from emcie.server.core.guideline_connections import GuidelineConnectionStore
from emcie.server.indexer import Indexer
from tests.test_utilities import SyncAwaiter


@asynccontextmanager
async def new_file_path() -> AsyncIterator[Path]:
    with tempfile.NamedTemporaryFile(delete=True) as new_file:
        yield Path(new_file.name)


@fixture
def agent_id(
    container: Container,
    sync_await: SyncAwaiter,
) -> AgentId:
    store = container[AgentStore]
    agent = sync_await(store.create_agent(name="test-agent"))
    return agent.id


async def test_that_guidelines_written_in_the_cache_file(
    container: Container,
    agent_id: AgentId,
) -> None:

    guideline_store = container[GuidelineStore]

    first_guideline = await guideline_store.create_guideline(
        guideline_set=agent_id,
        predicate="greeting the user",
        content="do your job when the user says hello",
    )

    second_guideline = await guideline_store.create_guideline(
        guideline_set=agent_id,
        predicate="the user asks what is your favourite food",
        content="tell him it is pizza",
    )

    async with new_file_path() as cache_file:
        indexer = Indexer(container=container, cache_file=cache_file)
        await indexer.index()
        with open(cache_file, "r") as f:
            cache_dict = json.load(f)

            cached_guidelines = cache_dict["guidelines"][str(agent_id)]

            assert str(hash(first_guideline)) in cached_guidelines
            assert str(hash(second_guideline)) in cached_guidelines

            assert cached_guidelines[str(hash(first_guideline))] == first_guideline.id
            assert cached_guidelines[str(hash(second_guideline))] == second_guideline.id


async def test_that_removed_guidelines_are_also_removed_from_the_cache_file(
    container: Container,
    agent_id: AgentId,
) -> None:
    guideline_store = container[GuidelineStore]

    await guideline_store.create_guideline(
        guideline_set=agent_id,
        predicate="greeting the user",
        content="do your job when the user says hello",
    )

    _guideline = await guideline_store.create_guideline(
        guideline_set=agent_id,
        predicate="the user asks what is your favourite food",
        content="tell him it is pizza",
    )

    async with new_file_path() as cache_file:
        await Indexer(container=container, cache_file=cache_file).index()
        with open(cache_file, "r") as f:
            cache_dict = json.load(f)

            assert len(cache_dict["guidelines"][str(agent_id)]) == 2

        await guideline_store.delete_guideline(
            guideline_set=agent_id,
            guideline_id=_guideline.id,
        )

        await Indexer(container=container, cache_file=cache_file).index()

        with open(cache_file, "r") as f:
            cache_dict = json.load(f)

            assert len(cache_dict["guidelines"][str(agent_id)]) == 1


async def test_that_guideline_connections_are_created(
    container: Container,
    agent_id: AgentId,
) -> None:
    guideline_store = container[GuidelineStore]
    connection_store = container[GuidelineConnectionStore]

    first_guideline = await guideline_store.create_guideline(
        guideline_set=agent_id,
        predicate="The user asks about the weather",
        content="provide the current weather update",
    )

    second_guideline = await guideline_store.create_guideline(
        guideline_set=agent_id,
        predicate="providing the weather update",
        content="mention the best time to go for a walk",
    )

    async with new_file_path() as cache_file:
        indexer = Indexer(container=container, cache_file=cache_file)
        await indexer.index()

        connections = await connection_store.list_connections(first_guideline.id, indirect=False)

        assert len(connections) == 1
        assert connections[0].source == first_guideline.id
        assert connections[0].target == second_guideline.id


async def test_that_guideline_connections_are_removed_when_guideline_deleted(
    container: Container,
    agent_id: AgentId,
) -> None:
    guideline_store = container[GuidelineStore]
    connection_store = container[GuidelineConnectionStore]

    first_guideline = await guideline_store.create_guideline(
        guideline_set=agent_id,
        predicate="The user asks about the weather",
        content="provide the current weather update",
    )

    await guideline_store.create_guideline(
        guideline_set=agent_id,
        predicate="providing the weather update",
        content="mention the best time to go for a walk",
    )

    async with new_file_path() as cache_file:
        indexer = Indexer(container=container, cache_file=cache_file)
        await indexer.index()

        connections = await connection_store.list_connections(first_guideline.id, indirect=False)

        assert len(connections) == 1

        await guideline_store.delete_guideline(
            guideline_set=agent_id,
            guideline_id=first_guideline.id,
        )

        await indexer.index()

        connections = await connection_store.list_connections(first_guideline.id, indirect=False)

        assert len(connections) == 0
