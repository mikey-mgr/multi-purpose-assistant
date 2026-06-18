"""
Prefect flows for the automated job application pipeline.

Pipeline:
  1. Match unscored jobs (batch LLM) → job_matches table
  2. For each matched job, generate resume + cover letter
"""

import logging
from datetime import timedelta

from prefect import flow, task, get_run_logger
from prefect.tasks import task_input_hash

from app.config import settings
from app.matcher import batch_match_jobs
from app.orchestrator import process_job_for_user
from core.database import get_matched_unprocessed_jobs

logger = logging.getLogger(__name__)


# ── Tasks ──────────────────────────────────────────────────────────────

@task(retries=2, retry_delay_seconds=30, cache_key_fn=task_input_hash)
def match_pending_jobs(user_id: str, limit: int = 50) -> int:
    """Batch-classify unscored jobs and persist decisions."""
    decisions = batch_match_jobs(user_id, limit=limit)
    return len(decisions)


@task(retries=2, retry_delay_seconds=30, cache_key_fn=task_input_hash)
def fetch_matched_jobs(user_id: str, limit: int = 10) -> list:
    """Fetch matched jobs that haven't been generated yet."""
    return get_matched_unprocessed_jobs(user_id, limit=limit)


@task(timeout_seconds=300, retries=1)
def generate_application(job_id: int, user_id: str) -> dict:
    """Run the full generation pipeline for one matched job + user."""
    docs = process_job_for_user(user_id=user_id, job_id=job_id)
    return {
        "job_id": job_id,
        "user_id": user_id,
        "documents": len(docs),
        "status": "completed",
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
    name="pull-and-process-jobs",
    description="Match unscored jobs, then generate documents for matched ones.",
    retries=1,
    retry_delay_seconds=60,
    log_prints=True,
)
def pull_and_process_jobs(
    user_id: str,
    match_limit: int = 50,
    job_limit: int = 10,
):
    """
    Scheduled flow: match new jobs, then generate resume + cover letter
    for every matched job that hasn't been generated yet.
    """
    run_logger = get_run_logger()
    run_logger.info("Starting pipeline for user %s ...", user_id)

    # Step 1 — match unscored jobs
    matched_count = match_pending_jobs(user_id, limit=match_limit)
    run_logger.info("Batch match complete — %d decisions saved.", matched_count)

    # Step 2 — generate documents for matched jobs
    jobs = fetch_matched_jobs(user_id, limit=job_limit)
    if not jobs:
        run_logger.info("No matched-but-unprocessed jobs found.")
        return

    run_logger.info("Generating documents for %d matched jobs.", len(jobs))
    for job in jobs:
        result = generate_application(job_id=job.id, user_id=user_id)
        mark_processed(result)


@flow(
    name="manual-generate",
    description="One-shot generation for a specific job + user.",
)
def manual_generate(user_id: str, job_id: int):
    """Trigger document generation for one specific job posting."""
    result = generate_application(job_id=job_id, user_id=user_id)
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
