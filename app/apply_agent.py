"""
WhatsApp notification composer.
Takes stored apply_details + execution results from batch_process_applications
and composes natural WhatsApp messages via a single batch LLM call.
"""

import json
import logging
from app.llm import generate_text

logger = logging.getLogger(__name__)


def _parse_json_response(content: str) -> dict | list | None:
    """Strip fences and parse JSON from LLM output."""
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0].strip()
    elif "```" in content:
        content = content.split("```")[1].split("```")[0].strip()
    try:
        return json.loads(content)
    except (json.JSONDecodeError, IndexError) as e:
        logger.warning("Failed to parse LLM output: %s — raw: %s", e, content[:200])
        return None


def _build_whatsapp_entry(
    job,
    match,
    email_sent: bool,
    missing_docs: list[str],
) -> dict:
    """Build a single notification entry from stored DB data."""
    return {
        "job_title": job.title or "Unknown",
        "company": job.company or "Unknown",
        "match_score": match.score if match else 0,
        "reason": match.reason or "",
        "apply_action": match.apply_action or "unknown",
        "proceed": match.proceed or "apply_now",
        "apply_url": match.apply_url or "",
        "email_sent": email_sent,
        "missing_docs": missing_docs,
    }


def batch_compose_whatsapp(
    jobs_with_matches: list[dict],
    email_sent_map: dict[int, bool],
    results_map: dict[int, dict],
    model: str | None = None,
    provider: str | None = None,
) -> list[str]:
    """
    Compose natural WhatsApp messages for all processed jobs in one LLM call.

    Reads directly from stored DB fields (match.apply_action, match.reason, etc.)
    plus execution results.

    Returns list of notification_text strings in the same order as jobs_with_matches.
    """
    entries = []
    for item in jobs_with_matches:
        job = item["job"]
        match = item["match"]
        email_sent = email_sent_map.get(job.id, False)
        missing_docs = results_map.get(job.id, {}).get("missing_docs", [])
        entries.append(_build_whatsapp_entry(job, match, email_sent, missing_docs))

    batch_input_json = json.dumps(entries, indent=2)
    logger.info("Composing WhatsApp batch notification for %d jobs.", len(entries))
    logger.debug("Batch WhatsApp raw input:\n%s", batch_input_json)

    result = generate_text(
        "whatsapp_notify_batch_v1",
        model=model,
        provider=provider,
        batch_input=batch_input_json,
    )
    content = result.get("content", "").strip()
    parsed = _parse_json_response(content)

    if isinstance(parsed, list):
        return [item.get("notification_text", "") for item in parsed]

    logger.warning("WhatsApp batch LLM did not return an array — fallback to empty.")
    return [""] * len(entries)
