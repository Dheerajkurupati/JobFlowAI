"""Unit tests for ATS Semantic Matcher & Skill Gap Engine."""

from src.parser.profile_schema import CandidateProfile
from src.brain.matcher import calculate_ats_match, generate_skill_roadmap


def test_calculate_ats_match():
    """Verify ATS score calculation, matched skills, and gap identification."""
    profile = CandidateProfile(
        name="Alex Mercer",
        email="alex@example.com",
        phone="+91 9876543210",
        city="Hyderabad",
        skills=["Python", "FastAPI", "LangChain", "SQL", "ChromaDB"]
    )

    jd_text = """
    We are looking for a Junior AI Engineer.
    Must have experience with Python, FastAPI, and LangChain.
    Knowledge of Redis and Docker is a big plus.
    """

    res = calculate_ats_match(profile, jd_text, posted_salary_text="5-7 LPA")

    assert res.match_score >= 75
    assert "Python" in res.matched_skills
    assert "FastAPI" in res.matched_skills
    assert "Redis" in res.missing_skills
    assert "7 LPA" in res.suggested_ctc_response
    assert len(res.learning_roadmap) > 0


def test_generate_skill_roadmap():
    """Verify actionable learning recommendations for missing skills."""
    missing = ["Docker", "Kafka", "Celery"]
    roadmap = generate_skill_roadmap(missing)
    assert len(roadmap) == 3
    assert any("Docker" in item for item in roadmap)
    assert any("Kafka" in item for item in roadmap)
    assert any("Celery" in item for item in roadmap)
