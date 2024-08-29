from datetime import datetime
from typing import Optional, Sequence
from fastapi import APIRouter, HTTPException, status


from emcie.server.base_models import DefaultBaseModel
from emcie.server.core.evaluations import (
    EvaluationGuidelinePayload,
    EvaluationId,
    EvaluationInvoiceData,
    EvaluationPayload,
    EvaluationStatus,
    EvaluationStore,
)
from emcie.server.indexing.behavioral_change_evaluation import (
    BehavioralChangeEvaluator,
    EvaluationValidationError,
)


class CreateEvaluationRequest(DefaultBaseModel):
    payloads: Sequence[EvaluationGuidelinePayload]


class CreateEvaluationResponse(DefaultBaseModel):
    evaluation_id: EvaluationId


class EvaluationInvoiceDTO(DefaultBaseModel):
    payload: EvaluationPayload
    checksum: str
    approved: bool
    data: Optional[EvaluationInvoiceData]
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
                    data=invoice.data,
                    error=invoice.error,
                )
                for invoice in evaluation.invoices
            ],
            error=evaluation.error,
        )

    return router
