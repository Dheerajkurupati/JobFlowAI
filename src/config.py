"""Configuration manager for JobFlow-AI.

Loads settings from YAML files and environment variables, validating them
with Pydantic schemas to ensure clean error messages for users.
"""

from pathlib import Path
from typing import List, Optional
import os
import yaml
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Automatically load .env file if present
load_dotenv()


class CandidateConfig(BaseModel):
    """Candidate personal details and availability."""
    name: str = Field(default="Candidate")
    email: str = Field(default="")
    phone: str = Field(default="")
    city: str = Field(default="Hyderabad")
    resume_path: str = Field(default="data/resume.pdf")
    current_experience_years: float = Field(default=0.0)
    highest_qualification: str = Field(default="B.Tech")
    graduation_year: int = Field(default=2025)
    notice_period_days: int = Field(default=0)
    availability_status: str = Field(default="Immediate")


class SearchPreferencesConfig(BaseModel):
    """Target locations, portals, and application velocity limits."""
    target_locations: List[str] = Field(
        default_factory=lambda: ["Hyderabad", "Bengaluru", "Chennai", "Pune", "Remote"]
    )
    allow_pan_india_if_virtual: bool = Field(default=True)
    daily_application_limit: int = Field(default=30)


class FilterRulesConfig(BaseModel):
    """Rules to discard non-matching or exploitative job postings."""
    ignore_role_keywords: List[str] = Field(
        default_factory=lambda: [
            "sales",
            "telecalling",
            "tele-caller",
            "bpo",
            "voice process",
            "customer support",
            "collections",
            "bda",
            "business development",
        ]
    )
    ignore_shift_keywords: List[str] = Field(
        default_factory=lambda: [
            "night shift",
            "us shift",
            "uk shift",
            "graveyard shift",
        ]
    )
    ignore_unpaid_internships: bool = Field(default=True)


class TrackerConfig(BaseModel):
    """Spreadsheet / Excel tracker settings."""
    excel_path: str = Field(default="data/Job_Tracker.xlsx")
    enable_daily_separator: bool = Field(default=True)


class AppConfig(BaseModel):
    """Root configuration object combining all modules."""
    candidate: CandidateConfig = Field(default_factory=CandidateConfig)
    search_preferences: SearchPreferencesConfig = Field(default_factory=SearchPreferencesConfig)
    filter_rules: FilterRulesConfig = Field(default_factory=FilterRulesConfig)
    tracker: TrackerConfig = Field(default_factory=TrackerConfig)

    # Environment overrides
    llm_provider: str = Field(default_factory=lambda: os.getenv("LLM_PROVIDER", "gemini"))
    gemini_api_key: Optional[str] = Field(default_factory=lambda: os.getenv("GEMINI_API_KEY"))
    ollama_base_url: str = Field(default_factory=lambda: os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"))


def load_config(config_path: Optional[str] = None) -> AppConfig:
    """Load configuration from settings.yaml or fallback to settings.example.yaml.
    
    Args:
        config_path: Path to the YAML file. If None, checks config/settings.yaml
                     then config/settings.example.yaml.
                     
    Returns:
        AppConfig: Validated application configuration.
    """
    root_dir = Path(__file__).resolve().parent.parent

    if config_path:
        target_path = Path(config_path)
    else:
        # Check user config first, then example template
        user_config = root_dir / "config" / "settings.yaml"
        example_config = root_dir / "config" / "settings.example.yaml"
        target_path = user_config if user_config.exists() else example_config

    if not target_path.exists():
        # Fallback to sensible defaults
        return AppConfig()

    with open(target_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    return AppConfig(**data)
