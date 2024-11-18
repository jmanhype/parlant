import asyncio
import tempfile
import time
from pathlib import Path
from pytest import fixture
from typing import Any, Iterator

from parlant.client import ParlantClient
from parlant.client.types.agent import Agent  # OR from parlant.client import Agent
from parlant.client.types.create_agent_request import CreateAgentRequest
from parlant.client.types.guideline_content import GuidelineContent
from parlant.client.types.guideline_invoice import GuidelineInvoice
from parlant.client.types.guideline_payload import GuidelinePayload
from parlant.client.types.guideline_tool_associations_patch import (
    GuidelineToolAssociationsPatch,
)
from parlant.client.types.guideline_with_connections_and_tool_associations import (
    GuidelineWithConnectionsAndToolAssociations,
)
from parlant.client.types import CreateSdkServiceRequest
from parlant.client.types.term import Term
from parlant.client.types.tool_id import ToolId

from tests.e2e.test_utilities import (
    SERVER_ADDRESS,
    ContextOfTest,
    run_server,
)
from tests.client.example_plugin import (
    PLUGIN_PORT,
    PLUGIN_ADDRESS,
)

REASONABLE_AMOUNT_OF_TIME = 5

CLI_PLUGIN_PATH = "tests/client/example_plugin.py"


@fixture
def context() -> Iterator[ContextOfTest]:
    with tempfile.TemporaryDirectory(prefix="parlant-client_test_") as home_dir:
        home_dir_path = Path(home_dir)

        yield ContextOfTest(
            home_dir=home_dir_path,
        )


async def run_cli(*args: str, **kwargs: Any) -> asyncio.subprocess.Process:
    exec_args = ["poetry", "run", "python"] + list(args)
    return await asyncio.create_subprocess_exec(*exec_args, **kwargs)


def make_parlant_client(base_url: str) -> ParlantClient:
    client = ParlantClient(base_url=base_url)
    print(f"ParlantClient created with server=`{base_url}`.")
    return client


def make_api_agent(client: ParlantClient, name: str) -> Agent:
    create_agent_request = CreateAgentRequest(name=name)
    create_agent_reponse = client.create_agent(request=create_agent_request)
    print(f"Agent `{name}` created.")
    return create_agent_reponse.agent


def make_guideline_evaluation(
    client: ParlantClient,
    agent_id: str,
    action: str,
    condition: str,
) -> str:
    guideline_payload = GuidelinePayload(
        coherence_check=True,
        connection_proposition=True,
        content=GuidelineContent(action=action, condition=condition),
        kind="guideline",
        operation="add",
    )

    create_evaluation_response = client.create_evaluation(
        agent_id=agent_id,
        payloads=[guideline_payload],
    )
    print(f"Evaluation created with id=`{create_evaluation_response.evaluation_id}`")
    return create_evaluation_response.evaluation_id


def make_guideline(
    client: ParlantClient,
    agent_id: str,
    action: str,
    condition: str,
) -> GuidelineWithConnectionsAndToolAssociations:
    evaluation_id = make_guideline_evaluation(
        client=client,
        agent_id=agent_id,
        action=action,
        condition=condition,
    )

    while True:
        read_evaluation_response = client.read_evaluation(evaluation_id=evaluation_id)

        if read_evaluation_response.status == "running":
            time.sleep(1)
            continue

        if read_evaluation_response.status != "completed":
            raise Exception(read_evaluation_response.status)

        guidelines_invoices: list[GuidelineInvoice] = []

        for invoice in read_evaluation_response.invoices:
            if invoice.data is None:
                continue

            guidelines_invoices.append(
                GuidelineInvoice(
                    payload=invoice.payload,
                    checksum=invoice.checksum,
                    approved=invoice.approved,
                    data=invoice.data,
                    error=invoice.error,
                ),
            )

        guidelines_create_response = client.create_guidelines(
            agent_id,
            invoices=guidelines_invoices,
        )
        print(f"Created Guideline item=`{guidelines_create_response.items[0]}`")
        return guidelines_create_response.items[0]


def make_term(
    client: ParlantClient,
    agent_id: str,
    name: str,
    description: str,
    synonyms: list[str] | None,
) -> Term:
    create_term_response = client.create_term(
        agent_id=agent_id, name=name, description=description, synonyms=synonyms
    )
    print(f"Created Term `{name}~{synonyms}`='{description}'")
    return create_term_response.term


def make_service_tool_association(
    client: ParlantClient,
    agent_id: str,
    guideline_id: str,
    tool_name: str,
    tool_url: str,
) -> None:
    _create_service_response = client.upsert_service(
        tool_name,
        request=CreateSdkServiceRequest(url=tool_url),
    )
    service = client.read_service(tool_name)
    assert service.tools
    tool_randoms_flip = service.tools[1]
    tool_randoms_roll = service.tools[2]
    print("Got tools from service.")
    _patch_guildeline_reponse = client.patch_guideline(
        agent_id,
        guideline_id,
        tool_associations=GuidelineToolAssociationsPatch(
            add=[
                ToolId(service_name=service.name, tool_name=tool_randoms_flip.name),
                ToolId(service_name=service.name, tool_name=tool_randoms_roll.name),
            ]
        ),
    )
    print("Patched guideline with relevant tools.")


async def test_parlant_client_happy_path(context: ContextOfTest) -> None:
    with run_server(context):
        await asyncio.sleep(REASONABLE_AMOUNT_OF_TIME)
        _process = await run_cli(CLI_PLUGIN_PATH, str(PLUGIN_PORT))
        await asyncio.sleep(REASONABLE_AMOUNT_OF_TIME)

        client = make_parlant_client(base_url=SERVER_ADDRESS)

        agent = make_api_agent(client=client, name="demo-agent")

        guideline_randoms = make_guideline(
            client=client,
            agent_id=agent.id,
            action="Use the randoms tool to either flip coins or roll dice.",
            condition="The users wants a random number.",
        )
        assert guideline_randoms

        _term = make_term(
            client=client,
            agent_id=agent.id,
            name="Melupapepkin",
            description="A word that's meaning should be ignored. Serves as an arbitrary identifier.",
            synonyms=["Shoshanna", "Moshe"],
        )
        assert _term

        make_service_tool_association(
            client=client,
            agent_id=agent.id,
            guideline_id=guideline_randoms.guideline.id,
            tool_name="randoms",
            tool_url=PLUGIN_ADDRESS,
        )

        create_session_response = client.create_session(
            end_user_id="end_user",
            agent_id=agent.id,
        )
        assert create_session_response
        demo_session = create_session_response.session

        create_event_response = client.create_event(
            demo_session.id,
            kind="message",
            source="end_user",
            content="Heads or tails?",
            moderation="auto",
        )
        assert create_event_response

        last_known_offset = create_event_response.event.offset
        list_interaction_response = client.list_interactions(
            demo_session.id,
            min_event_offset=last_known_offset,
            source="ai_agent",
            wait=True,
        )

        for interaction in list_interaction_response.interactions:
            assert interaction.data
            print(interaction.data)
