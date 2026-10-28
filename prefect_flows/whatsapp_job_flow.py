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
from app.llm import generate_text, generate_text_with_fallback, generate_text_multimodal_with_fallback
from app.orchestrator import _render_pdf_with_retry, _doc_available
from app.document_generator import ensure_output_dir, cover_letter_to_docx
from app.utils import unique_path
from app.rendercv_renderer import build_yaml_dict
from app.whatsapp_notifier import send_whatsapp
from app.email_sender import send_application_email
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
)

logger = logging.getLogger(__name__)

_WHATSAPP_PROMPT = "whatsapp_image_job_v1"
_DEFAULT_USER_ID = "ff0465b9-6512-4f47-8b5e-6f14a343a25d"


def _resolve_prep_job_id(text: str, user_id: str, run_logger=None) -> int | None:
    """Resolve job_id for interview prep from WhatsApp text.

    Priority:
      1. Explicit id: #43, job 43, prep 43, or bare number after prep
      2. Direct DB lookup — verify job_id exists for this user (any age)
      3. Company/title substring in extended pool (last 3 weeks)
      4. Most recent matched job (fallback)
    """
    import re

    log = run_logger or logger

    # 1. Explicit ID — try all patterns, validate via DB before returning
    candidates: list[int] = []
    for pat in [r"#\s*(\d+)", r"\bjob\s+#?\s*(\d+)\b", r"\bprep\D*(\d+)\b", r"\bprepare\D*(\d+)\b"]:
        m = re.search(pat, text.lower())
        if m:
            try:
                candidates.append(int(m.group(1)))
            except ValueError:
                pass
    # Also bare trailing number for "prep 43" style
    if not candidates:
        m = re.search(r"\b(\d{1,6})\b", text.strip())
        # only treat bare number as job_id if text is short and contains prep
        if m and any(k in text.lower() for k in ("prep", "prepare")):
            try:
                candidates.append(int(m.group(1)))
            except ValueError:
                pass

    # Validate each candidate directly against DB (any age, not just recent 20)
    for job_id in candidates:
        try:
            session = get_session()
            try:
                uid = __import__("uuid").UUID(user_id) if isinstance(user_id, str) else user_id
                exists = session.query(JobMatch).filter(JobMatch.job_id == job_id, JobMatch.user_id == uid).first()
                if exists:
                    log.info("Prep job_id resolved via direct DB hit: %s", job_id)
                    return job_id
                # Also allow if ScrapedJob exists even without match (e.g. whatsapp job not yet matched)
                job = session.query(ScrapedJob).filter(ScrapedJob.id == job_id).first()
                if job:
                    log.info("Prep job_id resolved via ScrapedJob direct hit: %s", job_id)
                    return job_id
                log.warning("Prep candidate job_id %s not found for user — trying next", job_id)
            finally:
                session.close()
        except Exception as e:
            log.warning("DB check failed for candidate %s: %s", job_id, e)

    # 2. Company/title substring — use extended pool (last 3 weeks, not just 20)
    try:
        recent = get_recent_matches(user_id, limit=50)
        # If still not enough and user has older jobs, fallback to time-filtered query
        if len(recent) < 50:
            try:
                from datetime import datetime, timedelta, timezone
                from core.database import get_session as _gs
                cutoff = datetime.now(timezone.utc) - timedelta(days=21)
                session = _gs()
                try:
                    uid = __import__("uuid").UUID(user_id) if isinstance(user_id, str) else user_id
                    rows = (
                        session.query(
                            ScrapedJob.id.label("job_id"),
                            ScrapedJob.company,
                            ScrapedJob.title,
                        )
                        .join(JobMatch, ScrapedJob.id == JobMatch.job_id)
                        .filter(JobMatch.user_id == uid, JobMatch.status != "rejected", ScrapedJob.scraped_at >= cutoff)
                        .order_by(ScrapedJob.id.desc())
                        .limit(100)
                        .all()
                    )
                    # Merge any not already in recent
                    seen = {r.get("job_id") for r in recent}
                    for row in rows:
                        if row.job_id not in seen:
                            recent.append({"job_id": row.job_id, "company": row.company, "title": row.title})
                finally:
                    session.close()
            except Exception as e:
                log.warning("Extended pool fetch failed: %s", e)

        lower = text.lower()
        for r in recent:
            company = (r.get("company") or "").lower()
            title = (r.get("title") or r.get("job_title") or "").lower()
            if company and len(company) > 2 and company in lower:
                jid = r.get("job_id") or r.get("id")
                if jid:
                    log.info("Prep job_id resolved via company match '%s' -> %s", company, jid)
                    return int(jid)
            if title and len(title) > 4 and title in lower:
                jid = r.get("job_id") or r.get("id")
                if jid:
                    log.info("Prep job_id resolved via title match '%s' -> %s", title, jid)
                    return int(jid)
        # 3. Fallback to most recent
        if recent:
            jid = recent[0].get("job_id") or recent[0].get("id")
            if jid:
                log.info("Prep job_id fallback to most recent: %s", jid)
                return int(jid)
    except Exception as e:
        log.warning("Failed to resolve prep job_id via recent matches: %s", e)

    return None


def _get_relevant_matches_for_query(user_id: str, query_text: str, run_logger=None, limit: int = 10) -> list[dict]:
    """Hybrid semantic + keyword retrieval for data_query — avoids overloading prompt.

    Tries embedding + search_jobs_hybrid filtered to user's matched jobs.
    Falls back to get_recent_matches on any failure.
    Keeps prompt lean: 8-10 most relevant rows instead of blind 20.
    """
    log = run_logger or logger
    try:
        from app.llm import generate_embedding
        from core.database import search_jobs_hybrid

        embedding = None
        try:
            embedding = generate_embedding(query_text)
        except Exception as e:
            log.warning("Embedding failed for data_query, falling back to keyword: %s", e)

        # Greeting shortcut — no need for semantic search
        if query_text.strip().lower() in ("hi", "hello", "hey", "hi there", "hello there"):
            raise ValueError("greeting — use recent")

        hybrid = search_jobs_hybrid(query_text=query_text, embedding_vector=embedding, top_k=20)
        if not hybrid:
            raise ValueError("hybrid returned no results")

        # Intersect hybrid job ids with user's matches
        hybrid_ids = [job.id for job, _ in hybrid]
        session = get_session()
        try:
            uid = __import__("uuid").UUID(user_id) if isinstance(user_id, str) else user_id
            rows = (
                session.query(
                    ScrapedJob.site,
                    ScrapedJob.id.label("job_id"),
                    ScrapedJob.company,
                    ScrapedJob.title,
                    __import__("sqlalchemy", fromlist=["func"]).func.left(ScrapedJob.description, 50).label("description"),
                    JobMatch.status,
                    JobMatch.score,
                    JobMatch.reason,
                    JobMatch.proceed,
                    ScrapedJob.scraped_at,
                    JobMatch.required_docs,
                    JobMatch.apply_recipient,
                    JobMatch.expiry_date,
                    ScrapedJob.location,
                    ScrapedJob.job_url,
                    ScrapedJob.apply_instructions,
                )
                .join(JobMatch, ScrapedJob.id == JobMatch.job_id)
                .filter(JobMatch.user_id == uid, JobMatch.status != "rejected", ScrapedJob.id.in_(hybrid_ids))
                .all()
            )
            if rows:
                columns = ["site","job_id","company","title","description","status","score","reason","proceed","scraped_at","required_docs","apply_recipient","expiry_date","location","job_url","apply_instructions"]
                # Preserve hybrid ranking order
                order = {jid: i for i, jid in enumerate(hybrid_ids)}
                dicts = [dict(zip(columns, r)) for r in rows]
                dicts.sort(key=lambda d: order.get(d["job_id"], 999))
                log.info("Hybrid data_query: %d relevant matches (from %d hybrid)", len(dicts), len(hybrid))
                return dicts[:limit]
            raise ValueError("no intersection with user matches")
        finally:
            session.close()
    except Exception as e:
        log.info("Falling back to time-filtered matches for data_query: %s", e)
        # Fallback: last 3 weeks (21 days) — not "all time", keeps prompt lean
        try:
            from datetime import datetime, timedelta, timezone
            cutoff = datetime.now(timezone.utc) - timedelta(days=21)
            session = get_session()
            try:
                uid = __import__("uuid").UUID(user_id) if isinstance(user_id, str) else user_id
                rows = (
                    session.query(
                        ScrapedJob.site,
                        ScrapedJob.id.label("job_id"),
                        ScrapedJob.company,
                        ScrapedJob.title,
                        __import__("sqlalchemy", fromlist=["func"]).func.left(ScrapedJob.description, 50).label("description"),
                        JobMatch.status,
                        JobMatch.score,
                        JobMatch.reason,
                        JobMatch.proceed,
                        ScrapedJob.scraped_at,
                        JobMatch.required_docs,
                        JobMatch.apply_recipient,
                        JobMatch.expiry_date,
                        ScrapedJob.location,
                        ScrapedJob.job_url,
                        ScrapedJob.apply_instructions,
                    )
                    .join(JobMatch, ScrapedJob.id == JobMatch.job_id)
                    .filter(JobMatch.user_id == uid, JobMatch.status != "rejected", ScrapedJob.scraped_at >= cutoff)
                    .order_by(ScrapedJob.id.desc())
                    .limit(50)
                    .all()
                )
                if rows:
                    columns = ["site","job_id","company","title","description","status","score","reason","proceed","scraped_at","required_docs","apply_recipient","expiry_date","location","job_url","apply_instructions"]
                    dicts = [dict(zip(columns, r)) for r in rows]
                    log.info("Fallback to last 3 weeks: %d matches", len(dicts))
                    return dicts[:limit]
            finally:
                session.close()
        except Exception as fe:
            log.warning("3-week fallback failed: %s", fe)
        return get_recent_matches(user_id, limit=limit)


def _classify_intent(text: str, run_logger=None) -> str:
    """Classify WhatsApp text intent via LLM router with rule fallback.

    Calls whatsapp_text_router_v1 (3 intents). On any failure or low confidence,
    falls back to cheap rules: prep keywords -> interview_prep, ? -> data_query, else job_posting.
    No user details are dumped to the router — only user_message.
    """
    log = run_logger or logger
    # Try LLM router
    try:
        result = generate_text_with_fallback(
            prompt_name="whatsapp_text_router_v1",
            model="models/gemini-3.5-flash-lite",
            provider="gemini",
            fallback_model="gemma-4-e2b-it",
            fallback_provider="local",
            user_message=text,
        )
        raw = (result.get("content") or "").strip()
        # Tolerant JSON parse (handle fences)
        if "```" in raw:
            try:
                raw = raw.split("```")[1].split("```")[0].strip()
                if raw.startswith("json"):
                    raw = raw[4:].strip()
            except Exception:
                pass
        parsed = json.loads(raw)
        intent = (parsed.get("intent") or "").strip().lower()
        conf = parsed.get("confidence", 0)
        if intent in ("job_posting", "data_query", "interview_prep"):
            log.info("LLM router classified intent=%s confidence=%s", intent, conf)
            # Low-confidence interview_prep with no prep keywords -> fallback to rule
            if intent == "interview_prep" and conf < 60:
                lower = text.lower()
                if not any(k in lower for k in ("prep", "prepare", "interview")):
                    log.info("LLM low-confidence interview_prep (%s) without prep keywords — falling back to data_query/job_posting", conf)
                else:
                    return intent
            else:
                return intent
        log.warning("LLM router returned unknown intent '%s' — falling back to rules", intent)
    except Exception as e:
        log.warning("LLM router failed (%s) — falling back to rules", e)

    # Rule fallback (cheap, no LLM)
    lower = text.strip().lower()
    is_prep = any(k in lower for k in ("interview prep", "interview preparation", " prep ", " prep#", "prep #"))
    if lower.startswith("prep") or lower.startswith("prepare"):
        is_prep = True
    if is_prep:
        log.info("Rule fallback classified intent=interview_prep")
        return "interview_prep"
    if text.strip().endswith("?"):
        log.info("Rule fallback classified intent=data_query")
        return "data_query"
    log.info("Rule fallback classified intent=job_posting")
    return "job_posting"


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

    # 3. Call multimodal LLM with image + profile (local GPU primary, Gemini fallback)
    run_logger.info("Calling multimodal LLM with image (%s)...", mimetype)
    try:
        result = generate_text_multimodal_with_fallback(
            system_prompt=system_prompt,
            user_text=f"USER PROFILE:\n{profile_json}",
            image_base64=image_base64,
            mimetype=mimetype,
            model=generate_model or "models/gemini-3.5-flash-lite",
            provider=generate_provider or "gemini",
            fallback_model=generate_fallback_model or "gemma-4-e2b-it",
            fallback_provider=generate_fallback_provider or "local",
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
        email_sent = send_application_email(
            to=recip,
            subject=subject,
            body=body,
            user_id=uid,
            job_id=db_job.id,
            attachments=attachment_paths or None,
        )
        run_logger.info("Email %s to %s", "sent" if email_sent else "FAILED", recip)
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
        email_sent = send_application_email(
            to=recip,
            subject=subject,
            body=body,
            user_id=uid,
            job_id=db_job.id,
            attachments=attachment_paths or None,
        )

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

    # 1. Route the intent via LLM router (whatsapp_text_router_v1) with rule fallback
    intent = _classify_intent(text, run_logger)
    run_logger.info("Classified intent: %s", intent)

    # 1b. Handle interview prep (on-demand, company-only MVP)
    if intent == "interview_prep":
        try:
            job_id = _resolve_prep_job_id(text, uid, run_logger)
            if not job_id:
                _send_error_whatsapp(uid, "I couldn't find which job you mean. Try: prep #<job id>  e.g. prep #1818")
                return {"status": "failed", "error": "no_job_id", "intent": "interview_prep"}
            from app.interview_prep import generate_interview_prep
            result = generate_interview_prep(
                user_id=uid,
                job_id=job_id,
                model=generate_model or "models/gemini-3.5-flash-lite",
                provider=generate_provider or "gemini",
                fallback_model=generate_fallback_model or "gemma-4-e2b-it",
                fallback_provider=generate_fallback_provider or "local",
            )
            whatsapp_text = result.get("whatsapp_text", "") or f"Prep ready for {result.get('company','')} — Job #{job_id}"
            docx_path = result.get("docx_path")
            # Send summary text
            send_whatsapp(text=f"{whatsapp_text}\n\n🆔 Job #{job_id}")
            # Send doc if available
            if docx_path:
                try:
                    from app.whatsapp_notifier import send_whatsapp_document
                    send_whatsapp_document(
                        file_path=docx_path,
                        caption=f"Interview Prep — {result.get('job_title','')} at {result.get('company','')} — Job #{job_id}",
                    )
                except Exception as e:
                    run_logger.warning("Failed to send prep doc for job %s: %s", job_id, e)
            run_logger.info("Interview prep completed for job %s", job_id)
            return {"status": "completed", "intent": "interview_prep", "job_id": job_id, "doc_id": result.get("doc_id")}
        except Exception as e:
            run_logger.error("Interview prep failed: %s", e)
            _send_error_whatsapp(uid, "Failed to generate interview prep. Please try again.")
            return {"status": "failed", "error": str(e), "intent": "interview_prep"}

    # 2. Handle data query / greeting (hybrid retrieval — lean prompt)
    if intent == "data_query":
        try:
            matches = _get_relevant_matches_for_query(uid, text, run_logger, limit=10)
            formatted = _format_matches_for_llm(matches)
            result = generate_text_with_fallback(
                prompt_name="whatsapp_data_query_v1",
                model="models/gemini-3.5-flash-lite",
                provider="gemini",
                fallback_model="gemma-4-e2b-it",
                fallback_provider="local",
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
