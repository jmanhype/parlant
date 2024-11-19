from pytest_bdd import given, parsers

from parlant.core.agents import AgentId
from parlant.core.context_variables import (
    ContextVariable,
    ContextVariableStore,
    ContextVariableValue,
)
from parlant.core.end_users import EndUserStore
from parlant.core.sessions import SessionId, SessionStore

from parlant.core.tags import TagStore
from tests.core.engines.alpha.utils import ContextOfTest, step


def get_or_create_variable(
    context: ContextOfTest,
    agent_id: AgentId,
    context_variable_store: ContextVariableStore,
    variable_name: str,
) -> ContextVariable:
    variables = context.sync_await(context_variable_store.list_variables(agent_id))
    if variable := next(
        (variable for variable in variables if variable.name == variable_name), None
    ):
        return variable

    variable = context.sync_await(
        context_variable_store.create_variable(
            variable_set=agent_id,
            name=variable_name,
            description="",
            tool_id=None,
            freshness_rules=None,
        )
    )
    return variable


@step(given, parsers.parse('a context variable "{variable_name}" with a value "{variable_value}"'))
def given_a_context_variable(
    context: ContextOfTest,
    variable_name: str,
    variable_value: str,
    agent_id: AgentId,
    session_id: SessionId,
) -> ContextVariableValue:
    session_store = context.container[SessionStore]
    context_variable_store = context.container[ContextVariableStore]

    end_user_id = context.sync_await(session_store.read_session(session_id)).end_user_id

    variable = context.sync_await(
        context_variable_store.create_variable(
            variable_set=agent_id,
            name=variable_name,
            description="",
            tool_id=None,
            freshness_rules=None,
        )
    )

    return context.sync_await(
        context_variable_store.update_value(
            variable_set=agent_id,
            key=end_user_id,
            variable_id=variable.id,
            data=variable_value,
        )
    )


@step(
    given,
    parsers.parse(
        'a context variable "{variable_name}" with a value "{variable_value}" to "{end_user_name}"'
    ),
)
def given_a_context_variable_to_specific_user(
    context: ContextOfTest,
    variable_name: str,
    variable_value: str,
    end_user_name: str,
    agent_id: AgentId,
) -> ContextVariableValue:
    end_user_store = context.container[EndUserStore]
    context_variable_store = context.container[ContextVariableStore]

    end_users = context.sync_await(end_user_store.list_end_users())

    end_user = next(user for user in end_users if user.name == end_user_name)

    variable = get_or_create_variable(context, agent_id, context_variable_store, variable_name)

    return context.sync_await(
        context_variable_store.update_value(
            variable_set=agent_id,
            key=end_user.id,
            variable_id=variable.id,
            data=variable_value,
        )
    )


@step(
    given,
    parsers.parse(
        'a context variable "{variable_name}" with a value "{variable_value}" to tag "{label}"'
    ),
)
def given_a_context_variable_for_a_tag(
    context: ContextOfTest,
    variable_name: str,
    variable_value: str,
    agent_id: AgentId,
    label: str,
) -> ContextVariableValue:
    context_variable_store = context.container[ContextVariableStore]
    tag_store = context.container[TagStore]

    tag = next(t for t in context.sync_await(tag_store.list_tags()) if t.label == label)

    variable = context.sync_await(
        context_variable_store.create_variable(
            variable_set=agent_id,
            name=variable_name,
            description="",
            tool_id=None,
            freshness_rules=None,
        )
    )

    return context.sync_await(
        context_variable_store.update_value(
            variable_set=agent_id,
            key=f"tag:{tag.id}",
            variable_id=variable.id,
            data=variable_value,
        )
    )
