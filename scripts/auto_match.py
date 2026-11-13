"""Run matching for active profiles on a loop or once."""

import argparse
import json
import logging
import os
import time
from pathlib import Path

import httpx
import psycopg2

logger = logging.getLogger("mukana.auto_match")

ROOT = Path(__file__).resolve().parents[1]
MATCHER_URL = os.getenv("MATCHER_URL", "https://match.mikeyverse.co.zw/match")
NOTIFY_URL = os.getenv(
    "NOTIFY_URL", "https://mukana.mikeyverse.co.zw/api/notifications/matches"
)
INTERVAL = int(os.getenv("MUKANA_AUTO_MATCH_INTERVAL_MINUTES", "15"))


def load_env() -> None:
    env_file = Path(os.environ["USERPROFILE"]) / ".mukana" / "matcher.env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.strip().startswith("#"):
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())
    env_file = ROOT / "web" / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("DATABASE_URL="):
                os.environ.setdefault("DATABASE_URL", line.split("=", 1)[1].strip())


def profiles(database_url: str) -> list[str]:
    with psycopg2.connect(database_url) as conn, conn.cursor() as cur:
        cur.execute(
            """select p.user_id
               from profiles p
               join "user" u on u.id = p.user_id
               where p.onboarding_completed = true
                 and (coalesce(length(p.resume_text), 0) > 0 or p.headline is not null)
                 and lower(u.email) not like '%@example.com'
               order by p.updated_at desc
               limit 25"""
        )
        return [row[0] for row in cur.fetchall()]


def run_once(database_url: str, secret: str) -> None:
    user_ids = profiles(database_url)
    logger.info("Running matching for %d profile(s)", len(user_ids))
    for user_id in user_ids:
        try:
            response = httpx.post(
                MATCHER_URL,
                headers={"x-match-trigger-secret": secret},
                json={"web_user_id": user_id, "limit": 50},
                timeout=240,
            )
            if response.status_code >= 400:
                logger.warning("Matcher returned %s for %s", response.status_code, user_id)
                continue
            result = response.json()
            logger.info(
                "Matched %s: processed=%s matched=%s rejected=%s",
                user_id,
                result.get("processed"),
                result.get("matched"),
                result.get("rejected"),
            )
            if (result.get("matched") or 0) > 0:
                notify = httpx.post(
                    NOTIFY_URL,
                    headers={"x-match-trigger-secret": secret},
                    json={"user_id": user_id},
                    timeout=60,
                )
                if notify.status_code >= 400:
                    logger.warning("Notification returned %s for %s", notify.status_code, user_id)
        except Exception:
            logger.exception("Matching failed for %s", user_id)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Mukana matching on a loop")
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    load_env()

    database_url = os.getenv("DATABASE_URL")
    secret = os.getenv("MATCH_TRIGGER_SECRET")
    if not database_url or not secret:
        raise SystemExit("DATABASE_URL and MATCH_TRIGGER_SECRET are required")

    with psycopg2.connect(database_url) as lock_conn:
        with lock_conn.cursor() as cur:
            cur.execute("select pg_try_advisory_lock(hashtext('mukana-auto-match'))")
            if not cur.fetchone()[0]:
                logger.info("Another auto-match run is active; exiting")
                return
        try:
            while True:
                run_once(database_url, secret)
                if args.once:
                    break
                time.sleep(max(60, INTERVAL * 60))
        except KeyboardInterrupt:
            logger.info("Auto matcher stopped")
        finally:
            with lock_conn.cursor() as cur:
                cur.execute("select pg_advisory_unlock(hashtext('mukana-auto-match'))")
                lock_conn.commit()


if __name__ == "__main__":
    main()
