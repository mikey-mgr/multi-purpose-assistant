"""
Core orchestration logic — called by Prefect flows (or CLI / API).

Pipeline:
  1. Fetch an unprocessed job posting
  2. Assemble the user's profile (RAG) — raw data from normalized tables
  3. Single LLM call for both ATS-optimised resume JSON + cover letter
  4. Build RenderCV YAML from DB data + LLM overrides
  5. Render PDF via rendercv with retry, save DOCX for cover letter with retry
  6. Snapshot both in generated_documents table
"""

import json
import logging
import os
import time

from core.database import (
    get_session,
    ScrapedJob,
    JobMatch,
    save_generated_document,
    update_job_match_status,
    get_application_documents,
    get_generated_jobs_with_matches,
    save_apply_details,
    normalize_job_title,
    Resume,
    User,
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
    fallback_model: str | None = None,
    fallback_provider: str | None = None,
) -> list[GDocSchema]:
    """
    Full pipeline for one user + one job.

    Makes a single LLM call that returns both resume JSON and cover letter text,
    then renders both files with retries.

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

        # ── 2. Load job description (includes apply_instructions) ───
        job_desc_str = _load_job_description(job_id, profile)

        # ── 3. Single LLM call — resume + cover letter ──────────────
        combined_result = _generate_combined_with_fallback(
            prompt_name="ats_and_cover_v1",
            variables={
                "user_profile": profile_str,
                "job_description": job_desc_str,
            },
            primary_model=model,
            primary_provider=provider,
            fallback_model=fallback_model,
            fallback_provider=fallback_provider,
            max_attempts=3,
        )
        if combined_result is None:
            logger.error("All attempts failed for job %s — skipping.", job_id)
            return []

        combined, llm_model_used = combined_result
        llm_raw = json.dumps(combined, indent=2)
        resume_overrides = combined.get("resume", {})
        cover_letter_text = combined.get("cover_letter")

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
            llm_section_overrides=resume_overrides,
        )
        cv_yaml_str = json.dumps(cv_dict, indent=2)

        # ── 5. Render PDF with retry ────────────────────────────────
        pdf_path = _render_pdf_with_retry(cv_dict, job_title, job_id)

        # ── 6. Snapshot resume in DB ────────────────────────────────
        resume_doc = save_generated_document(
            session,
            resume_id=profile_data["resume"]["id"],
            job_id=job_id,
            document_type="resume",
            rendercv_yaml=cv_yaml_str,
            content=llm_raw,
            pdf_path=pdf_path or None,
            prompt_name="ats_and_cover_v1",
            model=llm_model_used,
            tokens_used=0,
        )
        session.commit()
        results.append(GDocSchema(
            job_id=job_id,
            prompt_name="ats_and_cover_v1",
            document_type="resume",
            content=llm_raw,
            model=llm_model_used,
            tokens_used=0,
        ))
        logger.info("Resume snapshot saved (id=%s, pdf=%s)", resume_doc.id, pdf_path or "(none)")

        # ── 7. Save cover letter (if generated) ─────────────────────
        if cover_letter_text and cover_letter_text.strip():
            docx_path = _save_cover_letter_with_retry(
                cover_letter_text, user_name, job_title, job_id
            )
            cl_doc = save_generated_document(
                session,
                resume_id=profile_data["resume"]["id"],
                job_id=job_id,
                document_type="cover_letter",
                content=cover_letter_text,
                docx_path=docx_path,
                prompt_name="ats_and_cover_v1",
                model=llm_model_used,
                tokens_used=0,
            )
            session.commit()
            results.append(GDocSchema(
                job_id=job_id,
                prompt_name="ats_and_cover_v1",
                document_type="cover_letter",
                content=cover_letter_text,
                model=llm_model_used,
                tokens_used=0,
            ))
            logger.info("Cover letter snapshot saved (id=%s, docx=%s)", cl_doc.id, docx_path or "(none)")
        else:
            logger.info("Cover letter skipped for job %s (LLM returned null).", job_id)

        # ── 8. Save apply_details + reason to job_matches ─────────────
        apply_details = combined.get("apply_details") or {}
        missing_resources = combined.get("missing_resources") or ""
        if apply_details or missing_resources:
            from core.database import save_apply_details
            save_apply_details(
                job_id=job_id,
                user_id=user_id,
                apply_action=apply_details.get("action"),
                apply_recipient=apply_details.get("recipient"),
                apply_subject=apply_details.get("subject"),
                apply_body=apply_details.get("body"),
                apply_url=apply_details.get("url"),
                required_docs=apply_details.get("required_docs"),
                reason=missing_resources,
                proceed=apply_details.get("proceed"),
                expiry_date=apply_details.get("expiry_date"),
                merged_pdf=apply_details.get("merged_pdf"),
            )
            logger.info("Apply details saved for job %s.", job_id)

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    logger.info("Pipeline complete — %d document(s).", len(results))
    return results


# ── Private helpers ─────────────────────────────────────────────────


def _generate_combined_with_fallback(
    prompt_name: str,
    variables: dict,
    primary_model: str | None,
    primary_provider: str | None,
    fallback_model: str | None,
    fallback_provider: str | None,
    max_attempts: int = 3,
) -> tuple[dict, str] | None:
    """
    Call the LLM for the combined prompt, retrying with fallback on failure.

    Attempt 1 uses primary model/provider.
    Attempts 2+ use fallback model/provider.

    Returns (parsed_json, model_name) or None if all attempts fail.
    """
    last_error = None
    for attempt in range(max_attempts):
        try:
            if attempt % 2 == 0:
                m, p = primary_model, primary_provider
                tag = "primary"
            else:
                m, p = fallback_model, fallback_provider
                tag = f"fallback (attempt {attempt + 1})"

            logger.info(
                "Combined LLM call attempt %d/%d [%s]: model=%s provider=%s",
                attempt + 1, max_attempts, tag, m, p,
            )

            result = generate_text(
                prompt_name,
                model=m,
                provider=p,
                **variables,
            )
            raw = result.get("content", "")
            if not raw:
                logger.warning("Attempt %d returned empty content.", attempt + 1)
                continue

            parsed = _parse_combined_output(raw)
            if parsed and "resume" in parsed:
                return parsed, result.get("model", m or "unknown")

            logger.warning(
                "Attempt %d output not valid combined JSON — will retry.",
                attempt + 1,
            )

        except Exception as e:
            last_error = e
            logger.warning("Attempt %d failed with exception: %s", attempt + 1, e)

        if attempt < max_attempts - 1:
            time.sleep(2)

    logger.error(
        "All %d attempts failed for prompt '%s': %s",
        max_attempts, prompt_name, last_error or "invalid output",
    )
    return None


def _parse_combined_output(raw: str) -> dict | None:
    """Parse the combined resume + cover letter JSON from the LLM."""
    if "```json" in raw:
        raw = raw.split("```json")[1].split("```")[0].strip()
    elif "```" in raw:
        raw = raw.split("```")[1].split("```")[0].strip()
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict) and "resume" in parsed:
            return parsed
    except (json.JSONDecodeError, IndexError):
        pass
    return None


def _render_pdf_with_retry(
    cv_dict: dict, job_title: str, job_id: int, max_attempts: int = 3
) -> str | None:
    """Render PDF via rendercv with retries."""
    for attempt in range(max_attempts):
        pdf_path = rendercv_render(cv_dict, job_title=job_title)
        if pdf_path and os.path.exists(pdf_path):
            return pdf_path
        logger.warning(
            "PDF not generated on attempt %d/%d for job %s",
            attempt + 1, max_attempts, job_id,
        )
        if attempt < max_attempts - 1:
            time.sleep(3)
    return None


def _save_cover_letter_with_retry(
    cover_letter_text: str,
    user_name: str,
    job_title: str,
    job_id: int,
    max_attempts: int = 3,
) -> str | None:
    """Generate DOCX from cover letter text with retries."""
    out_dir = ensure_output_dir("cover_letters")
    cl_basename = f"{user_name} Cover Letter - {job_title}" if job_title else f"{user_name} Cover Letter"
    docx_path = unique_path(out_dir, cl_basename, ".docx")

    for attempt in range(max_attempts):
        try:
            cover_letter_to_docx(cover_letter_text, docx_path)
            if os.path.exists(docx_path):
                return docx_path
        except Exception as e:
            logger.warning(
                "Cover letter DOCX failed on attempt %d/%d for job %s: %s",
                attempt + 1, max_attempts, job_id, e,
            )
        if attempt < max_attempts - 1:
            time.sleep(2)
    return None


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
    """Load job details (including apply_instructions) as a JSON string."""
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
                "apply_instructions": job.apply_instructions,
            }, indent=2)
    matches = find_relevant_jobs(profile.professional_summary or "")
    return json.dumps([m.model_dump() for m in matches], indent=2) if matches else "{}"


def batch_process_applications(
    user_id: str,
    limit: int = 10,
    model: str | None = None,
    provider: str | None = None,
) -> list[dict]:
    """
    Batch-apply for all generated-but-unapplied jobs using stored apply_details.

    1. Loads all generated-but-unapplied jobs with match data + apply_details
    2. Sends emails where stored apply_action = "email" and docs exist
    3. Single LLM call to compose all WhatsApp notifications (reads reason + scores + action)
    4. Sends WhatsApp messages
    5. Updates statuses
    """
    logger.info("Batch-processing applications for user %s (limit=%d)", user_id, limit)

    # 1. Load jobs with match data (includes new apply_* columns via JobMatch)
    jobs_with_matches = get_generated_jobs_with_matches(user_id, limit=limit)
    if not jobs_with_matches:
        logger.info("No generated-but-unapplied jobs found.")
        return []

    # 2. Load resume info for doc lookups
    session = get_session()
    try:
        resume_row = session.query(Resume).filter(
            Resume.user_id == user_id,
            Resume.is_active == True,
        ).first()
        resolve_resume_id = str(resume_row.id) if resume_row else None
    finally:
        session.close()

    if not resolve_resume_id:
        logger.warning("No active resume found for user %s", user_id)
        return []

    results_map: dict[int, dict] = {}
    email_sent_map: dict[int, bool] = {}
    whatsapp_doc_sent_map: dict[int, bool] = {}
    seen_recipient_titles: set[tuple[str, str]] = set()

    for item in jobs_with_matches:
        job = item["job"]
        match = item["match"]

        action = match.apply_action or "unknown"
        proceed = match.proceed or "apply_now"
        recip = match.apply_recipient if action == "email" else None
        subject = match.apply_subject or f"Application: {job.title}"
        body = match.apply_body or f"Please find attached my application for {job.title}."
        required_docs_raw = match.required_docs
        required_docs = json.loads(required_docs_raw) if required_docs_raw else ["resume"]

        # Step 04 dedup: skip email if same (recipient + normalized title) already emailed or in DB
        title_key = normalize_job_title(job.title or "")
        dup_key = (recip or "", title_key)
        if recip and dup_key in seen_recipient_titles:
            logger.info(
                "Dedup: skipping email for job #%d '%s' — already emailed '%s' for same title.",
                job.id, job.title, recip,
            )
            email_sent_map[job.id] = False
            whatsapp_doc_sent_map[job.id] = False
            results_map[job.id] = {"action": action, "missing_docs": []}
            update_job_match_status(job.id, user_id, "duplicate")
            continue

        # Determine missing docs
        docs = get_application_documents(resolve_resume_id, job.id)
        missing_docs = [d for d in required_docs if not _doc_available(d, docs)]
        logger.info(
            "Job #%d: required_docs=%s missing_docs=%s misc_docs_keys=%s",
            job.id, required_docs, missing_docs, list(docs.get("misc_docs", {}).keys()),
        )

        # Generate merged PDF — for email (attach) or external_url (send via WhatsApp)
        merged_pdf_path = None
        if (action == "email" and not missing_docs and proceed == "apply_now") or (action == "external_url" and not missing_docs):
            try:
                from app.document_generator import build_merged_pdf
                merged_pdf_path = build_merged_pdf(
                    required_docs=required_docs,
                    docs=docs,
                    job_id=job.id,
                )
            except Exception as e:
                logger.warning("Failed to build merged PDF for job %s: %s", job.id, e)

        email_sent = False
        # Only send email if: action is email, recipient exists, no missing docs, AND proceed says apply_now
        if action == "email" and recip and not missing_docs and proceed == "apply_now":
            attachment_paths = _build_attachment_list(required_docs, docs, merged_pdf_path)
            from app.email_sender import send_email
            ok = send_email(
                to=recip,
                subject=subject,
                body=body,
                attachments=attachment_paths or None,
            )
            logger.info(
                "Email condition met for job %s — calling send_email(to=%s, attachments=%d)",
                job.id, recip, len(attachment_paths or []),
            )
            email_sent = ok
            if not ok:
                logger.warning("Email FAILED for job %s — check email_sender logs above.", job.id)

        # Send document via WhatsApp when action is external_url and docs are available
        whatsapp_doc_sent = False
        if action == "external_url" and not missing_docs and merged_pdf_path:
            from app.whatsapp_notifier import send_whatsapp_document
            caption = f"Your application documents for {job.title} at {job.company} — apply at: {match.apply_url or 'external link'}"
            whatsapp_doc_sent = send_whatsapp_document(
                file_path=merged_pdf_path,
                caption=caption,
            )
            if whatsapp_doc_sent:
                logger.info("WhatsApp document sent for job #%d (external_url).", job.id)
            else:
                logger.warning("WhatsApp document FAILED for job #%d.", job.id)

        email_sent_map[job.id] = email_sent
        whatsapp_doc_sent_map[job.id] = whatsapp_doc_sent
        results_map[job.id] = {
            "action": action,
            "missing_docs": missing_docs,
        }
        seen_recipient_titles.add(dup_key)

    # 4. Single LLM call to compose WhatsApp notifications (reads reason + scores)
    from app.apply_agent import batch_compose_whatsapp
    notification_texts = batch_compose_whatsapp(
        jobs_with_matches,
        email_sent_map,
        results_map,
        user_id=user_id,
        model=model,
        provider=provider,
    )

    # 5. Send WhatsApp and update status
    final_results = []
    for item, note in zip(jobs_with_matches, notification_texts):
        job = item["job"]
        match = item["match"]
        r = results_map[job.id]

        if note:
            from app.whatsapp_notifier import send_whatsapp
            whatsapp_ok = send_whatsapp(
                text=note,
                score=match.score,
                missing_docs=r["missing_docs"],
            )
        else:
            whatsapp_ok = False

        new_status = "waiting" if (match.proceed or "apply_now") != "apply_now" else "applied"
        update_job_match_status(job.id, user_id, new_status)

        final_results.append({
            "job_id": job.id,
            "action": r["action"],
            "email_sent": email_sent_map.get(job.id, False),
            "whatsapp_sent": whatsapp_ok,
            "whatsapp_doc_sent": whatsapp_doc_sent_map.get(job.id, False),
            "missing_docs": r["missing_docs"],
            "status": new_status,
        })

    logger.info("Batch application complete — %d jobs processed.", len(final_results))
    return final_results


# ── Private helpers ────────────────────────────────────────────────


def _doc_available(doc_type: str, docs: dict) -> bool:
    """Check if a document type is available."""
    if doc_type == "resume":
        return bool(docs.get("resume_pdf"))
    if doc_type == "cover_letter":
        return bool(docs.get("cover_letter_docx"))
    if doc_type == "education_cert":
        return bool(docs.get("education_docs"))
    if doc_type == "certification_cert":
        return bool(docs.get("certification_docs"))
    # Misc doc types (id_doc, drivers_license, proof_of_age, etc.) — check by key
    return doc_type in docs.get("misc_docs", {})


def _build_attachment_list(
    required_docs: list[str],
    docs: dict,
    merged_pdf: str | None = None,
) -> list[str]:
    """Build attachment file path list from required docs.

    If merged_pdf is provided, returns a single-element list — the merged
    PDF already contains all required documents in order.
    """
    if merged_pdf and os.path.isfile(merged_pdf):
        return [merged_pdf]

    paths = []
    if "resume" in required_docs and docs.get("resume_pdf"):
        paths.append(docs["resume_pdf"])
    if "cover_letter" in required_docs and docs.get("cover_letter_docx"):
        paths.append(docs["cover_letter_docx"])
    if "education_cert" in required_docs:
        paths.extend(docs.get("education_docs", []))
    if "certification_cert" in required_docs:
        paths.extend(docs.get("certification_docs", []))
    # Misc doc types — map from required_docs values (e.g. "id_doc") to file paths
    misc = docs.get("misc_docs", {})
    for doc_type in required_docs:
        if doc_type in misc:
            paths.append(misc[doc_type])
    return paths
