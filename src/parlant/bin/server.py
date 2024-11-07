# mypy: disable-error-code=import-untyped

import asyncio
from contextlib import asynccontextmanager, AsyncExitStack
from dataclasses import dataclass
from enum import Enum, auto
import os
from fastapi import FastAPI
from lagom import Container, Singleton
from typing import AsyncIterator
import click
import click_completion
from pathlib import Path
import sys
import uvicorn

from parlant import VERSION
from parlant.adapters.db.chroma.glossary import GlossaryChromaStore
from parlant.adapters.nlp.openai import (
    GPT_4o,
    GPT_4o_Mini,
    OmniModeration,
    OpenAITextEmbedding3Large,
)
from parlant.api.app import create_api_app
from parlant.core.contextual_correlator import ContextualCorrelator
from parlant.core.agents import AgentDocumentStore, AgentStore
from parlant.core.context_variables import ContextVariableDocumentStore, ContextVariableStore
from parlant.core.emission.event_publisher import EventPublisherFactory
from parlant.core.emissions import EventEmitterFactory
from parlant.core.end_users import EndUserDocumentStore, EndUserStore
from parlant.core.evaluations import (
    EvaluationDocumentStore,
    EvaluationStatus,
    EvaluationStore,
)
from parlant.core.guideline_connections import (
    GuidelineConnectionDocumentStore,
    GuidelineConnectionStore,
)
from parlant.core.guidelines import (
    GuidelineDocumentStore,
    GuidelineStore,
)
from parlant.adapters.db.chroma.database import ChromaDatabase
from parlant.adapters.db.json_file import JSONFileDocumentDatabase
from parlant.core.nlp.embedding import EmbedderFactory
from parlant.core.nlp.generation import FallbackSchematicGenerator, SchematicGenerator
from parlant.core.services.tools.service_registry import (
    ServiceRegistry,
    ServiceDocumentRegistry,
)
from parlant.core.sessions import (
    PollingSessionListener,
    SessionDocumentStore,
    SessionListener,
    SessionStore,
)
from parlant.core.glossary import GlossaryStore
from parlant.core.engines.alpha.engine import AlphaEngine
from parlant.core.guideline_tool_associations import (
    GuidelineToolAssociationDocumentStore,
    GuidelineToolAssociationStore,
)
from parlant.core.engines.alpha.tool_caller import ToolCallInferenceSchema
from parlant.core.engines.alpha.guideline_proposer import (
    GuidelineProposer,
    GuidelinePropositionsSchema,
)
from parlant.core.engines.alpha.message_event_producer import (
    MessageEventProducer,
    MessageEventSchema,
)
from parlant.core.engines.alpha.tool_event_producer import ToolEventProducer
from parlant.core.engines.types import Engine
from parlant.core.services.indexing.behavioral_change_evaluation import (
    BehavioralChangeEvaluator,
)
from parlant.core.services.indexing.coherence_checker import (
    CoherenceChecker,
    PredicatesEntailmentTestsSchema,
    ActionsContradictionTestsSchema,
)
from parlant.core.services.indexing.guideline_connection_proposer import (
    GuidelineConnectionProposer,
    GuidelineConnectionPropositionsSchema,
)
from parlant.core.logging import FileLogger, LogLevel, Logger
from parlant.core.application import Application

DEFAULT_PORT = 8000
SERVER_ADDRESS = "https://localhost"

PARLANT_HOME_DIR = Path(os.environ.get("PARLANT_HOME", "/var/lib/parlant"))
PARLANT_HOME_DIR.mkdir(parents=True, exist_ok=True)

EXIT_STACK: AsyncExitStack

DEFAULT_AGENT_NAME = "Default Agent"

sys.path.append(PARLANT_HOME_DIR.as_posix())


CORRELATOR = ContextualCorrelator()
LOGGER = FileLogger(PARLANT_HOME_DIR / "parlant.log", CORRELATOR, LogLevel.INFO)

LOGGER.info(f"Parlant server version {VERSION}")
LOGGER.info(f"Using home directory '{PARLANT_HOME_DIR.absolute()}'")


class StartupError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)


@dataclass
class CLIParams:
    port: int


class ShutdownReason(Enum):
    HOT_RELOAD = auto()
    SHUTDOWN_REQUEST = auto()


async def create_agent_if_absent(agent_store: AgentStore) -> None:
    agents = await agent_store.list_agents()
    if not agents:
        await agent_store.create_agent(name=DEFAULT_AGENT_NAME)


@asynccontextmanager
async def setup_container() -> AsyncIterator[Container]:
    c = Container()

    c[ContextualCorrelator] = CORRELATOR
    c[Logger] = LOGGER

    c[SchematicGenerator[GuidelinePropositionsSchema]] = GPT_4o[GuidelinePropositionsSchema](
        logger=LOGGER
    )
    c[SchematicGenerator[MessageEventSchema]] = GPT_4o[MessageEventSchema](logger=LOGGER)
    c[SchematicGenerator[ToolCallInferenceSchema]] = FallbackSchematicGenerator(
        GPT_4o_Mini[ToolCallInferenceSchema](logger=LOGGER),
        GPT_4o[ToolCallInferenceSchema](logger=LOGGER),
        logger=LOGGER,
    )
    c[SchematicGenerator[PredicatesEntailmentTestsSchema]] = GPT_4o[
        PredicatesEntailmentTestsSchema
    ](logger=LOGGER)
    c[SchematicGenerator[ActionsContradictionTestsSchema]] = GPT_4o[
        ActionsContradictionTestsSchema
    ](logger=LOGGER)
    c[SchematicGenerator[GuidelineConnectionPropositionsSchema]] = GPT_4o[
        GuidelineConnectionPropositionsSchema
    ](logger=LOGGER)

    agents_db = await EXIT_STACK.enter_async_context(
        JSONFileDocumentDatabase(LOGGER, PARLANT_HOME_DIR / "agents.json")
    )
    context_variables_db = await EXIT_STACK.enter_async_context(
        JSONFileDocumentDatabase(LOGGER, PARLANT_HOME_DIR / "context_variables.json")
    )
    end_users_db = await EXIT_STACK.enter_async_context(
        JSONFileDocumentDatabase(LOGGER, PARLANT_HOME_DIR / "end_users.json")
    )
    sessions_db = await EXIT_STACK.enter_async_context(
        JSONFileDocumentDatabase(
            LOGGER,
            PARLANT_HOME_DIR / "sessions.json",
        )
    )
    guidelines_db = await EXIT_STACK.enter_async_context(
        JSONFileDocumentDatabase(LOGGER, PARLANT_HOME_DIR / "guidelines.json")
    )
    guideline_tool_associations_db = await EXIT_STACK.enter_async_context(
        JSONFileDocumentDatabase(LOGGER, PARLANT_HOME_DIR / "guideline_tool_associations.json")
    )
    guideline_connections_db = await EXIT_STACK.enter_async_context(
        JSONFileDocumentDatabase(LOGGER, PARLANT_HOME_DIR / "guideline_connections.json")
    )
    evaluations_db = await EXIT_STACK.enter_async_context(
        JSONFileDocumentDatabase(LOGGER, PARLANT_HOME_DIR / "evaluations.json")
    )
    services_db = await EXIT_STACK.enter_async_context(
        JSONFileDocumentDatabase(LOGGER, PARLANT_HOME_DIR / "services.json")
    )

    c[AgentStore] = AgentDocumentStore(agents_db)
    c[ContextVariableStore] = ContextVariableDocumentStore(context_variables_db)
    c[EndUserStore] = EndUserDocumentStore(end_users_db)
    c[GuidelineStore] = GuidelineDocumentStore(guidelines_db)

    c[GuidelineToolAssociationStore] = GuidelineToolAssociationDocumentStore(
        guideline_tool_associations_db
    )
    c[GuidelineConnectionStore] = GuidelineConnectionDocumentStore(guideline_connections_db)
    c[SessionStore] = SessionDocumentStore(sessions_db)
    c[SessionListener] = PollingSessionListener
    c[GlossaryStore] = GlossaryChromaStore(
        ChromaDatabase(LOGGER, PARLANT_HOME_DIR, EmbedderFactory(c)),
        embedder_type=OpenAITextEmbedding3Large,
    )

    c[EvaluationStore] = EvaluationDocumentStore(evaluations_db)

    c[GuidelineProposer] = GuidelineProposer(
        c[Logger],
        c[SchematicGenerator[GuidelinePropositionsSchema]],
    )
    c[GuidelineConnectionProposer] = GuidelineConnectionProposer(
        c[Logger],
        c[SchematicGenerator[GuidelineConnectionPropositionsSchema]],
        c[GlossaryStore],
    )

    c[CoherenceChecker] = CoherenceChecker(
        c[Logger],
        c[SchematicGenerator[PredicatesEntailmentTestsSchema]],
        c[SchematicGenerator[ActionsContradictionTestsSchema]],
        c[GlossaryStore],
    )

    c[BehavioralChangeEvaluator] = BehavioralChangeEvaluator(
        c[Logger],
        c[AgentStore],
        c[EvaluationStore],
        c[GuidelineStore],
        c[GuidelineConnectionProposer],
        c[CoherenceChecker],
    )

    c[EventEmitterFactory] = Singleton(EventPublisherFactory)

    c[ServiceRegistry] = await EXIT_STACK.enter_async_context(
        ServiceDocumentRegistry(
            database=services_db,
            event_emitter_factory=c[EventEmitterFactory],
            correlator=c[ContextualCorrelator],
            moderation_services={"openai": OmniModeration(logger=c[Logger])},
        )
    )

    c[MessageEventProducer] = MessageEventProducer(
        c[Logger],
        c[ContextualCorrelator],
        c[SchematicGenerator[MessageEventSchema]],
    )

    c[ToolEventProducer] = ToolEventProducer(
        c[Logger],
        c[ContextualCorrelator],
        c[ServiceRegistry],
        c[SchematicGenerator[ToolCallInferenceSchema]],
    )

    c[Engine] = AlphaEngine

    c[Application] = await EXIT_STACK.enter_async_context(Application(c))
    yield c


async def recover_server_tasks(
    evaluation_store: EvaluationStore,
    evaluator: BehavioralChangeEvaluator,
) -> None:
    for evaluation in await evaluation_store.list_evaluations():
        if evaluation.status in [EvaluationStatus.PENDING, EvaluationStatus.RUNNING]:
            await evaluator.run_evaluation(evaluation)


@asynccontextmanager
async def load_app(params: CLIParams) -> AsyncIterator[FastAPI]:
    global EXIT_STACK

    EXIT_STACK = AsyncExitStack()

    async with setup_container() as container, EXIT_STACK:
        await recover_server_tasks(
            evaluation_store=container[EvaluationStore],
            evaluator=container[BehavioralChangeEvaluator],
        )

        await create_agent_if_absent(container[AgentStore])

        yield await create_api_app(container)


async def serve_app(
    app: FastAPI,
    port: int,
) -> ShutdownReason:
    config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="info")
    server = uvicorn.Server(config)
    interrupted = False

    async def monitor_shutdown_request() -> ShutdownReason:
        try:
            while True:
                await asyncio.sleep(1)

                if interrupted:
                    return ShutdownReason.SHUTDOWN_REQUEST
        except asyncio.CancelledError:
            return ShutdownReason.SHUTDOWN_REQUEST

    shutdown_monitor_task = asyncio.create_task(monitor_shutdown_request())

    try:
        await server.serve()
        interrupted = True
    except (KeyboardInterrupt, asyncio.CancelledError):
        return ShutdownReason.SHUTDOWN_REQUEST
    except BaseException as e:
        LOGGER.critical(e.__class__.__name__ + ": " + str(e))
        sys.exit(1)

    return await shutdown_monitor_task


async def start_server(params: CLIParams) -> None:
    while True:
        async with load_app(params) as app:
            shutdown_reason = await serve_app(
                app,
                params.port,
            )

            if shutdown_reason == ShutdownReason.SHUTDOWN_REQUEST:
                return
            elif shutdown_reason == ShutdownReason.HOT_RELOAD:
                LOGGER.info("***** HOT RELOAD *****")


def main() -> None:
    click_completion.init()

    @click.group
    @click.pass_context
    def cli(ctx: click.Context) -> None:
        if not ctx.obj:
            ctx.obj = CLIParams(
                port=DEFAULT_PORT,
            )

    @cli.command(help="Run the Parlant server")
    @click.option(
        "-p",
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help="Server port",
    )
    @click.pass_context
    def run(ctx: click.Context, port: int) -> None:
        ctx.obj.port = port
        asyncio.run(start_server(ctx.obj))

    try:
        cli()
    except StartupError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
