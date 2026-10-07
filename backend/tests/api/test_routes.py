"""Integration tests for the trimmed REST API surface.

Only the endpoints that survive in routes.py are tested here:
- POST /api/v1/projects (create_project)
- POST /api/v1/upload/parse (file parsing)
- GET  / (root)
- GET  /health

All other project operations (parse, plan, generate, render, page updates,
status, templates, LLM config) are exercised through the WebSocket gateway
in test_websocket.py.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.storage.memory import memory_store


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def clear_store():
    memory_store._projects.clear()
    yield
    memory_store._projects.clear()


@pytest.fixture
def sample_spec():
    return {
        "topic": "Test Topic",
        "audience": "Test Audience",
        "page_count": 5,
        "style": "学术简约",
    }


class TestProjectCreate:
    """POST /api/v1/projects — only surviving REST endpoint."""

    def test_create_project_with_spec(self, client):
        response = client.post(
            "/api/v1/projects",
            json={
                "spec": {"topic": "Test", "page_count": 5},
                "user_input": "Test PPT",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"].startswith("proj_")
        assert data["spec"]["topic"] == "Test"
        assert data["status"] == "idle"

    def test_create_project_without_spec(self, client):
        response = client.post("/api/v1/projects", json={})
        assert response.status_code == 200
        data = response.json()
        assert data["id"].startswith("proj_")
        # Default spec should fill in sensible values
        assert data["spec"].get("topic") is not None

    def test_create_project_minimal_payload(self, client):
        response = client.post("/api/v1/projects", json={"user_input": "Just text"})
        assert response.status_code == 200
        assert response.json()["user_input"] == "Just text"


class TestFileUploadParse:
    """POST /api/v1/upload/parse — text extraction utility."""

    def test_upload_markdown(self, client):
        md_content = "# Title\n\nSome markdown content."
        response = client.post(
            "/api/v1/upload/parse",
            files={"file": ("notes.md", md_content.encode("utf-8"), "text/markdown")},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["filename"] == "notes.md"
        assert "# Title" in data["content"]

    def test_upload_txt(self, client):
        response = client.post(
            "/api/v1/upload/parse",
            files={"file": ("doc.txt", b"hello world", "text/plain")},
        )
        assert response.status_code == 200
        assert response.json()["content"] == "hello world"

    def test_upload_unsupported_extension(self, client):
        response = client.post(
            "/api/v1/upload/parse",
            files={"file": ("image.png", b"\x89PNG", "image/png")},
        )
        assert response.status_code == 400
        assert "不支持" in response.json()["detail"]

    def test_upload_too_large(self, client):
        # 11MB of data
        large = b"a" * (11 * 1024 * 1024)
        response = client.post(
            "/api/v1/upload/parse",
            files={"file": ("big.txt", large, "text/plain")},
        )
        assert response.status_code == 400
        assert "过大" in response.json()["detail"]


class TestHealthAndRoot:
    def test_root(self, client):
        response = client.get("/")
        assert response.status_code == 200
        assert response.json()["name"] == "Folio Studio"

    def test_health(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
