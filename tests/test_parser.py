"""Unit tests for Resume Parser and Profile Ingestion."""

from pathlib import Path
from src.parser.pdf_reader import (
    extract_text_from_file,
    extract_contact_details,
    extract_skills_inventory,
    infer_dynamic_roles,
    parse_resume_to_profile
)


def test_extract_sample_resume():
    """Verify text extraction from sample resume fixture."""
    sample_path = Path("data/sample_resume.txt")
    assert sample_path.exists()
    text = extract_text_from_file(str(sample_path))
    assert len(text) > 100
    assert "Alex Mercer" in text
    assert "FastAPI" in text


def test_contact_details_extraction():
    """Verify regex extraction of email, phone, city, and URLs."""
    sample_text = """
    Jane Doe
    Bengaluru, India | jane.doe@example.com | +91 9123456789
    LinkedIn: https://linkedin.com/in/janedoe | GitHub: https://github.com/janedoe
    """
    name, email, phone, city, linkedin, github = extract_contact_details(sample_text)
    assert name == "Jane Doe"
    assert email == "jane.doe@example.com"
    assert "9123456789" in phone
    assert city == "Bengaluru"
    assert "janedoe" in linkedin
    assert "janedoe" in github


def test_skills_inventory_and_role_inference():
    """Verify skills extraction and dynamic role derivation."""
    sample_text = "Experienced in Python, FastAPI, LangChain, RAG architecture, ChromaDB, and Docker."
    skills = extract_skills_inventory(sample_text)
    assert "Python" in skills
    assert "FastAPI" in skills
    assert "LangChain" in skills
    assert "Docker" in skills

    primary, secondary = infer_dynamic_roles(skills)
    assert any("AI" in r or "LLM" in r for r in primary)
    assert any("Python" in r or "Backend" in r for r in secondary)


def test_full_parse_pipeline():
    """Verify parse_resume_to_profile creates a valid CandidateProfile."""
    sample_path = Path("data/sample_resume.txt")
    profile = parse_resume_to_profile(str(sample_path))
    assert profile.name == "Alex Mercer"
    assert "Python" in profile.skills
    assert "FastAPI" in profile.skills
    assert len(profile.primary_roles) > 0

