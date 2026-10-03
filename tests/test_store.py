import json
from datetime import datetime, timedelta, timezone

from jobwatch.parse import Job
from jobwatch.store import load_seen, mark_seen, prune, save_seen, unseen

NOW = datetime(2026, 10, 4, 12, 0, tzinfo=timezone.utc)


def job(job_id: str, title: str = "Web Developer") -> Job:
    return Job(id=job_id, title=title, url=f"https://x.test/{job_id}", posted=None, salary=None, snippet="", job_type=None)


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
