"""Strict, high-speed deterministic filter rules for JobFlow-AI.

Filters out non-IT roles, sales, telecalling, unfavorable night shifts,
and unpaid positions before any tokens or time are wasted.
"""

import re
from typing import Optional
from pydantic import BaseModel
from src.config import FilterRulesConfig, SearchPreferencesConfig


class FilterDecision(BaseModel):
    is_accepted: bool
    rejection_reason: Optional[str] = None


def is_job_acceptable(
    title: str,
    description: str,
    location: str,
    filter_rules: FilterRulesConfig,
    search_prefs: SearchPreferencesConfig
) -> FilterDecision:
    """Evaluate whether a discovered job meets candidate criteria."""
    combined_text = f"{title} {description}".lower()

    # 1. Non-IT / Blacklisted Keywords Filter
    for kw in filter_rules.ignore_role_keywords:
        pattern = rf"\b{re.escape(kw.lower())}\b"
        if re.search(pattern, combined_text):
            return FilterDecision(
                is_accepted=False,
                rejection_reason=f"Ignored Role Keyword: '{kw}'"
            )

    # 2. Unfavorable Shifts Filter (Night Shift, US/UK Shifts)
    for shift_kw in filter_rules.ignore_shift_keywords:
        pattern = rf"\b{re.escape(shift_kw.lower())}\b"
        if re.search(pattern, combined_text):
            return FilterDecision(
                is_accepted=False,
                rejection_reason=f"Ignored Shift: '{shift_kw}'"
            )

    # 3. Unpaid Internship Filter
    if filter_rules.ignore_unpaid_internships:
        if re.search(r"\bunpaid\b|no\s+stipend|unpaid\s+intern", combined_text):
            return FilterDecision(
                is_accepted=False,
                rejection_reason="Unpaid role detected"
            )

    # 4. Location Verification
    loc_lower = location.lower() if location else ""
    is_target_hub = any(h.lower() in loc_lower for h in search_prefs.target_locations)
    is_remote = "remote" in loc_lower or "work from home" in loc_lower or "wfh" in combined_text

    if is_target_hub or is_remote:
        return FilterDecision(is_accepted=True)

    # Pan-India check: Allow if interview/process is virtual
    if search_prefs.allow_pan_india_if_virtual:
        if any(v in combined_text for v in ["virtual", "online interview", "remote interview", "video call"]):
            return FilterDecision(is_accepted=True)

    # If on-site in unapproved location (e.g. Noida, Delhi on-site with no virtual option)
    return FilterDecision(
        is_accepted=False,
        rejection_reason=f"Location outside preferred hubs: '{location}'"
    )
