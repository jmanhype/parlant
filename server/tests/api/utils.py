from typing import Callable, Optional

from lagom import Container

from emcie.common.tools import ToolId, ToolResult
from emcie.server.core.agents import Agent, AgentId, AgentStore
from emcie.server.core.async_utils import Timeout
from emcie.server.core.end_users import EndUserId
from emcie.server.core.guideline_tool_associations import GuidelineToolAssociationStore
from emcie.server.core.guidelines import GuidelineStore
from emcie.server.core.mc import MC
from emcie.server.core.sessions import Event, MessageEventData, Session, SessionId, SessionStore
from emcie.server.core.tools import LocalToolService


async def create_agent(container: Container, name: str) -> Agent:
    return await container[AgentStore].create_agent(name="test-agent")


async def create_session(
    container: Container,
    agent_id: AgentId,
    end_user_id: Optional[EndUserId] = None,
    title: Optional[str] = None,
) -> Session:
    return await container[SessionStore].create_session(
        end_user_id or EndUserId("test-user"),
        agent_id=agent_id,
        title=title,
    )


async def create_guideline(
    container: Container,
    agent_id: AgentId,
    predicate: str,
    action: str,
    tool_function: Optional[Callable[[], ToolResult]] = None,
) -> None:
    guideline = await container[GuidelineStore].create_guideline(
        guideline_set=agent_id,
        predicate=predicate,
        action=action,
    )

    if tool_function:
        tool_service = container[LocalToolService]

        existing_tools = await tool_service.list_tools()

        tool = next((t for t in existing_tools if t.name == tool_function.__name__), None)

        if not tool:
            tool = await tool_service.create_tool(
                name=tool_function.__name__,
                module_path=tool_function.__module__,
                description="",
                parameters={},
                required=[],
            )

        await container[GuidelineToolAssociationStore].create_association(
            guideline_id=guideline.id,
            tool_id=ToolId(f"local__{tool.id}"),
        )


async def post_message(
    container: Container,
    session_id: SessionId,
    message: str,
    response_timeout: Timeout = Timeout.none(),
) -> Event:
    data: MessageEventData = {"message": message}

    event = await container[MC].post_client_event(
        session_id=session_id,
        kind="message",
        data=data,
    )

    if response_timeout:
        await container[MC].wait_for_update(
            session_id=session_id,
            min_offset=event.offset + 1,
            timeout=response_timeout,
        )

    return event
