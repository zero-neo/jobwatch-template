"""Greenhouse public job-board API (no authentication required)."""
from __future__ import annotations

import html
import re

import requests

from ..models import Company, Job

API = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
_TAG = re.compile(r"<[^>]+>")
_SPACE = re.compile(r"\s+")


def _to_text(escaped_html: str) -> str:
    # Greenhouse returns HTML that is itself entity-escaped, hence two unescapes.
    text = _TAG.sub(" ", html.unescape(escaped_html or ""))
    return _SPACE.sub(" ", html.unescape(text)).strip()


def parse(company: Company, payload: dict) -> list[Job]:
    jobs = []
    for item in payload.get("jobs", []):
        jobs.append(
            Job(
                source="greenhouse",
                external_id=str(item["id"]),
                title=(item.get("title") or "").strip(),
                company=company.name,
                location=((item.get("location") or {}).get("name") or "").strip(),
                url=item.get("absolute_url") or "",
                # first_published is not always present; updated_at is a fallback
                # and may be later than the true posting date.
                posted=item.get("first_published") or item.get("updated_at"),
                description=_to_text(item.get("content", "")),
            )
        )
    return jobs


def fetch(company: Company, session=None, timeout: int = 20) -> list[Job]:
    client = session or requests
    response = client.get(
        API.format(slug=company.slug), params={"content": "true"}, timeout=timeout
    )
    response.raise_for_status()
    return parse(company, response.json())
