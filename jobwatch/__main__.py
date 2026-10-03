"""CLI entry point: python -m jobwatch [--dry-run]"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .config import DEFAULT_CONFIG_PATH, load_config
from .fetch import fetch_pages
from .parse import PH_TZ, Job, parse_jobs

log = logging.getLogger("jobwatch")


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    _setup_output()

    config = load_config(args.config)
    pages = fetch_pages(config.source_url, config.pages, config.http)
    jobs = [job for html in pages for job in parse_jobs(html)]
    log.info("Listings found: %d", len(jobs))

    if args.dry_run:
        for job in jobs:
            print(_describe(job))
    return 0


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="jobwatch", description="OnlineJobs.ph developer job alerts")
    parser.add_argument("--dry-run", action="store_true", help="print what would be sent; send nothing, save nothing")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH, help="path to config.yaml")
    return parser.parse_args(argv)


def _setup_output() -> None:
    # Windows consoles default to cp1252, which crashes on job text like "₱". Force UTF-8.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")


def _describe(job: Job) -> str:
    posted = job.posted.astimezone(PH_TZ).strftime("%Y-%m-%d %H:%M PHT") if job.posted else "?"
    return f"[{job.id}] {job.title} | {job.job_type or '-'} | {job.salary or '-'} | {posted}\n    {job.url}"


if __name__ == "__main__":
    sys.exit(main())
