from datetime import datetime, timezone

import pytest
import requests

from jobwatch.app import run_and_report
from jobwatch.db import DatabaseError, SupabaseJobsStore, job_rows
from jobwatch.health import Health
from jobwatch.parse import parse_jobs
from jobwatch.store import load_seen

from .conftest import FakeNotifier, load_fixture, make_config

NOW = datetime(2026, 10, 3, 22, 0, tzinfo=timezone.utc)  # 06:00 PHT: no heartbeat
SECRET = "sb_secret_TESTKEY123"


class FakeResponse:
    def __init__(self, status=201, text=""):
        self.status_code = status
        self.text = text


class FakeSession:
    def __init__(self, response=None, error=None):
        self.response = response or FakeResponse()
        self.error = error
        self.posts = []

    def post(self, url, params, json, headers, timeout):
        self.posts.append({"url": url, "params": params, "json": json, "headers": headers, "timeout": timeout})
        if self.error:
            raise self.error
        return self.response


class RecordingStore:
    def __init__(self, fail: bool = False):
        self.calls = []
        self.fail = fail

    def upsert_jobs(self, rows):
        if self.fail:
            raise DatabaseError("Supabase HTTP 500: boom")
        self.calls.append(rows)


def serve(name):
    return lambda url, pages, http: [load_fixture(name)]


# --- rows ---------------------------------------------------------------------------------


def test_job_rows_have_every_column_and_the_matched_keyword(tmp_path):
    config = make_config(tmp_path)
    rows = {row["id"]: row for row in job_rows(parse_jobs(load_fixture("jobsearch_developer.html")), config.filter, NOW)}
    row = rows["1742846"]
    assert row["title"] == "Senior WordPress Developer"
    assert row["matched_keyword"] == "developer"
    assert row["url"].endswith("-1742846")
    assert row["posted_at"].endswith("+00:00")
    assert isinstance(row["tags"], list)
    assert row["updated_at"] == "2026-10-03T22:00:00+00:00"
    assert "first_seen_at" not in row  # set by the database, never overwritten
    assert rows["1742325"]["matched_keyword"] is None  # QA Engineer: filtered out


# --- Supabase REST client ---------------------------------------------------------------------


def test_upsert_posts_all_rows_in_one_request():
    session = FakeSession()
    SupabaseJobsStore("https://abc.supabase.co/", SECRET, session).upsert_jobs([{"id": "1"}, {"id": "2"}])
    post = session.posts[0]
    assert post["url"] == "https://abc.supabase.co/rest/v1/jobs"
    assert post["params"] == {"on_conflict": "id"}
    assert post["json"] == [{"id": "1"}, {"id": "2"}]
    assert post["headers"]["apikey"] == SECRET
    assert "resolution=merge-duplicates" in post["headers"]["Prefer"]
    assert "Authorization" not in post["headers"]  # new-style keys go in apikey only


def test_legacy_service_role_key_is_also_sent_as_bearer():
    session = FakeSession()
    SupabaseJobsStore("https://abc.supabase.co", "eyJhbGciOi.legacy.jwt", session).upsert_jobs([{"id": "1"}])
    assert session.posts[0]["headers"]["Authorization"] == "Bearer eyJhbGciOi.legacy.jwt"


def test_nothing_to_save_makes_no_request():
    session = FakeSession()
    SupabaseJobsStore("https://abc.supabase.co", SECRET, session).upsert_jobs([])
    assert session.posts == []


def test_errors_never_contain_the_key():
    response = FakeResponse(401, text=f"Invalid API key {SECRET}")
    with pytest.raises(DatabaseError, match="HTTP 401") as info:
        SupabaseJobsStore("https://abc.supabase.co", SECRET, FakeSession(response)).upsert_jobs([{"id": "1"}])
    assert SECRET not in str(info.value)

    error = requests.ConnectionError(f"failed with key {SECRET}")
    with pytest.raises(DatabaseError) as info:
        SupabaseJobsStore("https://abc.supabase.co", SECRET, FakeSession(error=error)).upsert_jobs([{"id": "1"}])
    assert SECRET not in str(info.value) and info.value.__cause__ is None


# --- in the pipeline --------------------------------------------------------------------------


def test_every_run_saves_all_listings_including_the_seed_run(tmp_path):
    config = make_config(tmp_path)
    store = RecordingStore()
    run_and_report(config, FakeNotifier(), now=NOW, fetch=serve("jobsearch_latest.html"), store=store)
    run_and_report(config, FakeNotifier(), now=NOW, fetch=serve("jobsearch_developer.html"), store=store)
    assert [len(rows) for rows in store.calls] == [30, 30]


def test_dry_run_does_not_write_to_the_database(tmp_path):
    store = RecordingStore()
    run_and_report(make_config(tmp_path), FakeNotifier(), dry_run=True, now=NOW, fetch=serve("jobsearch_latest.html"), store=store)
    assert store.calls == []


def test_database_failure_never_blocks_alerts(tmp_path):
    config = make_config(tmp_path)
    run_and_report(config, FakeNotifier(), now=NOW, fetch=serve("jobsearch_latest.html"))  # seed
    notifier = FakeNotifier()
    exit_code = run_and_report(
        config, notifier, now=NOW, fetch=serve("jobsearch_developer.html"), store=RecordingStore(fail=True)
    )
    assert exit_code == 1  # the run is marked failed...
    assert notifier.titles == ["17 new developer jobs on OnlineJobs.ph", "jobwatch: run failed"]  # ...after alerting
    assert len(load_seen(config.seen_path)) == 60  # and state was still saved
    assert Health.load(config.health_path).errors == 1
