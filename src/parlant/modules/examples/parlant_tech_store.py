from lagom import Container

from parlant.core.background_tasks import BackgroundTaskService
from parlant.core.services.tools.plugins import PluginServer, tool
from parlant.core.services.tools.service_registry import ServiceRegistry
from parlant.core.tools import ToolContext, ToolResult


server_instance: PluginServer | None = None


@tool
def list_categories(context: ToolContext) -> ToolResult:
    return ToolResult(["laptops", "chairs"])


async def initialize_module(container: Container) -> None:
    global server_instance
    _background_task_service = container[BackgroundTaskService]

    server = PluginServer(
        tools=[list_categories],
        port=8095,
        host="127.0.0.1",
    )

    await _background_task_service.start(
        server.serve(),
        tag="plugin-server 'parlant-tech-store'",
    )
    server_instance = server

    service_registry = container[ServiceRegistry]
    await service_registry.update_tool_service(
        name="parlant-tech-store",
        kind="sdk",
        url="http://127.0.0.1:8095",
    )


async def shutdown_module() -> None:
    global server_instance

    if server_instance is not None:
        await server_instance.shutdown()
        server_instance = None
