from pytest_bdd import given, parsers

from parlant.core.agents import AgentId
from parlant.core.context_variables import (
    ContextVariableStore,
    ContextVariableValue,
)
from parlant.core.end_users import EndUserStore
from parlant.core.sessions import SessionId, SessionStore

from tests.core.engines.alpha.utils import ContextOfTest, step


@step(
    given, parsers.parse('a context variable "{variable_name}" with a value of "{variable_value}"')
)
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
        'a context variable "{variable_name}" with the value "{variable_value}" assigned to users with the tag "{label}"'
    ),
)
def given_a_context_variable_for_users_with_a_tag(
    context: ContextOfTest,
    variable_name: str,
    variable_value: str,
    agent_id: AgentId,
    session_id: SessionId,
    label: str,
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
            data={f"tag:{label}": variable_value},
        )
    )


@step(given, parsers.parse('the user is tagged as "{label}"'))
def given_a_user_tag(
    context: ContextOfTest,
    session_id: SessionId,
    label: str,
) -> None:
    session_store = context.container[SessionStore]
    end_user_store = context.container[EndUserStore]

    end_user_id = context.sync_await(session_store.read_session(session_id)).end_user_id

    context.sync_await(
        end_user_store.set_tag(
            end_user_id=end_user_id,
            label=label,
        )
    )
