import asyncio
import json
import os
import traceback
import httpx

from tests.test_utilities import (
    CLI_CLIENT_PATH,
    DEFAULT_AGENT_NAME,
    SERVER_ADDRESS,
    ContextOfTest,
    load_active_agent,
    run_server,
)

REASONABLE_AMOUNT_OF_TIME = 5
REASONABLE_AMOUNT_OF_TIME_FOR_TERM_CREATION = 0.25


async def get_first_agent_id() -> str:
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
            return str(agent["id"])

        except:
            traceback.print_exc()
            raise


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

        result = await asyncio.create_subprocess_exec(*exec_args)
        await result.wait()

        assert result.returncode == os.EX_OK

        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=httpx.Timeout(30),
        ) as client:
            try:
                terminology_response = await client.get(
                    f"{SERVER_ADDRESS}/agents/{agent_id}/terms/",
                )
                terminology_response.raise_for_status()

                assert len(terminology_response.json()["terms"]) == 1
                assert terminology_response.json()["terms"][0]["name"] == "guideline"

            except:
                traceback.print_exc()
                raise


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

        result = await asyncio.create_subprocess_exec(*exec_args)
        await result.wait()

        assert result.returncode == os.EX_OK

        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=httpx.Timeout(30),
        ) as client:
            try:
                terminology_response = await client.get(
                    f"{SERVER_ADDRESS}/agents/{agent_id}/terms/{term_name}",
                )
                terminology_response.raise_for_status()

                term = terminology_response.json()
                assert term["name"] == term_name
                assert term["description"] == description
                assert term["synonyms"] is None

            except:
                traceback.print_exc()
                raise


async def test_that_terms_can_be_listed(
    context: ContextOfTest,
    agent_name: str = DEFAULT_AGENT_NAME,
) -> None:
    guideline_term_name = "guideline"
    tool_term_name = "tool"
    guideline_description = "when and then statements"
    tool_description = "techniuqe to fetch external data"
    guideline_synonyms = "rule, instruction"

    with run_server(context):
        await asyncio.sleep(REASONABLE_AMOUNT_OF_TIME)

        agent = load_active_agent(home_dir=context.home_dir, agent_name=agent_name)

        exec_args_1 = [
            "poetry",
            "run",
            "python",
            CLI_CLIENT_PATH.as_posix(),
            "--server",
            SERVER_ADDRESS,
            "glossary",
            "add",
            "--agent-id",
            agent["id"],
            guideline_term_name,
            guideline_description,
            "--synonyms",
            guideline_synonyms,
        ]
        exec_args_2 = [
            "poetry",
            "run",
            "python",
            CLI_CLIENT_PATH.as_posix(),
            "--server",
            SERVER_ADDRESS,
            "glossary",
            "add",
            "--agent-id",
            agent["id"],
            tool_term_name,
            tool_description,
        ]

        assert await (await asyncio.create_subprocess_exec(*exec_args_1)).wait() == os.EX_OK
        assert await (await asyncio.create_subprocess_exec(*exec_args_2)).wait() == os.EX_OK

        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=httpx.Timeout(30),
        ) as client:
            try:
                terminology_response = await client.get(
                    f"{SERVER_ADDRESS}/agents/{agent['id']}/terms/",
                )
                terminology_response.raise_for_status()

                terms = terminology_response.json()["terms"]
                assert len(terms) == 2

                term_names = {term["name"] for term in terms}
                assert guideline_term_name in term_names
                assert tool_term_name in term_names

            except:
                traceback.print_exc()
                raise


async def test_that_a_term_can_be_deleted(
    context: ContextOfTest,
    agent_name: str = DEFAULT_AGENT_NAME,
) -> None:
    name = "guideline_delete"
    description = "to be deleted"
    synonyms = "rule, principle"

    with run_server(context):
        await asyncio.sleep(REASONABLE_AMOUNT_OF_TIME)

        agent = load_active_agent(home_dir=context.home_dir, agent_name=agent_name)

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
            agent["id"],
            name,
            description,
            "--synonyms",
            synonyms,
        ]
        result = await asyncio.create_subprocess_exec(*exec_args)
        await result.wait()

        assert result.returncode == os.EX_OK

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
            agent["id"],
            name,
        ]
        result_delete = await asyncio.create_subprocess_exec(*exec_args_delete)
        await result_delete.wait()

        assert result_delete.returncode == os.EX_OK

        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=httpx.Timeout(30),
        ) as client:
            try:
                terminology_response = await client.get(
                    f"{SERVER_ADDRESS}/agents/{agent['id']}/terms/",
                )
                terminology_response.raise_for_status()

                terms = terminology_response.json()["terms"]
                assert len(terms) == 0

            except:
                traceback.print_exc()
                raise


async def test_that_terms_are_loaded_on_server_startup(
    context: ContextOfTest,
    agent_name: str = DEFAULT_AGENT_NAME,
) -> None:
    term_name = "guideline_no_synonyms"
    description = "simple guideline with no synonyms"

    with run_server(context):
        await asyncio.sleep(REASONABLE_AMOUNT_OF_TIME)

        agent = load_active_agent(home_dir=context.home_dir, agent_name=agent_name)

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
            agent["id"],
            term_name,
            description,
        ]

        result_delete = await asyncio.create_subprocess_exec(*exec_args)
        await result_delete.wait()

        assert result_delete.returncode == os.EX_OK

    with run_server(context):
        await asyncio.sleep(REASONABLE_AMOUNT_OF_TIME)

        agent = load_active_agent(home_dir=context.home_dir, agent_name=agent_name)

        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=httpx.Timeout(30),
        ) as client:
            try:
                terminology_response = await client.get(
                    f"{SERVER_ADDRESS}/agents/{agent['id']}/terms/{term_name}",
                )
                terminology_response.raise_for_status()

                term = terminology_response.json()
                assert term["name"] == term_name
                assert term["description"] == description
                assert term["synonyms"] is None

            except:
                traceback.print_exc()
                raise


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

        result = await asyncio.create_subprocess_exec(*exec_args)
        await result.wait()

        assert result.returncode == os.EX_OK

        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=httpx.Timeout(30),
        ) as client:
            guidelines_response = await client.get(
                f"{SERVER_ADDRESS}/agents/{agent_id}/guidelines/",
            )

            guidelines_response.raise_for_status()

            guidelines = guidelines_response.json()["guidelines"]
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

        exec_args_first = [
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

        result_first = await asyncio.create_subprocess_exec(*exec_args_first)
        await result_first.wait()

        exec_args_conflict = [
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

        result_conflict = await asyncio.create_subprocess_exec(
            *exec_args_conflict,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await result_conflict.communicate()
        output = stdout.decode() + stderr.decode()

        assert "Detected incoherence with other guidelines" in output

        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=httpx.Timeout(30),
        ) as client:
            guidelines_response = await client.get(
                f"{SERVER_ADDRESS}/agents/{agent_id}/guidelines/",
            )

            guidelines_response.raise_for_status()

            guidelines = guidelines_response.json()["guidelines"]

            assert not any(
                g["predicate"] == predicate and g["action"] == conflicting_action
                for g in guidelines
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

        exec_args_first = [
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

        result_first = await asyncio.create_subprocess_exec(*exec_args_first)
        await result_first.wait()

        assert result_first.returncode == os.EX_OK

        exec_args_second = [
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

        result_second = await asyncio.create_subprocess_exec(*exec_args_second)
        await result_second.wait()

        assert result_second.returncode == os.EX_OK

        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=httpx.Timeout(30),
        ) as client:
            guidelines_response = await client.get(
                f"{SERVER_ADDRESS}/agents/{agent_id}/guidelines/",
            )
            guidelines_response.raise_for_status()
            guidelines = guidelines_response.json()["guidelines"]

            assert len(guidelines) == 2
            source = guidelines[0]
            target = guidelines[1]

            source_guideline_response = await client.get(
                f"{SERVER_ADDRESS}/agents/{agent_id}/guidelines/{source['id']}"
            )
            source_guideline_response.raise_for_status()
            source_guideline_connections = source_guideline_response.json()["connections"]

            assert len(source_guideline_connections) == 1
            connection = source_guideline_connections[0]

            assert connection["source"] == source
            assert connection["target"] == target
            assert connection["kind"] == "entails"


async def test_that_guideline_can_be_viewed_via_cli(
    context: ContextOfTest,
) -> None:
    predicate = "the user says goodbye"
    action = "say 'Goodbye' back"

    with run_server(context):
        await asyncio.sleep(REASONABLE_AMOUNT_OF_TIME)

        agent_id = await get_first_agent_id()

        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=httpx.Timeout(30),
        ) as client:
            add_guideline_response = await client.post(
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
                            "approved": True,
                            "data": {
                                "coherence_checks": [],
                                "connection_propositions": None,
                            },
                            "error": None,
                        }
                    ],
                },
            )
            add_guideline_response.raise_for_status()
            added_item = add_guideline_response.json()["items"][0]
            guideline_id = added_item["guideline"]["id"]

        exec_args_view = [
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
            guideline_id,
        ]
        process_view = await asyncio.create_subprocess_exec(
            *exec_args_view,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_view, stderr_view = await process_view.communicate()
        output_view = stdout_view.decode() + stderr_view.decode()
        assert process_view.returncode == os.EX_OK

        assert guideline_id in output_view
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

        exec_args_view = [
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
        process_view = await asyncio.create_subprocess_exec(
            *exec_args_view,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_view, stderr_view = await process_view.communicate()
        output_view = stdout_view.decode() + stderr_view.decode()
        assert process_view.returncode == os.EX_OK

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


async def test_that_guidelines_can_be_listed_via_cli(
    context: ContextOfTest,
) -> None:
    predicate1 = "the user asks for help"
    action1 = "provide assistance"

    predicate2 = "the user needs support"
    action2 = "offer support"

    with run_server(context):
        await asyncio.sleep(REASONABLE_AMOUNT_OF_TIME)

        agent_id = await get_first_agent_id()

        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=httpx.Timeout(30),
        ) as client:
            response_add1 = await client.post(
                f"{SERVER_ADDRESS}/agents/{agent_id}/guidelines/",
                json={
                    "invoices": [
                        {
                            "payload": {
                                "kind": "guideline",
                                "predicate": predicate1,
                                "action": action1,
                            },
                            "checksum": "checksum1",
                            "approved": True,
                            "data": {
                                "coherence_checks": [],
                                "connection_propositions": None,
                            },
                            "error": None,
                        }
                    ],
                },
            )
            response_add1.raise_for_status()

            response_add2 = await client.post(
                f"{SERVER_ADDRESS}/agents/{agent_id}/guidelines/",
                json={
                    "invoices": [
                        {
                            "payload": {
                                "kind": "guideline",
                                "predicate": predicate2,
                                "action": action2,
                            },
                            "checksum": "checksum2",
                            "approved": True,
                            "data": {
                                "coherence_checks": [],
                                "connection_propositions": None,
                            },
                            "error": None,
                        }
                    ],
                },
            )
            response_add2.raise_for_status()

        exec_args_list = [
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
            *exec_args_list,
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


async def test_that_guidelines_can_be_entailed_via_cli(
    context: ContextOfTest,
) -> None:
    predicate1 = "the user needs assistance"
    action1 = "provide help"

    predicate2 = "user ask about a certain subject"
    action2 = "offer detailed explanation"

    with run_server(context):
        await asyncio.sleep(REASONABLE_AMOUNT_OF_TIME)

        agent_id = await get_first_agent_id()

        exec_args_add1 = [
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
        result_add1 = await asyncio.create_subprocess_exec(*exec_args_add1)
        await result_add1.wait()
        assert result_add1.returncode == os.EX_OK

        exec_args_add2 = [
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
        result_add2 = await asyncio.create_subprocess_exec(*exec_args_add2)
        await result_add2.wait()
        assert result_add2.returncode == os.EX_OK

        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=httpx.Timeout(30),
        ) as client:
            guidelines_response = await client.get(
                f"{SERVER_ADDRESS}/agents/{agent_id}/guidelines/"
            )
            guidelines_response.raise_for_status()
            guidelines = guidelines_response.json()["guidelines"]

            guideline1 = next(
                g for g in guidelines if g["predicate"] == predicate1 and g["action"] == action1
            )
            guideline2 = next(
                g for g in guidelines if g["predicate"] == predicate2 and g["action"] == action2
            )

        exec_args_connect = [
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
            guideline1["id"],
            guideline2["id"],
        ]
        process_connect = await asyncio.create_subprocess_exec(
            *exec_args_connect,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await process_connect.communicate()
        await process_connect.wait()
        assert process_connect.returncode == os.EX_OK

        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=httpx.Timeout(30),
        ) as client:
            guideline_response = await client.get(
                f"{SERVER_ADDRESS}/agents/{agent_id}/guidelines/{guideline1['id']}"
            )
            guideline_response.raise_for_status()
            guideline_data = guideline_response.json()

            assert "connections" in guideline_data and len(guideline_data["connections"]) == 1
            connection = guideline_data["connections"][0]
            assert (
                connection["source"] == guideline1
                and connection["target"] == guideline2
                and connection["kind"] == "entails"
            )


async def test_that_guidelines_can_be_suggestively_entailed_via_cli(
    context: ContextOfTest,
) -> None:
    predicate1 = "the user needs assistance"
    action1 = "provide help"

    predicate2 = "user ask about a certain subject"
    action2 = "offer detailed explanation"

    with run_server(context):
        await asyncio.sleep(REASONABLE_AMOUNT_OF_TIME)

        agent_id = await get_first_agent_id()

        exec_args_add1 = [
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
        result_add1 = await asyncio.create_subprocess_exec(*exec_args_add1)
        await result_add1.wait()
        assert result_add1.returncode == os.EX_OK

        exec_args_add2 = [
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
        result_add2 = await asyncio.create_subprocess_exec(*exec_args_add2)
        await result_add2.wait()
        assert result_add2.returncode == os.EX_OK

        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=httpx.Timeout(30),
        ) as client:
            guidelines_response = await client.get(
                f"{SERVER_ADDRESS}/agents/{agent_id}/guidelines/"
            )
            guidelines_response.raise_for_status()
            guidelines = guidelines_response.json()["guidelines"]

            guideline1 = next(
                g for g in guidelines if g["predicate"] == predicate1 and g["action"] == action1
            )
            guideline2 = next(
                g for g in guidelines if g["predicate"] == predicate2 and g["action"] == action2
            )

        exec_args_connect = [
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
            guideline1["id"],
            guideline2["id"],
        ]
        process_connect = await asyncio.create_subprocess_exec(
            *exec_args_connect,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await process_connect.communicate()
        await process_connect.wait()
        assert process_connect.returncode == os.EX_OK

        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=httpx.Timeout(30),
        ) as client:
            guideline_response = await client.get(
                f"{SERVER_ADDRESS}/agents/{agent_id}/guidelines/{guideline1['id']}"
            )
            guideline_response.raise_for_status()
            guideline_data = guideline_response.json()

            assert "connections" in guideline_data and len(guideline_data["connections"]) == 1
            connection = guideline_data["connections"][0]
            assert (
                connection["source"] == guideline1
                and connection["target"] == guideline2
                and connection["kind"] == "suggests"
            )


async def test_that_guideline_can_be_removed_cli(
    context: ContextOfTest,
) -> None:
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
                                "predicate": "the user greets you",
                                "action": "greet them back with 'Hello'",
                            },
                            "checksum": "checksum_value",
                            "approved": True,
                            "data": {
                                "coherence_checks": [],
                                "connection_propositions": None,
                            },
                            "error": None,
                        }
                    ]
                },
            )

            add_guidelines_response.raise_for_status()

            guideline_id = add_guidelines_response.json()["items"][0]["guideline"]["id"]

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
            guideline_id,
        ]

        result = await asyncio.create_subprocess_exec(*exec_args)
        await result.wait()

        assert result.returncode == os.EX_OK

        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=httpx.Timeout(30),
        ) as client:
            add_guidelines_response = await client.get(
                f"{SERVER_ADDRESS}/agents/{agent_id}/guidelines/{guideline_id}",
            )

            assert add_guidelines_response.status_code == httpx.codes.NOT_FOUND


async def test_that_connection_can_be_removed_via_cli(
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

        result = await asyncio.create_subprocess_exec(*exec_args)
        await result.wait()

        assert result.returncode == os.EX_OK

        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=httpx.Timeout(30),
        ) as client:
            guidelines_response = await client.get(
                f"{SERVER_ADDRESS}/agents/{agent_id}/guidelines/{first}",
            )

            assert len(guidelines_response.json()["connections"]) == 0


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

        async with httpx.AsyncClient(
            base_url=SERVER_ADDRESS,
            follow_redirects=True,
            timeout=httpx.Timeout(30),
        ) as client:
            _ = (
                (
                    await client.post(
                        f"/agents/{agent_id}/variables",
                        json={
                            "name": name1,
                            "description": description1,
                        },
                    )
                )
                .raise_for_status()
                .json()["variable"]
            )

            _ = (
                (
                    await client.post(
                        f"/agents/{agent_id}/variables",
                        json={
                            "name": name2,
                            "description": description2,
                        },
                    )
                )
                .raise_for_status()
                .json()["variable"]
            )

            exec_args_list = [
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

            process_list = await asyncio.create_subprocess_exec(
                *exec_args_list,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_list, stderr_list = await process_list.communicate()
            output_list = stdout_list.decode() + stderr_list.decode()

            assert process_list.returncode == os.EX_OK

            assert name1 in output_list
            assert description1 in output_list
            assert name2 in output_list
            assert description2 in output_list


async def test_that_variable_can_be_added(
    context: ContextOfTest,
) -> None:
    name = "test_variable_cli"
    description = "Variable added via CLI"

    with run_server(context):
        await asyncio.sleep(REASONABLE_AMOUNT_OF_TIME)

        agent_id = await get_first_agent_id()

        exec_args_add = [
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
        result_add = await asyncio.create_subprocess_exec(*exec_args_add)
        await result_add.wait()
        assert result_add.returncode == os.EX_OK

        async with httpx.AsyncClient(
            base_url=SERVER_ADDRESS,
            follow_redirects=True,
            timeout=httpx.Timeout(30),
        ) as client:
            response_list = await client.get(f"/agents/{agent_id}/variables/")
            response_list.raise_for_status()
            variables = response_list.json()["variables"]

            added_variable = next(
                (v for v in variables if v["name"] == name and v["description"] == description),
                None,
            )
            assert added_variable is not None, "Variable was not added"


async def test_that_variable_can_be_removed(
    context: ContextOfTest,
) -> None:
    name = "test_variable_to_remove"
    description = "Variable to be removed via CLI"

    with run_server(context):
        await asyncio.sleep(REASONABLE_AMOUNT_OF_TIME)

        agent_id = await get_first_agent_id()

        async with httpx.AsyncClient(
            base_url=SERVER_ADDRESS,
            follow_redirects=True,
            timeout=httpx.Timeout(30),
        ) as client:
            response_add = await client.post(
                f"/agents/{agent_id}/variables",
                json={
                    "name": name,
                    "description": description,
                },
            )
            response_add.raise_for_status()

        exec_args_remove = [
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
        result_remove = await asyncio.create_subprocess_exec(*exec_args_remove)
        await result_remove.wait()
        assert result_remove.returncode == os.EX_OK

        async with httpx.AsyncClient(
            base_url=SERVER_ADDRESS,
            follow_redirects=True,
            timeout=httpx.Timeout(30),
        ) as client:
            response_list = await client.get(f"/agents/{agent_id}/variables/")
            response_list.raise_for_status()
            variables = response_list.json()["variables"]

            removed_variable = next(
                (v for v in variables if v["name"] == name and v["description"] == description),
                None,
            )
            assert removed_variable is None, "Variable was not removed"


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

        async with httpx.AsyncClient(
            base_url=SERVER_ADDRESS,
            follow_redirects=True,
            timeout=httpx.Timeout(30),
        ) as client:
            response_add = await client.post(
                f"/agents/{agent_id}/variables",
                json={
                    "name": variable_name,
                    "description": variable_description,
                },
            )
            response_add.raise_for_status()
            variable = response_add.json()["variable"]
            variable_id = variable["id"]

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
        result_set = await asyncio.create_subprocess_exec(*exec_args_set)
        await result_set.wait()
        assert result_set.returncode == os.EX_OK

        async with httpx.AsyncClient(
            base_url=SERVER_ADDRESS,
            follow_redirects=True,
            timeout=httpx.Timeout(30),
        ) as client:
            response_get_value = await client.get(
                f"/agents/{agent_id}/variables/{variable_id}/{key}"
            )
            response_get_value.raise_for_status()

            retrieved_data = response_get_value.json()["data"]
            assert retrieved_data == data


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

        async with httpx.AsyncClient(
            base_url=SERVER_ADDRESS,
            follow_redirects=True,
            timeout=httpx.Timeout(30),
        ) as client:
            response_add = await client.post(
                f"/agents/{agent_id}/variables",
                json={
                    "name": variable_name,
                    "description": variable_description,
                },
            )
            response_add.raise_for_status()
            variable = response_add.json()["variable"]
            variable_id = variable["id"]

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
        result_set = await asyncio.create_subprocess_exec(*exec_args_set)
        await result_set.wait()
        assert result_set.returncode == os.EX_OK

        async with httpx.AsyncClient(
            base_url=SERVER_ADDRESS,
            follow_redirects=True,
            timeout=httpx.Timeout(30),
        ) as client:
            response_get_value = await client.get(
                f"/agents/{agent_id}/variables/{variable_id}/{key}"
            )
            response_get_value.raise_for_status()

            retrieved_data = response_get_value.json()["data"]
            assert retrieved_data == data


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

        async with httpx.AsyncClient(
            base_url=SERVER_ADDRESS,
            follow_redirects=True,
            timeout=httpx.Timeout(30),
        ) as client:
            response_add = await client.post(
                f"/agents/{agent_id}/variables",
                json={
                    "name": variable_name,
                    "description": variable_description,
                },
            )
            response_add.raise_for_status()
            variable = response_add.json()["variable"]
            variable_id = variable["id"]

            for key, data in values.items():
                response_set_value = await client.put(
                    f"/agents/{agent_id}/variables/{variable_id}/{key}",
                    json={"data": data},
                )
                response_set_value.raise_for_status()

        exec_args_get_all = [
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
        process_get_all = await asyncio.create_subprocess_exec(
            *exec_args_get_all,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_get_all_values, stderr_get_all = await process_get_all.communicate()
        output_get_all_values = stdout_get_all_values.decode() + stderr_get_all.decode()
        assert process_get_all.returncode == os.EX_OK

        for key, data in values.items():
            assert key in output_get_all_values
            assert data in output_get_all_values

        specific_key = "key2"
        expected_value = values[specific_key]

        exec_args_get_key = [
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
        process_get_key = await asyncio.create_subprocess_exec(
            *exec_args_get_key,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_get_value_by_key, stderr_get_key = await process_get_key.communicate()
        output_get_value_by_key = stdout_get_value_by_key.decode() + stderr_get_key.decode()
        assert process_get_key.returncode == os.EX_OK

        assert specific_key in output_get_value_by_key
        assert expected_value in output_get_value_by_key
