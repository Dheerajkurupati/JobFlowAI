"""Autonomous Browser Pilot with Strict Human-in-the-Loop Review Gate.

Launches visible Chromium browser session, navigates to application link,
fills fields via FormFiller, highlights completed inputs in green,
and pauses at the final step for user approval.
"""

import asyncio
from pathlib import Path
from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from playwright.async_api import async_playwright, Page, Browser
from src.config import AppConfig, load_config
from src.parser.profile_schema import CandidateProfile
from src.parser.pdf_reader import parse_resume_to_profile
from src.agent.form_filler import FormFiller, FillResult
from src.server.storage import CRMStorage


class ApplicationRunResult(BaseModel):
    success: bool
    status: str  # "ready_for_review" | "needs_user_input" | "blocked_login" | "submitted"
    job_url: str
    fields_filled: List[str] = Field(default_factory=list)
    questions_answered: Dict[str, str] = Field(default_factory=dict)
    unanswered_questions: List[str] = Field(default_factory=list)
    audit_notes: str = ""


class BrowserPilot:
    """Manages browser lifecycle, safety checks, and auto-filling."""

    def __init__(self, config: Optional[AppConfig] = None):
        self.config = config or load_config()
        self.storage = CRMStorage()

        # Load profile from live dashboard storage or fallback
        saved_p = self.storage.get_candidate_profile()
        resume_file = saved_p.get("resume_path") or self.config.candidate.resume_path
        try:
            self.profile = parse_resume_to_profile(resume_file)
        except Exception:
            self.profile = CandidateProfile(
                name=saved_p.get("name") or self.config.candidate.name,
                email=saved_p.get("email") or self.config.candidate.email,
                phone=saved_p.get("phone") or self.config.candidate.phone,
                city=saved_p.get("city") or self.config.candidate.city,
                linkedin=saved_p.get("linkedin", ""),
                github=saved_p.get("github", ""),
                skills=saved_p.get("skills") or ["Python", "FastAPI", "AI"],
                primary_roles=saved_p.get("primary_roles") or ["AI Engineer"]
            )

        self.form_filler = FormFiller(self.profile)

    async def run_application(
        self,
        job_url: str,
        headless: bool = False,
        slow_mo_ms: int = 100,
        pause_for_review: bool = True,
        review_timeout_seconds: int = 15
    ) -> ApplicationRunResult:
        """Execute autonomous form-filling on a job application URL.
        
        Args:
            job_url: Web link to the job application.
            headless: False for visible browser window (Cockpit mode).
            slow_mo_ms: Artificial typing delay for human-like pacing.
            pause_for_review: If True, halts before final submit button.
            review_timeout_seconds: Time (seconds) to keep browser open for user review when headless=False.
            
        Returns:
            ApplicationRunResult with audit trail.
        """
        async with async_playwright() as p:
            # Launch Chromium browser
            browser: Browser = await p.chromium.launch(
                headless=headless,
                slow_mo=slow_mo_ms
            )
            context = await browser.new_context(
                viewport={"width": 1280, "height": 850},
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )
            page: Page = await context.new_page()

            try:
                # 1. Navigate to Job URL
                await page.goto(job_url, timeout=30000, wait_until="domcontentloaded")
                await page.wait_for_timeout(2000)

                # 2. Check for Login Gate / CAPTCHA (Safety check)
                if await self._detect_login_or_captcha(page):
                    return ApplicationRunResult(
                        success=False,
                        status="blocked_login",
                        job_url=job_url,
                        audit_notes="External login or CAPTCHA detected. Apply manually via direct link."
                    )

                # 3. Fill Form Inputs
                fill_res: FillResult = await self.form_filler.fill_application(page)

                # 4. Visual Highlight of Filled Fields (CSS injection for review)
                await page.evaluate("""
                    () => {
                        const inputs = document.querySelectorAll('input:not([type="hidden"]), textarea');
                        inputs.forEach(el => {
                            if (el.value) {
                                el.style.border = '2px solid #10b981';
                                el.style.backgroundColor = '#f0fdf4';
                            }
                        });
                    }
                """)

                # 5. Locate Submit Button
                submit_btn = page.locator('button[type="submit"], input[type="submit"], button:has-text("Submit"), button:has-text("Apply")')
                if await submit_btn.count() > 0:
                    await submit_btn.first.scroll_into_view_if_needed()

                # 6. Human-in-the-Loop Safety Stop
                if pause_for_review:
                    # When pause_for_review is True, the agent leaves the form ready
                    # and halts BEFORE clicking Submit.
                    if not headless and review_timeout_seconds > 0:
                        try:
                            # Keep browser open for the user to review the pre-filled fields
                            await page.wait_for_timeout(review_timeout_seconds * 1000)
                        except Exception:
                            pass

                    return ApplicationRunResult(
                        success=True,
                        status=fill_res.status,
                        job_url=job_url,
                        fields_filled=fill_res.fields_filled,
                        questions_answered=fill_res.questions_answered,
                        unanswered_questions=fill_res.unanswered_questions,
                        audit_notes=f"Cockpit Review Mode: Form pre-filled ({len(fill_res.fields_filled)} fields). Paused before submit."
                    )

                return ApplicationRunResult(
                    success=True,
                    status="ready_for_review",
                    job_url=job_url,
                    fields_filled=fill_res.fields_filled,
                    questions_answered=fill_res.questions_answered,
                    unanswered_questions=fill_res.unanswered_questions,
                    audit_notes=fill_res.audit_notes
                )

            except Exception as e:
                return ApplicationRunResult(
                    success=False,
                    status="error",
                    job_url=job_url,
                    audit_notes=f"Navigation error: {str(e)[:100]}"
                )
            finally:
                await browser.close()

    async def _detect_login_or_captcha(self, page: Page) -> bool:
        """Detect whether the page is blocked by a login wall or CAPTCHA."""
        content = (await page.content()).lower()
        if "recaptcha" in content or "cf-turnstile" in content or "hcaptcha" in content:
            return True
        # Check for mandatory sign in screens
        if "sign in to apply" in content or "login to continue" in content:
            return True
        return False
