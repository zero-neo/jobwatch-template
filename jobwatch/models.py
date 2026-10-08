from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Company:
    name: str
    ats: str
    slug: str


@dataclass(frozen=True)
class Job:
    """The single record every source must produce."""

    source: str          # e.g. "greenhouse"
    external_id: str     # the source's own job id
    title: str
    company: str
    location: str
    url: str
    posted: str | None   # ISO timestamp if the source provides one
    description: str     # plain text; used for matching, not stored

    @property
    def key(self) -> str:
        """Stable deduplication key."""
        return f"{self.source}:{self.company.lower()}:{self.external_id}"
