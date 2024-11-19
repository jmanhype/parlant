from fastapi import APIRouter, status
from typing import Optional

from parlant.api.common import apigen_config
from parlant.core.agents import AgentId
from parlant.core.common import DefaultBaseModel
from parlant.core.glossary import TermUpdateParams, GlossaryStore, TermId

API_GROUP = "glossary"


class TermCreationParamsDTO(DefaultBaseModel):
    name: str
    description: str
    synonyms: Optional[list[str]] = []


class TermDTO(DefaultBaseModel):
    id: TermId
    name: str
    description: str
    synonyms: list[str] = []


class CreateTermResponse(DefaultBaseModel):
    term: TermDTO


class TermListResponse(DefaultBaseModel):
    terms: list[TermDTO]


class TermUpdateParamsDTO(DefaultBaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    synonyms: Optional[list[str]] = None


class TermDeletionResponse(DefaultBaseModel):
    term_id: TermId


def create_router(
    glossary_store: GlossaryStore,
) -> APIRouter:
    router = APIRouter()

    @router.post(
        "/{agent_id}/terms",
        status_code=status.HTTP_201_CREATED,
        operation_id="create_term",
        **apigen_config(group_name=API_GROUP, method_name="create_term"),
    )
    async def create_term(agent_id: AgentId, params: TermCreationParamsDTO) -> CreateTermResponse:
        term = await glossary_store.create_term(
            term_set=agent_id,
            name=params.name,
            description=params.description,
            synonyms=params.synonyms,
        )

        return CreateTermResponse(
            term=TermDTO(
                id=term.id,
                name=term.name,
                description=term.description,
                synonyms=term.synonyms,
            )
        )

    @router.get(
        "/{agent_id}/terms/{term_id}",
        operation_id="read_term",
        **apigen_config(group_name=API_GROUP, method_name="retrieve_term"),
    )
    async def read_term(agent_id: AgentId, term_id: TermId) -> TermDTO:
        term = await glossary_store.read_term(term_set=agent_id, term_id=term_id)

        return TermDTO(
            id=term.id,
            name=term.name,
            description=term.description,
            synonyms=term.synonyms,
        )

    @router.get(
        "/{agent_id}/terms",
        operation_id="list_terms",
        **apigen_config(group_name=API_GROUP, method_name="list_terms"),
    )
    async def list_terms(agent_id: AgentId) -> TermListResponse:
        terms = await glossary_store.list_terms(term_set=agent_id)

        return TermListResponse(
            terms=[
                TermDTO(
                    id=term.id,
                    name=term.name,
                    description=term.description,
                    synonyms=term.synonyms,
                )
                for term in terms
            ]
        )

    @router.patch(
        "/{agent_id}/terms/{term_id}",
        operation_id="update_term",
        **apigen_config(group_name=API_GROUP, method_name="update_term"),
    )
    async def update_term(
        agent_id: AgentId,
        term_id: TermId,
        params: TermUpdateParamsDTO,
    ) -> TermDTO:
        def from_dto(dto: TermUpdateParamsDTO) -> TermUpdateParams:
            params: TermUpdateParams = {}

            if dto.name:
                params["name"] = dto.name
            if dto.description:
                params["description"] = dto.description
            if dto.synonyms:
                params["synonyms"] = dto.synonyms

            return params

        term = await glossary_store.update_term(
            term_set=agent_id,
            term_id=term_id,
            params=from_dto(params),
        )

        return TermDTO(
            id=term.id,
            name=term.name,
            description=term.description,
            synonyms=term.synonyms,
        )

    @router.delete(
        "/{agent_id}/terms/{term_id}",
        operation_id="delete_term",
        **apigen_config(group_name=API_GROUP, method_name="delete_term"),
    )
    async def delete_term(agent_id: str, term_id: TermId) -> TermDeletionResponse:
        deleted_term_id = await glossary_store.delete_term(term_set=agent_id, term_id=term_id)
        return TermDeletionResponse(term_id=deleted_term_id)

    return router
