from datetime import datetime
from typing import Optional, Sequence
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel


from emcie.server.behavioral_change_evaluation import (
    BehavioralChangeEvaluator,
    EvaluationValidationError,
)
from emcie.server.base_models import DefaultBaseModel
from emcie.server.core.evaluations import (
    EvaluationGuidelinePayload,
    EvaluationId,
    EvaluationInvoiceData,
    EvaluationInvoiceId,
    EvaluationPayload,
    EvaluationStatus,
    EvaluationStore,
)


class CreateEvaluationRequest(DefaultBaseModel):
    payloads: Sequence[EvaluationGuidelinePayload]


class CreateEvaluationResponse(DefaultBaseModel):
    evaluation_id: EvaluationId


class EvaluationInvoiceDTO(BaseModel):
    invoice_id: EvaluationInvoiceId
    payload: EvaluationPayload
    checksum: str
    approved: bool
    data: Optional[EvaluationInvoiceData]
    error: Optional[str]


class EvaluationDTO(DefaultBaseModel):
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
    async def get_evaluation(evaluation_id: EvaluationId) -> EvaluationDTO:
        evaluation = await evaluation_store.read_evaluation(evaluation_id=evaluation_id)

        return EvaluationDTO(
            evaluation_id=evaluation.id,
            status=evaluation.status,
            creation_utc=evaluation.creation_utc,
            invoices=[
                EvaluationInvoiceDTO(
                    invoice_id=invoice.id,
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
