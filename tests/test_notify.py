from dataclasses import replace

import pytest
import requests

from jobwatch.notify import (
    TELEGRAM_LIMIT,
    NotifyError,
    NtfyNotifier,
    TelegramNotifier,
    build_messages,
    digest_message,
    job_message,
    split_text,
)
from jobwatch.parse import parse_jobs

from .conftest import load_fixture

TOKEN = "123456:SECRET-TOKEN"


class FakeResponse:
    def __init__(self, status=200, payload=None, text=""):
        self.status_code = status
        self._payload = payload
        self.text = text

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


class FakeSession:
    def __init__(self, response=None, error=None):
        self.response = response or FakeResponse(200, {"ok": True})
        self.error = error
        self.posts = []

    def post(self, url, json, timeout):
        self.posts.append({"url": url, "json": json, "timeout": timeout})
        if self.error:
            raise self.error
        return self.response


@pytest.fixture
def dev_jobs():
    return {job.id: job for job in parse_jobs(load_fixture("jobsearch_developer.html"))}


# --- formatting ----------------------------------------------------------------------


def test_job_message_has_title_type_salary_posted_and_link(dev_jobs):
    job = dev_jobs["1742998"]
    message = job_message(job)
    assert message.title == "Mortgage / Lending GoHighLevel Developer + Advanced Claude Expert"
    assert message.body.splitlines() == [
        "Full Time · $8/hr",
        "Posted Oct 03, 21:33 PHT",
        "https://www.onlinejobs.ph/jobseekers/job/mortgage-lending-gohighlevel-developer-advanced-claude-expert-1742998",
    ]
    assert message.url == job.url and message.jobs == (job,)


def test_job_message_skips_missing_salary_and_date(dev_jobs):
    job = replace(dev_jobs["1742998"], salary=None, posted=None)
    assert job_message(job).body.splitlines() == ["Full Time", job.url]


def test_digest_lists_every_job_with_its_link(dev_jobs):
    jobs = list(dev_jobs.values())[:7]
    message = digest_message(jobs)
    assert message.title == "7 new developer jobs on OnlineJobs.ph"
    assert all(job.url in message.body for job in jobs)


def test_digest_only_above_threshold(dev_jobs):
    jobs = list(dev_jobs.values())
    assert len(build_messages(jobs[:5], digest_threshold=5)) == 5
    assert len(build_messages(jobs[:6], digest_threshold=5)) == 1


def test_split_text_respects_limit_and_keeps_content():
    text = "\n".join(f"line {i} " + "x" * 50 for i in range(300))
    chunks = split_text(text, 1000)
    assert all(len(chunk) <= 1000 for chunk in chunks)
    assert "\n".join(chunks) == text


def test_split_text_hard_cuts_a_giant_line():
    chunks = split_text("a" * 2500, 1000)
    assert [len(c) for c in chunks] == [1000, 1000, 500]


# --- Telegram ------------------------------------------------------------------------


def test_telegram_posts_escaped_html(dev_jobs):
    session = FakeSession()
    TelegramNotifier(TOKEN, "42", session).send(job_message(dev_jobs["1743001"]))
    post = session.posts[0]
    assert post["url"] == f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    assert post["json"]["chat_id"] == "42"
    assert post["json"]["parse_mode"] == "HTML"
    assert post["json"]["text"].startswith("<b>Shopify Web Developer &amp; CRO Specialist")
    assert post["timeout"] == 20


def test_telegram_splits_long_digests(dev_jobs):
    session = FakeSession()
    jobs = list(dev_jobs.values()) * 5  # ~150 entries, well over 4096 characters
    TelegramNotifier(TOKEN, "42", session).send(digest_message(jobs))
    assert len(session.posts) > 1
    assert all(len(p["json"]["text"]) <= TELEGRAM_LIMIT for p in session.posts)


def test_telegram_network_error_never_leaks_the_token(dev_jobs):
    error = requests.ConnectionError(f"Max retries exceeded with url: /bot{TOKEN}/sendMessage")
    notifier = TelegramNotifier(TOKEN, "42", FakeSession(error=error))
    with pytest.raises(NotifyError) as info:
        notifier.send(job_message(dev_jobs["1743001"]))
    assert TOKEN not in str(info.value)
    assert info.value.__cause__ is None and info.value.__suppress_context__  # original hidden


def test_telegram_api_error_includes_description(dev_jobs):
    response = FakeResponse(400, {"ok": False, "description": "Bad Request: chat not found"})
    with pytest.raises(NotifyError, match="chat not found"):
        TelegramNotifier(TOKEN, "42", FakeSession(response)).send(job_message(dev_jobs["1743001"]))


# --- ntfy ----------------------------------------------------------------------------


def test_ntfy_publishes_json_with_click_link(dev_jobs):
    session = FakeSession()
    job = dev_jobs["1742978"]
    NtfyNotifier("my-secret-topic", "https://ntfy.sh/", session).send(job_message(job))
    post = session.posts[0]
    assert post["url"] == "https://ntfy.sh"  # topic is in the body, not the URL
    assert post["json"]["topic"] == "my-secret-topic"
    assert post["json"]["title"] == job.title  # non-ASCII is fine in JSON
    assert post["json"]["click"] == job.url


def test_ntfy_error_redacts_topic(dev_jobs):
    response = FakeResponse(429, text="limit reached for topic my-secret-topic")
    with pytest.raises(NotifyError) as info:
        NtfyNotifier("my-secret-topic", session=FakeSession(response)).send(job_message(dev_jobs["1742978"]))
    assert "my-secret-topic" not in str(info.value)
