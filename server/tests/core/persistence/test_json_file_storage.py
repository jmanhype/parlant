from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from lagom import Container
from pytest import fixture
import pytest

from emcie.server.core.agents import AgentDocumentStore, AgentId, AgentStore
from emcie.server.core.context_variables import (
    ContextVariableDocumentStore,
    ContextVariableStore,
)
from emcie.server.core.end_users import EndUserDocumentStore, EndUserId, EndUserStore
from emcie.server.core.guidelines import (
    GuidelineDocumentStore,
    GuidelineId,
    GuidelineStore,
)
from emcie.server.core.persistence import DocumentDatabase, JSONFileDocumentDatabase
from emcie.server.core.sessions import Event, SessionDocumentStore, SessionStore
from emcie.server.core.tools import ToolDocumentStore, ToolId, ToolStore
from emcie.server.engines.alpha.guideline_tool_associations import (
    GuidelineToolAssociationDocumentStore,
)
from tests.test_utilities import SyncAwaiter

TEST_CACHE_DIR = Path(__file__).parent.resolve() / "test_cache"
AGENT_JSON_PATH = Path(os.path.join(TEST_CACHE_DIR, "test_agents.json"))
SESSION_JSON_PATH = Path(os.path.join(TEST_CACHE_DIR, "test_sessions.json"))
TOOL_JSON_PATH = Path(os.path.join(TEST_CACHE_DIR, "test_tools.json"))
GUIDELINE_JSON_PATH = Path(os.path.join(TEST_CACHE_DIR, "test_guidelines.json"))
END_USER_JSON_PATH = Path(os.path.join(TEST_CACHE_DIR, "test_end_users.json"))
CONTEXT_VARIABLES_JSON_PATH = Path(os.path.join(TEST_CACHE_DIR, "test_context_variables.json"))
GUIDELINE_TOOL_ASSOCIATION_JSON_PATH = Path(
    os.path.join(TEST_CACHE_DIR, "test_guideline_tool_associations.json")
)


@fixture
def agent_id(
    container: Container,
    sync_await: SyncAwaiter,
) -> AgentId:
    store = container[AgentStore]
    agent = sync_await(store.create_agent(name="test-agent"))
    return agent.id


@dataclass
class _TestContext:
    sync_await: SyncAwaiter
    container: Container
    agent_id: AgentId


@fixture
def context(sync_await: SyncAwaiter, container: Container, agent_id: AgentId) -> _TestContext:
    return _TestContext(sync_await, container, agent_id)


@fixture
def agent_store() -> AgentStore:
    AGENT_JSON_PATH.unlink(missing_ok=True)

    agent_db: DocumentDatabase = JSONFileDocumentDatabase(str(AGENT_JSON_PATH.resolve()))
    return AgentDocumentStore(agent_db)


@fixture
def session_store() -> SessionStore:
    SESSION_JSON_PATH.unlink(missing_ok=True)

    session_db: DocumentDatabase = JSONFileDocumentDatabase(str(SESSION_JSON_PATH.resolve()))
    return SessionDocumentStore(session_db)


@fixture
def guideline_store() -> GuidelineStore:
    GUIDELINE_JSON_PATH.unlink(missing_ok=True)

    guideline_db: DocumentDatabase = JSONFileDocumentDatabase(str(GUIDELINE_JSON_PATH.resolve()))
    return GuidelineDocumentStore(guideline_db)


@fixture
def tool_store() -> ToolStore:
    TOOL_JSON_PATH.unlink(missing_ok=True)

    tool_db: DocumentDatabase = JSONFileDocumentDatabase(str(TOOL_JSON_PATH.resolve()))
    return ToolDocumentStore(tool_db)


@fixture
def end_user_store() -> EndUserStore:
    END_USER_JSON_PATH.unlink(missing_ok=True)

    end_user_db: DocumentDatabase = JSONFileDocumentDatabase(str(END_USER_JSON_PATH.resolve()))
    return EndUserDocumentStore(end_user_db)


@fixture
def context_variable_store() -> ContextVariableStore:
    CONTEXT_VARIABLES_JSON_PATH.unlink(missing_ok=True)

    variable_db: DocumentDatabase = JSONFileDocumentDatabase(
        str(CONTEXT_VARIABLES_JSON_PATH.resolve())
    )
    return ContextVariableDocumentStore(variable_db)


@fixture
def guideline_tool_association_store() -> GuidelineToolAssociationDocumentStore:
    GUIDELINE_TOOL_ASSOCIATION_JSON_PATH.unlink(missing_ok=True)

    association_db: DocumentDatabase = JSONFileDocumentDatabase(
        str(GUIDELINE_TOOL_ASSOCIATION_JSON_PATH.resolve())
    )
    return GuidelineToolAssociationDocumentStore(association_db)


def test_agent_creation(
    context: _TestContext,
    agent_store: AgentDocumentStore,
) -> None:
    agent = context.sync_await(agent_store.create_agent(name="Test Agent"))

    with open(AGENT_JSON_PATH) as f:
        agents_from_json = json.load(f)

    assert len(agents_from_json["agents"]) == 1
    json_agent = agents_from_json["agents"][0]
    assert json_agent["id"] == agent.id
    assert json_agent["name"] == agent.name
    assert datetime.fromisoformat(json_agent["creation_utc"]) == agent.creation_utc
    AGENT_JSON_PATH.unlink()


def test_agent_retrieval(
    context: _TestContext,
    agent_store: AgentDocumentStore,
) -> None:
    agent = context.sync_await(
        agent_store.create_agent(
            name="Test Agent",
        )
    )

    loaded_agents = context.sync_await(agent_store.list_agents())
    loaded_agent_list = list(loaded_agents)

    assert len(loaded_agent_list) == 1
    loaded_agent = loaded_agent_list[0]
    assert loaded_agent.name == agent.name


def test_session_creation(
    context: _TestContext,
    session_store: SessionStore,
) -> None:
    end_user_id = EndUserId("test_user")

    session = context.sync_await(
        session_store.create_session(
            end_user_id=end_user_id,
            agent_id=context.agent_id,
        )
    )

    with open(SESSION_JSON_PATH) as f:
        sessions_from_json = json.load(f)

    assert len(sessions_from_json["sessions"]) == 1
    json_session = sessions_from_json["sessions"][0]
    assert json_session["id"] == session.id
    assert json_session["end_user_id"] == end_user_id
    assert json_session["agent_id"] == context.agent_id
    assert json_session["consumption_offsets"] == {
        "client": 0,
    }
    SESSION_JSON_PATH.unlink()


def test_event_creation(
    context: _TestContext,
    session_store: SessionStore,
) -> None:
    end_user_id = EndUserId("test_user")

    session = context.sync_await(
        session_store.create_session(
            end_user_id=end_user_id,
            agent_id=context.agent_id,
        )
    )

    event = context.sync_await(
        session_store.create_event(
            session_id=session.id,
            source="client",
            kind=Event.MESSAGE_KIND,
            data={"message": "Hello, world!"},
            creation_utc=datetime.now(timezone.utc),
        )
    )

    with open(SESSION_JSON_PATH) as f:
        events_from_json = json.load(f)

    assert len(events_from_json["events"]) == 1
    json_event = events_from_json["events"][0]
    assert json_event["kind"] == event.kind
    assert json_event["data"] == event.data
    assert json_event["source"] == event.source
    assert datetime.fromisoformat(json_event["creation_utc"]) == event.creation_utc
    SESSION_JSON_PATH.unlink()


def test_guideline_creation(
    context: _TestContext,
    guideline_store: GuidelineStore,
) -> None:

    guideline = context.sync_await(
        guideline_store.create_guideline(
            guideline_set=context.agent_id,
            predicate="Creating a guideline with JSONFileDatabase implementation",
            content="Expecting it to show in the guidelines json file",
        )
    )

    with open(GUIDELINE_JSON_PATH) as f:
        guidelines_from_json = json.load(f)

    assert len(guidelines_from_json) == 1

    json_guideline = guidelines_from_json["guidelines"][0]
    assert json_guideline["guideline_set"] == context.agent_id

    assert json_guideline["predicate"] == guideline.predicate
    assert json_guideline["content"] == guideline.content
    assert datetime.fromisoformat(json_guideline["creation_utc"]) == guideline.creation_utc

    second_guideline = context.sync_await(
        guideline_store.create_guideline(
            guideline_set=context.agent_id,
            predicate="Second guideline creation",
            content="Additional test entry in the JSON file",
        )
    )

    with open(GUIDELINE_JSON_PATH) as f:
        guidelines_from_json = json.load(f)

    assert len(guidelines_from_json["guidelines"]) == 2

    second_json_guideline = guidelines_from_json["guidelines"][1]
    assert second_json_guideline["guideline_set"] == context.agent_id

    assert second_json_guideline["predicate"] == second_guideline.predicate
    assert second_json_guideline["content"] == second_guideline.content
    assert (
        datetime.fromisoformat(second_json_guideline["creation_utc"])
        == second_guideline.creation_utc
    )
    GUIDELINE_JSON_PATH.unlink()


def test_guideline_retrieval(
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


def test_tool_creation(
    context: _TestContext,
    tool_store: ToolStore,
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

    with open(TOOL_JSON_PATH) as f:
        tools_from_json = json.load(f)

    assert len(tools_from_json) == 1
    json_tool = tools_from_json["tools"][0]

    assert json_tool["tool_set"] == context.agent_id
    assert json_tool["name"] == tool.name
    assert json_tool["module_path"] == tool.module_path
    assert json_tool["description"] == tool.description
    assert json_tool["parameters"] == tool.parameters
    assert json_tool["required"] == tool.required
    assert json_tool["consequential"] == tool.consequential
    TOOL_JSON_PATH.unlink()


def test_tool_retrieval(
    context: _TestContext,
    tool_store: ToolStore,
) -> None:
    tool = context.sync_await(
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
    assert loaded_tool == tool


def test_end_user_creation(
    context: _TestContext,
    end_user_store: EndUserStore,
) -> None:
    name = "Jane Doe"
    email = "jane.doe@example.com"

    created_user = context.sync_await(end_user_store.create_end_user(name=name, email=email))

    with open(END_USER_JSON_PATH, "r") as file:
        data = json.load(file)

    assert len(data["end_users"]) == 1
    json_end_user = data["end_users"][0]
    assert json_end_user["name"] == name
    assert json_end_user["email"] == email
    assert datetime.fromisoformat(json_end_user["creation_utc"]) == created_user.creation_utc
    END_USER_JSON_PATH.unlink()


def test_end_user_retrieval(
    context: _TestContext,
    end_user_store: EndUserStore,
) -> None:
    name = "John Doe"
    email = "john.doe@example.com"

    created_user = context.sync_await(end_user_store.create_end_user(name=name, email=email))

    retrieved_user = context.sync_await(end_user_store.read_end_user(created_user.id))

    assert created_user == retrieved_user


def test_context_variable_creation(
    context: _TestContext,
    context_variable_store: ContextVariableStore,
) -> None:
    tool_id = ToolId("test_tool")
    variable = context.sync_await(
        context_variable_store.create_variable(
            variable_set=context.agent_id,
            name="Sample Variable",
            description="A test variable for persistence.",
            tool_id=tool_id,
            freshness_rules=None,
        )
    )

    with open(CONTEXT_VARIABLES_JSON_PATH) as f:
        variables_from_json = json.load(f)

    assert len(variables_from_json["variables"]) == 1
    json_variable = variables_from_json["variables"][0]

    assert json_variable["variable_set"] == context.agent_id
    assert json_variable["name"] == variable.name
    assert json_variable["description"] == variable.description
    assert json_variable["tool_id"] == tool_id
    CONTEXT_VARIABLES_JSON_PATH.unlink()


def test_context_variable_value_update_and_retrieval(
    context: _TestContext,
    context_variable_store: ContextVariableStore,
) -> None:
    tool_id = ToolId("test_tool")
    end_user_id = EndUserId("test_user")
    variable = context.sync_await(
        context_variable_store.create_variable(
            variable_set=context.agent_id,
            name="Sample Variable",
            description="A test variable for persistence.",
            tool_id=tool_id,
            freshness_rules=None,
        )
    )

    value = context.sync_await(
        context_variable_store.update_value(
            variable_set=context.agent_id,
            key=end_user_id,
            variable_id=variable.id,
            data={"key": "value"},
        )
    )

    with open(CONTEXT_VARIABLES_JSON_PATH) as f:
        values_from_json = json.load(f)

    assert len(values_from_json["values"]) == 1
    json_value = values_from_json["values"][0]

    assert json_value["data"] == value.data
    assert json_value["variable_id"] == value.variable_id
    assert json_value["data"] == value.data
    CONTEXT_VARIABLES_JSON_PATH.unlink()


def test_context_variable_listing(
    context: _TestContext,
    context_variable_store: ContextVariableStore,
) -> None:
    tool_id = ToolId("test_tool")
    var1 = context.sync_await(
        context_variable_store.create_variable(
            variable_set=context.agent_id,
            name="Variable One",
            description="First test variable",
            tool_id=tool_id,
            freshness_rules=None,
        )
    )
    var2 = context.sync_await(
        context_variable_store.create_variable(
            variable_set=context.agent_id,
            name="Variable Two",
            description="Second test variable",
            tool_id=tool_id,
            freshness_rules=None,
        )
    )

    variables = list(context.sync_await(context_variable_store.list_variables(context.agent_id)))

    assert var1 in variables
    assert var2 in variables
    assert len(variables) == 2


def test_context_variable_deletion(
    context: _TestContext,
    context_variable_store: ContextVariableStore,
) -> None:
    tool_id = ToolId("test_tool")
    variable = context.sync_await(
        context_variable_store.create_variable(
            variable_set=context.agent_id,
            name="Deletable Variable",
            description="A variable to be deleted.",
            tool_id=tool_id,
            freshness_rules=None,
        )
    )

    value_data = {"key": "test", "data": "This is a test value"}
    context.sync_await(
        context_variable_store.update_value(
            variable_set=context.agent_id,
            key="test_user",
            variable_id=variable.id,
            data=value_data,
        )
    )

    variables_before_deletion = list(
        context.sync_await(context_variable_store.list_variables(context.agent_id))
    )
    assert any(v.id == variable.id for v in variables_before_deletion)

    value_before_deletion = context.sync_await(
        context_variable_store.read_value(
            variable_set=context.agent_id,
            key="test_user",
            variable_id=variable.id,
        )
    )
    assert value_before_deletion.data == value_data

    context.sync_await(
        context_variable_store.delete_variable(
            variable_set=context.agent_id,
            id=variable.id,
        )
    )

    variables_after_deletion = list(
        context.sync_await(context_variable_store.list_variables(context.agent_id))
    )
    assert all(var.id != variable.id for var in variables_after_deletion)

    with pytest.raises(ValueError):
        context.sync_await(
            context_variable_store.read_value(
                variable_set=context.agent_id, key="test_user", variable_id=variable.id
            )
        )


def test_guideline_tool_association_creation(
    context: _TestContext,
    guideline_tool_association_store: GuidelineToolAssociationDocumentStore,
) -> None:
    guideline_id = GuidelineId("guideline-789")
    tool_id = ToolId("tool-012")

    context.sync_await(
        guideline_tool_association_store.create_association(
            guideline_id=guideline_id, tool_id=tool_id
        )
    )

    with open(GUIDELINE_TOOL_ASSOCIATION_JSON_PATH, "r") as f:
        guideline_tool_associations_from_json = json.load(f)

    assert len(guideline_tool_associations_from_json["associations"]) == 1
    json_variable = guideline_tool_associations_from_json["associations"][0]

    assert json_variable["guideline_id"] == guideline_id
    assert json_variable["tool_id"] == tool_id
    GUIDELINE_TOOL_ASSOCIATION_JSON_PATH.unlink()


def test_guideline_tool_association_retrieval(
    context: _TestContext,
    guideline_tool_association_store: GuidelineToolAssociationDocumentStore,
) -> None:
    guideline_id = GuidelineId("test_guideline")
    tool_id = ToolId("test_tool")
    creation_utc = datetime.now(timezone.utc)

    created_association = context.sync_await(
        guideline_tool_association_store.create_association(
            guideline_id=guideline_id,
            tool_id=tool_id,
            creation_utc=creation_utc,
        )
    )

    associations = list(context.sync_await(guideline_tool_association_store.list_associations()))
    assert len(associations) == 1
    retrieved_association = list(associations)[0]

    assert retrieved_association.id == created_association.id
    assert retrieved_association.guideline_id == guideline_id
    assert retrieved_association.tool_id == tool_id
    assert retrieved_association.creation_utc == creation_utc
