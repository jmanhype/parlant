import asyncio
from typing import Any, AsyncIterator, Dict
from fastapi.testclient import TestClient
from lagom import Container, Singleton
from pytest import fixture, Config

from emcie.server.api.app import create_app
from emcie.server.core.agents import AgentStore
from emcie.server.core.context_variables import ContextVariableStore
from emcie.server.core.end_users import EndUserStore
from emcie.server.core.guidelines import GuidelineStore
from emcie.server.core.sessions import PollingSessionListener, SessionListener, SessionStore
from emcie.server.core.tools import ToolStore
from emcie.server.engines.alpha.engine import AlphaEngine
from emcie.server.engines.alpha.guideline_tool_associations import GuidelineToolAssociationStore
from emcie.server.engines.common import Engine
from emcie.server.mc import MC

from .test_utilities import SyncAwaiter


@fixture
async def sync_await() -> SyncAwaiter:
    return SyncAwaiter(asyncio.get_event_loop())


@fixture
def test_config(pytestconfig: Config) -> Dict[str, Any]:
    return {"patience": 10}


@fixture
async def container() -> AsyncIterator[Container]:
    container = Container(log_undefined_deps=True)

    container[AgentStore] = AgentStore()
    container[ContextVariableStore] = ContextVariableStore()
    container[EndUserStore] = EndUserStore()
    container[GuidelineStore] = GuidelineStore()
    container[GuidelineToolAssociationStore] = GuidelineToolAssociationStore()
    container[SessionStore] = SessionStore()
    container[ToolStore] = ToolStore()
    container[SessionListener] = Singleton(PollingSessionListener)
    container[Engine] = Singleton(AlphaEngine)

    async with MC(container) as mc:
        container[MC] = mc
        yield container


@fixture
async def client(container: Container) -> AsyncIterator[TestClient]:
    app = await create_app(container)

    with TestClient(app) as client:
        yield client
