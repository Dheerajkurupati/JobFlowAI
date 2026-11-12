"""Intelligent ATS & Career Page Form-Filler.

Detects form inputs, maps candidate fields with fuzzy matching,
answers screening questions from permanent memory, uploads resume,
and strictly pauses before submission.
"""

import re
from pathlib import Path
from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from src.parser.profile_schema import CandidateProfile
from src.server.storage import CRMStorage


class FillResult(BaseModel):
    fields_filled: List[str] = Field(default_factory=list)
    resume_uploaded: bool = False
    questions_answered: Dict[str, str] = Field(default_factory=dict)
    unanswered_questions: List[str] = Field(default_factory=list)
    status: str = "ready_for_review"  # ready_for_review | needs_user_input | blocked
    audit_notes: str = ""


class FormFiller:
    """Automates form interaction safely using Playwright page context."""

    def __init__(self, profile: CandidateProfile, memory: Optional[Dict[str, str]] = None):
        self.profile = profile
        self.storage = CRMStorage()
        self.memory = memory or self.storage.get_memory()

    async def fill_application(self, page, resume_path: Optional[str] = None) -> FillResult:
        """Fill application form fields on the active page.
        
        Args:
            page: Playwright Page instance.
            resume_path: Path to candidate resume file.
            
        Returns:
            FillResult summarizing all actions taken.
        """
        result = FillResult()
        effective_resume = resume_path or self.profile.resume_path or "data/resume.pdf"

        # 1. Fill Name fields
        first_name = self.profile.name.split()[0] if self.profile.name else "Candidate"
        last_name = " ".join(self.profile.name.split()[1:]) if len(self.profile.name.split()) > 1 else ""

        if await self._try_fill(page, ['input[name*="first_name" i]', 'input[name*="firstName" i]', 'input[id*="first_name" i]'], first_name):
            result.fields_filled.append("First Name")
            if last_name:
                if await self._try_fill(page, ['input[name*="last_name" i]', 'input[name*="lastName" i]', 'input[id*="last_name" i]'], last_name):
                    result.fields_filled.append("Last Name")
        else:
            if await self._try_fill(page, ['input[name*="name" i]', 'input[id*="name" i]', 'input[autocomplete="name"]'], self.profile.name):
                result.fields_filled.append("Full Name")

        # 2. Fill Email
        if self.profile.email:
            if await self._try_fill(page, ['input[type="email"]', 'input[name*="email" i]', 'input[id*="email" i]'], self.profile.email):
                result.fields_filled.append("Email")

        # 3. Fill Phone / Mobile
        if self.profile.phone:
            if await self._try_fill(page, ['input[type="tel"]', 'input[name*="phone" i]', 'input[name*="mobile" i]', 'input[id*="phone" i]'], self.profile.phone):
                result.fields_filled.append("Phone")

        # 4. Fill Location / City
        if self.profile.city:
            if await self._try_fill(page, ['input[name*="location" i]', 'input[name*="city" i]', 'input[id*="city" i]'], self.profile.city):
                result.fields_filled.append("City / Location")

        # 5. Fill LinkedIn & GitHub URLs
        if self.profile.linkedin_url:
            if await self._try_fill(page, ['input[name*="linkedin" i]', 'input[id*="linkedin" i]'], self.profile.linkedin_url):
                result.fields_filled.append("LinkedIn URL")

        if self.profile.github_url:
            if await self._try_fill(page, ['input[name*="github" i]', 'input[id*="github" i]'], self.profile.github_url):
                result.fields_filled.append("GitHub URL")

        # 6. Upload Resume File
        if Path(effective_resume).exists():
            file_inputs = page.locator('input[type="file"]')
            count = await file_inputs.count()
            if count > 0:
                try:
                    await file_inputs.first.set_input_files(effective_resume)
                    result.resume_uploaded = True
                    result.fields_filled.append("Resume PDF")
                except Exception:
                    pass

        # 7. Answer Custom Screening Questions from Memory
        await self._answer_screening_questions(page, result)

        # 8. Check for mandatory unanswered questions
        if result.unanswered_questions:
            result.status = "needs_user_input"
            result.audit_notes = f"Form filled with {len(result.fields_filled)} fields. Needs input for: {', '.join(result.unanswered_questions)}"
        else:
            result.status = "ready_for_review"
            result.audit_notes = f"All {len(result.fields_filled)} fields filled. Resume attached. Ready for review."

        return result

    async def _try_fill(self, page, selectors: List[str], value: str) -> bool:
        """Attempt to fill the first matching input selector."""
        for selector in selectors:
            loc = page.locator(selector)
            if await loc.count() > 0:
                try:
                    first_loc = loc.first
                    if await first_loc.is_visible():
                        await first_loc.fill(value)
                        return True
                except Exception:
                    continue
        return False

    async def _answer_screening_questions(self, page, result: FillResult) -> None:
        """Scan page inputs for screening questions and match with memory vault."""
        # Find all textareas and text inputs that are not already filled
        inputs = page.locator('textarea, input[type="text"]:not([value])')
        count = await inputs.count()

        for i in range(count):
            try:
                inp = inputs.nth(i)
                if not await inp.is_visible():
                    continue

                # Retrieve associated label text
                label_text = await self._get_input_label(inp)
                if not label_text or len(label_text) < 3:
                    continue

                label_lower = label_text.lower()

                # Check against known memory keys
                matched_answer = self._find_matching_memory_answer(label_lower)
                if matched_answer:
                    await inp.fill(matched_answer)
                    result.questions_answered[label_text[:40]] = matched_answer
                    result.fields_filled.append(f"Screening: {label_text[:30]}")
                else:
                    # If field is marked required and not answered, record it
                    is_required = await inp.get_attribute("required") is not None
                    if is_required and not await inp.input_value():
                        result.unanswered_questions.append(label_text[:50])

            except Exception:
                continue

    async def _get_input_label(self, locator) -> str:
        """Retrieve the text of the associated label or placeholder."""
        try:
            input_id = await locator.get_attribute("id")
            if input_id:
                label = locator.page.locator(f'label[for="{input_id}"]')
                if await label.count() > 0:
                    return (await label.first.text_content() or "").strip()

            placeholder = await locator.get_attribute("placeholder")
            if placeholder:
                return placeholder.strip()

            name = await locator.get_attribute("name")
            if name:
                return name.replace("_", " ").strip()
        except Exception:
            pass
        return ""

    def _find_matching_memory_answer(self, label_text: str) -> Optional[str]:
        """Fuzzy-match question label to memory bank."""
        if any(k in label_text for k in ["notice", "availability", "how soon"]):
            return self.memory.get("notice_period", "Immediate (0 days)")

        if any(k in label_text for k in ["expected ctc", "salary expectation", "expected salary", "compensation"]):
            return self.memory.get("expected_ctc", "Negotiable / As per company budget")

        if any(k in label_text for k in ["current ctc", "current salary", "present ctc"]):
            return self.memory.get("current_ctc", "0 LPA (Fresher)")

        if any(k in label_text for k in ["relocate", "relocation"]):
            return self.memory.get("willing_to_relocate", "Yes")

        if any(k in label_text for k in ["hybrid", "work from office"]):
            return self.memory.get("comfortable_with_hybrid", "Yes")

        if any(k in label_text for k in ["authorized", "work in india", "legal right"]):
            return self.memory.get("authorized_to_work_in_india", "Yes")

        if any(k in label_text for k in ["previously employed", "worked here"]):
            return self.memory.get("previously_employed", "No")

        return None
