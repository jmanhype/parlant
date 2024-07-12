import os
import signal
import time

from tests.e2e.test_utilities import (
    _Guideline,
    _TestContext,
    find_guideline,
    read_guideline_config,
    read_loaded_guidelines,
    run_server,
    write_guideline_config,
)


REASONABLE_AMOUNT_OF_TIME = 5


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
