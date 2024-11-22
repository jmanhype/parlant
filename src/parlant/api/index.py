from datetime import datetime
from typing import Optional, Sequence, cast
from fastapi import APIRouter, HTTPException, status

from parlant.api.common import (
    CoherenceCheckDTO,
    CoherenceCheckKindDTO,
    ConnectionPropositionDTO,
    ConnectionPropositionKindDTO,
    EvaluationStatusDTO,
    GuidelineContentDTO,
    GuidelinePayloadDTO,
    GuidelinePayloadOperationDTO,
    GuidelineInvoiceDataDTO,
    InvoiceDataDTO,
    PayloadDTO,
    PayloadKindDTO,
    apigen_config,
    connection_kind_to_dto,
)
from parlant.core.common import DefaultBaseModel
from parlant.core.agents import AgentId, AgentStore
from parlant.core.evaluations import (
    EvaluationId,
    EvaluationStatus,
    EvaluationStore,
    GuidelinePayload,
    InvoiceData,
    Payload,
    PayloadDescriptor,
    PayloadKind,
)
from parlant.core.guidelines import GuidelineContent
from parlant.core.services.indexing.behavioral_change_evaluation import (
    BehavioralChangeEvaluator,
    EvaluationValidationError,
)

API_GROUP = "evaluations"


def _evaluation_status_to_dto(
    status: EvaluationStatus,
) -> EvaluationStatusDTO:
    return cast(
        EvaluationStatusDTO,
        {
            EvaluationStatus.PENDING: "pending",
            EvaluationStatus.RUNNING: "running",
            EvaluationStatus.COMPLETED: "completed",
            EvaluationStatus.FAILED: "failed",
        }[status],
    )


def _payload_from_dto(dto: PayloadDTO) -> Payload:
    if dto.kind == PayloadKindDTO.GUIDELINE:
        if not dto.guideline:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Missing Guideline payload",
            )

        return GuidelinePayload(
            content=GuidelineContent(
                condition=dto.guideline.content.condition,
                action=dto.guideline.content.action,
            ),
            operation=dto.guideline.operation.value,
            updated_id=dto.guideline.updated_id,
            coherence_check=dto.guideline.coherence_check,
            connection_proposition=dto.guideline.connection_proposition,
        )

    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="Unsupported DTO kind",
    )


def _payload_descriptor_to_dto(descriptor: PayloadDescriptor) -> PayloadDTO:
    if descriptor.kind == PayloadKind.GUIDELINE:
        return PayloadDTO(
            kind=PayloadKindDTO.GUIDELINE,
            guideline=GuidelinePayloadDTO(
                content=GuidelineContentDTO(
                    condition=descriptor.payload.content.condition,
                    action=descriptor.payload.content.action,
                ),
                operation=GuidelinePayloadOperationDTO(descriptor.payload.operation),
                updated_id=descriptor.payload.updated_id,
                coherence_check=descriptor.payload.coherence_check,
                connection_proposition=descriptor.payload.connection_proposition,
            ),
        )

    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="Unsupported descriptor kind",
    )


def _invoice_data_to_dto(kind: PayloadKind, invoice_data: InvoiceData) -> InvoiceDataDTO:
    if kind == PayloadKind.GUIDELINE:
        return InvoiceDataDTO(
            guideline=GuidelineInvoiceDataDTO(
                coherence_checks=[
                    CoherenceCheckDTO(
                        kind=CoherenceCheckKindDTO(c.kind),
                        first=GuidelineContentDTO(
                            condition=c.first.condition,
                            action=c.first.action,
                        ),
                        second=GuidelineContentDTO(
                            condition=c.second.condition,
                            action=c.second.action,
                        ),
                        issue=c.issue,
                        severity=c.severity,
                    )
                    for c in invoice_data.coherence_checks
                ],
                connection_propositions=[
                    ConnectionPropositionDTO(
                        check_kind=ConnectionPropositionKindDTO(c.check_kind),
                        source=GuidelineContentDTO(
                            condition=c.source.condition,
                            action=c.source.action,
                        ),
                        target=GuidelineContentDTO(
                            condition=c.target.condition,
                            action=c.target.action,
                        ),
                        connection_kind=connection_kind_to_dto(c.connection_kind),
                    )
                    for c in invoice_data.connection_propositions
                ]
                if invoice_data.connection_propositions
                else None,
            )
        )

    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="Unsupported descriptor kind",
    )


class InvoiceDTO(DefaultBaseModel):
    payload: PayloadDTO
    checksum: str
    approved: bool
    data: Optional[InvoiceDataDTO]
    error: Optional[str]


class EvaluationCreationParamsDTO(DefaultBaseModel):
    agent_id: AgentId
    payloads: Sequence[PayloadDTO]


class EvaluationCreationResult(DefaultBaseModel):
    evaluation_id: EvaluationId


class EvaluationReadResult(DefaultBaseModel):
    evaluation_id: EvaluationId
    status: EvaluationStatusDTO
    progress: float
    creation_utc: datetime
    error: Optional[str]
    invoices: list[InvoiceDTO]


def create_router(
    evaluation_service: BehavioralChangeEvaluator,
    evaluation_store: EvaluationStore,
    agent_store: AgentStore,
) -> APIRouter:
    router = APIRouter()

    @router.post(
        "/evaluations",
        status_code=status.HTTP_201_CREATED,
        operation_id="create_evaluation",
        **apigen_config(group_name=API_GROUP, method_name="create"),
    )
    async def create_evaluation(params: EvaluationCreationParamsDTO) -> EvaluationCreationResult:
        try:
            agent = await agent_store.read_agent(agent_id=params.agent_id)
            evaluation_id = await evaluation_service.create_evaluation_task(
                agent=agent,
                payload_descriptors=[
                    PayloadDescriptor(PayloadKind.GUIDELINE, p)
                    for p in [_payload_from_dto(p) for p in params.payloads]
                ],
            )
        except EvaluationValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            )

        return EvaluationCreationResult(evaluation_id=evaluation_id)

    @router.get(
        "/evaluations/{evaluation_id}",
        operation_id="read_evaluation",
        **apigen_config(group_name=API_GROUP, method_name="retrieve"),
    )
    async def read_evaluation(evaluation_id: EvaluationId) -> EvaluationReadResult:
        evaluation = await evaluation_store.read_evaluation(evaluation_id=evaluation_id)

        return EvaluationReadResult(
            evaluation_id=evaluation.id,
            status=_evaluation_status_to_dto(evaluation.status),
            progress=evaluation.progress,
            creation_utc=evaluation.creation_utc,
            invoices=[
                InvoiceDTO(
                    payload=_payload_descriptor_to_dto(
                        PayloadDescriptor(kind=invoice.kind, payload=invoice.payload)
                    ),
                    checksum=invoice.checksum,
                    approved=invoice.approved,
                    data=_invoice_data_to_dto(invoice.kind, invoice.data) if invoice.data else None,
                    error=invoice.error,
                )
                for invoice in evaluation.invoices
            ],
            error=evaluation.error,
        )

    return router
