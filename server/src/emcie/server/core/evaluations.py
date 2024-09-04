from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum, auto
from typing import (
    Any,
    NamedTuple,
    NewType,
    Optional,
    Sequence,
    TypeAlias,
    Union,
)
from typing_extensions import Literal

from emcie.server.base_models import DefaultBaseModel
from emcie.server.core.common import ItemNotFoundError, UniqueId, generate_id
from emcie.server.core.guideline_connections import ConnectionKind
from emcie.server.core.guidelines import GuidelineContent
from emcie.server.core.persistence.common import NoMatchingDocumentsError
from emcie.server.core.persistence.document_database import DocumentDatabase

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
    guideline_set: str
    predicate: str
    action: str

    def __repr__(self) -> str:
        return f"guideline_set: {self.guideline_set}, predicate: {self.predicate}, action: {self.action}"


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
    creation_utc: datetime
    status: EvaluationStatus
    error: Optional[str]
    invoices: Sequence[Invoice]


class EvaluationStore(ABC):
    @abstractmethod
    async def create_evaluation(
        self,
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
    class EvaluationDocument(DefaultBaseModel):
        id: EvaluationId
        status: EvaluationStatus
        creation_utc: datetime
        error: Optional[str]
        invoices: list[Invoice]

    def __init__(self, database: DocumentDatabase):
        self._evaluation_collection = database.get_or_create_collection(
            name="evaluations",
            schema=self.EvaluationDocument,
        )

    @staticmethod
    def _invoice_data_from_dict(
        kind: PayloadKind,
        d: dict[str, Any],
    ) -> InvoiceData:
        if kind == PayloadKind.GUIDELINE:
            return InvoiceGuidelineData(
                coherence_checks=[
                    CoherenceCheck(
                        kind=c["kind"],
                        first=GuidelineContent(**c["first"]),
                        second=GuidelineContent(**c["second"]),
                        issue=c["issue"],
                        severity=c["severity"],
                    )
                    for c in d["coherence_checks"]
                ],
                connection_propositions=[
                    ConnectionProposition(
                        check_kind=c["check_kind"],
                        source=GuidelineContent(**c["source"]),
                        target=GuidelineContent(**c["target"]),
                        connection_kind=c["connection_kind"],
                    )
                    for c in d["connection_propositions"]
                ]
                if d["connection_propositions"]
                else None,
            )

    async def create_evaluation(
        self,
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
            document={
                "id": evaluation_id,
                "creation_utc": creation_utc,
                "status": EvaluationStatus.PENDING,
                "error": None,
                "invoices": [asdict(i) for i in invoices],
            }
        )

        return Evaluation(
            id=evaluation_id,
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
                **asdict(evaluation),
                "invoices": [asdict(i) for i in evaluation_invoices],
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
            updated_document={**asdict(evaluation), "status": status, "error": error},
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
            status=EvaluationStatus(evaluation_document["status"]),
            creation_utc=evaluation_document["creation_utc"],
            error=evaluation_document["error"],
            invoices=[
                Invoice(
                    kind=PayloadKind(invoice["kind"]),
                    payload=Payload(**invoice["payload"]),
                    checksum=invoice["checksum"],
                    state_version=invoice["state_version"],
                    approved=invoice["approved"],
                    data=self._invoice_data_from_dict(PayloadKind(invoice["kind"]), invoice["data"])
                    if invoice["data"]
                    else None,
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
                status=EvaluationStatus(e["status"]),
                creation_utc=e["creation_utc"],
                error=e["error"],
                invoices=[
                    Invoice(
                        kind=PayloadKind(invoice["kind"]),
                        payload=Payload(**invoice["payload"]),
                        checksum=invoice["checksum"],
                        state_version=invoice["state_version"],
                        approved=invoice["approved"],
                        data=self._invoice_data_from_dict(
                            PayloadKind(invoice["kind"]), invoice["data"]
                        )
                        if invoice["data"]
                        else None,
                        error=invoice["error"],
                    )
                    for invoice in e["invoices"]
                ],
            )
            for e in await self._evaluation_collection.find(filters={})
        ]
