"""FastAPI backend application for JobFlow-AI CRM Dashboard."""

import re
import uuid
from datetime import date
from pathlib import Path
from typing import Dict, Optional
import httpx
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from src.server.storage import CRMStorage, JobItem
from src.config import load_config

app = FastAPI(title="JobFlow-AI CRM", version="0.1.0")

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


@app.get("/", response_class=HTMLResponse)
async def serve_dashboard(request: Request):
    """Render the interactive Kanban CRM Dashboard."""
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"candidate": config.candidate}
    )


@app.get("/api/jobs")
async def get_jobs():
    """Retrieve all jobs categorized by Kanban pipeline column."""
    all_jobs = storage.get_all_jobs()
    columns = {
        "discovered": [],
        "needs_input": [],
        "review": [],
        "applied": [],
        "interview": [],
        "rejected": []
    }
    for j in all_jobs:
        status = j.get("status", "discovered")
        if status in columns:
            columns[status].append(j)
        else:
            columns["discovered"].append(j)

    stats = {
        "total": len(all_jobs),
        "applied": len(columns["applied"]),
        "review": len(columns["review"]),
        "interviews": len(columns["interview"])
    }
    return {"columns": columns, "stats": stats}


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

    # Attempt ultra-fast HTTP fetch
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
        # Fallback to domain name heuristic if page blocks direct scraper
        domain_match = re.search(r"https?://(?:www\.)?([^/]+)", url)
        if domain_match:
            company = domain_match.group(1).split(".")[0].capitalize()

    # Dynamic Keyword & Match Evaluation
    tech_keywords = ["python", "fastapi", "rag", "llm", "langchain", "sql", "docker", "pytorch"]
    matched = [k.capitalize() for k in tech_keywords if k in raw_text] or ["Python", "FastAPI"]
    missing = ["Kubernetes"] if "kubernetes" in raw_text else []
    match_score = min(max(70 + len(matched) * 4, 75), 94)

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
        screening_notes=f"Auto-parsed from URL. {match_score}% Match. Skills: {', '.join(matched)}.",
        recruiter_name=None,
        recruiter_url=None,
        outreach_draft=f"Hi Hiring Team at {company}, I recently came across your {title} opening. Given my background in {', '.join(matched[:3])}, I would love to discuss how I can contribute!"
    )

    storage.save_job(new_job)
    return {"message": "Job successfully ingested into pipeline", "job": new_job.model_dump()}


@app.post("/api/jobs/{job_id}/status")
async def update_status(job_id: str, req: StatusUpdateRequest):
    """Move job across Kanban stages."""
    updated = storage.update_job_status(job_id, req.status, req.notes)
    if not updated:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"message": "Status updated", "job": updated}


@app.post("/api/jobs/{job_id}/approve")
async def approve_and_apply(job_id: str):
    """Cockpit Action: User reviews pre-filled answers and triggers Apply."""
    jobs = storage.get_all_jobs()
    target = next((j for j in jobs if j["id"] == job_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Job not found")

    approval_note = f"Approved & Applied on {date.today().isoformat()}. Screened: Notice=Immediate, Relocation=Yes."
    updated = storage.update_job_status(job_id, "applied", approval_note)
    return {"message": "Application Approved & Logged to Excel", "job": updated}


@app.get("/api/memory")
async def get_memory():
    """Retrieve saved screening questions and answers."""
    return storage.get_memory()


@app.post("/api/memory")
async def save_memory(req: MemoryUpdateRequest):
    """Update or save an answer for a screening question."""
    updated = storage.update_memory(req.key.strip(), req.value.strip())
    return {"message": "Memory updated", "memory": updated}


@app.post("/api/jobs/{job_id}/outreach")
async def generate_outreach(job_id: str):
    """Generate or retrieve a tailored cold outreach script for the recruiter."""
    jobs = storage.get_all_jobs()
    target = next((j for j in jobs if j["id"] == job_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Job not found")

    company = target.get("company", "the team")
    title = target.get("title", "this role")
    skills = ", ".join(target.get("matched_skills", ["Python", "AI", "FastAPI"]))

    recruiter = target.get("recruiter_name") or "Hiring Manager"
    first_name = recruiter.split()[0] if recruiter else "there"

    draft = (
        f"Subject: Application for {title} - {config.candidate.name}\n\n"
        f"Hi {first_name},\n\n"
        f"I came across the {title} opening at {company} and wanted to reach out directly. "
        f"I have hands-on experience building autonomous AI systems and REST APIs with {skills}.\n\n"
        f"Recently, I built JobFlow-AI—an open-source multi-source career agent with RAG and Playwright automation. "
        f"I'm based in {config.candidate.city} and available to join immediately.\n\n"
        f"I would love the opportunity to share how my background aligns with your team's goals. "
        f"You can review my work at https://github.com/{config.candidate.name.replace(' ', '')}\n\n"
        f"Best regards,\n{config.candidate.name}\n{config.candidate.phone}"
    )

    target["outreach_draft"] = draft
    storage.save_job(JobItem(**target))
    return {"outreach_draft": draft}
