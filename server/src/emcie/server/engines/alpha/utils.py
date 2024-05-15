from contextlib import contextmanager
import json
import os
import time
from typing import Any, Iterable, Literal
from loguru import logger
from openai import AsyncClient

from emcie.server.sessions import Event


def make_llm_client(provider: Literal["openai", "together"]) -> AsyncClient:
    if provider == "openai":
        return AsyncClient(api_key=os.environ["OPENAI_API_KEY"])
    elif provider == "together":
        return AsyncClient(
            api_key=os.environ["TOGETHER_API_KEY"],
            base_url="https://api.together.xyz/v1",
        )


@contextmanager
def duration_logger(operation_name: str) -> Any:
    t_start = time.time()

    try:
        yield
    finally:
        t_end = time.time()
        logger.info(f"{operation_name} took {round(t_end - t_start, 3)}s")


def events_to_json(events: Iterable[Event]) -> str:
    event_dicts = [event_to_dict(e) for e in events]
    return json.dumps(event_dicts)


def event_to_dict(event: Event) -> dict[str, Any]:
    return {
        "id": event.id,
        "type": event.type,
        "source": {
            "client": "user",
            "server": "assistant",
        }.get(event.source),
        "data": event.data,
    }
