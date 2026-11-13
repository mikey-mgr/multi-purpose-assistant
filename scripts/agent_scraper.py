"""Poll the Mukana server for scrape tasks, run local scrapers, and submit jobs."""

import argparse
import logging
import os

os.environ.setdefault("SKIP_PREFECT_BLOCKS", "1")

import pandas as pd

from scripts.agent_common import run_agent
from scrapers.unified_scraper import UnifiedJobScraper

logger = logging.getLogger("mukana.agent.scraper")


def _clean(value):
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


MAX_JOBS_PER_SITE = int(os.getenv("MUKANA_SCRAPE_MAX_JOBS", "40"))


def handle_scrape(payload: dict) -> dict:
    site_names = payload.get("site_names") or None
    max_pages = payload.get("max_pages") or 1
    max_jobs = int(payload.get("max_jobs") or MAX_JOBS_PER_SITE)
    scraper = UnifiedJobScraper()

    logger.info(
        "Scraping sites=%s max_pages=%s max_jobs=%s",
        site_names or "all",
        max_pages,
        max_jobs,
    )
    frame = scraper.scrape_jobs(
        site_name=site_names,
        max_pages=max_pages,
        results_wanted=1000,
        existing_urls=set(),
        max_jobs=max_jobs,
    )

    jobs = []
    if isinstance(frame, pd.DataFrame) and not frame.empty:
        for record in frame.to_dict("records"):
            source_url = record.get("source_url") or record.get("job_url")
            if not source_url:
                continue
            jobs.append(
                {
                    "source": record.get("source") or record.get("site"),
                    "source_url": source_url,
                    "title": _clean(record.get("title")),
                    "company": _clean(record.get("company")),
                    "location": _clean(record.get("location")),
                    "description": _clean(record.get("description")),
                    "job_type": _clean(record.get("job_type")),
                    "compensation": _clean(record.get("compensation")),
                    "date_posted": _clean(record.get("date_posted")),
                    "expires": _clean(record.get("expires")),
                    "category": _clean(record.get("category")),
                    "remote": _clean(record.get("remote")),
                    "apply_instructions": _clean(record.get("apply_instructions")),
                }
            )

    logger.info("Submitting %d jobs", len(jobs))
    return {"jobs": jobs, "count": len(jobs), "sites": site_names or "all"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Mukana local scraper agent")
    parser.add_argument("--once", action="store_true", help="Process one task and exit")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    run_agent("scrape", handle_scrape, once=args.once)


if __name__ == "__main__":
    main()
