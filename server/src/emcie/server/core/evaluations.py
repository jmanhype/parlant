from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal, NewType, Optional, Sequence, TypeAlias, Union

from emcie.server.base_models import DefaultBaseModel
from emcie.server.core.common import ItemNotFoundError, UniqueId, generate_id
from emcie.server.core.guideline_connections import ConnectionKind
from emcie.server.core.persistence.common import NoMatchingDocumentsError
from emcie.server.core.persistence.document_database import DocumentDatabase
from emcie.server.indexing.common import GuidelineData

EvaluationId = NewType("EvaluationId", str)
EvaluationStatus = Literal["pending", "running", "completed", "failed"]


@dataclass(frozen=True)
class EvaluationGuidelinePayload:
    type: Literal["guideline"]
    guideline_set: str
    predicate: str
    content: str

    def __repr__(self) -> str:
        return f"type: {self.type}, guideline_set: {self.guideline_set}, predicate: {self.predicate}, content: {self.content}"


EvaluationPayload: TypeAlias = Union[EvaluationGuidelinePayload]


@dataclass(frozen=True)
class CoherenceCheckResult:
    type: Literal[
        "Contradiction With Existing Guideline", "Contradiction With Other Proposed Guideline"
    ]
    first: GuidelineData
    second: GuidelineData
    issue: str
    severity: int


@dataclass(frozen=True)
class ConnectionPropositionResult:
    type: Literal["Connection With Existing Guideline", "Connection With Other Proposed Guideline"]
    source: GuidelineData
    target: GuidelineData
    kind: ConnectionKind


@dataclass(frozen=True)
class EvaluationGuidelineCoherenceCheckResult:
    coherence_checks: list[CoherenceCheckResult]


@dataclass(frozen=True)
class EvaluationGuidelineConnectionPropositionsResult:
    connection_propositions: list[ConnectionPropositionResult]


@dataclass(frozen=True)
class EvaluationInvoiceGuidelineData:
    type: Literal["guideline"]
    coherence_check_detail: EvaluationGuidelineCoherenceCheckResult
    connections_detail: EvaluationGuidelineConnectionPropositionsResult


EvaluationInvoiceData: TypeAlias = Union[EvaluationInvoiceGuidelineData]


@dataclass(frozen=True)
class EvaluationInvoice:
    payload: EvaluationPayload
    checksum: str
    state_version: str
    approved: bool
    data: Optional[EvaluationInvoiceData]
    error: Optional[str]


@dataclass(frozen=True)
class Evaluation:
    id: EvaluationId
    creation_utc: datetime
    status: EvaluationStatus
    error: Optional[str]
    invoices: Sequence[EvaluationInvoice]


class EvaluationStore(ABC):
    @abstractmethod
    async def create_evaluation(
        self,
        payload: Sequence[EvaluationPayload],
        creation_utc: Optional[datetime] = None,
    ) -> Evaluation: ...

    @abstractmethod
    async def update_evaluation_invoice(
        self,
        evaluation_id: EvaluationId,
        invoice_index: int,
        updated_invoice: EvaluationInvoice,
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
    class EvaluationDocument(DefaultBaseModel):
        id: EvaluationId
        status: EvaluationStatus
        creation_utc: datetime
        error: Optional[str]
        invoices: list[EvaluationInvoice]

    def __init__(self, database: DocumentDatabase):
        self._evaluation_collection = database.get_or_create_collection(
            name="evaluations",
            schema=self.EvaluationDocument,
        )

    async def create_evaluation(
        self,
        payloads: Sequence[EvaluationPayload],
        creation_utc: Optional[datetime] = None,
    ) -> Evaluation:
        creation_utc = creation_utc or datetime.now(timezone.utc)

        evaluation_id = EvaluationId(generate_id())

        invoices = [
            EvaluationInvoice(
                payload=p,
                state_version="",
                checksum="",
                approved=False,
                data=None,
                error=None,
            )
            for p in payloads
        ]

        await self._evaluation_collection.insert_one(
            document={
                "id": evaluation_id,
                "creation_utc": creation_utc,
                "status": "pending",
                "error": None,
                "invoices": invoices,
            }
        )

        return Evaluation(
            id=evaluation_id,
            status="pending",
            creation_utc=creation_utc,
            error=None,
            invoices=invoices,
        )

    async def update_evaluation_invoice(
        self,
        evaluation_id: EvaluationId,
        invoice_index: int,
        updated_invoice: EvaluationInvoice,
    ) -> Evaluation:
        try:
            evaluation = await self.read_evaluation(evaluation_id)
        except NoMatchingDocumentsError:
            raise ItemNotFoundError(item_id=UniqueId(evaluation_id))

        evaluation_invoices = [
            invoice if i != invoice_index else updated_invoice
            for i, invoice in enumerate(evaluation.invoices)
        ]

        await self._evaluation_collection.update_one(
            filters={"id": {"$eq": evaluation.id}},
            updated_document={
                "id": evaluation.id,
                "creation_utc": evaluation.creation_utc,
                "status": evaluation.status,
                "error": evaluation.error,
                "invoices": [
                    {
                        "payload": {
                            "type": invoice.payload.type,
                            "guideline_set": invoice.payload.guideline_set,
                            "predicate": invoice.payload.predicate,
                            "content": invoice.payload.content,
                        },
                        "state_version": invoice.state_version,
                        "checksum": invoice.checksum,
                        "approved": invoice.approved,
                        "data": invoice.data,
                        "error": invoice.error,
                    }
                    for invoice in evaluation_invoices
                ],
            },
        )

        return Evaluation(
            id=evaluation.id,
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
        try:
            evaluation = await self.read_evaluation(evaluation_id)
        except NoMatchingDocumentsError:
            raise ItemNotFoundError(item_id=UniqueId(evaluation_id))

        await self._evaluation_collection.update_one(
            filters={"id": {"$eq": evaluation.id}},
            updated_document={
                "id": evaluation.id,
                "creation_utc": evaluation.creation_utc,
                "status": status,
                "error": error,
                "invoices": [
                    {
                        "payload": {
                            "type": invoice.payload.type,
                            "guideline_set": invoice.payload.guideline_set,
                            "predicate": invoice.payload.predicate,
                            "content": invoice.payload.content,
                        },
                        "state_version": invoice.state_version,
                        "checksum": invoice.checksum,
                        "approved": invoice.approved,
                        "data": invoice.data,
                        "error": invoice.error,
                    }
                    for invoice in evaluation.invoices
                ],
            },
        )

        return Evaluation(
            id=evaluation.id,
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

        return Evaluation(
            id=evaluation_document["id"],
            status=evaluation_document["status"],
            creation_utc=evaluation_document["creation_utc"],
            error=evaluation_document["error"],
            invoices=[
                EvaluationInvoice(
                    payload=EvaluationPayload(**invoice["payload"]),
                    checksum=invoice["checksum"],
                    state_version=invoice["state_version"],
                    approved=invoice["approved"],
                    data=invoice["data"],
                    error=invoice["error"],
                )
                for invoice in evaluation_document["invoices"]
            ],
        )

    async def list_evaluations(
        self,
    ) -> Sequence[Evaluation]:
        return [
            Evaluation(
                id=e["id"],
                status=e["status"],
                creation_utc=e["creation_utc"],
                error=e["error"],
                invoices=[
                    EvaluationInvoice(
                        payload=EvaluationPayload(**invoice["payload"]),
                        checksum=invoice["checksum"],
                        state_version=invoice["state_version"],
                        approved=invoice["approved"],
                        data=invoice["data"],
                        error=invoice["error"],
                    )
                    for invoice in e["invoices"]
                ],
            )
            for e in await self._evaluation_collection.find(filters={})
        ]
