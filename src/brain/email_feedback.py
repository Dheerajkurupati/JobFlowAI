"""Closed-Loop Email Feedback Engine for JobFlow-AI.

Scans incoming recruiter emails (via IMAP SSL or simulation mode),
classifies updates (Interview, Online Assessment, Shortlisted, Rejection, Offer),
matches them against applied jobs in the CRM and Excel tracker, and automatically
updates application statuses in a closed-loop feedback mechanism.
"""

import email
import imaplib
import os
import re
from datetime import datetime
from email.header import decode_header
from typing import Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

from src.server.storage import CRMStorage, JobItem
from src.tracker.excel_tracker import ExcelJobTracker
from src.config import load_config


class EmailFeedbackItem(BaseModel):
    """Represents a classified email feedback event."""
    company: str
    detected_status: str  # "interview", "review", "rejected", "applied"
    status_label: str  # e.g. "Interview Scheduled", "Online Assessment", "Shortlisted", "Rejected", "Offer Received"
    email_subject: str
    sender: str
    snippet: str
    timestamp: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M"))
    action_taken: str = ""


class EmailFeedbackEngine:
    """Intelligent recruiter response detector and pipeline loop synchronizer."""

    # High-precision classification patterns
    PATTERNS = {
        "OFFER": [
            r"offer letter",
            r"pleased to offer you",
            r"formal offer",
            r"employment offer",
            r"congratulations on your offer",
        ],
        "INTERVIEW_INVITE": [
            r"schedule (?:an|a|your) interview",
            r"invitation to interview",
            r"interview scheduled",
            r"technical discussion",
            r"calendly\.com",
            r"zoom\.us\/j\/",
            r"meet\.google\.com\/",
            r"teams\.microsoft\.com",
            r"round \d+ interview",
            r"discussion regarding your application",
            r"screening call",
            r"first round of discussion",
        ],
        "ONLINE_ASSESSMENT": [
            r"online assessment",
            r"coding (?:test|challenge|assessment)",
            r"hackerrank\.com",
            r"codility\.com",
            r"complete (?:the|this) assessment",
            r"technical test link",
            r"hirevue",
            r"take-home assignment",
        ],
        "SHORTLISTED": [
            r"profile (?:has been |is )?shortlisted",
            r"selected for the next (?:round|stage|step)",
            r"impressed with your profile",
            r"advancing your candidacy",
        ],
        "REJECTION": [
            r"unfortunately",
            r"not moving forward",
            r"other candidates",
            r"after careful consideration",
            r"decided to pursue other",
            r"position has been filled",
            r"unable to offer you an interview",
            r"will not be progressing",
            r"future endeavors",
        ]
    }

    def __init__(self, storage: Optional[CRMStorage] = None, excel_path: str = "data/Job_Tracker.xlsx"):
        self.storage = storage or CRMStorage()
        self.excel_tracker = ExcelJobTracker(file_path=excel_path)
        self.config = load_config()

    def classify_email(self, subject: str, body: str, sender: str) -> Optional[Tuple[str, str]]:
        """Classify email text into a recruitment event status.
        
        Returns:
            Tuple of (crm_status, display_label) or None if not recruitment related.
        """
        combined = f"{subject} {body}".lower()

        # Priority 1: Offer
        for pattern in self.PATTERNS["OFFER"]:
            if re.search(pattern, combined):
                return "interview", "Offer Received 🎉"

        # Priority 2: Interview Invite
        for pattern in self.PATTERNS["INTERVIEW_INVITE"]:
            if re.search(pattern, combined):
                return "interview", "Interview Scheduled 📅"

        # Priority 3: Online Assessment
        for pattern in self.PATTERNS["ONLINE_ASSESSMENT"]:
            if re.search(pattern, combined):
                return "needs_input", "Online Assessment 💻"

        # Priority 4: Shortlisted
        for pattern in self.PATTERNS["SHORTLISTED"]:
            if re.search(pattern, combined):
                return "interview", "Shortlisted ⭐"

        # Priority 5: Rejection
        for pattern in self.PATTERNS["REJECTION"]:
            if re.search(pattern, combined):
                return "rejected", "Rejected"

        return None

    def find_matching_job(self, subject: str, body: str, sender: str) -> Optional[Dict]:
        """Find an existing tracked job in CRM that matches this email."""
        jobs = self.storage.get_all_jobs()
        combined = f"{subject} {sender} {body}".lower()

        # Extract domain from sender
        domain_match = re.search(r"@([a-zA-Z0-9.-]+)", sender)
        sender_domain = domain_match.group(1).lower() if domain_match else ""

        for job in jobs:
            company_name = job.get("company", "").strip().lower()
            if not company_name or len(company_name) < 2:
                continue

            # 1. Exact company name in text or subject
            if company_name in combined:
                return job

            # 2. Domain matching (e.g. google in google.com)
            company_slug = re.sub(r"[^a-z0-9]", "", company_name)
            if company_slug and company_slug in sender_domain:
                return job

        return None

    def process_feedback(
        self,
        company: str,
        detected_status: str,
        status_label: str,
        subject: str,
        sender: str,
        snippet: str
    ) -> EmailFeedbackItem:
        """Apply the loop update to CRM storage and Excel."""
        jobs = self.storage.get_all_jobs()
        target_job = None
        for j in jobs:
            if j.get("company", "").lower() == company.lower():
                target_job = j
                break

        action_note = f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] Recruiter Email: {status_label} ({subject[:40]})"

        if target_job:
            # Update CRM storage
            current_notes = target_job.get("screening_notes", "") or ""
            # Avoid repeating the exact same recruiter event in notes
            if f"Recruiter Email: {status_label}" in current_notes or subject[:35] in current_notes:
                updated_notes = current_notes
            else:
                updated_notes = f"{current_notes} | {action_note}" if current_notes else action_note
            self.storage.update_job_status(target_job["id"], detected_status, updated_notes)

            # Update Excel tracker
            self.excel_tracker.log_application(
                company=target_job.get("company", company),
                job_title=target_job.get("title", "Software Engineer"),
                location=target_job.get("location", "Hyderabad"),
                job_link=target_job.get("job_link", ""),
                status=status_label,
                reason_notes=action_note,
                work_type=target_job.get("work_type", "Hybrid")
            )
            action_summary = f"Updated CRM & Excel for {company} -> {status_label}"
        else:
            action_summary = f"No active application found matching {company} (Ignored)"

        return EmailFeedbackItem(
            company=company,
            detected_status=detected_status,
            status_label=status_label,
            email_subject=subject,
            sender=sender,
            snippet=snippet[:120],
            action_taken=action_summary
        )

    def sync_simulated_feedback(self, persist: bool = False) -> List[EmailFeedbackItem]:
        """Simulate recruiter responses for testing the closed-loop mechanism without modifying real applications unless persist=True."""
        jobs = self.storage.get_all_jobs()
        if not jobs:
            return []

        # Pick candidate companies from existing jobs
        feedback_results = []
        templates = [
            (
                "Interview Scheduled 📅",
                "interview",
                "Invitation to Interview: AI Engineer Discussion Round 1",
                "talent@{company_slug}.com",
                "Hi, We were very impressed by your JobFlow-AI project and would like to invite you for a 45-minute technical discussion next Monday."
            ),
            (
                "Online Assessment 💻",
                "needs_input",
                "Next Steps: Complete Your HackerRank Coding Challenge",
                "assessments@{company_slug}.com",
                "Please find your assessment link enclosed. You have 72 hours to complete the 90-minute Python & Algorithms challenge."
            ),
            (
                "Rejected",
                "rejected",
                "Update regarding your application for AI Developer",
                "recruiting@{company_slug}.com",
                "Thank you for your interest. While your profile has strong skills, we have decided to pursue candidates with different qualifications at this time."
            )
        ]

        # Apply simulation to up to 3 jobs
        for i, job in enumerate(jobs[:3]):
            tmpl = templates[i % len(templates)]
            company = job.get("company", "Company")
            slug = re.sub(r"[^a-z0-9]", "", company.lower()) or "company"
            
            status_label = tmpl[0]
            crm_status = tmpl[1]
            subject = tmpl[2]
            sender = tmpl[3].format(company_slug=slug)
            snippet = tmpl[4]

            if persist:
                item = self.process_feedback(
                    company=company,
                    detected_status=crm_status,
                    status_label=status_label,
                    subject=subject,
                    sender=sender,
                    snippet=snippet
                )
            else:
                item = EmailFeedbackItem(
                    company=company,
                    detected_status=crm_status,
                    status_label=status_label,
                    email_subject=subject,
                    sender=sender,
                    snippet=snippet[:120],
                    action_taken="Simulated preview (No changes applied to CRM)"
                )
            feedback_results.append(item)

        return feedback_results

    def sync_live_inbox(
        self,
        imap_host: str = "imap.gmail.com",
        username: Optional[str] = None,
        password: Optional[str] = None,
        max_emails: int = 15
    ) -> List[EmailFeedbackItem]:
        """Connect to live IMAP server (SSL) and process incoming recruiter emails.
        
        Credentials can be passed explicitly or read from environment variables:
        EMAIL_IMAP_SERVER, EMAIL_ACCOUNT, EMAIL_APP_PASSWORD.
        """
        user = username or os.getenv("EMAIL_ACCOUNT") or os.getenv("EMAIL_USER")
        pwd = password or os.getenv("EMAIL_APP_PASSWORD") or os.getenv("EMAIL_PASSWORD")
        host = os.getenv("EMAIL_IMAP_SERVER", imap_host)

        if not user or not pwd:
            # Fallback to simulation mode if live credentials are not provided
            return self.sync_simulated_feedback()

        feedback_results = []
        try:
            # Connect via IMAP SSL
            mail = imaplib.IMAP4_SSL(host, timeout=10)
            mail.login(user, pwd)
            mail.select("INBOX", readonly=True)  # Read-only for safety

            # Search recent emails (last 14 days or UNSEEN)
            status, messages = mail.search(None, "ALL")
            if status != "OK" or not messages[0]:
                mail.logout()
                return []

            msg_ids = messages[0].split()
            # Check latest max_emails
            recent_ids = msg_ids[-max_emails:]

            for msg_id in reversed(recent_ids):
                res, data = mail.fetch(msg_id, "(RFC822)")
                if res != "OK":
                    continue

                raw_email = data[0][1]
                msg = email.message_from_bytes(raw_email)

                # Decode subject
                subject_header = decode_header(msg.get("Subject", ""))[0]
                subject = subject_header[0]
                if isinstance(subject, bytes):
                    subject = subject.decode(subject_header[1] or "utf-8", errors="ignore")

                sender = msg.get("From", "")

                # Extract plain text body
                body = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        content_type = part.get_content_type()
                        if content_type == "text/plain":
                            body = part.get_payload(decode=True).decode("utf-8", errors="ignore")
                            break
                else:
                    body = msg.get_payload(decode=True).decode("utf-8", errors="ignore")

                # 1. Match company
                matched_job = self.find_matching_job(subject, body, sender)
                if not matched_job:
                    continue

                # 2. Classify intent
                classification = self.classify_email(subject, body, sender)
                if not classification:
                    continue

                detected_status, status_label = classification
                company = matched_job["company"]

                item = self.process_feedback(
                    company=company,
                    detected_status=detected_status,
                    status_label=status_label,
                    subject=subject,
                    sender=sender,
                    snippet=body[:150]
                )
                feedback_results.append(item)

            mail.logout()
        except Exception as e:
            # Graceful error handling
            print(f"[EmailFeedbackEngine] Live sync notice: {e}")
            return self.sync_simulated_feedback()

        return feedback_results
