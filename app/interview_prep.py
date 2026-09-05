"""
Interview prep generation — MVP (company-only research).

Flow:
  1. Load user profile + job posting
  2. Research company via SerpAPI (graceful skip if missing)
  3. Single LLM call (interview_prep_v1) with fallback
  4. Parse output, build markdown guide
  5. Render PDF/DOCX via document_generator helpers
  6. Snapshot to generated_documents (document_type='interview_prep')
"""

import json
import logging
import os

from core.database import get_session, ScrapedJob, save_generated_document, Resume
from app.config import settings
from app.company_research import research_company
from app.llm import generate_text_with_fallback
from app.document_generator import ensure_output_dir, cover_letter_to_docx
from app.utils import unique_path

logger = logging.getLogger(__name__)


def _parse_interview_prep(raw: str) -> dict | None:
    """Parse interview_prep JSON — tolerant of markdown fences."""
    if "```json" in raw:
        raw = raw.split("```json")[1].split("```")[0].strip()
    elif "```" in raw:
        raw = raw.split("```")[1].split("```")[0].strip()
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict) and "prep_guide" in parsed:
            return parsed
    except (json.JSONDecodeError, IndexError):
        pass
    return None


def _build_prep_markdown(parsed: dict, job_title: str, company: str) -> str:
    """Combine parsed fields into a single markdown document."""
    import re
    # Sanitize title parts — strip stray markdown artifacts like "~~ 0" from scraped data
    def _clean(s: str) -> str:
        s = (s or "").strip()
        # Remove trailing strikethrough artifacts e.g. " ~~ 0", "~~", " ~0"
        s = re.sub(r"\s*~~.*$", "", s).strip()
        s = re.sub(r"\s+~+\s*\d*\s*$", "", s).strip()
        return s
    job_title = _clean(job_title)
    company = _clean(company)

    parts: list[str] = []
    title = f"# Interview Prep — {job_title} at {company}" if company else f"# Interview Prep — {job_title}"
    parts.append(title)
    parts.append("")

    if parsed.get("company_insights"):
        parts.append("## Company Insights")
        parts.append(parsed["company_insights"].strip())
        parts.append("")

    if parsed.get("prep_guide"):
        parts.append("## Preparation Guide")
        parts.append(parsed["prep_guide"].strip())
        parts.append("")

    questions = parsed.get("questions") or []
    if questions:
        parts.append("## Likely Questions & Tailored Answers")
        for i, q in enumerate(questions, 1):
            if isinstance(q, dict):
                question = q.get("question", "")
                answer = q.get("answer", "")
                why = q.get("why_asked", "")
                parts.append(f"### {i}. {question}")
                if why:
                    parts.append(f"*Why asked:* {why}")
                if answer:
                    parts.append(f"\n{answer}")
            else:
                parts.append(f"### {i}. {q}")
            parts.append("")

    if parsed.get("cheat_sheet"):
        parts.append("## Cheat Sheet")
        parts.append(parsed["cheat_sheet"].strip())
        parts.append("")

    if parsed.get("questions_to_ask"):
        qta = parsed["questions_to_ask"]
        if isinstance(qta, list):
            parts.append("## Questions to Ask the Interviewer")
            for q in qta:
                parts.append(f"- {q}")
            parts.append("")
        elif isinstance(qta, str) and qta.strip():
            parts.append("## Questions to Ask the Interviewer")
            parts.append(qta.strip())
            parts.append("")

    return "\n".join(parts).strip()


def _save_prep_with_retry(markdown: str, user_name: str, job_title: str) -> tuple[str | None, str | None]:
    """Save prep markdown as DOCX and PDF (via DOCX->PDF if needed). Returns (docx_path, pdf_path)."""
    out_dir = ensure_output_dir("interview_prep")
    basename = f"{user_name} Interview Prep - {job_title}" if job_title else f"{user_name} Interview Prep"
    docx_path = unique_path(out_dir, basename, ".docx")
    # Use cover_letter_to_docx helper — it handles paragraph splitting
    try:
        cover_letter_to_docx(markdown, docx_path)
        if os.path.exists(docx_path):
            # Also try PDF via same helper path if available, else keep docx only
            # Reuse DOCX as primary; PDF optional
            pdf_path = docx_path.replace(".docx", ".pdf")
            # Simple: keep docx, don't block on PDF
            return docx_path, None
    except Exception as e:
        logger.warning("Failed to save interview prep docx: %s", e)
    return None, None


def generate_interview_prep(
    user_id: str,
    job_id: int,
    model: str = "models/gemini-3.5-flash-lite",
    provider: str = "gemini",
    fallback_model: str = "gemma-4-e2b-it",
    fallback_provider: str = "local",
) -> dict:
    """
    Generate interview prep for a user + job.

    Returns dict with keys: job_id, company, prep_markdown, parsed, doc_id, pdf_path, model
    """
    from app.rag import _fetch_profile_with_pydantic

    session = get_session()
    try:
        # 1. Load profile
        logger.info("Loading profile for interview prep user %s ...", user_id)
        profile_data = _fetch_profile_with_pydantic(user_id)
        profile = profile_data["profile"]
        profile_str = profile.model_dump_json(indent=2)
        user_name = f"{profile_data['user'].get('first_name','')} {profile_data['user'].get('last_name','')}".strip() or "Candidate"

        # 2. Load job
        job = session.query(ScrapedJob).filter(ScrapedJob.id == job_id).first()
        if not job:
            raise ValueError(f"Job {job_id} not found")
        job_title = job.title or ""
        company = (job.company or "").strip()
        job_desc_str = json.dumps({
            "title": job.title,
            "company": job.company,
            "description": job.description,
            "location": job.location,
            "job_type": job.job_type,
            "apply_instructions": job.apply_instructions,
        }, indent=2)

        # Need resume_id for FK (optional but preferred)
        resume_row = session.query(Resume).filter(Resume.user_id == user_id, Resume.is_active == True).first()
        resume_id = str(resume_row.id) if resume_row else None
    finally:
        session.close()

    # 3. Company research (outside DB session)
    company_research = research_company(company)
    logger.info("Company research for '%s': %d chars", company, len(company_research))

    # 4. LLM call
    result = generate_text_with_fallback(
        prompt_name="interview_prep_v1",
        model=model,
        provider=provider,
        fallback_model=fallback_model,
        fallback_provider=fallback_provider,
        user_profile=profile_str,
        job_description=job_desc_str,
        company_research=company_research,
    )
    raw = result.get("content", "")
    model_used = result.get("model", model)
    parsed = _parse_interview_prep(raw)
    if not parsed:
        logger.warning("Interview prep LLM output failed to parse — saving raw.")
        parsed = {"prep_guide": raw, "questions": [], "company_insights": "", "whatsapp_text": raw[:800]}

    prep_markdown = _build_prep_markdown(parsed, job_title, company)
    whatsapp_text = (parsed.get("whatsapp_text") or prep_markdown[:1000]).strip()

    # 5. Save doc files
    docx_path, pdf_path = _save_prep_with_retry(prep_markdown, user_name, job_title)

    # 6. Snapshot to generated_documents
    session = get_session()
    try:
        doc = save_generated_document(
            session,
            resume_id=resume_id,
            job_id=job_id,
            document_type="interview_prep",
            content=prep_markdown,
            pdf_path=pdf_path,
            docx_path=docx_path,
            prompt_name="interview_prep_v1",
            model=model_used,
            tokens_used=result.get("tokens_used", 0),
        )
        session.commit()
        logger.info("Interview prep saved id=%s job=%s company=%s", doc.id, job_id, company)
        return {
            "job_id": job_id,
            "company": company,
            "job_title": job_title,
            "prep_markdown": prep_markdown,
            "whatsapp_text": whatsapp_text,
            "parsed": parsed,
            "doc_id": str(doc.id),
            "docx_path": docx_path,
            "pdf_path": pdf_path,
            "model": model_used,
        }
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
