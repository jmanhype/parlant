from __future__ import annotations
from abc import ABC, abstractmethod
from pydantic.dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum, auto
from typing import (
    NamedTuple,
    NewType,
    Optional,
    Sequence,
    TypeAlias,
    Union,
)
from typing_extensions import Literal

from emcie.server.core.agents import AgentId
from emcie.server.core.common import ItemNotFoundError, UniqueId, generate_id
from emcie.server.core.guideline_connections import ConnectionKind
from emcie.server.core.guidelines import GuidelineContent
from emcie.server.core.persistence.common import BaseDocument, ObjectId
from emcie.server.core.persistence.document_database import (
    DocumentDatabase,
)

EvaluationId = NewType("EvaluationId", str)


class EvaluationStatus(Enum):
    PENDING = auto()
    RUNNING = auto()
    COMPLETED = auto()
    FAILED = auto()


class PayloadKind(Enum):
    GUIDELINE = auto()


CoherenceCheckKind = Literal[
    "contradiction_with_existing_guideline", "contradiction_with_another_evaluated_guideline"
]
ConnectionPropositionKind = Literal[
    "connection_with_existing_guideline", "connection_with_another_evaluated_guideline"
]


@dataclass(frozen=True)
class GuidelinePayload:
    content: GuidelineContent

    def __repr__(self) -> str:
        return f"predicate: {self.content.predicate}, action: {self.content.action}"


Payload: TypeAlias = Union[GuidelinePayload]


class PayloadDescriptor(NamedTuple):
    kind: PayloadKind
    payload: Payload


@dataclass(frozen=True)
class CoherenceCheck:
    kind: CoherenceCheckKind
    first: GuidelineContent
    second: GuidelineContent
    issue: str
    severity: int


@dataclass(frozen=True)
class ConnectionProposition:
    check_kind: ConnectionPropositionKind
    source: GuidelineContent
    target: GuidelineContent
    connection_kind: ConnectionKind


@dataclass(frozen=True)
class InvoiceGuidelineData:
    coherence_checks: Sequence[CoherenceCheck]
    connection_propositions: Optional[Sequence[ConnectionProposition]]
    _type: Literal["guideline"] = "guideline"  # Union discrimator for Pydantic


InvoiceData: TypeAlias = Union[InvoiceGuidelineData]


@dataclass(frozen=True)
class Invoice:
    kind: PayloadKind
    payload: Payload
    checksum: str
    state_version: str
    approved: bool
    data: Optional[InvoiceData]
    error: Optional[str]


@dataclass(frozen=True)
class Evaluation:
    id: EvaluationId
    agent_id: AgentId
    creation_utc: datetime
    status: EvaluationStatus
    error: Optional[str]
    invoices: Sequence[Invoice]


class EvaluationStore(ABC):
    @abstractmethod
    async def create_evaluation(
        self,
        agent_id: AgentId,
        payload_descriptors: Sequence[PayloadDescriptor],
        creation_utc: Optional[datetime] = None,
    ) -> Evaluation: ...

    @abstractmethod
    async def update_evaluation_invoice(
        self,
        evaluation_id: EvaluationId,
        invoice_index: int,
        updated_invoice: Invoice,
    ) -> Evaluation: ...

    @abstractmethod
    async def update_evaluation_status(
        self,
        evaluation_id: EvaluationId,
        status: EvaluationStatus,
        error: Optional[str] = None,
    ) -> Evaluation: ...

    @abstractmethod
    async def read_evaluation(
        self,
        evaluation_id: EvaluationId,
    ) -> Evaluation: ...

    @abstractmethod
    async def list_evaluations(
        self,
    ) -> Sequence[Evaluation]: ...


class EvaluationDocumentStore(EvaluationStore):
    class EvaluationDocument(BaseDocument):
        agent_id: AgentId
        status: EvaluationStatus
        creation_utc: datetime
        error: Optional[str]
        invoices: Sequence[Invoice]

    def __init__(self, database: DocumentDatabase):
        self._evaluation_collection = database.get_or_create_collection(
            name="evaluations",
            schema=self.EvaluationDocument,
        )

    async def create_evaluation(
        self,
        agent_id: AgentId,
        payload_descriptors: Sequence[PayloadDescriptor],
        creation_utc: Optional[datetime] = None,
    ) -> Evaluation:
        creation_utc = creation_utc or datetime.now(timezone.utc)

        evaluation_id = EvaluationId(generate_id())

        invoices = [
            Invoice(
                kind=k,
                payload=p,
                state_version="",
                checksum="",
                approved=False,
                data=None,
                error=None,
            )
            for k, p in payload_descriptors
        ]

        await self._evaluation_collection.insert_one(
            self.EvaluationDocument(
                id=ObjectId(evaluation_id),
                agent_id=agent_id,
                creation_utc=creation_utc,
                status=EvaluationStatus.PENDING,
                error=None,
                invoices=invoices,
            )
        )

        return Evaluation(
            id=evaluation_id,
            agent_id=agent_id,
            status=EvaluationStatus.PENDING,
            creation_utc=creation_utc,
            error=None,
            invoices=invoices,
        )

    async def update_evaluation_invoice(
        self,
        evaluation_id: EvaluationId,
        invoice_index: int,
        updated_invoice: Invoice,
    ) -> Evaluation:
        evaluation = await self.read_evaluation(evaluation_id)

        evaluation_invoices = [
            invoice if i != invoice_index else updated_invoice
            for i, invoice in enumerate(evaluation.invoices)
        ]

        await self._evaluation_collection.update_one(
            filters={"id": {"$eq": evaluation.id}},
            updated_document=self.EvaluationDocument(
                id=ObjectId(evaluation.id),
                agent_id=evaluation.agent_id,
                creation_utc=evaluation.creation_utc,
                status=evaluation.status,
                error=evaluation.error,
                invoices=evaluation_invoices,
            ),
        )

        return Evaluation(
            id=evaluation.id,
            agent_id=evaluation.agent_id,
            status=evaluation.status,
            creation_utc=evaluation.creation_utc,
            error=evaluation.error,
            invoices=evaluation_invoices,
        )

    async def update_evaluation_status(
        self,
        evaluation_id: EvaluationId,
        status: EvaluationStatus,
        error: Optional[str] = None,
    ) -> Evaluation:
        evaluation = await self.read_evaluation(evaluation_id)

        await self._evaluation_collection.update_one(
            filters={"id": {"$eq": evaluation.id}},
            updated_document=self.EvaluationDocument(
                id=ObjectId(evaluation.id),
                agent_id=evaluation.agent_id,
                creation_utc=evaluation.creation_utc,
                status=status,
                error=error,
                invoices=evaluation.invoices,
            ),
        )

        return Evaluation(
            id=evaluation.id,
            agent_id=evaluation.agent_id,
            status=status,
            creation_utc=evaluation.creation_utc,
            error=error,
            invoices=evaluation.invoices,
        )

    async def read_evaluation(
        self,
        evaluation_id: EvaluationId,
    ) -> Evaluation:
        evaluation_document = await self._evaluation_collection.find_one(
            filters={"id": {"$eq": evaluation_id}},
        )

        if not evaluation_document:
            raise ItemNotFoundError(item_id=UniqueId(evaluation_id))

        return Evaluation(
            id=EvaluationId(evaluation_document.id),
            agent_id=evaluation_document.agent_id,
            status=evaluation_document.status,
            creation_utc=evaluation_document.creation_utc,
            error=evaluation_document.error,
            invoices=evaluation_document.invoices,
        )

    async def list_evaluations(
        self,
    ) -> Sequence[Evaluation]:
        return [
            Evaluation(
                id=EvaluationId(e.id),
                agent_id=e.agent_id,
                status=e.status,
                creation_utc=e.creation_utc,
                error=e.error,
                invoices=e.invoices,
            )
            for e in await self._evaluation_collection.find(filters={})
        ]
