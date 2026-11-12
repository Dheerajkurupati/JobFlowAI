"""RAG Semantic Matcher & Skill Gap Learning Engine.

Calculates ATS match scores, detects missing keyword gaps, and
generates concrete learning roadmaps to turn rejections into offers.
"""

import re
from typing import List, Set
from pydantic import BaseModel, Field
from src.parser.profile_schema import CandidateProfile
from src.parser.pdf_reader import extract_skills_inventory


class MatchResult(BaseModel):
    match_score: int
    matched_skills: List[str]
    missing_skills: List[str]
    fit_verdict: str  # "Strong Fit", "Good Fit", "Upskill Opportunity"
    learning_roadmap: List[str] = Field(default_factory=list)
    suggested_ctc_response: str


def calculate_ats_match(profile: CandidateProfile, job_description: str, posted_salary_text: str = "") -> MatchResult:
    """Calculate ATS match score between Candidate Profile and target Job Description.
    
    Args:
        profile: Parsed CandidateProfile from resume.
        job_description: Full text of target job posting.
        posted_salary_text: Optional salary string from job posting (e.g. "4-6 LPA").
        
    Returns:
        MatchResult with score, matched skills, gaps, and roadmap.
    """
    jd_skills = set(extract_skills_inventory(job_description))
    candidate_skills = set(profile.skills)

    # Core skill overlap
    matched = sorted(list(candidate_skills.intersection(jd_skills)))
    missing = sorted(list(jd_skills.difference(candidate_skills)))

    # Base ATS Score calculation
    if not jd_skills:
        # If JD has few explicit tech keywords, default to candidate baseline
        score = 80
    else:
        overlap_ratio = len(matched) / len(jd_skills)
        # Scaled between 60% and 98%
        score = int(60 + (overlap_ratio * 38))

    # Verdict
    if score >= 85:
        verdict = "Strong Fit (>85%)"
    elif score >= 75:
        verdict = "Good Fit (75-84%)"
    else:
        verdict = "Upskill Opportunity (<75%)"

    # Actionable Learning Roadmap for missing skills
    roadmap = generate_skill_roadmap(missing)

    # Context-Aware CTC Negotiation:
    # If JD specifies a budget (e.g., 4-6 LPA), answer within their upper bound
    ctc_response = "Negotiable / As per company budget"
    salary_match = re.search(r"(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*(?:LPA|lacs?|lakhs?)", posted_salary_text, re.IGNORECASE)
    if salary_match:
        upper_lpa = salary_match.group(2)
        ctc_response = f"{upper_lpa} LPA (Negotiable based on company standards)"

    return MatchResult(
        match_score=min(max(score, 65), 98),
        matched_skills=matched or ["Python"],
        missing_skills=missing,
        fit_verdict=verdict,
        learning_roadmap=roadmap,
        suggested_ctc_response=ctc_response
    )


def generate_skill_roadmap(missing_skills: List[str]) -> List[str]:
    """Generate concrete micro-projects and revision tips to bridge skill gaps."""
    recommendations = []
    
    skill_guides = {
        "Docker": "Build a multi-stage Dockerfile containerizing your FastAPI app and deploy it locally.",
        "Kubernetes": "Write a basic K8s Deployment and Service manifest exposing a containerized microservice on Minikube.",
        "Redis": "Implement an in-memory Redis cache with TTL for your top 3 slowest API endpoints.",
        "Celery": "Set up a background Celery worker for asynchronous email notifications and scraping tasks.",
        "Kafka": "Design a basic Kafka producer-consumer stream passing job events to an analytics topic.",
        "PostgreSQL": "Optimize complex relational queries using indexes and EXPLAIN ANALYZE on foreign keys.",
        "MongoDB": "Model an unstructured document schema for job raw payloads with TTL indexes.",
        "LangChain": "Implement an agentic ReAct loop with tool calling over structured search APIs.",
        "ChromaDB": "Build a persistent vector collection using HNSW indexing and cosine distance.",
        "PyTorch": "Fine-tune a lightweight DistilBERT model for multi-class resume text classification.",
        "AWS": "Deploy a serverless lambda function behind an API Gateway connected to S3 storage."
    }

    for skill in missing_skills[:4]:  # Top 4 actionable gaps
        if skill in skill_guides:
            recommendations.append(f"• Learn {skill}: {skill_guides[skill]}")
        else:
            recommendations.append(f"• Explore {skill}: Review official documentation and build a 1-day proof-of-concept project.")

    if not recommendations:
        recommendations.append("• Complete Match: Your technical stack aligns directly with all requirements in this posting.")

    return recommendations
