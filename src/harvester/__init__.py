"""Multi-platform job harvester package for JobFlow-AI."""

from .filter_rules import is_job_acceptable, FilterDecision
from .multi_scraper import harvest_jobs_across_platforms

__all__ = ["is_job_acceptable", "FilterDecision", "harvest_jobs_across_platforms"]
