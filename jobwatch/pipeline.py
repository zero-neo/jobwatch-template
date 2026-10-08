from __future__ import annotations

import logging

from .filters import JobFilter
from .models import Company, Job
from .sources import REGISTRY

log = logging.getLogger("jobwatch")


def collect(companies: list[Company], job_filter: JobFilter, fetchers=None):
    """Fetch every company, apply filters. One failing company never stops the run.

    Returns (matched_jobs, errors).
    """
    fetchers = fetchers or REGISTRY
    matched: list[Job] = []
    errors: list[str] = []
    for company in companies:
        try:
            jobs = fetchers[company.ats](company)
        except Exception as exc:  # network errors, bad slug (404), malformed JSON
            msg = f"{company.name} ({company.ats}/{company.slug}): {exc}"
            log.warning("fetch failed: %s", msg)
            errors.append(msg)
            continue
        hits = [j for j in jobs if job_filter.matches(j)]
        log.info("%s: %d jobs fetched, %d matched", company.name, len(jobs), len(hits))
        matched.extend(hits)
    return matched, errors
