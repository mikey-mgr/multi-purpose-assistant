"""Point the local Evolution instance at the Mukana Pages webhook."""

import os
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
EVOLUTION_HOME = Path(
    os.getenv("EVOLUTION_HOME", r"C:\Users\mmash\Desktop\Projects\Whatsapp-evolution-api")
)
WEBHOOK_URL = os.getenv(
    "EVOLUTION_WEBHOOK_URL", "https://mukana.mikeyverse.co.zw/api/webhooks/whatsapp"
)
API_URL = os.getenv("EVOLUTION_API_URL", "http://localhost:8080")


def read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def main() -> None:
    app_env = read_env(ROOT / ".env")
    evolution_env = read_env(EVOLUTION_HOME / ".env")

    api_key = evolution_env.get("AUTHENTICATION_API_KEY") or app_env.get("WHATSAPP_API_KEY")
    secret = app_env.get("WHATSAPP_WEBHOOK_SECRET")
    instance = app_env.get("EVOLUTION_INSTANCE_NAME", "Apex_Web_Services")
    if not api_key or not secret:
        raise SystemExit("Evolution API key or WhatsApp webhook secret is missing")

    payload = {
        "webhook": {
            "enabled": True,
            "url": WEBHOOK_URL,
            "webhookByEvents": False,
            "webhookBase64": False,
            "events": ["MESSAGES_UPSERT"],
            "headers": {"x-webhook-secret": secret},
        }
    }

    last_error = None
    for _ in range(30):
        try:
            response = httpx.post(
                f"{API_URL.rstrip('/')}/webhook/set/{instance}",
                headers={"apikey": api_key},
                json=payload,
                timeout=15,
            )
            response.raise_for_status()
            print(f"Evolution webhook registered for {instance} -> {WEBHOOK_URL}")
            return
        except Exception as exc:
            last_error = exc
            time.sleep(4)
    raise SystemExit(f"Could not register Evolution webhook: {last_error}")


if __name__ == "__main__":
    main()
