"""International roles from public ATS job-board APIs.

Greenhouse and Ashby both expose documented, unauthenticated JSON endpoints for
every company that uses them, so there is no HTML parsing and no bot-blocking.
Only companies with a public board are scraped, and only postings that a
candidate outside the employer's country could realistically hold are kept -
role-level "Remote" is preserved so the matcher can gate on it honestly.
"""

from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Iterable

import requests

from scrapers.utils import SiteScrapeError

logger = logging.getLogger(__name__)

USER_AGENT = "MukanaJobIngest/1.0 (+job-listing-ingestion)"

# Boards that reliably hire remotely and publish a public JSON feed. Extend via
# MUKANA_GREENHOUSE_BOARDS / MUKANA_ASHBY_BOARDS without touching this file.
DEFAULT_GREENHOUSE_BOARDS = (
    "cloudflare",
    "gitlab",
    "stripe",
    "airbnb",
    "hashicorp",
    "elastic",
    "canonical",
    "automattic",
    "mozilla",
    "sentry",
    "twilio",
    "datadog",
)

DEFAULT_ASHBY_BOARDS = (
    "ramp",
    "openai",
    "linear",
    "posthog",
    "supabase",
    "vercel",
    "neon",
)

# Postings whose location reads as one of these are plausible from Zimbabwe.
_GLOBAL_TERMS = (
    "remote",
    "anywhere",
    "worldwide",
    "global",
    "emea",
    "africa",
    "distributed",
)

# Only these explicit signals mean "hireable from anywhere". Anything else -
# including a bare city, or "Remote (Sweden)" - is treated as region-locked.
# An allowlist beats listing every country/city on earth and missing one.
_GLOBAL_TERMS = (
    "worldwide",
    "anywhere",
    "fully remote",
    "remote - global",
    "remote (global)",
    "global remote",
    "emea",
    "africa",
    "distributed",
)

# Boards use these to mean "remote within the country named nearby".
_COUNTRY_HINT = re.compile(
    r"\b(united states|usa|u\.s\.|us|canada|united kingdom|uk|germany|france|"
    r"sweden|norway|denmark|finland|spain|poland|portugal|netherlands|ireland|"
    r"india|australia|singapore|japan|brazil|mexico|argentina|colombia|"
    r"philippines|nigeria|kenya|south africa|d\.c\.|dc)\b",
    re.IGNORECASE,
)

# Allow opting back into region-locked remote roles if the policy changes.
INCLUDE_REGION_LOCKED = os.getenv("MUKANA_INCLUDE_REGION_LOCKED", "").strip() == "1"


def _boards(env_name: str, defaults: Iterable[str]) -> list[str]:
    raw = os.getenv(env_name, "").strip()
    if raw:
        return [item.strip().lower() for item in raw.split(",") if item.strip()]
    return list(defaults)


def _iso_date(value: str | None) -> str | None:
    """Return YYYY-MM-DD from an ISO timestamp, or None."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(timezone.utc).date().isoformat()


def _is_reachable(location: str, remote_flag: bool) -> bool:
    """Keep only roles a Zimbabwe-based candidate could realistically hold.

    Deliberately an allowlist: a posting is kept only when its location carries
    an explicit global signal, or when it says plainly "Remote" with no country
    attached. "Remote - US", "New York, NY" and "Remote (Sweden)" all mean work
    authorisation somewhere else, so applying would waste the user's time.
    """
    text = " ".join((location or "").strip().lower().split())

    if INCLUDE_REGION_LOCKED:
        return bool(text) or bool(remote_flag)

    if any(term in text for term in _GLOBAL_TERMS):
        return True
    if _COUNTRY_HINT.search(text):
        return False
    return text in {"remote", "remote/hybrid", "hybrid remote"}


def _remote_label(location: str, remote_flag: bool) -> str | None:
    text = (location or "").lower()
    if remote_flag or any(
        term in text for term in ("remote", "anywhere", "distributed", "global")
    ):
        return "Remote"
    if "hybrid" in text:
        return "Hybrid"
    return "On-site" if text.strip() else None


class GreenhouseScraper:
    """Public Greenhouse job-board API."""

    base_url = "https://boards-api.greenhouse.io/v1/boards"

    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})
        self.boards = _boards("MUKANA_GREENHOUSE_BOARDS", DEFAULT_GREENHOUSE_BOARDS)

    def scrape_jobs(
        self,
        max_pages: int = 1,
        delay: float | None = None,
        max_jobs: int | None = None,
        existing_urls: set[str] | None = None,
    ) -> list[dict]:
        existing_urls = existing_urls or set()
        results: list[dict] = []
        limit = max_jobs or 200

        for board in self.boards:
            if len(results) >= limit:
                break
            url = f"{self.base_url}/{board}/jobs?content=true"
            try:
                response = self.session.get(url, timeout=30)
            except requests.RequestException as exc:
                logger.warning("Greenhouse %s unreachable: %s", board, exc)
                continue
            if response.status_code == 404:
                logger.info("Greenhouse board '%s' does not exist - skipping", board)
                continue
            if response.status_code != 200:
                logger.warning("Greenhouse %s returned %s", board, response.status_code)
                continue

            try:
                jobs = response.json().get("jobs", [])
            except ValueError:
                logger.warning("Greenhouse %s returned invalid JSON", board)
                continue

            kept = 0
            for job in jobs:
                if len(results) >= limit:
                    break
                mapped = self._map(job, board)
                if not mapped or mapped["source_url"] in existing_urls:
                    continue
                results.append(mapped)
                kept += 1
            logger.info("Greenhouse %s: %d kept of %d", board, kept, len(jobs))

        if not results:
            logger.warning("Greenhouse returned no reachable roles")
        return results

    def _map(self, job: dict[str, Any], board: str) -> dict | None:
        source_url = job.get("absolute_url")
        title = (job.get("title") or "").strip()
        if not source_url or not title:
            return None

        location = ((job.get("location") or {}).get("name") or "").strip()
        if not _is_reachable(location, False):
            return None

        departments = job.get("departments") or []
        category = departments[0].get("name") if departments else None

        return {
            "source": "greenhouse",
            "source_url": source_url,
            "title": title,
            "company": (job.get("company_name") or board).strip(),
            "location": location or None,
            "description": _strip_html(job.get("content") or ""),
            "job_type": None,
            "compensation": None,
            "date_posted": _iso_date(job.get("first_published") or job.get("updated_at")),
            "expires": _iso_date(job.get("application_deadline")),
            "category": category,
            "remote": _remote_label(location, False),
            "apply_instructions": f"Apply online: {source_url}",
        }


class AshbyScraper:
    """Public Ashby job-board API."""

    base_url = "https://api.ashbyhq.com/posting-api/job-board"

    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})
        self.boards = _boards("MUKANA_ASHBY_BOARDS", DEFAULT_ASHBY_BOARDS)

    def scrape_jobs(
        self,
        max_pages: int = 1,
        delay: float | None = None,
        max_jobs: int | None = None,
        existing_urls: set[str] | None = None,
    ) -> list[dict]:
        existing_urls = existing_urls or set()
        results: list[dict] = []
        limit = max_jobs or 200

        for board in self.boards:
            if len(results) >= limit:
                break
            try:
                response = self.session.get(f"{self.base_url}/{board}", timeout=30)
            except requests.RequestException as exc:
                logger.warning("Ashby %s unreachable: %s", board, exc)
                continue
            if response.status_code == 404:
                logger.info("Ashby board '%s' does not exist - skipping", board)
                continue
            if response.status_code != 200:
                logger.warning("Ashby %s returned %s", board, response.status_code)
                continue

            try:
                jobs = response.json().get("jobs", [])
            except ValueError:
                logger.warning("Ashby %s returned invalid JSON", board)
                continue

            kept = 0
            for job in jobs:
                if len(results) >= limit:
                    break
                mapped = self._map(job, board)
                if not mapped or mapped["source_url"] in existing_urls:
                    continue
                results.append(mapped)
                kept += 1
            logger.info("Ashby %s: %d kept of %d", board, kept, len(jobs))

        if not results:
            logger.warning("Ashby returned no reachable roles")
        return results

    def _map(self, job: dict[str, Any], board: str) -> dict | None:
        source_url = job.get("jobUrl") or job.get("applyUrl")
        title = (job.get("title") or "").strip()
        if not source_url or not title:
            return None
        if job.get("isListed") is False:
            return None

        location = (job.get("location") or "").strip()
        remote_flag = bool(job.get("isRemote"))
        if not _is_reachable(location, remote_flag):
            return None

        employment = job.get("employmentType")
        job_type = {
            "FullTime": "Full-time",
            "PartTime": "Part-time",
            "Intern": "Internship",
            "Contract": "Contract",
            "Temporary": "Temporary",
        }.get(str(employment), None)

        return {
            "source": "ashby",
            "source_url": source_url,
            "title": title,
            "company": board.replace("-", " ").title(),
            "location": location or None,
            "description": (job.get("descriptionPlain") or "").strip() or None,
            "job_type": job_type,
            "compensation": None,
            "date_posted": _iso_date(job.get("publishedAt")),
            "expires": None,
            "category": job.get("department") or None,
            "remote": _remote_label(location, remote_flag),
            "apply_instructions": f"Apply online: {job.get('applyUrl') or source_url}",
        }


_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"[ \t]+")


def _strip_html(html: str) -> str | None:
    """Greenhouse returns HTML-escaped markup; convert it to readable text."""
    if not html:
        return None
    from html import unescape

    text = unescape(html)
    text = re.sub(r"<(br|/p|/div|/li|/h[1-6])[^>]*>", "\n", text, flags=re.IGNORECASE)
    text = _TAG_RE.sub("", text)
    text = _WS_RE.sub(" ", text)
    lines = [line.strip() for line in text.splitlines()]
    cleaned = "\n".join(line for line in lines if line)
    return cleaned or None
