"""
Prefect flow: process a job posting image received via WhatsApp webhook.

Single flow that:
  1. Parses the image via Gemini multimodal (one LLM call for everything)
  2. Inserts ScrapedJob + JobMatch
  3. Renders resume PDF + cover letter
  4. Sends email if proceed=apply_now
  5. Sends WhatsApp notification with result
"""

import json
import logging
import os
import uuid
from datetime import datetime, timezone

from prefect import flow, get_run_logger

from app.config import settings
from app.llm import generate_text, generate_text_with_fallback, generate_text_multimodal
from app.orchestrator import _render_pdf_with_retry, _doc_available
from app.document_generator import ensure_output_dir, cover_letter_to_docx
from app.utils import unique_path
from app.rendercv_renderer import build_yaml_dict
from app.whatsapp_notifier import send_whatsapp
from app.email_sender import send_email
from core.database import (
    get_session,
    ScrapedJob,
    JobMatch,
    save_generated_document,
    save_apply_details,
    update_job_match_status,
    get_application_documents,
    get_recent_matches,
    find_similar_job,
    find_existing_application,
    normalize_job_title,
    check_email_cooldown,
    record_email_sent,
)

logger = logging.getLogger(__name__)

_WHATSAPP_PROMPT = "whatsapp_image_job_v1"
_DEFAULT_USER_ID = "ff0465b9-6512-4f47-8b5e-6f14a343a25d"


@flow(
    name="process-whatsapp-job",
    description="Parse a job posting image, match, generate docs, apply, and notify via WhatsApp.",
    retries=1,
    retry_delay_seconds=30,
    log_prints=True,
)
def process_whatsapp_job(
    image_base64: str,
    mimetype: str = "image/jpeg",
    user_id: str | None = None,
    generate_model: str | None = None,
    generate_provider: str | None = None,
    generate_fallback_model: str | None = None,
    generate_fallback_provider: str | None = None,
):
    """Process a job posting image received via WhatsApp webhook."""
    run_logger = get_run_logger()
    uid = user_id or _DEFAULT_USER_ID
    run_logger.info("Processing WhatsApp job image for user %s ...", uid)

    # 1. Load user profile (pydantic for prompt injection)
    from app.rag import _fetch_profile_with_pydantic

    profile_data = _fetch_profile_with_pydantic(uid)
    if not profile_data or not profile_data.get("profile"):
        run_logger.error("No profile found for user %s — aborting.", uid)
        return {"status": "failed", "error": "no_profile"}

    profile_json = profile_data["profile"].model_dump_json(indent=2)

    # 2. Load prompt text from DB
    from core.database import build_prompt

    system_prompt, _, _ = build_prompt(_WHATSAPP_PROMPT)

    # 3. Call Gemini multimodal with image + profile
    run_logger.info("Calling multimodal LLM with image (%s)...", mimetype)
    try:
        result = generate_text_multimodal(
            system_prompt=system_prompt,
            user_text=f"USER PROFILE:\n{profile_json}",
            image_base64=image_base64,
            mimetype=mimetype,
            model=generate_model,
            provider=generate_provider,
            max_tokens=12000,
            temperature=0.7,
        )
    except Exception as e:
        run_logger.error("Multimodal LLM call failed: %s", e)
        _send_error_whatsapp(uid, "Failed to parse the job posting image. Please try again.")
        return {"status": "failed", "error": str(e)}

    raw = result.get("content", "")
    if not raw or raw == "[MOCK] multimodal output":
        run_logger.warning("LLM returned mock/no content.")
        _send_error_whatsapp(uid, "Failed to process the job image. Please try again.")
        return {"status": "failed", "error": "empty_llm_response"}

    # 4. Strip markdown fences and parse JSON
    parsed = _parse_llm_json(raw, run_logger)
    if parsed is None:
        _send_error_whatsapp(uid, "Failed to understand the job posting. Please try again.")
        return {"status": "failed", "error": "json_parse"}

    job_data = parsed.get("job", {})
    match_data = parsed.get("match", {})
    resume_overrides = parsed.get("resume", {})
    cover_letter_text = parsed.get("cover_letter")
    apply_details = parsed.get("apply_details", {})
    whatsapp_text = parsed.get("whatsapp_text", "")

    if not job_data.get("title") or not job_data.get("company"):
        run_logger.error("LLM output missing required job fields: %s", job_data)
        _send_error_whatsapp(uid, "Could not extract job details from the image. Please ensure the image is clear.")
        return {"status": "failed", "error": "missing_job_fields"}

    # 5. Check for duplicate job (same title + company + location from another site)
    session = get_session()
    try:
        similar = find_similar_job(
            title=job_data.get("title", ""),
            company=job_data.get("company", ""),
            location=job_data.get("location"),
        )
        if similar:
            run_logger.info(
                "WhatsApp job '%s' at '%s' matches existing ScrapedJob #%d from %s — reusing it",
                job_data.get("title"), job_data.get("company"), similar.id, similar.site,
            )
            db_job = similar
            # Re-attach to session so relationship loading works
            session.add(db_job)
            already_matched = session.query(JobMatch).filter(
                JobMatch.job_id == db_job.id,
                JobMatch.user_id == uuid.UUID(uid),
            ).first()
            if already_matched:
                run_logger.info("Job #%d already matched for this user — skipping", db_job.id)
                return {"status": "skipped", "reason": "duplicate_job"}
            match = JobMatch(
                job_id=db_job.id,
                user_id=uuid.UUID(uid) if isinstance(uid, str) else uid,
                status="matched",
                score=match_data.get("score", 50),
                reason=match_data.get("reason"),
                matched_by="llm",
            )
            session.add(match)
        else:
            job_url = f"whatsapp://{uuid.uuid4().hex[:12]}"
            db_job = ScrapedJob(
                site="whatsapp",
                title=job_data.get("title"),
                company=job_data.get("company"),
                job_url=job_url,
                location=job_data.get("location"),
                description=job_data.get("description"),
                job_type=job_data.get("job_type"),
                compensation=job_data.get("compensation"),
                apply_instructions=job_data.get("apply_instructions"),
            )
            session.add(db_job)
            session.flush()

            match = JobMatch(
                job_id=db_job.id,
                user_id=uuid.UUID(uid) if isinstance(uid, str) else uid,
                status="matched",
                score=match_data.get("score", 50),
                reason=match_data.get("reason"),
                matched_by="llm",
            )
            session.add(match)

        # 6. Render resume PDF + save cover letter
        user_data = profile_data  # raw dict from _fetch_profile_with_pydantic
        resume_id = user_data.get("resume", {}).get("id")

        cv_dict = build_yaml_dict(
            user=user_data["user"],
            resume=user_data["resume"],
            experiences=user_data["experiences"],
            education=user_data["education"],
            certifications=user_data["certifications"],
            projects=user_data["projects"],
            skills=user_data["skills"],
            llm_section_overrides=resume_overrides,
            references_full=user_data.get("references_full"),
        )
        pdf_path = _render_pdf_with_retry(cv_dict, job_data.get("title", "job"), db_job.id)

        if pdf_path:
            save_generated_document(
                session,
                resume_id=resume_id,
                job_id=db_job.id,
                document_type="resume",
                rendercv_yaml=json.dumps(cv_dict, indent=2),
                content=raw,
                pdf_path=pdf_path,
                prompt_name=_WHATSAPP_PROMPT,
                model=result.get("model"),
                tokens_used=result.get("tokens_used", 0),
            )
            run_logger.info("Resume PDF saved: %s", pdf_path)

        if cover_letter_text:
            output_dir = ensure_output_dir("cover_letters")
            user_name = f"{user_data['user'].get('first_name', '')} {user_data['user'].get('last_name', '')}".strip()
            job_title = job_data.get("title", "")
            cl_basename = f"{user_name} Cover Letter - {job_title}" if job_title else f"{user_name} Cover Letter"
            docx_path = unique_path(output_dir, cl_basename, ".docx")
            cover_letter_to_docx(cover_letter_text, docx_path)
            save_generated_document(
                session,
                resume_id=resume_id,
                job_id=db_job.id,
                document_type="cover_letter",
                content=cover_letter_text,
                docx_path=docx_path,
                prompt_name=_WHATSAPP_PROMPT,
                model=result.get("model"),
                tokens_used=result.get("tokens_used", 0),
            )
            run_logger.info("Cover letter saved: %s", docx_path)

        # Update match status to generated
        match.status = "generated"
        session.commit()
        run_logger.info("Inserted ScrapedJob #%d + JobMatch for %s at %s",
                        db_job.id, job_data.get("title"), job_data.get("company"))
    except Exception as e:
        session.rollback()
        run_logger.error("DB/render step failed: %s", e)
        _send_error_whatsapp(uid, "Error while processing job application. Please try again.")
        return {"status": "failed", "error": str(e)}
    finally:
        session.close()

    # 7. Save apply_details + reason to JobMatch
    save_apply_details(
        job_id=db_job.id,
        user_id=uid,
        apply_action=apply_details.get("action"),
        apply_recipient=apply_details.get("recipient"),
        apply_subject=apply_details.get("subject"),
        apply_body=apply_details.get("body"),
        apply_url=apply_details.get("url"),
        required_docs=apply_details.get("required_docs"),
        reason=match_data.get("reason"),
        proceed=apply_details.get("proceed"),
        expiry_date=apply_details.get("expiry_date"),
        merged_pdf=apply_details.get("merged_pdf"),
    )

    # 8. Send email if applicable
    proceed = apply_details.get("proceed", "apply_now")
    action = apply_details.get("action", "unknown")
    email_sent = False

    # Dedup: skip if already applied to same (recipient, normalized title)
    recip = apply_details.get("recipient")
    existing_app = find_existing_application(
        user_id=uid,
        recipient=recip or "",
        title=job_data.get("title", ""),
        exclude_job_id=db_job.id,
    ) if recip else None
    if existing_app:
        run_logger.info(
            "Dedup: WhatsApp job '%s' at '%s' → already applied to '%s' (existing JobMatch #%d). Marking duplicate.",
            job_data.get("title"), job_data.get("company"), recip, existing_app.job_id,
        )
        proceed = "skip_dedup"

    docs = get_application_documents(str(resume_id), db_job.id) if resume_id else {}
    req_docs = apply_details.get("required_docs", ["resume"])
    missing_docs = [d for d in req_docs if not _doc_available(d, docs)]

    # ── Cooldown check: never email same recipient within 7 days ──
    _cooldown_until = None
    if action == "email" and recip and not existing_app:
        cooldown_record = check_email_cooldown(recip, uid)
        if cooldown_record:
            now = datetime.now(timezone.utc)
            if cooldown_record.cooldown_until > now:
                run_logger.info(
                    "Cooldown active for %s — skipping email for WhatsApp job #%d (cooldown until %s)",
                    recip, db_job.id, cooldown_record.cooldown_until,
                )
                _cooldown_until = cooldown_record.cooldown_until.isoformat()
            else:
                cooldown_expired = cooldown_record.cooldown_until
                job_scraped = db_job.scraped_at
                if job_scraped and job_scraped <= cooldown_expired:
                    run_logger.info(
                        "Cooldown expired for %s but WhatsApp job #%d was scraped during cooldown (%s) — discarding",
                        recip, db_job.id, job_scraped,
                    )
                    _cooldown_until = "expired_discard"

    if action == "email" and recip and not existing_app and not _cooldown_until and proceed == "apply_now" and not missing_docs:
        subject = apply_details.get("subject") or f"Application: {job_data.get('title')}"
        body = apply_details.get("body") or ""

        # Generate merged PDF if employer wants a single file
        merged_pdf_path = None
        if apply_details.get("merged_pdf"):
            try:
                from app.document_generator import build_merged_pdf
                merged_pdf_path = build_merged_pdf(
                    required_docs=req_docs,
                    docs=docs,
                    job_id=db_job.id,
                )
            except Exception as e:
                run_logger.warning("Failed to build merged PDF: %s", e)

        attachment_paths = _build_attachment_list(req_docs, docs, merged_pdf_path)
        email_sent = send_email(
            to=recip,
            subject=subject,
            body=body,
            attachments=attachment_paths or None,
        )
        run_logger.info("Email %s to %s", "sent" if email_sent else "FAILED", recip)
        if email_sent:
            record_email_sent(recip, uid, db_job.id)
    elif _cooldown_until:
        run_logger.info("Email skipped for WhatsApp job #%d due to cooldown on %s", db_job.id, recip)

    # Send document via WhatsApp when action is external_url
    if action == "external_url":
        try:
            merged_pdf_path = None
            if apply_details.get("merged_pdf"):
                try:
                    from app.document_generator import build_merged_pdf
                    merged_pdf_path = build_merged_pdf(
                        required_docs=req_docs,
                        docs=docs,
                        job_id=db_job.id,
                    )
                except Exception as e:
                    run_logger.warning("Failed to build merged PDF: %s", e)
            if merged_pdf_path:
                from app.whatsapp_notifier import send_whatsapp_document
                url = apply_details.get("url", "external link")
                caption = f"Your application documents for {job_data.get('title')} at {job_data.get('company')} - apply at: {url}  🆔 Job #{db_job.id}"
                doc_sent = send_whatsapp_document(
                    file_path=merged_pdf_path,
                    caption=caption,
                )
                if doc_sent:
                    run_logger.info("WhatsApp document sent for WhatsApp job #%d (external_url).", db_job.id)
        except Exception as e:
            run_logger.warning("Failed to send WhatsApp document for external_url: %s", e)

    # 9. Send WhatsApp notification (text is pre-composed by LLM)
    if whatsapp_text:
        if _cooldown_until and _cooldown_until != "expired_discard":
            cooldown_date = _cooldown_until[:10]
            whatsapp_text += (
                f"\n\nNote: Email to {recip} was not sent — "
                f"a recent application was already made to this employer "
                f"(cooldown until {cooldown_date})."
            )
        elif _cooldown_until == "expired_discard":
            whatsapp_text += (
                f"\n\nNote: Email to {recip} was not sent — "
                f"this job posting was scraped during a past cooldown period "
                f"for this employer and has been discarded."
            )
        send_whatsapp(
            text=f"{whatsapp_text}\n\n🆔 Job #{db_job.id}",
            score=match_data.get("score"),
        )

    # 10. Update status
    if proceed == "skip_dedup":
        new_status = "duplicate"
    elif proceed != "apply_now" or action in ("unknown", "external_url"):
        new_status = "waiting"
    else:
        new_status = "applied"
    update_job_match_status(db_job.id, uid, new_status)

    run_logger.info("WhatsApp job complete — #%d %s status=%s email=%s",
                    db_job.id, job_data.get("title"), new_status, email_sent)
    return {
        "status": "completed",
        "job_id": db_job.id,
        "title": job_data.get("title"),
        "company": job_data.get("company"),
        "email_sent": email_sent,
        "proceed": proceed,
    }


# ── Helpers ────────────────────────────────────────────────────────────

def _parse_llm_json(raw: str, logger=None) -> dict | None:
    """Strip markdown fences and parse LLM JSON response. Returns None on failure."""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        first_newline = cleaned.find("\n")
        if first_newline != -1:
            cleaned = cleaned[first_newline + 1:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3].strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        if logger:
            logger.error("Failed to parse LLM JSON: %s\nRaw: %s", e, cleaned[:500])
        return None


def _format_matches_for_llm(matches: list[dict]) -> str:
    """Format recent match results as a readable text table for the LLM."""
    if not matches:
        return "No job match data found."
    header = f"{'Job #':<8} {'Site':<12} {'Company':<20} {'Title':<30} {'Score':<6} {'Status':<12} {'Proceed':<10} {'URL'}"
    sep = "-" * len(header)
    lines = [header, sep]
    for m in matches:
        url = m.get("job_url") or m.get("apply_instructions") or ""
        lines.append(
            f"{m.get('job_id', ''):<8} "
            f"{m.get('site', ''):<12} "
            f"{str(m.get('company', ''))[:18]:<20} "
            f"{str(m.get('title', ''))[:28]:<30} "
            f"{m.get('score', ''):<6} "
            f"{m.get('status', ''):<12} "
            f"{m.get('proceed', ''):<10} "
            f"{url}"
        )
    return "\n".join(lines)


def _build_job_pipeline_from_llm(
    parsed: dict,
    profile_data: dict,
    uid: str,
    run_logger,
    llm_raw: str = "",
    llm_model: str = "unknown",
    tokens_used: int = 0,
    prompt_name: str = "whatsapp_text_job_v1",
) -> dict:
    """
    Shared job pipeline logic for text and image flows.
    Takes parsed LLM output, runs dedup, render, email, and WhatsApp notification.
    Returns result dict with status.
    """
    job_data = parsed.get("job", {})
    match_data = parsed.get("match", {})
    resume_overrides = parsed.get("resume", {})
    cover_letter_text = parsed.get("cover_letter")
    apply_details = parsed.get("apply_details", {})
    whatsapp_text = parsed.get("whatsapp_text", "")

    if not job_data.get("title") or not job_data.get("company"):
        run_logger.error("LLM output missing required job fields: %s", job_data)
        return {"status": "failed", "error": "missing_job_fields"}

    session = get_session()
    try:
        similar = find_similar_job(
            title=job_data.get("title", ""),
            company=job_data.get("company", ""),
            location=job_data.get("location"),
        )
        if similar:
            run_logger.info(
                "Job '%s' at '%s' matches existing ScrapedJob #%d from %s — reusing it",
                job_data.get("title"), job_data.get("company"), similar.id, similar.site,
            )
            db_job = similar
            session.add(db_job)
            already_matched = session.query(JobMatch).filter(
                JobMatch.job_id == db_job.id,
                JobMatch.user_id == uuid.UUID(uid),
            ).first()
            if already_matched:
                run_logger.info("Job #%d already matched for this user — skipping", db_job.id)
                return {"status": "skipped", "reason": "duplicate_job"}
            match = JobMatch(
                job_id=db_job.id,
                user_id=uuid.UUID(uid) if isinstance(uid, str) else uid,
                status="matched",
                score=match_data.get("score", 50),
                reason=match_data.get("reason"),
                matched_by="llm",
            )
            session.add(match)
        else:
            job_url = f"whatsapp://{uuid.uuid4().hex[:12]}"
            db_job = ScrapedJob(
                site="whatsapp",
                title=job_data.get("title"),
                company=job_data.get("company"),
                job_url=job_url,
                location=job_data.get("location"),
                description=job_data.get("description"),
                job_type=job_data.get("job_type"),
                compensation=job_data.get("compensation"),
                apply_instructions=job_data.get("apply_instructions"),
            )
            session.add(db_job)
            session.flush()

            match = JobMatch(
                job_id=db_job.id,
                user_id=uuid.UUID(uid) if isinstance(uid, str) else uid,
                status="matched",
                score=match_data.get("score", 50),
                reason=match_data.get("reason"),
                matched_by="llm",
            )
            session.add(match)

        # Render resume PDF + save cover letter
        user_data = profile_data
        resume_id = user_data.get("resume", {}).get("id")

        cv_dict = build_yaml_dict(
            user=user_data["user"],
            resume=user_data["resume"],
            experiences=user_data["experiences"],
            education=user_data["education"],
            certifications=user_data["certifications"],
            projects=user_data["projects"],
            skills=user_data["skills"],
            llm_section_overrides=resume_overrides,
            references_full=user_data.get("references_full"),
        )
        pdf_path = _render_pdf_with_retry(cv_dict, job_data.get("title", "job"), db_job.id)

        if pdf_path:
            save_generated_document(
                session,
                resume_id=resume_id,
                job_id=db_job.id,
                document_type="resume",
                rendercv_yaml=json.dumps(cv_dict, indent=2),
                content=llm_raw,
                pdf_path=pdf_path,
                prompt_name=prompt_name,
                model=llm_model,
                tokens_used=tokens_used,
            )

        if cover_letter_text:
            output_dir = ensure_output_dir("cover_letters")
            user_name = f"{user_data['user'].get('first_name', '')} {user_data['user'].get('last_name', '')}".strip()
            job_title = job_data.get("title", "")
            cl_basename = f"{user_name} Cover Letter - {job_title}" if job_title else f"{user_name} Cover Letter"
            docx_path = unique_path(output_dir, cl_basename, ".docx")
            cover_letter_to_docx(cover_letter_text, docx_path)
            save_generated_document(
                session,
                resume_id=resume_id,
                job_id=db_job.id,
                document_type="cover_letter",
                content=cover_letter_text,
                docx_path=docx_path,
                prompt_name=prompt_name,
                model=llm_model,
                tokens_used=tokens_used,
            )

        match.status = "generated"
        session.commit()
        run_logger.info("Inserted ScrapedJob #%d + JobMatch for %s at %s",
                        db_job.id, job_data.get("title"), job_data.get("company"))
    except Exception as e:
        session.rollback()
        run_logger.error("DB/render step failed: %s", e)
        return {"status": "failed", "error": str(e)}
    finally:
        session.close()

    # Save apply_details
    save_apply_details(
        job_id=db_job.id,
        user_id=uid,
        apply_action=apply_details.get("action"),
        apply_recipient=apply_details.get("recipient"),
        apply_subject=apply_details.get("subject"),
        apply_body=apply_details.get("body"),
        apply_url=apply_details.get("url"),
        required_docs=apply_details.get("required_docs"),
        reason=match_data.get("reason"),
        proceed=apply_details.get("proceed"),
        expiry_date=apply_details.get("expiry_date"),
        merged_pdf=apply_details.get("merged_pdf"),
    )

    # Email + cooldown + whatsapp notification (same as image flow)
    proceed = apply_details.get("proceed", "apply_now")
    action = apply_details.get("action", "unknown")
    email_sent = False

    recip = apply_details.get("recipient")
    existing_app = find_existing_application(
        user_id=uid,
        recipient=recip or "",
        title=job_data.get("title", ""),
        exclude_job_id=db_job.id,
    ) if recip else None
    if existing_app:
        run_logger.info(
            "Dedup: already applied to '%s' (existing JobMatch #%d). Marking duplicate.",
            recip, existing_app.job_id,
        )
        proceed = "skip_dedup"

    docs = get_application_documents(str(resume_id), db_job.id) if resume_id else {}
    req_docs = apply_details.get("required_docs", ["resume"])
    missing_docs = [d for d in req_docs if not _doc_available(d, docs)]

    _cooldown_until = None
    if action == "email" and recip and not existing_app:
        cooldown_record = check_email_cooldown(recip, uid)
        if cooldown_record:
            now = datetime.now(timezone.utc)
            if cooldown_record.cooldown_until > now:
                run_logger.info("Cooldown active for %s — skipping email", recip)
                _cooldown_until = cooldown_record.cooldown_until.isoformat()
            else:
                cooldown_expired = cooldown_record.cooldown_until
                job_scraped = db_job.scraped_at
                if job_scraped and job_scraped <= cooldown_expired:
                    _cooldown_until = "expired_discard"

    if action == "email" and recip and not existing_app and not _cooldown_until and proceed == "apply_now" and not missing_docs:
        subject = apply_details.get("subject") or f"Application: {job_data.get('title')}"
        body = apply_details.get("body") or ""
        merged_pdf_path = None
        if apply_details.get("merged_pdf"):
            try:
                from app.document_generator import build_merged_pdf
                merged_pdf_path = build_merged_pdf(required_docs=req_docs, docs=docs, job_id=db_job.id)
            except Exception as e:
                run_logger.warning("Failed to build merged PDF: %s", e)
        attachment_paths = _build_attachment_list(req_docs, docs, merged_pdf_path)
        email_sent = send_email(to=recip, subject=subject, body=body, attachments=attachment_paths or None)
        if email_sent:
            record_email_sent(recip, uid, db_job.id)

    if action == "external_url":
        try:
            merged_pdf_path = None
            if apply_details.get("merged_pdf"):
                try:
                    from app.document_generator import build_merged_pdf
                    merged_pdf_path = build_merged_pdf(required_docs=req_docs, docs=docs, job_id=db_job.id)
                except Exception as e:
                    run_logger.warning("Failed to build merged PDF: %s", e)
            if merged_pdf_path:
                from app.whatsapp_notifier import send_whatsapp_document
                url = apply_details.get("url", "external link")
                caption = f"Your application documents for {job_data.get('title')} at {job_data.get('company')} - apply at: {url}  🆔 Job #{db_job.id}"
                send_whatsapp_document(file_path=merged_pdf_path, caption=caption)
        except Exception as e:
            run_logger.warning("Failed to send WhatsApp document for external_url: %s", e)

    if whatsapp_text:
        if _cooldown_until and _cooldown_until != "expired_discard":
            whatsapp_text += f"\n\nNote: Email to {recip} was not sent — cooldown until {_cooldown_until[:10]}."
        elif _cooldown_until == "expired_discard":
            whatsapp_text += "\n\nNote: This job posting was scraped during a past cooldown period and has been discarded."
        send_whatsapp(text=f"{whatsapp_text}\n\n🆔 Job #{db_job.id}", score=match_data.get("score"))

    if proceed == "skip_dedup":
        new_status = "duplicate"
    elif proceed != "apply_now" or action in ("unknown", "external_url"):
        new_status = "waiting"
    else:
        new_status = "applied"
    update_job_match_status(db_job.id, uid, new_status)

    return {
        "status": "completed",
        "job_id": db_job.id,
        "title": job_data.get("title"),
        "company": job_data.get("company"),
        "email_sent": email_sent,
        "proceed": proceed,
    }


@flow(
    name="process-whatsapp-text",
    description="Process WhatsApp text: route (job posting or data query), then execute.",
    retries=1,
    retry_delay_seconds=30,
    log_prints=True,
)
def process_whatsapp_text(
    text: str,
    user_id: str | None = None,
    generate_model: str | None = None,
    generate_provider: str | None = None,
    generate_fallback_model: str | None = None,
    generate_fallback_provider: str | None = None,
):
    """Process text received via WhatsApp — either a job posting or a data query."""
    run_logger = get_run_logger()
    uid = user_id or _DEFAULT_USER_ID
    run_logger.info("Processing WhatsApp text for user %s ...", uid)

    # 1. Route the intent — question mark = data query/greeting, else = job posting
    intent = "data_query" if text.strip().endswith("?") else "job_posting"
    run_logger.info("Classified intent: %s (rule: ends_with_question_mark)", intent)

    # 2. Handle data query / greeting
    if intent == "data_query":
        try:
            matches = get_recent_matches(uid, limit=20)
            formatted = _format_matches_for_llm(matches)
            result = generate_text_with_fallback(
                prompt_name="whatsapp_data_query_v1",
                user_question=text,
                query_results=formatted,
            )
            reply = result.get("content", "I could not find an answer based on your data.")
            send_whatsapp(text=reply.strip())
            run_logger.info("Data query answered and sent to user.")
            return {"status": "completed", "intent": "data_query"}
        except Exception as e:
            run_logger.error("Data query failed: %s", e)
            _send_error_whatsapp(uid, "Failed to retrieve your data. Please try again.")
            return {"status": "failed", "error": str(e)}

    # 3. Handle job posting
    from app.rag import _fetch_profile_with_pydantic

    profile_data = _fetch_profile_with_pydantic(uid)
    if not profile_data or not profile_data.get("profile"):
        run_logger.error("No profile found for user %s — aborting.", uid)
        _send_error_whatsapp(uid, "No profile found. Please set up your profile first.")
        return {"status": "failed", "error": "no_profile"}

    profile_json = profile_data["profile"].model_dump_json(indent=2)

    try:
        result = generate_text_with_fallback(
            prompt_name="whatsapp_text_job_v1",
            model=generate_model,
            provider=generate_provider,
            fallback_model=generate_fallback_model,
            fallback_provider=generate_fallback_provider,
            user_profile=profile_json,
            job_text=text,
        )
        raw = result.get("content", "")
    except Exception as e:
        run_logger.error("LLM call for job text failed: %s", e)
        _send_error_whatsapp(uid, "Failed to process the job posting. Please try again.")
        return {"status": "failed", "error": str(e)}

    if not raw or raw.startswith("[MOCK]"):
        run_logger.warning("LLM returned mock/no content for job text.")
        _send_error_whatsapp(uid, "Failed to process the job posting. Please try again.")
        return {"status": "failed", "error": "empty_llm_response"}

    parsed = _parse_llm_json(raw, run_logger)
    if parsed is None:
        _send_error_whatsapp(uid, "Failed to understand the job posting. Please try again.")
        return {"status": "failed", "error": "json_parse"}

    pipeline_result = _build_job_pipeline_from_llm(
        parsed, profile_data, uid, run_logger,
        llm_raw=raw,
        llm_model=result.get("model"),
        tokens_used=result.get("tokens_used", 0),
        prompt_name="whatsapp_text_job_v1",
    )
    if pipeline_result.get("status") in ("failed", "skipped"):
        err_msg = pipeline_result.get("error") or pipeline_result.get("reason", "unknown")
        if pipeline_result.get("status") == "failed":
            _send_error_whatsapp(uid, "Error while processing the job. Please try again.")
        return pipeline_result

    run_logger.info("WhatsApp text job complete — #%d %s", pipeline_result.get("job_id"), pipeline_result.get("title"))
    return pipeline_result


def _build_attachment_list(
    required_docs: list[str],
    docs: dict,
    merged_pdf_path: str | None = None,
) -> list[str]:
    """Build attachment file path list from required docs.

    If merged_pdf_path is provided, returns a single-element list with it.
    """
    if merged_pdf_path and os.path.isfile(merged_pdf_path):
        return [merged_pdf_path]

    paths = []
    if "resume" in required_docs and docs.get("resume_pdf"):
        paths.append(docs["resume_pdf"])
    if "cover_letter" in required_docs and docs.get("cover_letter_docx"):
        paths.append(docs["cover_letter_docx"])
    if "education_cert" in required_docs:
        paths.extend(docs.get("education_docs", []))
    if "certification_cert" in required_docs:
        paths.extend(docs.get("certification_docs", []))
    misc = docs.get("misc_docs", {})
    for doc_type in required_docs:
        if doc_type in misc:
            paths.append(misc[doc_type])
    return paths


def _send_error_whatsapp(uid: str, message: str):
    """Send a failure notification to the user."""
    try:
        send_whatsapp(text=f"⚠️ {message}")
    except Exception as e:
        logger.error("Failed to send error WhatsApp: %s", e)
