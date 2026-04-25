"""Tests for GET /health.

Covers response shape for both unloaded and loaded store states.
"""

from fastapi.testclient import TestClient


def test_health_unloaded_returns_200(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200


def test_health_unloaded_shape(client: TestClient) -> None:
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["store_loaded"] is False
    assert body["store_row_count"] == 0


def test_health_loaded_reflects_store(loaded_client: TestClient) -> None:
    body = loaded_client.get("/health").json()
    assert body["status"] == "ok"
    assert body["store_loaded"] is True
    assert body["store_row_count"] == 5
