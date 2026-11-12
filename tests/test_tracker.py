"""Unit tests for Excel Job Tracker."""

from pathlib import Path
import tempfile
import openpyxl
from src.tracker.excel_tracker import ExcelJobTracker


def test_tracker_creation_and_headers():
    """Verify that Job_Tracker.xlsx creates with the exact sheets and headers."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_path = Path(tmpdir) / "Test_Tracker.xlsx"
        tracker = ExcelJobTracker(file_path=str(test_path))

        assert test_path.exists()
        wb = openpyxl.load_workbook(test_path)
        assert "Applications" in wb.sheetnames
        assert "Recruiter Contacts" in wb.sheetnames

        ws_apps = wb["Applications"]
        headers = [cell.value for cell in ws_apps[1]]
        assert headers == [
            "Date", "Company", "Job Title", "Location",
            "Work Type", "D2C?", "Job Link", "Status", "Reason / Notes"
        ]


def test_log_application_and_deduplication():
    """Verify application logging, status formatting, and duplicate link tracking."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_path = Path(tmpdir) / "Test_Tracker.xlsx"
        tracker = ExcelJobTracker(file_path=str(test_path))

        test_url = "https://www.naukri.com/job-listings-ai-engineer-12345"
        tracker.log_application(
            company="Tech Corp",
            job_title="Junior AI Engineer",
            location="Hyderabad",
            job_link=test_url,
            status="Applied",
            reason_notes="88% Match, LangChain + FastAPI match. Screened: Notice period = Immediate.",
            work_type="Remote",
        )

        existing_links = tracker.get_existing_job_links()
        assert test_url in existing_links
        assert len(existing_links) == 1

        # Verify row content
        wb = openpyxl.load_workbook(test_path)
        ws = wb["Applications"]
        assert ws.max_row == 2
        assert ws.cell(row=2, column=2).value == "Tech Corp"
        assert ws.cell(row=2, column=8).value == "Applied"


def test_log_contact():
    """Verify recruiter contact logging."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_path = Path(tmpdir) / "Test_Tracker.xlsx"
        tracker = ExcelJobTracker(file_path=str(test_path))

        tracker.log_contact(
            company="Wise",
            contact_type="HR",
            name_title="Sparsh Divekar - Technical Recruiter",
            profile_url="https://www.linkedin.com/in/sparshdivekar/",
            status="Request sent",
        )

        wb = openpyxl.load_workbook(test_path)
        ws = wb["Recruiter Contacts"]
        assert ws.max_row == 2
        assert ws.cell(row=2, column=2).value == "Wise"
        assert ws.cell(row=2, column=6).value == "Request sent"
