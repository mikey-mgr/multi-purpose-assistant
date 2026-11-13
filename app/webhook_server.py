"""
FastAPI webhook server for the Evolution WhatsApp API.

Replaces n8n entirely — receives messages directly from Evolution API,
handles text and images, and triggers the appropriate Prefect flow.

Usage: python -m app.webhook_server
"""

import base64
import logging
import os
import secrets
from contextlib import asynccontextmanager
from datetime import datetime

import httpx
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import JSONResponse

from app.config import settings

logger = logging.getLogger(__name__)

_API_KEY_HEADER = "apikey"
_EXPECTED_API_KEY = settings.WHATSAPP_API_KEY
_WEBHOOK_SECRET_HEADER = "x-webhook-secret"
_WEBHOOK_SECRET = settings.WHATSAPP_WEBHOOK_SECRET
_MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MB
_VALID_MIMETYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}

# Comma-separated numbers or prefixes. Empty means deny all inbound messages.
_ALLOWED_NUMBERS = tuple(
    item.strip().lstrip("+")
    for item in settings.WHATSAPP_ALLOWED_NUMBERS.split(",")
    if item.strip()
)

_EVOLUTION_API_URL = settings.EVOLUTION_API_URL
_EVOLUTION_WEBHOOK_URL = settings.EVOLUTION_WEBHOOK_URL
_MATCH_TRIGGER_SECRET = settings.MATCH_TRIGGER_SECRET
_MATCH_TRIGGER_HEADER = "x-match-trigger-secret"

# The web app owns matching, generation and delivery. Parsed WhatsApp jobs are
# posted here instead of being processed by the legacy Prefect flows.
_WEB_INGEST_URL = os.getenv(
    "WEB_INGEST_URL", "https://mukana.mikeyverse.co.zw/api/whatsapp/ingest"
)


async def _register_evolution_webhook() -> bool:
    """Idempotently register this receiver on the configured Evolution instance."""
    if not _EVOLUTION_WEBHOOK_URL or not _EXPECTED_API_KEY or not _WEBHOOK_SECRET:
        logger.error(
            "Evolution webhook registration skipped: URL, API key, or webhook secret is missing"
        )
        return False

    url = f"{_EVOLUTION_API_URL.rstrip('/')}/webhook/set/{settings.EVOLUTION_INSTANCE_NAME}"
    payload = {
        "webhook": {
            "enabled": True,
            "url": _EVOLUTION_WEBHOOK_URL,
            "webhookByEvents": False,
            "webhookBase64": False,
            "events": ["MESSAGES_UPSERT"],
            "headers": {_WEBHOOK_SECRET_HEADER: _WEBHOOK_SECRET},
        }
    }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                url,
                headers={"apikey": _EXPECTED_API_KEY},
                json=payload,
            )
            response.raise_for_status()
        logger.info("Evolution webhook registration verified for %s", settings.EVOLUTION_INSTANCE_NAME)
        return True
    except Exception as exc:
        logger.error("Evolution webhook registration failed: %s", exc)
        return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("WhatsApp webhook server starting ...")
    if os.getenv("SKIP_EVOLUTION_REGISTRATION", "").lower() in {"1", "true", "yes"}:
        app.state.evolution_webhook_configured = False
    else:
        app.state.evolution_webhook_configured = await _register_evolution_webhook()
    yield
    logger.info("WhatsApp webhook server shutting down.")


app = FastAPI(
    title="WhatsApp Job Webhook",
    description="Receives messages from the Evolution API and triggers the application pipeline.",
    version="2.0.0",
    lifespan=lifespan,
)


# ── Helpers ────────────────────────────────────────────────────────────

def _resolve_sender(key: dict) -> tuple[str | None, str]:
    """Return (jid, reason). jid is None when this is not a personal chat.

    WhatsApp now delivers many personal chats as "<id>@lid" and puts the phone
    number in remoteJidAlt. Treating every non-@s.whatsapp.net JID as a group
    dropped real users, while @g.us ids were read as phone numbers.
    """
    remote = (key or {}).get("remoteJid") or ""
    alt = (key or {}).get("remoteJidAlt") or ""

    if not remote and not alt:
        return None, "no_jid"

    for suffix in ("@g.us", "@broadcast", "@newsletter", "@status"):
        if remote.endswith(suffix):
            return None, "group"

    if remote.endswith("@s.whatsapp.net") or remote.endswith("@c.us"):
        return remote, "ok"
    if alt.endswith("@s.whatsapp.net") or alt.endswith("@c.us"):
        # A linked-device chat: remoteJidAlt carries the real phone number.
        return alt, "ok"
    if remote.endswith("@lid"):
        # Pure LID with no phone alternative; we cannot match it to an account.
        return None, "lid_only"

    return None, "unsupported_jid"


def _jid_to_phone(jid: str) -> str:
    """Produce the 2637... canonical form used by the pilot table."""
    digits = "".join(ch for ch in jid.split("@")[0] if ch.isdigit())
    return f"263{digits[1:]}" if digits.startswith("0") else digits


def _is_allowed_number(phone_number: str) -> bool:
    """Check if a normalized phone number matches the configured allowlist."""
    normalized = phone_number.strip().lstrip("+")
    return any(normalized.startswith(item) for item in _ALLOWED_NUMBERS)


def _is_authenticated(request: Request) -> bool:
    """Validate Evolution's shared webhook secret without timing leaks."""
    supplied = request.headers.get(_WEBHOOK_SECRET_HEADER, "")
    return bool(_WEBHOOK_SECRET) and secrets.compare_digest(supplied, _WEBHOOK_SECRET)


async def _fetch_image_base64(instance_id: str, msg_id: str) -> dict | None:
    """Call Evolution API's getBase64FromMediaMessage to get image data."""
    url = f"{_EVOLUTION_API_URL}/chat/getBase64FromMediaMessage/{instance_id}"
    headers = {"Content-Type": "application/json", "apikey": _EXPECTED_API_KEY}
    payload = {"message": {"key": {"id": msg_id}}}
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        logger.error("Failed to fetch image base64 from Evolution API: %s", e)
        return None


# ── Evolution API Webhook (replaces n8n entirely) ──────────────────────

@app.post("/api/webhooks/evolution")
async def evolution_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Receive messages directly from the Evolution API.

    Configure your Evolution API instance to send webhooks to:
    http://<your-host>:8055/api/webhooks/evolution
    """
    if not _is_authenticated(request):
        return JSONResponse(status_code=401, content={"error": "Invalid or missing webhook secret"})

    try:
        payload = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "Invalid JSON body"})

    if payload.get("event") != "messages.upsert":
        return JSONResponse(status_code=200, content={"status": "ignored"})

    data = payload.get("data", {})
    key = data.get("key", {})
    remote_jid = key.get("remoteJid", "")
    from_me = key.get("fromMe", False)
    instance_id = payload.get("instance", data.get("instanceId", ""))
    msg_id = key.get("id", "")
    message = data.get("message", {})
    message_type = data.get("messageType", "")

    # Filter: drop own messages
    if from_me:
        logger.info("Skipping own message (fromMe=true)")
        return JSONResponse(status_code=200, content={"status": "filtered_own"})

    # Resolve who actually wrote to us. Personal chats may arrive as "@lid" with
    # the phone number in remoteJidAlt; groups are never users.
    sender_jid, reason = _resolve_sender(key)
    if not sender_jid:
        logger.info("Skipping message (%s): remoteJid=%s", reason, remote_jid)
        return JSONResponse(status_code=200, content={"status": f"filtered_{reason}"})

    remote_jid = sender_jid
    phone_number = _jid_to_phone(sender_jid)
    if not _is_allowed_number(phone_number):
        logger.info("Skipping message from non-pilot number: %s", phone_number)
        return JSONResponse(status_code=200, content={"status": "filtered_number"})

    logger.info("Received message from %s (type=%s)", phone_number, message_type)

    # Record the message before doing any work, so history is complete even if
    # parsing later fails.
    _log_inbound({"phone": phone_number}, payload)

    # ── Handle image messages ────────────────────────────────────────
    if message_type == "imageMessage" or message.get("imageMessage"):
        logger.info("Processing image message from %s", phone_number)
        result = await _fetch_image_base64(instance_id, msg_id)
        if not result or not result.get("base64"):
            logger.error("Failed to get image base64 for msg %s", msg_id)
            return JSONResponse(status_code=200, content={"status": "image_fetch_failed"})

        image_base64 = result["base64"]
        mimetype = result.get("mimetype", result.get("mimeType", "image/jpeg"))

        if "," in image_base64:
            image_base64 = image_base64.split(",", 1)[1]

        try:
            decoded = base64.b64decode(image_base64, validate=True)
        except Exception:
            logger.warning("Invalid base64 from Evolution API for msg %s", msg_id)
            return JSONResponse(status_code=200, content={"status": "invalid_base64"})

        if len(decoded) > _MAX_IMAGE_BYTES:
            logger.warning("Image too large: %d bytes", len(decoded))
            return JSONResponse(status_code=200, content={"status": "image_too_large"})

        background_tasks.add_task(_run_image_flow, image_base64, mimetype, remote_jid)
        return JSONResponse(status_code=200, content={"status": "image_accepted"})

    # ── Handle text messages ─────────────────────────────────────────
    text = (
        message.get("conversation")
        or message.get("extendedTextMessage", {}).get("text")
        or ""
    )
    if not text:
        logger.info("Unsupported message type or empty text: %s", message_type)
        return JSONResponse(status_code=200, content={"status": "unsupported_type"})

    logger.info("Processing text message (%d chars) from %s", len(text), phone_number)
    background_tasks.add_task(_run_text_flow, text, remote_jid)
    return JSONResponse(status_code=200, content={"status": "text_accepted"})


# ── Legacy endpoints (kept for backward compatibility) ─────────────────

@app.post("/api/webhooks/whatsapp-image")
async def whatsapp_image_webhook(request: Request, background_tasks: BackgroundTasks):
    """Legacy endpoint — receive a job posting image with base64 already resolved."""
    api_key = request.headers.get(_API_KEY_HEADER)
    if not api_key or api_key != _EXPECTED_API_KEY:
        return JSONResponse(status_code=401, content={"error": "Invalid or missing API key"})

    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "Invalid JSON body"})

    image_base64 = body.get("imageBase64")
    mimetype = body.get("mimetype", "image/jpeg")
    if not image_base64:
        return JSONResponse(status_code=400, content={"error": "Missing imageBase64"})

    if mimetype not in _VALID_MIMETYPES:
        return JSONResponse(status_code=400, content={"error": f"Unsupported mimetype '{mimetype}'"})

    try:
        decoded = base64.b64decode(image_base64, validate=True)
    except Exception:
        return JSONResponse(status_code=400, content={"error": "Invalid base64 encoding"})

    if len(decoded) > _MAX_IMAGE_BYTES:
        return JSONResponse(status_code=400, content={"error": "Image too large"})

    if "," in image_base64:
        image_base64 = image_base64.split(",", 1)[1]

    legacy_sender = body.get("sender") or body.get("number") or None
    background_tasks.add_task(_run_image_flow, image_base64, mimetype, legacy_sender)
    return JSONResponse(status_code=202, content={"status": "accepted"})


@app.post("/api/webhooks/whatsapp-text")
async def whatsapp_text_webhook(request: Request, background_tasks: BackgroundTasks):
    """Legacy endpoint — receive text directly (bypassed Evolution API)."""
    api_key = request.headers.get(_API_KEY_HEADER)
    if not api_key or api_key != _EXPECTED_API_KEY:
        return JSONResponse(status_code=401, content={"error": "Invalid or missing API key"})

    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "Invalid JSON body"})

    text = body.get("text", "").strip()
    if not text:
        return JSONResponse(status_code=400, content={"error": "Missing 'text' field"})
    if len(text) > 10000:
        return JSONResponse(status_code=400, content={"error": "Text too long (max 10000 chars)"})

    legacy_text_sender = body.get("sender") or body.get("number") or None
    background_tasks.add_task(_run_text_flow, text, legacy_text_sender)
    return JSONResponse(status_code=202, content={"status": "accepted"})


@app.post("/api/matches/run")
async def run_matches(request: Request, background_tasks: BackgroundTasks):
    """Trigger a matching run for a linked candidate."""
    if not _MATCH_TRIGGER_SECRET:
        return JSONResponse(status_code=503, content={"error": "Match trigger is not configured"})

    header = request.headers.get(_MATCH_TRIGGER_HEADER)
    if not header or not secrets.compare_digest(header, _MATCH_TRIGGER_SECRET):
        return JSONResponse(status_code=401, content={"error": "Unauthorized"})

    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "Invalid JSON body"})

    user_id = body.get("user_id")
    if not isinstance(user_id, str) or not user_id.strip():
        return JSONResponse(status_code=400, content={"error": "Missing user_id"})

    try:
        limit = int(body.get("limit") or 50)
    except (TypeError, ValueError):
        return JSONResponse(status_code=400, content={"error": "Invalid limit"})

    match_since = None
    raw_since = body.get("match_since")
    if raw_since:
        if not isinstance(raw_since, str):
            return JSONResponse(status_code=400, content={"error": "Invalid match_since"})
        try:
            match_since = datetime.fromisoformat(raw_since.replace("Z", "+00:00"))
        except ValueError:
            return JSONResponse(status_code=400, content={"error": "Invalid match_since"})

    background_tasks.add_task(
        _run_match_flow, user_id.strip(), match_since, max(1, min(limit, 200))
    )
    return JSONResponse(
        status_code=202,
        content={
            "status": "accepted",
            "user_id": user_id.strip(),
            "match_since": raw_since,
        },
    )


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "evolution_webhook_configured": bool(
            getattr(app.state, "evolution_webhook_configured", False)
        ),
    }


# ── Background runners ─────────────────────────────────────────────────

_WEB_FORWARD_URL = os.getenv(
    "WHATSAPP_FORWARD_URL", "https://mukana.mikeyverse.co.zw/api/webhooks/whatsapp"
)


def _log_inbound(payload: dict, payload_raw: dict) -> None:
    """Record the message so the dashboard shows the same history the app has.

    Best effort: a logging failure must never stop a job from being ingested.
    """
    if not _WEB_FORWARD_URL or not _WEBHOOK_SECRET:
        return
    try:
        httpx.post(
            _WEB_FORWARD_URL,
            headers={
                "Content-Type": "application/json",
                _WEBHOOK_SECRET_HEADER: _WEBHOOK_SECRET,
            },
            json=payload_raw,
            timeout=20,
        )
    except Exception:
        logger.exception("Could not log inbound WhatsApp message")


def _ingest(payload: dict, label: str) -> dict | None:
    """Forward a raw WhatsApp message to the web pipeline, which parses and matches it."""
    if not _WEB_INGEST_URL or not _WEBHOOK_SECRET:
        logger.error("Web ingest is not configured; dropping %s", label)
        return None

    try:
        response = httpx.post(
            _WEB_INGEST_URL,
            headers={
                "Content-Type": "application/json",
                _WEBHOOK_SECRET_HEADER: _WEBHOOK_SECRET,
            },
            json=payload,
            timeout=300,
        )
        if response.status_code >= 400:
            logger.error(
                "Web ingest rejected %s (%s): %s",
                label,
                response.status_code,
                response.text[:400],
            )
            return None
        logger.info("Web ingest accepted %s: %s", label, response.text[:300])
        return response.json()
    except Exception:
        logger.exception("Web ingest failed for %s", label)
        return None


def _confirmation(job: dict) -> str:
    company = job.get("company")
    suffix = f" at {company}" if company else ""
    return f"📥 Added *{job['title']}*{suffix}. Matching and preparing your application now."


def _run_image_flow(image_base64: str, mimetype: str, sender: str | None = None):
    result = _ingest(
        {"image_base64": image_base64, "mimetype": mimetype, "sender": sender}, "image job"
    )
    if result is None:
        _notify("⚠️ I could not read that job posting. Please try again.", sender)
        return
    job = result.get("parsed")
    if not job:
        logger.info("Image was not a job posting; ignoring")
        return
    if result.get("ok") is False:
        _notify(_not_registered_message(), sender)
        return
    _notify(_confirmation(job), sender)


def _run_text_flow(text: str, sender: str | None = None):
    result = _ingest({"text": text, "sender": sender}, "text job")
    if result is None:
        _notify("⚠️ I could not read that job posting. Please try again.", sender)
        return
    job = result.get("parsed")
    if not job:
        logger.info("Text was not a job posting; ignoring")
        return
    if result.get("ok") is False:
        _notify(_not_registered_message(), sender)
        return
    _notify(_confirmation(job), sender)


def _not_registered_message() -> str:
    return (
        "This number is not linked to a Mukana account yet. "
        "Join the WhatsApp pilot from your dashboard, then resend the job posting."
    )


def _notify(message: str, sender: str | None = None) -> None:
    """Best-effort WhatsApp confirmation back to the number that wrote to us."""
    if not _EXPECTED_API_KEY:
        logger.warning("Skipping WhatsApp confirmation: API key not configured")
        return
    try:
        from app.whatsapp_notifier import send_whatsapp

        send_whatsapp(text=message, number=sender)
    except Exception:
        logger.exception("Could not send WhatsApp confirmation")


if __name__ == "__main__":
    import uvicorn

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("prefect").setLevel(logging.WARNING)
    logging.getLogger("app.llm").setLevel(logging.WARNING)
    port = int(os.getenv("WEBHOOK_PORT", "8055"))
    host = os.getenv("WEBHOOK_HOST", "::")

    # ╔═══════════════════════════════════════════════════════════════════════════════╗
    # ║  ⚠️  WARNING — HOOK HOST BINDING — READ BEFORE CHANGING  ⚠️                    ║
    # ║                                                                               ║
    # ║  The committed/known-good value is  host="::"  (everything IPv4+IPv6).         ║
    # ║  The Evolution API delivers to "http://localhost:8055/..." — it must be        ║
    # ║  reachable over BOTH v4 (127.0.0.1) and v6 ([::1]). The Evolution API sends    ║
    # ║  over the address family the OS resolves "localhost" to; changing the bind     ║
    # ║  to IPv6-only or IPv4-only can silently drop ALL inbound WhatsApp messages     ║
    # ║  (nothing received, no replies sent). This bug was hit on 2026-08-12.          ║
    # ║                                                                               ║
    # ║  If you change host and inbound stops working, VERIFY with BOTH:               ║
    # ║     curl http://127.0.0.1:8055/api/webhooks/evolution ...                      ║
    # ║     curl http://[::1]:8055/health ...                                          ║
    # ║  and never assume one family. Prefer "::" (dual-stack) on this machine.        ║
    # ╚═══════════════════════════════════════════════════════════════════════════════╝
    uvicorn.run("app.webhook_server:app", host=host, port=port, reload=False)
