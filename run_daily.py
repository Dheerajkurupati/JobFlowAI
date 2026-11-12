"""Daily Autonomous Job Harvesting & Application Entry Point.

Run:
    python run_daily.py

This script:
1. Loads candidate preferences and resume from config/settings.yaml
2. Ingests candidate profile to derive search keywords automatically
3. Concurrently queries LinkedIn, Indeed, Glassdoor, and ZipRecruiter
4. Filters out sales, telecalling, and night shifts
5. Computes ATS Match Scores & Skill Gap Roadmaps
6. Logs results to data/crm_jobs.json and data/Job_Tracker.xlsx
"""

from src.config import load_config
from src.harvester.multi_scraper import harvest_jobs_across_platforms


def main():
    print("=" * 70)
    print("🚀 JobFlow-AI: Launching Multi-Platform Autonomous Job Harvester...")
    print("=" * 70)

    config = load_config()
    print(f"\n[1] Candidate: {config.candidate.name} ({config.candidate.city})")
    print(f"    Target Hubs: {', '.join(config.search_preferences.target_locations)}")
    print(f"    Platforms: LinkedIn, Indeed, Glassdoor, ZipRecruiter")

    print("\n[2] Executing concurrent multi-board search & RAG matching...")
    summary = harvest_jobs_across_platforms(
        config=config,
        platforms=["linkedin", "indeed", "glassdoor", "ziprecruiter"],
        max_results_per_platform=12
    )

    print("\n" + "=" * 70)
    print("🎉 DAILY RUN SUMMARY:")
    print(f"    • Total Postings Inspected: {summary['total_scraped']}")
    print(f"    • Passed Criteria & Scored: {summary['accepted']}")
    print(f"    • Skipped (Unrelated/Shifts): {summary['skipped']}")
    print(f"    • New Jobs Added to CRM:    {summary['new_added']}")
    print("=" * 70)
    print("👉 View & Approve in Dashboard: http://localhost:8000")
    print("👉 Excel Audit Tracker: data/Job_Tracker.xlsx\n")


if __name__ == "__main__":
    main()

