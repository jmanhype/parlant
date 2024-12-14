import asyncio
from lagom import Container

from parlant.core.services.tools.plugins import PluginServer, tool
from parlant.core.services.tools.service_registry import ServiceRegistry
from parlant.core.tools import ToolContext, ToolResult


server_instance: PluginServer | None = None


@tool
def read_account_balance(context: ToolContext) -> ToolResult:
    return ToolResult(999)


async def initialize_module(container: Container) -> None:
    global server_instance

    server = PluginServer(
        tools=[read_account_balance],
        port=8094,
        host="127.0.0.1",
    )

    asyncio.create_task(server.serve())
    server_instance = server

    service_registry = container[ServiceRegistry]
    await service_registry.update_tool_service(
        name="parlant-bank",
        kind="sdk",
        url="http://127.0.0.1:8094",
    )


async def shutdown_module() -> None:
    global server_instance

    if server_instance is not None:
        await server_instance.shutdown()
        server_instance = None
