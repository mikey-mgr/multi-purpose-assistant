"""
Backfill enrichment data for all scraped jobs missing job_enrichments.

Usage:
    conda run -n prefect_env python scripts/backfill_enrichments.py
    conda run -n prefect_env python scripts/backfill_enrichments.py --batch-size 20 --model openai/gpt-oss-120b:free
"""

import argparse
import json
import logging
import sys
import time

from core.database import (
    get_session,
    ScrapedJob,
    JobEnrichment,
    save_job_enrichments,
)
from app.llm import generate_text_direct

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
)
logger = logging.getLogger(__name__)

ENRICHMENT_PROMPT = """
You are a job metadata extraction assistant. Given a list of job postings, extract structured metadata from each one.

For each job return an object with:
- job_index (int): 1-based index from the jobs list below
- enrichment (object): structured metadata with these fields:
  - technical_skills (array of strings): tools, software, programming languages, methodologies, equipment explicitly mentioned as requirements — e.g. "sap", "python", "autocad", "crm software", "gis", "microsoft excel", "seo", "social media management". Convert to lowercase. List each distinct skill separately — be thorough.
  - soft_skills (array of strings): interpersonal, communication, personality traits, work style attributes explicitly mentioned — e.g. "communication", "problem-solving", "attention to detail", "teamwork", "leadership", "time management", "analytical thinking", "customer service". Convert to lowercase.
  - required_qualifications (array of strings): degrees, diplomas, certifications, licences, trade certificates explicitly required — e.g. "degree in computer science", "class 4 driver's licence", "cima", "acca", "cisa", "trade certificate in fitting and turning". Convert to lowercase. Include only formal credentials, NOT skills.
  - required_experience (string or null): experience level mentioned — e.g. "3+ years", "entry-level", "5+ years", "minimum 5 years", "senior". One concise phrase, or null if not mentioned.
  - salary_range (object or null): extracted salary info with fields: {"min": number|null, "max": number|null, "currency": string|null} — null if no salary info
  - category (string or null): normalized category — "Engineering", "IT", "Sales", "Administration", "Hospitality", "Construction", "Education", "Healthcare", "Finance", "Agriculture", "Logistics", "Marketing", "Legal", "Other"
  - job_type (string or null): normalized type — "Full-time", "Part-time", "Contract", "Temporary", "Internship", "Volunteer", or null
  - remote_eligible (boolean or null): true if remote/hybrid, false if on-site, null if unclear

Return ONLY a JSON array of these objects. No markdown fences or extra text.
"""


def get_jobs_without_enrichment() -> list[ScrapedJob]:
    """Return all scraped_jobs that don't have a job_enrichments row."""
    session = get_session()
    try:
        subq = session.query(JobEnrichment.job_id).subquery()
        rows = session.query(ScrapedJob).outerjoin(
            subq, ScrapedJob.id == subq.c.job_id
        ).filter(
            subq.c.job_id == None,
            ScrapedJob.description.isnot(None),
            ScrapedJob.description != "",
        ).order_by(ScrapedJob.scraped_at.desc()).all()
        return rows
    finally:
        session.close()


def _build_prompt_chunk(jobs: list[ScrapedJob], start_index: int = 1) -> str:
    """Build a prompt chunk for a batch of jobs."""
    lines = ["## Jobs"]
    for i, job in enumerate(jobs, start_index):
        lines.extend([
            f"### Job {i}",
            f"- job_index: {i}",
            f"- title: {job.title}",
            f"- company: {job.company}",
            f"- description: {job.description or ''}",
            f"- location: {job.location or 'Not listed'}",
            f"- job_type: {job.job_type or 'Not listed'}",
            f"- compensation: {job.compensation or 'Not listed'}",
            f"- category: {job.category or 'Not listed'}",
            f"- remote: {job.remote or 'Not listed'}",
            "",
        ])
    return "\n".join(lines)


def _parse_enrichments(raw: str) -> list[dict]:
    """Parse LLM json response into enrichment dicts."""
    if "```json" in raw:
        raw = raw.split("```json")[1].split("```")[0].strip()
    elif "```" in raw:
        raw = raw.split("```")[1].split("```")[0].strip()
    start = raw.find("[")
    end = raw.rfind("]")
    if start == -1 or end == -1 or end <= start:
        return []
    raw = raw[start:end + 1]
    raw = "".join(ch for ch in raw if ch >= " " or ch in "\n\r\t")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return parsed


def _to_float(v):
    if v is None:
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def backfill_enrichments(
    batch_size: int = 20,
    model: str = "openai/gpt-oss-120b:free",
    delay: float = 1.0,
):
    """Backfill enrichment data for all jobs missing it."""
    jobs = get_jobs_without_enrichment()
    if not jobs:
        logger.info("No jobs missing enrichment data.")
        return

    logger.info("Found %d jobs without enrichment. Processing in batches of %d ...", len(jobs), batch_size)

    total_enriched = 0
    for batch_start in range(0, len(jobs), batch_size):
        batch = jobs[batch_start:batch_start + batch_size]
        prompt_chunk = _build_prompt_chunk(batch, start_index=1)

        logger.info("Batch %d/%d: %d jobs ...", batch_start // batch_size + 1, (len(jobs) + batch_size - 1) // batch_size, len(batch))

        try:
            result = generate_text_direct(
                system_prompt=ENRICHMENT_PROMPT,
                user_prompt=prompt_chunk,
                model=model,
            )
        except Exception as e:
            logger.error("LLM call failed for batch: %s — skipping batch", e)
            time.sleep(5)
            continue

        raw = result.get("content", "")
        parsed = _parse_enrichments(raw)
        if not parsed:
            logger.warning("Failed to parse LLM output for batch — skipping")
            time.sleep(5)
            continue

        enrichments = []
        for item in parsed:
            idx = item.get("job_index", 0) - 1
            if 0 <= idx < len(batch):
                enc = item.get("enrichment") or {}
                salary = enc.get("salary_range") or {}
                enrichments.append({
                    "job_id": batch[idx].id,
                    "technical_skills": enc.get("technical_skills"),
                    "soft_skills": enc.get("soft_skills"),
                    "required_qualifications": enc.get("required_qualifications"),
                    "required_experience": enc.get("required_experience"),
                    "min_salary": _to_float(salary.get("min")),
                    "max_salary": _to_float(salary.get("max")),
                    "currency": salary.get("currency"),
                    "normalized_category": enc.get("category"),
                    "job_type": enc.get("job_type"),
                    "remote_eligible": enc.get("remote_eligible"),
                    "enrichment_model": model,
                })

        if enrichments:
            save_job_enrichments(enrichments)
            total_enriched += len(enrichments)
            logger.info("Saved enrichment for %d jobs (total: %d)", len(enrichments), total_enriched)

        if batch_start + batch_size < len(jobs):
            time.sleep(delay)

    logger.info("Backfill complete — %d jobs enriched.", total_enriched)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill job enrichment data")
    parser.add_argument("--batch-size", type=int, default=20, help="Jobs per LLM batch")
    parser.add_argument("--model", type=str, default="openai/gpt-oss-120b:free", help="LLM model for extraction")
    parser.add_argument("--delay", type=float, default=1.0, help="Delay between batches (seconds)")
    args = parser.parse_args()
    backfill_enrichments(batch_size=args.batch_size, model=args.model, delay=args.delay)
