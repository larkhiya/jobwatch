"""Turn an OnlineJobs.ph search results page into Job objects."""

from __future__ import annotations

import copy
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

log = logging.getLogger(__name__)

SITE_ROOT = "https://www.onlinejobs.ph"
PH_TZ = timezone(timedelta(hours=8))  # Philippine time; no daylight saving.

# The stable job ID is the number at the end of the job URL:
#   /jobseekers/job/senior-wordpress-developer-1742846  ->  "1742846"
_JOB_ID_RE = re.compile(r"/jobseekers/job/(?:.*-)?(\d+)/?$")
_WHITESPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class Job:
    id: str
    title: str
    url: str
    posted: datetime | None  # timezone-aware, UTC
    salary: str | None
    snippet: str
    job_type: str | None  # "Full Time", "Part Time", "Gig", "Any"
    tags: tuple[str, ...] = ()

    @property
    def search_text(self) -> str:
        """Everything the keyword filters look at."""
        return " ".join([self.title, self.snippet, *self.tags])


def parse_jobs(html: str) -> list[Job]:
    """Extract all job cards from a results page, in page order, without duplicates."""
    soup = BeautifulSoup(html, "html.parser")
    jobs: list[Job] = []
    seen_ids: set[str] = set()

    for card in soup.select("div.jobpost-cat-box"):
        job = _parse_card(card)
        if job is None or job.id in seen_ids:
            continue
        seen_ids.add(job.id)
        jobs.append(job)
    return jobs


def _parse_card(card: Tag) -> Job | None:
    link = card.find_parent("a", href=True)
    href = link["href"] if link else ""
    match = _JOB_ID_RE.search(href.split("?")[0])
    heading = card.find("h4")
    if not match or heading is None:
        log.debug("Skipping card without a job link or title: %r", href)
        return None

    return Job(
        id=match.group(1),
        title=_title(heading),
        url=urljoin(SITE_ROOT, href),
        posted=_posted(card),
        salary=_salary(card),
        snippet=_snippet(card),
        job_type=_text(heading.select_one(".badge")) or None,
        tags=tuple(t for t in (_text(a) for a in card.select("div.job-tag a.badge")) if t),
    )


def _text(node: Tag | None) -> str:
    if node is None:
        return ""
    return _WHITESPACE_RE.sub(" ", node.get_text(" ")).strip()


def _title(heading: Tag) -> str:
    heading = copy.copy(heading)  # don't mutate the original tree
    for badge in heading.select(".badge"):
        badge.decompose()
    return _text(heading)


def _posted(card: Tag) -> datetime | None:
    stamp = card.find("p", attrs={"data-temp-2": True})
    if stamp is not None:  # data-temp-2 is UTC
        return _parse_time(stamp["data-temp-2"], timezone.utc)
    stamp = card.find("p", attrs={"data-temp": True})
    if stamp is not None:  # data-temp is Philippine time
        return _parse_time(stamp["data-temp"], PH_TZ)
    return None


def _parse_time(value: str, tz: timezone) -> datetime | None:
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d %H:%M:%S").replace(tzinfo=tz).astimezone(timezone.utc)
    except ValueError:
        return None


def _salary(card: Tag) -> str | None:
    icon = card.select_one(".icon-round-dollar")
    row = icon.find_parent("dl") if icon else None
    return _text(row.find("dd") if row else None) or None


def _snippet(card: Tag) -> str:
    desc = card.select_one("div.desc")
    if desc is None:
        return ""
    desc = copy.copy(desc)
    for link in desc.find_all("a"):  # the "See More" link
        link.decompose()
    text = _text(desc).rstrip("�…").rstrip()  # site truncates, sometimes mid-character
    return f"{text}…" if text else ""
