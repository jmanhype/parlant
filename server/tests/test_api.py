from fastapi.testclient import TestClient

from emcie.server import api

client = TestClient(api.app)


def test_index() -> None:
    response = client.get("/")
    assert response.status_code == 200
