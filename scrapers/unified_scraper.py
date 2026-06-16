"""
Unified Job Scraper Interface
Manages all custom site scrapers with JobSpy-compatible API
"""

import os
import sys
import pandas as pd
import logging
from typing import List, Optional, Union

# Ensure project root is on sys.path for absolute imports
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from scrapers.vacancymail_scraper import VacancyMailScraper
from scrapers.iharare_scraper import IHarareJobsScraper
from scrapers.vacancybox_scraper import VacancyBoxScraper

logger = logging.getLogger(__name__)

class UnifiedJobScraper:
    """
    Unified scraper that manages all custom site scrapers
    Provides JobSpy-compatible interface for easy integration
    """
    
    def __init__(self):
        self.scrapers = {
            'vacancymail': VacancyMailScraper(),
            'iharare': IHarareJobsScraper(),
            'vacancybox': VacancyBoxScraper(),
        }
    
    def scrape_jobs(self, site_name: Union[str, List[str]] = None, results_wanted: int = 50, 
                   hours_old: int = 72, **kwargs) -> pd.DataFrame:
        """
        JobSpy-compatible interface for scraping jobs
        
        Args:
            site_name (list or str): Sites to scrape from
            results_wanted (int): Maximum number of results
            hours_old (int): How old jobs can be (hours)
            **kwargs: Additional parameters
            
        Returns:
            pandas.DataFrame: Combined job listings from all requested sites
        """
        if site_name is None:
            site_name = list(self.scrapers.keys())
        elif isinstance(site_name, str):
            site_name = [site_name]
        
        all_jobs = []
        # Give each site the full results_wanted to maximize job collection
        results_per_site = results_wanted  # Let each site try to get the full amount
        
        for site in site_name:
            if site not in self.scrapers:
                logger.warning(f"Site '{site}' not supported. Available sites: {list(self.scrapers.keys())}")
                continue
                
            try:
                logger.info(f"Scraping {site}...")
                scraper = self.scrapers[site]
                
                # Let each site use its own defaults (max_pages, random delay 5-15s, all jobs)
                jobs_result = scraper.scrape_jobs()
                
                # Convert to DataFrame if it's a list
                if isinstance(jobs_result, list):
                    if jobs_result:  # Non-empty list
                        jobs_df = pd.DataFrame(jobs_result)
                    else:  # Empty list
                        jobs_df = pd.DataFrame()
                elif isinstance(jobs_result, pd.DataFrame):
                    jobs_df = jobs_result
                else:
                    logger.warning(f"Unexpected return type from {site}: {type(jobs_result)}")
                    jobs_df = pd.DataFrame()
                
                if not jobs_df.empty:
                    all_jobs.append(jobs_df)
                    logger.info(f"Successfully processed {len(jobs_df)} new jobs from {site}")
                else:
                    logger.warning(f"No jobs found from {site}")
                    
            except Exception as e:
                logger.error(f"Error scraping {site}: {e}")
                continue
        
        if all_jobs:
            # Combine all DataFrames
            combined_df = pd.concat(all_jobs, ignore_index=True)
            
            # Apply final limit to respect results_wanted
            if len(combined_df) > results_wanted:
                combined_df = combined_df.head(results_wanted)
            
            logger.info(f"Total jobs scraped: {len(combined_df)} from {len(all_jobs)} sites")
            return combined_df
        else:
            logger.warning("No jobs scraped from any site")
            return pd.DataFrame()
    
    def get_supported_sites(self) -> List[str]:
        """Get list of supported job sites"""
        return list(self.scrapers.keys())


def scrape_jobs(site_name: Union[str, List[str]] = None, results_wanted: int = 50, 
               hours_old: int = 72, **kwargs) -> pd.DataFrame:
    """
    JobSpy-compatible function for scraping jobs
    
    Args:
        site_name (list or str): Sites to scrape from
        results_wanted (int): Maximum number of results
        hours_old (int): How old jobs can be (hours)
        **kwargs: Additional parameters
        
    Returns:
        pandas.DataFrame: Combined job listings
    """
    scraper = UnifiedJobScraper()
    return scraper.scrape_jobs(site_name=site_name, results_wanted=results_wanted, 
                              hours_old=hours_old, **kwargs)


def test_unified_scraper():
    """Test the unified scraper with all three custom scrapers"""
    from core.database import init_db, insert_jobs

    scraper = UnifiedJobScraper()

    jobs_df = scraper.scrape_jobs(site_name=['iharare', 'vacancybox', 'vacancymail'])

    print(f"Found {len(jobs_df)} jobs from all three sites")
    if len(jobs_df) > 0:
        print("\nColumns:", list(jobs_df.columns))
        print("\nSites scraped:", jobs_df['site'].value_counts().to_dict())

        init_db()
        count = insert_jobs(jobs_df.to_dict('records'))
        print(f"\nInserted {count} new job(s) into database.")

    return jobs_df


if __name__ == "__main__":
    test_unified_scraper()
