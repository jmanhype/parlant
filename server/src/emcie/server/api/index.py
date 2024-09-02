from datetime import datetime
from typing import Literal, Optional, Sequence
from fastapi import APIRouter, HTTPException, status


from emcie.server.base_models import DefaultBaseModel
from emcie.server.core.evaluations import (
    EvaluationCoherenceCheckResultType,
    EvaluationConnectionPropositionResultType,
    EvaluationGuidelinePayload,
    EvaluationId,
    EvaluationPayload,
    EvaluationStatus,
    EvaluationStore,
)
from emcie.server.core.guideline_connections import ConnectionKind
from emcie.server.core.guidelines import GuidelineData
from emcie.server.indexing.behavioral_change_evaluation import (
    BehavioralChangeEvaluator,
    EvaluationValidationError,
)


class CoherenceCheckResultDTO(DefaultBaseModel):
    type: EvaluationCoherenceCheckResultType
    first: GuidelineData
    second: GuidelineData
    issue: str
    severity: int


class ConnectionPropositionResultDTO(DefaultBaseModel):
    type: EvaluationConnectionPropositionResultType
    source: GuidelineData
    target: GuidelineData
    kind: ConnectionKind


class EvaluationGuidelineCoherenceCheckResultDTO(DefaultBaseModel):
    coherence_checks: Optional[list[CoherenceCheckResultDTO]]


class EvaluationGuidelineConnectionPropositionsResultDTO(DefaultBaseModel):
    connection_propositions: Optional[list[ConnectionPropositionResultDTO]]


class EvaluationInvoiceGuidelineDataDTO(DefaultBaseModel):
    type: Literal["guideline"]
    coherence_check_detail: EvaluationGuidelineCoherenceCheckResultDTO
    connections_detail: EvaluationGuidelineConnectionPropositionsResultDTO


class CreateEvaluationRequest(DefaultBaseModel):
    payloads: Sequence[EvaluationGuidelinePayload]


class CreateEvaluationResponse(DefaultBaseModel):
    evaluation_id: EvaluationId


class EvaluationInvoiceDTO(DefaultBaseModel):
    payload: EvaluationPayload
    checksum: str
    approved: bool
    data: Optional[EvaluationInvoiceGuidelineDataDTO]
    error: Optional[str]


class ReadEvaluationResponse(DefaultBaseModel):
    evaluation_id: EvaluationId
    status: EvaluationStatus
    creation_utc: datetime
    error: Optional[str]
    invoices: list[EvaluationInvoiceDTO]


def create_router(
    evaluation_service: BehavioralChangeEvaluator,
    evaluation_store: EvaluationStore,
) -> APIRouter:
    router = APIRouter()

    @router.post("/evaluations")
    async def create_evaluation(request: CreateEvaluationRequest) -> CreateEvaluationResponse:
        try:
            evaluation_id = await evaluation_service.create_evaluation_task(
                payloads=request.payloads,
            )
        except EvaluationValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            )

        return CreateEvaluationResponse(evaluation_id=evaluation_id)

    @router.get("/evaluations/{evaluation_id}")
    async def get_evaluation(evaluation_id: EvaluationId) -> ReadEvaluationResponse:
        evaluation = await evaluation_store.read_evaluation(evaluation_id=evaluation_id)

        return ReadEvaluationResponse(
            evaluation_id=evaluation.id,
            status=evaluation.status,
            creation_utc=evaluation.creation_utc,
            invoices=[
                EvaluationInvoiceDTO(
                    payload=invoice.payload,
                    checksum=invoice.checksum,
                    approved=invoice.approved,
                    data=EvaluationInvoiceGuidelineDataDTO(
                        type=invoice.data.type,
                        coherence_check_detail=EvaluationGuidelineCoherenceCheckResultDTO(
                            coherence_checks=[
                                CoherenceCheckResultDTO(
                                    type=c.type,
                                    first=c.first,
                                    second=c.second,
                                    issue=c.issue,
                                    severity=c.severity,
                                )
                                for c in invoice.data.coherence_check_detail.coherence_checks
                            ]
                            if invoice.data.coherence_check_detail
                            else []
                        ),
                        connections_detail=EvaluationGuidelineConnectionPropositionsResultDTO(
                            connection_propositions=[
                                ConnectionPropositionResultDTO(
                                    type=c.type,
                                    source=c.source,
                                    target=c.target,
                                    kind=c.kind,
                                )
                                for c in invoice.data.connections_detail.connection_propositions
                            ]
                            if invoice.data.connections_detail
                            else []
                        ),
                    )
                    if invoice.data
                    else None,
                    error=invoice.error,
                )
                for invoice in evaluation.invoices
            ],
            error=evaluation.error,
        )

    return router
