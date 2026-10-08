"""Adzuna job-search API: keyword searches across all employers in a country.

Needs a free key from developer.adzuna.com (ADZUNA_APP_ID and ADZUNA_APP_KEY).
Error messages never include the request URL, because it contains your key.
"""
from __future__ import annotations

import html
import re
import time

import requests

from ..models import Job

API = "https://api.adzuna.com/v1/api/jobs/{country}/search/{page}"
PAGE_SIZE = 50
RETRY_STATUSES = {429, 500, 502, 503, 504}  # temporary: worth another try
COUNTRIES = {
    "at": "Austria", "au": "Australia", "be": "Belgium", "br": "Brazil", "ca": "Canada",
    "ch": "Switzerland", "de": "Germany", "es": "Spain", "fr": "France",
    "gb": "United Kingdom", "in": "India", "it": "Italy", "mx": "Mexico",
    "nl": "Netherlands", "nz": "New Zealand", "pl": "Poland", "sg": "Singapore",
    "us": "United States", "za": "South Africa",
}
_TAG = re.compile(r"<[^>]+>")
_SPACE = re.compile(r"\s+")


def _clean(text: str) -> str:
    return _SPACE.sub(" ", html.unescape(_TAG.sub(" ", text or ""))).strip()


def parse(country: str, payload: dict) -> list[Job]:
    country_name = COUNTRIES.get(country, country.upper())
    jobs = []
    for item in payload.get("results", []):
        location = _clean((item.get("location") or {}).get("display_name", ""))
        # Adzuna's location text often omits the country, which your filters need.
        if country_name.lower() not in location.lower():
            location = f"{location}, {country_name}" if location else country_name
        jobs.append(
            Job(
                source="adzuna",
                external_id=str(item["id"]),
                title=_clean(item.get("title", "")),
                company=_clean((item.get("company") or {}).get("display_name", "")) or "Unknown company",
                location=location,
                url=item.get("redirect_url") or "",
                posted=item.get("created"),
                description=_clean(item.get("description", "")),  # Adzuna sends only a snippet
            )
        )
    return jobs


def _get(country, page, params, session, timeout) -> dict:
    client = session or requests
    for attempt in range(3):
        try:
            response = client.get(API.format(country=country, page=page), params=params, timeout=timeout)
        except requests.RequestException as exc:
            raise RuntimeError(f"network error ({type(exc).__name__})") from None
        if response.status_code in RETRY_STATUSES and attempt < 2:
            time.sleep(2 * (attempt + 1))  # 2 s, then 4 s
            continue
        break
    if response.status_code != 200:
        raise RuntimeError(f"HTTP {response.status_code} from Adzuna for country '{country}'")
    try:
        return response.json()
    except ValueError:
        raise RuntimeError("Adzuna returned something that is not JSON") from None


def fetch_query(country: str, query: str, max_pages: int, max_days_old: int,
                app_id: str, app_key: str, session=None, timeout: int = 20) -> list[Job]:
    jobs: list[Job] = []
    for page in range(1, max_pages + 1):
        payload = _get(country, page, {
            "app_id": app_id, "app_key": app_key, "what": query,
            "results_per_page": PAGE_SIZE, "max_days_old": max_days_old, "sort_by": "date",
        }, session, timeout)
        jobs.extend(parse(country, payload))
        if len(payload.get("results", [])) < PAGE_SIZE:
            break
    return jobs
