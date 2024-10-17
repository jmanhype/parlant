from typing import Any
from pytest_bdd import given, parsers

from emcie.common.tools import Tool
from emcie.server.core.agents import AgentId, AgentStore
from emcie.server.core.guideline_tool_associations import (
    GuidelineToolAssociation,
    GuidelineToolAssociationStore,
)
from emcie.server.core.guidelines import GuidelineStore
from emcie.server.core.tools import LocalToolService, MultiplexedToolService

from tests.core.engines.alpha.utils import ContextOfTest, step


@step(given, parsers.parse('an association between "{guideline_name}" and "{tool_name}"'))
def given_a_guideline_tool_association(
    context: ContextOfTest,
    tool_name: str,
    guideline_name: str,
) -> GuidelineToolAssociation:
    guideline_tool_association_store = context.container[GuidelineToolAssociationStore]

    return context.sync_await(
        guideline_tool_association_store.create_association(
            guideline_id=context.guidelines[guideline_name].id,
            tool_id=context.tools[tool_name].id,
        )
    )


@step(
    given,
    parsers.parse('a guideline "{guideline_name}" to {do_something} when {a_condition_holds}'),
)
def given_a_guideline_name_to_when(
    context: ContextOfTest,
    guideline_name: str,
    do_something: str,
    a_condition_holds: str,
    agent_id: AgentId,
) -> None:
    guideline_store = context.container[GuidelineStore]

    context.guidelines[guideline_name] = context.sync_await(
        guideline_store.create_guideline(
            guideline_set=agent_id,
            predicate=a_condition_holds,
            action=do_something,
        )
    )


@step(given, parsers.parse('the tool "{tool_name}"'))
def given_a_tool(
    context: ContextOfTest,
    tool_name: str,
) -> None:
    tool_store = context.container[LocalToolService]

    async def create_tool(
        name: str,
        module_path: str,
        description: str,
        parameters: dict[str, Any],
        required: list[str],
    ) -> Tool:
        return await tool_store.create_tool(
            name=name,
            module_path=module_path,
            description=description,
            parameters=parameters,
            required=required,
        )

    tools: dict[str, dict[str, Any]] = {
        "get_terrys_offering": {
            "name": "get_terrys_offering",
            "description": "Explain Terry's offering",
            "module_path": "tests.tool_utilities",
            "parameters": {},
            "required": [],
        },
        "get_available_drinks": {
            "name": "get_available_drinks",
            "description": "Get the drinks available in stock",
            "module_path": "tests.tool_utilities",
            "parameters": {},
            "required": [],
        },
        "get_available_toppings": {
            "name": "get_available_toppings",
            "description": "Get the toppings available in stock",
            "module_path": "tests.tool_utilities",
            "parameters": {},
            "required": [],
        },
        "expert_answer": {
            "name": "expert_answer",
            "description": "Get answers to questions by consulting documentation",
            "module_path": "tests.tool_utilities",
            "parameters": {
                "user_query": {"type": "string", "description": "The query from the user"}
            },
            "required": ["user_query"],
        },
        "get_available_product_by_type": {
            "name": "get_available_product_by_type",
            "description": "Get the products available in stock by type",
            "module_path": "tests.tool_utilities",
            "parameters": {
                "product_type": {
                    "type": "string",
                    "description": "The type of product (either 'drinks' or 'toppings')",
                    "enum": ["drinks", "toppings"],
                }
            },
            "required": ["product_type"],
        },
        "add": {
            "name": "add",
            "description": "Getting the addition calculation between two numbers",
            "module_path": "tests.tool_utilities",
            "parameters": {
                "first_number": {"type": "number", "description": "The first number"},
                "second_number": {"type": "number", "description": "The second number"},
            },
            "required": ["first_number", "second_number"],
        },
        "multiply": {
            "name": "multiply",
            "description": "Getting the multiplication calculation between two numbers",
            "module_path": "tests.tool_utilities",
            "parameters": {
                "first_number": {"type": "number", "description": "The first number"},
                "second_number": {"type": "number", "description": "The second number"},
            },
            "required": ["first_number", "second_number"],
        },
        "get_account_balance": {
            "name": "get_account_balance",
            "description": "Get the account balance by given name",
            "module_path": "tests.tool_utilities",
            "parameters": {
                "account_name": {"type": "string", "description": "The name of the account"}
            },
            "required": ["account_name"],
        },
        "get_account_loans": {
            "name": "get_account_loans",
            "description": "Get the account loans by given name",
            "module_path": "tests.tool_utilities",
            "parameters": {
                "account_name": {"type": "string", "description": "The name of the account"}
            },
            "required": ["account_name"],
        },
        "transfer_money": {
            "name": "transfer_money",
            "description": "Transfer money from one account to another",
            "module_path": "tests.tool_utilities",
            "parameters": {
                "from_account": {
                    "type": "string",
                    "description": "The account from which money will be transferred",
                },
                "to_account": {
                    "type": "string",
                    "description": "The account to which money will be transferred",
                },
            },
            "required": ["from_account", "to_account"],
        },
    }

    tool = context.sync_await(create_tool(**tools[tool_name]))

    multiplexed_tool_service = context.container[MultiplexedToolService]

    context.tools[tool_name] = context.sync_await(
        multiplexed_tool_service.read_tool(
            tool.id, next(iter(multiplexed_tool_service.services.keys()))
        )
    )


@step(given, parsers.parse("an agent with a maximum of {max_engine_iterations} engine iteration"))
def given_max_engine_iteration(
    context: ContextOfTest,
    agent_id: AgentId,
    max_engine_iterations: str,
) -> None:
    agent_store = context.container[AgentStore]

    context.sync_await(
        agent_store.update_agent(
            agent_id=agent_id,
            params={"max_engine_iterations": int(max_engine_iterations)},
        )
    )
