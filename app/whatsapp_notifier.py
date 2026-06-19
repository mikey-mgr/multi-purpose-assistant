"""
WhatsApp notifier via local API.
Sends a text message to a configured number via a local HTTP endpoint.
"""

import logging

import requests

logger = logging.getLogger(__name__)

_WHATSAPP_URL = "http://localhost:8080/message/sendText/Apex_Web_Services"
_WHATSAPP_API_KEY = "ApexWebServiceSecretKey2026"
_WHATSAPP_NUMBER = "263788667111@s.whatsapp.net"


def send_whatsapp(text: str) -> bool:
    """
    Send a WhatsApp message to the configured number.

    Parameters
    ----------
    text : str
        Message body to send.

    Returns
    -------
    bool — True if sent successfully, False otherwise.
    """
    if not text:
        logger.warning("WhatsApp message text is empty — skipping.")
        return False

    payload = {
        "number": _WHATSAPP_NUMBER,
        "text": text,
    }
    headers = {
        "apikey": _WHATSAPP_API_KEY,
        "Content-Type": "application/json",
    }

    try:
        resp = requests.post(_WHATSAPP_URL, json=payload, headers=headers, timeout=15)
        resp.raise_for_status()
        logger.info("WhatsApp notification sent (status=%s)", resp.status_code)
        return True
    except requests.RequestException as e:
        logger.error("WhatsApp API error: %s", e)
        return False
