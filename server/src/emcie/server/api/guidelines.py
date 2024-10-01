from itertools import chain
from typing import Optional, Sequence
from fastapi import APIRouter, HTTPException, status


from emcie.server.api.common import (
    ConnectionKindDTO,
    GuidelinePayloadDTO,
    InvoiceGuidelineDataDTO,
    connection_kind_dto_to_connection_kind,
    connection_kind_to_dto,
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
from emcie.server.core.guideline_connections import (
    GuidelineConnection,
    GuidelineConnectionId,
    GuidelineConnectionStore,
)
from emcie.server.core.guidelines import Guideline, GuidelineContent, GuidelineId, GuidelineStore
from emcie.server.core.mc import MC


class GuidelineConnectionDTO(DefaultBaseModel):
    id: GuidelineConnectionId
    source: GuidelineId
    target: GuidelineId
    kind: ConnectionKindDTO


class GuidelineDTO(DefaultBaseModel):
    id: GuidelineId
    guideline_set: str
    predicate: str
    action: str
    connections: Sequence[GuidelineConnectionDTO]


class InvoiceGuidelineDTO(DefaultBaseModel):
    payload: GuidelinePayloadDTO
    checksum: str
    approved: bool
    data: InvoiceGuidelineDataDTO
    error: Optional[str]


class CreateGuidelineRequest(DefaultBaseModel):
    invoices: Sequence[InvoiceGuidelineDTO]


class CreateGuidelinesResponse(DefaultBaseModel):
    guidelines: list[GuidelineDTO]


class ListGuidelineResponse(DefaultBaseModel):
    guidelines: list[GuidelineDTO]


class DeleteGuidelineRequest(DefaultBaseModel):
    guideline_id: GuidelineId


class DeleteGuidelineResponse(DefaultBaseModel):
    deleted_guideline_id: GuidelineId


class ListGuidelinesResponse(DefaultBaseModel):
    guidelines: list[GuidelineDTO]


class ConnectionDTO(DefaultBaseModel):
    source: GuidelineId
    target: GuidelineId
    kind: ConnectionKindDTO


class PatchGuidelineRequest(DefaultBaseModel):
    added_connections: Optional[Sequence[ConnectionDTO]] = None
    removed_connections: Optional[Sequence[GuidelineId]] = None


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
                    connection_kind=connection_kind_dto_to_connection_kind(prop.connection_kind),
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
    guideline_connection_store: GuidelineConnectionStore,
) -> APIRouter:
    router = APIRouter()

    @router.post("/{agent_id}/guidelines/", status_code=status.HTTP_201_CREATED)
    async def create_guidelines(
        agent_id: AgentId,
        request: CreateGuidelineRequest,
    ) -> CreateGuidelinesResponse:
        try:
            invoices = [_invoice_dto_to_invoice(i) for i in request.invoices]
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            )

        result = await mc.create_guidelines(
            guideline_set=agent_id,
            invoices=invoices,
        )

        return CreateGuidelinesResponse(
            guidelines=[
                GuidelineDTO(
                    guideline_set=agent_id,
                    id=guideline.id,
                    predicate=guideline.content.predicate,
                    action=guideline.content.action,
                    connections=[
                        GuidelineConnectionDTO(
                            id=c.id,
                            source=c.source,
                            target=c.target,
                            kind=connection_kind_to_dto(c.kind),
                        )
                        for c in connections
                    ],
                )
                for guideline, connections in result
            ]
        )

    @router.get("/{agent_id}/guidelines/{guideline_id}")
    async def read_guideline(agent_id: AgentId, guideline_id: GuidelineId) -> GuidelineDTO:
        guideline = await guideline_store.read_guideline(
            guideline_set=agent_id, guideline_id=guideline_id
        )

        connections = await mc.get_guideline_connections(guideline_id)

        return GuidelineDTO(
            guideline_set=agent_id,
            id=guideline.id,
            predicate=guideline.content.predicate,
            action=guideline.content.action,
            connections=[
                GuidelineConnectionDTO(
                    id=c.id,
                    source=c.source,
                    target=c.target,
                    kind=connection_kind_to_dto(c.kind),
                )
                for c in connections
            ],
        )

    @router.get("/{agent_id}/guidelines/")
    async def list_guidelines(agent_id: AgentId) -> ListGuidelinesResponse:
        guidelines = await guideline_store.list_guidelines(guideline_set=agent_id)

        guideline_connections: list[tuple[Guideline, list[GuidelineConnection]]] = [
            (
                g,
                list(
                    chain(
                        await guideline_connection_store.list_connections(
                            indirect=False, source=g.id
                        ),
                        await guideline_connection_store.list_connections(
                            indirect=False, target=g.id
                        ),
                    )
                ),
            )
            for g in guidelines
        ]

        return ListGuidelinesResponse(
            guidelines=[
                GuidelineDTO(
                    guideline_set=agent_id,
                    id=guideline.id,
                    predicate=guideline.content.predicate,
                    action=guideline.content.action,
                    connections=[
                        GuidelineConnectionDTO(
                            id=c.id,
                            source=c.source,
                            target=c.target,
                            kind=connection_kind_to_dto(c.kind),
                        )
                        for c in connections
                    ],
                )
                for guideline, connections in guideline_connections
            ]
        )

    @router.patch("/{agent_id}/guidelines/{guideline_id}")
    async def patch_guideline(
        agent_id: AgentId, guideline_id: GuidelineId, request: PatchGuidelineRequest
    ) -> GuidelineDTO:
        guideline = await guideline_store.read_guideline(
            guideline_set=agent_id,
            guideline_id=guideline_id,
        )

        if request.added_connections:
            for req in request.added_connections:
                await guideline_connection_store.create_connection(
                    source=req.source,
                    target=req.target,
                    kind=connection_kind_dto_to_connection_kind(req.kind),
                )

        connections = await mc.get_guideline_connections(guideline_id)

        if request.removed_connections:
            for id in request.removed_connections:
                if connection_to_remove := next(
                    iter([c for c in connections if id in [c.source, c.target]])
                ):
                    await guideline_connection_store.delete_connection(connection_to_remove.id)

        return GuidelineDTO(
            guideline_set=agent_id,
            id=guideline.id,
            predicate=guideline.content.predicate,
            action=guideline.content.action,
            connections=[
                GuidelineConnectionDTO(
                    id=c.id,
                    source=c.source,
                    target=c.target,
                    kind=connection_kind_to_dto(c.kind),
                )
                for c in await mc.get_guideline_connections(guideline_id)
            ],
        )

    @router.delete("/{agent_id}/guidelines/{guideline_id}")
    async def delete_guideline(
        agent_id: AgentId, guideline_id: GuidelineId
    ) -> DeleteGuidelineResponse:
        deleted_guideline = await guideline_store.delete_guideline(
            guideline_set=agent_id,
            guideline_id=guideline_id,
        )

        return DeleteGuidelineResponse(deleted_guideline_id=deleted_guideline.id)

    return router
