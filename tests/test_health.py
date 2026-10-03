from datetime import datetime, timedelta, timezone

from jobwatch.health import Health, cooldown_over

PHT = timezone(timedelta(hours=8))
UTC = timezone.utc


def at(text: str) -> datetime:
    """'2026-10-04 08:30' in Philippine time -> aware datetime."""
    return datetime.strptime(text, "%Y-%m-%d %H:%M").replace(tzinfo=PHT)


def test_cooldown():
    now = at("2026-10-04 12:00")
    assert cooldown_over(None, now, 24)
    assert not cooldown_over(now - timedelta(hours=23), now, 24)
    assert cooldown_over(now - timedelta(hours=24), now, 24)


def test_heartbeat_waits_for_the_configured_hour():
    assert not Health().heartbeat_due(at("2026-10-04 07:59"), 8, PHT)
    assert Health().heartbeat_due(at("2026-10-04 08:00"), 8, PHT)


def test_heartbeat_once_per_local_day():
    health = Health(last_heartbeat=at("2026-10-04 08:10"))
    assert not health.heartbeat_due(at("2026-10-04 23:50"), 8, PHT)
    assert not health.heartbeat_due(at("2026-10-05 07:50"), 8, PHT)  # next day, but too early
    assert health.heartbeat_due(at("2026-10-05 08:05"), 8, PHT)


def test_reset_counters():
    health = Health(runs=96, new_listings=300, jobs_sent=4, errors=1)
    assert "300 new listings checked, 4 matching jobs sent, 96 runs, 1 errors" in health.heartbeat_text()
    now = at("2026-10-04 08:00")
    health.reset_counters(now)
    assert (health.runs, health.new_listings, health.jobs_sent, health.errors) == (0, 0, 0, 0)
    assert health.last_heartbeat == now


def test_save_and_load_round_trip(tmp_path):
    path = tmp_path / "health.json"
    health = Health(last_error_alert=datetime(2026, 10, 4, 1, 2, 3, tzinfo=UTC), runs=5)
    health.save(path)
    assert Health.load(path) == health


def test_load_tolerates_missing_file_and_unknown_keys(tmp_path):
    assert Health.load(tmp_path / "missing.json") == Health()
    path = tmp_path / "health.json"
    path.write_text('{"runs": 3, "from_a_future_version": true}')
    assert Health.load(path).runs == 3
