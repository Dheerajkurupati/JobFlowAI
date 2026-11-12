"""Pydantic schemas for Candidate Career Profile and Vault."""

from typing import List, Optional
from pydantic import BaseModel, Field


class Education(BaseModel):
    degree: str
    field_of_study: str
    institution: str
    graduation_year: int
    score: Optional[str] = None


class Project(BaseModel):
    title: str
    description: str
    technologies: List[str] = Field(default_factory=list)
    metrics_or_highlights: List[str] = Field(default_factory=list)


class Experience(BaseModel):
    company: str
    role: str
    duration: Optional[str] = None
    location: Optional[str] = None
    bullet_points: List[str] = Field(default_factory=list)


class CandidateProfile(BaseModel):
    """Complete structured representation of a candidate's resume and career vault."""
    name: str
    email: str
    phone: str
    city: str
    linkedin_url: Optional[str] = None
    github_url: Optional[str] = None
    summary: Optional[str] = None

    education: List[Education] = Field(default_factory=list)
    skills: List[str] = Field(default_factory=list)
    projects: List[Project] = Field(default_factory=list)
    experience: List[Experience] = Field(default_factory=list)

    # Derived Role Matrix (automatically computed from resume skills)
    primary_roles: List[str] = Field(default_factory=list)
    secondary_roles: List[str] = Field(default_factory=list)

    # Screening Defaults
    notice_period_days: int = 0
    availability_status: str = "Immediate"
    willing_to_relocate: bool = True
    target_locations: List[str] = Field(
        default_factory=lambda: ["Hyderabad", "Bengaluru", "Chennai", "Pune", "Remote"]
    )

