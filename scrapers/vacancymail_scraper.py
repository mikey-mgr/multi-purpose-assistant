"""
Custom VacancyMail.co.zw Scraper
Robust scraper for vacancymail.co.zw with proper field extraction
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import random
import re
from urllib.parse import urljoin, urlparse
from datetime import datetime, timedelta
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VacancyMailScraper:
    def __init__(self):
        self.base_url = "https://vacancymail.co.zw"
        self.jobs_url = "https://vacancymail.co.zw/jobs/"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
    def scrape_jobs(self, max_pages=2, delay=None, max_jobs=None):
        """
        Scrape jobs from vacancymail.co.zw
        
        Args:
            max_pages (int): Maximum number of pages to scrape
            delay (int): Delay between requests in seconds
            max_jobs (int): Maximum number of jobs to scrape. If None, all available jobs up to max_pages will be scraped.
            
        Returns:
            list: A list of dictionaries, each representing a job listing, standardized for the backend.
        """
        if delay is None:
            delay = random.randint(5, 15)

        all_jobs = []
        
        for page in range(1, max_pages + 1):
            # Stop if we've reached the maximum desired jobs
            if max_jobs is not None and len(all_jobs) >= max_jobs:
                logger.info(f"Reached maximum number of jobs ({max_jobs}). Stopping scraping.")
                break

            logger.info(f"Scraping VacancyMail page {page}...")
            
            # Get job listings page
            page_url = f"{self.jobs_url}?page={page}"
            try:
                response = self.session.get(page_url, timeout=10)
                response.raise_for_status()
            except requests.RequestException as e:
                logger.error(f"Error fetching page {page}: {e}")
                continue
                
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find job listings
            job_links = soup.find_all('a', class_='job-listing')
            
            if not job_links:
                logger.info(f"No job listings found on page {page}")
                break
                
            logger.info(f"Found {len(job_links)} job listings on page {page}")
            
            # Extract basic info from listing page
            for job_link in job_links:
                if max_jobs is not None and len(all_jobs) >= max_jobs:
                    logger.info(f"Reached maximum number of jobs ({max_jobs}). Stopping processing current page.")
                    break
                try:
                    job_data = self._extract_listing_data(job_link)
                    if job_data:
                        # Get detailed job information
                        job_url = urljoin(self.base_url, job_link.get('href'))
                        detailed_data = self._scrape_job_details(job_url)
                        
                        # Merge data
                        job_data.update(detailed_data)
                        
                        # Standardize and add to all_jobs
                        standardized_job = self._standardize_job_data(job_data)
                        all_jobs.append(standardized_job)
                        
                        # Respectful delay
                        time.sleep(delay)
                        
                except Exception as e:
                    logger.error(f"Error processing job listing: {e}")
                    continue
            
            # Delay between pages
            time.sleep(delay)
            
        logger.info(f"Total jobs scraped: {len(all_jobs)}")
        
        return all_jobs
    
    def _extract_listing_data(self, job_link):
        """Extract basic data from job listing on main page"""
        try:
            data = {}
            
            # Job title
            title_elem = job_link.find('h3', class_='job-listing-title')
            data['title'] = title_elem.get_text(strip=True) if title_elem else None
            
            # Company name
            company_elem = job_link.find('h4', class_='job-listing-company')
            data['company'] = company_elem.get_text(strip=True) if company_elem else None
            
            # Job description preview (will be overwritten by full description)
            desc_elem = job_link.find('p', class_='job-listing-text')
            data['description_preview'] = desc_elem.get_text(strip=True) if desc_elem else None
            
            # Footer information
            footer = job_link.find('div', class_='job-listing-footer')
            if footer:
                footer_items = footer.find_all('li')
                # Initialize these to None
                data['location'] = None
                data['job_type'] = None
                data['salary'] = None
                data['date_posted'] = None
                data['expires'] = None

                for item in footer_items:
                    text = item.get_text(strip=True)
                    
                    # Location
                    if 'icon-material-outline-location-on' in str(item):
                        data['location'] = text
                    
                    # Job type
                    elif 'icon-material-outline-business-center' in str(item):
                        data['job_type'] = text
                    
                    # Salary
                    elif 'icon-material-outline-account-balance-wallet' in str(item):
                        data['salary'] = text
                    
                    # Posted time
                    elif 'Posted' in text:
                        data['date_posted'] = self._parse_posted_time(text)
                    
                    # Expiry date
                    elif 'Expires' in text:
                        data['expires'] = self._parse_expiry_date(text)
            
            # Job URL
            data['job_url'] = urljoin(self.base_url, job_link.get('href'))
            
            return data
            
        except Exception as e:
            logger.error(f"Error extracting listing data: {e}")
            return None
    
    def _scrape_job_details(self, job_url):
        """Scrape detailed job information from individual job page"""
        try:
            response = self.session.get(job_url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            data = {}
            
            # Get job overview details (more reliable than header)
            overview = soup.find('div', class_='job-overview-inner')
            if overview:
                overview_items = overview.find_all('li')
                # Initialize these to None
                data['location_detailed'] = None
                data['job_type_detailed'] = None
                data['salary_detailed'] = None
                data['expiry_detailed'] = None
                data['date_posted_detailed'] = None

                for item in overview_items:
                    span = item.find('span')
                    h5 = item.find('h5')
                    
                    if span and h5:
                        field = span.get_text(strip=True).lower()
                        value = h5.get_text(strip=True)
                        
                        if 'location' in field:
                            data['location_detailed'] = value
                        elif 'job type' in field:
                            data['job_type_detailed'] = value
                        elif 'salary' in field:
                            data['salary_detailed'] = value
                        elif 'expiry' in field:
                            data['expiry_detailed'] = self._parse_expiry_date(value) # Parse here too
                        elif 'date posted' in field:
                            data['date_posted_detailed'] = self._parse_posted_time(value) # Parse here too
            
            # Get job description sections, filtering for relevant content
            relevant_description_parts = []
            
            # Keywords to identify sections relevant for resume matching
            relevant_keywords = [
                'job description', 'duties and responsibilities', 'qualifications and experience',
                'requirements', 'skills', 'key attributes', 'roles and responsibilities',
                'about the role', 'what you will do', 'what we are looking for', 'minimum requirements'
            ]

            sections = soup.find_all('div', class_='single-page-section')
            
            for section in sections:
                h3 = section.find('h3')
                section_title = h3.get_text(strip=True).lower() if h3 else ''

                # Check if the section title contains any relevant keywords
                if any(keyword in section_title for keyword in relevant_keywords):
                    section_content = []
                    # Get all paragraphs in this section
                    for p in section.find_all('p'):
                        content = p.get_text(strip=True)
                        if content and "how to apply" not in content.lower(): # Exclude "How to Apply" from paragraphs
                            section_content.append(content)
                    
                    # Also include list items (e.g., for bullet points of duties/requirements)
                    for ul in section.find_all('ul'):
                        for li in ul.find_all('li'):
                            content = li.get_text(strip=True)
                            if content and "how to apply" not in content.lower():
                                section_content.append(content)

                    if section_content:
                        # Append the section title and its content
                        relevant_description_parts.append(f"{h3.get_text(strip=True)}:\n" + "\n".join(section_content))
            
            data['description'] = "\n\n".join(relevant_description_parts) if relevant_description_parts else None
            
            # Get category from header
            header = soup.find('div', class_='header-details')
            if header:
                category_link = header.find('h5').find('a') if header.find('h5') else None
                if category_link:
                    data['category'] = category_link.get_text(strip=True)
            
            return data
            
        except Exception as e:
            logger.error(f"Error scraping job details from {job_url}: {e}")
            return {}
    
    def _parse_posted_time(self, text):
        """Parse 'Posted X minutes/hours/days ago' text, returning None if unparseable."""
        if not text:
            return None
        try:
            # Extract number and unit
            match = re.search(r'Posted (\d+)\s*(minute|hour|day)', text.lower())
            if match:
                number = int(match.group(1))
                unit = match.group(2)
                
                if 'minute' in unit:
                    delta = timedelta(minutes=number)
                elif 'hour' in unit:
                    delta = timedelta(hours=number)
                elif 'day' in unit:
                    delta = timedelta(days=number)
                else:
                    return None # Unrecognized unit
                
                posted_date = datetime.now() - delta
                return posted_date.strftime('%Y-%m-%d')
            
            return None # No match found
        except Exception as e:
            logger.warning(f"Could not parse posted time '{text}': {e}")
            return None
    
    def _parse_expiry_date(self, text):
        """Parse expiry date text to standard YYYY-MM-DD format, returning None if unparseable."""
        if not text:
            return None
        try:
            # Look for date pattern (DD MMM YYYY)
            date_match = re.search(r'(\d{1,2})\s+(\w+)\s+(\d{4})', text)
            if date_match:
                day, month, year = date_match.groups()
                # Convert month name to number
                months = {
                    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
                    'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
                }
                month_num = months.get(month.lower()[:3], None)
                if month_num is None: # If month name not found, return None
                    return None
                return f"{year}-{month_num:02d}-{int(day):02d}"
            
            return None # No match found
        except Exception as e:
            logger.warning(f"Could not parse expiry date '{text}': {e}")
            return None
    
    def _standardize_job_data(self, job_data):
        """Standardize a single job dictionary to match the universal schema."""
        standardized = {
            'site': 'vacancymail',
            'title': job_data.get('title') or None,
            'company': job_data.get('company') or None,
            'job_url': job_data.get('job_url') or None,
            'location': job_data.get('location_detailed') or job_data.get('location') or None,
            'description': job_data.get('description') or job_data.get('description_preview') or None,
            'job_type': job_data.get('job_type_detailed') or job_data.get('job_type') or None,
            'compensation': job_data.get('salary_detailed') or job_data.get('salary') or None,
            'date_posted': job_data.get('date_posted_detailed') or job_data.get('date_posted') or None,
            'expires': job_data.get('expiry_detailed') or job_data.get('expires') or None,
            'category': job_data.get('category') or None,
            'remote': None # Assuming no explicit remote status for now
        }
        return standardized


def scrape_vacancymail_jobs(**kwargs):
    """Scrape jobs from VacancyMail (returns a list of standardized dicts)"""
    scraper = VacancyMailScraper()
    return scraper.scrape_jobs(**kwargs)


if __name__ == "__main__":
    import json
    from core.database import init_db, insert_jobs

    print("Testing VacancyMail scraper (max_pages=2, random delay 5-15s):")
    jobs_data = scrape_vacancymail_jobs()

    print(f"\nFound {len(jobs_data)} jobs")
    if len(jobs_data) > 0:
        init_db()
        count = insert_jobs(jobs_data)
        print(f"\nInserted {count} new job(s) into database.")
