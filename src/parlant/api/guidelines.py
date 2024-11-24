from collections import defaultdict
from itertools import chain
from typing import Optional, Sequence
from fastapi import APIRouter, HTTPException, status

from parlant.api.common import (
    ConnectionKindDTO,
    InvoiceDataDTO,
    PayloadKindDTO,
    ToolIdDTO,
    apigen_config,
    connection_kind_dto_to_connection_kind,
    connection_kind_to_dto,
)
from parlant.api.index import InvoiceDTO
from parlant.core.agents import AgentId
from parlant.core.common import DefaultBaseModel
from parlant.core.evaluations import (
    CoherenceCheck,
    ConnectionProposition,
    GuidelinePayload,
    Invoice,
    InvoiceGuidelineData,
    PayloadKind,
)
from parlant.core.guideline_connections import (
    ConnectionKind,
    GuidelineConnectionId,
    GuidelineConnectionStore,
)
from parlant.core.guidelines import Guideline, GuidelineContent, GuidelineId, GuidelineStore
from parlant.core.guideline_tool_associations import (
    GuidelineToolAssociationId,
    GuidelineToolAssociationStore,
)
from parlant.core.application import Application
from parlant.core.services.tools.service_registry import ServiceRegistry
from parlant.core.tools import ToolId

API_GROUP = "guidelines"


class GuidelineDTO(DefaultBaseModel):
    id: GuidelineId
    condition: str
    action: str


class GuidelineConnectionDTO(DefaultBaseModel):
    id: GuidelineConnectionId
    source: GuidelineDTO
    target: GuidelineDTO
    kind: ConnectionKindDTO
    indirect: bool


class GuidelineToolAssociationDTO(DefaultBaseModel):
    id: GuidelineToolAssociationId
    guideline_id: GuidelineId
    tool_id: ToolIdDTO


class GuidelineWithConnectionsAndToolAssociationsDTO(DefaultBaseModel):
    guideline: GuidelineDTO
    connections: Sequence[GuidelineConnectionDTO]
    tool_associations: Sequence[GuidelineToolAssociationDTO]


class GuidelineCreationParamsDTO(DefaultBaseModel):
    invoices: Sequence[InvoiceDTO]


class GuidelineCreationResult(DefaultBaseModel):
    items: list[GuidelineWithConnectionsAndToolAssociationsDTO]


class GuidelineConnectionAdditionDTO(DefaultBaseModel):
    source: GuidelineId
    target: GuidelineId
    kind: ConnectionKindDTO


class GuidelineConnectionUpdateParamsDTO(DefaultBaseModel):
    add: Optional[Sequence[GuidelineConnectionAdditionDTO]] = None
    remove: Optional[Sequence[GuidelineId]] = None


class GuidelineToolAssociationUpdateParamsDTO(DefaultBaseModel):
    add: Optional[Sequence[ToolIdDTO]] = None
    remove: Optional[Sequence[ToolIdDTO]] = None


class GuidelineUpdateParamsDTO(DefaultBaseModel):
    connections: Optional[GuidelineConnectionUpdateParamsDTO] = None
    tool_associations: Optional[GuidelineToolAssociationUpdateParamsDTO] = None


class GuidelineConnection(DefaultBaseModel):
    id: GuidelineConnectionId
    source: Guideline
    target: Guideline
    kind: ConnectionKind


def _invoice_dto_to_invoice(dto: InvoiceDTO) -> Invoice:
    if dto.payload.kind != PayloadKindDTO.GUIDELINE:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Only guideline invoices are supported here",
        )

    if not dto.approved:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Unapproved invoice",
        )

    if not dto.payload.guideline:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Missing guideline payload",
        )

    payload = GuidelinePayload(
        content=GuidelineContent(
            condition=dto.payload.guideline.content.condition,
            action=dto.payload.guideline.content.action,
        ),
        operation=dto.payload.guideline.operation.value,
        coherence_check=dto.payload.guideline.coherence_check,
        connection_proposition=dto.payload.guideline.connection_proposition,
        updated_id=dto.payload.guideline.updated_id,
    )

    kind = PayloadKind.GUIDELINE

    if not dto.data:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Missing invoice data",
        )

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


def _invoice_data_dto_to_invoice_data(dto: InvoiceDataDTO) -> InvoiceGuidelineData:
    if not dto.guideline:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Missing guideline invoice data",
        )

    try:
        coherence_checks = [
            CoherenceCheck(
                kind=check.kind.value,
                first=GuidelineContent(condition=check.first.condition, action=check.first.action),
                second=GuidelineContent(
                    condition=check.second.condition, action=check.second.action
                ),
                issue=check.issue,
                severity=check.severity,
            )
            for check in dto.guideline.coherence_checks
        ]

        if dto.guideline.connection_propositions:
            connection_propositions = [
                ConnectionProposition(
                    check_kind=prop.check_kind.value,
                    source=GuidelineContent(
                        condition=prop.source.condition, action=prop.source.action
                    ),
                    target=GuidelineContent(
                        condition=prop.target.condition, action=prop.target.action
                    ),
                    connection_kind=connection_kind_dto_to_connection_kind(prop.connection_kind),
                )
                for prop in dto.guideline.connection_propositions
            ]
        else:
            connection_propositions = None

        return InvoiceGuidelineData(
            coherence_checks=coherence_checks, connection_propositions=connection_propositions
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid invoice guideline data",
        )


def create_router(
    application: Application,
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

    @router.post(
        "/{agent_id}/guidelines",
        status_code=status.HTTP_201_CREATED,
        operation_id="create_guidelines",
        **apigen_config(group_name=API_GROUP, method_name="create"),
    )
    async def create_guidelines(
        agent_id: AgentId,
        params: GuidelineCreationParamsDTO,
    ) -> GuidelineCreationResult:
        invoices = [_invoice_dto_to_invoice(i) for i in params.invoices]

        guideline_ids = set(
            await application.create_guidelines(
                guideline_set=agent_id,
                invoices=invoices,
            )
        )

        guidelines = [
            await guideline_store.read_guideline(guideline_set=agent_id, guideline_id=id)
            for id in guideline_ids
        ]

        tool_associations = defaultdict(list)
        for association in await guideline_tool_association_store.list_associations():
            if association.guideline_id in guideline_ids:
                tool_associations[association.guideline_id].append(
                    GuidelineToolAssociationDTO(
                        id=association.id,
                        guideline_id=association.guideline_id,
                        tool_id=ToolIdDTO(
                            service_name=association.tool_id.service_name,
                            tool_name=association.tool_id.tool_name,
                        ),
                    )
                )

        return GuidelineCreationResult(
            items=[
                GuidelineWithConnectionsAndToolAssociationsDTO(
                    guideline=GuidelineDTO(
                        id=guideline.id,
                        condition=guideline.content.condition,
                        action=guideline.content.action,
                    ),
                    connections=[
                        GuidelineConnectionDTO(
                            id=connection.id,
                            source=GuidelineDTO(
                                id=connection.source.id,
                                condition=connection.source.content.condition,
                                action=connection.source.content.action,
                            ),
                            target=GuidelineDTO(
                                id=connection.target.id,
                                condition=connection.target.content.condition,
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
                    tool_associations=tool_associations.get(guideline.id, []),
                )
                for guideline in guidelines
            ]
        )

    @router.get(
        "/{agent_id}/guidelines/{guideline_id}",
        operation_id="read_guideline",
        **apigen_config(group_name=API_GROUP, method_name="retrieve"),
    )
    async def read_guideline(
        agent_id: AgentId,
        guideline_id: GuidelineId,
    ) -> GuidelineWithConnectionsAndToolAssociationsDTO:
        guideline = await guideline_store.read_guideline(
            guideline_set=agent_id, guideline_id=guideline_id
        )

        connections = await get_guideline_connections(
            guideline_set=agent_id,
            guideline_id=guideline_id,
            include_indirect=True,
        )

        return GuidelineWithConnectionsAndToolAssociationsDTO(
            guideline=GuidelineDTO(
                id=guideline.id,
                condition=guideline.content.condition,
                action=guideline.content.action,
            ),
            connections=[
                GuidelineConnectionDTO(
                    id=connection.id,
                    source=GuidelineDTO(
                        id=connection.source.id,
                        condition=connection.source.content.condition,
                        action=connection.source.content.action,
                    ),
                    target=GuidelineDTO(
                        id=connection.target.id,
                        condition=connection.target.content.condition,
                        action=connection.target.content.action,
                    ),
                    kind=connection_kind_to_dto(connection.kind),
                    indirect=indirect,
                )
                for connection, indirect in connections
            ],
            tool_associations=[
                GuidelineToolAssociationDTO(
                    id=a.id,
                    guideline_id=a.guideline_id,
                    tool_id=ToolIdDTO(
                        service_name=a.tool_id.service_name,
                        tool_name=a.tool_id.tool_name,
                    ),
                )
                for a in await guideline_tool_association_store.list_associations()
                if a.guideline_id == guideline_id
            ],
        )

    @router.get(
        "/{agent_id}/guidelines",
        operation_id="list_guidelines",
        **apigen_config(group_name=API_GROUP, method_name="list"),
    )
    async def list_guidelines(agent_id: AgentId) -> list[GuidelineDTO]:
        guidelines = await guideline_store.list_guidelines(guideline_set=agent_id)

        return [
            GuidelineDTO(
                id=guideline.id,
                condition=guideline.content.condition,
                action=guideline.content.action,
            )
            for guideline in guidelines
        ]

    @router.patch(
        "/{agent_id}/guidelines/{guideline_id}",
        operation_id="update_guideline",
        **apigen_config(group_name=API_GROUP, method_name="update"),
    )
    async def update_guideline(
        agent_id: AgentId,
        guideline_id: GuidelineId,
        params: GuidelineUpdateParamsDTO,
    ) -> GuidelineWithConnectionsAndToolAssociationsDTO:
        guideline = await guideline_store.read_guideline(
            guideline_set=agent_id,
            guideline_id=guideline_id,
        )

        if params.connections and params.connections.add:
            for req in params.connections.add:
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

        if params.connections and params.connections.remove:
            for id in params.connections.remove:
                if found_connection := next(
                    (c for c, _ in connections if id in [c.source.id, c.target.id]), None
                ):
                    await guideline_connection_store.delete_connection(found_connection.id)
                else:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail="Only direct connections may be removed",
                    )

        if params.tool_associations and params.tool_associations.add:
            for tool_id_dto in params.tool_associations.add:
                service_name = tool_id_dto.service_name
                tool_name = tool_id_dto.tool_name

                service = await service_registry.read_tool_service(service_name)
                _ = await service.read_tool(tool_name)

                await guideline_tool_association_store.create_association(
                    guideline_id=guideline_id,
                    tool_id=ToolId(service_name=service_name, tool_name=tool_name),
                )

        if params.tool_associations and params.tool_associations.remove:
            associations = await guideline_tool_association_store.list_associations()

            for tool_id_dto in params.tool_associations.remove:
                if association := next(
                    (
                        assoc
                        for assoc in associations
                        if assoc.tool_id.service_name == tool_id_dto.service_name
                        and assoc.tool_id.tool_name == tool_id_dto.tool_name
                    ),
                    None,
                ):
                    await guideline_tool_association_store.delete_association(association.id)
                else:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Tool association not found for service '{tool_id_dto.service_name}' and tool '{tool_id_dto.tool_name}'",
                    )

        return GuidelineWithConnectionsAndToolAssociationsDTO(
            guideline=GuidelineDTO(
                id=guideline.id,
                condition=guideline.content.condition,
                action=guideline.content.action,
            ),
            connections=[
                GuidelineConnectionDTO(
                    id=connection.id,
                    source=GuidelineDTO(
                        id=connection.source.id,
                        condition=connection.source.content.condition,
                        action=connection.source.content.action,
                    ),
                    target=GuidelineDTO(
                        id=connection.target.id,
                        condition=connection.target.content.condition,
                        action=connection.target.content.action,
                    ),
                    kind=connection_kind_to_dto(connection.kind),
                    indirect=indirect,
                )
                for connection, indirect in await get_guideline_connections(
                    agent_id, guideline_id, True
                )
            ],
            tool_associations=[
                GuidelineToolAssociationDTO(
                    id=a.id,
                    guideline_id=a.guideline_id,
                    tool_id=ToolIdDTO(
                        service_name=a.tool_id.service_name,
                        tool_name=a.tool_id.tool_name,
                    ),
                )
                for a in await guideline_tool_association_store.list_associations()
                if a.guideline_id == guideline_id
            ],
        )

    @router.delete(
        "/{agent_id}/guidelines/{guideline_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        operation_id="delete_guideline",
        **apigen_config(group_name=API_GROUP, method_name="delete"),
    )
    async def delete_guideline(
        agent_id: AgentId,
        guideline_id: GuidelineId,
    ) -> None:
        await guideline_store.read_guideline(
            guideline_set=agent_id,
            guideline_id=guideline_id,
        )

        await guideline_store.delete_guideline(
            guideline_set=agent_id,
            guideline_id=guideline_id,
        )

        for c in chain(
            await guideline_connection_store.list_connections(indirect=False, source=guideline_id),
            await guideline_connection_store.list_connections(indirect=False, target=guideline_id),
        ):
            await guideline_connection_store.delete_connection(c.id)

        for associastion in await guideline_tool_association_store.list_associations():
            if associastion.guideline_id == guideline_id:
                await guideline_tool_association_store.delete_association(associastion.id)

    return router
