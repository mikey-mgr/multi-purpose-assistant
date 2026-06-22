"""
WhatsApp notifier via local API.
Sends a "composing" presence signal, then immediately sends the text message.
Also supports sending document files (PDF, DOCX, etc.) via sendMedia endpoint.
"""

import base64
import logging
import os
import random

import requests
from app.config import settings

logger = logging.getLogger(__name__)

_WHATSAPP_URL = "http://localhost:8080/message/sendText/Apex_Web_Services"
_MEDIA_URL = "http://localhost:8080/message/sendMedia/Apex_Web_Services"
_PRESENCE_URL = "http://localhost:8080/chat/sendPresence/Apex_Web_Services"
_WHATSAPP_API_KEY = settings.WHATSAPP_API_KEY
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
    
    if not _WHATSAPP_API_KEY:
        logger.error("Whatsapp API Key not configured (WHATSAPP_API_KEY).")
        return False

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


def send_whatsapp_document(
    file_path: str,
    caption: str = "",
    mimetype: str = "application/pdf",
) -> bool:
    """
    Send a document file via WhatsApp using the Evolution API sendMedia endpoint.

    Parameters
    ----------
    file_path : str
        Path to the file on disk.
    caption : str
        Optional caption text sent with the document.
    mimetype : str
        MIME type of the file (default application/pdf).

    Returns
    -------
    bool — True if sent successfully, False otherwise.
    """
    if not _WHATSAPP_API_KEY:
        logger.error("Whatsapp API Key not configured (WHATSAPP_API_KEY).")
        return False

    if not file_path or not os.path.isfile(file_path):
        logger.warning("WhatsApp document file not found: %s", file_path)
        return False

    try:
        with open(file_path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode("utf-8")
    except OSError as e:
        logger.error("Failed to read document for WhatsApp: %s", e)
        return False

    file_name = os.path.basename(file_path)

    headers = {
        "apikey": _WHATSAPP_API_KEY,
        "Content-Type": "application/json",
    }

    payload = {
        "number": _WHATSAPP_NUMBER,
        "mediatype": "document",
        "mimetype": mimetype,
        "caption": caption,
        "media": encoded,
        "fileName": file_name,
    }

    try:
        resp = requests.post(_MEDIA_URL, json=payload, headers=headers, timeout=60)
        resp.raise_for_status()
        logger.info("WhatsApp document sent: %s (status=%s)", file_name, resp.status_code)
        return True
    except requests.RequestException as e:
        logger.error("WhatsApp document send error: %s", e)
        return False