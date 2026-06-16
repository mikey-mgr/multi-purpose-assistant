# Scrapers — Job Board Scrapers

Modular scrapers for Zimbabwean job boards. Each scraper can run standalone or via the unified interface.

## Modules

| Module | Class | Site | Entry Point |
|--------|-------|------|-------------|
| `unified_scraper` | `UnifiedJobScraper` | All sites | `python -m scrapers.unified_scraper` |
| `iharare_scraper` | `IHarareJobsScraper` | ihararejobs.com | `python -m scrapers.iharare_scraper` |
| `vacancybox_scraper` | `VacancyBoxScraper` | vacancybox.co.zw | `python -m scrapers.vacancybox_scraper` |
| `vacancymail_scraper` | `VacancyMailScraper` | vacancymail.co.zw | `python -m scrapers.vacancymail_scraper` |

## CLI Usage

Each module runs a self-test when executed directly. All scrapers accept the same parameters:

```bash
# Run a single scraper with default settings (5 jobs)
python -m scrapers.iharare_scraper
python -m scrapers.vacancybox_scraper
python -m scrapers.vacancymail_scraper

# Run the unified scraper (all 3 sites, 2 jobs each)
python -m scrapers.unified_scraper
```

### Parameters (per-scraper `scrape_jobs`)

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `max_pages` | int | 2 (1 for VacancyBox) | Max pages to request |
| `delay` | int/None | None (random 5–15s) | Seconds between requests |
| `max_jobs` | int/None | None | Max jobs to collect (`None` = all from `max_pages`) |

### Top-level convenience functions

Each module exposes a `scrape_<site>_jobs(**kwargs)` function that passes all kwargs through to the class `scrape_jobs()`:

```python
from scrapers.iharare_scraper import scrape_iharare_jobs
from scrapers.vacancybox_scraper import scrape_vacancybox_jobs
from scrapers.vacancymail_scraper import scrape_vacancymail_jobs

# Uses defaults: max_pages=2, random delay 5-15s, all jobs on pages
jobs = scrape_iharare_jobs()

# Override individual params
jobs = scrape_vacancymail_jobs(max_pages=3, delay=10)
```

## Unified Interface

The `UnifiedJobScraper` aggregates all site scrapers and provides a `pandas.DataFrame` output.

```python
from scrapers.unified_scraper import UnifiedJobScraper, scrape_jobs

# Via class
scraper = UnifiedJobScraper()
df = scraper.scrape_jobs(site_name=['iharare', 'vacancybox'], results_wanted=25)

# Via convenience function (JobSpy-compatible)
df = scrape_jobs(site_name='vacancymail', results_wanted=10)

# All sites
df = scrape_jobs(results_wanted=50)
```

### `UnifiedJobScraper.scrape_jobs()` Parameters

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `site_name` | str / list[str] / None | `None` | Site(s) to scrape; `None` = all |
| `results_wanted` | int | 50 | Max total jobs across all sites |
| `hours_old` | int | 72 | Max age (hours) — stored in schema, not enforced |

Supported sites: `iharare`, `vacancybox`, `vacancymail`.

## Output Schema

All scrapers produce a standardized list of dicts with these fields:

| Field | Type | Description |
|-------|------|-------------|
| `site` | str | Source site key (`iharare`, `vacancybox`, `vacancymail`) |
| `title` | str/None | Job title |
| `company` | str/None | Employer name |
| `job_url` | str/None | Full URL to the job listing |
| `location` | str/None | Job location |
| `description` | str/None | Cleaned job description (relevant sections only, ads removed) |
| `job_type` | str/None | e.g. "Full Time", "Contract" |
| `compensation` | str/None | Salary info (only available on VacancyMail) |
| `date_posted` | str/None | Posted date in `YYYY-MM-DD` |
| `expires` | str/None | Closing date in `YYYY-MM-DD` |
| `category` | str/None | Job category (iharare, vacancymail) |
| `remote` | str/None | Remote status (not yet populated) |

## Per-Scraper Notes

### iHarare (`iharare_scraper.py`)
- Scrapes listing pages then individual detail pages.
- Extracts: title, company, location, job type, category, description, dates.
- Description focuses on relevant sections (duties, requirements, skills) and excludes "How to Apply".

### VacancyBox (`vacancybox_scraper.py`)
- Uses AJAX pagination (`admin-ajax.php?action=job_manager_get_listings`).
- Extracts: title, company, location, description, expiry date.
- Description cleaning removes ad divs, "TO APPLY" sections, and trims trailing contact info.

### VacancyMail (`vacancymail_scraper.py`)
- Scrapes listing pages then individual detail pages.
- Extracts: title, company, location, job type, salary, category, dates, description.
- Only scraper that provides `compensation` (salary) data.
- Parses relative posted times ("Posted 3 days ago") into absolute dates.

## Output & Persistence

When run via `python -m scrapers.<module>` or the unified `__main__`, each scraper **inserts job records** into the local PostgreSQL `ai_assistant` database (`scraped_jobs` table). Duplicates are skipped based on `job_url`.

Database credentials are read from the `DB_CONN_URI` environment variable (see `.env`).

Run the migration to initialise the database:

```bash
psql -U postgres -f db_configs/migrations/init.sql
```

Or let the scraper create the table automatically on first run (`init_db()` is called from each `__main__` block).

## Default Behaviour

| Scraper | `max_pages` | Delay | Job Limit |
|---------|-------------|-------|-----------|
| iHarare | 2 | Random 5–15s | All jobs on page(s) |
| VacancyMail | 2 | Random 5–15s | All jobs on page(s) |
| VacancyBox | 1 | Random 5–15s | All jobs on page(s) |

These can be overridden by passing parameters to `scrape_jobs()` or the convenience functions.

## Dependencies

Install all at once:

```bash
pip install -r requirements.txt
```
