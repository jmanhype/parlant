from dataclasses import dataclass
from datetime import datetime
import json
import os
from pathlib import Path
from lagom import Container
from pytest import fixture
from emcie.server.core.agents import AgentId
from emcie.server.core.guidelines import Guideline, GuidelineDocumentStore
from emcie.server.core.persistence import DocumentDatabase, JSONFileDatabase
from tests.test_utilities import SyncAwaiter

JSON_TEST_FILES_PATH = "tests/engines/alpha/persistence/json_test_files/"


@dataclass
class _TestContext:
    sync_await: SyncAwaiter
    container: Container
    agent_id: AgentId


@fixture
def context(sync_await: SyncAwaiter, container: Container, agent_id: AgentId) -> _TestContext:
    return _TestContext(sync_await, container, agent_id)


def test_guideline_creation_persists_in_json(
    context: _TestContext,
) -> None:
    guidelines_json_file_path = os.path.join(JSON_TEST_FILES_PATH, "test_guidelines.json")
    file_path = Path(guidelines_json_file_path)
    file_path.unlink(missing_ok=True)

    db: DocumentDatabase[Guideline] = JSONFileDatabase[Guideline](guidelines_json_file_path)
    guideline_store = GuidelineDocumentStore(db)

    guideline = context.sync_await(
        guideline_store.create_guideline(
            guideline_set=context.agent_id,
            predicate="Creating a guideline with JSONFileDatabase implementation",
            content="Expecting it to show in the guidelines json file",
        )
    )

    with open(guidelines_json_file_path) as _f:
        guidelines_from_json = json.load(_f)

    assert len(guidelines_from_json) == 1
    assert context.agent_id in guidelines_from_json
    assert guideline.id in guidelines_from_json[context.agent_id]
    assert guidelines_from_json[context.agent_id][guideline.id]["predicate"] == guideline.predicate
    assert guidelines_from_json[context.agent_id][guideline.id]["content"] == guideline.content
    assert (
        datetime.fromisoformat(guidelines_from_json[context.agent_id][guideline.id]["creation_utc"])
        == guideline.creation_utc
    )
    # Create a second guideline to check if both are stored correctly
    second_guideline = context.sync_await(
        guideline_store.create_guideline(
            guideline_set=context.agent_id,
            predicate="Second guideline creation",
            content="Additional test entry in the JSON file",
        )
    )

    with open(guidelines_json_file_path) as _f:
        guidelines_from_json = json.load(_f)

    assert len(guidelines_from_json) == 1
    assert len(guidelines_from_json[context.agent_id]) == 2
    assert second_guideline.id in guidelines_from_json[context.agent_id]
    assert (
        guidelines_from_json[context.agent_id][second_guideline.id]["predicate"]
        == second_guideline.predicate
    )
    assert (
        guidelines_from_json[context.agent_id][second_guideline.id]["content"]
        == second_guideline.content
    )
    assert (
        datetime.fromisoformat(
            guidelines_from_json[context.agent_id][second_guideline.id]["creation_utc"]
        )
        == second_guideline.creation_utc
    )


def test_guideline_loading_from_json(
    context: _TestContext,
) -> None:
    guidelines_json_file_path = os.path.join(JSON_TEST_FILES_PATH, "test_guidelines.json")
    file_path = Path(guidelines_json_file_path)
    file_path.unlink(missing_ok=True)

    db: DocumentDatabase[Guideline] = JSONFileDatabase[Guideline](guidelines_json_file_path)
    guideline_store = GuidelineDocumentStore(db)

    context.sync_await(
        guideline_store.create_guideline(
            guideline_set=context.agent_id,
            predicate="Test predicate for loading",
            content="Test content for loading guideline",
        )
    )

    loaded_guidelines = context.sync_await(guideline_store.list_guidelines(context.agent_id))
    loaded_guideline_list = list(loaded_guidelines)

    assert len(loaded_guideline_list) == 1
    loaded_guideline = loaded_guideline_list[0]
    assert loaded_guideline.predicate == "Test predicate for loading"
    assert loaded_guideline.content == "Test content for loading guideline"
