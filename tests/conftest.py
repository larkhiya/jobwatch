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
    return replace(load_config(CONFIG_PATH), state_dir=tmp_path / "state", **overrides)


@pytest.fixture(autouse=True)
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail loudly if any test tries to make a real HTTP request."""

    def blocked(*args, **kwargs):
        raise RuntimeError("Network access is disabled in tests")

    monkeypatch.setattr(requests.Session, "request", blocked)
