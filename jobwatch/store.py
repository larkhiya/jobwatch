"""State files: state/seen.json (job ID -> first-seen time) and small JSON helpers."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .parse import Job

Seen = dict[str, datetime]  # job ID -> when we first saw it (UTC)


def load_json(path: Path) -> Any:
    """Return the parsed file, or None if it doesn't exist yet."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None


def save_json(path: Path, data: Any) -> None:
    """Write atomically: a crash mid-write can't leave a half-written (corrupt) file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    # indent=0 + sorted keys = one entry per line in a stable order -> small, readable git diffs.
    tmp.write_text(json.dumps(data, indent=0, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def load_seen(path: Path) -> Seen:
    raw = load_json(path) or {}
    return {job_id: _parse_utc(stamp) for job_id, stamp in raw.items()}


def save_seen(path: Path, seen: Seen) -> None:
    save_json(path, {job_id: _format_utc(when) for job_id, when in seen.items()})


def unseen(jobs: list[Job], seen: Seen) -> list[Job]:
    """Jobs whose ID we have never recorded. Dedupe is by ID only, never by title."""
    return [job for job in jobs if job.id not in seen]


def mark_seen(seen: Seen, jobs: list[Job], now: datetime) -> None:
    for job in jobs:
        seen.setdefault(job.id, now)


def prune(seen: Seen, now: datetime, retention_days: int) -> int:
    """Forget IDs first seen more than `retention_days` ago. Returns how many were removed."""
    cutoff = now - timedelta(days=retention_days)
    old = [job_id for job_id, when in seen.items() if when < cutoff]
    for job_id in old:
        del seen[job_id]
    return len(old)


def _format_utc(when: datetime) -> str:
    return when.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_utc(stamp: str) -> datetime:
    return datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
