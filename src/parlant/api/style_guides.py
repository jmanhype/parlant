# # api/style_guides.py
# # Copyright 2024 Emcie Co Ltd.
# #
# # Licensed under the Apache License, Version 2.0 (the "License");
# # you may not use this file except in compliance with the License.
# # You may obtain a copy of the License at
# #
# #     http://www.apache.org/licenses/LICENSE-2.0
# #
# # Unless required by applicable law or agreed to in writing, software
# # distributed under the License is distributed on an "AS IS" BASIS,
# # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# # See the License for the specific language governing permissions and
# # limitations under the License.

# from dataclasses import dataclass
# from typing import Annotated, Optional, Sequence, TypeAlias
# from fastapi import APIRouter, HTTPException, Path, status

# from parlant.api import agents, common
# from parlant.api.common import (
#     ExampleJson,
#     InvoiceDataDTO,
#     PayloadKindDTO,
#     apigen_config,
# )
# from parlant.api.index import InvoiceDTO
# from parlant.core.application import Application
# from parlant.core.common import DefaultBaseModel, ItemNotFoundError
# from parlant.core.evaluations import (
#     Invoice,
#     PayloadKind,
#     StyleGuidePayload,
#     CoherenceCheck,      # if you have style guide–related checks
#     InvoiceStyleGuideData,
# )
# from parlant.core.style_guides import (
#     StyleGuideStore,
#     StyleGuideId,
#     StyleGuide,
#     StyleGuideExample,
#     StyleGuideEvent,
# )
# from parlant.core.services.tools.service_registry import ServiceRegistry

# ############################################
# # Example DTOs for Style Guide
# ############################################

# # Example style guide examples
# style_guide_dto_example: ExampleJson = {
#     "id": "sg_123xyz",
#     "principle": "Be friendly, casual, and helpful",
#     "examples": [
#         {
#             "before": [
#                 {"source": {"id": "system"}, "message": "Your request is denied."}
#             ],
#             "after": [
#                 {"source": {"id": "system"}, "message": "We can’t do that now, but let's see what else might help!"}
#             ],
#             "violation": "The 'before' message is abrupt and lacking empathy.",
#         }
#     ],
# }


# StyleGuideIdPath: TypeAlias = Annotated[
#     StyleGuideId,
#     Path(
#         description="Unique identifier for the style guide",
#         examples=["sg_abc123"],
#     ),
# ]


# class StyleGuideExampleEventDTO(DefaultBaseModel):
#     """Represents a single event, including its source and message."""

#     source: dict  # or a more specific type if you'd like
#     message: str


# class StyleGuideExampleDTO(DefaultBaseModel):
#     """
#     Illustrates one 'before' vs. 'after' scenario within a style guide,
#     plus a 'violation' explanation for why 'before' is bad.
#     """

#     before: Sequence[StyleGuideExampleEventDTO]
#     after: Sequence[StyleGuideExampleEventDTO]
#     violation: str


# class StyleGuideDTO(
#     DefaultBaseModel,
#     json_schema_extra={"example": style_guide_dto_example},
# ):
#     """
#     A simplified representation of a StyleGuide with an ID, principle,
#     and one or more examples.
#     """

#     id: StyleGuideIdPath
#     principle: str
#     examples: Sequence[StyleGuideExampleDTO]


# ############################################
# # Style Guide Creation from Invoices
# ############################################

# # For invoice-based creation, we define request/response structures:
# style_guide_creation_params_example: ExampleJson = {
#     "invoices": [
#         {
#             "payload": {
#                 "kind": "style_guide",
#                 "style_guide": {
#                     "principle": "Avoid negative or abrupt phrasing",
#                     "examples": [
#                         {
#                             "before": [
#                                 {"source": {"id": "editor"}, "message": "Denied."}
#                             ],
#                             "after": [
#                                 {"source": {"id": "editor"}, "message": "We’re unable to do that. Let’s find another option."}
#                             ],
#                             "violation": "The 'before' text sounds blunt and unfriendly.",
#                         }
#                     ],
#                 },
#             },
#             "data": {
#                 "style_guide": {
#                     "coherence_checks": [],
#                 }
#             },
#             "approved": True,
#             "checksum": "abc123",
#             "error": None,
#         }
#     ]
# }


# class StyleGuideCreationParamsDTO(
#     DefaultBaseModel,
#     json_schema_extra={"example": style_guide_creation_params_example},
# ):
#     """Request for creating style guides from evaluation invoices."""

#     invoices: Sequence[InvoiceDTO]


# style_guide_creation_result_example: ExampleJson = {
#     "items": [
#         {
#             "id": "sg_123xyz",
#             "principle": "Be friendly, casual, and helpful",
#             "examples": [
#                 {
#                     "before": [
#                         {"source": {"id": "system"}, "message": "Your request is denied."}
#                     ],
#                     "after": [
#                         {"source": {"id": "system"}, "message": "We can’t do that now, but let's see what else might help!"}
#                     ],
#                     "violation": "The 'before' message is abrupt and lacking empathy.",
#                 }
#             ],
#         }
#     ]
# }


# class StyleGuideCreationResultDTO(
#     DefaultBaseModel,
#     json_schema_extra={"example": style_guide_creation_result_example},
# ):
#     """A collection of style guides created from the provided invoices."""

#     items: Sequence[StyleGuideDTO]


# ############################################
# # Helper to parse InvoiceDTO → Invoice (domain)
# ############################################

# def _invoice_dto_to_invoice(dto: InvoiceDTO) -> Invoice:
#     """
#     Convert the StyleGuide-relevant portion of an InvoiceDTO into
#     a domain Invoice with a `StyleGuidePayload`.
#     """
#     if dto.payload.kind != PayloadKindDTO.STYLE_GUIDE:
#         raise HTTPException(
#             status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
#             detail="Only style_guide invoices are supported here",
#         )

#     if not dto.approved:
#         raise HTTPException(
#             status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
#             detail="Unapproved invoice",
#         )

#     if not dto.payload.style_guide:
#         raise HTTPException(
#             status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
#             detail="Missing style_guide payload",
#         )

#     # Build a domain payload (StyleGuidePayload).
#     payload = StyleGuidePayload(
#         principle=dto.payload.style_guide.principle,
#         examples=[
#             StyleGuideExample(
#                 before=[StyleGuideEvent(source=e.source, message=e.message) for e in ex.before],
#                 after=[StyleGuideEvent(source=e.source, message=e.message) for e in ex.after],
#                 violation=ex.violation,
#             )
#             for ex in dto.payload.style_guide.examples
#         ],
#     )

#     # Any domain-specific logic for a style guide goes here.
#     # For example, we might not have an "operation" or "updated_id" like guidelines might.

#     # Handle 'data' => typically includes coherence checks for style guides
#     data = _invoice_data_dto_to_invoice_data(dto.data) if dto.data else None

#     return Invoice(
#         kind=PayloadKind.STYLE_GUIDE,
#         payload=payload,   # domain
#         checksum=dto.checksum,
#         state_version="",  # not used, but required by domain
#         approved=dto.approved,
#         data=data,
#         error=dto.error,
#     )


# def _invoice_data_dto_to_invoice_data(dto: InvoiceDataDTO) -> InvoiceStyleGuideData:
#     """
#     Convert the InvoiceDataDTO → domain-specific InvoiceStyleGuideData.
#     Raise errors if data is missing or malformed.
#     """
#     if not dto.style_guide:
#         raise HTTPException(
#             status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
#             detail="Missing style_guide invoice data",
#         )

#     # Example coherence checks for style guides
#     try:
#         coherence_checks = []
#         for check in dto.style_guide.coherence_checks:
#             # e.g., CoherenceCheck -> with style guide content
#             coherence_checks.append(
#                 CoherenceCheck(
#                     kind=check.kind.value,
#                     first=None,  # you can store these if you want
#                     second=None,
#                     issue=check.issue,
#                     severity=check.severity,
#                 )
#             )
#         return InvoiceStyleGuideData(coherence_checks=coherence_checks)
#     except Exception:
#         raise HTTPException(
#             status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
#             detail="Invalid invoice style_guide data",
#         )


# ############################################
# # The Router
# ############################################

# def create_router(
#     application: Application,
#     style_guide_store: StyleGuideStore,
#     service_registry: ServiceRegistry,  # if needed for additional logic
# ) -> APIRouter:
#     router = APIRouter()

#     #
#     # 1) Create style guides (from invoices)
#     #
#     @router.post(
#         "/{agent_id}/style_guides",
#         status_code=status.HTTP_201_CREATED,
#         operation_id="create_style_guides",
#         response_model=StyleGuideCreationResultDTO,
#         responses={
#             status.HTTP_201_CREATED: {
#                 "description": "Style guides successfully created. Returns the created style guides.",
#                 "content": common.example_json_content(style_guide_creation_result_example),
#             },
#             status.HTTP_404_NOT_FOUND: {"description": "Agent not found"},
#             status.HTTP_422_UNPROCESSABLE_ENTITY: {
#                 "description": "Validation error in request parameters"
#             },
#         },
#         **apigen_config(group_name="style_guides", method_name="create"),
#     )
#     async def create_style_guides(
#         agent_id: agents.AgentIdPath,
#         params: StyleGuideCreationParamsDTO,
#     ) -> StyleGuideCreationResultDTO:
#         """
#         Creates new style guides from the provided invoices.

#         Similar to how guidelines are created, but specifically for style guides.
#         Invoices come from the client calling `create_evaluation` (or similar).
#         """
#         # Convert each invoice DTO → domain Invoice
#         invoices = [_invoice_dto_to_invoice(i) for i in params.invoices]

#         # Use the application logic to persist them
#         style_guide_ids = await application.create_style_guides(
#             style_guide_set=agent_id,
#             invoices=invoices,
#         )

#         # Retrieve the newly created style guides
#         created_style_guides = [
#             await style_guide_store.read_style_guide(style_guide_set=agent_id, style_guide_id=sg_id)
#             for sg_id in style_guide_ids
#         ]

#         # Convert domain → StyleGuideDTO
#         return StyleGuideCreationResultDTO(
#             items=[
#                 StyleGuideDTO(
#                     id=sg.id,
#                     principle=sg.principle,
#                     examples=[
#                         StyleGuideExampleDTO(
#                             before=[
#                                 StyleGuideExampleEventDTO(source=e.source, message=e.message)
#                                 for e in ex.before
#                             ],
#                             after=[
#                                 StyleGuideExampleEventDTO(source=e.source, message=e.message)
#                                 for e in ex.after
#                             ],
#                             violation=ex.violation,
#                         )
#                         for ex in sg.examples
#                     ],
#                 )
#                 for sg in created_style_guides
#             ]
#         )

#     #
#     # 2) Read a single style guide
#     #
#     @router.get(
#         "/{agent_id}/style_guides/{style_guide_id}",
#         operation_id="read_style_guide",
#         response_model=StyleGuideDTO,
#         responses={
#             status.HTTP_200_OK: {
#                 "description": "Style guide details successfully retrieved.",
#                 "content": common.example_json_content(style_guide_dto_example),
#             },
#             status.HTTP_404_NOT_FOUND: {"description": "Style guide or agent not found"},
#         },
#         **apigen_config(group_name="style_guides", method_name="retrieve"),
#     )
#     async def read_style_guide(
#         agent_id: agents.AgentIdPath,
#         style_guide_id: StyleGuideIdPath,
#     ) -> StyleGuideDTO:
#         """
#         Retrieves the specified style guide by ID.
#         """
#         try:
#             style_guide = await style_guide_store.read_style_guide(
#                 style_guide_set=agent_id, style_guide_id=style_guide_id
#             )
#         except ItemNotFoundError:
#             raise HTTPException(
#                 status_code=status.HTTP_404_NOT_FOUND,
#                 detail=f"Style guide '{style_guide_id}' not found for agent '{agent_id}'.",
#             )

#         return StyleGuideDTO(
#             id=style_guide.id,
#             principle=style_guide.principle,
#             examples=[
#                 StyleGuideExampleDTO(
#                     before=[
#                         StyleGuideExampleEventDTO(source=e.source, message=e.message)
#                         for e in ex.before
#                     ],
#                     after=[
#                         StyleGuideExampleEventDTO(source=e.source, message=e.message)
#                         for e in ex.after
#                     ],
#                     violation=ex.violation,
#                 )
#                 for ex in style_guide.examples
#             ],
#         )

#     #
#     # 3) List all style guides
#     #
#     @router.get(
#         "/{agent_id}/style_guides",
#         operation_id="list_style_guides",
#         response_model=Sequence[StyleGuideDTO],
#         responses={
#             status.HTTP_200_OK: {
#                 "description": "List of all style guides for the specified agent",
#                 "content": common.example_json_content([style_guide_dto_example]),
#             },
#             status.HTTP_404_NOT_FOUND: {"description": "Agent not found"},
#         },
#         **apigen_config(group_name="style_guides", method_name="list"),
#     )
#     async def list_style_guides(
#         agent_id: agents.AgentIdPath,
#     ) -> Sequence[StyleGuideDTO]:
#         """
#         Lists all style guides for the specified agent.

#         Returns an empty list if none exist. Returned in no guaranteed order.
#         """
#         style_guides = await style_guide_store.list_style_guides(style_guide_set=agent_id)
#         return [
#             StyleGuideDTO(
#                 id=sg.id,
#                 principle=sg.principle,
#                 examples=[
#                     StyleGuideExampleDTO(
#                         before=[
#                             StyleGuideExampleEventDTO(source=e.source, message=e.message)
#                             for e in ex.before
#                         ],
#                         after=[
#                             StyleGuideExampleEventDTO(source=e.source, message=e.message)
#                             for e in ex.after
#                         ],
#                         violation=ex.violation,
#                     )
#                     for ex in sg.examples
#                 ],
#             )
#             for sg in style_guides
#         ]

#     #
#     # 4) Update a style guide
#     #
#     @router.patch(
#         "/{agent_id}/style_guides/{style_guide_id}",
#         operation_id="update_style_guide",
#         response_model=StyleGuideDTO,
#         responses={
#             status.HTTP_200_OK: {
#                 "description": "Style guide successfully updated. Returns the updated style guide.",
#                 "content": common.example_json_content(style_guide_dto_example),
#             },
#             status.HTTP_404_NOT_FOUND: {
#                 "description": "Style guide or agent not found"
#             },
#             status.HTTP_422_UNPROCESSABLE_ENTITY: {
#                 "description": "Validation error in update parameters"
#             },
#         },
#         **apigen_config(group_name="style_guides", method_name="update"),
#     )
#     async def update_style_guide(
#         agent_id: agents.AgentIdPath,
#         style_guide_id: StyleGuideIdPath,
#         params: "UpdateStyleGuideParamsDTO",  # or something similar
#     ) -> StyleGuideDTO:
#         """
#         Updates the specified style guide's principle and/or examples.
#         Only provided fields will be updated.
#         """
#         # (1) Confirm existence
#         try:
#             existing = await style_guide_store.read_style_guide(
#                 style_guide_set=agent_id, style_guide_id=style_guide_id
#             )
#         except ItemNotFoundError:
#             raise HTTPException(
#                 status_code=status.HTTP_404_NOT_FOUND,
#                 detail=f"Style guide '{style_guide_id}' not found for agent '{agent_id}'.",
#             )

#         # (2) Build update params
#         update_params = {}
#         if hasattr(params, "principle") and params.principle is not None:
#             update_params["principle"] = params.principle
#         if hasattr(params, "examples") and params.examples is not None:
#             domain_examples = []
#             for ex_dto in params.examples:
#                 before = [StyleGuideEvent(source=e.source, message=e.message) for e in ex_dto.before]
#                 after = [StyleGuideEvent(source=e.source, message=e.message) for e in ex_dto.after]
#                 domain_examples.append(StyleGuideExample(before=before, after=after, violation=ex_dto.violation))
#             update_params["examples"] = domain_examples

#         # (3) Persist
#         try:
#             updated_sg = await style_guide_store.update_style_guide(
#                 style_guide_set=agent_id,
#                 style_guide_id=style_guide_id,
#                 params=update_params,
#             )
#         except ItemNotFoundError:  # in case it was removed in between
#             raise HTTPException(
#                 status_code=status.HTTP_404_NOT_FOUND,
#                 detail=f"Style guide '{style_guide_id}' not found for agent '{agent_id}'.",
#             )
#         except Exception as exc:
#             raise HTTPException(
#                 status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
#                 detail=str(exc),
#             ) from exc

#         return StyleGuideDTO(
#             id=updated_sg.id,
#             principle=updated_sg.principle,
#             examples=[
#                 StyleGuideExampleDTO(
#                     before=[
#                         StyleGuideExampleEventDTO(source=e.source, message=e.message)
#                         for e in ex.before
#                     ],
#                     after=[
#                         StyleGuideExampleEventDTO(source=e.source, message=e.message)
#                         for e in ex.after
#                     ],
#                     violation=ex.violation,
#                 )
#                 for ex in updated_sg.examples
#             ],
#         )

#     #
#     # 5) Delete a style guide
#     #
#     @router.delete(
#         "/{agent_id}/style_guides/{style_guide_id}",
#         status_code=status.HTTP_204_NO_CONTENT,
#         operation_id="delete_style_guide",
#         responses={
#             status.HTTP_204_NO_CONTENT: {
#                 "description": "Style guide successfully deleted. No content returned."
#             },
#             status.HTTP_404_NOT_FOUND: {"description": "Style guide or agent not found"},
#         },
#         **apigen_config(group_name="style_guides", method_name="delete"),
#     )
#     async def delete_style_guide(
#         agent_id: agents.AgentIdPath,
#         style_guide_id: StyleGuideIdPath,
#     ) -> None:
#         """
#         Deletes a style guide from the agent.
#         A 404 is returned if it does not exist.
#         """
#         try:
#             await style_guide_store.delete_style_guide(
#                 style_guide_set=agent_id, style_guide_id=style_guide_id
#             )
#         except ItemNotFoundError:
#             raise HTTPException(
#                 status_code=status.HTTP_404_NOT_FOUND,
#                 detail=f"Style guide '{style_guide_id}' not found for agent '{agent_id}'.",
#             )

#     return router
