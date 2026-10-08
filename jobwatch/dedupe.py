"""Merge repeat postings of the same role (same company and title)."""
from __future__ import annotations

import re

from .models import Job

# "(m/w/d)", "(f/m/d)", "(d/f/m)", "(w|m|d)", "(all genders)", "(gn)" ...
_GENDER = re.compile(
    r"\(\s*(?:[mwfdxhgn]\s*[/|*]\s*)+[mwfdxhgn]\s*\)|\(\s*(?:all\s+genders?|gn|mfd)\s*\)",
    re.IGNORECASE,
)
_NOT_WORD = re.compile(r"[^0-9a-zà-ÿ]+")


def _norm(text: str) -> str:
    return _NOT_WORD.sub(" ", _GENDER.sub(" ", text.casefold())).strip()


def listing_key(company: str, title: str) -> str:
    return f"{_norm(company)}|{_norm(title)}"


def dedupe(jobs: list[Job]) -> list[Job]:
    """Keep the first job for each company+title. Pass direct company sources first."""
    seen, kept = set(), []
    for job in jobs:
        key = listing_key(job.company, job.title)
        if key not in seen:
            seen.add(key)
            kept.append(job)
    return kept
