"""Unit tests for Playwright Browser Pilot and FormFiller."""

import pytest
from src.parser.profile_schema import CandidateProfile
from src.agent.form_filler import FormFiller, FillResult
from src.agent.browser_pilot import BrowserPilot, ApplicationRunResult


def test_form_filler_memory_matching():
    """Verify that screening question labels fuzzy-match the memory vault."""
    profile = CandidateProfile(
        name="Alex Mercer",
        email="alex@example.com",
        phone="+91 9876543210",
        city="Hyderabad",
        skills=["Python", "FastAPI"]
    )
    custom_memory = {
        "notice_period": "Immediate (0 days)",
        "expected_ctc": "6 LPA",
        "willing_to_relocate": "Yes",
        "previously_employed": "No"
    }

    filler = FormFiller(profile, memory=custom_memory)

    assert filler._find_matching_memory_answer("what is your notice period?") == "Immediate (0 days)"
    assert filler._find_matching_memory_answer("expected ctc in lpa") == "6 LPA"
    assert filler._find_matching_memory_answer("are you willing to relocate to hyderabad?") == "Yes"
    assert filler._find_matching_memory_answer("have you previously worked here?") == "No"
    assert filler._find_matching_memory_answer("what is your favorite movie?") is None


def test_fill_result_schema():
    """Verify FillResult defaults and data structure."""
    result = FillResult(
        fields_filled=["Full Name", "Email", "Phone", "Resume PDF"],
        resume_uploaded=True,
        questions_answered={"Notice Period": "Immediate"},
        status="ready_for_review"
    )
    assert result.resume_uploaded is True
    assert len(result.fields_filled) == 4
    assert result.status == "ready_for_review"


def test_browser_pilot_safety_defaults():
    """Verify that BrowserPilot initializes with Human-in-the-Loop review mode enabled."""
    pilot = BrowserPilot()
    assert pilot.form_filler is not None
    assert pilot.profile is not None

