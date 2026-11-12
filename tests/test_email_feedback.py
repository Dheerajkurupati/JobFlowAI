"""Unit tests for the Closed-Loop Email Feedback Engine."""

import pytest
from src.brain.email_feedback import EmailFeedbackEngine, EmailFeedbackItem
from src.server.storage import CRMStorage, JobItem


@pytest.fixture
def mock_storage(tmp_path):
    storage = CRMStorage(data_dir=str(tmp_path))
    job1 = JobItem(
        id="test-job-1",
        date="2026-11-12",
        company="Anthropic",
        title="AI Engineer",
        location="Remote",
        work_type="Remote",
        job_link="https://anthropic.com/careers/ai-eng",
        status="applied",
        match_score=92,
        matched_skills=["Python", "FastAPI", "RAG"],
        missing_skills=[],
        screening_notes="Applied via website"
    )
    job2 = JobItem(
        id="test-job-2",
        date="2026-11-12",
        company="Uber",
        title="Backend Developer",
        location="Hyderabad",
        work_type="Hybrid",
        job_link="https://uber.com/jobs/backend",
        status="applied",
        match_score=85,
        matched_skills=["Python", "SQL"],
        missing_skills=["Docker"],
        screening_notes="Applied on Indeed"
    )
    storage.save_job(job1)
    storage.save_job(job2)
    return storage


def test_classify_interview_invite(mock_storage, tmp_path):
    engine = EmailFeedbackEngine(storage=mock_storage, excel_path=str(tmp_path / "test.xlsx"))
    result = engine.classify_email(
        subject="Invitation to Interview: AI Engineer Round 1",
        body="We would like to schedule an interview with our engineering team next week.",
        sender="recruiter@anthropic.com"
    )
    assert result is not None
    status, label = result
    assert status == "interview"
    assert "Interview" in label


def test_classify_online_assessment(mock_storage, tmp_path):
    engine = EmailFeedbackEngine(storage=mock_storage, excel_path=str(tmp_path / "test.xlsx"))
    result = engine.classify_email(
        subject="Action Required: Complete Your HackerRank Assessment",
        body="Please complete the coding assessment within 48 hours.",
        sender="noreply@hackerrank.com"
    )
    assert result is not None
    status, label = result
    assert status == "needs_input"
    assert "Assessment" in label


def test_classify_rejection(mock_storage, tmp_path):
    engine = EmailFeedbackEngine(storage=mock_storage, excel_path=str(tmp_path / "test.xlsx"))
    result = engine.classify_email(
        subject="Update on your application",
        body="Unfortunately, after careful consideration, we will not be moving forward with other candidates.",
        sender="careers@uber.com"
    )
    assert result is not None
    status, label = result
    assert status == "rejected"
    assert "Rejected" in label


def test_matching_job_by_company_and_domain(mock_storage, tmp_path):
    engine = EmailFeedbackEngine(storage=mock_storage, excel_path=str(tmp_path / "test.xlsx"))
    match = engine.find_matching_job(
        subject="Discussion regarding your application at Anthropic",
        body="Hello Candidate, we received your application.",
        sender="recruiting@anthropic.com"
    )
    assert match is not None
    assert match["company"] == "Anthropic"


def test_process_feedback_updates_storage(mock_storage, tmp_path):
    engine = EmailFeedbackEngine(storage=mock_storage, excel_path=str(tmp_path / "test.xlsx"))
    item = engine.process_feedback(
        company="Anthropic",
        detected_status="interview",
        status_label="Interview Scheduled 📅",
        subject="Interview Invitation",
        sender="recruiting@anthropic.com",
        snippet="We would love to invite you for a 45 min chat."
    )
    assert item.company == "Anthropic"
    assert item.detected_status == "interview"

    # Verify CRM updated
    updated_job = next(j for j in mock_storage.get_all_jobs() if j["company"] == "Anthropic")
    assert updated_job["status"] == "interview"
    assert "Recruiter Email: Interview Scheduled" in updated_job["screening_notes"]


def test_simulation_feedback(mock_storage, tmp_path):
    engine = EmailFeedbackEngine(storage=mock_storage, excel_path=str(tmp_path / "test.xlsx"))
    simulated = engine.sync_simulated_feedback()
    assert len(simulated) > 0
    assert any(item.detected_status in ["interview", "needs_input", "rejected"] for item in simulated)
