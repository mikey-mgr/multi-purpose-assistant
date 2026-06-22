"""
FastAPI webhook server for WhatsApp job posting images.

Usage: python -m app.webhook_server
"""

import base64
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import JSONResponse

from app.config import settings

logger = logging.getLogger(__name__)

_API_KEY_HEADER = "apikey"
_EXPECTED_API_KEY = settings.WHATSAPP_API_KEY
_MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MB
_VALID_MIMETYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("WhatsApp webhook server starting ...")
    yield
    logger.info("WhatsApp webhook server shutting down.")


app = FastAPI(
    title="WhatsApp Job Webhook",
    description="Receives job posting images from WhatsApp and triggers the application pipeline.",
    version="1.0.0",
    lifespan=lifespan,
)


def _run_flow(image_base64: str, mimetype: str):
    """Run the Prefect flow in a background thread."""
    from prefect_flows.whatsapp_job_flow import process_whatsapp_job

    process_whatsapp_job(image_base64=image_base64, mimetype=mimetype)
    logger.info("WhatsApp job flow completed for image (%s).", mimetype)


@app.post("/api/webhooks/whatsapp-image")
async def whatsapp_image_webhook(request: Request, background_tasks: BackgroundTasks):
    """Receive a job posting image and kick off the application pipeline."""

    # 1. Validate API key header
    api_key = request.headers.get(_API_KEY_HEADER)
    if not api_key:
        logger.warning("Missing apikey header.")
        return JSONResponse(status_code=401, content={"error": "Missing apikey header"})
    if api_key != _EXPECTED_API_KEY:
        logger.warning("Invalid apikey: %s", api_key[:8])
        return JSONResponse(status_code=401, content={"error": "Invalid API key"})

    # 2. Parse body
    try:
        body = await request.json()
    except Exception:
        logger.warning("Invalid JSON body.")
        return JSONResponse(status_code=400, content={"error": "Invalid JSON body"})

    image_base64 = body.get("imageBase64")
    mimetype = body.get("mimetype", "image/jpeg")

    if not image_base64:
        logger.warning("Missing imageBase64 in body.")
        return JSONResponse(status_code=400, content={"error": "Missing imageBase64"})

    # 3. Validate mimetype
    if mimetype not in _VALID_MIMETYPES:
        logger.warning("Unsupported mimetype: %s", mimetype)
        return JSONResponse(status_code=400, content={
            "error": f"Unsupported mimetype '{mimetype}'. Supported: {', '.join(sorted(_VALID_MIMETYPES))}",
        })

    # 4. Validate base64
    try:
        decoded = base64.b64decode(image_base64, validate=True)
    except Exception:
        logger.warning("Invalid base64 encoding.")
        return JSONResponse(status_code=400, content={"error": "Invalid base64 encoding"})

    if len(decoded) > _MAX_IMAGE_BYTES:
        logger.warning("Image too large: %d bytes", len(decoded))
        return JSONResponse(status_code=400, content={
            "error": f"Image too large ({len(decoded)} bytes). Max {_MAX_IMAGE_BYTES} bytes.",
        })

    # 5. Sanitize base64 (remove data: URI prefix if present)
    if "," in image_base64:
        image_base64 = image_base64.split(",", 1)[1]

    logger.info("Valid webhook request: mimetype=%s, size=%d bytes", mimetype, len(decoded))

    # 6. Trigger flow in background
    background_tasks.add_task(_run_flow, image_base64, mimetype)

    return JSONResponse(
        status_code=202,
        content={"status": "accepted", "message": "Job posting image queued for processing."},
    )


@app.get("/health")
async def health():
    return {"status": "ok"}


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
