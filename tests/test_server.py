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


def test_harvest_endpoint_exists():
    """Verify that /api/harvest endpoint can be called."""
    from unittest.mock import patch

    with patch("src.harvester.multi_scraper.harvest_jobs_across_platforms") as mock_harvest:
        mock_harvest.return_value = {"total_scraped": 10, "accepted": 8, "skipped": 2, "new_added": 8}
        response = client.post("/api/harvest")
        assert response.status_code == 200
        assert response.json()["message"] == "Harvest complete"
        assert response.json()["summary"]["accepted"] == 8


def test_email_sync_endpoint():
    """Verify that /api/email-sync processes simulated or live emails."""
    res = client.post("/api/email-sync", json={"simulate": True})
    assert res.status_code == 200
    data = res.json()
    assert "message" in data
    assert "events" in data
    assert isinstance(data["events"], list)


def test_auto_fill_endpoint_invalid_job():
    """Verify that auto-fill returns 404 for unknown job."""
    res = client.post("/api/jobs/nonexistent-id/auto-fill", json={"headless": True})
    assert res.status_code == 404

