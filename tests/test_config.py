import pytest

from jobwatch.config import ConfigError, load_config, require_secrets

from .conftest import CONFIG_PATH


def write_config(tmp_path, old: str, new: str):
    path = tmp_path / "config.yaml"
    path.write_text(CONFIG_PATH.read_text(encoding="utf-8").replace(old, new), encoding="utf-8")
    return path


def test_real_config_loads():
    config = load_config(CONFIG_PATH, env={})
    assert config.source_url == "https://www.onlinejobs.ph/jobseekers/jobsearch"
    assert config.http.timeout_seconds == 20 and config.http.max_retries == 3
    assert "developer" in config.filter.include and "unpaid" in config.filter.exclude
    assert config.notify.channel == "ntfy" and config.notify.digest_threshold == 5


def test_secrets_come_from_env_and_never_show_in_repr():
    config = load_config(CONFIG_PATH, env={"NTFY_TOPIC": "jobwatch-SECRET-7f3k9q"})
    assert config.secrets.ntfy_topic == "jobwatch-SECRET-7f3k9q"
    assert "SECRET" not in repr(config)
    require_secrets(config)  # does not raise


def test_ntfy_channel_needs_topic():
    with pytest.raises(ConfigError, match="NTFY_TOPIC"):
        require_secrets(load_config(CONFIG_PATH, env={}))


@pytest.mark.parametrize("topic", ["https://ntfy.sh/jobwatch-abc", "my topic", "x" * 65])
def test_ntfy_topic_must_be_a_bare_name(topic):
    with pytest.raises(ConfigError, match="just the topic name") as info:
        require_secrets(load_config(CONFIG_PATH, env={"NTFY_TOPIC": topic}))
    assert topic not in str(info.value)  # never echo the secret


def test_telegram_channel_names_missing_secrets(tmp_path):
    path = write_config(tmp_path, "channel: ntfy", "channel: telegram")
    with pytest.raises(ConfigError, match="TELEGRAM_BOT_TOKEN"):
        require_secrets(load_config(path, env={"TELEGRAM_CHAT_ID": "42"}))
    require_secrets(load_config(path, env={"TELEGRAM_BOT_TOKEN": "123:abc", "TELEGRAM_CHAT_ID": "42"}))


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        ("channel: ntfy", "channel: email", "notify.channel"),
        ("pages: 1", "pages: 10", "source.pages"),
        ("timeout_seconds: 20", "timeout_seconds: fast", "http.timeout_seconds"),
        ("url: https://www", "url: http://www", "https"),
    ],
)
def test_bad_values_give_clear_errors(tmp_path, old, new, message):
    with pytest.raises(ConfigError, match=message):
        load_config(write_config(tmp_path, old, new), env={})


def test_missing_file():
    with pytest.raises(ConfigError, match="not found"):
        load_config(CONFIG_PATH.with_name("nope.yaml"))
