"""Demo script: Visual test of the JobFlow-AI Excel Tracker.

Run this script to generate a live 'data/Job_Tracker.xlsx' spreadsheet
matching your exact screenshots with sample rows.
"""

from pathlib import Path
from src.tracker.excel_tracker import ExcelJobTracker
from src.config import load_config


def main():
    print("=" * 70)
    print("🚀 Running JobFlow-AI Tracker Verification...")
    print("=" * 70)

    # 1. Load validated configuration
    config = load_config()
    excel_path = Path("data/Job_Tracker.xlsx")
    print(f"\n[1] Configuration Loaded Successfully:")
    print(f"    • Target Locations: {', '.join(config.search_preferences.target_locations)}")
    print(f"    • Output Excel File: {excel_path.resolve()}")

    # 2. Initialize Excel Tracker
    tracker = ExcelJobTracker(file_path=str(excel_path))
    print(f"\n[2] Initializing Excel Tracker with custom Navy headers...")

    # 3. Log a sample "Applied" job (matching Image 4 from your screenshots)
    print(f"\n[3] Logging Sample Applications:")
    tracker.log_application(
        company="Cognizant",
        job_title="Junior AI / Python Developer",
        location="Hyderabad",
        job_link="https://www.naukri.com/job-listings-python-dev-12345",
        status="Applied",
        reason_notes="88% Match, FastAPI + LangChain match. Screening: Previously employed = No. Notice = Immediate.",
        work_type="Hybrid",
        d2c="Easy Apply",
    )
    print("    ✅ Logged 'Applied' row: Cognizant - Junior AI / Python Developer")

    # 4. Log a sample "Skipped" job (matching your skip rules)
    tracker.log_application(
        company="Omnicom Global Solutions",
        job_title="Operations Analyst",
        location="Hyderabad",
        job_link="https://www.naukri.com/job-listings-ops-67890",
        status="Skipped",
        reason_notes="Skipped by Filter Rule: Night/US shift (6:30 PM - 3:30 AM).",
        work_type="On-site",
    )
    print("    ⚠️  Logged 'Skipped' row: Omnicom - Night shift detected")

    # 5. Log a sample Recruiter Contact (matching Image 3 from your screenshots)
    print(f"\n[4] Logging Sample Recruiter Contact:")
    tracker.log_contact(
        company="Wise",
        contact_type="HR",
        name_title="Sparsh Divekar - Technical Recruiter (job poster)",
        profile_url="https://www.linkedin.com/in/sparshdivekar/",
        status="Request sent",
    )
    print("    👤 Logged Contact: Sparsh Divekar (Technical Recruiter at Wise)")

    # 6. Verify duplicate detection
    existing = tracker.get_existing_job_links()
    print(f"\n[5] Deduplication System Check:")
    print(f"    • Total tracked unique links: {len(existing)}")

    print("\n" + "=" * 70)
    print(f"🎉 SUCCESS! Open the generated Excel file to inspect:")
    print(f"👉 File Location: {excel_path.resolve()}")
    print("=" * 70)


if __name__ == "__main__":
    main()
