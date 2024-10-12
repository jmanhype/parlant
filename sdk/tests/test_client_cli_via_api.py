import asyncio
import json
import os
from typing import Any, Optional
import httpx

from tests.test_utilities import (
    CLI_CLIENT_PATH,
    SERVER_ADDRESS,
    ContextOfTest,
    run_server,
)

REASONABLE_AMOUNT_OF_TIME = 5
REASONABLE_AMOUNT_OF_TIME_FOR_TERM_CREATION = 0.25


async def get_first_agent_id() -> str:
    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=httpx.Timeout(30),
    ) as client:
        agents_response = await client.get(
            f"{SERVER_ADDRESS}/agents/",
        )
        agents_response.raise_for_status()

        assert len(agents_response.json()["agents"]) > 0
        agent = agents_response.json()["agents"][0]
        return str(agent["id"])


async def get_term_list(agent_id: str) -> Any:
    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=httpx.Timeout(30),
    ) as client:
        response = await client.get(
            f"{SERVER_ADDRESS}/agents/{agent_id}/terms/",
        )
        response.raise_for_status()

        return response.json()["terms"]


async def get_term(agent_id: str, term_name: str) -> Any:
    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=httpx.Timeout(30),
    ) as client:
        response = await client.get(
            f"{SERVER_ADDRESS}/agents/{agent_id}/terms/{term_name}",
        )
        response.raise_for_status()

        return response.json()


async def get_guideline_list(agent_id: str) -> Any:
    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=httpx.Timeout(30),
    ) as client:
        response = await client.get(
            f"{SERVER_ADDRESS}/agents/{agent_id}/guidelines/",
        )

        response.raise_for_status()

        return response.json()["guidelines"]


async def get_guideline(agent_id: str, guideline_id: str) -> Any:
    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=httpx.Timeout(30),
    ) as client:
        response = await client.get(
            f"{SERVER_ADDRESS}/agents/{agent_id}/guidelines/{guideline_id}",
        )

        response.raise_for_status()

        return response.json()


async def create_guideline(
    agent_id: str,
    predicate: str,
    action: str,
    coherence_check: Optional[dict[str, Any]] = None,
    connection_propositions: Optional[dict[str, Any]] = None,
) -> Any:
    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=httpx.Timeout(30),
    ) as client:
        response = await client.post(
            f"{SERVER_ADDRESS}/agents/{agent_id}/guidelines/",
            json={
                "invoices": [
                    {
                        "payload": {
                            "kind": "guideline",
                            "predicate": predicate,
                            "action": action,
                        },
                        "checksum": "checksum_value",
                        "approved": True if coherence_check is None else False,
                        "data": {
                            "coherence_checks": coherence_check if coherence_check else [],
                            "connection_propositions": connection_propositions
                            if connection_propositions
                            else None,
                        },
                        "error": None,
                    }
                ]
            },
        )

        response.raise_for_status()

        return response.json()["items"][0]["guideline"]


async def create_context_variable(agent_id: str, name: str, description: str) -> Any:
    async with httpx.AsyncClient(
        base_url=SERVER_ADDRESS,
        follow_redirects=True,
        timeout=httpx.Timeout(30),
    ) as client:
        response = await client.post(
            f"/agents/{agent_id}/context-variables",
            json={
                "name": name,
                "description": description,
            },
        )

        response.raise_for_status()

        return response.json()["context_variable"]


async def get_context_variable_list(agent_id: str) -> Any:
    async with httpx.AsyncClient(
        base_url=SERVER_ADDRESS,
        follow_redirects=True,
        timeout=httpx.Timeout(30),
    ) as client:
        response = await client.get(f"/agents/{agent_id}/context-variables/")

        response.raise_for_status()

        return response.json()["context_variables"]


async def get_context_variable_value(agent_id: str, variable_id: str, key: str) -> Any:
    async with httpx.AsyncClient(
        base_url=SERVER_ADDRESS,
        follow_redirects=True,
        timeout=httpx.Timeout(30),
    ) as client:
        response = await client.get(
            f"{SERVER_ADDRESS}/agents/{agent_id}/context-variables/{variable_id}/{key}",
        )

        response.raise_for_status()

        return response.json()


async def test_that_a_term_can_be_created_with_synonyms(
    context: ContextOfTest,
) -> None:
    term_name = "guideline"
    description = "when and then statements"
    synonyms = "rule, principle"

    with run_server(context):
        await asyncio.sleep(REASONABLE_AMOUNT_OF_TIME)

        agent_id = await get_first_agent_id()

        exec_args = [
            "poetry",
            "run",
            "python",
            CLI_CLIENT_PATH.as_posix(),
            "--server",
            SERVER_ADDRESS,
            "glossary",
            "add",
            "--agent-id",
            agent_id,
            term_name,
            description,
            "--synonyms",
            synonyms,
        ]

        process = await asyncio.create_subprocess_exec(*exec_args)
        await process.wait()

        assert process.returncode == os.EX_OK


async def test_that_a_term_can_be_created_without_synonyms(
    context: ContextOfTest,
) -> None:
    term_name = "guideline_no_synonyms"
    description = "simple guideline with no synonyms"

    with run_server(context):
        await asyncio.sleep(REASONABLE_AMOUNT_OF_TIME)

        agent_id = await get_first_agent_id()

        exec_args = [
            "poetry",
            "run",
            "python",
            CLI_CLIENT_PATH.as_posix(),
            "--server",
            SERVER_ADDRESS,
            "glossary",
            "add",
            "--agent-id",
            agent_id,
            term_name,
            description,
        ]

        process = await asyncio.create_subprocess_exec(*exec_args)
        await process.wait()

        assert process.returncode == os.EX_OK

        term = await get_term(agent_id, term_name)
        assert term["name"] == term_name
        assert term["description"] == description
        assert term["synonyms"] is None


async def test_that_terms_can_be_listed(
    context: ContextOfTest,
) -> None:
    guideline_term_name = "guideline"
    tool_term_name = "tool"
    guideline_description = "when and then statements"
    tool_description = "techniuqe to fetch external data"
    guideline_synonyms = "rule, instruction"

    with run_server(context):
        await asyncio.sleep(REASONABLE_AMOUNT_OF_TIME)

        agent_id = await get_first_agent_id()

        first_exec_args = [
            "poetry",
            "run",
            "python",
            CLI_CLIENT_PATH.as_posix(),
            "--server",
            SERVER_ADDRESS,
            "glossary",
            "add",
            "--agent-id",
            agent_id,
            guideline_term_name,
            guideline_description,
            "--synonyms",
            guideline_synonyms,
        ]
        seconds_exec_args = [
            "poetry",
            "run",
            "python",
            CLI_CLIENT_PATH.as_posix(),
            "--server",
            SERVER_ADDRESS,
            "glossary",
            "add",
            "--agent-id",
            agent_id,
            tool_term_name,
            tool_description,
        ]

        assert await (await asyncio.create_subprocess_exec(*first_exec_args)).wait() == os.EX_OK
        assert await (await asyncio.create_subprocess_exec(*seconds_exec_args)).wait() == os.EX_OK

        terms = await get_term_list(agent_id)
        assert len(terms) == 2

        term_names = {term["name"] for term in terms}
        assert guideline_term_name in term_names
        assert tool_term_name in term_names


async def test_that_a_term_can_be_deleted(
    context: ContextOfTest,
) -> None:
    name = "guideline_delete"
    description = "to be deleted"
    synonyms = "rule, principle"

    with run_server(context):
        await asyncio.sleep(REASONABLE_AMOUNT_OF_TIME)

        agent_id = await get_first_agent_id()

        exec_args = [
            "poetry",
            "run",
            "python",
            CLI_CLIENT_PATH.as_posix(),
            "--server",
            SERVER_ADDRESS,
            "glossary",
            "add",
            "--agent-id",
            agent_id,
            name,
            description,
            "--synonyms",
            synonyms,
        ]
        process = await asyncio.create_subprocess_exec(*exec_args)
        await process.wait()

        assert process.returncode == os.EX_OK

        exec_args_delete = [
            "poetry",
            "run",
            "python",
            CLI_CLIENT_PATH.as_posix(),
            "--server",
            SERVER_ADDRESS,
            "glossary",
            "remove",
            "--agent-id",
            agent_id,
            name,
        ]
        process = await asyncio.create_subprocess_exec(*exec_args_delete)
        await process.wait()

        assert process.returncode == os.EX_OK

        terms = await get_term_list(agent_id)
        assert len(terms) == 0


async def test_that_terms_are_loaded_on_server_startup(
    context: ContextOfTest,
) -> None:
    term_name = "guideline_no_synonyms"
    description = "simple guideline with no synonyms"

    with run_server(context):
        await asyncio.sleep(REASONABLE_AMOUNT_OF_TIME)

        agent_id = await get_first_agent_id()

        exec_args = [
            "poetry",
            "run",
            "python",
            CLI_CLIENT_PATH.as_posix(),
            "--server",
            SERVER_ADDRESS,
            "glossary",
            "add",
            "--agent-id",
            agent_id,
            term_name,
            description,
        ]

        process = await asyncio.create_subprocess_exec(*exec_args)
        await process.wait()

        assert process.returncode == os.EX_OK

    with run_server(context):
        await asyncio.sleep(REASONABLE_AMOUNT_OF_TIME)

        agent_id = await get_first_agent_id()

        term = await get_term(agent_id, term_name)
        assert term["name"] == term_name
        assert term["description"] == description
        assert term["synonyms"] is None


async def test_that_guideline_can_be_added(
    context: ContextOfTest,
) -> None:
    predicate = "the user greets you"
    action = "greet them back with 'Hello'"

    with run_server(context):
        await asyncio.sleep(REASONABLE_AMOUNT_OF_TIME)

        agent_id = await get_first_agent_id()

        exec_args = [
            "poetry",
            "run",
            "python",
            CLI_CLIENT_PATH.as_posix(),
            "--server",
            SERVER_ADDRESS,
            "guideline",
            "add",
            "-a",
            agent_id,
            predicate,
            action,
        ]

        process = await asyncio.create_subprocess_exec(*exec_args)
        await process.wait()

        assert process.returncode == os.EX_OK

        guidelines = await get_guideline_list(agent_id)
        assert any(g["predicate"] == predicate and g["action"] == action for g in guidelines)


async def test_that_adding_a_contradictory_guideline_shows_coherence_errors(
    context: ContextOfTest,
) -> None:
    predicate = "the user greets you"
    action = "greet them back with 'Hello'"

    conflicting_action = "ignore the user"

    with run_server(context):
        await asyncio.sleep(REASONABLE_AMOUNT_OF_TIME)

        agent_id = await get_first_agent_id()

        first_exec_args = [
            "poetry",
            "run",
            "python",
            CLI_CLIENT_PATH.as_posix(),
            "--server",
            SERVER_ADDRESS,
            "guideline",
            "add",
            "-a",
            agent_id,
            predicate,
            action,
        ]

        process = await asyncio.create_subprocess_exec(*first_exec_args)
        await process.wait()

        second_exec_args = [
            "poetry",
            "run",
            "python",
            CLI_CLIENT_PATH.as_posix(),
            "--server",
            SERVER_ADDRESS,
            "guideline",
            "add",
            "-a",
            agent_id,
            predicate,
            conflicting_action,
        ]

        process = await asyncio.create_subprocess_exec(
            *second_exec_args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        output = stdout.decode() + stderr.decode()

        assert "Detected incoherence with other guidelines" in output

        guidelines = await get_guideline_list(agent_id)

        assert not any(
            g["predicate"] == predicate and g["action"] == conflicting_action for g in guidelines
        )


async def test_that_adding_connected_guidelines_creates_connections(
    context: ContextOfTest,
) -> None:
    predicate1 = "the user asks about the weather"
    action1 = "provide a weather update"

    predicate2 = "providing a weather update"
    action2 = "include temperature and humidity"

    with run_server(context):
        await asyncio.sleep(REASONABLE_AMOUNT_OF_TIME)

        agent_id = await get_first_agent_id()

        first_exec_args = [
            "poetry",
            "run",
            "python",
            CLI_CLIENT_PATH.as_posix(),
            "--server",
            SERVER_ADDRESS,
            "guideline",
            "add",
            "-a",
            agent_id,
            predicate1,
            action1,
        ]

        process = await asyncio.create_subprocess_exec(*first_exec_args)
        await process.wait()

        assert process.returncode == os.EX_OK

        second_exec_args = [
            "poetry",
            "run",
            "python",
            CLI_CLIENT_PATH.as_posix(),
            "--server",
            SERVER_ADDRESS,
            "guideline",
            "add",
            "-a",
            agent_id,
            predicate2,
            action2,
        ]

        process = await asyncio.create_subprocess_exec(*second_exec_args)
        await process.wait()

        assert process.returncode == os.EX_OK

        guidelines = await get_guideline_list(agent_id)

        assert len(guidelines) == 2
        source = guidelines[0]
        target = guidelines[1]

        source_guideline = await get_guideline(agent_id, source["id"])
        source_connections = source_guideline["connections"]

        assert len(source_connections) == 1
        connection = source_connections[0]

        assert connection["source"] == source
        assert connection["target"] == target
        assert connection["kind"] == "entails"


async def test_that_guideline_can_be_viewed(
    context: ContextOfTest,
) -> None:
    predicate = "the user says goodbye"
    action = "say 'Goodbye' back"

    with run_server(context):
        await asyncio.sleep(REASONABLE_AMOUNT_OF_TIME)

        agent_id = await get_first_agent_id()

        guideline = await create_guideline(agent_id=agent_id, predicate=predicate, action=action)

        exec_args = [
            "poetry",
            "run",
            "python",
            CLI_CLIENT_PATH.as_posix(),
            "--server",
            SERVER_ADDRESS,
            "guideline",
            "view",
            "-a",
            agent_id,
            guideline["id"],
        ]
        process = await asyncio.create_subprocess_exec(
            *exec_args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_view, stderr_view = await process.communicate()
        output_view = stdout_view.decode() + stderr_view.decode()
        assert process.returncode == os.EX_OK

        assert guideline["id"] in output_view
        assert predicate in output_view
        assert action in output_view


async def test_that_view_guideline_with_connections_displays_indirect_and_direct_connections(
    context: ContextOfTest,
) -> None:
    predicate1 = "AAA"
    action1 = "BBB"

    predicate2 = "BBB"
    action2 = "CCC"

    predicate3 = "CCC"
    action3 = "DDD"

    with run_server(context):
        await asyncio.sleep(REASONABLE_AMOUNT_OF_TIME)

        agent_id = await get_first_agent_id()

        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=httpx.Timeout(30),
        ) as client:
            add_guidelines_response = await client.post(
                f"{SERVER_ADDRESS}/agents/{agent_id}/guidelines/",
                json={
                    "invoices": [
                        {
                            "payload": {
                                "kind": "guideline",
                                "predicate": predicate1,
                                "action": action1,
                            },
                            "checksum": "checksum_value",
                            "approved": True,
                            "data": {
                                "coherence_checks": [],
                                "connection_propositions": [
                                    {
                                        "check_kind": "connection_with_another_evaluated_guideline",
                                        "source": {
                                            "predicate": predicate1,
                                            "action": action1,
                                        },
                                        "target": {
                                            "predicate": predicate2,
                                            "action": action2,
                                        },
                                        "connection_kind": "entails",
                                    }
                                ],
                            },
                            "error": None,
                        },
                        {
                            "payload": {
                                "kind": "guideline",
                                "predicate": predicate2,
                                "action": action2,
                            },
                            "checksum": "checksum_value",
                            "approved": True,
                            "data": {
                                "coherence_checks": [],
                                "connection_propositions": [
                                    {
                                        "check_kind": "connection_with_another_evaluated_guideline",
                                        "source": {
                                            "predicate": predicate1,
                                            "action": action1,
                                        },
                                        "target": {
                                            "predicate": predicate2,
                                            "action": action2,
                                        },
                                        "connection_kind": "entails",
                                    },
                                    {
                                        "check_kind": "connection_with_another_evaluated_guideline",
                                        "source": {
                                            "predicate": predicate2,
                                            "action": action2,
                                        },
                                        "target": {
                                            "predicate": predicate3,
                                            "action": action3,
                                        },
                                        "connection_kind": "entails",
                                    },
                                ],
                            },
                            "error": None,
                        },
                        {
                            "payload": {
                                "kind": "guideline",
                                "predicate": predicate3,
                                "action": action3,
                            },
                            "checksum": "checksum_value",
                            "approved": True,
                            "data": {
                                "coherence_checks": [],
                                "connection_propositions": [
                                    {
                                        "check_kind": "connection_with_another_evaluated_guideline",
                                        "source": {
                                            "predicate": predicate2,
                                            "action": action2,
                                        },
                                        "target": {
                                            "predicate": predicate3,
                                            "action": action3,
                                        },
                                        "connection_kind": "entails",
                                    }
                                ],
                            },
                            "error": None,
                        },
                    ]
                },
            )

            add_guidelines_response.raise_for_status()

        first = add_guidelines_response.json()["items"][0]["guideline"]
        first_connection = add_guidelines_response.json()["items"][0]["connections"][0]
        second_connection = add_guidelines_response.json()["items"][1]["connections"][0]

        exec_args = [
            "poetry",
            "run",
            "python",
            CLI_CLIENT_PATH.as_posix(),
            "--server",
            SERVER_ADDRESS,
            "guideline",
            "view",
            "-a",
            agent_id,
            first["id"],
        ]
        process = await asyncio.create_subprocess_exec(
            *exec_args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_view, stderr_view = await process.communicate()
        output_view = stdout_view.decode() + stderr_view.decode()
        assert process.returncode == os.EX_OK

        assert first["id"] in output_view
        assert predicate1 in output_view
        assert action1 in output_view

        assert "Direct Entailments:" in output_view
        assert first_connection["id"] in output_view
        assert predicate2 in output_view
        assert action2 in output_view

        assert "Indirect Entailments:" in output_view
        assert second_connection["id"] in output_view
        assert predicate3 in output_view
        assert action3 in output_view


async def test_that_guidelines_can_be_listed(
    context: ContextOfTest,
) -> None:
    predicate1 = "the user asks for help"
    action1 = "provide assistance"

    predicate2 = "the user needs support"
    action2 = "offer support"

    with run_server(context):
        await asyncio.sleep(REASONABLE_AMOUNT_OF_TIME)

        agent_id = await get_first_agent_id()

        _ = await create_guideline(agent_id=agent_id, predicate=predicate1, action=action1)
        _ = await create_guideline(agent_id=agent_id, predicate=predicate2, action=action2)

        exec_args = [
            "poetry",
            "run",
            "python",
            CLI_CLIENT_PATH.as_posix(),
            "--server",
            SERVER_ADDRESS,
            "guideline",
            "list",
            "-a",
            agent_id,
        ]
        process_list = await asyncio.create_subprocess_exec(
            *exec_args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_list, stderr_list = await process_list.communicate()
        output_list = stdout_list.decode() + stderr_list.decode()
        assert process_list.returncode == os.EX_OK

        assert predicate1 in output_list
        assert action1 in output_list
        assert predicate2 in output_list
        assert action2 in output_list


async def test_that_guidelines_can_be_entailed(
    context: ContextOfTest,
) -> None:
    predicate1 = "the user needs assistance"
    action1 = "provide help"

    predicate2 = "user ask about a certain subject"
    action2 = "offer detailed explanation"

    with run_server(context):
        await asyncio.sleep(REASONABLE_AMOUNT_OF_TIME)

        agent_id = await get_first_agent_id()

        first_exec_args = [
            "poetry",
            "run",
            "python",
            CLI_CLIENT_PATH.as_posix(),
            "--server",
            SERVER_ADDRESS,
            "guideline",
            "add",
            "-a",
            agent_id,
            "--no-check",
            "--no-index",
            predicate1,
            action1,
        ]
        process = await asyncio.create_subprocess_exec(*first_exec_args)
        await process.wait()
        assert process.returncode == os.EX_OK

        second_exec_args = [
            "poetry",
            "run",
            "python",
            CLI_CLIENT_PATH.as_posix(),
            "--server",
            SERVER_ADDRESS,
            "guideline",
            "add",
            "-a",
            agent_id,
            "--no-check",
            "--no-index",
            predicate2,
            action2,
        ]
        process = await asyncio.create_subprocess_exec(*second_exec_args)
        await process.wait()
        assert process.returncode == os.EX_OK

        guidelines = await get_guideline_list(agent_id)

        first_guideline = next(
            g for g in guidelines if g["predicate"] == predicate1 and g["action"] == action1
        )
        second_guideline = next(
            g for g in guidelines if g["predicate"] == predicate2 and g["action"] == action2
        )

        third_exec_args = [
            "poetry",
            "run",
            "python",
            CLI_CLIENT_PATH.as_posix(),
            "--server",
            SERVER_ADDRESS,
            "guideline",
            "entail",
            "-a",
            agent_id,
            first_guideline["id"],
            second_guideline["id"],
        ]
        process = await asyncio.create_subprocess_exec(
            *third_exec_args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await process.communicate()
        await process.wait()
        assert process.returncode == os.EX_OK

        guideline = await get_guideline(agent_id, first_guideline["id"])
        assert "connections" in guideline and len(guideline["connections"]) == 1
        connection = guideline["connections"][0]
        assert (
            connection["source"] == first_guideline
            and connection["target"] == second_guideline
            and connection["kind"] == "entails"
        )


async def test_that_guidelines_can_be_suggestively_entailed(
    context: ContextOfTest,
) -> None:
    predicate1 = "the user needs assistance"
    action1 = "provide help"

    predicate2 = "user ask about a certain subject"
    action2 = "offer detailed explanation"

    with run_server(context):
        await asyncio.sleep(REASONABLE_AMOUNT_OF_TIME)

        agent_id = await get_first_agent_id()

        first_exec_args = [
            "poetry",
            "run",
            "python",
            CLI_CLIENT_PATH.as_posix(),
            "--server",
            SERVER_ADDRESS,
            "guideline",
            "add",
            "-a",
            agent_id,
            "--no-check",
            "--no-index",
            predicate1,
            action1,
        ]
        process = await asyncio.create_subprocess_exec(*first_exec_args)
        await process.wait()
        assert process.returncode == os.EX_OK

        second_exec_args = [
            "poetry",
            "run",
            "python",
            CLI_CLIENT_PATH.as_posix(),
            "--server",
            SERVER_ADDRESS,
            "guideline",
            "add",
            "-a",
            agent_id,
            "--no-check",
            "--no-index",
            predicate2,
            action2,
        ]
        process = await asyncio.create_subprocess_exec(*second_exec_args)
        await process.wait()
        assert process.returncode == os.EX_OK

        guidelines = await get_guideline_list(agent_id)

        first_guideline = next(
            g for g in guidelines if g["predicate"] == predicate1 and g["action"] == action1
        )
        second_guideline = next(
            g for g in guidelines if g["predicate"] == predicate2 and g["action"] == action2
        )

        third_exec_args = [
            "poetry",
            "run",
            "python",
            CLI_CLIENT_PATH.as_posix(),
            "--server",
            SERVER_ADDRESS,
            "guideline",
            "entail",
            "-a",
            agent_id,
            "--suggestive",
            first_guideline["id"],
            second_guideline["id"],
        ]
        process = await asyncio.create_subprocess_exec(
            *third_exec_args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await process.communicate()
        await process.wait()
        assert process.returncode == os.EX_OK

        guideline = await get_guideline(agent_id, first_guideline["id"])

        assert "connections" in guideline and len(guideline["connections"]) == 1
        connection = guideline["connections"][0]
        assert (
            connection["source"] == first_guideline
            and connection["target"] == second_guideline
            and connection["kind"] == "suggests"
        )


async def test_that_guideline_can_be_removed(
    context: ContextOfTest,
) -> None:
    with run_server(context):
        await asyncio.sleep(REASONABLE_AMOUNT_OF_TIME)

        agent_id = await get_first_agent_id()

        guideline = await create_guideline(
            agent_id, predicate="the user greets you", action="greet them back with 'Hello'"
        )

        exec_args = [
            "poetry",
            "run",
            "python",
            CLI_CLIENT_PATH.as_posix(),
            "--server",
            SERVER_ADDRESS,
            "guideline",
            "remove",
            "-a",
            agent_id,
            guideline["id"],
        ]

        process = await asyncio.create_subprocess_exec(*exec_args)
        await process.wait()

        assert process.returncode == os.EX_OK

        guidelines = await get_guideline_list(agent_id)
        assert len(guidelines) == 0


async def test_that_connection_can_be_removed(
    context: ContextOfTest,
) -> None:
    with run_server(context):
        await asyncio.sleep(REASONABLE_AMOUNT_OF_TIME)

        agent_id = await get_first_agent_id()

        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=httpx.Timeout(30),
        ) as client:
            guidelines_response = await client.post(
                f"{SERVER_ADDRESS}/agents/{agent_id}/guidelines/",
                json={
                    "invoices": [
                        {
                            "payload": {
                                "kind": "guideline",
                                "predicate": "the user greets you",
                                "action": "greet them back with 'Hello'",
                            },
                            "checksum": "checksum_value",
                            "approved": True,
                            "data": {
                                "coherence_checks": [],
                                "connection_propositions": [
                                    {
                                        "check_kind": "connection_with_another_evaluated_guideline",
                                        "source": {
                                            "predicate": "the user greets you",
                                            "action": "greet them back with 'Hello'",
                                        },
                                        "target": {
                                            "predicate": "greeting the user",
                                            "action": "ask for his health condition",
                                        },
                                        "connection_kind": "entails",
                                    }
                                ],
                            },
                            "error": None,
                        },
                        {
                            "payload": {
                                "kind": "guideline",
                                "predicate": "greeting the user",
                                "action": "ask for his health condition",
                            },
                            "checksum": "checksum_value",
                            "approved": True,
                            "data": {
                                "coherence_checks": [],
                                "connection_propositions": [
                                    {
                                        "check_kind": "connection_with_another_evaluated_guideline",
                                        "source": {
                                            "predicate": "the user greets you",
                                            "action": "greet them back with 'Hello'",
                                        },
                                        "target": {
                                            "predicate": "greeting the user",
                                            "action": "ask for his health condition",
                                        },
                                        "connection_kind": "entails",
                                    }
                                ],
                            },
                            "error": None,
                        },
                    ]
                },
            )

            guidelines_response.raise_for_status()
            first = guidelines_response.json()["items"][0]["guideline"]["id"]
            second = guidelines_response.json()["items"][1]["guideline"]["id"]

        exec_args = [
            "poetry",
            "run",
            "python",
            CLI_CLIENT_PATH.as_posix(),
            "--server",
            SERVER_ADDRESS,
            "guideline",
            "disentail",
            "-a",
            agent_id,
            first,
            second,
        ]

        process = await asyncio.create_subprocess_exec(*exec_args)
        await process.wait()

        assert process.returncode == os.EX_OK

        guideline = await get_guideline(agent_id, first)
        assert len(guideline["connections"]) == 0


async def test_that_variables_can_be_listed(
    context: ContextOfTest,
) -> None:
    name1 = "test_variable1"
    description1 = "test variable one"

    name2 = "test_variable2"
    description2 = "test variable two"

    with run_server(context):
        await asyncio.sleep(REASONABLE_AMOUNT_OF_TIME)

        agent_id = await get_first_agent_id()
        _ = await create_context_variable(agent_id, name1, description1)
        _ = await create_context_variable(agent_id, name2, description2)

        exec_args = [
            "poetry",
            "run",
            "python",
            CLI_CLIENT_PATH.as_posix(),
            "--server",
            SERVER_ADDRESS,
            "variable",
            "list",
            "--agent-id",
            agent_id,
        ]

        process = await asyncio.create_subprocess_exec(
            *exec_args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        process_output = stdout.decode() + stderr.decode()

        assert process.returncode == os.EX_OK

        assert name1 in process_output
        assert description1 in process_output
        assert name2 in process_output
        assert description2 in process_output


async def test_that_variable_can_be_added(
    context: ContextOfTest,
) -> None:
    name = "test_variable_cli"
    description = "Variable added via CLI"

    with run_server(context):
        await asyncio.sleep(REASONABLE_AMOUNT_OF_TIME)

        agent_id = await get_first_agent_id()

        exec_args = [
            "poetry",
            "run",
            "python",
            CLI_CLIENT_PATH.as_posix(),
            "--server",
            SERVER_ADDRESS,
            "variable",
            "add",
            "--agent-id",
            agent_id,
            "--description",
            description,
            name,
        ]

        process = await asyncio.create_subprocess_exec(*exec_args)
        await process.wait()
        assert process.returncode == os.EX_OK

        variables = await get_context_variable_list(agent_id)

        variable = next(
            (v for v in variables if v["name"] == name and v["description"] == description),
            None,
        )
        assert variable is not None, "Variable was not added"


async def test_that_variable_can_be_removed(
    context: ContextOfTest,
) -> None:
    name = "test_variable_to_remove"
    description = "Variable to be removed via CLI"

    with run_server(context):
        await asyncio.sleep(REASONABLE_AMOUNT_OF_TIME)

        agent_id = await get_first_agent_id()

        _ = await create_context_variable(agent_id, name, description)

        exec_args = [
            "poetry",
            "run",
            "python",
            CLI_CLIENT_PATH.as_posix(),
            "--server",
            SERVER_ADDRESS,
            "variable",
            "remove",
            "--agent-id",
            agent_id,
            name,
        ]

        process = await asyncio.create_subprocess_exec(*exec_args)
        await process.wait()
        assert process.returncode == os.EX_OK

        variables = await get_context_variable_list(agent_id)
        assert len(variables) == 0


async def test_that_variable_value_can_be_set_with_json(
    context: ContextOfTest,
) -> None:
    variable_name = "test_variable_set"
    variable_description = "Variable to test setting value via CLI"
    key = "test_key"
    data = {"test": "data", "type": 27}

    with run_server(context):
        await asyncio.sleep(REASONABLE_AMOUNT_OF_TIME)

        agent_id = await get_first_agent_id()
        variable = await create_context_variable(agent_id, variable_name, variable_description)

        exec_args = [
            "poetry",
            "run",
            "python",
            CLI_CLIENT_PATH.as_posix(),
            "--server",
            SERVER_ADDRESS,
            "variable",
            "set",
            "--agent-id",
            agent_id,
            variable_name,
            key,
            json.dumps(data),
        ]

        process = await asyncio.create_subprocess_exec(*exec_args)
        await process.wait()
        assert process.returncode == os.EX_OK

        value = await get_context_variable_value(agent_id, variable["id"], key)
        assert value["data"] == data


async def test_that_variable_value_can_be_set_with_string(
    context: ContextOfTest,
) -> None:
    variable_name = "test_variable_set"
    variable_description = "Variable to test setting value via CLI"
    key = "test_key"
    data = "test_string"

    with run_server(context):
        await asyncio.sleep(REASONABLE_AMOUNT_OF_TIME)

        agent_id = await get_first_agent_id()
        variable = await create_context_variable(agent_id, variable_name, variable_description)

        exec_args_set = [
            "poetry",
            "run",
            "python",
            CLI_CLIENT_PATH.as_posix(),
            "--server",
            SERVER_ADDRESS,
            "variable",
            "set",
            "--agent-id",
            agent_id,
            variable_name,
            key,
            json.dumps(data),
        ]

        process = await asyncio.create_subprocess_exec(*exec_args_set)
        await process.wait()
        assert process.returncode == os.EX_OK

        value = await get_context_variable_value(agent_id, variable["id"], key)

        assert value["data"] == data


async def test_that_variable_values_can_be_retrieved(
    context: ContextOfTest,
) -> None:
    variable_name = "test_variable_get"
    variable_description = "Variable to test retrieving values via CLI"
    values = {
        "key1": "data1",
        "key2": "data2",
        "key3": "data3",
    }

    with run_server(context):
        await asyncio.sleep(REASONABLE_AMOUNT_OF_TIME)

        agent_id = await get_first_agent_id()
        variable = await create_context_variable(agent_id, variable_name, variable_description)

        async with httpx.AsyncClient(
            base_url=SERVER_ADDRESS,
            follow_redirects=True,
            timeout=httpx.Timeout(30),
        ) as client:
            for key, data in values.items():
                response = await client.put(
                    f"/agents/{agent_id}/context-variables/{variable["id"]}/{key}",
                    json={"data": data},
                )
                response.raise_for_status()

        exec_args = [
            "poetry",
            "run",
            "python",
            CLI_CLIENT_PATH.as_posix(),
            "--server",
            SERVER_ADDRESS,
            "variable",
            "get",
            "--agent-id",
            agent_id,
            variable_name,
        ]

        process = await asyncio.create_subprocess_exec(
            *exec_args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_get_all_values, stderr_get_all = await process.communicate()
        output_get_all_values = stdout_get_all_values.decode() + stderr_get_all.decode()
        assert process.returncode == os.EX_OK

        for key, data in values.items():
            assert key in output_get_all_values
            assert data in output_get_all_values

        specific_key = "key2"
        expected_value = values[specific_key]

        exec_args = [
            "poetry",
            "run",
            "python",
            CLI_CLIENT_PATH.as_posix(),
            "--server",
            SERVER_ADDRESS,
            "variable",
            "get",
            "--agent-id",
            agent_id,
            variable_name,
            specific_key,
        ]
        process = await asyncio.create_subprocess_exec(
            *exec_args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_get_value_by_key, stderr_get_key = await process.communicate()
        output_get_value_by_key = stdout_get_value_by_key.decode() + stderr_get_key.decode()
        assert process.returncode == os.EX_OK

        assert specific_key in output_get_value_by_key
        assert expected_value in output_get_value_by_key
