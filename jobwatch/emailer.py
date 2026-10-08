"""Email digest of new jobs over SMTP. Works with Gmail (app password), Brevo, Resend, etc.

Configured by environment variables (normally via .env or GitHub secrets).
For Gmail only SMTP_USER and SMTP_PASSWORD (an app password) are needed. Optional:
  SMTP_HOST (default smtp.gmail.com), SMTP_PORT (default 587; 465 uses SSL),
  EMAIL_TO (default: SMTP_USER), EMAIL_FROM (default: SMTP_USER).
"""
from __future__ import annotations

import os
import smtplib
import ssl
from collections import defaultdict
from email.message import EmailMessage

from .models import Job
from .storage import Store

MAX_LISTED = 100


def _settings() -> dict | None:
    user = os.environ.get("SMTP_USER", "").strip()
    host = os.environ.get("SMTP_HOST", "").strip() or ("smtp.gmail.com" if user else "")
    to = os.environ.get("EMAIL_TO", "").strip() or user  # default: email yourself
    if not host or not to:
        return None
    return {
        "host": host,
        "port": int(os.environ.get("SMTP_PORT", "").strip() or 587),
        "user": user,
        "password": os.environ.get("SMTP_PASSWORD", ""),
        "to": to,
        "sender": os.environ.get("EMAIL_FROM", "").strip() or user or to,
    }


def _sheet_url() -> str | None:
    sheet_id = os.environ.get("JOBWATCH_SHEET_ID", "").strip()
    return f"https://docs.google.com/spreadsheets/d/{sheet_id}" if sheet_id else None


def build_message(jobs: list[Job], sender: str, recipient: str,
                  sheet_url: str | None = None) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = f"jobwatch: {len(jobs)} new job{'s' if len(jobs) != 1 else ''}"
    msg["From"] = sender
    msg["To"] = recipient
    by_company = defaultdict(list)
    for job in jobs[:MAX_LISTED]:
        by_company[job.company].append(job)
    lines = []
    for company in sorted(by_company):
        lines.append(company)
        for job in by_company[company]:
            where = f" ({job.location})" if job.location else ""
            lines.append(f"  - {job.title}{where}\n    {job.url}")
        lines.append("")
    if len(jobs) > MAX_LISTED:
        lines.append(f"...and {len(jobs) - MAX_LISTED} more.")
    if sheet_url:
        lines.append(f"All jobs: {sheet_url}")
    msg.set_content("\n".join(lines).strip() + "\n")
    return msg


def _connect(cfg: dict):
    context = ssl.create_default_context()
    if cfg["port"] == 465:
        server = smtplib.SMTP_SSL(cfg["host"], cfg["port"], timeout=30, context=context)
    else:
        server = smtplib.SMTP(cfg["host"], cfg["port"], timeout=30)
        server.starttls(context=context)
    if cfg["user"]:
        server.login(cfg["user"], cfg["password"])
    return server


def notify(store: Store, cfg: dict) -> int:
    """Email unnotified jobs, then mark them. Marked only after a successful send."""
    pending = store.pending("notified")
    if not pending:
        return 0
    message = build_message(pending, cfg["sender"], cfg["to"], _sheet_url())
    with _connect(cfg) as server:
        server.send_message(message)
    store.mark("notified", pending)
    return len(pending)


def notify_from_env(store: Store) -> int | None:
    """Returns None if email is not configured."""
    cfg = _settings()
    return None if cfg is None else notify(store, cfg)


def check_email() -> str:
    """Status for `--check`: logs in to the mail server but sends nothing."""
    try:
        cfg = _settings()
    except ValueError as exc:
        return f"Email settings problem: {exc}"
    if cfg is None:
        return ("Email not configured. Set SMTP_USER (your Gmail address) and "
                "SMTP_PASSWORD (a Gmail app password).")
    try:
        with _connect(cfg):
            pass
    except Exception as exc:
        return (f"Could not log in to {cfg['host']}:{cfg['port']}: {exc!r}\n"
                "For Gmail, use an app password (needs 2-step verification), not your normal password.")
    return f"Email OK. Digests go to {cfg['to']} via {cfg['host']}."
