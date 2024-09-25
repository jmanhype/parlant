from fastapi import APIRouter, status
from typing import Optional

from emcie.server.core.agents import AgentId
from emcie.server.core.common import DefaultBaseModel
from emcie.server.core.terminology import TermUpdateParams, TerminologyStore, TermId


class CreateTermRequest(DefaultBaseModel):
    agent_id: AgentId
    name: str
    description: str
    synonyms: Optional[list[str]] = []


class TermDTO(DefaultBaseModel):
    term_id: TermId
    name: str
    description: str
    synonyms: Optional[list[str]] = []


class ListTermsResponse(DefaultBaseModel):
    terms: list[TermDTO]


class PatchTermRequest(DefaultBaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    synonyms: Optional[list[str]] = None


class DeleteTermResponse(DefaultBaseModel):
    deleted_term_id: TermId


def create_router(
    terminology_store: TerminologyStore,
) -> APIRouter:
    router = APIRouter()

    @router.post("/", status_code=status.HTTP_201_CREATED)
    async def create_term(request: CreateTermRequest) -> TermDTO:
        term = await terminology_store.create_term(
            term_set=request.agent_id,
            name=request.name,
            description=request.description,
            synonyms=request.synonyms,
        )

        return TermDTO(
            term_id=term.id,
            name=term.name,
            description=term.description,
            synonyms=term.synonyms,
        )

    @router.get("/{agent_id}/{name}")
    async def read_term(agent_id: str, name: str) -> TermDTO:
        term = await terminology_store.read_term(term_set=agent_id, name=name)

        return TermDTO(
            term_id=term.id,
            name=term.name,
            description=term.description,
            synonyms=term.synonyms,
        )

    @router.get("/{agent_id}/")
    async def list_terms(agent_id: str) -> ListTermsResponse:
        terms = await terminology_store.list_terms(term_set=agent_id)

        return ListTermsResponse(
            terms=[
                TermDTO(
                    term_id=term.id,
                    name=term.name,
                    description=term.description,
                    synonyms=term.synonyms,
                )
                for term in terms
            ]
        )

    @router.patch("/agent_id={agent_id}/term_id={term_id}")
    async def patch_term(agent_id: str, term_id: str, request: PatchTermRequest) -> TermDTO:
        params: TermUpdateParams = {}
        if request.name:
            params["name"] = request.name
        if request.description:
            params["description"] = request.description
        if request.synonyms:
            params["synonyms"] = request.synonyms

        term = await terminology_store.update_term(
            term_set=agent_id,
            term_id=term_id,
            params=params,
        )

        return TermDTO(
            term_id=term.id,
            name=term.name,
            description=term.description,
            synonyms=term.synonyms,
        )

    @router.delete("/{agent_id}/{name}")
    async def delete_term(agent_id: str, name: str) -> DeleteTermResponse:
        deleted_term_id = await terminology_store.delete_term(term_set=agent_id, name=name)

        return DeleteTermResponse(deleted_term_id=deleted_term_id)

    return router
