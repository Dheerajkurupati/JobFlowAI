"""Unit tests for configuration loading and validation."""

from pathlib import Path
from src.config import load_config, AppConfig


def test_load_default_config():
    """Verify that default configuration loads without errors."""
    config = load_config()
    assert isinstance(config, AppConfig)
    assert len(config.search_preferences.target_locations) > 0
    assert "Hyderabad" in config.search_preferences.target_locations
    assert config.candidate.current_experience_years == 0.0
    assert config.filter_rules.ignore_unpaid_internships is True
    assert "sales" in config.filter_rules.ignore_role_keywords
    assert "night shift" in config.filter_rules.ignore_shift_keywords


def test_config_candidate_fields():
    """Verify candidate fields can be parsed correctly."""
    config = load_config()
    assert config.candidate.availability_status == "Immediate"
    assert config.tracker.excel_path == "data/Job_Tracker.xlsx"
