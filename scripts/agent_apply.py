"""Poll the Mukana server for apply tasks and run the local apply flow for one profile."""

import argparse
import base64
import json
import logging
import os
import smtplib
import time
from email.message import EmailMessage
from email.utils import make_msgid
from pathlib import Path

from scripts.agent_common import DEFAULT_SERVER, AgentClient, load_agent_config, run_agent

logger = logging.getLogger("mukana.agent.apply")

SENT_LEDGER = Path(
    os.getenv("MUKANA_SENT_LEDGER", str(Path.home() / ".mukana" / "sent.json"))
)


def load_ledger() -> dict:
    if not SENT_LEDGER.exists():
        return {}
    try:
        return json.loads(SENT_LEDGER.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def record_sent(kit_id: str, entry: dict) -> None:
    ledger = load_ledger()
    ledger[kit_id] = entry
    SENT_LEDGER.parent.mkdir(parents=True, exist_ok=True)
    SENT_LEDGER.write_text(json.dumps(ledger, indent=2), encoding="utf-8")


def send_kit_application(config: dict, payload: dict) -> dict:
    kit_id = payload.get("kit_id")
    match_id = payload.get("match_id")
    legacy_user_id = payload.get("legacy_user_id")
    if not kit_id or not match_id or not legacy_user_id:
        raise ValueError("Kit task is missing kit_id, match_id or legacy_user_id")

    address = config.get("gmail_address") or os.getenv("GMAIL_ADDRESS")
    password = config.get("gmail_app_password") or os.getenv("GMAIL_APP_PASSWORD")
    if not address or not password:
        raise RuntimeError("Gmail credentials are not configured")

    client = AgentClient(
        config.get("server_url", DEFAULT_SERVER),
        config["agent_id"],
        config["agent_key"],
    )
    try:
        recorded = load_ledger().get(kit_id)
        if recorded:
            logger.info("Kit %s was already sent; marking the match applied", kit_id)
            client.mark_application_sent(
                kit_id,
                {
                    "legacy_user_id": legacy_user_id,
                    "match_id": match_id,
                    "sent": True,
                    "message_id": recorded.get("message_id"),
                },
            )
            return {"sent": True, "already_sent": True, "match_id": match_id}

        kit = client.application_kit(kit_id, legacy_user_id)
        attachments = kit.get("attachments") or []
        test_recipient = (payload.get("test_recipient") or "").strip() or None
        to_address = test_recipient or kit["recipient"]
        message = EmailMessage()
        message["From"] = address
        message["To"] = to_address
        message["Subject"] = f"[TEST] {kit['subject']}" if test_recipient else kit["subject"]
        message["Message-ID"] = make_msgid(domain=address.split("@")[-1])
        message.set_content(kit["body"])

        for attachment in attachments:
            maintype, subtype = attachment["mime"].split("/", 1)
            message.add_attachment(
                base64.b64decode(attachment["contentBase64"]),
                maintype=maintype,
                subtype=subtype,
                filename=attachment["name"],
            )

        if payload.get("dry_run"):
            logger.info(
                "Dry run: would send kit %s for '%s' to %s with %d attachment(s)",
                kit_id,
                kit.get("jobTitle"),
                kit["recipient"],
                len(attachments),
            )
            return {
                "sent": False,
                "dry_run": True,
                "match_id": match_id,
                "recipient": kit["recipient"],
                "subject": kit["subject"],
                "attachments": [item["name"] for item in attachments],
            }

        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=60) as smtp:
            smtp.login(address, password)
            smtp.send_message(message)

        if test_recipient:
            logger.info("Test email sent to %s for kit %s", to_address, kit_id)
            return {
                "sent": True,
                "test": True,
                "match_id": match_id,
                "recipient": to_address,
                "subject": message["Subject"],
                "attachments": [item["name"] for item in attachments],
            }

        entry = {
            "sent_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "recipient": kit["recipient"],
            "message_id": message["Message-ID"],
        }
        record_sent(kit_id, entry)

        last_error: Exception | None = None
        for attempt in range(3):
            try:
                client.mark_application_sent(
                    kit_id,
                    {
                        "legacy_user_id": legacy_user_id,
                        "match_id": match_id,
                        "sent": True,
                        "message_id": message["Message-ID"],
                    },
                )
                last_error = None
                break
            except Exception as exc:
                last_error = exc
                time.sleep(2 + attempt * 2)
        if last_error:
            raise last_error

        logger.info("Sent '%s' to %s", kit.get("jobTitle"), kit["recipient"])
        return {
            "sent": True,
            "match_id": match_id,
            "recipient": kit["recipient"],
            "subject": kit["subject"],
            "attachments": [item["name"] for item in attachments],
        }
    finally:
        client.close()


def handle_apply(payload: dict) -> dict:
    config = load_agent_config()
    for config_key, env_key in (
        ("db_conn_uri", "DB_CONN_URI"),
        ("gmail_address", "GMAIL_ADDRESS"),
        ("gmail_app_password", "GMAIL_APP_PASSWORD"),
        ("gemini_api_key", "GEMINI_API_KEY"),
        ("evolution_api_url", "EVOLUTION_API_URL"),
        ("whatsapp_api_key", "WHATSAPP_API_KEY"),
        ("whatsapp_number", "WHATSAPP_NUMBER"),
    ):
        if config.get(config_key) and not os.getenv(env_key):
            os.environ[env_key] = str(config[config_key])
    if config.get("db_conn_uri"):
        os.environ.setdefault("SKIP_PREFECT_BLOCKS", "1")

    legacy_user_id = payload.get("legacy_user_id")
    limit = int(payload.get("limit") or 10)
    dry_run = bool(payload.get("dry_run"))

    if not legacy_user_id:
        raise ValueError("Task is missing legacy_user_id")

    allowed_user = config.get("apply_user_id") or os.getenv("AGENT_APPLY_USER_ID")
    if allowed_user and str(allowed_user) != legacy_user_id:
        raise ValueError("This agent is not allowed to apply for that profile")

    if payload.get("kit_id"):
        return send_kit_application(config, payload)

    if dry_run:
        logger.info("Dry run for user %s; no emails will be sent", legacy_user_id)
        return {"processed": 0, "dry_run": True}

    from app.orchestrator import batch_process_applications

    logger.info("Running local apply flow for %s (limit=%d)", legacy_user_id, limit)
    results = batch_process_applications(user_id=legacy_user_id, limit=limit)
    if isinstance(results, list):
        sample = results[:5]
        processed = len(results)
    else:
        sample = results
        processed = 1 if results else 0

    return {
        "processed": processed,
        "sample": json.loads(json.dumps(sample, default=str)),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Mukana local apply agent")
    parser.add_argument("--once", action="store_true", help="Process one task and exit")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    run_agent("apply", handle_apply, once=args.once)


if __name__ == "__main__":
    main()
