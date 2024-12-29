# Copyright 2024 Emcie Co Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum, auto
from typing import (
    Mapping,
    NamedTuple,
    NewType,
    Optional,
    Sequence,
    TypeAlias,
    Union,
    cast,
)
from typing_extensions import Literal, override, TypedDict, Self

from parlant.core.agents import AgentId
from parlant.core.async_utils import ReaderWriterLock, Timeout
from parlant.core.common import (
    ItemNotFoundError,
    JSONSerializable,
    UniqueId,
    Version,
    generate_id,
)
from parlant.core.guidelines import GuidelineContent, GuidelineId
from parlant.core.style_guides import (
    StyleGuideContent,
    StyleGuideEvent,
    StyleGuideEventDocument,
    StyleGuideExample,
    StyleGuideExampleDocument,
    StyleGuideId,
)
from parlant.core.persistence.common import ObjectId
from parlant.core.persistence.document_database import DocumentDatabase, DocumentCollection

EvaluationId = NewType("EvaluationId", str)


class EvaluationStatus(Enum):
    PENDING = auto()
    RUNNING = auto()
    COMPLETED = auto()
    FAILED = auto()


class PayloadKind(Enum):
    GUIDELINE = auto()
    STYLE_GUIDE = auto()


GuidelineCoherenceCheckKind = Literal[
    "contradiction_with_existing_guideline", "contradiction_with_another_evaluated_guideline"
]
GuidelineConnectionPropositionKind = Literal[
    "connection_with_existing_guideline", "connection_with_another_evaluated_guideline"
]

StyleGuideCoherenceCheckKind = Literal[
    "contradiction_with_existing_style_guide", "contradiction_with_another_evaluated_style_guide"
]


@dataclass(frozen=True)
class GuidelinePayload:
    content: GuidelineContent
    operation: Literal["add", "update"]
    coherence_check: bool
    connection_proposition: bool
    updated_id: Optional[GuidelineId] = None

    def __repr__(self) -> str:
        return f"condition: {self.content.condition}, action: {self.content.action}"


@dataclass(frozen=True)
class StyleGuidePayload:
    content: StyleGuideContent
    operation: Literal["add", "update"]
    coherence_check: bool
    updated_id: Optional[StyleGuideId] = None


Payload: TypeAlias = Union[GuidelinePayload, StyleGuidePayload]


class PayloadDescriptor(NamedTuple):
    kind: PayloadKind
    payload: Payload


@dataclass(frozen=True)
class GuidelineCoherenceCheck:
    kind: GuidelineCoherenceCheckKind
    first: GuidelineContent
    second: GuidelineContent
    issue: str
    severity: int


@dataclass(frozen=True)
class GuidelineConnectionProposition:
    check_kind: GuidelineConnectionPropositionKind
    source: GuidelineContent
    target: GuidelineContent


@dataclass(frozen=True)
class InvoiceGuidelineData:
    coherence_checks: Sequence[GuidelineCoherenceCheck]
    connection_propositions: Optional[Sequence[GuidelineConnectionProposition]]
    _type: Literal["guideline"] = "guideline"  # Union discrimator for Pydantic


@dataclass(frozen=True)
class StyleGuideCoherenceCheck:
    kind: StyleGuideCoherenceCheckKind
    first: StyleGuideContent
    second: StyleGuideContent
    issue: str
    severity: int


@dataclass(frozen=True)
class InvoiceStyleGuideData:
    coherence_checks: Sequence[StyleGuideCoherenceCheck]
    _type: Literal["style_guide"] = "style_guide"  # Union discrimator for Pydantic


InvoiceData: TypeAlias = Union[InvoiceGuidelineData, InvoiceStyleGuideData]


# @dataclass(frozen=True)
# class GuidelineInvoice:
#     payload: GuidelinePayload
#     checksum: str
#     state_version: str
#     approved: bool
#     data: Optional[InvoiceGuidelineData]
#     error: Optional[str]
#     kind: Literal[PayloadKind.GUIDELINE] = PayloadKind.GUIDELINE


# @dataclass(frozen=True)
# class StyleGuideInvoice:
#     payload: StyleGuidePayload
#     checksum: str
#     state_version: str
#     approved: bool
#     data: Optional[InvoiceStyleGuideData]
#     error: Optional[str]
#     kind: Literal[PayloadKind.STYLE_GUIDE] = PayloadKind.STYLE_GUIDE


# Invoice: TypeAlias = Union[GuidelineInvoice, StyleGuideInvoice]


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
    progress: float


class EvaluationUpdateParams(TypedDict, total=False):
    status: EvaluationStatus
    error: Optional[str]
    invoices: Sequence[Invoice]
    progress: float


class EvaluationStore(ABC):
    @abstractmethod
    async def create_evaluation(
        self,
        agent_id: AgentId,
        payload_descriptors: Sequence[PayloadDescriptor],
        creation_utc: Optional[datetime] = None,
        extra: Optional[Mapping[str, JSONSerializable]] = None,
    ) -> Evaluation: ...

    @abstractmethod
    async def update_evaluation(
        self,
        evaluation_id: EvaluationId,
        params: EvaluationUpdateParams,
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


class _GuidelineContentDocument(TypedDict):
    condition: str
    action: str


class _GuidelinePayloadDocument(TypedDict):
    content: _GuidelineContentDocument
    action: Literal["add", "update"]
    updated_id: Optional[GuidelineId]
    coherence_check: bool
    connection_proposition: bool


class _StyleGuideContentDocument(TypedDict):
    principle: str
    examples: Sequence[StyleGuideExampleDocument]


class _StyleGuidePayloadDocument(TypedDict):
    content: _StyleGuideContentDocument
    action: Literal["add", "update"]
    updated_id: Optional[StyleGuideId]
    coherence_check: bool


_PayloadDocument = Union[_GuidelinePayloadDocument, _StyleGuidePayloadDocument]


class _GuidelineCoherenceCheckDocument(TypedDict):
    kind: GuidelineCoherenceCheckKind
    first: _GuidelineContentDocument
    second: _GuidelineContentDocument
    issue: str
    severity: int


class _GuidelineConnectionPropositionDocument(TypedDict):
    check_kind: GuidelineConnectionPropositionKind
    source: _GuidelineContentDocument
    target: _GuidelineContentDocument


class _InvoiceGuidelineDataDocument(TypedDict):
    coherence_checks: Sequence[_GuidelineCoherenceCheckDocument]
    connection_propositions: Optional[Sequence[_GuidelineConnectionPropositionDocument]]


class _StyleGuideCoherenceCheckDocument(TypedDict):
    kind: StyleGuideCoherenceCheckKind
    first: _StyleGuideContentDocument
    second: _StyleGuideContentDocument
    issue: str
    severity: int


class _InvoiceStyleGuideDataDocument(TypedDict):
    coherence_checks: Sequence[_StyleGuideCoherenceCheckDocument]


_InvoiceDataDocument = Union[_InvoiceGuidelineDataDocument, _InvoiceStyleGuideDataDocument]


class _InvoiceDocument(TypedDict, total=False):
    kind: str
    payload: _PayloadDocument
    checksum: str
    state_version: str
    approved: bool
    data: Optional[_InvoiceDataDocument]
    error: Optional[str]


class _EvaluationDocument(TypedDict, total=False):
    id: ObjectId
    version: Version.String
    agent_id: AgentId
    creation_utc: str
    status: str
    error: Optional[str]
    invoices: Sequence[_InvoiceDocument]
    progress: float


class EvaluationDocumentStore(EvaluationStore):
    VERSION = Version.from_string("0.1.0")

    def __init__(self, database: DocumentDatabase):
        self._database = database
        self._collection: DocumentCollection[_EvaluationDocument]

        self._lock = ReaderWriterLock()

    async def __aenter__(self) -> Self:
        self._collection = await self._database.get_or_create_collection(
            name="evaluations",
            schema=_EvaluationDocument,
        )
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[object],
    ) -> None:
        pass

    def _serialize_invoice(self, invoice: Invoice) -> _InvoiceDocument:
        def serialize_guideline_coherence_check(
            check: GuidelineCoherenceCheck,
        ) -> _GuidelineCoherenceCheckDocument:
            return _GuidelineCoherenceCheckDocument(
                kind=check.kind,
                first=_GuidelineContentDocument(
                    condition=check.first.condition,
                    action=check.first.action,
                ),
                second=_GuidelineContentDocument(
                    condition=check.second.condition,
                    action=check.second.action,
                ),
                issue=check.issue,
                severity=check.severity,
            )

        def serialize_guideline_connection_proposition(
            cp: GuidelineConnectionProposition,
        ) -> _GuidelineConnectionPropositionDocument:
            return _GuidelineConnectionPropositionDocument(
                check_kind=cp.check_kind,
                source=_GuidelineContentDocument(
                    condition=cp.source.condition,
                    action=cp.source.action,
                ),
                target=_GuidelineContentDocument(
                    condition=cp.target.condition,
                    action=cp.target.action,
                ),
            )

        def serialize_invoice_guideline_data(
            data: InvoiceGuidelineData,
        ) -> _InvoiceGuidelineDataDocument:
            return _InvoiceGuidelineDataDocument(
                coherence_checks=[
                    serialize_guideline_coherence_check(cc) for cc in data.coherence_checks
                ],
                connection_propositions=(
                    [
                        serialize_guideline_connection_proposition(cp)
                        for cp in data.connection_propositions
                    ]
                    if data.connection_propositions
                    else None
                ),
            )

        def serialize_style_guide_content(content: StyleGuideContent) -> _StyleGuideContentDocument:
            def serialize_event(event: StyleGuideEvent) -> StyleGuideEventDocument:
                return StyleGuideEventDocument(
                    source=event.source,
                    message=event.message,
                )

            def serialize_example(example: StyleGuideExample) -> StyleGuideExampleDocument:
                return StyleGuideExampleDocument(
                    before=[serialize_event(event) for event in example.before],
                    after=[serialize_event(event) for event in example.after],
                    violation=example.violation,
                )

            return _StyleGuideContentDocument(
                principle=content.principle,
                examples=[serialize_example(example) for example in content.examples],
            )

        def serialize_style_guide_coherence_check(
            check: StyleGuideCoherenceCheck,
        ) -> _StyleGuideCoherenceCheckDocument:
            return _StyleGuideCoherenceCheckDocument(
                kind=check.kind,
                first=serialize_style_guide_content(check.first),
                second=serialize_style_guide_content(check.second),
                issue=check.issue,
                severity=check.severity,
            )

        def serialize_invoice_style_guide_data(
            data: InvoiceStyleGuideData,
        ) -> _InvoiceStyleGuideDataDocument:
            return _InvoiceStyleGuideDataDocument(
                coherence_checks=[
                    serialize_style_guide_coherence_check(cc) for cc in data.coherence_checks
                ],
            )

        def serialize_payload(payload: Payload) -> _PayloadDocument:
            if isinstance(payload, GuidelinePayload):
                return _GuidelinePayloadDocument(
                    content=_GuidelineContentDocument(
                        condition=payload.content.condition,
                        action=payload.content.action,
                    ),
                    action=payload.operation,
                    updated_id=payload.updated_id,
                    coherence_check=payload.coherence_check,
                    connection_proposition=payload.connection_proposition,
                )
            elif isinstance(payload, StyleGuidePayload):
                return _StyleGuidePayloadDocument(
                    content=serialize_style_guide_content(payload.content),
                    action=payload.operation,
                    updated_id=payload.updated_id,
                    coherence_check=payload.coherence_check,
                )
            else:
                raise TypeError(f"Unknown payload type: {type(payload)}")

        kind = invoice.kind.name  # Convert Enum to string
        if kind == "GUIDELINE":
            return _InvoiceDocument(
                kind=kind,
                payload=serialize_payload(invoice.payload),
                checksum=invoice.checksum,
                state_version=invoice.state_version,
                approved=invoice.approved,
                data=serialize_invoice_guideline_data(cast(InvoiceGuidelineData, invoice.data))
                if invoice.data
                else None,
                error=invoice.error,
            )
        elif kind == "STYLE_GUIDE":
            return _InvoiceDocument(
                kind=kind,
                payload=serialize_payload(invoice.payload),
                checksum=invoice.checksum,
                state_version=invoice.state_version,
                approved=invoice.approved,
                data=serialize_invoice_style_guide_data(cast(InvoiceStyleGuideData, invoice.data))
                if invoice.data
                else None,
                error=invoice.error,
            )
        else:
            raise ValueError(
                f"Unsupported invoice kind: {kind} with data type of: {type(invoice.data)}"
            )

    def _serialize_evaluation(self, evaluation: Evaluation) -> _EvaluationDocument:
        return _EvaluationDocument(
            id=ObjectId(evaluation.id),
            version=self.VERSION.to_string(),
            agent_id=evaluation.agent_id,
            creation_utc=evaluation.creation_utc.isoformat(),
            status=evaluation.status.name,
            error=evaluation.error,
            invoices=[self._serialize_invoice(inv) for inv in evaluation.invoices],
            progress=evaluation.progress,
        )

    def _deserialize_evaluation(self, evaluation_document: _EvaluationDocument) -> Evaluation:
        def deserialize_guideline_content_document(
            gc_doc: _GuidelineContentDocument,
        ) -> GuidelineContent:
            return GuidelineContent(
                condition=gc_doc["condition"],
                action=gc_doc["action"],
            )

        def deserialize_guideline_coherence_check_document(
            cc_doc: _GuidelineCoherenceCheckDocument,
        ) -> GuidelineCoherenceCheck:
            return GuidelineCoherenceCheck(
                kind=cc_doc["kind"],
                first=deserialize_guideline_content_document(cc_doc["first"]),
                second=deserialize_guideline_content_document(cc_doc["second"]),
                issue=cc_doc["issue"],
                severity=cc_doc["severity"],
            )

        def deserialize_guideline_connection_proposition_document(
            cp_doc: _GuidelineConnectionPropositionDocument,
        ) -> GuidelineConnectionProposition:
            return GuidelineConnectionProposition(
                check_kind=cp_doc["check_kind"],
                source=deserialize_guideline_content_document(cp_doc["source"]),
                target=deserialize_guideline_content_document(cp_doc["target"]),
            )

        def deserialize_invoice_guideline_data(
            data_doc: _InvoiceGuidelineDataDocument,
        ) -> InvoiceGuidelineData:
            return InvoiceGuidelineData(
                coherence_checks=[
                    deserialize_guideline_coherence_check_document(cc_doc)
                    for cc_doc in data_doc["coherence_checks"]
                ],
                connection_propositions=(
                    [
                        deserialize_guideline_connection_proposition_document(cp_doc)
                        for cp_doc in data_doc["connection_propositions"]
                    ]
                    if data_doc["connection_propositions"] is not None
                    else None
                ),
            )

        def deserialize_event(doc: StyleGuideEventDocument) -> StyleGuideEvent:
            return StyleGuideEvent(source=doc["source"], message=doc["message"])

        def deserialize_example(doc: StyleGuideExampleDocument) -> StyleGuideExample:
            return StyleGuideExample(
                before=[deserialize_event(event_doc) for event_doc in doc["before"]],
                after=[deserialize_event(event_doc) for event_doc in doc["after"]],
                violation=doc["violation"],
            )

        def deserialize_style_guide_content_document(
            sgc_doc: _StyleGuideContentDocument,
        ) -> StyleGuideContent:
            return StyleGuideContent(
                principle=sgc_doc["principle"],
                examples=[deserialize_example(example) for example in sgc_doc["examples"]],
            )

        def deserialize_style_guide_coherence_check_document(
            cc_doc: _StyleGuideCoherenceCheckDocument,
        ) -> StyleGuideCoherenceCheck:
            return StyleGuideCoherenceCheck(
                kind=cc_doc["kind"],
                first=deserialize_style_guide_content_document(cc_doc["first"]),
                second=deserialize_style_guide_content_document(cc_doc["second"]),
                issue=cc_doc["issue"],
                severity=cc_doc["severity"],
            )

        def deserialize_invoice_style_guide_data(
            data_doc: _InvoiceStyleGuideDataDocument,
        ) -> InvoiceStyleGuideData:
            return InvoiceStyleGuideData(
                coherence_checks=[
                    deserialize_style_guide_coherence_check_document(cc_doc)
                    for cc_doc in data_doc["coherence_checks"]
                ],
            )

        def deserialize_invoice_data(
            kind: PayloadKind, data_doc: _InvoiceDataDocument
        ) -> InvoiceData:
            if kind == PayloadKind.GUIDELINE:
                return deserialize_invoice_guideline_data(
                    cast(_InvoiceGuidelineDataDocument, data_doc)
                )
            elif kind == PayloadKind.STYLE_GUIDE:
                return deserialize_invoice_style_guide_data(
                    cast(_InvoiceStyleGuideDataDocument, data_doc)
                )
            else:
                raise ValueError(f"Unsupported payload kind: {kind}")

        def deserialize_guideline_payload_docuemnt(
            gp_doc: _GuidelinePayloadDocument,
        ) -> GuidelinePayload:
            return GuidelinePayload(
                content=GuidelineContent(
                    condition=gp_doc["content"]["condition"],
                    action=gp_doc["content"]["action"],
                ),
                operation=gp_doc["action"],
                updated_id=gp_doc["updated_id"],
                coherence_check=gp_doc["coherence_check"],
                connection_proposition=gp_doc["connection_proposition"],
            )

        def deserialize_style_guide_payload_docuemnt(
            sgp_doc: _StyleGuidePayloadDocument,
        ) -> StyleGuidePayload:
            return StyleGuidePayload(
                content=deserialize_style_guide_content_document(sgp_doc["content"]),
                operation=sgp_doc["action"],
                updated_id=sgp_doc["updated_id"],
                coherence_check=sgp_doc["coherence_check"],
            )

        def deserialize_invoice_document(invoice_doc: _InvoiceDocument) -> Invoice:
            kind = PayloadKind[invoice_doc["kind"]]
            if kind == PayloadKind.GUIDELINE:
                return Invoice(
                    kind=PayloadKind.GUIDELINE,
                    payload=deserialize_guideline_payload_docuemnt(
                        cast(_GuidelinePayloadDocument, invoice_doc["payload"])
                    ),
                    checksum=invoice_doc["checksum"],
                    state_version=invoice_doc["state_version"],
                    approved=invoice_doc["approved"],
                    data=deserialize_invoice_guideline_data(
                        cast(_InvoiceGuidelineDataDocument, invoice_doc["data"])
                    )
                    if invoice_doc.get("data")
                    else None,
                    error=invoice_doc.get("error"),
                )
            elif kind == PayloadKind.STYLE_GUIDE:
                return Invoice(
                    kind=PayloadKind.STYLE_GUIDE,
                    payload=deserialize_style_guide_payload_docuemnt(
                        cast(_StyleGuidePayloadDocument, invoice_doc["payload"])
                    ),
                    checksum=invoice_doc["checksum"],
                    state_version=invoice_doc["state_version"],
                    approved=invoice_doc["approved"],
                    data=deserialize_invoice_style_guide_data(
                        cast(_InvoiceStyleGuideDataDocument, invoice_doc["data"])
                    )
                    if invoice_doc.get("data")
                    else None,
                    error=invoice_doc.get("error"),
                )
            else:
                raise ValueError(f"Unsupported payload kind: {kind}")

        evaluation_id = EvaluationId(evaluation_document["id"])
        creation_utc = datetime.fromisoformat(evaluation_document["creation_utc"])

        status = EvaluationStatus[evaluation_document["status"]]

        invoices = [
            deserialize_invoice_document(inv_doc) for inv_doc in evaluation_document["invoices"]
        ]

        return Evaluation(
            id=evaluation_id,
            agent_id=AgentId(evaluation_document["agent_id"]),
            creation_utc=creation_utc,
            status=status,
            error=evaluation_document.get("error"),
            invoices=invoices,
            progress=evaluation_document["progress"],
        )

    @override
    async def create_evaluation(
        self,
        agent_id: AgentId,
        payload_descriptors: Sequence[PayloadDescriptor],
        creation_utc: Optional[datetime] = None,
        extra: Optional[Mapping[str, JSONSerializable]] = None,
    ) -> Evaluation:
        async with self._lock.writer_lock:
            creation_utc = creation_utc or datetime.now(timezone.utc)

            evaluation_id = EvaluationId(generate_id())

            invoices = [
                Invoice(
                    kind=k,
                    payload=cast(GuidelinePayload, p),
                    state_version="",
                    checksum="",
                    approved=False,
                    data=None,
                    error=None,
                )
                for k, p in payload_descriptors
            ]

            evaluation = Evaluation(
                id=evaluation_id,
                agent_id=agent_id,
                status=EvaluationStatus.PENDING,
                creation_utc=creation_utc,
                error=None,
                invoices=invoices,
                progress=0.0,
            )

            await self._collection.insert_one(self._serialize_evaluation(evaluation=evaluation))

        return evaluation

    @override
    async def update_evaluation(
        self,
        evaluation_id: EvaluationId,
        params: EvaluationUpdateParams,
    ) -> Evaluation:
        async with self._lock.writer_lock:
            evaluation = await self.read_evaluation(evaluation_id)

            update_params: _EvaluationDocument = {}
            if "invoices" in params:
                update_params["invoices"] = [self._serialize_invoice(i) for i in params["invoices"]]

            if "status" in params:
                update_params["status"] = params["status"].name
                update_params["error"] = params["error"] if "error" in params else None

            if "progress" in params:
                update_params["progress"] = params["progress"]

            result = await self._collection.update_one(
                filters={"id": {"$eq": evaluation.id}},
                params=update_params,
            )

        assert result.updated_document

        return self._deserialize_evaluation(result.updated_document)

    @override
    async def read_evaluation(
        self,
        evaluation_id: EvaluationId,
    ) -> Evaluation:
        async with self._lock.reader_lock:
            evaluation_document = await self._collection.find_one(
                filters={"id": {"$eq": evaluation_id}},
            )

        if not evaluation_document:
            raise ItemNotFoundError(item_id=UniqueId(evaluation_id))

        return self._deserialize_evaluation(evaluation_document=evaluation_document)

    @override
    async def list_evaluations(
        self,
    ) -> Sequence[Evaluation]:
        async with self._lock.reader_lock:
            return [
                self._deserialize_evaluation(evaluation_document=e)
                for e in await self._collection.find(filters={})
            ]


class EvaluationListener(ABC):
    @abstractmethod
    async def wait_for_completion(
        self,
        evaluation_id: EvaluationId,
        timeout: Timeout = Timeout.infinite(),
    ) -> bool: ...


class PollingEvaluationListener(EvaluationListener):
    def __init__(self, evaluation_store: EvaluationStore) -> None:
        self._evaluation_store = evaluation_store

    @override
    async def wait_for_completion(
        self,
        evaluation_id: EvaluationId,
        timeout: Timeout = Timeout.infinite(),
    ) -> bool:
        while True:
            evaluation = await self._evaluation_store.read_evaluation(
                evaluation_id,
            )

            if evaluation.status in [EvaluationStatus.COMPLETED, EvaluationStatus.FAILED]:
                return True
            elif timeout.expired():
                return False
            else:
                await timeout.wait_up_to(1)
