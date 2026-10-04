"""Load config.yaml (settings) and environment variables (secrets) into one validated object."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

import yaml

from .fetch import HttpSettings
from .filters import KeywordFilter

DEFAULT_CONFIG_PATH = Path("config.yaml")
_NTFY_TOPIC_RE = re.compile(r"[-_A-Za-z0-9]{1,64}")


class ConfigError(Exception):
    """config.yaml or the environment is missing something or has a bad value."""


@dataclass(frozen=True)
class NotifySettings:
    channel: str  # "telegram" or "ntfy"
    digest_threshold: int
    ntfy_server: str


@dataclass(frozen=True)
class HealthSettings:
    tz: timezone
    heartbeat_hour: int
    parser_alert_cooldown_hours: int
    error_alert_cooldown_hours: int


@dataclass(frozen=True)
class Secrets:
    """Read only from environment variables. repr=False keeps them out of logs and tracebacks."""

    telegram_bot_token: str | None = field(default=None, repr=False)
    telegram_chat_id: str | None = field(default=None, repr=False)
    ntfy_topic: str | None = field(default=None, repr=False)
    supabase_secret_key: str | None = field(default=None, repr=False)


@dataclass(frozen=True)
class Config:
    source_url: str
    pages: int
    http: HttpSettings
    state_dir: Path
    retention_days: int
    filter: KeywordFilter
    notify: NotifySettings
    health: HealthSettings
    supabase_url: str | None = None  # optional: where the web app's database lives
    secrets: Secrets = field(default_factory=Secrets, repr=False)

    @property
    def seen_path(self) -> Path:
        return self.state_dir / "seen.json"

    @property
    def health_path(self) -> Path:
        return self.state_dir / "health.json"


def load_config(path: Path = DEFAULT_CONFIG_PATH, env: Mapping[str, str] = os.environ) -> Config:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except FileNotFoundError:
        raise ConfigError(f"Config file not found: {path}") from None
    except yaml.YAMLError as exc:
        raise ConfigError(f"{path} is not valid YAML: {exc}") from None

    source = _section(raw, "source")
    http = _section(raw, "http")
    state = _section(raw, "state")
    filters = _section(raw, "filters")
    notify = _section(raw, "notify")
    health = _section(raw, "health")

    # The SUPABASE_URL env var (a GitHub repository variable shared with the web app) wins over config.yaml.
    supabase_url = _env(env, "SUPABASE_URL") or str((raw.get("database") or {}).get("supabase_url") or "").strip() or None
    if supabase_url and not supabase_url.startswith("https://"):
        raise ConfigError("database.supabase_url must start with https://")

    channel = notify.get("channel", "telegram")
    if channel not in ("telegram", "ntfy"):
        raise ConfigError("notify.channel must be 'telegram' or 'ntfy'")

    url = _require(source, "url", str, "source")
    if not url.startswith("https://"):
        raise ConfigError("source.url must start with https://")

    return Config(
        source_url=url,
        pages=_int_in_range(source, "pages", "source", 1, 3, default=1),
        http=HttpSettings(
            user_agent=_require(http, "user_agent", str, "http"),
            timeout_seconds=_int_in_range(http, "timeout_seconds", "http", 5, 60, default=20),
            max_retries=_int_in_range(http, "max_retries", "http", 0, 3, default=3),
        ),
        state_dir=Path(_require(state, "dir", str, "state")),
        retention_days=_int_in_range(state, "retention_days", "state", 1, 365, default=45),
        filter=KeywordFilter(
            include=_keywords(filters, "include_keywords", required=True),
            exclude=_keywords(filters, "exclude_keywords", required=False),
        ),
        notify=NotifySettings(
            channel=channel,
            digest_threshold=_int_in_range(notify, "digest_threshold", "notify", 1, 50, default=5),
            ntfy_server=str(notify.get("ntfy_server") or "https://ntfy.sh"),
        ),
        health=HealthSettings(
            tz=timezone(timedelta(hours=_int_in_range(health, "utc_offset_hours", "health", -12, 14, default=8))),
            heartbeat_hour=_int_in_range(health, "heartbeat_hour", "health", 0, 23, default=8),
            parser_alert_cooldown_hours=_int_in_range(health, "parser_alert_cooldown_hours", "health", 1, 168, default=24),
            error_alert_cooldown_hours=_int_in_range(health, "error_alert_cooldown_hours", "health", 1, 168, default=6),
        ),
        supabase_url=supabase_url,
        secrets=Secrets(
            telegram_bot_token=_env(env, "TELEGRAM_BOT_TOKEN"),
            telegram_chat_id=_env(env, "TELEGRAM_CHAT_ID"),
            ntfy_topic=_env(env, "NTFY_TOPIC"),
            supabase_secret_key=_env(env, "SUPABASE_SECRET_KEY"),
        ),
    )


def require_secrets(config: Config) -> None:
    """Fail early, with a clear message, if the chosen channel's secrets aren't set."""
    needed = {
        "telegram": {"TELEGRAM_BOT_TOKEN": config.secrets.telegram_bot_token, "TELEGRAM_CHAT_ID": config.secrets.telegram_chat_id},
        "ntfy": {"NTFY_TOPIC": config.secrets.ntfy_topic},
    }[config.notify.channel]
    missing = [name for name, value in needed.items() if not value]
    if missing:
        raise ConfigError(
            f"Missing environment variable(s) for notify.channel={config.notify.channel}: {', '.join(missing)}. "
            "Set them as GitHub Secrets (or locally in your shell)."
        )
    topic = config.secrets.ntfy_topic
    if config.notify.channel == "ntfy" and not _NTFY_TOPIC_RE.fullmatch(topic or ""):
        # Don't echo the value: it's a secret. Common mistake: pasting the full https://ntfy.sh/... URL.
        raise ConfigError(
            "NTFY_TOPIC must be just the topic name (letters, digits, '-' or '_', up to 64 characters), "
            "not a URL like https://ntfy.sh/<topic>."
        )


def _env(env: Mapping[str, str], name: str) -> str | None:
    value = env.get(name, "").strip()
    return value or None


def _section(raw: dict[str, Any], name: str) -> dict[str, Any]:
    value = raw.get(name)
    if not isinstance(value, dict):
        raise ConfigError(f"config.yaml needs a '{name}:' section")
    return value


def _require(section: dict[str, Any], key: str, kind: type, where: str) -> Any:
    value = section.get(key)
    if not isinstance(value, kind) or (kind is str and not value.strip()):
        raise ConfigError(f"{where}.{key} is missing or not a {kind.__name__}")
    return value


def _int_in_range(section: dict[str, Any], key: str, where: str, low: int, high: int, default: int) -> int:
    value = section.get(key, default)
    if not isinstance(value, int) or isinstance(value, bool) or not low <= value <= high:
        raise ConfigError(f"{where}.{key} must be a whole number from {low} to {high}")
    return value


def _keywords(section: dict[str, Any], key: str, required: bool) -> tuple[str, ...]:
    value = section.get(key) or []
    if not isinstance(value, list) or not all(isinstance(k, str) and k.strip() for k in value):
        raise ConfigError(f"filters.{key} must be a list of words/phrases")
    if required and not value:
        raise ConfigError(f"filters.{key} needs at least one keyword")
    return tuple(k.strip() for k in value)
