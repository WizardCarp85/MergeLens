"""Tests for FastAPI backend sidecar endpoints."""

from fastapi.testclient import TestClient
from mergelens.server.app import create_app


def test_api_health_endpoint():
    app = create_app(token="test-secret-token")
    client = TestClient(app)

    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["ok"] is True
    assert res.json()["service"] == "mergelens"


def test_unauthorized_without_token():
    app = create_app(token="test-secret-token")
    client = TestClient(app)

    res = client.get("/api/context")
    assert res.status_code == 401


def test_authorized_with_token():
    app = create_app(token="test-secret-token")
    client = TestClient(app)

    res = client.get(
        "/api/context",
        headers={"Authorization": "Bearer test-secret-token"},
    )
    assert res.status_code == 200
    data = res.json()
    assert "operation" in data


def test_decision_posting_and_storage():
    app = create_app(token="test-secret-token")
    client = TestClient(app)

    decision_payload = {
        "hunk_id": "src/app.py#1",
        "path": "src/app.py",
        "keep": "theirs",
        "reason": "Production verified upstream patch",
    }

    res = client.post(
        "/api/decisions",
        json=decision_payload,
        headers={"Authorization": "Bearer test-secret-token"},
    )
    assert res.status_code == 200
    assert res.json()["ok"] is True
    assert res.json()["saved"]["keep"] == "theirs"

