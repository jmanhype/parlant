from fastapi import FastAPI

from emcie.server.api import threads
from emcie.server.threads import ThreadStore


def create_app() -> FastAPI:
    thread_store = ThreadStore()

    app = FastAPI()

    app.mount(
        "/threads",
        threads.create_router(
            thread_store=thread_store,
        ),
    )

    return app
