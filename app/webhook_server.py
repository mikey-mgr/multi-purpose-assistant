"""
FastAPI webhook server for the Evolution WhatsApp API.

Replaces n8n entirely — receives messages directly from Evolution API,
handles text and images, and triggers the appropriate Prefect flow.

Usage: python -m app.webhook_server
"""

import base64
import logging
import os
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import JSONResponse

from app.config import settings

logger = logging.getLogger(__name__)

_API_KEY_HEADER = "apikey"
_EXPECTED_API_KEY = settings.WHATSAPP_API_KEY
_MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MB
_VALID_MIMETYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}

# Only process messages from these phone number prefixes
_RESTRICTED_PREFIXES = ["263788667111", "263773393934", "263771906135"]

_EVOLUTION_API_URL = settings.EVOLUTION_API_URL


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("WhatsApp webhook server starting ...")
    yield
    logger.info("WhatsApp webhook server shutting down.")


app = FastAPI(
    title="WhatsApp Job Webhook",
    description="Receives messages from the Evolution API and triggers the application pipeline.",
    version="2.0.0",
    lifespan=lifespan,
)


# ── Helpers ────────────────────────────────────────────────────────────

def _is_allowed_number(phone_number: str) -> bool:
    """Check if the phone number is in the allowed prefixes list."""
    return any(phone_number.startswith(p) for p in _RESTRICTED_PREFIXES)


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

    # Filter: only individual WhatsApp chats (@s.whatsapp.net)
    if not remote_jid.endswith("@s.whatsapp.net"):
        logger.debug("Skipping non-individual chat: %s", remote_jid)
        return JSONResponse(status_code=200, content={"status": "filtered_group"})

    # Filter: only allowed phone numbers
    phone_number = remote_jid.split("@")[0]
    if not _is_allowed_number(phone_number):
        logger.debug("Skipping message from non-allowed number: %s", phone_number)
        return JSONResponse(status_code=200, content={"status": "filtered_number"})

    logger.info("Received message from %s (type=%s)", phone_number, message_type)

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

        background_tasks.add_task(_run_image_flow, image_base64, mimetype)
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
    background_tasks.add_task(_run_text_flow, text)
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

    background_tasks.add_task(_run_image_flow, image_base64, mimetype)
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

    background_tasks.add_task(_run_text_flow, text)
    return JSONResponse(status_code=202, content={"status": "accepted"})


@app.get("/health")
async def health():
    return {"status": "ok"}


# ── Background runners ─────────────────────────────────────────────────

def _run_image_flow(image_base64: str, mimetype: str):
    from prefect_flows.whatsapp_job_flow import process_whatsapp_job

    process_whatsapp_job(image_base64=image_base64, mimetype=mimetype)
    logger.info("Image flow completed.")


def _run_text_flow(text: str):
    from prefect_flows.whatsapp_job_flow import process_whatsapp_text

    process_whatsapp_text(text=text)
    logger.info("Text flow completed.")


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
    uvicorn.run("app.webhook_server:app", host="::", port=port, reload=False)
