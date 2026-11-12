"""Playwright browser automation and form-filling agent package for JobFlow-AI."""

from .form_filler import FormFiller, FillResult
from .browser_pilot import BrowserPilot, ApplicationRunResult

__all__ = ["FormFiller", "FillResult", "BrowserPilot", "ApplicationRunResult"]

