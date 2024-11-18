import asyncio
import os
from typing import Awaitable, Callable, TypeAlias

from fastapi import APIRouter, FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.types import Receive, Scope, Send
from lagom import Container

from parlant.api import agents, index
from parlant.api import sessions
from parlant.api import glossary
from parlant.api import guidelines
from parlant.api import context_variables as variables
from parlant.api import services
from parlant.api import end_users
from parlant.core.context_variables import ContextVariableStore
from parlant.core.contextual_correlator import ContextualCorrelator
from parlant.core.agents import AgentStore
from parlant.core.common import ItemNotFoundError, generate_id
from parlant.core.end_users import EndUserStore
from parlant.core.evaluations import EvaluationStore
from parlant.core.guideline_connections import GuidelineConnectionStore
from parlant.core.guidelines import GuidelineStore
from parlant.core.guideline_tool_associations import GuidelineToolAssociationStore
from parlant.core.services.tools.service_registry import ServiceRegistry
from parlant.core.sessions import SessionListener, SessionStore
from parlant.core.glossary import GlossaryStore
from parlant.core.services.indexing.behavioral_change_evaluation import (
    BehavioralChangeEvaluator,
)
from parlant.core.logging import Logger
from parlant.core.application import Application

ASGIApplication: TypeAlias = Callable[
    [
        Scope,
        Receive,
        Send,
    ],
    Awaitable[None],
]


class AppWrapper:
    def __init__(self, app: FastAPI) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """FastAPI's built-in exception handling doesn't catch BaseExceptions
        such as asyncio.CancelledError. This causes the server process to terminate
        with an ugly traceback. This wrapper addresses that by specifically allowing
        asyncio.CancelledError to gracefully exit.
        """
        try:
            return await self.app(scope, receive, send)
        except asyncio.CancelledError:
            pass


async def create_api_app(container: Container) -> ASGIApplication:
    logger = container[Logger]
    correlator = container[ContextualCorrelator]
    agent_store = container[AgentStore]
    end_user_store = container[EndUserStore]
    session_store = container[SessionStore]
    session_listener = container[SessionListener]
    evaluation_store = container[EvaluationStore]
    evaluation_service = container[BehavioralChangeEvaluator]
    glossary_store = container[GlossaryStore]
    guideline_store = container[GuidelineStore]
    guideline_connection_store = container[GuidelineConnectionStore]
    guideline_tool_association_store = container[GuidelineToolAssociationStore]
    context_variable_store = container[ContextVariableStore]
    service_registry = container[ServiceRegistry]
    application = container[Application]

    api_app = FastAPI()

    @api_app.middleware("http")
    async def handle_cancellation(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        try:
            return await call_next(request)
        except asyncio.CancelledError:
            return Response(status_code=status.HTTP_503_SERVICE_UNAVAILABLE)

    api_app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @api_app.middleware("http")
    async def add_correlation_id(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        with correlator.correlation_scope(f"request({generate_id()})"):
            logger.info(f"{request.method} {request.url.path}")
            return await call_next(request)

    @api_app.exception_handler(ItemNotFoundError)
    async def item_not_found_error_handler(
        request: Request, exc: ItemNotFoundError
    ) -> HTTPException:
        logger.info(str(exc))

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )

    agent_router = APIRouter()

    static_dir = os.path.join(os.path.dirname(__file__), "chat/dist")
    api_app.mount("/chat", StaticFiles(directory=static_dir, html=True), name="static")

    @api_app.get("/")
    async def root() -> Response:
        return RedirectResponse("/chat")

    agent_router.include_router(
        agents.create_router(
            agent_store=agent_store,
        )
    )

    agent_router.include_router(
        guidelines.create_router(
            application=application,
            guideline_store=guideline_store,
            guideline_connection_store=guideline_connection_store,
            service_registry=service_registry,
            guideline_tool_association_store=guideline_tool_association_store,
        )
    )
    agent_router.include_router(
        glossary.create_router(
            glossary_store=glossary_store,
        )
    )
    agent_router.include_router(
        variables.create_router(
            context_variable_store=context_variable_store,
            service_registry=service_registry,
        )
    )

    api_app.include_router(
        prefix="/agents",
        router=agent_router,
    )

    api_app.include_router(
        prefix="/sessions",
        router=sessions.create_router(
            application=application,
            agent_store=agent_store,
            end_user_store=end_user_store,
            session_store=session_store,
            session_listener=session_listener,
            service_registry=service_registry,
        ),
    )

    api_app.include_router(
        prefix="/index",
        router=index.create_router(
            evaluation_service=evaluation_service,
            evaluation_store=evaluation_store,
            agent_store=agent_store,
        ),
    )

    api_app.include_router(
        prefix="/services",
        router=services.create_router(
            service_registry=service_registry,
        ),
    )

    api_app.include_router(
        prefix="/end-users",
        router=end_users.create_router(
            end_user_store=end_user_store,
        ),
    )

    return AppWrapper(api_app)
