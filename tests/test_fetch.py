import pytest
import requests

from jobwatch.fetch import (
    BlockedError,
    FetchError,
    HttpSettings,
    fetch_html,
    fetch_pages,
    looks_like_challenge,
    page_urls,
)

from .conftest import load_fixture

SETTINGS = HttpSettings(user_agent="jobwatch-test", timeout_seconds=20, max_retries=3)


class FakeResponse:
    def __init__(self, status: int, body: str = "<html>ok</html>"):
        self.status_code = status
        self.content = body.encode("utf-8")


class FakeSession:
    """Returns (or raises) the queued results in order and records each call."""

    def __init__(self, *results):
        self.results = list(results)
        self.calls = []

    def get(self, url, headers, timeout):
        self.calls.append({"url": url, "headers": headers, "timeout": timeout})
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def no_sleep(seconds):
    pass


def test_success_sends_user_agent_and_timeout():
    session = FakeSession(FakeResponse(200, "<html>jobs ₱</html>"))
    assert fetch_html("https://example.test/", SETTINGS, session, no_sleep) == "<html>jobs ₱</html>"
    assert session.calls[0]["headers"]["User-Agent"] == "jobwatch-test"
    assert session.calls[0]["timeout"] == 20


def test_retries_server_errors_with_exponential_backoff():
    delays = []
    session = FakeSession(FakeResponse(502), requests.Timeout(), FakeResponse(200))
    fetch_html("https://example.test/", SETTINGS, session, delays.append)
    assert delays == [2, 4]


def test_gives_up_after_max_retries():
    session = FakeSession(*[requests.ConnectionError()] * 4)
    with pytest.raises(FetchError, match="after 3 retries"):
        fetch_html("https://example.test/", SETTINGS, session, no_sleep)
    assert len(session.calls) == 4  # 1 try + 3 retries


@pytest.mark.parametrize("status", [403, 429])
def test_block_statuses_are_not_retried(status):
    session = FakeSession(FakeResponse(status))
    with pytest.raises(BlockedError):
        fetch_html("https://example.test/", SETTINGS, session, no_sleep)
    assert len(session.calls) == 1


def test_challenge_page_is_treated_as_block_even_with_200():
    session = FakeSession(FakeResponse(200, load_fixture("challenge.html")))
    with pytest.raises(BlockedError):
        fetch_html("https://example.test/", SETTINGS, session, no_sleep)


def test_other_client_errors_fail_without_retry():
    session = FakeSession(FakeResponse(404))
    with pytest.raises(FetchError, match="HTTP 404"):
        fetch_html("https://example.test/", SETTINGS, session, no_sleep)
    assert len(session.calls) == 1


def test_real_page_is_not_mistaken_for_a_challenge():
    assert not looks_like_challenge(load_fixture("jobsearch_latest.html"))
    assert looks_like_challenge(load_fixture("challenge.html"))


def test_page_urls_use_offsets_and_keep_query():
    assert page_urls("https://www.onlinejobs.ph/jobseekers/jobsearch?jobkeyword=developer", 3) == [
        "https://www.onlinejobs.ph/jobseekers/jobsearch?jobkeyword=developer",
        "https://www.onlinejobs.ph/jobseekers/jobsearch/30?jobkeyword=developer",
        "https://www.onlinejobs.ph/jobseekers/jobsearch/60?jobkeyword=developer",
    ]


def test_fetch_pages_pauses_between_pages_for_crawl_delay():
    delays = []
    session = FakeSession(FakeResponse(200, "a"), FakeResponse(200, "b"))
    assert fetch_pages("https://example.test/jobs", 2, SETTINGS, session, delays.append) == ["a", "b"]
    assert delays == [5]
