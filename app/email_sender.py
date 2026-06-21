"""
Email sender via Gmail SMTP.
"""

import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

from app.config import settings

logger = logging.getLogger(__name__)

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _resolve_path(path: str) -> str:
    """Resolve relative paths to project-root-absolute."""
    if not os.path.isabs(path):
        return os.path.join(_PROJECT_ROOT, path)
    return path


def send_email(
    to: str,
    subject: str,
    body: str,
    attachments: list[str] | None = None,
) -> bool:
    """
    Send an email via Gmail SMTP with optional file attachments.

    Parameters
    ----------
    to : str
        Recipient email address.
    subject : str
        Email subject line.
    body : str
        Email body text (plain text).
    attachments : list[str] | None
        List of absolute file paths to attach.

    Returns
    -------
    bool — True if sent successfully, False otherwise.
    """
    from_addr = settings.GMAIL_ADDRESS
    password = settings.GMAIL_APP_PASSWORD

    if not from_addr or not password:
        logger.error("Gmail credentials not configured (GMAIL_ADDRESS / GMAIL_APP_PASSWORD).")
        return False

    logger.info("Sending email to %s (attachments=%d)", to, len(attachments or []))

    msg = MIMEMultipart()
    msg["From"] = from_addr
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

    for filepath in (attachments or []):
        resolved = _resolve_path(filepath) if filepath else ""
        if not resolved or not os.path.isfile(resolved):
            logger.warning("Attachment not found, skipping: %s (resolved=%s)", filepath, resolved)
            continue
        try:
            with open(resolved, "rb") as f:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header(
                "Content-Disposition",
                "attachment",
                filename=("utf-8", "en", os.path.basename(resolved)),
            )
            msg.attach(part)
        except OSError as e:
            logger.warning("Failed to attach %s: %s", resolved, e)

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(from_addr, password)
        server.send_message(msg)
        server.quit()
        logger.info("Email sent to %s — subject: %s", to, subject)
        return True
    except smtplib.SMTPAuthenticationError:
        logger.error("Gmail authentication failed — check GMAIL_ADDRESS / GMAIL_APP_PASSWORD.")
        return False
    except smtplib.SMTPException as e:
        logger.error("SMTP error sending to %s: %s", to, e)
        return False
