from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from .dedupe import listing_key
from .models import Job

_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    key        TEXT PRIMARY KEY,
    source     TEXT NOT NULL,
    external_id TEXT NOT NULL,
    company    TEXT NOT NULL,
    title      TEXT NOT NULL,
    location   TEXT NOT NULL,
    url        TEXT NOT NULL,
    posted     TEXT,
    first_seen TEXT NOT NULL,
    synced     INTEGER NOT NULL DEFAULT 0,   -- written to the Google Sheet
    notified   INTEGER NOT NULL DEFAULT 0    -- included in an email digest
);
"""
_FLAGS = {"synced", "notified"}


class Store:
    def __init__(self, path: str):
        self.conn = sqlite3.connect(path)
        self.conn.executescript(_SCHEMA)
        self._migrate()

    def _migrate(self) -> None:
        """Older databases lack listing_key; add it and fill it in for existing rows."""
        columns = {row[1] for row in self.conn.execute("PRAGMA table_info(jobs)")}
        if "listing_key" in columns:
            return
        with self.conn:
            self.conn.execute("ALTER TABLE jobs ADD COLUMN listing_key TEXT")
            rows = self.conn.execute("SELECT key, company, title FROM jobs").fetchall()
            self.conn.executemany(
                "UPDATE jobs SET listing_key = ? WHERE key = ?",
                [(listing_key(company, title), key) for key, company, title in rows],
            )

    def drop_known_listings(self, jobs: list[Job]) -> list[Job]:
        """Remove jobs whose company+title is already stored under a different id (reposts)."""
        kept = []
        for job in jobs:
            row = self.conn.execute(
                "SELECT key FROM jobs WHERE listing_key = ? LIMIT 1",
                (listing_key(job.company, job.title),),
            ).fetchone()
            if row is None or row[0] == job.key:
                kept.append(job)
        return kept

    def add_new(self, jobs: list[Job]) -> list[Job]:
        """Insert unseen jobs; return only those that were actually new."""
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        new = []
        with self.conn:
            for job in jobs:
                cur = self.conn.execute(
                    "INSERT OR IGNORE INTO jobs "
                    "(key, source, external_id, company, title, location, url, posted, first_seen, "
                    "listing_key) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (job.key, job.source, job.external_id, job.company, job.title,
                     job.location, job.url, job.posted, now,
                     listing_key(job.company, job.title)),
                )
                if cur.rowcount == 1:
                    new.append(job)
        return new

    def pending(self, flag: str) -> list[Job]:
        """Jobs not yet synced / notified. Descriptions are not stored, so are empty."""
        self._check(flag)
        rows = self.conn.execute(
            f"SELECT source, external_id, title, company, location, url, posted "
            f"FROM jobs WHERE {flag} = 0 ORDER BY first_seen, key"
        ).fetchall()
        return [Job(r[0], r[1], r[2], r[3], r[4], r[5], r[6], "") for r in rows]

    def mark(self, flag: str, jobs: list[Job]) -> None:
        self._check(flag)
        with self.conn:
            self.conn.executemany(
                f"UPDATE jobs SET {flag} = 1 WHERE key = ?", [(j.key,) for j in jobs]
            )

    @staticmethod
    def _check(flag: str) -> None:
        if flag not in _FLAGS:
            raise ValueError(f"flag must be one of {sorted(_FLAGS)}")

    def close(self) -> None:
        self.conn.close()
