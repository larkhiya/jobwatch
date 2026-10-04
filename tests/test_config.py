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


def test_database_is_optional_and_validated(tmp_path):
    assert load_config(CONFIG_PATH, env={}).supabase_url is None
    path = write_config(tmp_path, 'supabase_url: ""', 'supabase_url: "https://abc.supabase.co"')
    config = load_config(path, env={"SUPABASE_SECRET_KEY": "sb_secret_x"})
    assert config.supabase_url == "https://abc.supabase.co"
    assert "sb_secret_x" not in repr(config)
    with pytest.raises(ConfigError, match="supabase_url"):
        load_config(write_config(tmp_path, 'supabase_url: ""', 'supabase_url: "http://abc"'), env={})


def test_half_configured_database_warns_instead_of_failing(tmp_path, capsys):
    from jobwatch.__main__ import _make_store

    assert _make_store(load_config(CONFIG_PATH, env={})) is None  # not set up: silent
    assert _make_store(load_config(CONFIG_PATH, env={"SUPABASE_SECRET_KEY": "sb_secret_x"})) is None
    assert "database.supabase_url" in capsys.readouterr().out
    path = write_config(tmp_path, 'supabase_url: ""', 'supabase_url: "https://abc.supabase.co"')
    assert _make_store(load_config(path, env={"SUPABASE_SECRET_KEY": "sb_secret_x"})) is not None
