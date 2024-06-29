from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from lagom import Container
from pytest import fixture
from emcie.server.core.agents import Agent, AgentDocumentStore, AgentId, AgentStore
from emcie.server.core.end_users import EndUserId
from emcie.server.core.guidelines import Guideline, GuidelineDocumentStore, GuidelineStore
from emcie.server.core.models import ModelId
from emcie.server.core.persistence import DocumentCollection, JSONFileDocumentCollection
from emcie.server.core.sessions import Event, Session, SessionDocumentStore, SessionStore
from emcie.server.core.tools import Tool, ToolDocumentStore, ToolStore
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


@fixture
def agent_json_path() -> str:
    return os.path.join(JSON_TEST_FILES_PATH, "test_agents.json")


@fixture
def tool_json_path() -> str:
    return os.path.join(JSON_TEST_FILES_PATH, "test_tools.json")


@fixture
def guideline_json_path() -> str:
    return os.path.join(JSON_TEST_FILES_PATH, "test_guidelines.json")


@fixture
def session_json_path() -> str:
    return os.path.join(JSON_TEST_FILES_PATH, "test_sessions.json")


@fixture
def agent_store(agent_json_path: str) -> AgentStore:
    file_path = Path(agent_json_path)
    file_path.unlink(missing_ok=True)
    db: DocumentCollection[Agent] = JSONFileDocumentCollection[Agent](agent_json_path)
    return AgentDocumentStore(db)


@fixture
def session_store(session_json_path: str) -> SessionStore:
    file_path = Path(session_json_path)
    file_path.unlink(missing_ok=True)  # Ensure the file is deleted if it exists
    db: DocumentCollection[Session] = JSONFileDocumentCollection[Session](session_json_path)
    event_db: DocumentCollection[Event] = JSONFileDocumentCollection[Event](
        session_json_path
    )  # Using the same file for simplicity
    return SessionDocumentStore(db, event_db)


@fixture
def guideline_store(guideline_json_path: str) -> GuidelineStore:
    file_path = Path(guideline_json_path)
    file_path.unlink(missing_ok=True)  # Ensure the file is deleted if it exists
    db: DocumentCollection[Guideline] = JSONFileDocumentCollection[Guideline](guideline_json_path)
    return GuidelineDocumentStore(db)


@fixture
def tool_store(tool_json_path: str) -> ToolStore:
    file_path = Path(tool_json_path)
    file_path.unlink(missing_ok=True)  # Ensure the file is deleted if it exists
    db: DocumentCollection[Tool] = JSONFileDocumentCollection[Tool](tool_json_path)
    return ToolDocumentStore(db)


def test_guideline_creation_persists_in_json(
    context: _TestContext,
    guideline_store: GuidelineStore,
    guideline_json_path: str,
) -> None:

    guideline = context.sync_await(
        guideline_store.create_guideline(
            guideline_set=context.agent_id,
            predicate="Creating a guideline with JSONFileDatabase implementation",
            content="Expecting it to show in the guidelines json file",
        )
    )

    with open(guideline_json_path) as _f:
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

    with open(guideline_json_path) as _f:
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
    guideline_store: GuidelineStore,
) -> None:
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


def test_tool_creation_persists_in_json(
    context: _TestContext,
    tool_store: ToolStore,
    tool_json_path: str,
) -> None:

    tool = context.sync_await(
        tool_store.create_tool(
            tool_set=context.agent_id,
            name="Unique tool name",
            module_path="path/to/module",
            description="A tool for testing JSON persistence",
            parameters={"param1": "value1", "param2": "value2"},
            required=["param1"],
            consequential=True,
        )
    )

    with open(tool_json_path) as _f:
        tools_from_json = json.load(_f)

    assert len(tools_from_json) == 1
    assert context.agent_id in tools_from_json
    assert tool.id in tools_from_json[context.agent_id]
    assert tools_from_json[context.agent_id][tool.id]["name"] == tool.name
    assert tools_from_json[context.agent_id][tool.id]["module_path"] == tool.module_path
    assert tools_from_json[context.agent_id][tool.id]["description"] == tool.description
    assert tools_from_json[context.agent_id][tool.id]["parameters"] == tool.parameters
    assert tools_from_json[context.agent_id][tool.id]["required"] == tool.required
    assert tools_from_json[context.agent_id][tool.id]["consequential"] == tool.consequential


def test_tool_loading_from_json(
    context: _TestContext,
    tool_store: ToolStore,
) -> None:
    context.sync_await(
        tool_store.create_tool(
            tool_set=context.agent_id,
            name="Tool for loading test",
            module_path="path/to/tool/module",
            description="Testing tool load functionality",
            parameters={"param1": "value1"},
            required=["param1"],
            consequential=False,
        )
    )

    loaded_tools = context.sync_await(tool_store.list_tools(context.agent_id))
    loaded_tool_list = list(loaded_tools)

    assert len(loaded_tool_list) == 1
    loaded_tool = loaded_tool_list[0]
    assert loaded_tool.name == "Tool for loading test"
    assert loaded_tool.module_path == "path/to/tool/module"
    assert loaded_tool.description == "Testing tool load functionality"
    assert loaded_tool.parameters == {"param1": "value1"}
    assert loaded_tool.required == ["param1"]
    assert not loaded_tool.consequential


def test_agent_creation_persists_in_json(
    context: _TestContext,
    agent_store: AgentDocumentStore,
    agent_json_path: str,
) -> None:
    model_id = ModelId("default_model")

    agent = context.sync_await(
        agent_store.create_agent(
            model_id=model_id,
        )
    )

    with open(agent_json_path) as _f:
        agents_from_json = json.load(_f)

    assert len(agents_from_json) == 1
    assert "agents" in agents_from_json
    assert len(agents_from_json["agents"]) == 1
    assert agent.id in agents_from_json["agents"]
    assert agents_from_json["agents"][agent.id]["model_id"] == model_id
    assert (
        datetime.fromisoformat(agents_from_json["agents"][agent.id]["creation_utc"])
        == agent.creation_utc
    )


def test_agent_loading_from_json(
    context: _TestContext,
    agent_store: AgentDocumentStore,
) -> None:
    # Create an agent to ensure there's something to load.
    model_id = ModelId("test_model")
    context.sync_await(
        agent_store.create_agent(
            model_id=model_id,
        )
    )

    # Load agents to test retrieval
    loaded_agents = context.sync_await(agent_store.list_agents())
    loaded_agent_list = list(loaded_agents)

    assert len(loaded_agent_list) == 1
    loaded_agent = loaded_agent_list[0]
    assert loaded_agent.model_id == model_id


def test_session_creation_persists_in_json(
    context: _TestContext,
    session_store: SessionStore,
    session_json_path: str,
) -> None:
    end_user_id = EndUserId("test_user")
    client_id = "test_client"

    session = context.sync_await(
        session_store.create_session(
            end_user_id=end_user_id,
            client_id=client_id,
        )
    )

    with open(session_json_path) as _f:
        sessions_from_json = json.load(_f)

    assert session.id in sessions_from_json["sessions"]
    assert sessions_from_json["sessions"][session.id]["end_user_id"] == end_user_id
    assert sessions_from_json["sessions"][session.id]["client_id"] == client_id
    assert sessions_from_json["sessions"][session.id]["consumption_offsets"] == {
        "server": 0,
        "client": 0,
    }


def test_event_creation_and_retrieval(
    context: _TestContext,
    session_store: SessionStore,
    session_json_path: str,
) -> None:
    end_user_id = EndUserId("test_user")
    client_id = "test_client"

    session = context.sync_await(
        session_store.create_session(
            end_user_id=end_user_id,
            client_id=client_id,
        )
    )

    event = context.sync_await(
        session_store.create_event(
            session_id=session.id,
            source="client",
            type=Event.MESSAGE_TYPE,
            data={"message": "Hello, world!"},
            creation_utc=datetime.now(timezone.utc),
        )
    )

    with open(session_json_path) as _f:
        sessions_from_json = json.load(_f)

    assert event.id in sessions_from_json[f"events_{session.id}"]
    event_from_json = sessions_from_json[f"events_{session.id}"][event.id]
    assert event_from_json["type"] == Event.MESSAGE_TYPE
    assert event_from_json["data"]["message"] == "Hello, world!"
    assert event_from_json["source"] == "client"
