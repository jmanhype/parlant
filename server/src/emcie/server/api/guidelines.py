from typing import Optional, Sequence, TypedDict
from fastapi import APIRouter, HTTPException, status


from emcie.server.api.common import (
    ConnectionKindDTO,
    GuidelinePayloadDTO,
    InvoiceGuidelineDataDTO,
)
from emcie.server.core.agents import AgentId
from emcie.server.core.common import DefaultBaseModel
from emcie.server.core.evaluations import (
    CoherenceCheck,
    ConnectionProposition,
    GuidelinePayload,
    Invoice,
    InvoiceGuidelineData,
    PayloadKind,
)
from emcie.server.core.guideline_connections import ConnectionKind
from emcie.server.core.guidelines import GuidelineContent, GuidelineId, GuidelineStore
from emcie.server.core.mc import MC


class GuidelineDTO(DefaultBaseModel):
    id: GuidelineId
    guideline_set: str
    predicate: str
    action: str


class InvoiceGuidelineDTO(DefaultBaseModel):
    payload: GuidelinePayloadDTO
    checksum: str
    approved: bool
    data: InvoiceGuidelineDataDTO
    error: Optional[str]


class CreateGuidelineRequest(DefaultBaseModel):
    agent_id: AgentId
    invoices: Sequence[InvoiceGuidelineDTO]


class CreateGuidelinesResponse(DefaultBaseModel):
    guidelines: list[GuidelineDTO]


class ListGuidelineResponse(DefaultBaseModel):
    guidelines: list[GuidelineDTO]


class DeleteGuidelineRequest(DefaultBaseModel):
    guideline_id: GuidelineId


class DeleteGuidelineResponse(DefaultBaseModel):
    deleted_guideline_id: Optional[GuidelineId]


class ListGuidelinesResponse(DefaultBaseModel):
    guidelines: list[GuidelineDTO]


def _invoice_dto_to_invoice(dto: InvoiceGuidelineDTO) -> Invoice:
    if not dto.approved:
        raise ValueError("Unapproved invoice.")

    payload = GuidelinePayload(
        content=GuidelineContent(
            predicate=dto.payload["predicate"],
            action=dto.payload["action"],
        )
    )

    kind = PayloadKind.GUIDELINE

    if not dto.data:
        raise ValueError("Unsupported payload.")

    data = _invoice_data_dto_to_invoice_data(dto.data)

    return Invoice(
        kind=kind,
        payload=payload,
        checksum=dto.checksum,
        state_version="",  # FIXME: once state functionality will be implemented this need to be refactored
        approved=dto.approved,
        data=data,
        error=dto.error,
    )


def _connection_kind_dto_to_connection_kind(dto: ConnectionKindDTO) -> ConnectionKind:
    return {
        "entails": ConnectionKind.ENTAILS,
        "suggests": ConnectionKind.SUGGESTS,
    }[dto]


def _invoice_data_dto_to_invoice_data(dto: InvoiceGuidelineDataDTO) -> InvoiceGuidelineData:
    try:
        coherence_checks = [
            CoherenceCheck(
                kind=check.kind,
                first=GuidelineContent(predicate=check.first.predicate, action=check.first.action),
                second=GuidelineContent(
                    predicate=check.second.predicate, action=check.second.action
                ),
                issue=check.issue,
                severity=check.severity,
            )
            for check in dto.coherence_checks
        ]

        if dto.connection_propositions:
            connection_propositions = [
                ConnectionProposition(
                    check_kind=prop.check_kind,
                    source=GuidelineContent(
                        predicate=prop.source.predicate, action=prop.source.action
                    ),
                    target=GuidelineContent(
                        predicate=prop.target.predicate, action=prop.target.action
                    ),
                    connection_kind=_connection_kind_dto_to_connection_kind(prop.connection_kind),
                )
                for prop in dto.connection_propositions
            ]
        else:
            connection_propositions = None

        return InvoiceGuidelineData(
            coherence_checks=coherence_checks, connection_propositions=connection_propositions
        )

    except Exception:
        raise ValueError(f"Unsupported invoice guideline data: {dto}")


def create_router(
    mc: MC,
    guideline_store: GuidelineStore,
) -> APIRouter:
    router = APIRouter()

    @router.post("/", status_code=status.HTTP_201_CREATED)
    async def create_guidelines(request: CreateGuidelineRequest) -> CreateGuidelinesResponse:
        try:
            invoices = [_invoice_dto_to_invoice(i) for i in request.invoices]
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            )

        guidelines = await mc.create_guidelines(
            guideline_set=request.agent_id,
            invoices=invoices,
        )

        return CreateGuidelinesResponse(
            guidelines=[
                GuidelineDTO(
                    guideline_set=request.agent_id,
                    id=g.id,
                    predicate=g.content.predicate,
                    action=g.content.action,
                )
                for g in guidelines
            ]
        )

    @router.get("/{agent_id}/{guideline_id}")
    async def read_guideline(agent_id: AgentId, guideline_id: GuidelineId) -> GuidelineDTO:
        guideline = await guideline_store.read_guideline(
            guideline_set=agent_id,
            guideline_id=guideline_id,
        )

        return GuidelineDTO(
            guideline_set=agent_id,
            id=guideline.id,
            predicate=guideline.content.predicate,
            action=guideline.content.action,
        )

    @router.get("/{agent_id}")
    async def list_guidelines(agent_id: AgentId) -> ListGuidelinesResponse:
        guidelines = await guideline_store.list_guidelines(guideline_set=agent_id)

        return ListGuidelinesResponse(
            guidelines=[
                GuidelineDTO(
                    guideline_set=agent_id,
                    id=g.id,
                    predicate=g.content.predicate,
                    action=g.content.action,
                )
                for g in guidelines
            ]
        )

    return router
