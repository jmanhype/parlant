# Copyright 2024 Emcie Co Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

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


class TermUpdateParamsDTO(DefaultBaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    synonyms: Optional[list[str]] = None


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
    async def create_term(agent_id: AgentId, params: TermCreationParamsDTO) -> TermDTO:
        term = await glossary_store.create_term(
            term_set=agent_id,
            name=params.name,
            description=params.description,
            synonyms=params.synonyms,
        )

        return TermDTO(
            id=term.id,
            name=term.name,
            description=term.description,
            synonyms=term.synonyms,
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
    async def list_terms(agent_id: AgentId) -> list[TermDTO]:
        terms = await glossary_store.list_terms(term_set=agent_id)

        return [
            TermDTO(
                id=term.id,
                name=term.name,
                description=term.description,
                synonyms=term.synonyms,
            )
            for term in terms
        ]

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
        status_code=status.HTTP_204_NO_CONTENT,
        operation_id="delete_term",
        **apigen_config(group_name=API_GROUP, method_name="delete_term"),
    )
    async def delete_term(
        agent_id: str,
        term_id: TermId,
    ) -> None:
        await glossary_store.read_term(term_set=agent_id, term_id=term_id)

        await glossary_store.delete_term(term_set=agent_id, term_id=term_id)

    return router
