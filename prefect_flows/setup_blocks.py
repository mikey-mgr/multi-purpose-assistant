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
    ("app-config-openrouter-api-key", "OPENROUTER_API_KEY", "OpenRouter API key"),
    ("app-config-gemini-api-key", "GEMINI_API_KEY", "Google Gemini API key"),
    ("app-config-llm-provider", "LLM_PROVIDER", "Default LLM provider (openrouter | gemini)"),
    ("app-config-llm-model", "LLM_MODEL", "Default LLM model for generation"),
    ("app-config-serpapi-api-key", "SERPAPI_API_KEY", "SerpAPI key"),
    ("app-config-gmail-address", "GMAIL_ADDRESS", "Gmail sending address"),
    ("app-config-gmail-app-password", "GMAIL_APP_PASSWORD", "Gmail app password"),
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
