from itertools import chain
from typing import Optional, Sequence
from fastapi import APIRouter, HTTPException, status


from emcie.server.api.common import (
    ConnectionKindDTO,
    GuidelinePayloadDTO,
    GuidelineInvoiceDataDTO,
    ToolIdDTO,
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
    ConnectionKind,
    GuidelineConnectionId,
    GuidelineConnectionStore,
)
from emcie.server.core.guidelines import Guideline, GuidelineContent, GuidelineId, GuidelineStore
from emcie.server.core.guideline_tool_associations import (
    GuidelineToolAssociationId,
    GuidelineToolAssociationStore,
)
from emcie.server.core.mc import MC
from emcie.server.core.services.tools.service_registry import ServiceRegistry
from emcie.server.core.tools import ToolId


class GuidelineDTO(DefaultBaseModel):
    id: GuidelineId
    predicate: str
    action: str


class GuidelineConnectionDTO(DefaultBaseModel):
    id: GuidelineConnectionId
    source: GuidelineDTO
    target: GuidelineDTO
    kind: ConnectionKindDTO
    indirect: bool


class GuidelineWithConnectionsDTO(DefaultBaseModel):
    guideline: GuidelineDTO
    connections: Sequence[GuidelineConnectionDTO]


class GuidelineInvoiceDTO(DefaultBaseModel):
    payload: GuidelinePayloadDTO
    checksum: str
    approved: bool
    data: GuidelineInvoiceDataDTO
    error: Optional[str]


class CreateGuidelineRequest(DefaultBaseModel):
    invoices: Sequence[GuidelineInvoiceDTO]


class CreateGuidelinesResponse(DefaultBaseModel):
    items: list[GuidelineWithConnectionsDTO]


class DeleteGuidelineRequest(DefaultBaseModel):
    guideline_id: GuidelineId


class DeleteGuidelineResponse(DefaultBaseModel):
    guideline_id: GuidelineId


class ListGuidelinesResponse(DefaultBaseModel):
    guidelines: list[GuidelineDTO]


class GuidelineConnectionAdditionDTO(DefaultBaseModel):
    source: GuidelineId
    target: GuidelineId
    kind: ConnectionKindDTO


class GuidelineConnectionsPatchDTO(DefaultBaseModel):
    add: Optional[Sequence[GuidelineConnectionAdditionDTO]] = None
    remove: Optional[Sequence[GuidelineId]] = None


class PatchGuidelineRequest(DefaultBaseModel):
    connections: Optional[GuidelineConnectionsPatchDTO] = None


class GuidelineConnection(DefaultBaseModel):
    id: GuidelineConnectionId
    source: Guideline
    target: Guideline
    kind: ConnectionKind


class CreateGuidelineToolAssociationRequest(DefaultBaseModel):
    service_name: str
    tool_name: str


class GuidelineToolAssociationDTO(DefaultBaseModel):
    id: GuidelineToolAssociationId
    guideline_id: GuidelineId
    tool_id: ToolIdDTO


class CreateGuidelineToolAssociationResponse(DefaultBaseModel):
    guideline_tool_association: GuidelineToolAssociationDTO


class DeleteGuidelineToolAssociationResponse(DefaultBaseModel):
    guideline_tool_association: GuidelineToolAssociationDTO


def _invoice_dto_to_invoice(dto: GuidelineInvoiceDTO) -> Invoice:
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


def _invoice_data_dto_to_invoice_data(dto: GuidelineInvoiceDataDTO) -> InvoiceGuidelineData:
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
    service_registry: ServiceRegistry,
    guideline_tool_association_store: GuidelineToolAssociationStore,
) -> APIRouter:
    router = APIRouter()

    async def get_guideline_connections(
        guideline_set: str,
        guideline_id: GuidelineId,
        include_indirect: bool = True,
    ) -> Sequence[tuple[GuidelineConnection, bool]]:
        connections = [
            GuidelineConnection(
                id=c.id,
                source=await guideline_store.read_guideline(
                    guideline_set=guideline_set, guideline_id=c.source
                ),
                target=await guideline_store.read_guideline(
                    guideline_set=guideline_set, guideline_id=c.target
                ),
                kind=c.kind,
            )
            for c in chain(
                await guideline_connection_store.list_connections(
                    indirect=include_indirect, source=guideline_id
                ),
                await guideline_connection_store.list_connections(
                    indirect=include_indirect, target=guideline_id
                ),
            )
        ]

        return [(c, guideline_id not in [c.source.id, c.target.id]) for c in connections]

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
            items=[
                GuidelineWithConnectionsDTO(
                    guideline=GuidelineDTO(
                        id=guideline.id,
                        predicate=guideline.content.predicate,
                        action=guideline.content.action,
                    ),
                    connections=[
                        GuidelineConnectionDTO(
                            id=connection.id,
                            source=GuidelineDTO(
                                id=connection.source.id,
                                predicate=connection.source.content.predicate,
                                action=connection.source.content.action,
                            ),
                            target=GuidelineDTO(
                                id=connection.target.id,
                                predicate=connection.target.content.predicate,
                                action=connection.target.content.action,
                            ),
                            kind=connection_kind_to_dto(connection.kind),
                            indirect=indirect,
                        )
                        for connection, indirect in await get_guideline_connections(
                            guideline_set=agent_id,
                            guideline_id=guideline.id,
                            include_indirect=True,
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

        connections = await get_guideline_connections(
            guideline_set=agent_id,
            guideline_id=guideline_id,
            include_indirect=True,
        )

        return GuidelineWithConnectionsDTO(
            guideline=GuidelineDTO(
                id=guideline.id,
                predicate=guideline.content.predicate,
                action=guideline.content.action,
            ),
            connections=[
                GuidelineConnectionDTO(
                    id=connection.id,
                    source=GuidelineDTO(
                        id=connection.source.id,
                        predicate=connection.source.content.predicate,
                        action=connection.source.content.action,
                    ),
                    target=GuidelineDTO(
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
                GuidelineDTO(
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

        if request.connections and request.connections.add:
            for req in request.connections.add:
                if req.source == req.target:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail="A guideline cannot be connected to itself",
                    )
                elif req.source == guideline.id:
                    _ = await guideline_store.read_guideline(
                        guideline_set=agent_id,
                        guideline_id=req.target,
                    )
                elif req.target == guideline.id:
                    _ = await guideline_store.read_guideline(
                        guideline_set=agent_id,
                        guideline_id=req.source,
                    )
                else:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="The connection must specify the guideline at hand as either source or target",
                    )

                await guideline_connection_store.create_connection(
                    source=req.source,
                    target=req.target,
                    kind=connection_kind_dto_to_connection_kind(req.kind),
                )

        connections = await get_guideline_connections(
            agent_id,
            guideline_id,
            include_indirect=False,
        )

        if request.connections and request.connections.remove:
            for id in request.connections.remove:
                if found_connection := next(
                    (c for c, _ in connections if id in [c.source.id, c.target.id]), None
                ):
                    await guideline_connection_store.delete_connection(found_connection.id)
                else:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail="Only direct connections may be removed",
                    )

        return GuidelineWithConnectionsDTO(
            guideline=GuidelineDTO(
                id=guideline.id,
                predicate=guideline.content.predicate,
                action=guideline.content.action,
            ),
            connections=[
                GuidelineConnectionDTO(
                    id=connection.id,
                    source=GuidelineDTO(
                        id=connection.source.id,
                        predicate=connection.source.content.predicate,
                        action=connection.source.content.action,
                    ),
                    target=GuidelineDTO(
                        id=connection.target.id,
                        predicate=connection.target.content.predicate,
                        action=connection.target.content.action,
                    ),
                    kind=connection_kind_to_dto(connection.kind),
                    indirect=indirect,
                )
                for connection, indirect in await get_guideline_connections(
                    agent_id, guideline_id, True
                )
            ],
        )

    @router.delete("/{agent_id}/guidelines/{guideline_id}")
    async def delete_guideline(
        agent_id: AgentId,
        guideline_id: GuidelineId,
    ) -> DeleteGuidelineResponse:
        await guideline_store.delete_guideline(
            guideline_set=agent_id,
            guideline_id=guideline_id,
        )

        for c in chain(
            await guideline_connection_store.list_connections(indirect=False, source=guideline_id),
            await guideline_connection_store.list_connections(indirect=False, target=guideline_id),
        ):
            await guideline_connection_store.delete_connection(c.id)

        return DeleteGuidelineResponse(guideline_id=guideline_id)

    @router.post(
        "/{agent_id}/guidelines/{guideline_id}/guideline_tool_associations",
        status_code=status.HTTP_201_CREATED,
    )
    async def create_guideline_tool_association(
        guideline_id: GuidelineId,
        request: CreateGuidelineToolAssociationRequest,
    ) -> CreateGuidelineToolAssociationResponse:
        service = await service_registry.read_tool_service(request.service_name)
        _ = await service.read_tool(request.tool_name)

        association = await guideline_tool_association_store.create_association(
            guideline_id=guideline_id,
            tool_id=ToolId(
                service_name=request.service_name,
                tool_name=request.tool_name,
            ),
        )

        return CreateGuidelineToolAssociationResponse(
            guideline_tool_association=GuidelineToolAssociationDTO(
                id=association.id,
                guideline_id=association.guideline_id,
                tool_id=ToolIdDTO(
                    service_name=association.tool_id.service_name,
                    tool_name=association.tool_id.tool_name,
                ),
            )
        )

    @router.delete(
        "/{agent_id}/guidelines/{guideline_id}/guideline_tool_associations/{association_id}",
        status_code=status.HTTP_200_OK,
    )
    async def delete_guideline_tool_association(
        guideline_id: GuidelineId,
        association_id: GuidelineToolAssociationId,
    ) -> DeleteGuidelineToolAssociationResponse:
        association = await guideline_tool_association_store.read_association(association_id)

        if association.guideline_id != guideline_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Association does not belong to the specified guideline",
            )

        association = await guideline_tool_association_store.delete_association(association_id)

        return DeleteGuidelineToolAssociationResponse(
            guideline_tool_association=GuidelineToolAssociationDTO(
                id=association.id,
                guideline_id=association.guideline_id,
                tool_id=ToolIdDTO(
                    service_name=association.tool_id.service_name,
                    tool_name=association.tool_id.tool_name,
                ),
            )
        )

    return router
