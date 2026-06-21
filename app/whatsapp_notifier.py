"""
WhatsApp notifier via local API.
Sends a "composing" presence signal, then immediately sends the text message.
"""

import logging
import random

import requests

logger = logging.getLogger(__name__)

_WHATSAPP_URL = "http://localhost:8080/message/sendText/Apex_Web_Services"
_PRESENCE_URL = "http://localhost:8080/chat/sendPresence/Apex_Web_Services"
_WHATSAPP_API_KEY = "ApexWebServiceSecretKey2026"
_WHATSAPP_NUMBER = "263788667111@s.whatsapp.net"


def send_whatsapp(
    text: str,
    fit_assessment: str | None = None,
    score: int | None = None,
    missing_docs: list[str] | None = None,
) -> bool:
    """
    Send a WhatsApp message with fit assessment and missing-docs context.

    1. Generates a random delay between 5-15 seconds (used as presence duration).
    2. Sends a "composing" presence signal for that duration.
    3. Immediately sends the actual message (no idle wait).

    Parameters
    ----------
    text : str
        Main message body.
    fit_assessment : str | None
        "high", "medium", or "low" — how well the user fits the role.
    score : int | None
        Match score from job_matches (0-100).
    missing_docs : list[str] | None
        Document types the job requires but the user doesn't have.

    Returns
    -------
    bool — True if sent successfully, False otherwise.
    """
    if not text:
        logger.warning("WhatsApp message text is empty — skipping.")
        return False

    delay_seconds = random.uniform(5, 15)
    delay_ms = int(delay_seconds * 1000)

    # Build a richer message
    lines = [text]
    if fit_assessment:
        lines.append(f"\nFit: {fit_assessment.upper()}")
    if score is not None:
        lines.append(f"Score: {score}/100")
    if missing_docs:
        lines.append(f"Missing docs: {', '.join(missing_docs)}")
    full_text = "\n".join(lines)

    headers = {
        "apikey": _WHATSAPP_API_KEY,
        "Content-Type": "application/json",
    }

    # Send presence composing signal (sets "typing…" for delay_ms duration)
    presence_payload = {
        "number": _WHATSAPP_NUMBER,
        "presence": "composing",
        "delay": delay_ms,
    }
    try:
        resp = requests.post(_PRESENCE_URL, json=presence_payload, headers=headers, timeout=10)
        resp.raise_for_status()
        logger.info("Presence sent (delay=%dms, status=%s)", delay_ms, resp.status_code)
    except requests.RequestException as e:
        logger.warning("Presence signal failed (continuing): %s", e)

    # Send actual message immediately (presence shows "typing…" while this sends)
    text_payload = {
        "number": _WHATSAPP_NUMBER,
        "text": full_text,
    }
    try:
        resp = requests.post(_WHATSAPP_URL, json=text_payload, headers=headers, timeout=15)
        resp.raise_for_status()
        logger.info("WhatsApp notification sent (status=%s)", resp.status_code)
        return True
    except requests.RequestException as e:
        logger.error("WhatsApp API error: %s", e)
        return False