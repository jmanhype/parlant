from datetime import datetime
from enum import Enum
from typing import Optional, TypeAlias, Union, cast
from fastapi import APIRouter, HTTPException, status

from parlant.api.common import apigen_config
from parlant.core.common import DefaultBaseModel
from parlant.core.services.tools.plugins import PluginClient
from parlant.core.tools import Tool, ToolParameter
from parlant.core.services.tools.openapi import OpenAPIClient
from parlant.core.services.tools.service_registry import ServiceRegistry, ToolServiceKind
from parlant.core.tools import ToolService

API_GROUP = "services"


class ToolServiceKindDTO(Enum):
    SDK = "sdk"
    OPENAPI = "openapi"


class ToolParameterTypeDTO(Enum):
    STRING = "string"
    NUMBER = "number"
    INTEGER = "integer"
    BOOLEAN = "boolean"


class SDKServiceParamsDTO(DefaultBaseModel):
    url: str


class OpenAPIServiceParamsDTO(DefaultBaseModel):
    url: str
    source: str


class ServiceUpdateParamsDTO(DefaultBaseModel):
    kind: ToolServiceKindDTO
    sdk: Optional[SDKServiceParamsDTO] = None
    openapi: Optional[OpenAPIServiceParamsDTO] = None


class ServiceUpdateResponse(DefaultBaseModel):
    name: str
    kind: ToolServiceKindDTO
    url: str


class ServiceDeletionResponse(DefaultBaseModel):
    name: str


EnumValueTypeDTO: TypeAlias = Union[str, int]


class ToolParameterDTO(DefaultBaseModel):
    type: ToolParameterTypeDTO
    description: Optional[str]
    enum: Optional[list[EnumValueTypeDTO]]


class ToolDTO(DefaultBaseModel):
    creation_utc: datetime
    name: str
    description: str
    parameters: dict[str, ToolParameterDTO]
    required: list[str]


class ServiceDTO(DefaultBaseModel):
    name: str
    kind: ToolServiceKindDTO
    url: str
    tools: Optional[list[ToolDTO]] = None


class ServiceListResponse(DefaultBaseModel):
    services: list[ServiceDTO]


def _tool_parameters_to_dto(parameters: ToolParameter) -> ToolParameterDTO:
    return ToolParameterDTO(
        type=ToolParameterTypeDTO(parameters["type"]),
        description=parameters["description"] if "description" in parameters else None,
        enum=parameters["enum"] if "enum" in parameters else None,
    )


def _tool_to_dto(tool: Tool) -> ToolDTO:
    return ToolDTO(
        creation_utc=tool.creation_utc,
        name=tool.name,
        description=tool.description,
        parameters={k: _tool_parameters_to_dto(p) for k, p in tool.parameters.items()},
        required=tool.required,
    )


def _get_service_kind(service: ToolService) -> ToolServiceKindDTO:
    return (
        ToolServiceKindDTO.OPENAPI if isinstance(service, OpenAPIClient) else ToolServiceKindDTO.SDK
    )


def _get_service_url(service: ToolService) -> str:
    return (
        service.server_url
        if isinstance(service, OpenAPIClient)
        else cast(PluginClient, service).url
    )


def _tool_service_kind_dto_to_tool_service_kind(dto: ToolServiceKindDTO) -> ToolServiceKind:
    return cast(
        ToolServiceKind,
        {
            ToolServiceKindDTO.OPENAPI: "openapi",
            ToolServiceKindDTO.SDK: "sdk",
        }[dto],
    )


def _tool_service_kind_to_dto(kind: ToolServiceKind) -> ToolServiceKindDTO:
    return {
        "openapi": ToolServiceKindDTO.OPENAPI,
        "sdk": ToolServiceKindDTO.SDK,
    }[kind]


def create_router(service_registry: ServiceRegistry) -> APIRouter:
    router = APIRouter()

    @router.put(
        "/{name}",
        operation_id="update_service",
        **apigen_config(group_name=API_GROUP, method_name="create_or_update"),
    )
    async def update_service(name: str, params: ServiceUpdateParamsDTO) -> ServiceUpdateResponse:
        if params.kind == ToolServiceKindDTO.SDK:
            if not params.sdk:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Missing SDK parameters",
                )

            if not (params.sdk.url.startswith("http://") or params.sdk.url.startswith("https://")):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Service URL is missing schema (http:// or https://)",
                )
        elif params.kind == ToolServiceKindDTO.OPENAPI:
            if not params.openapi:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Missing OpenAPI parameters",
                )
            if not (
                params.openapi.url.startswith("http://")
                or params.openapi.url.startswith("https://")
            ):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Service URL is missing schema (http:// or https://)",
                )
        else:
            raise Exception("Should never logically get here")

        if params.kind == ToolServiceKindDTO.SDK:
            assert params.sdk
            url = params.sdk.url
            source = None
        elif params.kind == ToolServiceKindDTO.OPENAPI:
            assert params.openapi
            url = params.openapi.url
            source = params.openapi.source
        else:
            raise Exception("Should never logically get here")

        service = await service_registry.update_tool_service(
            name=name,
            kind=_tool_service_kind_dto_to_tool_service_kind(params.kind),
            url=url,
            source=source,
        )

        return ServiceUpdateResponse(
            name=name,
            kind=_get_service_kind(service),
            url=_get_service_url(service),
        )

    @router.delete(
        "/{name}",
        operation_id="delete_service",
        **apigen_config(group_name=API_GROUP, method_name="delete"),
    )
    async def delete_service(name: str) -> ServiceDeletionResponse:
        await service_registry.delete_service(name)

        return ServiceDeletionResponse(name=name)

    @router.get(
        "/",
        operation_id="list_services",
        **apigen_config(group_name=API_GROUP, method_name="list"),
    )
    async def list_services() -> ServiceListResponse:
        return ServiceListResponse(
            services=[
                ServiceDTO(
                    name=name,
                    kind=_get_service_kind(service),
                    url=_get_service_url(service),
                )
                for name, service in await service_registry.list_tool_services()
                if type(service) in [OpenAPIClient, PluginClient]
            ]
        )

    @router.get(
        "/{name}",
        operation_id="read_service",
        **apigen_config(group_name=API_GROUP, method_name="retrieve"),
    )
    async def read_service(name: str) -> ServiceDTO:
        service = await service_registry.read_tool_service(name)

        return ServiceDTO(
            name=name,
            kind=_get_service_kind(service),
            url=_get_service_url(service),
            tools=[_tool_to_dto(t) for t in await service.list_tools()],
        )

    return router
