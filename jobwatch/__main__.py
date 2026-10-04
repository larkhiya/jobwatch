"""CLI entry point: python -m jobwatch [--dry-run] [--seed]"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .app import run_and_report
from .config import DEFAULT_CONFIG_PATH, Config, ConfigError, load_config, require_secrets
from .db import JobsStore, SupabaseJobsStore
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
    return run_and_report(config, notifier, dry_run=args.dry_run, seed=args.seed, store=_make_store(config))


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
