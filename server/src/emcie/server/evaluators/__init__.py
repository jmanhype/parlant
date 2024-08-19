from abc import ABC, abstractmethod
import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from typing import (
    Literal,
    Mapping,
    NamedTuple,
    NewType,
    Optional,
    Sequence,
    TypeAlias,
    TypedDict,
    Union,
)

from emcie.common.base_models import DefaultBaseModel
from emcie.server.core.common import JSONSerializable, UniqueId, generate_id
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


class EvaluationInvoiceGuidelineData(TypedDict):
    type: Literal["guideline"]
    detail: JSONSerializable


EvaluationInvoiceData: TypeAlias = Union[EvaluationInvoiceGuidelineData]


@dataclass(frozen=True)
class EvaluationInvoice:
    id: EvaluationInvoiceId
    creation_utc: datetime
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
        payload: dict[EvaluationType, EvaluationPayload],
        creation_utc: Optional[datetime] = None,
    ) -> Evaluation: ...

    @abstractmethod
    async def update_evaluation_status(
        self,
        evaluation_id: EvaluationId,
        status: EvaluationStatus,
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

    @abstractmethod
    async def create_invoice(
        self,
        evaluation_id: EvaluationId,
        state_version: str,
        result: bool,
        score: int,
        checksum: str,
        extra: Mapping[str, JSONSerializable],
        creation_utc: Optional[datetime] = None,
    ) -> EvaluationInvoice: ...

    @abstractmethod
    async def read_invoice(
        self,
        invoice_id: EvaluationInvoiceId,
    ) -> EvaluationInvoice: ...

    @abstractmethod
    async def list_invoices(
        self,
        evaluation_id: EvaluationId,
    ) -> Sequence[EvaluationInvoice]: ...


class EvaluationDocumentStore(EvaluationStore):
    class EvaluationDocument(DefaultBaseModel):
        id: EvaluationId
        status: EvaluationStatus
        creation_utc: datetime
        invoices: list[EvaluationInvoiceId]
        payload: dict[EvaluationType, EvaluationPayload]

    class InvoiceDocument(DefaultBaseModel):
        id: EvaluationInvoiceId
        evaluation_id: EvaluationId
        creation_utc: datetime
        state_version: str
        checksum: str
        result: bool
        score: int
        extra: dict[str, JSONSerializable]

    def __init__(self, database: DocumentDatabase):
        self._evaluation_collection = database.get_or_create_collection(
            name="evaluations",
            schema=self.EvaluationDocument,
        )
        self._invoice_collection = database.get_or_create_collection(
            name="invoices",
            schema=self.InvoiceDocument,
        )

    async def create_evaluation(
        self,
        payload: dict[EvaluationType, EvaluationPayload],
        creation_utc: Optional[datetime] = None,
    ) -> Evaluation:
        creation_utc = creation_utc or datetime.now(timezone.utc)
        status: EvaluationStatus = "pending"
        initial_invoices: list[EvaluationInvoiceId] = []

        document = {
            "id": EvaluationId(generate_id()),
            "creation_utc": creation_utc,
            "status": status,
            "invoices": initial_invoices,
            "payload": payload,
        }

        evaluation_id = await self._evaluation_collection.insert_one(document)

        return Evaluation(
            id=EvaluationId(evaluation_id),
            status=status,
            creation_utc=creation_utc,
            invoices=initial_invoices,
            payload=payload,
        )

    async def update_evaluation_status(
        self,
        evaluation_id: EvaluationId,
        status: EvaluationStatus,
    ) -> Evaluation:
        latest_evaluation = await self.read_evaluation(evaluation_id=evaluation_id)

        document = {
            "id": latest_evaluation.id,
            "creation_utc": latest_evaluation.creation_utc,
            "status": status,
            "invoices": latest_evaluation.invoices,
            "payload": latest_evaluation.payload,
        }

        evaluation_id = EvaluationId(
            await self._evaluation_collection.update_one(
                filters={"id": {"$eq": latest_evaluation.id}}, updated_document=document
            )
        )

        return Evaluation(
            id=EvaluationId(evaluation_id),
            status=status,
            creation_utc=latest_evaluation.creation_utc,
            invoices=latest_evaluation.invoices,
            payload=latest_evaluation.payload,
        )

    async def read_evaluation(
        self,
        evaluation_id: EvaluationId,
    ) -> Evaluation:
        evaluation_document = max(
            await self._evaluation_collection.find(
                filters={"id": {"$eq": evaluation_id}},
            ),
            key=lambda d: d["creation_utc"],
        )

        return Evaluation(
            id=evaluation_document["id"],
            status=evaluation_document["status"],
            creation_utc=evaluation_document["creation_utc"],
            invoices=evaluation_document["invoices"],
            payload=evaluation_document["payload"],
        )

    async def list_active_evaluations(
        self,
    ) -> Sequence[Evaluation]:
        return [
            Evaluation(
                id=e["id"],
                status=e["status"],
                creation_utc=e["creation_utc"],
                invoices=e["invoices"],
                payload=e["payload"],
            )
            for e in await self._evaluation_collection.find(
                filters={"$or": [{"status": {"$eq": "pending"}}, {"status": {"$eq": "running"}}]}
            )
        ]

    async def create_invoice(
        self,
        evaluation_id: EvaluationId,
        state_version: str,
        result: bool,
        score: int,
        checksum: str,
        extra: Mapping[str, JSONSerializable],
        creation_utc: Optional[datetime] = None,
    ) -> EvaluationInvoice:
        creation_utc = creation_utc or datetime.now(timezone.utc)
        invoice_id = EvaluationInvoiceId(generate_id())

        document = {
            "id": invoice_id,
            "evaluation_id": evaluation_id,
            "creation_utc": creation_utc,
            "state_version": state_version,
            "checksum": checksum,
            "result": result,
            "score": score,
            "extra": extra,
        }

        await self._invoice_collection.insert_one(document)

        evaluation = await self.read_evaluation(evaluation_id)

        new_invoices = list(evaluation.invoices) + [invoice_id]

        evaluation_updated_document = {
            "id": evaluation.id,
            "creation_utc": evaluation.creation_utc,
            "status": evaluation.status,
            "invoices": new_invoices,
            "payload": evaluation.payload,
        }

        await self._evaluation_collection.update_one(
            filters={"id": {"$eq": evaluation.id}},
            updated_document=evaluation_updated_document,
        )

        return EvaluationInvoice(
            creation_utc=creation_utc,
            state_version=state_version,
            checksum=checksum,
            result=result,
            score=score,
            extra=extra,
        )

    async def read_invoice(
        self,
        invoice_id: EvaluationInvoiceId,
    ) -> EvaluationInvoice:
        invoice_document = await self._invoice_collection.find_one(
            filters={"id": {"$eq": invoice_id}}
        )

        return EvaluationInvoice(
            creation_utc=invoice_document["creation_utc"],
            state_version=invoice_document["state_version"],
            checksum=invoice_document["checksum"],
            result=invoice_document["result"],
            score=invoice_document["score"],
            extra=invoice_document["extra"],
        )

    async def list_invoices(
        self,
        evaluation_id: EvaluationId,
    ) -> Sequence[EvaluationInvoice]:
        return [
            EvaluationInvoice(
                creation_utc=d["creation_utc"],
                state_version=d["state_version"],
                checksum=d["checksum"],
                result=d["result"],
                score=d["score"],
                extra=d["extra"],
            )
            for d in await self._invoice_collection.find(
                filters={"evaluation_id": {"$eq": evaluation_id}}
            )
        ]


class EvaluationService:
    def __init__(self, evaluation_store: EvaluationStore):
        self._evaluation_store = evaluation_store
        self._guideline_evaluator = GuidelineEvaluator()

    async def create_evaluation_task(
        self,
        payload: dict[EvaluationType, EvaluationPayload],
    ) -> EvaluationId:
        evaluation = await self._evaluation_store.create_evaluation(payload=payload)

        asyncio.create_task(self._run_evaluation(evaluation.id))

        return evaluation.id

    async def _run_evaluation(self, evaluation_id: EvaluationId) -> None:
        evaluation = await self._evaluation_store.read_evaluation(evaluation_id)

        try:
            await self._evaluation_store.update_evaluation_status(evaluation_id, "running")
            all_results = []

            for eval_type, payloads in evaluation.payload.items():
                if eval_type == "guidelines":
                    for unique_id, payload in payloads.items():
                        result = await self._guideline_evaluator.evaluate(payload)

                        await self._evaluation_store.create_invoice(
                            evaluation_id,
                            state_version="1.0",
                            checksum=self._generate_checksum(payload),
                            result=result.result,
                            score=result.score,
                            extra=result.extra,
                        )

                        all_results.append(result)

            while len(all_results) < len(evaluation.payload):
                await asyncio.sleep(1)

            await self._evaluation_store.update_evaluation_status(evaluation_id, "completed")

        except Exception as e:
            await self._evaluation_store.create_invoice(
                evaluation_id,
                state_version="1.0",
                checksum="",
                result=False,
                score=0,
                extra={
                    "error": {
                        "type": str(type(e).__name__),
                        "message": str(e),
                    }
                },
            )
            await self._evaluation_store.update_evaluation_status(evaluation_id, "failed")

    def _generate_checksum(self, payload: EvaluationGuidelinePayload) -> str:
        md5_hash = hashlib.md5()
        md5_hash.update(f"{json.dumps(payload)}".encode("utf-8"))

        return md5_hash.hexdigest()
