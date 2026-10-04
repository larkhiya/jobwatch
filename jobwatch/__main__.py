"""CLI entry point: python -m jobwatch [--dry-run] [--seed]"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from pathlib import Path

from .ai import AiService, ClaudeAgentRunner
from .app import run_and_report
from .config import DEFAULT_CONFIG_PATH, Config, ConfigError, load_config, require_secrets
from .db import JobsStore, SupabaseJobsStore
from .fetch import CRAWL_DELAY_SECONDS, fetch_html
from .notify import Notifier, NtfyNotifier, PrintNotifier, TelegramNotifier

log = logging.getLogger("jobwatch")


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    _setup_output()
    try:
        config = load_config(args.config)
        notifier = PrintNotifier() if args.dry_run else _make_notifier(config)
    except ConfigError as exc:
        log.error("Configuration problem: %s", exc)
        return 2
    store = _make_store(config)
    return run_and_report(
        config, notifier, dry_run=args.dry_run, seed=args.seed, store=store, ai=_make_ai(config, store)
    )


def _make_store(config: Config) -> JobsStore | None:
    """The web app's database, if it's set up. Alerts work fine without it."""
    url, key = config.supabase_url, config.secrets.supabase_secret_key
    if url and key:
        return SupabaseJobsStore(url, key)
    if url or key:
        # Half-configured: say so loudly instead of silently leaving the web app empty.
        missing = "SUPABASE_SECRET_KEY secret" if url else "database.supabase_url in config.yaml"
        message = f"Database not updated: {missing} is missing."
        log.warning(message)
        print(f"::warning title=jobwatch database::{message}")
    return None


def _make_ai(config: Config, store: JobsStore | None) -> AiService | None:
    """The optional Claude features, if switched on and fully set up."""
    if not config.ai.enabled:
        return None
    secrets = config.secrets
    problem = None
    if store is None:
        problem = "it needs the database (your profile and the results live there)"
    elif not (secrets.claude_oauth_token or secrets.anthropic_api_key):
        problem = "the CLAUDE_CODE_OAUTH_TOKEN secret is missing (run `claude setup-token`)"
    if problem:
        message = f"AI is switched on but not running: {problem}."
        log.warning(message)
        print(f"::warning title=jobwatch AI::{message}")
        return None

    def fetch_job_page(url: str) -> str:
        time.sleep(CRAWL_DELAY_SECONDS)  # robots.txt crawl delay between requests to the site
        return fetch_html(url, config.http)

    runner = ClaudeAgentRunner(
        config.ai.model,
        secret=secrets.claude_oauth_token or secrets.anthropic_api_key,
        cli_path=os.environ.get("CLAUDE_CLI_PATH") or None,  # only needed for local runs on Windows
    )
    return AiService(config.ai, runner, store, fetch_job_page)


def _make_notifier(config: Config) -> Notifier:
    require_secrets(config)
    secrets = config.secrets
    if config.notify.channel == "ntfy":
        return NtfyNotifier(secrets.ntfy_topic, config.notify.ntfy_server)
    return TelegramNotifier(secrets.telegram_bot_token, secrets.telegram_chat_id)


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="jobwatch", description="OnlineJobs.ph developer job alerts")
    parser.add_argument("--dry-run", action="store_true", help="print what would be sent; send nothing, save nothing")
    parser.add_argument("--seed", action="store_true", help="record current listings as seen without notifying")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH, help="path to config.yaml")
    return parser.parse_args(argv)


def _setup_output() -> None:
    # Windows consoles default to cp1252, which crashes on job text like "₱". Force UTF-8.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")


if __name__ == "__main__":
    sys.exit(main())
