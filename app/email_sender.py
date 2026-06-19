"""
Email sender via Gmail SMTP.
Uses GMAIL_ADDRESS + GMAIL_APP_PASSWORD from config / Prefect blocks.
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

    msg = MIMEMultipart()
    msg["From"] = from_addr
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

    for filepath in (attachments or []):
        if not filepath or not os.path.isfile(filepath):
            logger.warning("Attachment not found, skipping: %s", filepath)
            continue
        try:
            with open(filepath, "rb") as f:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header(
                "Content-Disposition",
                f'attachment; filename="{os.path.basename(filepath)}"',
            )
            msg.attach(part)
        except OSError as e:
            logger.warning("Failed to attach %s: %s", filepath, e)

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
