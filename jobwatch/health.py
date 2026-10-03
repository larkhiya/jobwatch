"""Health tracking (state/health.json): alert cooldowns, daily counters and the heartbeat."""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .store import load_json, save_json

_TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
_TIME_FIELDS = ("last_parser_alert", "last_error_alert", "last_heartbeat")


@dataclass
class Health:
    last_parser_alert: datetime | None = None
    last_error_alert: datetime | None = None
    last_heartbeat: datetime | None = None
    # Counters since the last heartbeat:
    runs: int = 0
    new_listings: int = 0
    jobs_sent: int = 0
    errors: int = 0

    @classmethod
    def load(cls, path: Path) -> Health:
        raw = load_json(path) or {}
        known = {f.name for f in fields(cls)}
        values = {key: value for key, value in raw.items() if key in known}
        for key in _TIME_FIELDS:
            if values.get(key):
                values[key] = datetime.strptime(values[key], _TIME_FORMAT).replace(tzinfo=timezone.utc)
        return cls(**values)

    def save(self, path: Path) -> None:
        data = asdict(self)
        for key in _TIME_FIELDS:
            if data[key] is not None:
                data[key] = data[key].astimezone(timezone.utc).strftime(_TIME_FORMAT)
        save_json(path, data)

    def heartbeat_due(self, now: datetime, hour: int, tz: timezone) -> bool:
        """True on the first run at/after `hour` local time each day."""
        local_now = now.astimezone(tz)
        if local_now.hour < hour:
            return False
        if self.last_heartbeat is None:
            return True
        return self.last_heartbeat.astimezone(tz).date() < local_now.date()

    def heartbeat_text(self) -> str:
        return (
            f"jobwatch alive: {self.new_listings} new listings checked, "
            f"{self.jobs_sent} matching jobs sent, {self.runs} runs, {self.errors} errors "
            "since the last heartbeat."
        )

    def reset_counters(self, now: datetime) -> None:
        self.last_heartbeat = now
        self.runs = self.new_listings = self.jobs_sent = self.errors = 0


def cooldown_over(last_sent: datetime | None, now: datetime, hours: int) -> bool:
    return last_sent is None or now - last_sent >= timedelta(hours=hours)
