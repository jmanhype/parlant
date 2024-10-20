import asyncio
import os
import signal
import traceback
import httpx

from emcie.common.tools import ToolContext, ToolResult
from emcie.common.plugin import PluginServer, tool

from emcie.server.core.async_utils import Timeout
from emcie.server.core.agents import Agent

from tests.e2e.test_utilities import (
    SERVER_ADDRESS,
    _Guideline,
    ContextOfTest,
    find_guideline,
    read_guideline_config,
    read_loaded_guidelines,
    run_server,
    write_guideline_config,
    write_service_config,
)
from tests.test_utilities import nlp_test


REASONABLE_AMOUNT_OF_TIME = 5
EXTENDED_AMOUNT_OF_TIME = 10


async def get_first_agent() -> Agent:
    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=httpx.Timeout(30),
    ) as client:
        try:
            agents_response = await client.get(
                f"{SERVER_ADDRESS}/agents/",
            )
            agents_response.raise_for_status()

            assert len(agents_response.json()["agents"]) > 0
            agent = agents_response.json()["agents"][0]

            return Agent(
                id=agent["id"],
                name=agent["name"],
                description=agent["description"],
                creation_utc=agent["creation_utc"],
                max_engine_iterations=agent["max_engine_iterations"],
            )
        except:
            traceback.print_exc()
            raise


async def get_agent_replies(
    context: ContextOfTest,
    message: str,
    number_of_replies_to_expect: int,
    agent: Agent,
) -> list[str]:
    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=httpx.Timeout(30),
    ) as client:
        try:
            session_creation_response = await client.post(
                f"{SERVER_ADDRESS}/sessions",
                json={
                    "end_user_id": "test_user",
                    "agent_id": agent.id,
                },
            )
            session_creation_response.raise_for_status()
            session_id = session_creation_response.json()["session"]["id"]

            await asyncio.sleep(REASONABLE_AMOUNT_OF_TIME)

            user_message_response = await client.post(
                f"{SERVER_ADDRESS}/sessions/{session_id}/events",
                json={
                    "content": message,
                },
            )
            user_message_response.raise_for_status()
            user_message_offset = int(user_message_response.json()["event_offset"])

            last_known_offset = user_message_offset

            replies: list[str] = []
            timeout = Timeout(300)

            while len(replies) < number_of_replies_to_expect:
                response = await client.get(
                    f"{SERVER_ADDRESS}/sessions/{session_id}/events",
                    params={
                        "min_offset": last_known_offset + 1,
                        "kinds": "message",
                        "wait": True,
                    },
                )
                response.raise_for_status()
                events = response.json()["events"]

                if message_events := [e for e in events if e["kind"] == "message"]:
                    replies.append(str(message_events[0]["data"]["message"]))

                last_known_offset = events[-1]["offset"]

                if timeout.expired():
                    raise TimeoutError()

            return replies
        except:
            traceback.print_exc()
            raise


async def test_that_the_server_starts_and_shuts_down_cleanly_on_interrupt(
    context: ContextOfTest,
) -> None:
    with run_server(context) as server_process:
        await asyncio.sleep(REASONABLE_AMOUNT_OF_TIME)
        server_process.send_signal(signal.SIGINT)
        server_process.wait(timeout=REASONABLE_AMOUNT_OF_TIME)
        assert server_process.returncode == os.EX_OK


async def test_that_the_server_hot_reloads_guideline_changes(
    context: ContextOfTest,
) -> None:
    with run_server(context, extra_args=["--no-index", "--force"]):
        initial_guidelines = read_guideline_config(context.config_file)

        new_guideline: _Guideline = {
            "when": "talking about bananas",
            "then": "say they're very tasty",
        }

        write_guideline_config(
            new_guidelines=initial_guidelines + [new_guideline],
            config_file=context.config_file,
        )

        await asyncio.sleep(REASONABLE_AMOUNT_OF_TIME)

        loaded_guidelines = read_loaded_guidelines(context.home_dir)

        assert find_guideline(new_guideline, within=loaded_guidelines)

        agent = await get_first_agent()

        agent_replies = await get_agent_replies(
            context,
            message="what are bananas?",
            agent=agent,
            number_of_replies_to_expect=1,
        )

        assert await nlp_test(
            agent_replies[0],
            "It says that bananas are very tasty",
        )


async def test_that_the_server_loads_and_interacts_with_a_plugin(
    context: ContextOfTest,
) -> None:
    @tool(id="about_dor", name="about_dor")
    async def about_dor(context: ToolContext) -> ToolResult:
        """Gets information about Dor"""
        await context.emit_message("Dor makes the worst pizza")
        await asyncio.sleep(1)
        return ToolResult("Dor makes great pizza", {"metadata_item": 123})

    plugin_port = 8090

    write_service_config(
        [
            {
                "type": "plugin",
                "name": "my_plugin",
                "url": f"http://localhost:{plugin_port}",
            }
        ],
        context.config_file,
    )

    write_guideline_config(
        [
            {
                "when": "the user says hello",
                "then": "tell the user about Dor",
                "enabled_tools": ["my_plugin__about_dor"],
            }
        ],
        config_file=context.config_file,
    )

    async with PluginServer(tools=[about_dor], port=plugin_port) as plugin_server:
        try:
            with run_server(context, extra_args=["--no-index", "--force"]):
                await asyncio.sleep(REASONABLE_AMOUNT_OF_TIME)

                agent = await get_first_agent()

                agent_replies = await get_agent_replies(
                    context,
                    message="Hello",
                    agent=agent,
                    number_of_replies_to_expect=2,
                )

                assert await nlp_test(
                    agent_replies[0],
                    "It says that Dor makes the worst pizza",
                )

                assert await nlp_test(
                    agent_replies[1],
                    "It says that Dor makes great pizza",
                )

        finally:
            await plugin_server.shutdown()


async def test_that_the_server_starts_when_there_are_no_state_changes_and_told_not_to_(
    context: ContextOfTest,
) -> None:
    with run_server(context, extra_args=["--no-index"]):
        await asyncio.sleep(REASONABLE_AMOUNT_OF_TIME)

        agent = await get_first_agent()

        agent_replies = await get_agent_replies(
            context,
            message="Hello",
            agent=agent,
            number_of_replies_to_expect=1,
        )

        assert await nlp_test(
            agent_replies[0],
            "It greeting the user",
        )


async def test_that_the_server_starts_when_there_are_no_state_changes_and_told_to_index(
    context: ContextOfTest,
) -> None:
    with run_server(context, extra_args=["--index"]):
        await asyncio.sleep(REASONABLE_AMOUNT_OF_TIME)

        agent = await get_first_agent()

        agent_replies = await get_agent_replies(
            context,
            message="Hello",
            agent=agent,
            number_of_replies_to_expect=1,
        )

        assert await nlp_test(
            agent_replies[0],
            "It greeting the user",
        )


async def test_that_the_server_refuses_to_start_on_detecting_a_state_change_that_requires_indexing_if_told_not_to_index_changes(
    context: ContextOfTest,
) -> None:
    with run_server(context, extra_args=["--no-index"]) as server_process:
        await asyncio.sleep(REASONABLE_AMOUNT_OF_TIME)

        new_guideline: _Guideline = {
            "when": "talking about bananas",
            "then": "say they're very tasty",
        }

        write_guideline_config(
            new_guidelines=[new_guideline],
            config_file=context.config_file,
        )

        server_process.wait(timeout=REASONABLE_AMOUNT_OF_TIME)
        assert server_process.returncode == 1


async def test_that_the_server_does_not_conform_to_state_changes_if_forced_to_start_and_told_not_to_index(
    context: ContextOfTest,
) -> None:
    with run_server(context, extra_args=["--no-index", "--force"]):
        await asyncio.sleep(REASONABLE_AMOUNT_OF_TIME)

        new_guidelines: list[_Guideline] = [
            {
                "when": "talking about bananas",
                "then": "say bananas are very tasty",
            },
            {
                "when": "saying bananas are very tasty",
                "then": "say also they are blue",
            },
        ]

        write_guideline_config(
            new_guidelines=new_guidelines,
            config_file=context.config_file,
        )

        await asyncio.sleep(REASONABLE_AMOUNT_OF_TIME)

        assert not context.index_file.exists()

        agent = await get_first_agent()

        agent_replies = await get_agent_replies(
            context,
            message="what are bananas?",
            agent=agent,
            number_of_replies_to_expect=1,
        )

        assert await nlp_test(
            agent_replies[0],
            "It says that bananas are very tasty but not mentioning they blue",
        )


async def test_that_the_server_detects_and_conforms_to_a_state_change_if_told_to_index_changes(
    context: ContextOfTest,
) -> None:
    with run_server(context, extra_args=["--index"]):
        await asyncio.sleep(REASONABLE_AMOUNT_OF_TIME)

        initial_guidelines = read_guideline_config(context.config_file)

        new_guidelines: list[_Guideline] = [
            {
                "when": "talking about bananas",
                "then": "say bananas are very tasty",
            },
            {
                "when": "saying bananas are very tasty",
                "then": "say also they are blue",
            },
        ]

        write_guideline_config(
            new_guidelines=initial_guidelines + new_guidelines,
            config_file=context.config_file,
        )

        await asyncio.sleep(EXTENDED_AMOUNT_OF_TIME)

        agent = await get_first_agent()

        agent_replies = await get_agent_replies(
            context,
            message="what are bananas?",
            agent=agent,
            number_of_replies_to_expect=1,
        )

        assert await nlp_test(
            agent_replies[0],
            "It says that bananas are very tasty and blue",
        )


async def test_that_the_server_recovery_restarts_all_active_evaluation_tasks(
    context: ContextOfTest,
) -> None:
    with run_server(context) as server_process:
        await asyncio.sleep(REASONABLE_AMOUNT_OF_TIME)

        agent = await get_first_agent()

        payloads = {
            "payloads": [
                {
                    "kind": "guideline",
                    "predicate": "the user greets you",
                    "action": "greet them back with 'Hello'",
                },
                {
                    "kind": "guideline",
                    "predicate": "the user greeting you",
                    "action": "greet them back with 'Hola'",
                },
            ],
        }
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=httpx.Timeout(30),
        ) as client:
            try:
                evaluation_creation_response = await client.post(
                    f"{SERVER_ADDRESS}/agents/{agent.id}/index/evaluations",
                    json=payloads,
                )
                evaluation_creation_response.raise_for_status()
                evaluation_id = evaluation_creation_response.json()["evaluation_id"]

                server_process.send_signal(signal.SIGINT)
                server_process.wait(timeout=1)
                assert server_process.returncode == os.EX_OK
            except:
                traceback.print_exc()
                raise

    with run_server(context) as server_process:
        EXTRA_TIME_TO_LET_THE_TASK_COMPLETE = 5
        await asyncio.sleep(REASONABLE_AMOUNT_OF_TIME + EXTRA_TIME_TO_LET_THE_TASK_COMPLETE)

        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=httpx.Timeout(30),
        ) as client:
            try:
                evaluation_response = await client.get(
                    f"{SERVER_ADDRESS}/agents/index/evaluations/{evaluation_id}",
                )
                evaluation_creation_response.raise_for_status()
                assert evaluation_response.json()["status"] == "completed"
            except:
                traceback.print_exc()
                raise
