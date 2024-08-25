from datetime import datetime
from typing import Optional, Sequence
from fastapi import APIRouter, HTTPException, status
from openai import BaseModel

from emcie.server.core.common import UniqueId
from emcie.server.behavioral_change_evaluation import (
    EvaluationInvoiceData,
    EvaluationPayload,
    BehavioralChangeEvaluator,
    EvaluationGuidelinePayload,
    EvaluationId,
    EvaluationStore,
)
from emcie.server.base_models import DefaultBaseModel


class CreateEvaluationRequest(DefaultBaseModel):
    payloads: Sequence[EvaluationGuidelinePayload]


class CreateEvaluationResponse(DefaultBaseModel):
    evaluation_id: EvaluationId


class InvoiceDTO(BaseModel):
    invoice_id: str
    checksum: str
    approved: bool
    data: EvaluationInvoiceData


class EvaluationItemDTO(BaseModel):
    item_id: UniqueId
    payload: EvaluationPayload
    invoice: Optional[InvoiceDTO]
    error: Optional[str]


class EvaluationDTO(BaseModel):
    evaluation_id: str
    status: str
    creation_utc: datetime
    error: Optional[str]
    items: list[EvaluationItemDTO]


def create_router(
    evaluation_service: BehavioralChangeEvaluator,
    evaluation_store: EvaluationStore,
) -> APIRouter:
    router = APIRouter()

    @router.post("/evaluations", response_model=CreateEvaluationResponse)
    async def create_evaluation(request: CreateEvaluationRequest) -> CreateEvaluationResponse:
        if not request.payloads:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No payloads provided for the evaluation task.",
            )

        evaluation_id = await evaluation_service.create_evaluation_task(
            payloads=request.payloads,
        )
        return CreateEvaluationResponse(evaluation_id=evaluation_id)

    @router.get("/evaluations/{evaluation_id}", response_model=EvaluationDTO)
    async def get_evaluation(evaluation_id: EvaluationId) -> EvaluationDTO:
        evaluation = await evaluation_store.read_evaluation(evaluation_id=evaluation_id)

        return EvaluationDTO(
            evaluation_id=evaluation.id,
            status=evaluation.status,
            creation_utc=evaluation.creation_utc,
            items=[
                EvaluationItemDTO(
                    item_id=i["id"],
                    payload=i["payload"],
                    invoice=InvoiceDTO(
                        invoice_id=i["invoice"]["id"],
                        checksum=i["invoice"]["checksum"],
                        approved=i["invoice"]["approved"],
                        data=i["invoice"]["data"],
                    )
                    if i["invoice"]
                    else None,
                    error=i["error"],
                )
                for i in evaluation.items
            ],
            error=evaluation.error,
        )

    return router
