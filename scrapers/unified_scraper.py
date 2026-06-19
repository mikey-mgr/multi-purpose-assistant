"""
Unified Job Scraper Interface
Manages all custom site scrapers with site-cycling and 403 retry logic.
"""

import os
import sys
import time
import random
import logging
from typing import List, Optional, Union

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from core.database import get_existing_job_urls
from scrapers.utils import SiteScrapeError
from scrapers.vacancymail_scraper import VacancyMailScraper
from scrapers.iharare_scraper import IHarareJobsScraper
from scrapers.vacancybox_scraper import VacancyBoxScraper

logger = logging.getLogger(__name__)


class UnifiedJobScraper:
    """
    Unified scraper that manages all custom site scrapers.
    Cycles through sites; on 403 / rate-limit errors it retries later
    with incremental wait times.
    """

    def __init__(self):
        self.scrapers = {
            'vacancymail': VacancyMailScraper(),
            'iharare': IHarareJobsScraper(),
            'vacancybox': VacancyBoxScraper(),
        }

    def scrape_jobs(self, site_name: Union[str, List[str]] = None, results_wanted: int = 50,
                   hours_old: int = 72, **kwargs) -> 'pd.DataFrame':
        """
        JobSpy-compatible interface for scraping jobs.
        On 403 errors, defers the site and retries after completing others.

        Parameters
        ----------
        site_name : list or str
            Sites to scrape from.
        results_wanted : int
            Maximum number of results.
        hours_old : int
            How old jobs can be (hours).
        max_pages : int | dict[str, int]
            Pages per site.  Accepts a single int (applied to all) or a
            dict mapping site name → pages (e.g. ``{"vacancybox": 1}``).
        """
        import pandas as pd

        if site_name is None:
            site_name = list(self.scrapers.keys())
        elif isinstance(site_name, str):
            site_name = [site_name]

        # Resolve per-site max_pages
        raw_pages = kwargs.pop("max_pages", 2)
        if isinstance(raw_pages, dict):
            per_site_pages = raw_pages
        else:
            per_site_pages = {s: int(raw_pages) for s in site_name}

        existing_urls = get_existing_job_urls()
        logger.info("Loaded %d existing job URLs to skip", len(existing_urls))

        all_jobs = []
        pending = list(site_name)
        retries = {s: 0 for s in site_name}
        max_retries = 2
        base_delay = 30

        while pending:
            site = pending.pop(0)
            if site not in self.scrapers:
                logger.warning("Site '%s' not supported.", site)
                continue

            try:
                logger.info("Scraping %s (attempt %d, max_pages=%s)...",
                            site, retries[site] + 1, per_site_pages.get(site, 2))
                scraper = self.scrapers[site]
                scrape_kwargs = {
                    "existing_urls": existing_urls,
                    "max_pages": per_site_pages.get(site, 2),
                }
                if "max_jobs" in kwargs:
                    scrape_kwargs["max_jobs"] = kwargs["max_jobs"]

                jobs_result = scraper.scrape_jobs(**scrape_kwargs)

                if isinstance(jobs_result, list):
                    jobs_df = pd.DataFrame(jobs_result) if jobs_result else pd.DataFrame()
                elif isinstance(jobs_result, pd.DataFrame):
                    jobs_df = jobs_result
                else:
                    jobs_df = pd.DataFrame()

                if not jobs_df.empty:
                    all_jobs.append(jobs_df)
                logger.info("%s returned %d jobs.", site, len(jobs_df))

            except SiteScrapeError as e:
                retries[site] += 1
                if retries[site] <= max_retries:
                    wait = base_delay * retries[site] + random.randint(10, 30)
                    logger.warning("%s failed (%s) — retry %d/%d in %ds.",
                                   site, e, retries[site], max_retries, wait)
                    time.sleep(wait)
                    pending.append(site)  # back of the queue
                else:
                    logger.error("%s failed after %d retries — skipping.", site, max_retries)
            except Exception as e:
                logger.error("%s failed with unexpected error: %s — skipping.", site, e)

        if all_jobs:
            combined_df = pd.concat(all_jobs, ignore_index=True)
            if len(combined_df) > results_wanted:
                combined_df = combined_df.head(results_wanted)
            logger.info("Total jobs scraped: %d from %d sites", len(combined_df), len(all_jobs))
            return combined_df
        else:
            logger.warning("No jobs scraped from any site")
            return pd.DataFrame()

    def get_supported_sites(self) -> List[str]:
        return list(self.scrapers.keys())


# ── Module-level convenience ────────────────────────────────────────────

def scrape_jobs(
    site_name: Union[str, List[str]] = None,
    results_wanted: int = 50,
    hours_old: int = 72,
    **kwargs,
) -> 'pd.DataFrame':
    """JobSpy-compatible function (see :class:`UnifiedJobScraper`)."""
    scraper = UnifiedJobScraper()
    return scraper.scrape_jobs(
        site_name=site_name,
        results_wanted=results_wanted,
        hours_old=hours_old,
        **kwargs,
    )


def test_unified_scraper():
    """Test the unified scraper with all three custom scrapers."""
    from core.database import init_db, insert_jobs

    scraper = UnifiedJobScraper()
    jobs_df = scraper.scrape_jobs(
        site_name=['iharare', 'vacancybox', 'vacancymail'],
    )
    print(f"Found {len(jobs_df)} jobs from all three sites")
    if not jobs_df.empty:
        print("Columns:", list(jobs_df.columns))
        print("Sites scraped:", jobs_df['site'].value_counts().to_dict())
        init_db()
        count = insert_jobs(jobs_df.to_dict('records'))
        print(f"Inserted {count} new job(s) into database.")
    return jobs_df


if __name__ == "__main__":
    test_unified_scraper()
