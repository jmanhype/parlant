from typing import Sequence
from fastapi import APIRouter, HTTPException, status

from emcie.server.evaluation_service import (
    EvaluationService,
    EvaluationGuidelinePayload,
    EvaluationId,
)
from emcie.server.base_models import DefaultBaseModel


class CreateEvaluationRequest(DefaultBaseModel):
    payloads: Sequence[EvaluationGuidelinePayload]


class CreateEvaluationResponse(DefaultBaseModel):
    evaluation_id: EvaluationId


def create_router(
    evaluation_service: EvaluationService,
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

    return router
