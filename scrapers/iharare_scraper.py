"""
Custom iHarare Jobs Scraper
Robust scraper for ihararejobs.com with proper field extraction
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import random
import re
from urllib.parse import urljoin
from datetime import datetime
import logging

from scrapers.utils import decode_cfemail, render_links

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class IHarareJobsScraper:
    def __init__(self):
        self.base_url = "https://ihararejobs.com"
        self.jobs_url = "https://ihararejobs.com/jobs/"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
    def scrape_jobs(self, max_pages=2, delay=None, max_jobs=None, existing_urls: set | None = None):
        """
        Scrape jobs from ihararejobs.com
        
        Args:
            max_pages (int): Maximum number of pages to scrape
            delay (int): Delay between requests in seconds
            max_jobs (int): Maximum number of jobs to scrape. If None, all available jobs up to max_pages will be scraped.
            existing_urls (set): Set of job URLs already in the DB – detail pages for these will be skipped.
            
        Returns:
            list: A list of dictionaries, each representing a job listing, standardized for the backend.
        """
        if delay is None:
            delay = random.randint(5, 15)
        existing_urls = existing_urls or set()

        all_jobs = []
        skipped = 0
        
        for page in range(1, max_pages + 1):
            # Stop if we've reached the maximum desired jobs
            if max_jobs is not None and len(all_jobs) >= max_jobs:
                logger.info(f"Reached maximum number of jobs ({max_jobs}). Stopping scraping.")
                break

            logger.info(f"Scraping iHarare page {page}...")
            
            # Get job listings page
            page_url = f"{self.jobs_url}?page={page}" if page > 1 else self.jobs_url
            try:
                response = self.session.get(page_url, timeout=10)
                response.raise_for_status()
            except requests.RequestException as e:
                logger.error(f"Error fetching page {page}: {e}")
                continue
                
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find job listings
            job_cards = soup.find_all('div', class_='sidebar-list-single')
            
            if not job_cards:
                logger.info(f"No job listings found on page {page}")
                break
                
            logger.info(f"Found {len(job_cards)} job listings on page {page}")
            
            # Extract basic info from listing page
            for job_card in job_cards:
                # Check max_jobs limit before processing each job card
                if max_jobs is not None and len(all_jobs) >= max_jobs:
                    logger.info(f"Reached maximum number of jobs ({max_jobs}). Stopping processing current page.")
                    break
                try:
                    job_data = self._extract_listing_data(job_card)
                    if job_data:
                        job_url = job_data.get('job_url')
                        if job_url:
                            if job_url in existing_urls:
                                skipped += 1
                            else:
                                detailed_data = self._scrape_job_details(job_url)
                                job_data.update(detailed_data)
                                standardized_job = self._standardize_job_data(job_data)
                                all_jobs.append(standardized_job)
                                time.sleep(delay)
                            
                except Exception as e:
                    logger.error(f"Error processing job listing: {e}")
                    continue
            
            # Delay between pages
            time.sleep(delay)
                
            # Continue to next page (we'll rely on max_pages limit)
            # Skip pagination check since we know the URL pattern works
        
        logger.info(f"Total jobs scraped: {len(all_jobs)} (skipped %d existing)", skipped)
        
        return all_jobs

    def _extract_listing_data(self, job_card):
        """Extract basic data from job card on main page"""
        try:
            data = {}
            
            # Find the job link
            job_link = job_card.find('a', href=True)
            if not job_link:
                return None
                
            data['job_url'] = urljoin(self.base_url, job_link.get('href'))
            
            # Job title (from the link text or h3)
            title_elem = job_card.find('h3')
            if title_elem:
                title_link = title_elem.find('a')
                data['title'] = title_link.get_text(strip=True) if title_link else title_elem.get_text(strip=True)
            else:
                data['title'] = None # Use None for missing data
            
            # Company name (from building icon)
            company_elem = job_card.find('p', class_='company-state')
            if company_elem and 'fa-building' in str(company_elem):
                data['company'] = company_elem.get_text(strip=True)
            else:
                # Fallback: look for company name in other places
                company_alt = job_card.find('div', class_='company-list-logo')
                if company_alt:
                    img = company_alt.find('img')
                    if img and img.get('alt'):
                        data['company'] = img.get('alt')
                    else:
                        data['company'] = None
                else:
                    data['company'] = None
            
            # Location (from map-marker icon)
            location_elem = job_card.find('p', class_='company-state')
            if location_elem and 'fa-map-marker' in str(location_elem):
                data['location'] = location_elem.get_text(strip=True)
            else:
                data['location'] = None
            
            # Initialize job_type, date_posted, expires to None
            data['job_type'] = None
            data['date_posted'] = None
            data['expires'] = None

            # Job type and other details from open-icon paragraphs
            open_icons = job_card.find_all('p', class_='open-icon')
            for icon_p in open_icons:
                text = icon_p.get_text(strip=True)
                
                # Expiry date
                if 'Expires' in text:
                    data['expires'] = self._parse_date(text.replace('Expires', '').strip())
                
                # Date posted
                elif 'Created' in text:
                    data['date_posted'] = self._parse_date(text.replace('Created', '').strip())
                
                # Job type (Full Time, Part Time, etc.)
                elif any(job_type in text for job_type in ['Full Time', 'Part Time', 'Contract', 'Temporary']):
                    data['job_type'] = text
            
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
            job_overview = soup.find('ul', class_='job-overview')
            if job_overview:
                overview_items = job_overview.find_all('li')
                for item in overview_items:
                    h4 = item.find('h4')
                    p = item.find('p')
                    
                    if h4 and p:
                        field = h4.get_text(strip=True).lower()
                        value = p.get_text(strip=True)
                        
                        if 'location' in field:
                            data['location_detailed'] = value
                        elif 'job type' in field:
                            data['job_type_detailed'] = value
                        elif 'expiry' in field:
                            data['expiry_detailed'] = self._parse_date(value)
                        elif 'date posted' in field:
                            data['date_posted_detailed'] = self._parse_date(value)
            
            # Get job description sections, filtering for relevant content
            relevant_description_parts = []
            
            # Keywords to identify sections relevant for resume matching
            relevant_keywords = [
                'job summary', 'job description', 'duties and responsibilities',
                'qualifications and experience', 'requirements', 'skills',
                'key attributes', 'roles and responsibilities', 'education', 'experience', 'certification'
            ]

            # Find all potential sections that might contain relevant info
            # iHarare often uses 'single-candidate-widget' for content blocks
            content_widgets = soup.find_all('div', class_='single-candidate-widget')

            for widget in content_widgets:
                h3 = widget.find('h3')
                section_title = h3.get_text(strip=True).lower() if h3 else ''

                # Check if the section title or its content is relevant
                if any(keyword in section_title for keyword in relevant_keywords):
                    section_content_parts = []
                    
                    # Get paragraphs
                    for p in widget.find_all('p'):
                        content = p.get_text(strip=True)
                        if content and "how to apply" not in content.lower(): # Exclude "How to Apply" from paragraphs
                            section_content_parts.append(content)
                    
                    # Get list items (e.g., for bullet points of duties/requirements)
                    for ul in widget.find_all('ul'):
                        for li in ul.find_all('li'):
                            content = li.get_text(strip=True)
                            if content and "how to apply" not in content.lower():
                                section_content_parts.append(content)

                    # Only add if there's actual content and it's not an "How to Apply" section header
                    if section_content_parts and "how to apply" not in section_title:
                        # Re-add the original title if it exists, otherwise just the content
                        if h3:
                            relevant_description_parts.append(f"{h3.get_text(strip=True)}:\n" + "\n".join(section_content_parts))
                        else:
                            relevant_description_parts.append("\n".join(section_content_parts))
            
            data['description'] = "\n\n".join(relevant_description_parts) if relevant_description_parts else None

            # ── Extract "How to Apply" section ───────────────────────
            for widget in content_widgets:
                h3 = widget.find('h3')
                if h3 and "how to apply" in h3.get_text(strip=True).lower():
                    apply_parts = []
                    for child in widget.children:
                        cname = getattr(child, 'name', None)
                        if cname == 'p':
                            # Decode Cloudflare emails before link rendering
                            for el in child.find_all(lambda tag: tag.get('data-cfemail')):
                                real = decode_cfemail(el.get('data-cfemail', ''))
                                if real:
                                    el.replace_with(f' {real} ')
                            # Render <a> tags as "text (url)" before text extraction
                            txt = render_links(child)
                            if txt:
                                apply_parts.append(txt)
                        elif cname in ('ul', 'ol'):
                            for li in child.find_all('li'):
                                t = li.get_text(strip=True)
                                if t:
                                    apply_parts.append(t)
                    if apply_parts:
                        data['apply_instructions'] = '\n'.join(filter(None, apply_parts))
                    break
            
            # Get category from header
            header = soup.find('section', class_='single-candidate-page')
            if header:
                category_link = header.find('h4')
                if category_link:
                    category_a = category_link.find('a')
                    if category_a:
                        data['category'] = category_a.get_text(strip=True)
            
            # Get company name from header if not found earlier
            if not data.get('company') or data.get('company') == 'N/A':
                company_header = soup.find('h4')
                if company_header:
                    company_link = company_header.find('a')
                    if company_link and 'employers' in company_link.get('href', ''):
                        data['company_detailed'] = company_link.get_text(strip=True)
            
            return data
            
        except Exception as e:
            logger.error(f"Error scraping job details from {job_url}: {e}")
            return {}
    
    def _parse_date(self, date_text):
        """Parse date text to standard YYYY-MM-DD format, returning None if unparseable."""
        if not date_text:
            return None
        try:
            # Remove common prefixes/suffixes
            date_text = date_text.replace('Expires:', '').replace('Created:', '').strip()
            
            # Look for date pattern (DD MMM YYYY)
            date_match = re.search(r'(\d{1,2})\s+(\w+)\s+(\d{4})', date_text)
            if date_match:
                day, month, year = date_match.groups()
                # Convert month name to number
                months = {
                    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
                    'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
                    'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6,
                    'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12
                }
                month_num = months.get(month.lower()[:3], None)
                if month_num is None: # If month name not found, return None
                    return None
                return f"{year}-{month_num:02d}-{int(day):02d}"
            
            return None # Return None if no match
        except Exception as e:
            logger.warning(f"Could not parse date '{date_text}': {e}")
            return None
    
    def _standardize_job_data(self, job_data):
        """Standardize a single job dictionary to match the universal schema."""
        standardized = {
            'site': 'iharare',
            'title': job_data.get('title') or None,
            'company': job_data.get('company_detailed') or job_data.get('company') or None,
            'job_url': job_data.get('job_url') or None,
            'location': job_data.get('location_detailed') or job_data.get('location') or None,
            'description': job_data.get('description') or None,
            'job_type': job_data.get('job_type_detailed') or job_data.get('job_type') or None,
            'compensation': None, # iHarare doesn't show salary info, explicitly set to None
            'date_posted': job_data.get('date_posted_detailed') or job_data.get('date_posted') or None,
            'expires': job_data.get('expiry_detailed') or job_data.get('expires') or None,
            'category': job_data.get('category') or None,
            'remote': None, # Assuming no explicit remote status for now
            'apply_instructions': job_data.get('apply_instructions') or None
        }
        return standardized

    def _has_next_page(self, soup):
        """Check if there's a next page"""
        # Look for pagination elements
        pagination = soup.find('div', class_='pagination') or soup.find('nav', class_='pagination')
        if pagination:
            # Look for next link or page numbers higher than current
            next_links = pagination.find_all('a', href=True)
            for link in next_links:
                href = link.get('href', '')
                if 'page=' in href:
                    return True
        
        # Also check for any links with page parameters
        page_links = soup.find_all('a', href=lambda x: x and 'page=' in x)
        return len(page_links) > 0


def scrape_iharare_jobs(**kwargs):
    """Scrape jobs from iHarare (returns a list of standardized dicts)"""
    scraper = IHarareJobsScraper()
    return scraper.scrape_jobs(**kwargs)


if __name__ == "__main__":
    import json
    from core.database import init_db, insert_jobs

    print("Testing iHarare scraper (max_pages=2, random delay 5-15s):")
    jobs_data = scrape_iharare_jobs()

    print(f"\nFound {len(jobs_data)} jobs")
    if len(jobs_data) > 0:
        init_db()
        count = insert_jobs(jobs_data)
        print(f"\nInserted {count} new job(s) into database.")
