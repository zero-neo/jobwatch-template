"""Append new jobs to a Google Sheet.

Configuration comes from environment variables, so no secrets live in the repo:
  GOOGLE_SERVICE_ACCOUNT_JSON  the key's JSON content, or a path to the key file
  JOBWATCH_SHEET_ID            the ID from the Sheet's URL (between /d/ and /edit)
  JOBWATCH_SHEET_TAB           optional worksheet name (default: Jobs)
"""
from __future__ import annotations

import json
import os
from datetime import date

from .models import Job
from .storage import Store

HEADERS = ["Found", "Company", "Title", "Location", "Posted", "URL", "Status", "Notes"]
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def job_to_row(job: Job, found: str) -> list[str]:
    posted = (job.posted or "")[:10]  # date part of the ISO timestamp
    # Status and Notes are left blank for you to fill in by hand.
    return [found, job.company, job.title, job.location, posted, job.url, "", ""]


def sync(store: Store, worksheet, today: str | None = None) -> int:
    """Append unsynced jobs, then mark them synced. Returns the number of rows added.

    Jobs are marked only after the append succeeds, so a failure means a retry on
    the next run rather than lost jobs. Existing rows are never touched, so your
    Status and Notes columns are safe.
    """
    pending = store.pending("synced")
    if not pending:
        return 0
    found = today or date.today().isoformat()
    rows = [job_to_row(j, found) for j in pending]
    if not worksheet.row_values(1):
        rows.insert(0, HEADERS)
    # RAW stops a job title starting with "=" from being run as a formula.
    worksheet.append_rows(rows, value_input_option="RAW")
    store.mark("synced", pending)
    return len(pending)


def _credentials() -> dict | None:
    raw = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    if not raw:
        return None
    if raw.startswith("{"):
        return json.loads(raw)
    with open(os.path.expanduser(raw), encoding="utf-8") as fh:
        return json.load(fh)


def open_worksheet(sheet_id: str, credentials: dict, tab: str = "Jobs"):
    import gspread  # imported here so the rest of the tool works without it

    client = gspread.service_account_from_dict(credentials, scopes=SCOPES)
    spreadsheet = client.open_by_key(sheet_id)
    try:
        return spreadsheet.worksheet(tab)
    except gspread.WorksheetNotFound:
        return spreadsheet.add_worksheet(title=tab, rows=1000, cols=len(HEADERS))


def sync_from_env(store: Store) -> int | None:
    """Sync using environment configuration. Returns None if not configured."""
    sheet_id = os.environ.get("JOBWATCH_SHEET_ID", "").strip()
    credentials = _credentials()
    if not sheet_id or credentials is None:
        return None
    tab = os.environ.get("JOBWATCH_SHEET_TAB", "").strip() or "Jobs"
    return sync(store, open_worksheet(sheet_id, credentials, tab))


def check_connection() -> str:
    """Human-readable status for `--check`. Opens the Sheet (and creates the tab if missing)."""
    sheet_id = os.environ.get("JOBWATCH_SHEET_ID", "").strip()
    try:
        credentials = _credentials()
    except (OSError, ValueError) as exc:
        return f"Could not read the Google key: {exc}"
    if not sheet_id or credentials is None:
        return ("Google Sheet not configured (optional). To use one, set "
                "GOOGLE_SERVICE_ACCOUNT_JSON and JOBWATCH_SHEET_ID in .env.")
    email = credentials.get("client_email", "(unknown)")
    tab = os.environ.get("JOBWATCH_SHEET_TAB", "").strip() or "Jobs"
    try:
        worksheet = open_worksheet(sheet_id, credentials, tab)
    except Exception as exc:
        return (f"Could not open the Sheet: {exc!r}\n"
                f"Check that the Sheet is shared (Editor) with {email} and that the "
                f"Google Sheets API is enabled for the project.")
    return f"Google Sheet OK. Rows go to tab '{worksheet.title}'. Share the Sheet with: {email}"
