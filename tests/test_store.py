import json
from datetime import datetime, timedelta, timezone

from jobwatch.app import run
from jobwatch.parse import Job
from jobwatch.store import load_seen, mark_seen, prune, save_seen, unseen

from .conftest import load_fixture, make_config

NOW = datetime(2026, 10, 4, 12, 0, tzinfo=timezone.utc)


def job(job_id: str, title: str = "Web Developer") -> Job:
    return Job(id=job_id, title=title, url=f"https://x.test/{job_id}", posted=None, salary=None, snippet="", job_type=None)


def fixture_fetch(url, pages, http):
    return [load_fixture("jobsearch_latest.html")]


# --- store functions -------------------------------------------------------


def test_save_and_load_round_trip(tmp_path):
    path = tmp_path / "state" / "seen.json"
    save_seen(path, {"2": NOW, "1": NOW - timedelta(days=1)})
    assert load_seen(path) == {"1": NOW - timedelta(days=1), "2": NOW}
    assert json.loads(path.read_text()) == {"1": "2026-10-03T12:00:00Z", "2": "2026-10-04T12:00:00Z"}
    assert not (tmp_path / "state" / "seen.json.tmp").exists()


def test_missing_file_loads_as_empty(tmp_path):
    assert load_seen(tmp_path / "nope.json") == {}


def test_dedupe_is_by_id_not_title():
    seen = {"100": NOW}
    jobs = [job("100", "Web Developer"), job("101", "Web Developer")]
    assert [j.id for j in unseen(jobs, seen)] == ["101"]


def test_mark_seen_keeps_the_first_seen_time():
    seen = {"100": NOW - timedelta(days=3)}
    mark_seen(seen, [job("100"), job("101")], NOW)
    assert seen == {"100": NOW - timedelta(days=3), "101": NOW}


def test_prune_removes_only_entries_older_than_retention():
    seen = {"old": NOW - timedelta(days=46), "edge": NOW - timedelta(days=45), "new": NOW}
    assert prune(seen, NOW, 45) == 1
    assert set(seen) == {"edge", "new"}


# --- run(): seeding and dedupe end to end ------------------------------------


def test_first_run_seeds_all_listings(tmp_path):
    config = make_config(tmp_path)
    summary = run(config, now=NOW, fetch=fixture_fetch)
    assert summary.seeded and summary.found == 30 and summary.new == 30
    assert len(load_seen(config.seen_path)) == 30


def test_second_run_finds_nothing_new(tmp_path):
    config = make_config(tmp_path)
    run(config, now=NOW, fetch=fixture_fetch)
    summary = run(config, now=NOW + timedelta(minutes=15), fetch=fixture_fetch)
    assert not summary.seeded and summary.new == 0


def test_only_unseen_ids_count_as_new(tmp_path):
    config = make_config(tmp_path)
    run(config, now=NOW, fetch=fixture_fetch)
    seen = load_seen(config.seen_path)
    del seen["1463731"]
    save_seen(config.seen_path, seen)
    summary = run(config, now=NOW, fetch=fixture_fetch)
    assert summary.new == 1
    assert "1463731" in load_seen(config.seen_path)


def test_dry_run_does_not_save_state(tmp_path):
    config = make_config(tmp_path)
    run(config, dry_run=True, now=NOW, fetch=fixture_fetch)
    assert not config.seen_path.exists()


def test_all_new_listings_logs_a_gap_warning(tmp_path, caplog):
    config = make_config(tmp_path)
    save_seen(config.seen_path, {"999": NOW})  # not empty, so this isn't a seed run
    run(config, now=NOW, fetch=fixture_fetch)
    assert "Possible gap" in caplog.text
