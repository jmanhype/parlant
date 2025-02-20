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

import asyncio
from fastapi.testclient import TestClient
from parlant.api.app import ASGIApplication
from lagom import Container
import pytest

from parlant.adapters.loggers.websocket import WebSocketLogger
from parlant.core.contextual_correlator import ContextualCorrelator


@pytest.fixture
def test_client(api_app: ASGIApplication) -> TestClient:
    return TestClient(api_app)


async def test_that_websocket_logger_sends_messages(
    container: Container,
    test_client: TestClient,
) -> None:
    ws_logger = container[WebSocketLogger]
    correlator = container[ContextualCorrelator]

    with test_client.websocket_connect("/logs") as ws:
        ws_logger.info("Hello from test!")
        await asyncio.sleep(1)

        data = ws.receive_json()

        assert data["message"] == "Hello from test!"
        assert data["level"] == "INFO"
        assert data["correlation_id"] == correlator.correlation_id


async def test_that_websocket_reconnects_and_receives_messages(
    container: Container,
    test_client: TestClient,
) -> None:
    ws_logger = container[WebSocketLogger]
    correlator = container[ContextualCorrelator]

    with test_client.websocket_connect("/logs") as ws1:
        ws_logger.info("First connection test")
        await asyncio.sleep(1)

        data1 = ws1.receive_json()
        assert data1["message"] == "First connection test"
        assert data1["level"] == "INFO"
        assert data1["correlation_id"] == correlator.correlation_id

    with test_client.websocket_connect("/logs") as ws2:
        ws_logger.info("Second connection test")
        await asyncio.sleep(1)

        data2 = ws2.receive_json()
        assert data2["message"] == "Second connection test"
        assert data2["level"] == "INFO"
        assert data2["correlation_id"] == correlator.correlation_id
