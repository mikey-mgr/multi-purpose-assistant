"""ApplyNow job ingestion via its public WordPress REST API."""

from __future__ import annotations

from datetime import datetime
from html import unescape
import logging
import re
import time
from typing import Any

import requests
from bs4 import BeautifulSoup

from scrapers.utils import SiteScrapeError, render_links

logger = logging.getLogger(__name__)


class ApplyNowScraper:
    """Collect paid jobs and internships from ApplyNow's Zimbabwe and remote feeds."""

    base_url = "https://applynow.co.zw"
    api_url = f"{base_url}/wp-json/wp/v2"
    feed_tags = {"zimbabwe": "Zimbabwe", "remote": "Remote"}
    excluded_terms = (
        "scholarship", "grant", "fellowship", "course", "contest",
    )
    role_terms = (
        "job", "hiring", "vacancy", "recruit", "position", "role", "intern",
        "career", "employment", "consultant", "officer", "manager", "developer",
        "engineer", "analyst", "assistant", "director", "specialist", "coordinator",
    )

    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "MovoJobAssistant/1.0 (+job-listing-ingestion)",
            "Accept": "application/json",
        })
        self._taxonomy_cache: dict[tuple[str, tuple[int, ...]], dict[int, str]] = {}

    def scrape_jobs(
        self,
        max_pages: int = 1,
        delay: float | None = None,
        max_jobs: int | None = None,
        existing_urls: set[str] | None = None,
    ) -> list[dict]:
        """Return eligible Zimbabwe and remote listings in the shared job schema.

        ``max_pages`` applies independently to each feed.  A post present in both
        feeds is represented once and is marked remote.
        """
        delay = 2 if delay is None else max(0, delay)
        existing_urls = existing_urls or set()
        discovered: dict[str, dict[str, Any]] = {}

        for tag_slug in self.feed_tags:
            tag_id = self._tag_id(tag_slug, delay)
            if tag_id is None:
                continue
            for page in range(1, max_pages + 1):
                posts = self._fetch_json(
                    "posts",
                    {"tags": tag_id, "per_page": 10, "page": page,
                     "_fields": "id,date,link,tags,categories,title,content"},
                )
                self._pause(delay)
                if not posts:
                    break
                for post in posts:
                    url = (post.get("link") or "").rstrip("/") + "/"
                    if not url:
                        continue
                    item = discovered.setdefault(url, {"post": post, "remote": False})
                    item["remote"] = item["remote"] or tag_slug == "remote"

        jobs: list[dict] = []
        skipped_existing = 0
        for url, item in discovered.items():
            if max_jobs is not None and len(jobs) >= max_jobs:
                break
            if url in existing_urls:
                skipped_existing += 1
                continue
            job = self._to_job(item["post"], remote_from_feed=item["remote"], delay=delay)
            if job:
                jobs.append(job)

        logger.info(
            "ApplyNow returned %d eligible jobs (%d existing URLs skipped).",
            len(jobs), skipped_existing,
        )
        return jobs

    def _tag_id(self, slug: str, delay: float) -> int | None:
        tags = self._fetch_json("tags", {"slug": slug, "per_page": 1})
        self._pause(delay)
        if not tags:
            logger.warning("ApplyNow tag '%s' was not found.", slug)
            return None
        return tags[0].get("id")

    def _fetch_json(self, endpoint: str, params: dict[str, Any]) -> list[dict]:
        try:
            response = self.session.get(f"{self.api_url}/{endpoint}", params=params, timeout=20)
            if response.status_code in {403, 429}:
                raise SiteScrapeError("applynow", f"HTTP {response.status_code} from ApplyNow")
            response.raise_for_status()
            payload = response.json()
            return payload if isinstance(payload, list) else []
        except SiteScrapeError:
            raise
        except requests.RequestException as exc:
            logger.warning("ApplyNow request failed for %s: %s", endpoint, exc)
        except ValueError as exc:
            logger.warning("ApplyNow returned invalid JSON for %s: %s", endpoint, exc)
        return []

    @staticmethod
    def _pause(delay: float) -> None:
        if delay:
            time.sleep(delay)

    def _taxonomy_names(self, taxonomy: str, ids: list[int], delay: float) -> list[str]:
        ids = sorted({int(value) for value in ids if value is not None})
        if not ids:
            return []
        key = (taxonomy, tuple(ids))
        if key not in self._taxonomy_cache:
            entries = self._fetch_json(taxonomy, {"include": ",".join(map(str, ids)), "per_page": 100})
            self._pause(delay)
            self._taxonomy_cache[key] = {
                entry["id"]: unescape(entry.get("name", "")).strip()
                for entry in entries if entry.get("id") is not None
            }
        return [self._taxonomy_cache[key][item_id] for item_id in ids if item_id in self._taxonomy_cache[key]]

    def _to_job(self, post: dict, remote_from_feed: bool, delay: float) -> dict | None:
        title = self._clean_html(post.get("title", {}).get("rendered", ""))
        content_html = post.get("content", {}).get("rendered", "")
        content_text = self._clean_html(content_html)
        tag_names = self._taxonomy_names("tags", post.get("tags", []), delay)
        category_names = self._taxonomy_names("categories", post.get("categories", []), delay)
        taxonomy_text = " ".join(tag_names + category_names)

        if not self._is_eligible(title, content_text, taxonomy_text):
            logger.info("Skipping non-job ApplyNow post: %s", title)
            return None

        fields = self._labelled_fields(content_text)
        remote = remote_from_feed or "remote" in f"{taxonomy_text} {content_text}".lower()
        location = fields.get("location") or ("Remote" if remote else None)
        description = self._description_with_links(content_html)
        return {
            "site": "applynow",
            "title": fields.get("title") or title or None,
            "company": self._company_from_title(title),
            "job_url": ((post.get("link") or "").rstrip("/") + "/") or None,
            "location": location,
            "description": description or content_text or None,
            "job_type": fields.get("contract") or fields.get("work format"),
            "compensation": fields.get("salary"),
            "date_posted": self._posted_date(post.get("date")),
            "expires": self._closing_date(fields.get("closing date")),
            "category": ", ".join(category_names + tag_names) or None,
            "remote": "Remote" if remote else None,
            "apply_instructions": self._application_links(content_html) or None,
        }

    def _is_eligible(self, title: str, content: str, taxonomy: str) -> bool:
        classification_signal = f"{title} {taxonomy} {content[:350]}".lower()
        if any(re.search(rf"\b{re.escape(term)}\w*\b", classification_signal) for term in self.excluded_terms):
            return False
        return any(re.search(rf"\b{re.escape(term)}\w*\b", classification_signal) for term in self.role_terms) or "job title:" in classification_signal

    @staticmethod
    def _clean_html(value: str) -> str:
        soup = BeautifulSoup(value or "", "html.parser")
        for node in soup(["script", "style", "noscript"]):
            node.decompose()
        return unescape(soup.get_text(" ", strip=True))

    @staticmethod
    def _description_with_links(value: str) -> str:
        soup = BeautifulSoup(value or "", "html.parser")
        for node in soup(["script", "style", "noscript"]):
            node.decompose()
        return render_links(soup)

    @staticmethod
    def _labelled_fields(text: str) -> dict[str, str]:
        labels = "Job Title|Job Location|Location|Closing Date|Work Format|Contract|Job Type|Salary"
        matches = list(re.finditer(rf"\b({labels})\s*:\s*", text, flags=re.IGNORECASE))
        fields: dict[str, str] = {}
        for index, match in enumerate(matches):
            end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            value = text[match.end():end].strip(" \t\r\n|-–")
            value = re.split(
                r"\s+(?=(?:About|Requirements|Key Responsibilities|How to Apply|Qualifications|Responsibilities)\b)",
                value,
                maxsplit=1,
                flags=re.IGNORECASE,
            )[0].strip()
            if value:
                key = match.group(1).lower()
                fields[{"job title": "title", "job location": "location", "job type": "contract"}.get(key, key)] = value
        return fields

    @staticmethod
    def _posted_date(value: str | None) -> str | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).date().isoformat()
        except ValueError:
            return None

    @staticmethod
    def _closing_date(value: str | None) -> str | None:
        if not value:
            return None
        value = value.strip()
        for pattern in ("%d %B %Y", "%d %b %Y", "%B %d, %Y", "%Y-%m-%d"):
            match = re.search(r"\d{1,2}\s+[A-Za-z]+\s+\d{4}|[A-Za-z]+\s+\d{1,2},\s*\d{4}|\d{4}-\d{2}-\d{2}", value)
            if match:
                try:
                    return datetime.strptime(match.group(0), pattern).date().isoformat()
                except ValueError:
                    continue
        return None

    @staticmethod
    def _company_from_title(title: str) -> str | None:
        patterns = (r"^(.+?)\s+(?:is\s+)?(?:hiring|seeks|recruiting)\b", r"\bJob at\s+(.+?)(?:\s*[|–-]|$)")
        for pattern in patterns:
            match = re.search(pattern, title, flags=re.IGNORECASE)
            if match:
                return match.group(1).strip(" -–|") or None
        return None

    @staticmethod
    def _application_links(value: str) -> str:
        soup = BeautifulSoup(value or "", "html.parser")
        links = []
        for anchor in soup.find_all("a", href=True):
            label = anchor.get_text(" ", strip=True)
            context = anchor.parent.get_text(" ", strip=True) if anchor.parent else label
            if "apply" in f"{label} {context}".lower() and "applynow.co.zw" not in anchor["href"]:
                links.append(f"{label or 'Apply'} ({anchor['href']})")
        return "\n".join(dict.fromkeys(links))


def scrape_applynow_jobs(**kwargs) -> list[dict]:
    """Convenience wrapper for ApplyNow ingestion."""
    return ApplyNowScraper().scrape_jobs(**kwargs)


if __name__ == "__main__":
    jobs = scrape_applynow_jobs(max_pages=1, max_jobs=5)
    print(f"Found {len(jobs)} eligible ApplyNow job(s).")
    for job in jobs:
        print(f"- {job['title']} ({job['remote'] or job['location'] or 'location not listed'})")
