"""
Application configuration.

Precedence (highest to lowest):
  1. OS environment variables
  2. Prefect Secret Blocks (when Prefect server is reachable)
  3. .env file (gitignored, local dev fallback)
"""

import logging
import os
from dotenv import load_dotenv

load_dotenv(override=False)

logger = logging.getLogger(__name__)


class Settings:
    # ── Database ────────────────────────────────────────────────────
    DB_CONN_URI: str = os.getenv(
        "DB_CONN_URI",
        "postgresql://postgres:@localhost:5432/ai_assistant",
    )

    # ── LLM Provider (OpenRouter or Gemini) ─────────────────────────
    OPENROUTER_API_KEY: str | None = os.getenv("OPENROUTER_API_KEY")
    GEMINI_API_KEY: str | None = os.getenv("GEMINI_API_KEY")

    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "openrouter")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "openai/gpt-4o")
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    EMBEDDING_DIM: int = int(os.getenv("EMBEDDING_DIM", "1536"))

    # ── Services ────────────────────────────────────────────────────
    SERPAPI_API_KEY: str | None = os.getenv("SERPAPI_API_KEY")
    EVOLUTION_API_URL: str = os.getenv("EVOLUTION_API_URL", "http://localhost:8080")

    # ── Email (Gmail SMTP) ──────────────────────────────────────────
    GMAIL_ADDRESS: str | None = os.getenv("GMAIL_ADDRESS")
    GMAIL_APP_PASSWORD: str | None = os.getenv("GMAIL_APP_PASSWORD")

    # ── Prefect ─────────────────────────────────────────────────────
    PREFECT_API_URL: str | None = os.getenv("PREFECT_API_URL")
    PREFECT_ENV: str = os.getenv("PREFECT_ENV", "development")

    # ── Paths ───────────────────────────────────────────────────────
    OUTPUT_DIR: str = os.getenv("OUTPUT_DIR", "data")

    # ── Key names in Prefect Secret blocks ─────────────────────────
    _SECRET_KEYS = {
        "DB_CONN_URI": "db-conn-uri",
        "OPENROUTER_API_KEY": "openrouter-api-key",
        "GEMINI_API_KEY": "gemini-api-key",
        "SERPAPI_API_KEY": "serpapi-api-key",
        "GMAIL_ADDRESS": "gmail-address",
        "GMAIL_APP_PASSWORD": "gmail-app-password",
        "LLM_PROVIDER": "llm-provider",
        "LLM_MODEL": "llm-model",
        "WHATSAPP_API_KEY": "whatsapp-api-key"
    }

    @classmethod
    def from_prefect(cls):
        """
        Override env/.env values with Prefect Secret blocks.
        Blocks named `app-config-<suffix>`.  Silently skips if
        the Prefect server is unreachable or a block is missing.
        """
        try:
            from prefect.blocks.system import Secret

            for attr, block_suffix in cls._SECRET_KEYS.items():
                block_name = f"app-config-{block_suffix}"
                try:
                    val = Secret.load(block_name).get()
                    if val:
                        setattr(cls, attr, val)
                except Exception:
                    pass  # block missing or server unreachable
        except ImportError:
            pass  # prefect not installed
        return cls


settings = Settings()
Settings.from_prefect()

# Debug-friendly log (password masked)
_uri_parts = settings.DB_CONN_URI.split("@")
_display_uri = f"...@{_uri_parts[-1]}" if len(_uri_parts) > 1 else settings.DB_CONN_URI
logger.debug("DB_CONN_URI resolved to: %s", _display_uri)
