from dataclasses import replace
from pathlib import Path

import pytest
import requests

from jobwatch.config import Config, load_config

FIXTURES = Path(__file__).parent / "fixtures"
CONFIG_PATH = Path(__file__).parents[1] / "config.yaml"


def load_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def make_config(tmp_path: Path, **overrides) -> Config:
    """The real config.yaml, but with state kept in a temporary folder."""
    return replace(load_config(CONFIG_PATH, env={}), state_dir=tmp_path / "state", **overrides)


class FakeNotifier:
    """Records messages instead of sending them. Can be told to fail."""

    def __init__(self, fail_on_call: int | None = None):
        self.sent = []
        self.fail_on_call = fail_on_call  # 1-based call number that raises
        self.calls = 0

    def send(self, message) -> None:
        from jobwatch.notify import NotifyError

        self.calls += 1
        if self.fail_on_call is not None and self.calls >= self.fail_on_call:
            raise NotifyError("simulated delivery failure")
        self.sent.append(message)

    @property
    def titles(self) -> list[str]:
        return [message.title for message in self.sent]


@pytest.fixture(autouse=True)
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail loudly if any test tries to make a real HTTP request."""

    def blocked(*args, **kwargs):
        raise RuntimeError("Network access is disabled in tests")

    monkeypatch.setattr(requests.Session, "request", blocked)
