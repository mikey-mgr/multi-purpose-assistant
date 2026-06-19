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
    get_unscored_jobs,
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

        # Technical skills (exclude Soft Skills)
        skill_rows = session.execute(
            select(Skill.skill_name).where(
                Skill.resume_id == resume_id,
                Skill.skill_type != "Soft Skill",
            )
        ).scalars().all()

        # Work experience titles
        title_rows = session.execute(
            select(WorkExperience.job_title).where(
                WorkExperience.resume_id == resume_id
            )
        ).scalars().all()

        # Education
        edu_rows = session.execute(
            select(Education).where(Education.resume_id == resume_id)
        ).scalars().all()

        # Project tech stacks
        stack_rows = session.execute(
            select(Project.tech_stack).where(Project.resume_id == resume_id)
        ).scalars().all()

        return {
            "technical_skills": sorted(set(skill_rows)),
            "work_experience_titles": sorted(set(title_rows)),
            "education": [
                f"{e.degree_type} {e.field_of_study}" for e in edu_rows
            ],
            "project_technologies": sorted(set(
                tech for stack in stack_rows if stack for tech in stack
            )),
        }
    finally:
        session.close()


def _build_prompt(profile: dict, jobs: list[ScrapedJob]) -> str:
    """Build the batch LLM prompt."""
    lines = [
        "You are a job matching assistant. Given a user's profile and a list of",
        "job postings, determine which jobs are relevant to the user's background.",
        "",
        "## User Profile",
        json.dumps(profile, indent=2),
        "",
        "## Jobs",
    ]
    for i, job in enumerate(jobs, 1):
        desc = (job.description or "")[:600]
        lines.extend([
            f"### Job {i}",
            f"- job_index: {i}",
            f"- title: {job.title}",
            f"- company: {job.company}",
            f"- description: {desc}",
            f"- location: {job.location}",
            f"- job_type: {job.job_type}",
            "",
        ])

    lines.append(
        "Return ONLY a JSON array of objects with keys: "
        "job_index (int), status (\"matched\"|\"rejected\"), "
        "score (int 0-100), reason (short explanation)."
    )
    return "\n".join(lines)


def _parse_response(raw: str, jobs: list[ScrapedJob]) -> list[dict]:
    """Parse LLM JSON response into match decision dicts."""
    if "```json" in raw:
        raw = raw.split("```json")[1].split("```")[0].strip()
    elif "```" in raw:
        raw = raw.split("```")[1].split("```")[0].strip()

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Failed to parse LLM match response as JSON")
        return []

    if not isinstance(parsed, list):
        return []

    decisions = []
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
    return decisions


def batch_match_jobs(
    user_id: str,
    limit: int = 50,
    model: str = "openai/gpt-4o-mini",
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
        "Profile: %d skills, %d work titles, %d education entries, %d project techs",
        len(profile.get("technical_skills", [])),
        len(profile.get("work_experience_titles", [])),
        len(profile.get("education", [])),
        len(profile.get("project_technologies", [])),
    )

    jobs = get_unscored_jobs(user_id, limit=limit)
    if not jobs:
        logger.info("No unscored jobs for user %s", user_id)
        return []

    logger.info("Fetched %d unscored jobs (limit=%d)", len(jobs), limit)

    prompt_text = _build_prompt(profile, jobs)
    logger.info("Sending %d jobs to LLM for batch classification ...", len(jobs))

    result = generate_text(
        "job_matcher_v1",
        model=model,
        provider=provider,
        batch_input=prompt_text,
    )
    raw = result.get("content", "")

    decisions = _parse_response(raw, jobs)
    if not decisions:
        logger.warning("Matcher returned 0 decisions for %d jobs", len(jobs))
        return []

    # Attach user_id now that we have the parsed decisions
    for d in decisions:
        d["user_id"] = user_id

    bulk_insert_job_matches(decisions)

    matched = sum(1 for d in decisions if d["status"] == "matched")
    logger.info(
        "Matched %d jobs for user %s: %d accepted, %d rejected",
        len(decisions), user_id, matched,
        len(decisions) - matched,
    )
    return decisions
