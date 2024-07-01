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

JSON_TEST_FILES_PATH = "tests/engines/alpha/persistence/json_test_files/"


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
def agent_json_path() -> str:
    return os.path.join(JSON_TEST_FILES_PATH, "test_agents.json")


@fixture
def session_json_path() -> str:
    return os.path.join(JSON_TEST_FILES_PATH, "test_sessions.json")


@fixture
def tool_json_path() -> str:
    return os.path.join(JSON_TEST_FILES_PATH, "test_tools.json")


@fixture
def guideline_json_path() -> str:
    return os.path.join(JSON_TEST_FILES_PATH, "test_guidelines.json")


@fixture
def end_user_json_path() -> str:
    return os.path.join(JSON_TEST_FILES_PATH, "test_end_users.json")


@fixture
def context_variables_json_path() -> str:
    return os.path.join(JSON_TEST_FILES_PATH, "test_context_variables.json")


@fixture
def association_json_path() -> str:
    return os.path.join(JSON_TEST_FILES_PATH, "test_guideline_tool_associations.json")


@fixture
def agent_store(agent_json_path: str) -> AgentStore:
    file_path = Path(agent_json_path)
    file_path.unlink(missing_ok=True)
    agent_db: DocumentDatabase = JSONFileDocumentDatabase(agent_json_path)
    return AgentDocumentStore(agent_db)


@fixture
def session_store(
    session_json_path: str,
) -> SessionStore:
    session_file_path = Path(session_json_path)
    session_file_path.unlink(missing_ok=True)

    session_db: DocumentDatabase = JSONFileDocumentDatabase(session_json_path)
    return SessionDocumentStore(session_db)


@fixture
def guideline_store(guideline_json_path: str) -> GuidelineStore:
    file_path = Path(guideline_json_path)
    file_path.unlink(missing_ok=True)
    guideline_db: DocumentDatabase = JSONFileDocumentDatabase(guideline_json_path)
    return GuidelineDocumentStore(guideline_db)


@fixture
def tool_store(tool_json_path: str) -> ToolStore:
    file_path = Path(tool_json_path)
    file_path.unlink(missing_ok=True)
    tool_db: DocumentDatabase = JSONFileDocumentDatabase(tool_json_path)
    return ToolDocumentStore(tool_db)


@fixture
def end_user_store(end_user_json_path: str) -> EndUserStore:
    file_path = Path(end_user_json_path)
    file_path.unlink(missing_ok=True)
    end_user_db: DocumentDatabase = JSONFileDocumentDatabase(end_user_json_path)
    return EndUserDocumentStore(end_user_db)


@fixture
def context_variable_store(
    context_variables_json_path: str,
) -> ContextVariableStore:
    file_path = Path(context_variables_json_path)
    file_path.unlink(missing_ok=True)

    variable_db: DocumentDatabase = JSONFileDocumentDatabase(context_variables_json_path)
    return ContextVariableDocumentStore(variable_db)


@fixture
def association_store(association_json_path: str) -> GuidelineToolAssociationDocumentStore:
    file_path = Path(association_json_path)
    file_path.unlink(missing_ok=True)
    association_db: DocumentDatabase = JSONFileDocumentDatabase(association_json_path)
    return GuidelineToolAssociationDocumentStore(association_db)


def test_agent_creation(
    context: _TestContext,
    agent_store: AgentDocumentStore,
    agent_json_path: str,
) -> None:
    agent = context.sync_await(agent_store.create_agent(name="Test Agent"))

    with open(agent_json_path) as _f:
        agents_from_json = json.load(_f)

    assert len(agents_from_json["agents"]) == 1
    json_agent = agents_from_json["agents"][0]
    assert json_agent["id"] == agent.id
    assert json_agent["name"] == agent.name
    assert datetime.fromisoformat(json_agent["creation_utc"]) == agent.creation_utc


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
    session_json_path: str,
) -> None:
    end_user_id = EndUserId("test_user")

    session = context.sync_await(
        session_store.create_session(
            end_user_id=end_user_id,
            agent_id=context.agent_id,
        )
    )

    with open(session_json_path) as _f:
        sessions_from_json = json.load(_f)

    assert len(sessions_from_json["sessions"]) == 1
    json_session = sessions_from_json["sessions"][0]
    assert json_session["id"] == session.id
    assert json_session["end_user_id"] == end_user_id
    assert json_session["agent_id"] == context.agent_id
    assert json_session["consumption_offsets"] == {
        "client": 0,
    }


def test_event_creation(
    context: _TestContext,
    session_store: SessionStore,
    session_json_path: str,
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
            kind=Event.MESSAGE_TYPE,
            data={"message": "Hello, world!"},
            creation_utc=datetime.now(timezone.utc),
        )
    )

    with open(session_json_path) as _f:
        events_from_json = json.load(_f)

    assert len(events_from_json["events"]) == 1
    json_event = events_from_json["events"][0]
    assert json_event["kind"] == event.kind
    assert json_event["data"] == event.data
    assert json_event["source"] == event.source
    assert datetime.fromisoformat(json_event["creation_utc"]) == event.creation_utc


def test_guideline_creation(
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

    with open(guideline_json_path) as _f:
        guidelines_from_json = json.load(_f)

    assert len(guidelines_from_json["guidelines"]) == 2

    second_json_guideline = guidelines_from_json["guidelines"][1]
    assert second_json_guideline["guideline_set"] == context.agent_id

    assert second_json_guideline["predicate"] == second_guideline.predicate
    assert second_json_guideline["content"] == second_guideline.content
    assert (
        datetime.fromisoformat(second_json_guideline["creation_utc"])
        == second_guideline.creation_utc
    )


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
    json_tool = tools_from_json["tools"][0]

    assert json_tool["tool_set"] == context.agent_id
    assert json_tool["name"] == tool.name
    assert json_tool["module_path"] == tool.module_path
    assert json_tool["description"] == tool.description
    assert json_tool["parameters"] == tool.parameters
    assert json_tool["required"] == tool.required
    assert json_tool["consequential"] == tool.consequential


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
    end_user_json_path: str,
) -> None:
    name = "Jane Doe"
    email = "jane.doe@example.com"

    created_user = context.sync_await(end_user_store.create_end_user(name=name, email=email))

    with open(end_user_json_path, "r") as file:
        data = json.load(file)

    assert len(data["end_users"]) == 1
    json_end_user = data["end_users"][0]
    assert json_end_user["name"] == name
    assert json_end_user["email"] == email
    assert datetime.fromisoformat(json_end_user["creation_utc"]) == created_user.creation_utc


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
    context_variables_json_path: str,
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

    with open(context_variables_json_path) as _f:
        variables_from_json = json.load(_f)

    assert len(variables_from_json["variables"]) == 1
    json_variable = variables_from_json["variables"][0]

    assert json_variable["variable_set"] == context.agent_id
    assert json_variable["name"] == variable.name
    assert json_variable["description"] == variable.description
    assert json_variable["tool_id"] == tool_id


def test_context_variable_value_update_and_retrieval(
    context: _TestContext,
    context_variable_store: ContextVariableStore,
    context_variables_json_path: str,
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

    with open(context_variables_json_path) as _f:
        values_from_json = json.load(_f)

    assert len(values_from_json["values"]) == 1
    json_value = values_from_json["values"][0]

    assert json_value["data"] == value.data
    assert json_value["variable_id"] == value.variable_id
    assert json_value["data"] == value.data


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


def test_association_creation(
    context: _TestContext,
    association_store: GuidelineToolAssociationDocumentStore,
    association_json_path: Path,
) -> None:
    guideline_id = GuidelineId("guideline-789")
    tool_id = ToolId("tool-012")

    context.sync_await(
        association_store.create_association(guideline_id=guideline_id, tool_id=tool_id)
    )

    with open(association_json_path, "r") as _f:
        associations_from_json = json.load(_f)

    assert len(associations_from_json["associations"]) == 1
    json_variable = associations_from_json["associations"][0]

    assert json_variable["guideline_id"] == guideline_id
    assert json_variable["tool_id"] == tool_id


def test_association_retrieval(
    context: _TestContext,
    association_store: GuidelineToolAssociationDocumentStore,
) -> None:
    guideline_id = GuidelineId("test_guideline")
    tool_id = ToolId("test_tool")
    creation_utc = datetime.now(timezone.utc)

    created_association = context.sync_await(
        association_store.create_association(
            guideline_id=guideline_id,
            tool_id=tool_id,
            creation_utc=creation_utc,
        )
    )

    associations = list(context.sync_await(association_store.list_associations()))
    assert len(associations) == 1
    retrieved_association = list(associations)[0]

    assert retrieved_association.id == created_association.id
    assert retrieved_association.guideline_id == guideline_id
    assert retrieved_association.tool_id == tool_id
    assert retrieved_association.creation_utc == creation_utc
