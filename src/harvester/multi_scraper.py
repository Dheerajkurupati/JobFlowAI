"""Multi-platform concurrent job harvester using JobSpy.

Scrapes concurrently across LinkedIn, Indeed, Glassdoor, ZipRecruiter,
Google Jobs, and Naukri with automatic deduplication, strict rule filtering,
and RAG match evaluation.
"""

import uuid
from datetime import date
from typing import Dict, List, Optional
from jobspy import scrape_jobs
from src.config import AppConfig, load_config
from src.parser.profile_schema import CandidateProfile
from src.parser.pdf_reader import parse_resume_to_profile
from src.brain.matcher import calculate_ats_match
from src.server.storage import CRMStorage, JobItem
from src.harvester.filter_rules import is_job_acceptable


def harvest_jobs_across_platforms(
    config: Optional[AppConfig] = None,
    platforms: Optional[List[str]] = None,
    search_terms: Optional[List[str]] = None,
    max_results_per_platform: int = 15,
) -> Dict[str, int]:
    """Execute concurrent multi-board job harvesting.
    
    Args:
        config: Application configuration. If None, loads default.
        platforms: List of job portals (e.g. ['linkedin', 'indeed', 'glassdoor', 'naukri']).
        search_terms: Job titles to search. If None, derived from candidate resume.
        max_results_per_platform: Maximum results per platform query.
        
    Returns:
        Summary dict of scraped, accepted, skipped, and new jobs.
    """
    cfg = config or load_config()
    storage = CRMStorage()
    existing_links = storage.excel_tracker.get_existing_job_links()

    # Supported platforms with safe normalization
    platform_map = {
        "linkedin": "linkedin",
        "indeed": "indeed",
        "glassdoor": "glassdoor",
        "ziprecruiter": "zip_recruiter",
        "zip_recruiter": "zip_recruiter",
        "naukri": "naukri",
        "google": "google"
    }
    raw_platforms = platforms or ["linkedin", "indeed", "glassdoor", "ziprecruiter"]
    target_platforms = [platform_map.get(p.lower(), p) for p in raw_platforms]

    # Ingest profile to get dynamic role search titles
    resume_path = cfg.candidate.resume_path
    try:
        profile = parse_resume_to_profile(resume_path)
    except Exception:
        profile = CandidateProfile(
            name=cfg.candidate.name,
            email=cfg.candidate.email,
            phone=cfg.candidate.phone,
            city=cfg.candidate.city,
            skills=["Python", "FastAPI", "SQL", "Machine Learning", "LLM"],
            primary_roles=["AI Engineer", "Python Developer"]
        )

    queries = search_terms or profile.primary_roles[:2] or ["AI Engineer", "Python Developer"]
    location_query = f"{cfg.candidate.city}, India"

    summary = {
        "total_scraped": 0,
        "accepted": 0,
        "skipped": 0,
        "new_added": 0
    }

    for query in queries:
        try:
            # Concurrently scrape across platforms
            df = scrape_jobs(
                site_name=target_platforms,
                search_term=query,
                location=location_query,
                results_wanted=max_results_per_platform,
                hours_old=72,
                country_indeed="India"
            )

            if df is None or df.empty:
                continue

            summary["total_scraped"] += len(df)

            for _, row in df.iterrows():
                job_url = str(row.get("job_url") or "").strip()
                if not job_url or job_url in existing_links:
                    continue  # Deduplication check

                title = str(row.get("title") or "Software Developer").strip()
                company = str(row.get("company") or "Tech Company").strip()
                location = str(row.get("location") or cfg.candidate.city).strip()
                description = str(row.get("description") or "").strip()
                work_type = "Remote" if "remote" in location.lower() or "remote" in description.lower() else "Hybrid"

                # 1. Apply Strict Deterministic Filter Rules
                decision = is_job_acceptable(
                    title=title,
                    description=description,
                    location=location,
                    filter_rules=cfg.filter_rules,
                    search_prefs=cfg.search_preferences
                )

                if not decision.is_accepted:
                    # Log to Excel as Skipped with audit note
                    storage.excel_tracker.log_application(
                        company=company,
                        job_title=title,
                        location=location,
                        job_link=job_url,
                        status="Skipped",
                        reason_notes=f"Skipped: {decision.rejection_reason}",
                        work_type=work_type
                    )
                    existing_links.add(job_url)
                    summary["skipped"] += 1
                    continue

                # 2. Evaluate ATS Match Score & Skill Gaps
                match_res = calculate_ats_match(profile, description)
                summary["accepted"] += 1

                # 3. Create Structured Job Item for CRM
                new_status = "review" if match_res.match_score >= 80 else "discovered"
                job_item = JobItem(
                    id=f"job-{uuid.uuid4().hex[:6]}",
                    date=date.today().isoformat(),
                    company=company,
                    title=title,
                    location=location,
                    work_type=work_type,
                    job_link=job_url,
                    status=new_status,
                    match_score=match_res.match_score,
                    matched_skills=match_res.matched_skills,
                    missing_skills=match_res.missing_skills,
                    screening_notes=(
                        f"Scraped via {row.get('site', 'JobSpy')}. {match_res.match_score}% Match. "
                        f"Matched: {', '.join(match_res.matched_skills[:3])}. "
                        f"CTC Suggestion: {match_res.suggested_ctc_response}. Notice: Immediate."
                    ),
                    outreach_draft=(
                        f"Subject: Application for {title} - {cfg.candidate.name}\n\n"
                        f"Hi Hiring Team at {company},\n\n"
                        f"I noticed your {title} opening in {location}. With hands-on experience in "
                        f"{', '.join(match_res.matched_skills[:3])}, I would love to connect and share my portfolio.\n\n"
                        f"Best regards,\n{cfg.candidate.name}\n{cfg.candidate.phone}"
                    )
                )

                storage.save_job(job_item)
                existing_links.add(job_url)
                summary["new_added"] += 1

        except Exception as e:
            # Silently handle network timeouts or platform blockers
            continue

    return summary

