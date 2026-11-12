"""Excel Job Tracker for JobFlow-AI.

Generates and maintains a professional multi-sheet Excel spreadsheet
matching the user's exact audit workflow:
- Sheet 1: Applications (Date, Company, Job Title, Location, Work Type, D2C?, Job Link, Status, Reason/Notes)
- Sheet 2: Recruiter Contacts (Date, Company, Type, Name - Title, Profile URL, Status)

Includes frozen navy headers, clickable hyperlinks, duplicate detection,
and date-grouped audit trails.
"""

from datetime import date
from pathlib import Path
from typing import Optional, Set
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter


class ExcelJobTracker:
    """Manages the Job_Tracker.xlsx spreadsheet."""

    NAVY_FILL = PatternFill(start_color="1B365D", end_color="1B365D", fill_type="solid")
    WHITE_BOLD_FONT = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    REGULAR_FONT = Font(name="Calibri", size=10)
    BOLD_FONT = Font(name="Calibri", size=10, bold=True)
    LINK_FONT = Font(name="Calibri", size=10, color="0563C1", underline="single")
    DATE_HEADER_FILL = PatternFill(start_color="E6EDF5", end_color="E6EDF5", fill_type="solid")

    STATUS_COLORS = {
        "Applied": PatternFill(start_color="D4EDDA", end_color="D4EDDA", fill_type="solid"),     # Soft Green
        "Skipped": PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid"),     # Soft Gray
        "Needs Input": PatternFill(start_color="FFF3CD", end_color="FFF3CD", fill_type="solid"), # Soft Yellow
        "Request sent": PatternFill(start_color="D1ECF1", end_color="D1ECF1", fill_type="solid"),# Soft Cyan
    }

    THIN_BORDER = Border(
        left=Side(style="thin", color="D9D9D9"),
        right=Side(style="thin", color="D9D9D9"),
        top=Side(style="thin", color="D9D9D9"),
        bottom=Side(style="thin", color="D9D9D9"),
    )

    APP_HEADERS = [
        "Date", "Company", "Job Title", "Location",
        "Work Type", "D2C?", "Job Link", "Status", "Reason / Notes"
    ]

    CONTACT_HEADERS = [
        "Date", "Company", "Type", "Name - Title", "Profile URL", "Status"
    ]

    def __init__(self, file_path: str = "data/Job_Tracker.xlsx"):
        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_workbook()

    def _init_workbook(self) -> None:
        """Initialize or load the Excel workbook with headers and formatting."""
        if self.file_path.exists():
            self.wb = openpyxl.load_workbook(self.file_path)
        else:
            self.wb = openpyxl.Workbook()
            # Remove default sheet
            if "Sheet" in self.wb.sheetnames:
                self.wb.remove(self.wb["Sheet"])

        # Setup Applications Sheet
        if "Applications" not in self.wb.sheetnames:
            ws_apps = self.wb.create_sheet("Applications", index=0)
            self._format_header(ws_apps, self.APP_HEADERS)
        else:
            ws_apps = self.wb["Applications"]

        # Setup Recruiter Contacts Sheet
        if "Recruiter Contacts" not in self.wb.sheetnames:
            ws_contacts = self.wb.create_sheet("Recruiter Contacts", index=1)
            self._format_header(ws_contacts, self.CONTACT_HEADERS)
        else:
            ws_contacts = self.wb["Recruiter Contacts"]

        self._save()

    def _format_header(self, ws, headers) -> None:
        """Apply navy blue style, bold text, and freeze the top row."""
        ws.append(headers)
        header_row = ws[1]
        for cell in header_row:
            cell.fill = self.NAVY_FILL
            cell.font = self.WHITE_BOLD_FONT
            cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=False)
            cell.border = self.THIN_BORDER

        # Freeze the top header row so it stays fixed while scrolling
        ws.freeze_panes = "A2"
        ws.row_dimensions[1].height = 26

    def _save(self) -> None:
        """Save workbook to disk."""
        self.wb.save(self.file_path)

    def get_existing_job_links(self) -> Set[str]:
        """Retrieve all job links already logged to prevent duplicate applications."""
        ws = self.wb["Applications"]
        links = set()
        # Job Link is Column G (Column index 7)
        for row in range(2, ws.max_row + 1):
            val = ws.cell(row=row, column=7).value
            if val and str(val).strip():
                links.add(str(val).strip())
        return links

    def log_application(
        self,
        company: str,
        job_title: str,
        location: str,
        job_link: str,
        status: str,
        reason_notes: str,
        work_type: str = "Not specified",
        d2c: str = "-",
        run_date: Optional[str] = None,
    ) -> None:
        """Log a job application (applied, skipped, or needs input)."""
        ws = self.wb["Applications"]
        today_str = run_date or date.today().isoformat()

        row_data = [
            today_str,
            company,
            job_title,
            location,
            work_type,
            d2c,
            job_link,
            status,
            reason_notes,
        ]

        ws.append(row_data)
        current_row = ws.max_row
        ws.row_dimensions[current_row].height = 20

        # Style the row
        for col_idx in range(1, len(row_data) + 1):
            cell = ws.cell(row=current_row, column=col_idx)
            cell.font = self.REGULAR_FONT
            cell.border = self.THIN_BORDER
            cell.alignment = Alignment(vertical="center")

            # Style Job Link as clickable hyperlink
            if col_idx == 7 and job_link.startswith("http"):
                cell.hyperlink = job_link
                cell.font = self.LINK_FONT

            # Style Status with distinct soft pastel highlight
            if col_idx == 8 and status in self.STATUS_COLORS:
                cell.fill = self.STATUS_COLORS[status]
                cell.font = self.BOLD_FONT

        self._auto_adjust_column_widths(ws)
        self._save()

    def log_contact(
        self,
        company: str,
        contact_type: str,
        name_title: str,
        profile_url: str,
        status: str = "Request sent",
        run_date: Optional[str] = None,
    ) -> None:
        """Log a recruiter / hiring manager contact for networking."""
        ws = self.wb["Recruiter Contacts"]
        today_str = run_date or date.today().isoformat()

        row_data = [
            today_str,
            company,
            contact_type,
            name_title,
            profile_url,
            status,
        ]

        ws.append(row_data)
        current_row = ws.max_row
        ws.row_dimensions[current_row].height = 20

        for col_idx in range(1, len(row_data) + 1):
            cell = ws.cell(row=current_row, column=col_idx)
            cell.font = self.REGULAR_FONT
            cell.border = self.THIN_BORDER
            cell.alignment = Alignment(vertical="center")

            if col_idx == 5 and profile_url.startswith("http"):
                cell.hyperlink = profile_url
                cell.font = self.LINK_FONT

            if col_idx == 6 and status in self.STATUS_COLORS:
                cell.fill = self.STATUS_COLORS[status]
                cell.font = self.BOLD_FONT

        self._auto_adjust_column_widths(ws)
        self._save()

    def _auto_adjust_column_widths(self, ws) -> None:
        """Auto-adjust column widths based on contents for clean readability."""
        for col in ws.columns:
            max_len = 0
            col_letter = get_column_letter(col[0].column)
            for cell in col:
                val = str(cell.value or "")
                if len(val) > max_len:
                    max_len = len(val)
            # Add padding, with min width 12 and max 60 to prevent giant columns
            ws.column_dimensions[col_letter].width = max(min(max_len + 3, 60), 12)
