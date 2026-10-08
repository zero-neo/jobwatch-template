from __future__ import annotations

import re

from .config import Filters
from .language import looks_english
from .models import Job


def compile_term(term: str) -> re.Pattern:
    """Whole-word, case-insensitive. A trailing * allows any word ending."""
    prefix = term.endswith("*")
    core = re.escape(term.rstrip("*").strip())
    tail = "" if prefix else r"(?!\w)"
    return re.compile(rf"(?<!\w){core}{tail}", re.IGNORECASE)


class JobFilter:
    def __init__(self, filters: Filters):
        self._title_in = [compile_term(t) for t in filters.title_include]
        self._desc_in = [compile_term(t) for t in filters.description_include]
        self._title_out = [compile_term(t) for t in filters.title_exclude]
        self._company_out = [compile_term(t) for t in filters.company_exclude]
        self._english_only = filters.english_only
        self._skipped: dict[str, Job] = {}  # otherwise-matching jobs removed by the language check
        self._loc_in = [compile_term(t) for t in filters.locations]
        self._loc_out = [compile_term(t) for t in filters.location_exclude]

    def matches(self, job: Job) -> bool:
        if any(p.search(job.company) for p in self._company_out):
            return False
        relevant = any(p.search(job.title) for p in self._title_in) or any(
            p.search(job.description) for p in self._desc_in
        )
        if not relevant:
            return False
        if any(p.search(job.title) for p in self._title_out):
            return False
        if any(p.search(job.location) for p in self._loc_out):
            return False
        if self._loc_in and not any(p.search(job.location) for p in self._loc_in):
            return False
        if self._english_only and not looks_english(f"{job.title} {job.description[:1200]}"):
            self._skipped[job.key] = job
            return False
        return True

    @property
    def non_english_skipped(self) -> list[Job]:
        return list(self._skipped.values())

    @property
    def non_english_dropped(self) -> int:
        return len(self._skipped)
