"""Notifications: message formatting plus Telegram / ntfy / print senders behind one interface."""

from __future__ import annotations

import html
from dataclasses import dataclass
from typing import Mapping, Protocol

import requests

from .parse import PH_TZ, Job

TELEGRAM_LIMIT = 4096  # max characters per Telegram message
NTFY_LIMIT = 3000  # characters; ntfy's limit is 4096 *bytes*, and "₱" or "–" take 3 bytes each
TIMEOUT_SECONDS = 20


class NotifyError(Exception):
    """A notification could not be delivered. The message never contains secrets."""


@dataclass(frozen=True)
class Message:
    title: str
    body: str
    jobs: tuple[Job, ...] = ()  # jobs this message announces (marked seen once it's sent)
    url: str | None = None  # where tapping the notification should go


class Notifier(Protocol):
    def send(self, message: Message) -> None: ...


# --- formatting ----------------------------------------------------------------


def job_message(job: Job, fit: str | None = None) -> Message:
    details = " · ".join(part for part in (job.job_type, job.salary) if part)
    lines = [fit] if fit else []  # optional AI fit line, e.g. "Fit 82/100 · apply: strong React match"
    if details:
        lines.append(details)
    if job.posted:
        lines.append(f"Posted {job.posted.astimezone(PH_TZ):%b %d, %H:%M} PHT")
    lines.append(job.url)
    return Message(title=job.title, body="\n".join(lines), jobs=(job,), url=job.url)


def digest_message(jobs: list[Job], fits: Mapping[str, str] | None = None) -> Message:
    fits = fits or {}
    items = []
    for job in jobs:
        salary = f" ({job.salary})" if job.salary else ""
        fit = f"\n  {fits[job.id]}" if job.id in fits else ""
        items.append(f"• {job.title}{salary}{fit}\n  {job.url}")
    return Message(title=f"{len(jobs)} new developer jobs on OnlineJobs.ph", body="\n\n".join(items), jobs=tuple(jobs))


def build_messages(jobs: list[Job], digest_threshold: int, fits: Mapping[str, str] | None = None) -> list[Message]:
    """One message per job, or a single digest when there are more than `digest_threshold`."""
    fits = fits or {}
    if len(jobs) > digest_threshold:
        return [digest_message(jobs, fits)]
    return [job_message(job, fits.get(job.id)) for job in jobs]


def analysis_ready_message(job: Job, analysis: Mapping[str, object], app_url: str | None) -> Message:
    body = (
        f"Fit {analysis['score']}/100 · {analysis['verdict']}\n{analysis['summary']}\n"
        "Open jobwatch for gaps, tips and a draft message."
    )
    return Message(title=f"Analysis ready: {job.title}", body=body, url=app_url or job.url)


def split_text(text: str, limit: int) -> list[str]:
    """Split on line breaks so each chunk fits in `limit` characters."""
    chunks: list[str] = []
    current = ""
    for line in text.split("\n"):
        while len(line) > limit:  # a single giant line: hard-cut it
            if current:
                chunks.append(current)
                current = ""
            chunks.append(line[:limit])
            line = line[limit:]
        candidate = f"{current}\n{line}" if current else line
        if len(candidate) > limit:
            chunks.append(current)
            candidate = line
        current = candidate
    if current:
        chunks.append(current)
    return chunks


def redact(text: str, *secrets: str | None) -> str:
    for secret in secrets:
        if secret:
            text = text.replace(secret, "***")
    return text


# --- senders --------------------------------------------------------------------


class TelegramNotifier:
    def __init__(self, bot_token: str, chat_id: str, session: requests.Session | None = None) -> None:
        self._token = bot_token
        self._chat_id = chat_id
        self._session = session or requests.Session()

    def send(self, message: Message) -> None:
        text = f"<b>{html.escape(message.title)}</b>\n{html.escape(message.body)}"
        for chunk in split_text(text, TELEGRAM_LIMIT):
            self._post(chunk)

    def _post(self, text: str) -> None:
        # The bot token is part of this URL, and requests puts URLs in its error
        # messages. So we never let a raw requests exception escape: we re-raise
        # a redacted NotifyError "from None" (which also hides the original traceback).
        url = f"https://api.telegram.org/bot{self._token}/sendMessage"
        payload = {"chat_id": self._chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
        try:
            response = self._session.post(url, json=payload, timeout=TIMEOUT_SECONDS)
        except requests.RequestException as exc:
            raise NotifyError(f"Telegram request failed: {redact(str(exc), self._token)}") from None
        if response.status_code != 200:
            raise NotifyError(f"Telegram HTTP {response.status_code}: {redact(_description(response), self._token)}")


class NtfyNotifier:
    def __init__(self, topic: str, server: str = "https://ntfy.sh", session: requests.Session | None = None) -> None:
        self._topic = topic
        self._server = server.rstrip("/")
        self._session = session or requests.Session()

    def send(self, message: Message) -> None:
        # ntfy turns messages over 4 KB into file attachments, which are awkward on a phone,
        # so long digests are sent as numbered parts instead.
        parts = split_text(message.body, NTFY_LIMIT)
        for number, part in enumerate(parts, start=1):
            title = f"{message.title} ({number}/{len(parts)})" if len(parts) > 1 else message.title
            self._post(title, part, message.url)

    def _post(self, title: str, body: str, url: str | None) -> None:
        # JSON publishing handles non-ASCII titles (e.g. "₱", "–"), which plain HTTP headers can't.
        # The topic goes in the body, not the URL, so it never shows up in error messages.
        payload = {"topic": self._topic, "title": title, "message": body, "tags": ["computer"]}
        if url:
            payload["click"] = url
        try:
            response = self._session.post(self._server, json=payload, timeout=TIMEOUT_SECONDS)
        except requests.RequestException as exc:
            raise NotifyError(f"ntfy request failed: {redact(str(exc), self._topic)}") from None
        if response.status_code != 200:
            raise NotifyError(f"ntfy HTTP {response.status_code}: {redact(response.text[:200], self._topic)}")


class PrintNotifier:
    """Used by --dry-run: shows exactly what would be sent, sends nothing."""

    def send(self, message: Message) -> None:
        print(f"----- would send -----\n{message.title}\n{message.body}\n----------------------")


def _description(response: requests.Response) -> str:
    try:
        return str(response.json().get("description", ""))
    except ValueError:
        return response.text[:200]
