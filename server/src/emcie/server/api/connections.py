from typing import Optional
from fastapi import APIRouter, status

from emcie.server.api.common import (
    ConnectionKindDTO,
    connection_kind_dto_to_connection_kind,
    connection_kind_to_dto,
)
from emcie.server.core.agents import AgentId
from emcie.server.core.guideline_connections import GuidelineConnectionId, GuidelineConnectionStore
from emcie.server.core.guidelines import GuidelineId
from emcie.server.core.common import DefaultBaseModel


class GuidelineConnectionDTO(DefaultBaseModel):
    id: GuidelineConnectionId
    source: GuidelineId
    target: GuidelineId
    kind: ConnectionKindDTO


class AddConnectionRequest(DefaultBaseModel):
    agent_id: AgentId
    source_guideline_id: GuidelineId
    target_guideline_id: GuidelineId
    kind: ConnectionKindDTO


class ListConnectionsResponse(DefaultBaseModel):
    connections: list[GuidelineConnectionDTO]


def create_router(
    guideline_connection_store: GuidelineConnectionStore,
) -> APIRouter:
    router = APIRouter()

    @router.post("/", status_code=status.HTTP_201_CREATED)
    async def add_connection(request: AddConnectionRequest) -> GuidelineConnectionDTO:
        connection_kind = connection_kind_dto_to_connection_kind(request.kind)

        connection = await guideline_connection_store.update_connection(
            source=request.source_guideline_id,
            target=request.target_guideline_id,
            kind=connection_kind,
        )

        return GuidelineConnectionDTO(
            id=connection.id,
            source=connection.source,
            target=connection.target,
            kind=request.kind,
        )

    @router.get("/")
    async def list_connections(
        source_guideline_id: Optional[GuidelineId] = None,
        target_guideline_id: Optional[GuidelineId] = None,
        indirect: bool = False,
    ) -> ListConnectionsResponse:
        connections = await guideline_connection_store.list_connections(
            indirect=indirect,
            source=source_guideline_id,
            target=target_guideline_id,
        )

        connection_dtos = [
            GuidelineConnectionDTO(
                id=conn.id,
                source=conn.source,
                target=conn.target,
                kind=connection_kind_to_dto(conn.kind),  # type: ignore
            )
            for conn in connections
        ]
        return ListConnectionsResponse(connections=connection_dtos)

    return router
