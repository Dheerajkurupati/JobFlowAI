"""Enhanced FastAPI backend application for JobFlow-AI Enterprise CRM."""

import re
import uuid
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional
import httpx
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException, Request, Query, UploadFile, File
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from src.server.storage import CRMStorage, JobItem
from src.config import load_config

app = FastAPI(title="JobFlow-AI CRM", version="0.2.0")

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
storage = CRMStorage()
config = load_config()


class QuickIngestRequest(BaseModel):
    url: str


class StatusUpdateRequest(BaseModel):
    status: str
    notes: Optional[str] = None


class MemoryUpdateRequest(BaseModel):
    key: str
    value: str


class AutoFillRequest(BaseModel):
    headless: bool = False
    pause_for_review: bool = True
    review_timeout_seconds: int = 15


class EmailSyncRequest(BaseModel):
    simulate: bool = False


class ProfileUpdateRequest(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    city: Optional[str] = None
    linkedin: Optional[str] = None
    github: Optional[str] = None
    skills: Optional[List[str]] = None
    primary_roles: Optional[List[str]] = None
    target_locations: Optional[List[str]] = None


@app.get("/", response_class=HTMLResponse)
async def serve_dashboard(request: Request):
    """Render the enterprise CRM Dashboard."""
    candidate_profile = storage.get_candidate_profile()
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"candidate": candidate_profile}
    )


@app.get("/api/jobs")
async def get_jobs(
    search: Optional[str] = None,
    status: Optional[str] = "all",
    location: Optional[str] = "all",
    page: int = 1,
    page_size: int = 20
):
    """Retrieve jobs with search, filtering, and pagination support."""
    all_jobs = storage.get_all_jobs()
    
    # 1. Filter by Status
    filtered = all_jobs
    if status and status != "all":
        filtered = [j for j in filtered if j.get("status") == status]

    # 2. Filter by Location
    if location and location != "all":
        loc_lower = location.lower()
        filtered = [j for j in filtered if loc_lower in j.get("location", "").lower()]

    # 3. Search query across company, title, skills, and notes
    if search:
        q = search.lower().strip()
        filtered = [
            j for j in filtered
            if q in j.get("company", "").lower()
            or q in j.get("title", "").lower()
            or q in j.get("location", "").lower()
            or any(q in s.lower() for s in j.get("matched_skills", []))
            or q in j.get("screening_notes", "").lower()
        ]

    # Overall pipeline counts
    counts = {
        "all": len(all_jobs),
        "discovered": sum(1 for j in all_jobs if j.get("status") == "discovered"),
        "needs_input": sum(1 for j in all_jobs if j.get("status") == "needs_input"),
        "review": sum(1 for j in all_jobs if j.get("status") == "review"),
        "applied": sum(1 for j in all_jobs if j.get("status") == "applied"),
        "interview": sum(1 for j in all_jobs if j.get("status") == "interview"),
        "rejected": sum(1 for j in all_jobs if j.get("status") == "rejected"),
    }

    # Grouping for Kanban view
    kanban_columns = {
        "discovered": [],
        "needs_input": [],
        "review": [],
        "applied": [],
        "interview": [],
        "rejected": []
    }
    for j in all_jobs:
        st = j.get("status", "discovered")
        if st in kanban_columns:
            kanban_columns[st].append(j)
        else:
            kanban_columns["discovered"].append(j)

    # Pagination for Table view
    total_count = len(filtered)
    total_pages = max((total_count + page_size - 1) // page_size, 1)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    paginated_jobs = filtered[start_idx:end_idx]

    return {
        "jobs": paginated_jobs,
        "kanban": kanban_columns,
        "counts": counts,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total_count": total_count,
            "total_pages": total_pages
        }
    }


@app.post("/api/jobs/quick-ingest")
async def quick_ingest_job(req: QuickIngestRequest):
    """Scrape and analyze any pasted job link in 1-2 seconds."""
    url = req.url.strip()
    if not url.startswith("http"):
        raise HTTPException(status_code=400, detail="Invalid URL. Please enter a valid http/https link.")

    title = "Software / AI Developer"
    company = "Tech Company"
    location = "Hyderabad / Remote"
    raw_text = ""

    try:
        async with httpx.AsyncClient(timeout=4.0, follow_redirects=True) as client:
            headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                page_title = soup.title.string if soup.title else ""
                if page_title:
                    parts = re.split(r"[-|–—]", page_title)
                    if len(parts) >= 2:
                        title = parts[0].strip()
                        company = parts[1].strip()
                    else:
                        title = page_title.strip()[:40]

                raw_text = soup.get_text(separator=" ", strip=True).lower()
    except Exception:
        domain_match = re.search(r"https?://(?:www\.)?([^/]+)", url)
        if domain_match:
            company = domain_match.group(1).split(".")[0].capitalize()

    # Dynamic Keyword & Match Evaluation via Brain Matcher
    from src.brain.matcher import calculate_ats_match
    from src.parser.pdf_reader import parse_resume_to_profile

    # Load candidate profile
    cand_p = storage.get_candidate_profile()
    resume_path = Path(cand_p.get("resume_path") or config.candidate.resume_path)
    if not resume_path.exists():
        resume_path = Path("data/sample_resume.txt")

    try:
        profile = parse_resume_to_profile(str(resume_path))
    except Exception:
        profile = None

    if profile:
        match_res = calculate_ats_match(profile, raw_text, raw_text)
        matched = match_res.matched_skills
        missing = match_res.missing_skills
        match_score = match_res.match_score
        ctc_response = match_res.suggested_ctc_response
        roadmap_notes = " | ".join(match_res.learning_roadmap[:2])
    else:
        tech_keywords = ["python", "fastapi", "rag", "llm", "langchain", "sql", "docker", "pytorch", "pandas"]
        matched = [k.capitalize() for k in tech_keywords if k in raw_text] or ["Python", "FastAPI"]
        missing = ["Kubernetes"] if "kubernetes" in raw_text else []
        match_score = min(max(70 + len(matched) * 4, 75), 94)
        ctc_response = "Negotiable / As per company budget"
        roadmap_notes = ""

    screening_notes = (
        f"ATS Match: {match_score}%. Matched: {', '.join(matched[:4])}. "
        f"Expected CTC: {ctc_response}. Notice: Immediate."
    )
    if roadmap_notes:
        screening_notes += f" Prep Tip: {roadmap_notes}"

    new_job = JobItem(
        id=f"job-{uuid.uuid4().hex[:6]}",
        date=date.today().isoformat(),
        company=company,
        title=title,
        location=location,
        work_type="Hybrid",
        job_link=url,
        status="review" if match_score >= 80 else "discovered",
        match_score=match_score,
        matched_skills=matched,
        missing_skills=missing,
        screening_notes=screening_notes,
        recruiter_name=None,
        recruiter_url=None,
        outreach_draft=f"Hi Hiring Team at {company},\n\nI noticed your opening for {title} in {location}. With hands-on experience in {', '.join(matched[:3])}, I would love to connect and share my portfolio.\n\nBest,\n{cand_p.get('name') or config.candidate.name}"
    )

    storage.save_job(new_job)
    return {"message": "Job successfully ingested", "job": new_job.model_dump()}


@app.post("/api/jobs/{job_id}/status")
async def update_status(job_id: str, req: StatusUpdateRequest):
    updated = storage.update_job_status(job_id, req.status, req.notes)
    if not updated:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"message": "Status updated", "job": updated}


@app.post("/api/jobs/{job_id}/approve")
async def approve_and_apply(job_id: str):
    approval_note = f"Approved & Applied on {date.today().isoformat()}. Screening: Notice=Immediate, Relocation=Yes."
    updated = storage.update_job_status(job_id, "applied", approval_note)
    if not updated:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"message": "Application Approved & Logged to Excel", "job": updated}


@app.get("/api/memory")
async def get_memory():
    return storage.get_memory()


@app.post("/api/memory")
async def save_memory(req: MemoryUpdateRequest):
    updated = storage.update_memory(req.key.strip(), req.value.strip())
    return {"message": "Memory updated", "memory": updated}


@app.get("/api/profile")
async def get_profile():
    """Retrieve active candidate profile and resume upload status."""
    return storage.get_candidate_profile()


@app.post("/api/profile")
async def update_profile(req: ProfileUpdateRequest):
    """Manually update candidate contact details and skills from dashboard."""
    update_data = {k: v for k, v in req.model_dump().items() if v is not None}
    updated = storage.save_candidate_profile(update_data)
    return {"message": "Profile updated successfully", "profile": updated}


@app.post("/api/profile/upload-resume")
async def upload_resume(file: UploadFile = File(...)):
    """Upload resume (PDF, TXT, MD), parse skills & contacts, and update active profile."""
    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Empty file uploaded")

    updated_profile = storage.save_uploaded_resume(content, file.filename)
    return {
        "message": "Resume uploaded & parsed successfully",
        "profile": updated_profile
    }


@app.post("/api/jobs/{job_id}/outreach")
async def generate_outreach(job_id: str):
    jobs = storage.get_all_jobs()
    target = next((j for j in jobs if j["id"] == job_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Job not found")

    company = target.get("company", "the team")
    title = target.get("title", "this role")
    skills = ", ".join(target.get("matched_skills", ["Python", "AI", "FastAPI"]))
    recruiter = target.get("recruiter_name") or "Hiring Manager"
    first_name = recruiter.split()[0] if recruiter else "there"
    cand_p = storage.get_candidate_profile()
    cand_name = cand_p.get("name") or config.candidate.name
    cand_phone = cand_p.get("phone") or config.candidate.phone
    cand_city = cand_p.get("city") or config.candidate.city

    draft = (
        f"Subject: Application for {title} - {cand_name}\n\n"
        f"Hi {first_name},\n\n"
        f"I came across the {title} opening at {company} and wanted to reach out directly. "
        f"I have hands-on experience building autonomous AI systems and REST APIs with {skills}.\n\n"
        f"Recently, I engineered JobFlow-AI with RAG, Playwright automation, and FastAPI. "
        f"I'm based in {cand_city} and available to join immediately.\n\n"
        f"Looking forward to connecting!\n\n"
        f"Best regards,\n{cand_name}\n{cand_phone}"
    )

    target["outreach_draft"] = draft
    storage.save_job(JobItem(**target))
    return {"outreach_draft": draft}


@app.post("/api/harvest")
async def trigger_harvest():
    """Trigger concurrent multi-board job harvesting across LinkedIn, Indeed, Glassdoor, and ZipRecruiter."""
    from src.harvester.multi_scraper import harvest_jobs_across_platforms
    summary = harvest_jobs_across_platforms(
        config=config,
        platforms=["linkedin", "indeed", "glassdoor", "ziprecruiter"],
        max_results_per_platform=10
    )
    return {"message": "Harvest complete", "summary": summary}


@app.get("/api/export-excel")
async def export_excel():
    """Trigger download of the formatted data/Job_Tracker.xlsx spreadsheet."""
    path = Path("data/Job_Tracker.xlsx")
    if not path.exists():
        raise HTTPException(status_code=404, detail="Excel file not yet generated")
    return FileResponse(
        path=path,
        filename="Job_Tracker.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


@app.post("/api/jobs/{job_id}/auto-fill")
async def auto_fill_job(job_id: str, req: Optional[AutoFillRequest] = None):
    """Run Playwright autonomous browser form-filler with safety pause for user review."""
    from src.agent.browser_pilot import BrowserPilot

    jobs = storage.get_all_jobs()
    target = next((j for j in jobs if j["id"] == job_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Job not found")

    job_url = target.get("job_link", "")
    if not job_url or not job_url.startswith("http"):
        raise HTTPException(status_code=400, detail="Job has no valid application link")

    options = req or AutoFillRequest()
    pilot = BrowserPilot(config=config)

    result = await pilot.run_application(
        job_url=job_url,
        headless=options.headless,
        pause_for_review=options.pause_for_review,
        review_timeout_seconds=options.review_timeout_seconds
    )

    # Update CRM status if unanswered questions or review ready
    new_status = target.get("status", "review")
    if result.status == "needs_user_input":
        new_status = "needs_input"
    elif result.status in ["ready_for_review", "submitted"]:
        new_status = "review"

    audit_note = f"Auto-fill: {len(result.fields_filled)} fields populated. {result.audit_notes}"
    current_notes = target.get("screening_notes", "")
    storage.update_job_status(job_id, new_status, f"{current_notes} | {audit_note}")

    return {
        "message": "Auto-fill pass complete",
        "result": result.model_dump()
    }


@app.post("/api/email-sync")
async def sync_emails(req: Optional[EmailSyncRequest] = None):
    """Sync recruiter replies, interview invites, coding assessments, and rejections into CRM."""
    from src.brain.email_feedback import EmailFeedbackEngine

    simulate = req.simulate if req else False
    engine = EmailFeedbackEngine(storage=storage)

    if simulate:
        results = engine.sync_simulated_feedback()
    else:
        results = engine.sync_live_inbox()

    return {
        "message": f"Processed {len(results)} email loop events",
        "events": [r.model_dump() for r in results]
    }
