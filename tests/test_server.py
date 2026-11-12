"""Unit tests for FastAPI CRM server endpoints."""

from fastapi.testclient import TestClient
from src.server.app import app

client = TestClient(app)


def test_serve_dashboard():
    """Verify that root URL returns the CRM Dashboard HTML."""
    response = client.get("/")
    assert response.status_code == 200
    assert "JobFlow-AI" in response.text
    assert "Kanban" in response.text or "Discovered" in response.text


def test_get_jobs_api():
    """Verify that /api/jobs returns structured jobs, kanban columns, and pagination."""
    response = client.get("/api/jobs")
    assert response.status_code == 200
    data = response.json()
    assert "jobs" in data
    assert "kanban" in data
    assert "counts" in data
    assert "pagination" in data
    assert "discovered" in data["kanban"]
    assert "applied" in data["kanban"]
    assert data["pagination"]["page"] == 1


def test_memory_api():
    """Verify that screening memory vault can be fetched and updated."""
    # Get memory
    res = client.get("/api/memory")
    assert res.status_code == 200
    mem = res.json()
    assert "notice_period" in mem

    # Save new memory
    save_res = client.post("/api/memory", json={"key": "github_portfolio", "value": "https://github.com/mywork"})
    assert save_res.status_code == 200
    updated_mem = save_res.json()["memory"]
    assert updated_mem["github_portfolio"] == "https://github.com/mywork"

