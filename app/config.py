"""
Application configuration.

Precedence:
  1. Prefect Secret Blocks (when Prefect server is reachable)
  2. .env file (local development, gitignored)

For production: store every key in Prefect, delete .env.
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # ── Database ────────────────────────────────────────────────────
    DB_CONN_URI: str = os.getenv(
        "DB_CONN_URI",
        "postgresql://postgres:@localhost:5432/ai_assistant",
    )

    # ── LLM Providers ───────────────────────────────────────────────
    OPENAI_API_KEY: str | None = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4")
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    EMBEDDING_DIM: int = int(os.getenv("EMBEDDING_DIM", "1536"))

    OPENROUTER_API_KEY: str | None = os.getenv("OPENROUTER_API_KEY")
    OPENROUTER_MODEL: str = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o")

    GEMINI_API_KEY: str | None = os.getenv("GEMINI_API_KEY")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

    # ── Services ────────────────────────────────────────────────────
    SERPAPI_API_KEY: str | None = os.getenv("SERPAPI_API_KEY")

    # ── Email (Gmail SMTP) ──────────────────────────────────────────
    GMAIL_ADDRESS: str | None = os.getenv("GMAIL_ADDRESS")
    GMAIL_APP_PASSWORD: str | None = os.getenv("GMAIL_APP_PASSWORD")

    # ── Prefect ─────────────────────────────────────────────────────
    PREFECT_API_URL: str | None = os.getenv("PREFECT_API_URL")
    PREFECT_ENV: str = os.getenv("PREFECT_ENV", "development")

    # ── Paths ───────────────────────────────────────────────────────
    OUTPUT_DIR: str = os.getenv("OUTPUT_DIR", "data")

    # ── Key names in Prefect ───────────────────────────────────────
    _SECRET_KEYS = {
        "DB_CONN_URI": "db-conn-uri",
        "OPENAI_API_KEY": "openai-api-key",
        "OPENROUTER_API_KEY": "openrouter-api-key",
        "GEMINI_API_KEY": "gemini-api-key",
        "SERPAPI_API_KEY": "serpapi-api-key",
        "GMAIL_ADDRESS": "gmail-address",
        "GMAIL_APP_PASSWORD": "gmail-app-password",
    }

    @classmethod
    def from_prefect(cls):
        """
        Override .env values with Prefect Secret blocks.
        Called once at import time.  Blocks named  app-config-<suffix>.
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
                    pass  # block missing or server unreachable — keep .env
        except ImportError:
            pass  # prefect not installed — .env is fine
        return cls


settings = Settings()
Settings.from_prefect()  # override .env with Prefect Secret blocks if reachable
