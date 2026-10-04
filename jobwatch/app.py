"""One run of the pipeline: fetch -> parse -> dedupe -> filter -> notify -> save state -> save to database."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from .config import Config
from .db import JobsStore, job_rows
from .fetch import BlockedError, HttpSettings, fetch_pages
from .health import Health, cooldown_over
from .notify import Message, Notifier, build_messages, redact
from .parse import Job, parse_jobs
from .store import Seen, load_seen, mark_seen, prune, save_seen, unseen

log = logging.getLogger(__name__)

PageFetcher = Callable[[str, int, HttpSettings], list[str]]


@dataclass
class RunSummary:
    found: int = 0
    new: int = 0
    matched: int = 0
    notified: int = 0
    seeded: bool = False


def run_and_report(
    config: Config,
    notifier: Notifier,
    *,
    dry_run: bool = False,
    seed: bool = False,
    now: datetime | None = None,
    fetch: PageFetcher = fetch_pages,
    store: JobsStore | None = None,
) -> int:
    """Run once, turn failures into (rate-limited) alerts, and return the process exit code."""
    now = now or datetime.now(timezone.utc)
    health = Health.load(config.health_path)
    health.runs += 1
    exit_code = 0

    try:
        summary = run(config, notifier, health, dry_run=dry_run, seed=seed, now=now, fetch=fetch, store=store)
        if summary.seeded and health.last_heartbeat is None:
            health.last_heartbeat = now  # the "jobwatch is running" message counts as today's heartbeat
        health.new_listings += summary.new
        health.jobs_sent += summary.notified
        if health.heartbeat_due(now, config.health.heartbeat_hour, config.health.tz):
            notifier.send(Message(title="jobwatch heartbeat", body=health.heartbeat_text()))
            health.reset_counters(now)
    except Exception as exc:  # anything unexpected: log it, alert (rate-limited), fail the run
        log.exception("Run failed")
        health.errors += 1
        _send_error_alert(config, notifier, health, exc, now)
        exit_code = 1

    if not dry_run:
        health.save(config.health_path)
    return exit_code


def run(
    config: Config,
    notifier: Notifier,
    health: Health,
    *,
    dry_run: bool = False,
    seed: bool = False,
    now: datetime,
    fetch: PageFetcher = fetch_pages,
    store: JobsStore | None = None,
) -> RunSummary:
    seen = load_seen(config.seen_path)
    # First run (no state yet) behaves like --seed so you aren't flooded with old jobs.
    seeding = seed or not seen

    jobs = [job for html in fetch(config.source_url, config.pages, config.http) for job in parse_jobs(html)]
    if not jobs:
        _report_empty_page(config, notifier, health, now)
        return RunSummary(seeded=seeding)

    if dry_run:
        _preview_filters(config, jobs)

    new = unseen(jobs, seen)
    matched = [] if seeding else config.filter.apply(new)
    summary = RunSummary(found=len(jobs), new=len(new), matched=len(matched), seeded=seeding)

    # Non-matching jobs are done with. Matching ones are only marked seen once
    # their notification is actually delivered (see _notify), so a failed send
    # is retried on the next run instead of being silently lost.
    matched_ids = {job.id for job in matched}
    mark_seen(seen, [job for job in new if job.id not in matched_ids], now)
    try:
        if seeding:
            log.info("Seeding: recorded %d current listings as seen without notifying", len(new))
            notifier.send(Message(
                title="jobwatch is running",
                body=f"Recorded {len(new)} current listings. You'll get a message for each new matching job.",
            ))
        else:
            _warn_if_gap(jobs, new)
            for job in matched:
                log.info("Match (%s): [%s] %s", config.filter.matched_keyword(job), job.id, job.title)
            summary.notified = _notify(notifier, matched, seen, now, config.notify.digest_threshold)
    finally:
        removed = prune(seen, now, config.retention_days)
        if removed:
            log.info("Pruned %d IDs older than %d days", removed, config.retention_days)
        if dry_run:
            log.info("Dry run: state not saved")
        else:
            save_seen(config.seen_path, seen)
        log.info(
            "Listings found: %d | new: %d | matched: %d | notified: %d",
            summary.found, summary.new, summary.matched, summary.notified,
        )

    # Last, so a database problem can never block your alerts. Every listing on the page is
    # upserted each run, so a failed write heals itself on the next run.
    if store is not None:
        if dry_run:
            log.info("Dry run: database not updated")
        else:
            store.upsert_jobs(job_rows(jobs, config.filter, now))
            log.info("Saved %d listings to the database", len(jobs))
    return summary


def _notify(notifier: Notifier, jobs: list[Job], seen: Seen, now: datetime, digest_threshold: int) -> int:
    sent = 0
    for message in build_messages(jobs, digest_threshold):
        notifier.send(message)  # raises on failure -> remaining jobs stay unseen
        mark_seen(seen, list(message.jobs), now)
        sent += len(message.jobs)
    return sent


def _report_empty_page(config: Config, notifier: Notifier, health: Health, now: datetime) -> None:
    # The page loaded fine (no HTTP error) but had no job cards: most likely the
    # site's HTML changed and the parser needs updating.
    text = "The search page loaded but 0 listings were parsed. The site layout may have changed."
    log.warning(text)
    print(f"::warning title=jobwatch parser::{text}")  # shows as an annotation in GitHub Actions
    if cooldown_over(health.last_parser_alert, now, config.health.parser_alert_cooldown_hours):
        notifier.send(Message(title="jobwatch: parser may be broken", body=f"{text}\n{config.source_url}"))
        health.last_parser_alert = now


def _send_error_alert(config: Config, notifier: Notifier, health: Health, exc: Exception, now: datetime) -> None:
    if not cooldown_over(health.last_error_alert, now, config.health.error_alert_cooldown_hours):
        log.info("Error alert suppressed (one was sent less than %dh ago)", config.health.error_alert_cooldown_hours)
        return
    secrets = config.secrets
    detail = redact(
        f"{type(exc).__name__}: {exc}", secrets.telegram_bot_token, secrets.ntfy_topic, secrets.supabase_secret_key
    )
    hint = (
        "OnlineJobs.ph seems to be blocking automated requests. jobwatch will not try to get around this; "
        "see README > Troubleshooting."
        if isinstance(exc, BlockedError)
        else "Check the GitHub Actions log for details."
    )
    try:
        notifier.send(Message(title="jobwatch: run failed", body=f"{detail[:500]}\n{hint}"))
        health.last_error_alert = now
    except Exception:
        log.exception("Could not send the error alert either")


def _preview_filters(config: Config, jobs: list[Job]) -> None:
    """Dry runs show which listings on the page match, seen or not, to make keyword tuning easy."""
    preview = config.filter.apply(jobs)
    log.info("Filter preview: %d of %d listings on this page match your keywords", len(preview), len(jobs))
    for job in preview:
        log.info("  (%s) %s  %s", config.filter.matched_keyword(job), job.title, job.url)


def _warn_if_gap(jobs: list[Job], new: list[Job]) -> None:
    # If even the oldest listing on the page is new, older new jobs may have
    # scrolled off the page since the last run.
    if len(new) == len(jobs):
        log.warning(
            "Possible gap: all %d listings are new, so some jobs may have been missed. "
            "If this keeps happening, set source.pages: 2 in config.yaml.",
            len(jobs),
        )
