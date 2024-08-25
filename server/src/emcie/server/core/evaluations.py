from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal, NewType, Optional, Sequence, TypeAlias, TypedDict, Union

from emcie.server.base_models import DefaultBaseModel
from emcie.server.core.common import ItemNotFoundError, UniqueId, generate_id
from emcie.server.core.persistence.common import NoMatchingDocumentsError
from emcie.server.core.persistence.document_database import DocumentDatabase

EvaluationId = NewType("EvaluationId", str)
EvaluationInvoiceId = NewType("EvaluationInvoiceId", str)
EvaluationStatus = Literal["pending", "running", "completed", "failed"]


class EvaluationGuidelinePayload(TypedDict):
    type: Literal["guideline"]
    guideline_set: str
    predicate: str
    content: str


EvaluationPayload: TypeAlias = Union[EvaluationGuidelinePayload]


class CoherenceCheckResult(TypedDict):
    proposed: str
    existing: str
    issue: str
    severity: int


class GuidelineCoherenceCheckResult(TypedDict):
    type: Literal["coherence_check"]
    data: list[CoherenceCheckResult]


class EvaluationInvoiceGuidelineData(TypedDict):
    type: Literal["guideline"]
    detail: Union[GuidelineCoherenceCheckResult]


EvaluationInvoiceData: TypeAlias = Union[EvaluationInvoiceGuidelineData]


class EvaluationInvoice(TypedDict):
    id: EvaluationInvoiceId
    state_version: str
    checksum: str
    approved: bool
    data: EvaluationInvoiceData


class EvaluationItem(TypedDict):
    id: UniqueId
    payload: EvaluationPayload
    invoice: Optional[EvaluationInvoice]
    error: Optional[str]


@dataclass(frozen=True)
class Evaluation:
    id: EvaluationId
    status: EvaluationStatus
    error: Optional[str]
    creation_utc: datetime
    items: Sequence[EvaluationItem]


class EvaluationStore(ABC):
    @abstractmethod
    async def create_evaluation(
        self,
        payload: Sequence[EvaluationPayload],
        creation_utc: Optional[datetime] = None,
    ) -> Evaluation: ...

    @abstractmethod
    async def update_evaluation(
        self,
        evaluation_id: EvaluationId,
        status: Optional[EvaluationStatus] = None,
        item: Optional[EvaluationItem] = None,
        error: Optional[str] = None,
    ) -> Evaluation: ...

    @abstractmethod
    async def read_evaluation(
        self,
        evaluation_id: EvaluationId,
    ) -> Evaluation: ...

    @abstractmethod
    async def list_active_evaluations(
        self,
    ) -> Sequence[Evaluation]: ...


class EvaluationDocumentStore(EvaluationStore):
    class EvaluationDocument(DefaultBaseModel):
        id: EvaluationId
        status: EvaluationStatus
        creation_utc: datetime
        error: Optional[str]
        items: list[EvaluationItem]

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

        items: list[EvaluationItem] = [
            {
                "id": UniqueId(generate_id()),
                "payload": p,
                "invoice": None,
                "error": None,
            }
            for p in payloads
        ]

        await self._evaluation_collection.insert_one(
            document={
                "id": evaluation_id,
                "creation_utc": creation_utc,
                "status": "pending",
                "error": None,
                "items": items,
            }
        )

        return Evaluation(
            id=evaluation_id,
            status="pending",
            creation_utc=creation_utc,
            error=None,
            items=items,
        )

    async def update_evaluation(
        self,
        evaluation_id: EvaluationId,
        status: Optional[EvaluationStatus] = None,
        item: Optional[EvaluationItem] = None,
        error: Optional[str] = None,
    ) -> Evaluation:
        try:
            evaluation = await self.read_evaluation(evaluation_id)
        except NoMatchingDocumentsError:
            raise ItemNotFoundError(item_id=UniqueId(evaluation_id))

        status = status if status else evaluation.status

        items = []

        if item:
            for i in evaluation.items:
                if i["id"] == item["id"]:
                    items.append(item)
                else:
                    items.append(i)

        evaluation_items: Sequence[EvaluationItem] = items if item else evaluation.items

        await self._evaluation_collection.update_one(
            filters={"id": {"$eq": evaluation.id}},
            updated_document={
                "id": evaluation.id,
                "creation_utc": evaluation.creation_utc,
                "status": status,
                "error": error,
                "items": evaluation_items,
            },
        )

        return Evaluation(
            id=evaluation.id,
            status=status,
            creation_utc=evaluation.creation_utc,
            error=error,
            items=evaluation_items,
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
            error=evaluation_document.get("error"),
            items=evaluation_document["items"],
        )

    async def list_active_evaluations(
        self,
    ) -> Sequence[Evaluation]:
        return [
            Evaluation(
                id=e["id"],
                status=e["status"],
                creation_utc=e["creation_utc"],
                error=e.get("error"),
                items=e["items"],
            )
            for e in await self._evaluation_collection.find(
                filters={
                    "$or": [
                        {"status": {"$eq": "pending"}},
                        {"status": {"$eq": "running"}},
                    ]
                }
            )
        ]
