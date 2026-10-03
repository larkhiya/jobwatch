"""Load config.yaml (settings) and environment variables (secrets) into one validated object."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .fetch import HttpSettings

DEFAULT_CONFIG_PATH = Path("config.yaml")


class ConfigError(Exception):
    """config.yaml or the environment is missing something or has a bad value."""


@dataclass(frozen=True)
class Config:
    source_url: str
    pages: int
    http: HttpSettings
    state_dir: Path
    retention_days: int

    @property
    def seen_path(self) -> Path:
        return self.state_dir / "seen.json"


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> Config:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except FileNotFoundError:
        raise ConfigError(f"Config file not found: {path}") from None
    except yaml.YAMLError as exc:
        raise ConfigError(f"{path} is not valid YAML: {exc}") from None

    source = _section(raw, "source")
    http = _section(raw, "http")
    state = _section(raw, "state")

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
    )


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
