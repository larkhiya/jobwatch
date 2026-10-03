"""HTTP fetching: one polite GET per page, with timeout, retries and block detection."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Callable
from urllib.parse import urlsplit, urlunsplit

import requests

log = logging.getLogger(__name__)

PAGE_SIZE = 30  # OnlineJobs.ph shows 30 jobs per results page.
CRAWL_DELAY_SECONDS = 5  # From robots.txt; only matters when fetching more than one page.

# Strings that only appear on Cloudflare challenge / block pages, never on a normal page.
# (We deliberately avoid generic words like "captcha" that a login modal could contain.)
_CHALLENGE_MARKERS = (
    "<title>just a moment...</title>",
    "<title>attention required! | cloudflare</title>",
    "cf-chl-",
    "_cf_chl_opt",
    "cf_chl_",
)


class FetchError(Exception):
    """The page could not be fetched (network problem or unexpected HTTP status)."""


class BlockedError(FetchError):
    """The site refused us (403/429 or a bot challenge). We never try to get around this."""


@dataclass(frozen=True)
class HttpSettings:
    user_agent: str
    timeout_seconds: float = 20
    max_retries: int = 3


def page_urls(base_url: str, pages: int) -> list[str]:
    """URLs for the first `pages` result pages.

    Page 1 is the base URL; later pages put an offset in the path:
    /jobseekers/jobsearch -> /jobseekers/jobsearch/30, /60, ... (query string kept).
    """
    parts = urlsplit(base_url)
    path = parts.path.rstrip("/")
    urls = [base_url]
    for page in range(1, pages):
        offset_path = f"{path}/{page * PAGE_SIZE}"
        urls.append(urlunsplit(parts._replace(path=offset_path)))
    return urls


def looks_like_challenge(html: str) -> bool:
    lowered = html.lower()
    return any(marker in lowered for marker in _CHALLENGE_MARKERS)


def fetch_html(
    url: str,
    settings: HttpSettings,
    session: requests.Session | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> str:
    """GET `url` and return its HTML.

    Retries (with exponential backoff: 2s, 4s, 8s) only on problems that are
    usually temporary: timeouts, connection errors and 5xx responses.
    A 403/429 or challenge page raises BlockedError immediately, without retrying.
    """
    session = session or requests.Session()
    headers = {"User-Agent": settings.user_agent, "Accept": "text/html"}
    last_problem = ""

    for attempt in range(settings.max_retries + 1):
        if attempt:
            delay = 2**attempt
            log.warning("Retry %d/%d in %ds (%s)", attempt, settings.max_retries, delay, last_problem)
            sleep(delay)
        try:
            response = session.get(url, headers=headers, timeout=settings.timeout_seconds)
        except (requests.Timeout, requests.ConnectionError) as exc:
            last_problem = type(exc).__name__
            continue

        # The site declares UTF-8; decode explicitly so salary symbols survive.
        html = response.content.decode("utf-8", errors="replace")
        status = response.status_code

        if status in (403, 429) or looks_like_challenge(html):
            raise BlockedError(
                f"HTTP {status} from {url}: the site appears to be blocking automated requests"
            )
        if status >= 500:
            last_problem = f"HTTP {status}"
            continue
        if status != 200:
            raise FetchError(f"Unexpected HTTP {status} from {url}")
        return html

    raise FetchError(f"Giving up on {url} after {settings.max_retries} retries ({last_problem})")


def fetch_pages(
    base_url: str,
    pages: int,
    settings: HttpSettings,
    session: requests.Session | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> list[str]:
    """Fetch result pages in order, pausing between them to respect the crawl delay."""
    session = session or requests.Session()
    htmls: list[str] = []
    for index, url in enumerate(page_urls(base_url, pages)):
        if index:
            sleep(CRAWL_DELAY_SECONDS)
        log.info("Fetching %s", url)
        htmls.append(fetch_html(url, settings, session=session, sleep=sleep))
    return htmls
