"""Save listings to Supabase (Postgres) so the web app can show them.

Talks to Supabase's REST API with plain `requests`, so there's no extra dependency.
Uses the SECRET key, which bypasses Row Level Security, so it must only ever run
server-side (here: GitHub Actions). See supabase/schema.sql for the tables.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Protocol

import requests

from .filters import KeywordFilter
from .notify import redact
from .parse import Job

TIMEOUT_SECONDS = 20


class DatabaseError(Exception):
    """Supabase rejected or couldn't receive the data. The message never contains the key."""


class JobsStore(Protocol):
    def upsert_jobs(self, rows: list[dict[str, Any]]) -> None: ...


def job_rows(jobs: list[Job], keyword_filter: KeywordFilter, now: datetime) -> list[dict[str, Any]]:
    """One row per job for the `jobs` table.

    first_seen_at is deliberately left out: the database fills it in on insert, and
    leaving it out of the upsert means later runs never overwrite it.
    """
    stamp = now.astimezone(timezone.utc).isoformat()
    return [
        {
            "id": job.id,
            "title": job.title,
            "url": job.url,
            "posted_at": job.posted.isoformat() if job.posted else None,
            "salary": job.salary,
            "job_type": job.job_type,
            "snippet": job.snippet,
            "tags": list(job.tags),
            "matched_keyword": keyword_filter.matched_keyword(job),
            "updated_at": stamp,
        }
        for job in jobs
    ]


class SupabaseJobsStore:
    def __init__(self, url: str, secret_key: str, session: requests.Session | None = None) -> None:
        self._endpoint = f"{url.rstrip('/')}/rest/v1/jobs"
        self._key = secret_key
        self._session = session or requests.Session()

    def upsert_jobs(self, rows: list[dict[str, Any]]) -> None:
        """Insert new jobs and update existing ones (matched on `id`) in a single request."""
        if not rows:
            return
        headers = {
            "apikey": self._key,
            "Content-Type": "application/json",
            # merge-duplicates = upsert; return=minimal = don't send the rows back.
            "Prefer": "resolution=merge-duplicates,return=minimal",
        }
        if not self._key.startswith("sb_"):
            # Legacy service_role keys are JWTs and must also be sent as a bearer token.
            headers["Authorization"] = f"Bearer {self._key}"
        try:
            response = self._session.post(
                self._endpoint, params={"on_conflict": "id"}, json=rows, headers=headers, timeout=TIMEOUT_SECONDS
            )
        except requests.RequestException as exc:
            raise DatabaseError(f"Supabase request failed: {redact(str(exc), self._key)}") from None
        if response.status_code not in (200, 201, 204):
            raise DatabaseError(f"Supabase HTTP {response.status_code}: {redact(response.text[:300], self._key)}")
