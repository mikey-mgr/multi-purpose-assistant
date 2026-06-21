"""
Prefect flows for the automated job application pipeline.

Exposes five independently-deployable flows:
  1. scrape-and-store      — run scrapers, insert jobs
  2. match-jobs            — batch-classify unscored jobs
  3. generate-matched      — generate docs for matched jobs
  4. apply-agent           — process apply_instructions for matched jobs
  5. pull-and-process      — scrape → match → generate → apply (all-in-one)
"""

import logging

from prefect import flow, task, get_run_logger

from app.config import settings
from app.matcher import batch_match_jobs
from app.orchestrator import process_job_for_user, batch_process_applications
from core.database import get_matched_unprocessed_jobs, update_job_match_status
from scrapers.unified_scraper import UnifiedJobScraper

logger = logging.getLogger(__name__)


# ── Tasks ──────────────────────────────────────────────────────────────

@task(retries=2, retry_delay_seconds=30)
def run_scrapers(
    site_names: list[str] | None = None,
    max_pages: dict = {},
) -> int:
    """Scrape specified job boards and insert new jobs into PostgreSQL."""
    from core.database import init_db, insert_jobs

    run_logger = get_run_logger()
    site_names = site_names or ["iharare", "vacancybox", "vacancymail"]
    run_logger.info("Scraping job boards %s (max_pages=%s) ...", site_names, max_pages)
    scraper = UnifiedJobScraper()
    kwargs = {"max_pages": max_pages} if max_pages else {}
    jobs_df = scraper.scrape_jobs(
        site_name=site_names,
        **kwargs,
    )
    if jobs_df.empty:
        get_run_logger().warning("No jobs found from any site.")
        return 0
    init_db()
    count = insert_jobs(jobs_df.to_dict("records"))
    get_run_logger().info("Inserted %d new jobs into database.", count)
    return count


@task(retries=2, retry_delay_seconds=30)
def match_pending_jobs(
    user_id: str,
    limit: int = 50,
    match_model: str = "openai/gpt-4o-mini",
    match_provider: str | None = None,
) -> int:
    """Batch-classify unscored jobs and persist decisions."""
    decisions = batch_match_jobs(
        user_id, limit=limit, model=match_model, provider=match_provider
    )
    return len(decisions)


@task(retries=2, retry_delay_seconds=30)
def fetch_matched_jobs(user_id: str, limit: int = 10) -> list:
    """Fetch matched jobs that haven't been generated yet."""
    return get_matched_unprocessed_jobs(user_id, limit=limit)


@task(retries=2, retry_delay_seconds=30)
def fetch_generated_jobs(user_id: str, limit: int = 10) -> list:
    """Fetch jobs that have documents generated but not yet applied to."""
    return get_generated_unapplied_jobs(user_id, limit=limit)


@task
def generate_application(
    job_id: int,
    user_id: str,
    generate_model: str | None = None,
    generate_provider: str | None = None,
    generate_fallback_model: str | None = None,
    generate_fallback_provider: str | None = None,
) -> dict:
    """Run the full generation pipeline for one matched job + user."""
    docs = process_job_for_user(
        user_id=user_id,
        job_id=job_id,
        model=generate_model,
        provider=generate_provider,
        fallback_model=generate_fallback_model,
        fallback_provider=generate_fallback_provider,
    )
    if docs:
        update_job_match_status(job_id, user_id, "generated")
    return {
        "job_id": job_id,
        "user_id": user_id,
        "documents": len(docs),
        "status": "completed" if docs else "failed",
    }


@task
def mark_processed(result: dict) -> None:
    """Log result."""
    get_run_logger().info(
        "Job %s processed for user %s — %d documents generated.",
        result["job_id"],
        result["user_id"],
        result["documents"],
    )


# ── Flows ──────────────────────────────────────────────────────────────

@flow(
    name="scrape-and-store",
    description="Scrape all Zimbabwe job boards and insert new postings.",
    retries=1,
    retry_delay_seconds=60,
    log_prints=True,
)
def scrape_and_store(
    site_names: list[str] | None = None,
    max_pages: dict = {},
):
    """Scrape iHarare, VacancyBox, VacancyMail and insert new jobs."""
    run_logger = get_run_logger()
    count = run_scrapers(site_names=site_names, max_pages=max_pages)
    run_logger.info("Scrape complete — %d new jobs inserted.", count)


@flow(
    name="match-jobs",
    description="Batch-classify unscored jobs via LLM.",
    retries=1,
    retry_delay_seconds=60,
    log_prints=True,
)
def match_jobs_flow(
    user_id: str,
    limit: int = 50,
    match_model: str = "openai/gpt-4o-mini",
    match_provider: str | None = None,
):
    """Match unscored jobs for a user."""
    run_logger = get_run_logger()
    matched = match_pending_jobs(
        user_id, limit=limit, match_model=match_model, match_provider=match_provider
    )
    run_logger.info("Match complete — %d decisions saved.", matched)


@flow(
    name="generate-matched",
    description="Generate resume + cover letter for all matched-but-unprocessed jobs.",
    retries=1,
    retry_delay_seconds=60,
    log_prints=True,
)
def generate_matched_flow(
    user_id: str,
    limit: int = 10,
    generate_model: str | None = None,
    generate_provider: str | None = None,
    generate_fallback_model: str | None = None,
    generate_fallback_provider: str | None = None,
):
    """
    Generate documents for matched jobs that haven't been generated yet.

    Parameters
    ----------
    user_id : str
    limit : int
        Max number of matched-but-unprocessed jobs to process this run.
    generate_model : str | None
        Override model for resume + cover letter (None → LLM_MODEL).
    generate_provider : str | None
        Provider for generation (None → LLM_PROVIDER).
    generate_fallback_model : str | None
        Fallback model if primary fails.
    generate_fallback_provider : str | None
        Fallback provider if primary fails.
    """
    run_logger = get_run_logger()
    jobs = fetch_matched_jobs(user_id, limit=limit)
    if not jobs:
        run_logger.info("No matched-but-unprocessed jobs found.")
        return

    run_logger.info("Generating documents for %d matched jobs.", len(jobs))

    results = generate_application.map(
        job_id=[j.id for j in jobs],
        user_id=[user_id] * len(jobs),
        generate_model=[generate_model] * len(jobs),
        generate_provider=[generate_provider] * len(jobs),
        generate_fallback_model=[generate_fallback_model] * len(jobs),
        generate_fallback_provider=[generate_fallback_provider] * len(jobs),
    )

    for r in results:
        mark_processed(r)


@flow(
    name="apply-agent",
    description="Parse apply_instructions for matched jobs and send email / WhatsApp notification.",
    retries=1,
    retry_delay_seconds=60,
    log_prints=True,
)
def apply_agent_flow(
    user_id: str,
    limit: int = 10,
    generate_model: str | None = None,
    generate_provider: str | None = None,
):
    """
    Process apply_instructions for matched-but-unapplied jobs using a single batch LLM call.

    Parameters
    ----------
    user_id : str
    limit : int
        Max number of jobs to process this run.
    generate_model : str | None
    generate_provider : str | None
    """
    run_logger = get_run_logger()
    results = batch_process_applications(
        user_id=user_id,
        limit=limit,
        model=generate_model,
        provider=generate_provider,
    )
    run_logger.info("Batch apply complete — %d jobs processed.", len(results))
    for r in results:
        run_logger.info(
            "Apply agent: job=%s action=%s email=%s whatsapp=%s",
            r.get("job_id"), r.get("action"),
            r.get("email_sent"), r.get("whatsapp_sent"),
        )


@flow(
    name="pull-and-process-jobs",
    description="Match unscored jobs → generate resume + cover letter for matches.",
    retries=1,
    retry_delay_seconds=60,
    log_prints=True,
)
def pull_and_process_jobs(
    user_id: str,
    match_limit: int = 50,
    job_limit: int = 10,
    match_model: str = "openai/gpt-4o-mini",
    generate_model: str | None = None,
    match_provider: str | None = None,
    generate_provider: str | None = None,
    generate_fallback_model: str | None = None,
    generate_fallback_provider: str | None = None,
    **kwargs,
):
    """
    Match unscored jobs, generate for matched ones, then apply.

    Scraping is a separate flow (``scrape-and-store`` — run on its own cron).

    Parameters
    ----------
    user_id : str
    match_limit : int
        Max unscored jobs to evaluate this run.
    job_limit : int
        Max matched-but-unprocessed jobs to generate for this run.
    match_model : str
        Model for batch matching (cheap).
    generate_model : str | None
        Model for resume / cover letter (None → LLM_MODEL).
    generate_fallback_model : str | None
        Fallback model if primary fails.
    generate_fallback_provider : str | None
        Fallback provider if primary fails.
    match_provider : str | None
        Provider for matching (None → LLM_PROVIDER).
    generate_provider : str | None
        Provider for generation (None → LLM_PROVIDER).
    """
    run_logger = get_run_logger()
    run_logger.info("Starting pipeline for user %s ...", user_id)

    # Step 1 — match unscored jobs
    matched_count = match_pending_jobs(
        user_id, limit=match_limit, match_model=match_model, match_provider=match_provider
    )
    run_logger.info("Batch match complete — %d decisions saved.", matched_count)

    # Step 2 — generate documents for matched jobs (parallel)
    jobs = fetch_matched_jobs(user_id, limit=job_limit)
    if not jobs:
        run_logger.info("No matched-but-unprocessed jobs found.")
        return

    run_logger.info("Generating documents for %d matched jobs.", len(jobs))
    results = generate_application.map(
        job_id=[j.id for j in jobs],
        user_id=[user_id] * len(jobs),
        generate_model=[generate_model] * len(jobs),
        generate_provider=[generate_provider] * len(jobs),
        generate_fallback_model=[generate_fallback_model] * len(jobs),
        generate_fallback_provider=[generate_fallback_provider] * len(jobs),
    )

    # Step 3 — batch-apply for all completed jobs
    for result in results:
        mark_processed(result)

    completed_jobs = [j for j, r in zip(jobs, results) if r.get("status") == "completed"]
    if completed_jobs:
        apply_results = batch_process_applications(
            user_id=user_id,
            limit=len(completed_jobs),
            model=generate_model,
            provider=generate_provider,
        )


@flow(
    name="manual-generate",
    description="One-shot generation for a specific job + user.",
)
def manual_generate(
    user_id: str,
    job_id: int,
    generate_model: str | None = None,
    generate_provider: str | None = None,
):
    """Trigger document generation for one specific job posting."""
    result = generate_application(
        job_id=job_id,
        user_id=user_id,
        generate_model=generate_model,
        generate_provider=generate_provider,
    )
    mark_processed(result)
    return result


# ── CLI entry point ────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 3 and sys.argv[1] == "--manual":
        manual_generate(user_id=sys.argv[2], job_id=int(sys.argv[3]))
    else:
        user_id = sys.argv[1] if len(sys.argv) >= 2 else "default"
        pull_and_process_jobs(user_id=user_id)
