import asyncio
import os
import traceback
import httpx
from emcie.server.core.agents import Agent
from tests.e2e.test_server_cli import REASONABLE_AMOUNT_OF_TIME
from tests.e2e.test_utilities import (
    CLI_CLIENT_PATH,
    DEFAULT_AGENT_NAME,
    SERVER_ADDRESS,
    ContextOfTest,
    load_active_agent,
    run_server,
)

REASONABLE_AMOUNT_OF_TIME_FOR_TERM_CREATION = 0.25


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
            )

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

        agent = await get_first_agent()

        exec_args = [
            "poetry",
            "run",
            "python",
            CLI_CLIENT_PATH.as_posix(),
            "--server",
            SERVER_ADDRESS,
            "terminology",
            "add",
            "--agent-id",
            agent.id,
            "--name",
            term_name,
            "--description",
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
                    f"{SERVER_ADDRESS}/terminology/{agent.id}",
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

        agent = await get_first_agent()

        exec_args = [
            "poetry",
            "run",
            "python",
            CLI_CLIENT_PATH.as_posix(),
            "--server",
            SERVER_ADDRESS,
            "terminology",
            "add",
            "--agent-id",
            agent.id,
            "--name",
            term_name,
            "--description",
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
                    f"{SERVER_ADDRESS}/terminology/{agent.id}/{term_name}",
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
            "terminology",
            "add",
            "--agent-id",
            agent["id"],
            "--name",
            guideline_term_name,
            "--description",
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
            "terminology",
            "add",
            "--agent-id",
            agent["id"],
            "--name",
            tool_term_name,
            "--description",
            tool_description,
        ]

        await asyncio.create_subprocess_exec(*exec_args_1)
        result = await asyncio.create_subprocess_exec(*exec_args_2)
        await result.wait()

        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=httpx.Timeout(30),
        ) as client:
            try:
                terminology_response = await client.get(
                    f"{SERVER_ADDRESS}/terminology/{agent['id']}",
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
            "terminology",
            "add",
            "--agent-id",
            agent["id"],
            "--name",
            name,
            "--description",
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
            "terminology",
            "delete",
            "--agent-id",
            agent["id"],
            "--name",
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
                    f"{SERVER_ADDRESS}/terminology/{agent['id']}",
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
            "terminology",
            "add",
            "--agent-id",
            agent["id"],
            "--name",
            term_name,
            "--description",
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
                    f"{SERVER_ADDRESS}/terminology/{agent['id']}/{term_name}",
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

        agent = await get_first_agent()

        exec_args = [
            "poetry",
            "run",
            "python",
            CLI_CLIENT_PATH.as_posix(),
            "--server",
            SERVER_ADDRESS,
            "guidelines",
            "add",
            "-a",
            agent.id,
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
                f"{SERVER_ADDRESS}/guidelines/{agent.id}",
            )

            guidelines_response.raise_for_status()

            guidelines = guidelines_response.json()["guidelines"]
            assert any(g["predicate"] == predicate and g["action"] == action for g in guidelines)


async def test_that_adding_conflicting_guideline_shows_contradictions_error(
    context: ContextOfTest,
) -> None:
    predicate = "the user greets you"
    action = "greet them back with 'Hello'"

    conflicting_action = "ignore the user"

    with run_server(context):
        await asyncio.sleep(REASONABLE_AMOUNT_OF_TIME)

        agent = await get_first_agent()

        exec_args_first = [
            "poetry",
            "run",
            "python",
            CLI_CLIENT_PATH.as_posix(),
            "--server",
            SERVER_ADDRESS,
            "guidelines",
            "add",
            "-a",
            agent.id,
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
            "guidelines",
            "add",
            "-a",
            agent.id,
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

        assert "Contradictions found" in output

        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=httpx.Timeout(30),
        ) as client:
            guidelines_response = await client.get(
                f"{SERVER_ADDRESS}/guidelines/{agent.id}",
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

    predicate2 = "provide a weather update"
    action2 = "include temperature and humidity"

    with run_server(context):
        await asyncio.sleep(REASONABLE_AMOUNT_OF_TIME)

        agent = await get_first_agent()

        exec_args_first = [
            "poetry",
            "run",
            "python",
            CLI_CLIENT_PATH.as_posix(),
            "--server",
            SERVER_ADDRESS,
            "guidelines",
            "add",
            "-a",
            agent.id,
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
            "guidelines",
            "add",
            "-a",
            agent.id,
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
                f"{SERVER_ADDRESS}/guidelines/{agent.id}",
            )
            guidelines_response.raise_for_status()

            guidelines = guidelines_response.json()["guidelines"]

            assert len(guidelines) == 2
            source = guidelines[0]
            target = guidelines[1]

            connections_response = (
                await client.get(
                    f"{SERVER_ADDRESS}/connections/?source_guideline_id={source["id"]}&indirect=false",
                )
            ).raise_for_status()

            connections = connections_response.json()["connections"]

            assert len(connections) == 1
            connection = connections[0]

            assert connection["source"] == source["id"]
            assert connection["target"] == target["id"]
            assert connection["kind"] == "entails"


async def test_that_guideline_can_be_viewed_via_cli(
    context: ContextOfTest,
) -> None:
    predicate = "the user says goodbye"
    action = "say 'Goodbye' back"

    with run_server(context):
        await asyncio.sleep(REASONABLE_AMOUNT_OF_TIME)

        agent = await get_first_agent()

        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=httpx.Timeout(30),
        ) as client:
            response_add = await client.post(
                f"{SERVER_ADDRESS}/guidelines/",
                json={
                    "agent_id": agent.id,
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
            response_add.raise_for_status()
            added_guideline = response_add.json()["guidelines"][0]
            guideline_id = added_guideline["id"]

        exec_args_view = [
            "poetry",
            "run",
            "python",
            CLI_CLIENT_PATH.as_posix(),
            "--server",
            SERVER_ADDRESS,
            "guidelines",
            "view",
            "-a",
            agent.id,
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

        assert f"Guideline ID: {guideline_id}" in output_view
        assert f"Predicate: {predicate}" in output_view
        assert f"Action: {action}" in output_view


async def test_that_view_guideline_with_connections_displays_connections(
    context: ContextOfTest,
) -> None:
    predicate1 = "the user asks for help"
    action1 = "provide assistance"

    predicate2 = "provide assistance"
    action2 = "ask for clarification if needed"

    with run_server(context):
        await asyncio.sleep(REASONABLE_AMOUNT_OF_TIME)

        agent = await get_first_agent()

        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=httpx.Timeout(30),
        ) as client:
            response = await client.post(
                f"{SERVER_ADDRESS}/guidelines/",
                json={
                    "agent_id": agent.id,
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
            response.raise_for_status()
            first = response.json()["guidelines"][0]

            response = await client.post(
                f"{SERVER_ADDRESS}/guidelines/",
                json={
                    "agent_id": agent.id,
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
            response.raise_for_status()
            second = response.json()["guidelines"][0]

            response_connection = await client.post(
                f"{SERVER_ADDRESS}/connections",
                json={
                    "source_guideline_id": first["id"],
                    "target_guideline_id": second["id"],
                    "kind": "entails",
                },
            )
            response_connection.raise_for_status()
            connection = response_connection.json()
            connection_id = connection["id"]

        exec_args_view = [
            "poetry",
            "run",
            "python",
            CLI_CLIENT_PATH.as_posix(),
            "--server",
            SERVER_ADDRESS,
            "guidelines",
            "view",
            "-a",
            agent.id,
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

        assert f"Guideline ID: {first["id"]}" in output_view
        assert f"Predicate: {predicate1}" in output_view
        assert f"Action: {action1}" in output_view

        assert "Connections:" in output_view

        assert first["id"] in output_view
        assert second["id"] in output_view
        assert connection_id in output_view
        assert "entails" in output_view
