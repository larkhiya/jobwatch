"""One run of the pipeline: fetch -> parse -> dedupe -> filter -> save state."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from .config import Config
from .fetch import HttpSettings, fetch_pages
from .parse import PH_TZ, Job, parse_jobs
from .store import load_seen, mark_seen, prune, save_seen, unseen

log = logging.getLogger(__name__)

PageFetcher = Callable[[str, int, HttpSettings], list[str]]


@dataclass
class RunSummary:
    found: int = 0
    new: int = 0
    matched: int = 0
    seeded: bool = False


def run(
    config: Config,
    *,
    dry_run: bool = False,
    seed: bool = False,
    now: datetime | None = None,
    fetch: PageFetcher = fetch_pages,
) -> RunSummary:
    now = now or datetime.now(timezone.utc)
    seen = load_seen(config.seen_path)
    # First run (no state yet) behaves like --seed so you aren't flooded with old jobs.
    seeding = seed or not seen

    jobs = [job for html in fetch(config.source_url, config.pages, config.http) for job in parse_jobs(html)]
    new = unseen(jobs, seen)
    matched = [] if seeding else config.filter.apply(new)
    summary = RunSummary(found=len(jobs), new=len(new), matched=len(matched), seeded=seeding)
    log.info("Listings found: %d | new: %d | matched: %d", summary.found, summary.new, summary.matched)

    if seeding:
        log.info("Seeding: recording %d current listings as seen without notifying", len(new))
    else:
        _warn_if_gap(jobs, new)
        for job in matched:
            log.info("Match (%s): [%s] %s", config.filter.matched_keyword(job), job.id, job.title)
        if dry_run:
            for job in matched:
                print(f"WOULD NOTIFY {describe(job)}")

    mark_seen(seen, new, now)
    removed = prune(seen, now, config.retention_days)
    if removed:
        log.info("Pruned %d IDs older than %d days", removed, config.retention_days)

    if dry_run:
        log.info("Dry run: state not saved")
    else:
        save_seen(config.seen_path, seen)
    return summary


def describe(job: Job) -> str:
    posted = job.posted.astimezone(PH_TZ).strftime("%Y-%m-%d %H:%M PHT") if job.posted else "?"
    return f"[{job.id}] {job.title} | {job.job_type or '-'} | {job.salary or '-'} | {posted}\n    {job.url}"


def _warn_if_gap(jobs: list[Job], new: list[Job]) -> None:
    # If even the oldest listing on the page is new, older new jobs may have
    # scrolled off the page since the last run.
    if jobs and len(new) == len(jobs):
        log.warning(
            "Possible gap: all %d listings are new, so some jobs may have been missed. "
            "If this keeps happening, set source.pages: 2 in config.yaml.",
            len(jobs),
        )
