"""
Core orchestration logic — called by Prefect flows (or CLI / API).

Pipeline:
  1. Fetch an unprocessed job posting
  2. Assemble the user's profile (RAG) — raw data from normalized tables
  3. Call LLM to rewrite per-section content for ATS fit
  4. Build RenderCV YAML from DB data + LLM overrides
  5. Render PDF via rendercv, save DOCX for cover letter
  6. Snapshot everything in generated_documents table
"""

import json
import logging

from core.database import (
    get_session,
    ScrapedJob,
    GeneratedDocument,
    save_generated_document,
)
from app.schemas import GeneratedDocument as GDocSchema
from app.llm import generate_text
from app.rag import (
    assemble_user_profile,
    find_relevant_jobs,
    _fetch_profile_with_pydantic,
)
from app.rendercv_renderer import build_yaml_dict, render as rendercv_render
from app.document_generator import ensure_output_dir, cover_letter_to_docx
from app.utils import unique_path

logger = logging.getLogger(__name__)


def process_job_for_user(
    user_id: str,
    job_id: int | None = None,
    resume_id: str | None = None,
    model: str | None = None,
    provider: str | None = None,
) -> list[GDocSchema]:
    """
    Full pipeline for one user + one job.
    Returns list of GDocSchema describing what was generated.
    """
    session = get_session()
    results: list[GDocSchema] = []

    try:
        # ── 1. Load raw profile data ────────────────────────────────
        logger.info("Loading profile for user %s ...", user_id)
        profile_data = _fetch_profile_with_pydantic(user_id, resume_id)
        profile = profile_data["profile"]
        profile_str = profile.model_dump_json(indent=2)

        # ── 2. Load job description ─────────────────────────────────
        job_desc_str = _load_job_description(job_id, profile)

        # ── 3. Generate ATS-optimised resume ────────────────────────
        logger.info("Generating ATS resume sections ...")
        resume_result = generate_text(
            "ats_resume_v1",
            model=model,
            provider=provider,
            user_profile=profile_str,
            job_description=job_desc_str,
        )


        llm_raw = resume_result.get("content", "")
        llm_overrides = _parse_llm_output(llm_raw)

        user_name = f"{profile_data['user'].get('first_name', '')} {profile_data['user'].get('last_name', '')}".strip()
        job_title = _fetch_job_title(job_id) or ""

        # ── 4. Build RenderCV YAML ──────────────────────────────────
        cv_dict = build_yaml_dict(
            user=profile_data["user"],
            resume=profile_data["resume"],
            experiences=profile_data["experiences"],
            education=profile_data["education"],
            certifications=profile_data["certifications"],
            projects=profile_data["projects"],
            skills=profile_data["skills"],
            llm_section_overrides=llm_overrides,
        )
        cv_yaml_str = json.dumps(cv_dict, indent=2)

        # ── 5. Render PDF ───────────────────────────────────────────
        pdf_path = rendercv_render(cv_dict, job_title=job_title)
        if not pdf_path:
            logger.warning("PDF was NOT generated for job %s — resume snapshot saved without file.", job_id)

        # ── 6. Snapshot resume in DB ────────────────────────────────
        resume_doc = save_generated_document(
            session,
            resume_id=profile_data["resume"]["id"],
            job_id=job_id,
            document_type="resume",
            rendercv_yaml=cv_yaml_str,
            content=llm_raw,
            pdf_path=pdf_path or None,
            prompt_name="ats_resume_v1",
            model=resume_result.get("model", ""),
            tokens_used=resume_result.get("tokens_used", 0),
        )
        session.commit()
        results.append(GDocSchema(
            job_id=job_id,
            prompt_name="ats_resume_v1",
            document_type="resume",
            content=llm_raw,
            model=resume_result.get("model", ""),
            tokens_used=resume_result.get("tokens_used", 0),
        ))
        logger.info("Resume snapshot saved (id=%s, pdf=%s)", resume_doc.id, pdf_path or "(none)")

        # ── 7. Generate cover letter ────────────────────────────────
        logger.info("Generating cover letter ...")
        cl_result = generate_text(
            "cover_letter_v1",
            model=model,
            provider=provider,
            user_profile=profile_str,
            job_description=job_desc_str,
        )
        out_dir = ensure_output_dir("cover_letters")
        cl_basename = f"{user_name} Cover Letter - {job_title}" if job_title else f"{user_name} Cover Letter"
        docx_path = unique_path(out_dir, cl_basename, ".docx")
        cover_letter_to_docx(cl_result["content"], docx_path)

        cl_doc = save_generated_document(
            session,
            resume_id=profile_data["resume"]["id"],
            job_id=job_id,
            document_type="cover_letter",
            content=cl_result["content"],
            docx_path=docx_path,
            prompt_name="cover_letter_v1",
            model=cl_result.get("model", ""),
            tokens_used=cl_result.get("tokens_used", 0),
        )
        session.commit()
        results.append(GDocSchema(
            job_id=job_id,
            prompt_name="cover_letter_v1",
            document_type="cover_letter",
            content=cl_result["content"],
            model=cl_result.get("model", ""),
            tokens_used=cl_result.get("tokens_used", 0),
        ))
        logger.info("Cover letter snapshot saved (id=%s, docx=%s)", cl_doc.id, docx_path)

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    logger.info("Pipeline complete — %d document(s).", len(results))
    return results


def _fetch_job_title(job_id: int | None) -> str | None:
    """Fetch the title of a job from the DB."""
    if not job_id:
        return None
    session = get_session()
    try:
        job = session.query(ScrapedJob).filter(ScrapedJob.id == job_id).first()
        return job.title if job else None
    finally:
        session.close()


def _load_job_description(job_id: int | None, profile) -> str:
    if job_id:
        session = get_session()
        try:
            job = session.query(ScrapedJob).filter(ScrapedJob.id == job_id).first()
        finally:
            session.close()
        if job:
            return json.dumps({
                "title": job.title,
                "company": job.company,
                "description": job.description,
                "location": job.location,
                "job_type": job.job_type,
            }, indent=2)
    matches = find_relevant_jobs(profile.professional_summary or "")
    return json.dumps([m.model_dump() for m in matches], indent=2) if matches else "{}"


def _parse_llm_output(raw: str) -> dict:
    """
    Try to parse the LLM output as JSON.
    If it fails, return an empty dict (proceed with unmodified DB data).
    Expected keys: summary, skills, experience_highlights, project_highlights.
    """
    # Try extracting a JSON block from markdown fences
    if "```json" in raw:
        raw = raw.split("```json")[1].split("```")[0].strip()
    elif "```" in raw:
        raw = raw.split("```")[1].split("```")[0].strip()

    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    except (json.JSONDecodeError, IndexError):
        logger.warning("LLM output not valid JSON — using DB data as-is")
    return {}
