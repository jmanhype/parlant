import asyncio
import time
from typing import Any, AsyncIterator

from pytest import fixture
import zmq
import zmq.asyncio

from parlant.core.contextual_correlator import ContextualCorrelator
from parlant.core.logging import LogLevel, ZMQLogger

PARLANT_LOG_PORT = 8779


@fixture
async def zmq_logger() -> AsyncIterator[ZMQLogger]:
    correlator = ContextualCorrelator()

    async with ZMQLogger(
        correlator=correlator,
        log_level=LogLevel.DEBUG,
        logger_id="test_zmq_logger",
        port=PARLANT_LOG_PORT,
    ) as zmq_logger:
        yield zmq_logger


async def _recv_all_messages(
    sub_socket: zmq.asyncio.Socket,
) -> list[Any]:
    poller = zmq.asyncio.Poller()
    poller.register(sub_socket, zmq.POLLIN)
    cutoff = time.time() + 0.3

    messages = []
    while time.time() < cutoff:
        socks = dict(await poller.poll(10))
        if sub_socket in socks and socks[sub_socket] == zmq.POLLIN:
            messages.append(sub_socket.recv_json(zmq.NOBLOCK))
        else:
            await asyncio.sleep(0.01)
    return messages


async def test_that_zmq_logger_emits_logs(zmq_logger: ZMQLogger) -> None:
    context = zmq.asyncio.Context.instance()
    sub_socket = context.socket(zmq.SUB)
    sub_socket.connect(f"tcp://localhost:{PARLANT_LOG_PORT}")
    sub_socket.setsockopt_string(zmq.SUBSCRIBE, "")

    await asyncio.sleep(1)

    zmq_logger.debug("Debug message test")
    zmq_logger.info("Info message test")

    received = await _recv_all_messages(sub_socket)
    sub_socket.close()

    assert any("Debug message test" in json_log.result()["message"] for json_log in received)
    assert any("Info message test" in json_log.result()["message"] for json_log in received)
