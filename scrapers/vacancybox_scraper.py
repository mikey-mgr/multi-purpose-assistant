"""
Custom VacancyBox Scraper
Robust scraper for vacancybox.co.zw with proper field extraction
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

from scrapers.utils import decode_cfemail, SiteScrapeError

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class VacancyBoxScraper:
    def __init__(self):
        self.base_url = "https://vacancybox.co.zw"
        self.jobs_url = "https://vacancybox.co.zw/" # Base URL for job listings
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
    def scrape_jobs(self, max_pages=1, delay=None, max_jobs=None, existing_urls: set | None = None):
        """
        Scrape jobs from vacancybox.co.zw using AJAX pagination
        
        Args:
            max_pages (int): Maximum number of pages to scrape
            delay (int): Delay between requests in seconds
            max_jobs (int, optional): The total number of jobs to scrape. 
                                            If None, scrapes up to max_pages.
                                            If specified, scraping stops when this number is reached.
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
            if max_jobs is not None and len(all_jobs) >= max_jobs:
                logger.info(f"Reached desired number of results ({max_jobs}). Stopping scraping.")
                break

            logger.info(f"Scraping VacancyBox page {page}...")
            
            # Use AJAX endpoint for all pages
            ajax_url = "https://vacancybox.co.zw/wp-admin/admin-ajax.php"
            ajax_data = {
                'action': 'job_manager_get_listings',
                'page': page,
                'per_page': 25,
                'orderby': 'date',
                'order': 'DESC'
            }
            
            try:
                response = self.session.post(ajax_url, data=ajax_data, timeout=15)
                response.raise_for_status()
                
                if response.headers.get('content-type', '').startswith('application/json'):
                    json_data = response.json()
                    if 'html' in json_data and json_data['html'].strip():
                        soup = BeautifulSoup(json_data['html'], 'html.parser')
                        job_cards = soup.select('li.job_listing')
                        logger.info(f"Page {page}: Found {len(job_cards)} jobs via AJAX")
                    else:
                        logger.info(f"No jobs found on page {page} - end of results")
                        break
                else:
                    logger.warning(f"Non-JSON response for page {page}")
                    break
                    
            except Exception as e:
                logger.error(f"Error fetching page {page}: {e}")
                break
            
            if not job_cards:
                logger.info(f"No job listings found on page {page}")
                break
                
            logger.info(f"Processing {len(job_cards)} job listings on page {page}")
            
            for job_card in job_cards:
                if max_jobs is not None and len(all_jobs) >= max_jobs:
                    logger.info(f"Reached desired number of results ({max_jobs}). Stopping processing current page.")
                    break
                try:
                    job_data = self._extract_listing_data(job_card)
                    if job_data:
                        job_url = job_data.get('job_url')
                        if job_url:
                            if job_url in existing_urls:
                                skipped += 1
                            else:
                                try:
                                    detailed_data = self._scrape_job_details(job_url)
                                except requests.HTTPError as e:
                                    if e.response and e.response.status_code == 403:
                                        logger.warning("VacancyBox returned 403 — site may be blocking. Skipping remaining jobs.")
                                        # Break both inner loop and outer processing
                                        raise
                                    raise
                                job_data.update(detailed_data)
                                standardized_job = self._standardize_job_data(job_data)
                                all_jobs.append(standardized_job)
                                time.sleep(delay)
                        else:
                            logger.warning(f"No job_url found for job: {job_data.get('title', 'Unknown')}")
                    else:
                        logger.warning(f"Failed to extract data from job card")
                        
                except requests.HTTPError as e:
                    if e.response and e.response.status_code == 403:
                        raise SiteScrapeError(site="vacancybox", message=f"403 on {job_url}")
                    logger.error(f"HTTP error for job listing: {e}")
                    continue
                except SiteScrapeError:
                    raise
                except Exception as e:
                    logger.error(f"Error processing job listing: {e}")
                    continue
            
            time.sleep(delay)
            
        logger.info(f"Total jobs scraped: {len(all_jobs)} (skipped %d existing)", skipped)
        
        if max_jobs is not None and len(all_jobs) > max_jobs:
            all_jobs = all_jobs[:max_jobs]

        return all_jobs
    
    def _extract_listing_data(self, job_card):
        try:
            data = {}
            
            job_link = job_card.find('a', href=True)
            if not job_link:
                return None
                
            data['job_url'] = job_link.get('href')
            
            position_div = job_card.find('div', class_='position')
            if position_div:
                title_elem = position_div.find('h3')
                data['title'] = title_elem.get_text(strip=True) if title_elem else 'N/A'
                
                company_div = position_div.find('div', class_='company')
                if company_div:
                    company_strong = company_div.find('strong')
                    data['company'] = company_strong.get_text(strip=True) if company_strong else 'N/A'
                else:
                    data['company'] = 'N/A'
            else:
                data['title'] = 'N/A'
                data['company'] = 'N/A'
            
            location_div = job_card.find('div', class_='location')
            data['location'] = location_div.get_text(strip=True) if location_div else 'N/A'
            
            meta_ul = job_card.find('ul', class_='meta')
            if meta_ul:
                date_li = meta_ul.find('li', class_='date')
                if date_li:
                    time_elem = date_li.find('time')
                    if time_elem:
                        data['date_posted'] = self._parse_date(time_elem.get('datetime', ''))
                        if not data['date_posted']:
                            data['date_posted'] = self._parse_date(time_elem.get_text(strip=True))
            
            logo_img = job_card.find('img', class_='company_logo')
            if logo_img and logo_img.get('alt'):
                if data.get('company') == 'N/A':
                    data['company'] = logo_img.get('alt')
            
            return data
            
        except Exception as e:
            logger.error(f"Error extracting listing data: {e}")
            return None
    
    def _scrape_job_details(self, job_url):
        """Scrape detailed job information from individual job page"""
        if not job_url:
            return {}
            
        try:
            response = self.session.get(job_url, timeout=10)
            if response.status_code == 403:
                raise requests.HTTPError(f"403 Client Error: Forbidden for url: {job_url}", response=response)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            details = {}
            
            # Find the main content area (using a more generic selector for robustness)
            # Try multiple common content selectors
            main_content = soup.find('div', class_='single_job_listing') or \
                           soup.find('div', class_='entry-content') or \
                           soup.find('article', class_='post')

            if not main_content:
                logger.warning(f"Main content area not found for {job_url}")
                return details
            
            # Get job title from header (more reliable than listing page)
            title_elem_detailed = main_content.find('h1', class_='entry-title') or \
                                  main_content.find('h1', class_='job-title')
            if title_elem_detailed:
                details['title_detailed'] = title_elem_detailed.get_text(strip=True)
            
            # Get company information (if not found in listing or more detailed here)
            company_div_detailed = main_content.find('div', class_='company')
            if company_div_detailed:
                company_name_elem = company_div_detailed.find('p', class_='name')
                if company_name_elem:
                    company_strong = company_name_elem.find('strong')
                    details['company_detailed'] = company_strong.get_text(strip=True) if company_strong else company_name_elem.get_text(strip=True)
            
            # Get job description
            job_desc_div = main_content.find('div', class_='job_description') or \
                           main_content.find('div', class_='entry-content')

            if job_desc_div:
                # --- Step 1: Extract Expiry Date FIRST (before content modification) ---
                # Look for 'DUE:' pattern
                expires_strong = job_desc_div.find('strong', string=re.compile(r'\s*DUE:\s*\d{1,2}\s*[A-Za-z]{3,}\s*\d{4}\s*', re.IGNORECASE))
                if expires_strong:
                    date_text = expires_strong.get_text(strip=True)
                    match = re.search(r'DUE:\s*(\d{1,2}\s*([A-Za-z]+)\s*\d{4})', date_text, re.IGNORECASE)
                    if match:
                        raw_date = match.group(1).strip()
                        month_abbr = match.group(2)
                        month_mapping = {
                            'jan': 'January', 'feb': 'February', 'mar': 'March', 'apr': 'April', 'may': 'May', 'jun': 'June',
                            'jul': 'July', 'aug': 'August', 'sep': 'September', 'oct': 'October', 'nov': 'November', 'dec': 'December'
                        }
                        for abbr, full_name in month_mapping.items():
                            if month_abbr.lower() == abbr.lower():
                                raw_date = raw_date.replace(month_abbr, full_name, 1)
                                break
                        try:
                            parsed_date = datetime.strptime(raw_date, '%d %B %Y')
                            details['expires'] = parsed_date.strftime('%Y-%m-%d')
                        except ValueError as ve:
                            logger.warning(f"Could not parse expiry date '{raw_date}' from '{date_text}': {ve}")
                            details['expires'] = None
                    else:
                        details['expires'] = None
                else:
                    details['expires'] = None
                # --- End of Expiry Date Extraction ---

                # --- Step 2: Prepare the HTML for cleaner text extraction ---

                # Remove specific ad/unwanted divs (existing rule)
                for ad_div in job_desc_div.find_all('div', class_=re.compile(r'vacan-.*')):
                    ad_div.decompose()

                # Remove the expiry date strong tag after extraction
                if expires_strong:
                    expires_strong.decompose()

                # Helper: replace Cloudflare placeholders with decoded emails
                def _resolve_cfemail(text: str, container) -> str:
                    text = text.replace('\xa0', ' ')
                    for el in container.find_all(lambda tag: tag.get('data-cfemail')):
                        real = decode_cfemail(el.get('data-cfemail', ''))
                        if real:
                            placeholder = el.get_text(strip=True).replace('\xa0', ' ')
                            text = text.replace(placeholder, f' {real} ')
                    return text

                # Find and remove elements that clearly signal the end of relevant job description,
                # such as "TO APPLY" sections or contact info, and capture them as apply_instructions.
                end_section_markers = [
                    re.compile(r'TO APPLY', re.IGNORECASE),
                    re.compile(r'Application Instructions', re.IGNORECASE),
                    re.compile(r'How to Apply', re.IGNORECASE),
                    re.compile(r'Interested candidates must submit', re.IGNORECASE),
                    re.compile(r'All applications should be emailed to', re.IGNORECASE),
                    re.compile(r'The deadline for submission of applications', re.IGNORECASE),
                    re.compile(r'Please note that only shortlisted applicants will be responded to', re.IGNORECASE),
                    re.compile(r'AFC Holdings is an equal opportunity employer', re.IGNORECASE),
                    re.compile(r'NB: Only shortlisted candidates will be contacted', re.IGNORECASE),
                    re.compile(r'Interested candidates should submit', re.IGNORECASE),
                    re.compile(r'Send your (CV|application)', re.IGNORECASE),
                ]

                # Iterate through all direct children of job_desc_div to find the cutoff point
                elements_to_keep = []
                apply_elements = []  # store element refs so we can render links too
                found_end_marker = False
                for child in job_desc_div.children:
                    if isinstance(child, str):
                        text_content = child.strip()
                        if any(marker.search(text_content) for marker in end_section_markers):
                            found_end_marker = True
                            apply_elements.append(text_content)
                        elif found_end_marker:
                            apply_elements.append(text_content)
                        else:
                            elements_to_keep.append(child)
                    elif child.name:
                        text_content = child.get_text(strip=True)
                        if any(marker.search(text_content) for marker in end_section_markers):
                            found_end_marker = True
                            apply_elements.append(child)
                        elif found_end_marker:
                            apply_elements.append(child)
                        else:
                            elements_to_keep.append(child)

                if apply_elements:
                    # Render each element preserving link text + URL,
                    # but decode Cloudflare email links to the real email
                    def _render_links(elem) -> str:
                        if isinstance(elem, str):
                            return elem
                        for a in elem.find_all('a', href=True):
                            # Cloudflare email: class on <a> itself OR nested <span>
                            cf = a.find('span', class_='__cf_email__')
                            cf_data = a.get('data-cfemail') or (cf and cf.get('data-cfemail'))
                            if cf_data:
                                real = decode_cfemail(cf_data)
                                if real:
                                    a.replace_with(f' {real} ')
                                    continue
                            # Regular link — render as "text (url)"
                            href = a['href']
                            txt = a.get_text(strip=True) or href
                            a.replace_with(f'{txt} ({href})')
                        return elem.get_text(separator='\n', strip=True)

                    parts = []
                    for e in apply_elements:
                        if isinstance(e, str):
                            if e.strip():
                                parts.append(e)
                        elif e.get_text(strip=True):
                            parts.append(_render_links(e))
                    raw = '\n'.join(filter(None, parts))
                    # Decode any remaining Cloudflare emails in bare text nodes
                    raw = _resolve_cfemail(raw, job_desc_div)
                    details['apply_instructions'] = raw
                else:
                    # ── Fallback: no marker found → look for Cloudflare emails + links ──
                    cf_parts = []
                    for span in job_desc_div.find_all('span', class_='__cf_email__'):
                        real = decode_cfemail(span.get('data-cfemail', ''))
                        if not real:
                            continue
                        parent = span.find_parent(['p', 'div', 'li'])
                        if parent:
                            txt = parent.get_text(separator='\n', strip=True)
                            txt = _resolve_cfemail(txt, parent)
                            cf_parts.append(txt)
                            nxt = parent.find_next_sibling(['p', 'div'])
                            if nxt:
                                txt2 = nxt.get_text(separator='\n', strip=True)
                                txt2 = _resolve_cfemail(txt2, nxt)
                                cf_parts.append(txt2)
                    # Collect all mailto: and external links in the description
                    for a in job_desc_div.find_all('a', href=True):
                        href = a['href']
                        if href.startswith('mailto:'):
                            cf_parts.append(href.replace('mailto:', ''))
                        elif href.startswith('http') and 'vacancybox' not in href and 'google' not in href:
                            cf_parts.append(a.get_text(strip=True) or href)
                    if cf_parts:
                        details['apply_instructions'] = '\n'.join(filter(None, cf_parts))
                    else:
                        # ── Last resort: grab the last 2 <p> from the description ──
                        all_ps = [p for p in job_desc_div.find_all('p') if p.get_text(strip=True)]
                        if len(all_ps) >= 2:
                            details['apply_instructions'] = '\n'.join(
                                p.get_text(separator='\n', strip=True) for p in all_ps[-2:]
                            )
                        elif all_ps:
                            details['apply_instructions'] = all_ps[-1].get_text(separator='\n', strip=True)
                
                # Create a new, clean soup from the elements we want to keep
                cleaned_soup = BeautifulSoup('', 'html.parser')
                for elem in elements_to_keep:
                    if isinstance(elem, str):
                        cleaned_soup.append(elem)
                    else:
                        cleaned_soup.append(elem.extract()) # Extract moves the element

                # --- Step 3: Extract cleaned text content from the prepared soup ---
                description_parts = []
                
                # Process common block elements and ensure proper spacing/newlines
                for element in cleaned_soup.find_all(['p', 'ul', 'ol', 'li', 'strong', 'span', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
                    # Check if the element has already been processed or is just whitespace
                    if not element.get_text(strip=True):
                        continue
                    
                    text_content = element.get_text(separator=' ', strip=True) # Use space separator for list items
                    
                    # Add specific handling for headings to avoid duplication with parent text
                    if element.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'strong']:
                        if len(text_content.split()) > 1: # Avoid single-word headings that might be noise
                            description_parts.append(f"\n**{text_content}**\n") # Bold headings for clarity
                    elif element.name in ['ul', 'ol']:
                        list_items = [li.get_text(strip=True) for li in element.find_all('li') if li.get_text(strip=True)]
                        description_parts.extend([f"• {item}" for item in list_items])
                    elif element.name == 'li':
                        description_parts.append(f"• {text_content}")
                    else: # For paragraphs, divs, spans
                        description_parts.append(text_content)

                # Join all parts and perform final cleanup
                final_description = '\n'.join(filter(None, description_parts)) # Filter out empty strings

                # Replace common encoding issues and special characters
                final_description = final_description.replace('\xa0', ' ') # Non-breaking space
                final_description = final_description.replace('\u200b', '') # Zero-width space
                final_description = re.sub(r'â€¢\s*', '• ', final_description) # Standardize bullet points
                final_description = re.sub(r'&[a-z]+;', '', final_description, flags=re.IGNORECASE) # Remove HTML entities like &amp; &lt;
                
                # Clean up excessive newlines or spaces
                final_description = re.sub(r'\n\s*\n', '\n\n', final_description) # Keep some separation between paragraphs
                final_description = re.sub(r'\s{2,}', ' ', final_description).strip() # Reduce multiple spaces to single

                details['description'] = final_description if final_description else None
            else:
                details['description'] = None
            
            return details
            
        except Exception as e:
            logger.error(f"Error scraping job details from {job_url}: {e}")
            return {}
    
    def _parse_date(self, date_text):
        """Parse date text to standard YYYY-MM-DD format, returning None if unparseable."""
        if not date_text:
            return None
        try:
            # Handle ISO format dates (e.g., from datetime attribute)
            if re.match(r'\d{4}-\d{2}-\d{2}', date_text):
                return date_text
            
            # Handle "Month DD, YYYY" format
            match_month_day_year = re.search(r'(\w+)\s+(\d{1,2}),\s+(\d{4})', date_text)
            if match_month_day_year:
                month_name, day, year = match_month_day_year.groups()
                # Convert full month name to number
                month_num = datetime.strptime(month_name, '%B').month
                return f"{year}-{month_num:02d}-{int(day):02d}"
            
            # Handle "DD Month YYYY" format (e.g., 25 July 2025)
            match_day_month_year = re.search(r'(\d{1,2})\s+(\w+)\s+(\d{4})', date_text)
            if match_day_month_year:
                day, month_name, year = match_day_month_year.groups()
                month_num = datetime.strptime(month_name, '%B').month
                return f"{year}-{month_num:02d}-{int(day):02d}"

            # Handle relative dates like "X days ago", "X hours ago"
            match_relative = re.search(r'(\d+)\s+(minute|hour|day|week|month|year)s? ago', date_text, re.IGNORECASE)
            if match_relative:
                num = int(match_relative.group(1))
                unit = match_relative.group(2).lower()
                
                if 'minute' in unit:
                    delta = timedelta(minutes=num)
                elif 'hour' in unit:
                    delta = timedelta(hours=num)
                elif 'day' in unit:
                    delta = timedelta(days=num)
                elif 'week' in unit:
                    delta = timedelta(weeks=num)
                elif 'month' in unit: # Approximate for months
                    delta = timedelta(days=num * 30)
                elif 'year' in unit: # Approximate for years
                    delta = timedelta(days=num * 365)
                else:
                    return None
                
                parsed_date = datetime.now() - delta
                return parsed_date.strftime('%Y-%m-%d')

            return None # Return None if no match
        except Exception as e:
            logger.warning(f"Could not parse date '{date_text}': {e}")
            return None
    
    def _has_next_page(self, pagination_soup, current_page):
        """
        Check if there's a next page available in the pagination.
        This needs to be robust for VacancyBox's dynamic nature.
        """
        # Look for a 'next' link or a link to the next page number
        next_link_text = pagination_soup.find('a', string='→') # Common next arrow
        if next_link_text:
            return True
        
        # Also check for a link to the (current_page + 1) number
        next_page_number_link = pagination_soup.find('a', class_='page-numbers', string=str(current_page + 1))
        if next_page_number_link:
            return True
            
        return False
    
    def _standardize_job_data(self, job_data):
        """Standardize a single job dictionary to match the universal schema."""
        standardized = {
            'site': 'vacancybox',
            'title': job_data.get('title_detailed') or job_data.get('title') or None,
            'company': job_data.get('company_detailed') or job_data.get('company') or None,
            'job_url': job_data.get('job_url') or None,
            'location': job_data.get('location_detailed') or job_data.get('location') or None,
            'description': job_data.get('description') or None,
            'job_type': job_data.get('job_type') or None, # VacancyBox might have job type
            'compensation': job_data.get('salary') or None, # VacancyBox might have salary
            'date_posted': job_data.get('date_posted_detailed') or job_data.get('date_posted') or None,
            'expires': job_data.get('expires') or None,
            'category': job_data.get('category') or None,
            'remote': None,
            'apply_instructions': job_data.get('apply_instructions') or None,
        }
        return standardized


def scrape_vacancybox_jobs(**kwargs):
    """Scrape jobs from VacancyBox (returns a list of standardized dicts)"""
    scraper = VacancyBoxScraper()
    return scraper.scrape_jobs(**kwargs)


if __name__ == "__main__":
    import json
    from core.database import init_db, insert_jobs

    print("Testing VacancyBox scraper (max_pages=1, random delay 5-15s):")
    jobs_data = scrape_vacancybox_jobs()

    print(f"\nFound {len(jobs_data)} jobs")
    if len(jobs_data) > 0:
        init_db()
        count = insert_jobs(jobs_data)
        print(f"\nInserted {count} new job(s) into database.")
