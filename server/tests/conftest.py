import asyncio
from pathlib import Path
import tempfile
from typing import Any, AsyncIterator
from fastapi.testclient import TestClient
from lagom import Container, Singleton
from pytest import fixture, Config

from emcie.server.api.app import create_app
from emcie.server.contextual_correlator import ContextualCorrelator
from emcie.server.core.context_variables import ContextVariableDocumentStore, ContextVariableStore
from emcie.server.core.end_users import EndUserDocumentStore, EndUserStore
from emcie.server.core.evaluations import EvaluationDocumentStore, EvaluationStore
from emcie.server.core.generation.embedders import Large3Embedder
from emcie.server.core.generation.schematic_generators import (
    BaseSchematicGenerator,
    GPT4o,
    GPT4oMini,
)
from emcie.server.core.guideline_connections import (
    GuidelineConnectionDocumentStore,
    GuidelineConnectionStore,
)
from emcie.server.core.guidelines import GuidelineDocumentStore, GuidelineStore
from emcie.server.core.persistence.chroma_database import ChromaDatabase
from emcie.server.core.persistence.transient_database import TransientDocumentDatabase
from emcie.server.core.sessions import (
    PollingSessionListener,
    SessionDocumentStore,
    SessionListener,
    SessionStore,
)
from emcie.server.core.tools import MultiplexedToolService, LocalToolService, ToolService
from emcie.server.engines.alpha.engine import AlphaEngine
from emcie.server.core.terminology import TerminologyChromaStore, TerminologyStore
from emcie.server.engines.alpha.guideline_proposer import (
    GuidelineProposer,
    GuidelinePropositionsSchema,
)
from emcie.server.engines.alpha.message_event_producer import (
    MessageEventProducer,
    MessageEventSchema,
)
from emcie.server.engines.alpha.tool_caller import ToolCallInferenceSchema
from emcie.server.engines.alpha.tool_event_producer import ToolEventProducer
from emcie.server.engines.common import Engine
from emcie.server.indexing.behavioral_change_evaluation import BehavioralChangeEvaluator
from emcie.server.indexing.coherence_checker import ContradictionTestsSchema
from emcie.server.indexing.guideline_connection_proposer import (
    GuidelineConnectionProposer,
    GuidelineConnectionPropositionsSchema,
)
from emcie.server.logger import Logger, StdoutLogger
from emcie.server.mc import MC
from emcie.server.core.agents import AgentDocumentStore, AgentStore
from emcie.server.core.persistence.document_database import (
    DocumentDatabase,
)
from emcie.server.core.guideline_tool_associations import (
    GuidelineToolAssociationDocumentStore,
    GuidelineToolAssociationStore,
)

from .test_utilities import SyncAwaiter


@fixture
async def sync_await() -> SyncAwaiter:
    return SyncAwaiter(asyncio.get_event_loop())


@fixture
def test_config(pytestconfig: Config) -> dict[str, Any]:
    return {"patience": 10}


@fixture
async def container() -> AsyncIterator[Container]:
    container = Container(log_undefined_deps=True)

    container[Logger] = StdoutLogger(container[ContextualCorrelator])

    container[BaseSchematicGenerator[GuidelinePropositionsSchema]] = Singleton(
        GPT4o(logger=container[Logger], schema=GuidelinePropositionsSchema)
    )
    container[BaseSchematicGenerator[MessageEventSchema]] = Singleton(
        GPT4o(logger=container[Logger], schema=MessageEventSchema)
    )
    container[BaseSchematicGenerator[ToolCallInferenceSchema]] = Singleton(
        GPT4oMini(logger=container[Logger], schema=ToolCallInferenceSchema)
    )
    container[BaseSchematicGenerator[ContradictionTestsSchema]] = Singleton(
        GPT4o(logger=container[Logger], schema=ContradictionTestsSchema)
    )
    container[BaseSchematicGenerator[GuidelineConnectionPropositionsSchema]] = Singleton(
        GPT4o(logger=container[Logger], schema=GuidelineConnectionPropositionsSchema)
    )

    container[ContextualCorrelator] = Singleton(ContextualCorrelator)
    container[DocumentDatabase] = TransientDocumentDatabase
    container[AgentStore] = Singleton(AgentDocumentStore)
    container[GuidelineStore] = Singleton(GuidelineDocumentStore)
    container[GuidelineProposer] = Singleton(GuidelineProposer)
    container[GuidelineConnectionStore] = Singleton(GuidelineConnectionDocumentStore)
    container[GuidelineConnectionProposer] = Singleton(GuidelineConnectionProposer)
    container[LocalToolService] = Singleton(LocalToolService)
    container[MultiplexedToolService] = MultiplexedToolService(
        services={"local": container[LocalToolService]}
    )
    container[ToolService] = lambda c: c[MultiplexedToolService]
    container[ToolEventProducer] = Singleton(ToolEventProducer)
    container[SessionStore] = Singleton(SessionDocumentStore)
    container[ContextVariableStore] = Singleton(ContextVariableDocumentStore)
    container[EndUserStore] = Singleton(EndUserDocumentStore)
    container[GuidelineToolAssociationStore] = Singleton(GuidelineToolAssociationDocumentStore)
    container[SessionListener] = PollingSessionListener
    container[MessageEventProducer] = Singleton(MessageEventProducer)
    container[EvaluationStore] = Singleton(EvaluationDocumentStore)
    container[BehavioralChangeEvaluator] = BehavioralChangeEvaluator

    container[Engine] = AlphaEngine

    with tempfile.TemporaryDirectory() as chroma_db_dir:
        container[TerminologyStore] = TerminologyChromaStore(
            ChromaDatabase(container[Logger], Path(chroma_db_dir)),
            embedder_type=Large3Embedder,
        )
        async with MC(container) as mc:
            container[MC] = mc
            yield container


@fixture
async def client(container: Container) -> AsyncIterator[TestClient]:
    app = await create_app(container)

    with TestClient(app) as client:
        yield client
