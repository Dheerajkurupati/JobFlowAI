"""Local storage and state manager for the JobFlow-AI CRM.

Maintains job application stages, screening memory vault, and syncs
bidirectionally with data/Job_Tracker.xlsx.
"""

import json
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from src.tracker.excel_tracker import ExcelJobTracker


class JobItem(BaseModel):
    id: str
    date: str = Field(default_factory=lambda: date.today().isoformat())
    company: str
    title: str
    location: str = "Hyderabad"
    work_type: str = "Hybrid"
    job_link: str
    status: str = "discovered"  # discovered | needs_input | review | applied | interview | rejected
    match_score: int = 85
    matched_skills: List[str] = Field(default_factory=list)
    missing_skills: List[str] = Field(default_factory=list)
    screening_notes: str = ""
    recruiter_name: Optional[str] = None
    recruiter_url: Optional[str] = None
    outreach_draft: Optional[str] = None


class CRMStorage:
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.jobs_file = self.data_dir / "crm_jobs.json"
        self.memory_file = self.data_dir / "screening_memory.json"
        self.excel_tracker = ExcelJobTracker(file_path=str(self.data_dir / "Job_Tracker.xlsx"))
        self._init_defaults()

    def _init_defaults(self):
        """Initialize default storage files if not existing."""
        if not self.memory_file.exists():
            default_memory = {
                "notice_period": "Immediate (0 days)",
                "expected_ctc": "Negotiable / As per company budget",
                "current_ctc": "Fresher (0 LPA)",
                "willing_to_relocate": "Yes, to Hyderabad, Bengaluru, Chennai, or Pune",
                "comfortable_with_hybrid": "Yes",
                "require_visa_sponsorship": "No",
                "previously_employed": "No"
            }
            with open(self.memory_file, "w", encoding="utf-8") as f:
                json.dump(default_memory, f, indent=2)

        if not self.jobs_file.exists():
            # Seed with starter sample jobs so user sees the live CRM immediately
            initial_jobs = [
                {
                    "id": "job-1",
                    "date": date.today().isoformat(),
                    "company": "Cognizant",
                    "title": "Junior AI / Python Developer",
                    "location": "Hyderabad",
                    "work_type": "Hybrid",
                    "job_link": "https://www.naukri.com/job-listings-python-dev-12345",
                    "status": "applied",
                    "match_score": 88,
                    "matched_skills": ["Python", "FastAPI", "LangChain", "SQL"],
                    "missing_skills": ["Docker in production"],
                    "screening_notes": "88% Match, FastAPI + LangChain match. Screening: Notice = Immediate, Previously employed = No.",
                    "recruiter_name": "Priya Sharma - Technical Hiring",
                    "recruiter_url": "https://www.linkedin.com/in/recruiter-priya",
                    "outreach_draft": "Hi Priya, I noticed Cognizant is hiring a Junior AI/Python Developer in Hyderabad. I recently built JobFlow-AI with FastAPI and LangChain, matching the requirements closely. Would love to connect!"
                },
                {
                    "id": "job-2",
                    "date": date.today().isoformat(),
                    "company": "Williams Lea",
                    "title": "Finance / Data Analyst",
                    "location": "Remote",
                    "work_type": "Remote",
                    "job_link": "https://www.naukri.com/job-listings-data-analyst-67890",
                    "status": "review",
                    "match_score": 92,
                    "matched_skills": ["Python", "Pandas", "SQL", "Reporting"],
                    "missing_skills": [],
                    "screening_notes": "92% Match. All screening answers verified. Ready for 1-click submission review.",
                    "recruiter_name": None,
                    "recruiter_url": None,
                    "outreach_draft": None
                },
                {
                    "id": "job-3",
                    "date": date.today().isoformat(),
                    "company": "TechMahindra",
                    "title": "Associate AI Engineer",
                    "location": "Bengaluru",
                    "work_type": "On-site",
                    "job_link": "https://www.naukri.com/job-listings-ai-eng-99887",
                    "status": "needs_input",
                    "match_score": 79,
                    "matched_skills": ["Python", "NLP", "Machine Learning"],
                    "missing_skills": ["AWS SageMaker"],
                    "screening_notes": "Needs your input: Company asks 'Are you willing to sign a 1-year service commitment?'",
                    "recruiter_name": "Arun Kumar - Talent Acquisition",
                    "recruiter_url": "https://www.linkedin.com/in/arun-kumar-hr",
                    "outreach_draft": None
                }
            ]
            with open(self.jobs_file, "w", encoding="utf-8") as f:
                json.dump(initial_jobs, f, indent=2)

    def get_all_jobs(self) -> List[Dict]:
        if not self.jobs_file.exists():
            return []
        with open(self.jobs_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_job(self, job: JobItem) -> None:
        jobs = self.get_all_jobs()
        # Update or append
        existing_idx = next((i for i, j in enumerate(jobs) if j["id"] == job.id), None)
        if existing_idx is not None:
            jobs[existing_idx] = job.model_dump()
        else:
            jobs.insert(0, job.model_dump())

        with open(self.jobs_file, "w", encoding="utf-8") as f:
            json.dump(jobs, f, indent=2)

    def update_job_status(self, job_id: str, new_status: str, notes: Optional[str] = None) -> Optional[Dict]:
        jobs = self.get_all_jobs()
        for j in jobs:
            if j["id"] == job_id:
                j["status"] = new_status
                if notes:
                    j["screening_notes"] = notes
                with open(self.jobs_file, "w", encoding="utf-8") as f:
                    json.dump(jobs, f, indent=2)
                # If moved to applied, sync to excel tracker
                if new_status == "applied":
                    self.sync_job_to_excel(j)
                return j
        return None

    def get_memory(self) -> Dict[str, str]:
        if not self.memory_file.exists():
            return {}
        with open(self.memory_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def update_memory(self, key: str, value: str) -> Dict[str, str]:
        memory = self.get_memory()
        memory[key] = value
        with open(self.memory_file, "w", encoding="utf-8") as f:
            json.dump(memory, f, indent=2)
        return memory

    def sync_job_to_excel(self, job_dict: Dict) -> None:
        """Sync an applied job into data/Job_Tracker.xlsx."""
        self.excel_tracker.log_application(
            company=job_dict.get("company", "Unknown"),
            job_title=job_dict.get("title", "Role"),
            location=job_dict.get("location", "Hyderabad"),
            job_link=job_dict.get("job_link", ""),
            status="Applied",
            reason_notes=job_dict.get("screening_notes", "Applied via CRM Cockpit"),
            work_type=job_dict.get("work_type", "Hybrid"),
            run_date=job_dict.get("date"),
        )

    def get_candidate_profile(self) -> Dict:
        profile_file = self.data_dir / "candidate_profile.json"
        if profile_file.exists():
            try:
                with open(profile_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass

        # Fallback to config settings / sample resume
        from src.config import load_config
        cfg = load_config()
        resume_exists = Path(cfg.candidate.resume_path).exists()
        return {
            "name": cfg.candidate.name,
            "email": cfg.candidate.email,
            "phone": cfg.candidate.phone,
            "city": cfg.candidate.city,
            "linkedin": "",
            "github": "",
            "skills": ["Python", "FastAPI", "SQL", "Machine Learning", "LLM", "RAG"],
            "primary_roles": ["AI Engineer", "Python Developer"],
            "target_locations": ["Hyderabad", "Bengaluru", "Chennai", "Pune", "Remote India"],
            "resume_path": cfg.candidate.resume_path,
            "resume_filename": Path(cfg.candidate.resume_path).name,
            "resume_uploaded": resume_exists
        }

    def save_candidate_profile(self, profile_data: Dict) -> Dict:
        profile_file = self.data_dir / "candidate_profile.json"
        current = self.get_candidate_profile()
        current.update(profile_data)
        with open(profile_file, "w", encoding="utf-8") as f:
            json.dump(current, f, indent=2)
        return current

    def save_uploaded_resume(self, file_bytes: bytes, filename: str) -> Dict:
        ext = Path(filename).suffix.lower() or ".pdf"
        target_path = self.data_dir / f"uploaded_resume{ext}"
        with open(target_path, "wb") as f:
            f.write(file_bytes)

        from src.parser.pdf_reader import parse_resume_to_profile
        current = self.get_candidate_profile()
        try:
            parsed = parse_resume_to_profile(str(target_path))
            parsed_dict = {
                "name": parsed.name if parsed.name and parsed.name != "Candidate" else current.get("name"),
                "email": parsed.email if parsed.email else current.get("email"),
                "phone": parsed.phone if parsed.phone else current.get("phone"),
                "city": parsed.city if parsed.city else current.get("city"),
                "linkedin": parsed.linkedin if parsed.linkedin else current.get("linkedin"),
                "github": parsed.github if parsed.github else current.get("github"),
                "skills": parsed.skills if parsed.skills else current.get("skills"),
                "primary_roles": parsed.primary_roles if parsed.primary_roles else current.get("primary_roles"),
                "resume_path": str(target_path),
                "resume_filename": filename,
                "resume_uploaded": True
            }
            return self.save_candidate_profile(parsed_dict)
        except Exception:
            fallback_dict = {
                "resume_path": str(target_path),
                "resume_filename": filename,
                "resume_uploaded": True
            }
            return self.save_candidate_profile(fallback_dict)

