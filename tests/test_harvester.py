"""Unit tests for Multi-Platform Harvester filter rules."""

from src.config import FilterRulesConfig, SearchPreferencesConfig
from src.harvester.filter_rules import is_job_acceptable


def test_reject_sales_and_telecalling():
    """Verify that non-IT and sales roles are rejected immediately."""
    filter_rules = FilterRulesConfig()
    search_prefs = SearchPreferencesConfig()

    decision = is_job_acceptable(
        title="Business Development Associate (Sales)",
        description="Looking for energetic sales candidates for field lead generation.",
        location="Hyderabad",
        filter_rules=filter_rules,
        search_prefs=search_prefs
    )
    assert decision.is_accepted is False
    assert "sales" in decision.rejection_reason.lower() or "bda" in decision.rejection_reason.lower()


def test_reject_night_shifts():
    """Verify that US/night shifts are rejected per user rules."""
    filter_rules = FilterRulesConfig()
    search_prefs = SearchPreferencesConfig()

    decision = is_job_acceptable(
        title="Operations Analyst",
        description="Night shift role: 6:30 PM to 3:30 AM IST. US client support.",
        location="Hyderabad",
        filter_rules=filter_rules,
        search_prefs=search_prefs
    )
    assert decision.is_accepted is False
    assert "night shift" in decision.rejection_reason.lower()


def test_accept_valid_tech_role():
    """Verify that genuine IT/AI roles in target tech hubs pass the filter."""
    filter_rules = FilterRulesConfig()
    search_prefs = SearchPreferencesConfig()

    decision = is_job_acceptable(
        title="Junior AI / Python Developer",
        description="Build FastAPI endpoints, RAG pipelines, and integrate LLMs.",
        location="Hyderabad",
        filter_rules=filter_rules,
        search_prefs=search_prefs
    )
    assert decision.is_accepted is True
    assert decision.rejection_reason is None


def test_accept_remote_role():
    """Verify that remote roles across India are approved."""
    filter_rules = FilterRulesConfig()
    search_prefs = SearchPreferencesConfig()

    decision = is_job_acceptable(
        title="Python Backend Developer",
        description="Work from home / Remote opportunity anywhere in India.",
        location="Remote",
        filter_rules=filter_rules,
        search_prefs=search_prefs
    )
    assert decision.is_accepted is True
