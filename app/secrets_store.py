"""
Secrets storage via OS credential manager (Windows Credential Manager).

Stores keys outside .env, outside Prefect blocks, outside env vars.
Uses Python's `keyring` library which talks directly to the OS secure store.

Usage:
    python -m app.secrets_store --help       # CLI management
    from app.secrets_store import get_secret  # programmatic
"""

import argparse
import getpass
import logging
import os
import sys

logger = logging.getLogger(__name__)

_SERVICE_NAME = "automated-job-assistant"


def _get_keyring():
    """Lazy-import keyring so missing dep doesn't break imports."""
    try:
        import keyring
        return keyring
    except ImportError:
        return None


def get_secret(key: str) -> str | None:
    """Read a secret from OS credential manager.
    
    Returns None if not found or keyring unavailable.
    """
    kr = _get_keyring()
    if kr is None:
        return None
    try:
        return kr.get_password(_SERVICE_NAME, key)
    except Exception as e:
        logger.debug("keyring get(%s) failed: %s", key, e)
        return None


def set_secret(key: str, value: str) -> bool:
    """Store a secret in OS credential manager.
    
    Returns True if stored successfully.
    """
    kr = _get_keyring()
    if kr is None:
        logger.error("keyring not installed — run: pip install keyring")
        return False
    try:
        kr.set_password(_SERVICE_NAME, key, value)
        logger.info("Secret '%s' stored in OS credential manager", key)
        return True
    except Exception as e:
        logger.error("Failed to store secret '%s': %s", key, e)
        return False


def delete_secret(key: str) -> bool:
    """Remove a secret from OS credential manager."""
    kr = _get_keyring()
    if kr is None:
        return False
    try:
        kr.delete_password(_SERVICE_NAME, key)
        logger.info("Secret '%s' deleted", key)
        return True
    except Exception as e:
        logger.debug("keyring delete(%s) failed: %s", key, e)
        return False


def list_keys() -> list[str]:
    """List stored secret keys (only works with some backends)."""
    kr = _get_keyring()
    if kr is None:
        return []
    try:
        # keyring doesn't have a standard list API — best effort via credential query
        return []
    except Exception:
        return []


# ── CLI ─────────────────────────────────────────────────────────────

def _cli():
    parser = argparse.ArgumentParser(
        description="Manage secrets in OS credential manager",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_set = sub.add_parser("set", help="Store a secret")
    p_set.add_argument("key", help="Secret name (e.g. OPENROUTER_API_KEY)")
    p_set.add_argument("value", nargs="?", help="Secret value (prompts if omitted)")

    p_get = sub.add_parser("get", help="Read a secret")
    p_get.add_argument("key", help="Secret name")

    p_del = sub.add_parser("delete", help="Remove a secret")
    p_del.add_argument("key", help="Secret name")

    args = parser.parse_args()

    if args.command == "set":
        value = args.value or getpass.getpass(f"Value for {args.key}: ")
        set_secret(args.key, value)

    elif args.command == "get":
        val = get_secret(args.key)
        if val is None:
            print(f"Secret '{args.key}' not found", file=sys.stderr)
            sys.exit(1)
        print(val)

    elif args.command == "delete":
        delete_secret(args.key)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    _cli()
