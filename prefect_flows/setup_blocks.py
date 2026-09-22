"""
Set up Prefect Secret blocks for local development.

Requires the Prefect server to be running on http://127.0.0.1:4200.

Usage:
    python prefect_flows/setup_blocks.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from prefect.blocks.system import Secret

SECRETS = [
    ("app-config-db-conn-uri", "DB_CONN_URI", "Database connection URI"),
    ("app-config-gemini-api-key", "GEMINI_API_KEY", "Google Gemini API key"),
    ("app-config-litert-api-key", "LITERT_API_KEY", "LiteRT-LM local GPU server API key"),
    ("app-config-llm-provider", "LLM_PROVIDER", "Default LLM provider (gemini | local)"),
    ("app-config-llm-model", "LLM_MODEL", "Default LLM model for generation"),
    ("app-config-serpapi-api-key", "SERPAPI_API_KEY", "SerpAPI key"),
    ("app-config-tavily-api-key", "TAVILY_API_KEY", "Tavily API key (fallback for company research)"),
    ("app-config-gmail-address", "GMAIL_ADDRESS", "Gmail sending address"),
    ("app-config-gmail-app-password", "GMAIL_APP_PASSWORD", "Gmail app password"),
    ("app-config-whatsapp-api-key", "WHATSAPP_API_KEY", "Whatsapp api key"),
    ("app-config-whatsapp-number", "WHATSAPP_NUMBER", "WhatsApp bot number (e.g. 263717827381@s.whatsapp.net)"),
    ("app-config-whatsapp-webhook-secret", "WHATSAPP_WEBHOOK_SECRET", "Shared Evolution webhook secret (x-webhook-secret)"),
    ("app-config-whatsapp-allowed-numbers", "WHATSAPP_ALLOWED_NUMBERS", "Comma-separated allowed sender numbers"),
    ("app-config-evolution-instance-name", "EVOLUTION_INSTANCE_NAME", "Evolution API instance name"),
    ("app-config-evolution-webhook-url", "EVOLUTION_WEBHOOK_URL", "Public webhook URL Evolution POSTs to"),
]


def main():
    from dotenv import load_dotenv

    load_dotenv()

    for block_name, env_var, desc in SECRETS:
        value = os.getenv(env_var, "")
        if not value:
            print(f"  [?] {env_var} is empty -- skipping {block_name}")
            continue
        try:
            Secret(value=value).save(name=block_name, overwrite=True)
            print(f"  [OK] {block_name} <- ${env_var}")
        except Exception as exc:
            print(f"  [FAIL] {block_name} -- {exc}")


if __name__ == "__main__":
    main()
