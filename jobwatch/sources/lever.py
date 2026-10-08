"""Lever public postings API (no authentication required)."""
from __future__ import annotations

import re
from datetime import datetime, timezone

import requests

from ..models import Company, Job

API = "https://api.lever.co/v0/postings/{slug}"
API_EU = "https://api.eu.lever.co/v0/postings/{slug}"
_TAG = re.compile(r"<[^>]+>")
_SPACE = re.compile(r"\s+")


def _location(item: dict) -> str:
    cats = item.get("categories") or {}
    places = cats.get("allLocations") or ([cats["location"]] if cats.get("location") else [])
    return " | ".join(p.strip() for p in places if p and p.strip())


def _posted(item: dict) -> str | None:
    ms = item.get("createdAt")  # milliseconds since the epoch
    if isinstance(ms, (int, float)):
        return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat(timespec="seconds")
    return None


def _description(item: dict) -> str:
    parts = [item.get("descriptionPlain"), item.get("additionalPlain")]
    parts += [f"{b.get('text', '')} {_TAG.sub(' ', b.get('content', ''))}"
              for b in item.get("lists") or []]
    return _SPACE.sub(" ", " ".join(p for p in parts if p)).strip()


def parse(company: Company, payload: list) -> list[Job]:
    return [
        Job(
            source="lever",
            external_id=str(item["id"]),
            title=(item.get("text") or "").strip(),
            company=company.name,
            location=_location(item),
            url=item.get("hostedUrl") or "",
            posted=_posted(item),
            description=_description(item),
        )
        for item in payload
    ]


def _fetch(company: Company, api: str, session, timeout: int) -> list[Job]:
    client = session or requests
    response = client.get(api.format(slug=company.slug), params={"mode": "json"}, timeout=timeout)
    response.raise_for_status()
    return parse(company, response.json())


def fetch(company: Company, session=None, timeout: int = 20) -> list[Job]:
    return _fetch(company, API, session, timeout)


def fetch_eu(company: Company, session=None, timeout: int = 20) -> list[Job]:
    return _fetch(company, API_EU, session, timeout)
