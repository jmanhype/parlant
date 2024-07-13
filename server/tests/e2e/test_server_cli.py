import os
import signal
import time
import requests  # type: ignore

from tests.e2e.test_utilities import (
    DEFAULT_AGENT_NAME,
    SERVER_ADDRESS,
    _Guideline,
    _TestContext,
    find_guideline,
    load_active_agent,
    read_guideline_config,
    read_loaded_guidelines,
    run_server,
    write_guideline_config,
)
from tests.test_utilities import nlp_test


REASONABLE_AMOUNT_OF_TIME = 5


def get_quick_reply_from_agent(
    context: _TestContext,
    message: str,
    agent_name: str = DEFAULT_AGENT_NAME,
) -> str:
    agent = load_active_agent(home_dir=context.home_dir, agent_name=agent_name)

    session_creation_response = requests.post(
        f"{SERVER_ADDRESS}/sessions",
        json={
            "end_user_id": "test_user",
            "agent_id": agent["id"],
        },
    )
    session_creation_response.raise_for_status()
    session_id = session_creation_response.json()["session_id"]

    user_message_response = requests.post(
        f"{SERVER_ADDRESS}/sessions/{session_id}/events",
        json={
            "content": message,
        },
    )
    user_message_response.raise_for_status()
    user_message_offset = int(user_message_response.json()["event_offset"])

    response = requests.get(
        f"{SERVER_ADDRESS}/sessions/{session_id}/events",
        params={
            "min_offset": user_message_offset + 1,
            "wait": True,
        },
    )

    response.raise_for_status()

    return str(response.json()["events"][0]["data"]["message"])


def test_server_starts_and_shuts_down_cleanly_on_interrupt(
    context: _TestContext,
) -> None:
    with run_server(context) as server_process:
        time.sleep(REASONABLE_AMOUNT_OF_TIME)
        server_process.send_signal(signal.SIGINT)
        server_process.wait(timeout=REASONABLE_AMOUNT_OF_TIME)
        assert server_process.returncode == os.EX_OK


def test_server_hot_reloads_guideline_changes(
    context: _TestContext,
) -> None:
    with run_server(context):
        initial_guidelines = read_guideline_config(context.config_file)

        new_guideline: _Guideline = {
            "when": "talking about bananas",
            "then": "say they're very tasty",
        }

        write_guideline_config(
            new_guidelines=initial_guidelines + [new_guideline],
            config_file=context.config_file,
        )

        time.sleep(REASONABLE_AMOUNT_OF_TIME)

        loaded_guidelines = read_loaded_guidelines(context.home_dir)

        assert find_guideline(new_guideline, within=loaded_guidelines)

        agent_reply = get_quick_reply_from_agent(context, message="what are bananas?")

        assert nlp_test(agent_reply, "It says that bananas are very tasty")
