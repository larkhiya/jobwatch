"""Keyword filters: include (any match) and exclude (any match rejects)."""

from __future__ import annotations

import re
from typing import Iterable

from .parse import Job

_SEPARATOR_RE = re.compile(r"[\s\-]+")


def compile_keyword(keyword: str) -> re.Pattern[str]:
    """Build a case-insensitive, whole-word pattern for one keyword.

    - Whole words only: "react" matches "React dev" but not "reactive".
    - Spaces/hyphens are interchangeable and optional: "full stack" matches
      "Full Stack", "full-stack" and "fullstack".
    - A trailing plural "s" is allowed: "developer" matches "Developers".
    We use (?<!\\w) / (?!\\w) instead of \\b so keywords like "c++" still work.
    """
    words = [re.escape(word) for word in _SEPARATOR_RE.split(keyword.strip()) if word]
    body = r"[\s\-]*".join(words)
    return re.compile(rf"(?<!\w){body}s?(?!\w)", re.IGNORECASE)


class KeywordFilter:
    def __init__(self, include: Iterable[str], exclude: Iterable[str] = ()) -> None:
        self.include = tuple(include)
        self.exclude = tuple(exclude)
        self._include = [(keyword, compile_keyword(keyword)) for keyword in self.include]
        self._exclude = [compile_keyword(keyword) for keyword in self.exclude]

    def matched_keyword(self, job: Job) -> str | None:
        """The first include keyword that matches, or None if the job is filtered out."""
        text = job.search_text
        if any(pattern.search(text) for pattern in self._exclude):
            return None
        for keyword, pattern in self._include:
            if pattern.search(text):
                return keyword
        return None

    def apply(self, jobs: list[Job]) -> list[Job]:
        return [job for job in jobs if self.matched_keyword(job)]
