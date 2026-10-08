"""Keyword searches on job aggregators: finds jobs at companies you did not list."""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

import yaml

from .config import ConfigError
from .filters import JobFilter
from .sources import adzuna

log = logging.getLogger("jobwatch")
_KEYS = {"countries", "queries", "max_pages", "max_days_old"}


@dataclass(frozen=True)
class AdzunaSearch:
    countries: list[str]
    queries: list[str]
    max_pages: int = 2        # 50 results per page
    max_days_old: int = 14


def load_searches(path) -> AdzunaSearch | None:
    """Returns None if the file has no 'adzuna' section."""
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict) or set(data) - {"adzuna"}:
        raise ConfigError(f"{path}: the only top-level key allowed is 'adzuna'")
    section = data.get("adzuna")
    if section is None:
        return None
    unknown = set(section) - _KEYS
    if unknown:
        raise ConfigError(f"{path}: unknown key(s) {sorted(unknown)}; expected {sorted(_KEYS)}")

    def strings(key):
        value = section.get(key) or []
        if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
            raise ConfigError(f"{path}: '{key}' must be a list of strings")
        return [v.strip().lower() if key == "countries" else v.strip() for v in value if v.strip()]

    countries, queries = strings("countries"), strings("queries")
    if not countries or not queries:
        raise ConfigError(f"{path}: give at least one country and one query")
    bad = [c for c in countries if c not in adzuna.COUNTRIES]
    if bad:
        raise ConfigError(f"{path}: unknown country code(s) {bad}; valid: {sorted(adzuna.COUNTRIES)}")

    def number(key, default, low, high):
        value = section.get(key, default)
        if not isinstance(value, int) or isinstance(value, bool) or not low <= value <= high:
            raise ConfigError(f"{path}: '{key}' must be a whole number from {low} to {high}")
        return value

    return AdzunaSearch(countries, queries, number("max_pages", 2, 1, 10),
                        number("max_days_old", 14, 1, 90))


def collect_adzuna(search: AdzunaSearch, job_filter: JobFilter, fetch=None):
    """Run every (country, query) pair. One failing search never stops the rest.

    Returns (matched_jobs, errors).
    """
    app_id = os.environ.get("ADZUNA_APP_ID", "").strip()
    app_key = os.environ.get("ADZUNA_APP_KEY", "").strip()
    if fetch is None:
        if not (app_id and app_key):
            return [], ["Adzuna: set ADZUNA_APP_ID and ADZUNA_APP_KEY in .env "
                        "(free key at developer.adzuna.com)"]
        fetch = adzuna.fetch_query
    seen, matched, errors = set(), [], []
    for country in search.countries:
        for query in search.queries:
            try:
                jobs = fetch(country, query, search.max_pages, search.max_days_old, app_id, app_key)
            except Exception as exc:
                msg = f"Adzuna {country} '{query}': {exc}"
                log.warning("search failed: %s", msg)
                errors.append(msg)
                continue
            hits = 0
            for job in jobs:
                if job.key not in seen and job_filter.matches(job):
                    seen.add(job.key)
                    matched.append(job)
                    hits += 1
            log.info("Adzuna %s '%s': %d fetched, %d new matches", country, query, len(jobs), hits)
    return matched, errors
