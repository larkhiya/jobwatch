"""End-to-end runs with saved pages and a fake notifier (no network)."""

import logging
from datetime import datetime, timedelta, timezone

from jobwatch.app import run_and_report
from jobwatch.config import Secrets
from jobwatch.fetch import BlockedError, FetchError
from jobwatch.health import Health
from jobwatch.notify import PrintNotifier
from jobwatch.store import load_seen, save_seen

from .conftest import FakeNotifier, load_fixture, make_config

EARLY = datetime(2026, 10, 3, 22, 0, tzinfo=timezone.utc)  # 06:00 PHT: before the heartbeat hour


def serve(fixture_name):
    def fetch(url, pages, http):
        return [load_fixture(fixture_name)]

    return fetch


def fail_with(exc):
    def fetch(url, pages, http):
        raise exc

    return fetch


def seed(config, fixture_name="jobsearch_latest.html", now=EARLY):
    assert run_and_report(config, FakeNotifier(), now=now, fetch=serve(fixture_name)) == 0


def forget(config, *job_ids):
    seen = load_seen(config.seen_path)
    for job_id in job_ids:
        del seen[job_id]
    save_seen(config.seen_path, seen)


# --- seeding, dedupe, notifications ------------------------------------------------


def test_first_run_seeds_and_only_sends_a_setup_message(tmp_path):
    config = make_config(tmp_path)
    notifier = FakeNotifier()
    assert run_and_report(config, notifier, now=EARLY, fetch=serve("jobsearch_latest.html")) == 0
    assert notifier.titles == ["jobwatch is running"]
    assert len(load_seen(config.seen_path)) == 30
    assert Health.load(config.health_path).last_heartbeat == EARLY


def test_unchanged_page_sends_nothing(tmp_path):
    config = make_config(tmp_path)
    seed(config)
    notifier = FakeNotifier()
    run_and_report(config, notifier, now=EARLY + timedelta(minutes=15), fetch=serve("jobsearch_latest.html"))
    assert notifier.sent == []


def test_many_new_matches_are_sent_as_one_digest(tmp_path, caplog):
    caplog.set_level(logging.INFO)
    config = make_config(tmp_path)
    seed(config)  # latest-jobs page: no developer jobs
    notifier = FakeNotifier()
    run_and_report(config, notifier, now=EARLY, fetch=serve("jobsearch_developer.html"))
    assert notifier.titles == ["17 new developer jobs on OnlineJobs.ph"]
    assert len(notifier.sent[0].jobs) == 17
    assert len(load_seen(config.seen_path)) == 60  # every new ID is recorded, matching or not
    assert "Possible gap" in caplog.text
    assert "notified: 17" in caplog.text


def test_a_few_new_matches_are_sent_individually(tmp_path):
    config = make_config(tmp_path)
    seed(config, "jobsearch_developer.html")
    forget(config, "1742846", "1742338")
    notifier = FakeNotifier()
    run_and_report(config, notifier, now=EARLY, fetch=serve("jobsearch_developer.html"))
    assert notifier.titles == ["Senior WordPress Developer", "Full Stack Developer ( Java ) -- ASAP"]
    assert all(message.url in message.body for message in notifier.sent)


def test_failed_delivery_keeps_jobs_unseen_for_a_retry(tmp_path):
    config = make_config(tmp_path)
    seed(config, "jobsearch_developer.html")
    forget(config, "1742846", "1742498", "1742338")

    broken = FakeNotifier(fail_on_call=2)  # the first message goes out, then everything fails
    assert run_and_report(config, broken, now=EARLY, fetch=serve("jobsearch_developer.html")) == 1
    assert broken.titles == ["Senior WordPress Developer"]
    assert Health.load(config.health_path).errors == 1

    working = FakeNotifier()
    assert run_and_report(config, working, now=EARLY + timedelta(minutes=15), fetch=serve("jobsearch_developer.html")) == 0
    assert working.titles == ["Salesforce Developer (Integrations & App development)", "Full Stack Developer ( Java ) -- ASAP"]


def test_dry_run_prints_messages_and_saves_nothing(tmp_path, capsys):
    config = make_config(tmp_path)
    seed(config, "jobsearch_developer.html")
    forget(config, "1742846")
    seen_before = config.seen_path.read_text()
    health_before = config.health_path.read_text()

    run_and_report(config, PrintNotifier(), dry_run=True, now=EARLY, fetch=serve("jobsearch_developer.html"))

    assert "would send" in capsys.readouterr().out
    assert config.seen_path.read_text() == seen_before
    assert config.health_path.read_text() == health_before


def test_dry_run_previews_all_matches_on_the_page(tmp_path, caplog):
    caplog.set_level(logging.INFO)
    config = make_config(tmp_path)
    seed(config, "jobsearch_developer.html")  # everything already seen
    run_and_report(config, PrintNotifier(), dry_run=True, now=EARLY, fetch=serve("jobsearch_developer.html"))
    assert "17 of 30 listings on this page match" in caplog.text


# --- health: errors, parser alerts, heartbeat ------------------------------------------


def test_errors_alert_at_most_once_per_cooldown(tmp_path):
    config = make_config(tmp_path)  # error_alert_cooldown_hours: 6
    notifier = FakeNotifier()
    fetch = fail_with(FetchError("Giving up after 3 retries (Timeout)"))

    assert run_and_report(config, notifier, now=EARLY, fetch=fetch) == 1
    assert run_and_report(config, notifier, now=EARLY + timedelta(hours=1), fetch=fetch) == 1
    assert notifier.titles == ["jobwatch: run failed"]
    assert run_and_report(config, notifier, now=EARLY + timedelta(hours=7), fetch=fetch) == 1
    assert notifier.titles == ["jobwatch: run failed"] * 2


def test_block_alert_explains_what_happened(tmp_path):
    config = make_config(tmp_path)
    notifier = FakeNotifier()
    run_and_report(config, notifier, now=EARLY, fetch=fail_with(BlockedError("HTTP 403 from https://x")))
    assert "blocking automated requests" in notifier.sent[0].body


def test_secrets_are_redacted_from_error_alerts(tmp_path):
    config = make_config(tmp_path, secrets=Secrets(telegram_bot_token="123:SECRET", telegram_chat_id="42"))
    notifier = FakeNotifier()
    run_and_report(config, notifier, now=EARLY, fetch=fail_with(RuntimeError("boom at /bot123:SECRET/x")))
    assert "123:SECRET" not in notifier.sent[0].body
    assert "***" in notifier.sent[0].body


def test_empty_page_sends_parser_alert_once_per_day(tmp_path, capsys):
    config = make_config(tmp_path)
    notifier = FakeNotifier()
    fetch = serve("jobsearch_empty.html")

    assert run_and_report(config, notifier, now=EARLY, fetch=fetch) == 0  # warning, not a failed run
    assert run_and_report(config, notifier, now=EARLY + timedelta(hours=2), fetch=fetch) == 0
    assert notifier.titles == ["jobwatch: parser may be broken"]
    assert "::warning" in capsys.readouterr().out
    run_and_report(config, notifier, now=EARLY + timedelta(hours=25), fetch=fetch)
    assert notifier.titles == ["jobwatch: parser may be broken"] * 2


def test_heartbeat_is_sent_once_per_day_after_the_configured_hour(tmp_path):
    config = make_config(tmp_path)
    seed(config, now=EARLY - timedelta(days=1))  # seeded yesterday
    fetch = serve("jobsearch_latest.html")
    morning = datetime(2026, 10, 4, 1, 0, tzinfo=timezone.utc)  # 09:00 PHT

    notifier = FakeNotifier()
    run_and_report(config, notifier, now=EARLY, fetch=fetch)  # 06:00 PHT: too early
    assert notifier.sent == []
    run_and_report(config, notifier, now=morning, fetch=fetch)
    run_and_report(config, notifier, now=morning + timedelta(minutes=15), fetch=fetch)
    assert notifier.titles == ["jobwatch heartbeat"]
    assert "jobwatch alive" in notifier.sent[0].body
    run_and_report(config, notifier, now=morning + timedelta(days=1), fetch=fetch)
    assert notifier.titles == ["jobwatch heartbeat"] * 2
