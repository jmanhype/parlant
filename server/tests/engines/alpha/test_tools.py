import json
from typing import Any
from lagom import Container
from pytest_bdd import scenarios, given, when, then, parsers

from emcie.server.core.agents import AgentId, AgentStore
from emcie.server.core.tools import Tool, ToolId, ToolStore
from emcie.server.engines.alpha.engine import AlphaEngine
from emcie.server.engines.alpha.guideline_tool_association import (
    GuidelineToolAssociation,
    GuidelineToolAssociationStore,
)
from emcie.server.engines.alpha.utils import produced_tools_event_to_dict
from emcie.server.engines.common import Context, ProducedEvent
from emcie.server.core.guidelines import Guideline, GuidelineId, GuidelineStore
from emcie.server.core.sessions import Event, SessionId, SessionStore

from tests import tools_utilities
from tests.test_utilities import SyncAwaiter, nlp_test

scenarios(
    "engines/alpha/tools/single_tool_event.feature",
    "engines/alpha/tools/multiple_tool_events.feature",
)


@given("the alpha engine", target_fixture="engine")
def given_the_alpha_engine(
    container: Container,
) -> AlphaEngine:
    return AlphaEngine(
        session_store=container[SessionStore],
        guideline_store=container[GuidelineStore],
        tool_store=container[ToolStore],
        guideline_tool_association_store=container[GuidelineToolAssociationStore],
    )


@given("an agent", target_fixture="agent_id")
def given_an_agent(
    sync_await: SyncAwaiter,
    container: Container,
) -> AgentId:
    store = container[AgentStore]
    agent = sync_await(store.create_agent())
    return agent.id


@given("an empty session", target_fixture="session_id")
def given_an_empty_session(
    sync_await: SyncAwaiter,
    container: Container,
) -> SessionId:
    store = container[SessionStore]
    session = sync_await(store.create_session(client_id="my_client"))
    return session.id


@given("a diverse selection of guidelines", target_fixture="guidelines")
def given_guidelines() -> dict[str, dict[str, str]]:
    return {
        "check_drinks_in_stock": {
            "predicate": "a client asks for a drink",
            "content": "check if the drink is available in stock",
        },
        "check_toppings_in_stock": {
            "predicate": "a client asks about toppings or order pizza with toppings",
            "content": "check what toppings are available in stock",
        },
        "ask_expert_about_Spot": {
            "predicate": "a client asks for information about Spot",
            "content": "ask and get the answer from the expert",
        },
        "check_toppings_or_drinks_in_stock": {
            "predicate": "a client asks for toppings or drinks",
            "content": "check if they are available in stock",
        },
        "calculate_sum": {
            "predicate": "an equation involves adding numbers",
            "content": "calculate the sum",
        },
        "check_drinks_or_toppings_in_stock": {
            "predicate": "a client asks for a drink or toppings",
            "content": "check what drinks or toppings are available in stock",
        },
        "calculate_addition_or_multiplication": {
            "predicate": "an equation contains addition or multiplication",
            "content": "calculate it",
        },
        "retrieve_account_information": {
            "predicate": "asked for information about an account",
            "content": "answer by retrieving the information from the database",
        },
        "calculate_addition": {
            "predicate": "an equation contains an add function",
            "content": "get the result from the add tool",
        },
        "calculate_multiplication": {
            "predicate": "an equation contains a multiply function",
            "content": "get the result from the multiply tool",
        },
        "transfer_money_between_accounts": {
            "predicate": "asked to transfer money from one account to another",
            "content": "check if the account has enough balance to make the transfer"
            "and then proceed with the transfer",
        },
        "retrieve_Spot_information": {
            "predicate": "asked for information about Spot",
            "content": "answer by retrieving the information from the database",
        },
        "retrieve_account_balance": {
            "predicate": "asked for information about an account",
            "content": "answer by retrieving the information from the database",
        },
    }


@given("a diverse selection of tools", target_fixture="tools")
def given_tools() -> dict[str, Any]:
    return {
        "get_available_drinks": {
            "name": "get_available_drinks",
            "description": "Get the drinks available in stock",
            "module_path": "tests.tools_utilities",
            "parameters": {},
            "required": [],
        },
        "get_available_toppings": {
            "name": "get_available_toppings",
            "description": "Get the toppings available in stock",
            "module_path": "tests.tools_utilities",
            "parameters": {},
            "required": [],
        },
        "expert_answer": {
            "name": "expert_answer",
            "description": "Get answers to questions by consulting documentation",
            "module_path": "tests.tools_utilities",
            "parameters": {
                "user_query": {"type": "string", "description": "The query from the user"}
            },
            "required": ["user_query"],
        },
        "get_available_product_by_type": {
            "name": "get_available_product_by_type",
            "description": "Get the products available in stock by type",
            "module_path": "tests.tools_utilities",
            "parameters": {
                "product_type": {
                    "product_type": "string",
                    "description": "The type of product (either 'drinks' or 'toppings')",
                    "enum": ["drinks", "toppings"],
                }
            },
            "required": ["product_type"],
        },
        "add": {
            "name": "add",
            "description": "Getting the addition calculation between two numbers",
            "module_path": "tests.tools_utilities",
            "parameters": {
                "first_number": {"type": "number", "description": "The first number"},
                "second_number": {"type": "number", "description": "The second number"},
            },
            "required": ["first_number", "second_number"],
        },
        "multiply": {
            "name": "multiply",
            "description": "Getting the multiplication calculation between two numbers",
            "module_path": "tests.tools_utilities",
            "parameters": {
                "first_number": {"type": "number", "description": "The first number"},
                "second_number": {"type": "number", "description": "The second number"},
            },
            "required": ["first_number", "second_number"],
        },
        "get_account_balance": {
            "name": "get_account_balance",
            "description": "Get the account balance by given name",
            "module_path": "tests.tools_utilities",
            "parameters": {
                "account_name": {"type": "string", "description": "The name of the account"}
            },
            "required": ["account_name"],
        },
        "get_account_loans": {
            "name": "get_account_loans",
            "description": "Get the account loans by given name",
            "module_path": "tests.tools_utilities",
            "parameters": {
                "account_name": {"type": "string", "description": "The name of the account"}
            },
            "required": ["account_name"],
        },
        "transfer_money": {
            "name": "transfer_money",
            "description": "Transfer money from one account to another",
            "module_path": "tests.tools_utilities",
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


@given(parsers.parse("{guideline_name} guideline"))
def given_a_guideline(
    sync_await: SyncAwaiter,
    container: Container,
    guidelines: dict[str, dict[str, str]],
    agent_id: AgentId,
    guideline_name: str,
) -> Guideline:
    guideline_store = container[GuidelineStore]

    async def create_guideline(predicate: str, content: str) -> Guideline:
        return await guideline_store.create_guideline(
            guideline_set=agent_id,
            predicate=predicate,
            content=content,
        )

    return sync_await(create_guideline(**guidelines[guideline_name]))


@given(parsers.parse("{tool_name} tool"))
def given_a_tool(
    sync_await: SyncAwaiter,
    container: Container,
    tools: dict[str, Any],
    agent_id: AgentId,
    tool_name: str,
) -> Tool:
    tool_store = container[ToolStore]

    async def create_tool(
        name: str,
        module_path: str,
        description: str,
        parameters: dict[str, Any],
        required: list[str],
    ) -> Tool:
        return await tool_store.create_tool(
            tool_set=agent_id,
            name=name,
            module_path=module_path,
            description=description,
            parameters=parameters,
            required=required,
        )

    return sync_await(create_tool(**tools[tool_name]))


@given(parsers.parse("an association between {tool_name} and {guideline_name}"))
def given_guideline_tool_association(
    sync_await: SyncAwaiter,
    container: Container,
    agent_id: AgentId,
    guidelines: dict[str, dict[str, str]],
    tool_name: str,
    guideline_name: str,
) -> GuidelineToolAssociation:
    guideline_tool_association_store = container[GuidelineToolAssociationStore]

    async def create_guideline_tool_association(
        guideline_id: GuidelineId,
        tool_id: ToolId,
    ) -> GuidelineToolAssociation:
        return await guideline_tool_association_store.create_guideline_tool_association(
            guideline_id=guideline_id,
            tool_id=tool_id,
        )

    async def get_guideline(
        predicate: str,
        content: str,
    ) -> Guideline:
        guidelines_store = container[GuidelineStore]
        guidelines_objects = await guidelines_store.list_guidelines(agent_id)
        for guideline in guidelines_objects:
            if guideline.predicate == predicate and guideline.content == content:
                return guideline
        raise ValueError

    async def get_tool(
        tool_name: str,
    ) -> Tool:
        tools_store = container[ToolStore]
        tools = await tools_store.list_tools(agent_id)
        for tool in tools:
            if tool.name == tool_name:
                return tool
        raise ValueError

    tool = sync_await(get_tool(tool_name))
    guideline = sync_await(get_guideline(**guidelines[guideline_name]))

    return sync_await(create_guideline_tool_association(guideline.id, tool.id))


@given(parsers.parse("a user message of {user_message}"), target_fixture="session_id")
def given_a_session_user_message(
    sync_await: SyncAwaiter,
    container: Container,
    session_id: SessionId,
    user_message: str,
) -> SessionId:
    store = container[SessionStore]
    session = sync_await(store.read_session(session_id=session_id))

    sync_await(
        store.create_event(
            session_id=session.id,
            source="client",
            type=Event.MESSAGE_TYPE,
            data={"message": user_message},
        )
    )

    return session.id


@given(
    parsers.parse("a server message of {server_message}"),
    target_fixture="session_id",
)
def given_a_session_with_server_message(
    sync_await: SyncAwaiter,
    container: Container,
    server_message: str,
    session_id: SessionId,
) -> SessionId:
    store = container[SessionStore]
    session = sync_await(store.read_session(session_id=session_id))

    sync_await(
        store.create_event(
            session_id=session.id,
            source="server",
            type=Event.MESSAGE_TYPE,
            data={"message": server_message},
        )
    )

    return session.id


@given(
    parsers.parse("a tool event with data of {tool_event_data}"),
    target_fixture="session_id",
)
def given_a_session_with_tool_event(
    sync_await: SyncAwaiter,
    container: Container,
    session_id: SessionId,
    tool_event_data: str,
) -> SessionId:
    store = container[SessionStore]
    session = sync_await(store.read_session(session_id=session_id))

    sync_await(
        store.create_event(
            session_id=session.id,
            source="server",
            type=Event.TOOL_TYPE,
            data=json.loads(tool_event_data),
        )
    )

    return session.id


@when("processing is triggered", target_fixture="produced_events")
def when_processing_is_triggered(
    sync_await: SyncAwaiter,
    engine: AlphaEngine,
    agent_id: AgentId,
    session_id: SessionId,
) -> list[ProducedEvent]:
    events = sync_await(
        engine.process(
            Context(
                session_id=session_id,
                agent_id=agent_id,
            )
        )
    )

    return list(events)


@then("no tool events are produced")
def then_no_tools_events_are_produced(
    produced_events: list[ProducedEvent],
) -> None:
    assert produced_events[0].type == Event.MESSAGE_TYPE


@then(parsers.parse("{tool_events_expeceted:d} tool events got produced"))
def then_verify_correct_number_of_tool_events_produced(
    produced_events: list[ProducedEvent],
    tool_events_expeceted: int,
) -> None:
    assert (
        len(list(filter(lambda e: e.type == Event.MESSAGE_TYPE, produced_events)))
        == tool_events_expeceted
    )


@then("a single tool event is produced")
def then_a_single_tool_event_is_produced(
    produced_events: list[ProducedEvent],
) -> None:
    assert len(list(filter(lambda e: e.type == Event.TOOL_TYPE, produced_events))) == 1


@then(
    parsers.parse(
        "a {tool_event_name} tool event is produced in tool event number {tool_event_number:d}"
    )
)
def then_drinks_available_in_stock_tool_event_is_produced(
    produced_events: list[ProducedEvent],
    tool_event_name: str,
    tool_event_number: int,
) -> None:
    results = produced_tools_event_to_dict(produced_events[tool_event_number - 1])["data"]

    tools_names = {
        "drinks-available-in-stock": "get_available_drinks",
        "toppings-available-in-stock": "get_available_toppings",
    }

    tool_event_functions = {
        "drinks-available-in-stock": tools_utilities.get_available_drinks,
        "toppings-available-in-stock": tools_utilities.get_available_toppings,
    }

    assert {
        "tool_name": tools_names[tool_event_name],
        "parameters": {},
        "result": tool_event_functions[tool_event_name](),
    } in results


@then(
    parsers.parse(
        "a tool event for product availability of {product_type} is generated "
        "at tool event number {tool_event_number:d}"
    )
)
def then_product_availability_for_toppings_and_drinks_tools_event_is_produced(
    produced_events: list[ProducedEvent],
    product_type: str,
    tool_event_number: int,
) -> None:
    types_functions = {
        "drinks": tools_utilities.get_available_drinks,
        "toppings": tools_utilities.get_available_toppings,
    }
    results = produced_tools_event_to_dict(produced_events[tool_event_number - 1])["data"]
    assert {
        "tool_name": "get_available_product_by_type",
        "parameters": {"product_type": product_type},
        "result": types_functions[product_type](),
    } in results


@then(
    parsers.parse(
        "an add tool event is produced with {first_num:d}, {second_num:d} numbers in "
        "tool event number {tool_event_number:d}"
    )
)
def then_add_tool_event_is_produced(
    produced_events: list[ProducedEvent],
    first_num: int,
    second_num: int,
    tool_event_number: int,
) -> None:
    results = produced_tools_event_to_dict(produced_events[tool_event_number - 1])["data"]

    assert {
        "tool_name": "add",
        "parameters": {
            "first_number": first_num,
            "second_number": second_num,
        },
        "result": tools_utilities.add(first_num, second_num),
    } in results


@then(
    parsers.parse(
        "a multiply tool event is produced with {first_num:d}, {second_num:d} "
        "numbers in tool event number {tool_event_number:d}"
    )
)
def then_multiply_tool_event_is_produced(
    produced_events: list[ProducedEvent],
    first_num: int,
    second_num: int,
    tool_event_number: int,
) -> None:
    results = produced_tools_event_to_dict(produced_events[tool_event_number - 1])["data"]

    assert {
        "tool_name": "multiply",
        "parameters": {
            "first_number": first_num,
            "second_number": second_num,
        },
        "result": tools_utilities.multiply(first_num, second_num),
    } in results


@then(
    parsers.parse(
        "a get balance account tool event is produced for the {name} account "
        "in tool event number {tool_event_number:d}"
    )
)
def then_get_balance_account_tool_event_is_produced(
    produced_events: list[ProducedEvent],
    name: str,
    tool_event_number: int,
) -> None:
    results = produced_tools_event_to_dict(produced_events[tool_event_number - 1])["data"]

    assert {
        "tool_name": "get_account_balance",
        "parameters": {
            "account_name": name,
        },
        "result": tools_utilities.get_account_balance(name),
    } in results


@then(
    "a get account loans tool event is produced for {name} "
    "in tool event number {tool_event_number:d}"
)
def then_get_account_loans_tool_event_is_produced(
    produced_events: list[ProducedEvent],
    name: str,
    tool_event_number: int,
) -> None:
    results = produced_tools_event_to_dict(produced_events[tool_event_number - 1])["data"]

    assert {
        "tool_name": "get_account_loans",
        "parameters": {
            "account_name": name,
        },
        "result": tools_utilities.get_account_loans(name),
    } in results


@then(parsers.parse("the message contains {something}"))
def then_the_message_contains(
    produced_events: list[ProducedEvent],
    something: str,
) -> None:
    message = produced_events[-1].data["message"]

    assert nlp_test(
        context=message,
        predicate=f"the text contains {something}",
    )
