"""Save listings (and optional AI results) to Supabase so the web app can show them.

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


class AiStore(Protocol):
    """The extra database calls the optional AI features need."""

    def get_profile(self) -> str: ...
    def upsert_analyses(self, rows: list[dict[str, Any]]) -> None: ...
    def pending_requests(self, limit: int) -> list[dict[str, Any]]: ...
    def finish_request(self, job_id: str, status: str, error: str | None, now: datetime) -> None: ...


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
        self._base = f"{url.rstrip('/')}/rest/v1"
        self._key = secret_key
        self._session = session or requests.Session()

    # --- jobs ------------------------------------------------------------------------------

    def upsert_jobs(self, rows: list[dict[str, Any]]) -> None:
        """Insert new jobs and update existing ones (matched on `id`) in a single request."""
        self._upsert("jobs", rows, conflict="id")

    # --- optional AI -------------------------------------------------------------------------

    def get_profile(self) -> str:
        rows = self._request("GET", "profile", params={"select": "content", "id": "eq.1"}).json()
        return (rows[0].get("content") or "").strip() if rows else ""

    def upsert_analyses(self, rows: list[dict[str, Any]]) -> None:
        self._upsert("analyses", rows, conflict="job_id")

    def pending_requests(self, limit: int) -> list[dict[str, Any]]:
        """Oldest pending "Analyze" requests from the web app, each with its job embedded."""
        params = {
            "select": "job_id,jobs(*)",
            "status": "eq.pending",
            "order": "requested_at.asc",
            "limit": str(limit),
        }
        return self._request("GET", "analysis_requests", params=params).json()

    def finish_request(self, job_id: str, status: str, error: str | None, now: datetime) -> None:
        body = {"status": status, "error": error, "completed_at": now.astimezone(timezone.utc).isoformat()}
        self._request("PATCH", "analysis_requests", params={"job_id": f"eq.{job_id}"}, json=body)

    # --- plumbing ----------------------------------------------------------------------------

    def _upsert(self, table: str, rows: list[dict[str, Any]], conflict: str) -> None:
        if rows:
            # merge-duplicates = upsert; return=minimal = don't send the rows back.
            prefer = "resolution=merge-duplicates,return=minimal"
            self._request("POST", table, params={"on_conflict": conflict}, json=rows, prefer=prefer)

    def _request(
        self, method: str, table: str, *, params: dict[str, str], json: Any = None, prefer: str | None = None
    ) -> requests.Response:
        headers = {"apikey": self._key, "Content-Type": "application/json"}
        if prefer:
            headers["Prefer"] = prefer
        if not self._key.startswith("sb_"):
            # Legacy service_role keys are JWTs and must also be sent as a bearer token.
            headers["Authorization"] = f"Bearer {self._key}"
        try:
            response = self._session.request(
                method, f"{self._base}/{table}", params=params, json=json, headers=headers, timeout=TIMEOUT_SECONDS
            )
        except requests.RequestException as exc:
            raise DatabaseError(f"Supabase request failed: {redact(str(exc), self._key)}") from None
        if response.status_code not in (200, 201, 204):
            raise DatabaseError(f"Supabase HTTP {response.status_code}: {redact(response.text[:300], self._key)}")
        return response
