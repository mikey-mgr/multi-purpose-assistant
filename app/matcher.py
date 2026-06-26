"""
Batch job matcher.

For a given user, fetches unscored job postings and the user's
technical profile, sends both to the LLM in a single prompt, and
persists the match/reject decisions to the job_matches table.
"""

import json
import logging
from typing import Any

from sqlalchemy import select

from core.database import (
    get_session,
    Resume,
    WorkExperience,
    Education,
    Project,
    Skill,
    ScrapedJob,
    JobMatch,
    bulk_insert_job_matches,
    save_job_enrichments,
    get_deduped_unscored_jobs,
)
from app.llm import generate_text

logger = logging.getLogger(__name__)


def _build_user_summary(user_id: str) -> dict:
    """Gather the fields relevant for matching."""
    session = get_session()
    try:
        resume_id_q = select(Resume.id).where(
            Resume.user_id == user_id, Resume.is_active == True
        )
        resume_id = session.execute(resume_id_q).scalar()
        if not resume_id:
            return {}

        # Active resume
        resume = session.get(Resume, resume_id)
        summary = (resume.professional_summary or "")
        words = summary.split()
        summary_trunc = " ".join(words[:70]) + ("..." if len(words) > 70 else "")

        # Technical skills (exclude Soft Skills)
        skill_rows = session.execute(
            select(Skill.skill_name).where(
                Skill.resume_id == resume_id,
                Skill.skill_type != "Soft Skill",
            )
        ).scalars().all()

        # Education
        edu_rows = session.execute(
            select(Education).where(Education.resume_id == resume_id)
        ).scalars().all()

        # Work experience with bullet points (first 3)
        exp_rows = session.execute(
            select(WorkExperience).where(WorkExperience.resume_id == resume_id).order_by(WorkExperience.display_order)
        ).scalars().all()

        # Projects with bullet points (first 2)
        proj_rows = session.execute(
            select(Project).where(Project.resume_id == resume_id).order_by(Project.display_order)
        ).scalars().all()

        return {
            "professional_summary": summary_trunc,
            "technical_skills": sorted(set(skill_rows)),
            "work_experience": [
                {
                    "company": e.company_name,
                    "title": e.job_title,
                    "highlights": (e.bullet_points or [])[:3],
                }
                for e in exp_rows
            ],
            "education": [
                f"{e.degree_type} {e.field_of_study}" for e in edu_rows
            ],
            "projects": [
                {
                    "name": p.project_name,
                    "highlights": (p.bullet_points or [])[:2],
                }
                for p in proj_rows
            ],
        }
    finally:
        session.close()


def _build_prompt(profile: dict, jobs: list[ScrapedJob]) -> str:
    """Build the batch LLM prompt (data portion — instructions in DB prompt)."""
    lines = [
        json.dumps(profile, indent=2),
        "",
        "## Jobs",
    ]
    for i, job in enumerate(jobs, 1):
        desc = (job.description or "")
        lines.extend([
            f"### Job {i}",
            f"- job_index: {i}",
            f"- title: {job.title}",
            f"- company: {job.company}",
            f"- description: {desc}",
            f"- location: {job.location}",
            f"- job_type: {job.job_type}",
            f"- compensation: {job.compensation or 'Not listed'}",
            f"- category: {job.category or 'Not listed'}",
            f"- remote: {job.remote or 'Not listed'}",
            f"- date_posted: {job.date_posted or 'Not listed'}",
            f"- site: {job.site}",
            "",
        ])

    # instructions in DB prompt
    return "\n".join(lines)


def _parse_response(raw: str, jobs: list[ScrapedJob]) -> tuple[list[dict], list[dict]]:
    """
    Parse LLM JSON response into match decision dicts + enrichment dicts.

    Returns (decisions, enrichments) where:
      decisions — list of dicts for job_matches table
      enrichments — list of dicts for job_enrichments table
    """
    # Strip markdown fences
    if "```json" in raw:
        raw = raw.split("```json")[1].split("```")[0].strip()
    elif "```" in raw:
        raw = raw.split("```")[1].split("```")[0].strip()

    # Find the outermost JSON array
    start = raw.find("[")
    end = raw.rfind("]")
    if start == -1 or end == -1 or end <= start:
        logger.warning("No JSON array found in LLM response")
        return [], []
    raw = raw[start:end + 1]

    # Remove control characters that break json.loads
    raw = "".join(ch for ch in raw if ch >= " " or ch in "\n\r\t")

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Failed to parse LLM match response as JSON")
        return [], []

    if not isinstance(parsed, list):
        return [], []

    decisions = []
    enrichments = []
    for item in parsed:
        idx = item.get("job_index", 0) - 1
        if 0 <= idx < len(jobs):
            decisions.append({
                "job_id": jobs[idx].id,
                "user_id": None,  # filled by caller
                "status": item.get("status", "rejected"),
                "score": item.get("score"),
                "reason": item.get("reason"),
                "matched_by": "llm",
                "llm_raw": json.dumps(item),
            })
            # Extract enrichment
            enc = item.get("enrichment") or {}
            salary = enc.get("salary_range") or {}
            enrichments.append({
                "job_id": jobs[idx].id,
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
            })
    return decisions, enrichments


def _to_float(v) -> float | None:
    """Safely convert a value to float or None."""
    if v is None:
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def batch_match_jobs(
    user_id: str,
    limit: int = 50,
    model: str = "openai/gpt-oss-120b:free",
    provider: str | None = None,
) -> list[dict]:
    """
    Main entry point.

    1. Build user profile summary
    2. Fetch unscored jobs
    3. Call LLM in batch mode
    4. Persist decisions to job_matches

    Returns the list of match decisions that were inserted.
    """
    logger.info("Building user profile summary for %s ...", user_id)
    profile = _build_user_summary(user_id)
    if not profile:
        logger.warning("No active resume found for user %s", user_id)
        return []

    logger.info(
        "Profile: %d skills, %d work entries, %d education entries, %d projects",
        len(profile.get("technical_skills", [])),
        len(profile.get("work_experience", [])),
        len(profile.get("education", [])),
        len(profile.get("projects", [])),
    )

    jobs, dedup_map = get_deduped_unscored_jobs(user_id, limit=limit)
    if not jobs:
        logger.info("No unscored jobs for user %s", user_id)
        return []

    logger.info("Fetched %d unscored jobs (limit=%d, %d duplicate groups collapsed)",
                len(jobs), limit, len(dedup_map))

    prompt_text = _build_prompt(profile, jobs)
    logger.info("Sending %d jobs to LLM for batch classification ...", len(jobs))

    result = generate_text(
        "job_matcher_v1",
        model=model,
        provider=provider,
        batch_input=prompt_text,
    )
    raw = result.get("content", "")

    decisions, enrichments = _parse_response(raw, jobs)
    if not decisions:
        logger.warning("Matcher returned 0 decisions for %d jobs", len(jobs))
        return []

    # Attach user_id now that we have the parsed decisions
    for d in decisions:
        d["user_id"] = user_id

    # Propagate match/reject to duplicate jobs (same title+company from other sites)
    extra_matches = []
    extra_enrichments = []
    for d in decisions:
        dups = dedup_map.get(d["job_id"], [])
        for dup_id in dups:
            extra_matches.append({
                "job_id": dup_id,
                "user_id": user_id,
                "status": d["status"],
                "score": d["score"],
                "reason": d.get("reason"),
                "matched_by": "llm_dedup",
                "llm_raw": d.get("llm_raw"),
            })
        # Propagate enrichment to duplicate jobs too
        enc = next((e for e in enrichments if e["job_id"] == d["job_id"]), None)
        if enc:
            for dup_id in dups:
                dup_enc = dict(enc)
                dup_enc["job_id"] = dup_id
                extra_enrichments.append(dup_enc)

    if extra_matches:
        bulk_insert_job_matches(extra_matches)
        logger.info("Propagated %d decisions to collapsed duplicate jobs", len(extra_matches))

    bulk_insert_job_matches(decisions)

    # Save enrichments (includes duplicates)
    all_enrichments = enrichments + extra_enrichments
    if all_enrichments:
        for e in all_enrichments:
            e["enrichment_model"] = model
        save_job_enrichments(all_enrichments)
        logger.info("Saved enrichment data for %d jobs", len(all_enrichments))

    matched = sum(1 for d in decisions if d["status"] == "matched")
    logger.info(
        "Matched %d jobs for user %s: %d accepted, %d rejected (%d extra via dedup)",
        len(decisions), user_id, matched,
        len(decisions) - matched,
        len(extra_matches),
    )
    return decisions + extra_matches
