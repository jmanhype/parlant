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
    GuidelineConnectionId,
    GuidelineConnectionStore,
)
from emcie.server.core.guidelines import GuidelineContent, GuidelineId, GuidelineStore
from emcie.server.core.mc import MC


class GuidelineContentDTO(DefaultBaseModel):
    id: GuidelineId
    predicate: str
    action: str


class GuidelineConnectionDTO(DefaultBaseModel):
    id: GuidelineConnectionId
    source: GuidelineContentDTO
    target: GuidelineContentDTO
    kind: ConnectionKindDTO
    indirect: bool


class GuidelineWithConnectionsDTO(DefaultBaseModel):
    id: GuidelineId
    guideline_set: str
    predicate: str
    action: str
    connections: Sequence[GuidelineConnectionDTO]


class GuidelineWithoutConnectionsDTO(DefaultBaseModel):
    guideline_set: str
    id: GuidelineId
    predicate: str
    action: str


class InvoiceGuidelineDTO(DefaultBaseModel):
    payload: GuidelinePayloadDTO
    checksum: str
    approved: bool
    data: InvoiceGuidelineDataDTO
    error: Optional[str]


class CreateGuidelineRequest(DefaultBaseModel):
    invoices: Sequence[InvoiceGuidelineDTO]


class CreateGuidelinesResponse(DefaultBaseModel):
    guidelines: list[GuidelineWithConnectionsDTO]


class DeleteGuidelineRequest(DefaultBaseModel):
    guideline_id: GuidelineId


class DeleteGuidelineResponse(DefaultBaseModel):
    deleted_guideline_id: GuidelineId


class ListGuidelinesResponse(DefaultBaseModel):
    guidelines: list[GuidelineWithoutConnectionsDTO]


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

        guideline_ids = await mc.create_guidelines(
            guideline_set=agent_id,
            invoices=invoices,
        )

        guidelines = [
            await guideline_store.read_guideline(guideline_set=agent_id, guideline_id=id)
            for id in guideline_ids
        ]

        return CreateGuidelinesResponse(
            guidelines=[
                GuidelineWithConnectionsDTO(
                    guideline_set=agent_id,
                    id=guideline.id,
                    predicate=guideline.content.predicate,
                    action=guideline.content.action,
                    connections=[
                        GuidelineConnectionDTO(
                            id=connection.id,
                            source=GuidelineContentDTO(
                                id=connection.source.id,
                                predicate=connection.source.content.predicate,
                                action=connection.source.content.action,
                            ),
                            target=GuidelineContentDTO(
                                id=connection.target.id,
                                predicate=connection.target.content.predicate,
                                action=connection.target.content.action,
                            ),
                            kind=connection_kind_to_dto(connection.kind),
                            indirect=indirect,
                        )
                        for connection, indirect in await mc.get_guideline_connections(
                            guideline_set=agent_id,
                            guideline_id=guideline.id,
                            indirect=True,
                        )
                    ],
                )
                for guideline in guidelines
            ]
        )

    @router.get("/{agent_id}/guidelines/{guideline_id}")
    async def read_guideline(
        agent_id: AgentId, guideline_id: GuidelineId
    ) -> GuidelineWithConnectionsDTO:
        guideline = await guideline_store.read_guideline(
            guideline_set=agent_id, guideline_id=guideline_id
        )

        connections = await mc.get_guideline_connections(
            guideline_set=agent_id,
            guideline_id=guideline_id,
            indirect=True,
        )

        return GuidelineWithConnectionsDTO(
            guideline_set=agent_id,
            id=guideline.id,
            predicate=guideline.content.predicate,
            action=guideline.content.action,
            connections=[
                GuidelineConnectionDTO(
                    id=connection.id,
                    source=GuidelineContentDTO(
                        id=connection.source.id,
                        predicate=connection.source.content.predicate,
                        action=connection.source.content.action,
                    ),
                    target=GuidelineContentDTO(
                        id=connection.target.id,
                        predicate=connection.target.content.predicate,
                        action=connection.target.content.action,
                    ),
                    kind=connection_kind_to_dto(connection.kind),
                    indirect=indirect,
                )
                for connection, indirect in connections
            ],
        )

    @router.get("/{agent_id}/guidelines/")
    async def list_guidelines(agent_id: AgentId) -> ListGuidelinesResponse:
        guidelines = await guideline_store.list_guidelines(guideline_set=agent_id)

        return ListGuidelinesResponse(
            guidelines=[
                GuidelineWithoutConnectionsDTO(
                    guideline_set=agent_id,
                    id=guideline.id,
                    predicate=guideline.content.predicate,
                    action=guideline.content.action,
                )
                for guideline in guidelines
            ]
        )

    @router.patch("/{agent_id}/guidelines/{guideline_id}")
    async def patch_guideline(
        agent_id: AgentId, guideline_id: GuidelineId, request: PatchGuidelineRequest
    ) -> GuidelineWithConnectionsDTO:
        guideline = await guideline_store.read_guideline(
            guideline_set=agent_id,
            guideline_id=guideline_id,
        )

        if request.added_connections:
            for req in request.added_connections:
                if req.source == guideline.id:
                    await guideline_store.read_guideline(
                        guideline_set=agent_id,
                        guideline_id=req.target,
                    )
                elif req.target == guideline.id:
                    await guideline_store.read_guideline(
                        guideline_set=agent_id,
                        guideline_id=req.source,
                    )
                else:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Neither source ID '{req.source}' nor target ID '{req.target}' match the provided guideline ID '{guideline_id}'.",
                    )

                await guideline_connection_store.create_connection(
                    source=req.source,
                    target=req.target,
                    kind=connection_kind_dto_to_connection_kind(req.kind),
                )

        connections = await mc.get_guideline_connections(agent_id, guideline_id, indirect=False)

        if request.removed_connections:
            for id in request.removed_connections:
                if connection_to_remove := next(
                    iter([c for c, _ in connections if id in [c.source.id, c.target.id]])
                ):
                    await guideline_connection_store.delete_connection(connection_to_remove.id)
                else:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Connection ID '{id}' was not found.",
                    )

        return GuidelineWithConnectionsDTO(
            guideline_set=agent_id,
            id=guideline.id,
            predicate=guideline.content.predicate,
            action=guideline.content.action,
            connections=[
                GuidelineConnectionDTO(
                    id=connection.id,
                    source=GuidelineContentDTO(
                        id=connection.source.id,
                        predicate=connection.source.content.predicate,
                        action=connection.source.content.action,
                    ),
                    target=GuidelineContentDTO(
                        id=connection.target.id,
                        predicate=connection.target.content.predicate,
                        action=connection.target.content.action,
                    ),
                    kind=connection_kind_to_dto(connection.kind),
                    indirect=indirect,
                )
                for connection, indirect in await mc.get_guideline_connections(
                    agent_id, guideline_id, True
                )
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
