# tests/test_style_guides.py
# Copyright 2024 Emcie Co Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# You may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import httpx
from lagom import Container
from pytest import raises
from fastapi import status

from parlant.core.agents import AgentId
from parlant.core.common import ItemNotFoundError
from parlant.core.style_guides import StyleGuideStore


async def test_that_a_style_guide_can_be_created(
    async_client: httpx.AsyncClient,
    agent_id: AgentId,
) -> None:
    request_data = {
        "invoices": [
            {
                "payload": {
                    "kind": "style_guide",
                    "style_guide": {
                        "content": {
                            "principle": "Be friendly and helpful",
                            "examples": [
                                {
                                    "before": [
                                        {
                                            "source": "ai_agent",
                                            "message": "Hello.",
                                        },
                                    ],
                                    "after": [
                                        {
                                            "source": "ai_agent",
                                            "message": "Hello there! How can I brighten your day?",
                                        },
                                    ],
                                    "violation": "No friendly tone in the 'before' example.",
                                }
                            ],
                        },
                        "coherence_check": True,
                        "operation": "add",
                    },
                },
                "checksum": "abc123",
                "approved": True,
                "data": {
                    "style_guide": {
                        "coherence_checks": [],
                    }
                },
                "error": None,
            }
        ]
    }

    response = await async_client.post(f"/agents/{agent_id}/style_guides", json=request_data)
    assert response.status_code == status.HTTP_201_CREATED

    items = response.json()["items"]
    assert len(items) == 1

    created_style_guide = items[0]
    assert created_style_guide["id"]
    assert created_style_guide["content"]["principle"] == "Be friendly and helpful"
    assert len(created_style_guide["content"]["examples"]) == 1


async def test_that_an_unapproved_invoice_is_rejected(
    async_client: httpx.AsyncClient,
    agent_id: AgentId,
) -> None:
    request_data = {
        "invoices": [
            {
                "payload": {
                    "kind": "style_guide",
                    "style_guide": {
                        "content": {
                            "principle": "Be extremely formal",
                            "examples": [],
                        },
                        "coherence_check": True,
                        "operation": "add",
                    },
                },
                "checksum": "abc123",
                "approved": False,
                "data": {
                    "style_guide": {
                        "coherence_checks": [],
                    }
                },
                "error": None,
            }
        ]
    }

    response = await async_client.post(f"/agents/{agent_id}/style_guides", json=request_data)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    resp_json = response.json()
    assert "detail" in resp_json
    assert resp_json["detail"] == "Unapproved invoice"


async def test_that_a_style_guide_can_be_read_by_id(
    async_client: httpx.AsyncClient,
    container: Container,
    agent_id: AgentId,
) -> None:
    style_guide_store = container[StyleGuideStore]

    stored_guide = await style_guide_store.create_style_guide(
        style_guide_set=agent_id,
        principle="Use comedic timing",
        examples=[],
    )

    response = await async_client.get(f"/agents/{agent_id}/style_guides/{stored_guide.id}")
    response.raise_for_status()

    returned_data = response.json()
    assert returned_data["id"] == stored_guide.id
    assert returned_data["content"]["principle"] == "Use comedic timing"


async def test_that_style_guides_can_be_listed_for_an_agent(
    async_client: httpx.AsyncClient,
    container: Container,
    agent_id: AgentId,
) -> None:
    style_guide_store = container[StyleGuideStore]

    first_style_guide = await style_guide_store.create_style_guide(
        style_guide_set=agent_id,
        principle="Whimsical approach",
        examples=[],
    )
    second_style_guide = await style_guide_store.create_style_guide(
        style_guide_set=agent_id,
        principle="Serious approach",
        examples=[],
    )

    response = await async_client.get(f"/agents/{agent_id}/style_guides")
    response.raise_for_status()

    listed = response.json()

    assert any(g["id"] == first_style_guide.id for g in listed)
    assert any(g["id"] == second_style_guide.id for g in listed)


async def test_that_a_style_guide_can_be_deleted(
    async_client: httpx.AsyncClient,
    container: Container,
    agent_id: AgentId,
) -> None:
    style_guide_store = container[StyleGuideStore]

    style_guide_to_delete = await style_guide_store.create_style_guide(
        style_guide_set=agent_id,
        principle="Delete me principle",
        examples=[],
    )

    delete_url = f"/agents/{agent_id}/style_guides/{style_guide_to_delete.id}"
    response = await async_client.delete(delete_url)
    response.raise_for_status()
    assert response.status_code == status.HTTP_204_NO_CONTENT

    with raises(ItemNotFoundError):
        await style_guide_store.read_style_guide(agent_id, style_guide_to_delete.id)
