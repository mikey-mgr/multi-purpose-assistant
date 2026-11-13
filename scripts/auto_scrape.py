"""Queue a scrape task on a loop so the local scraper stays busy."""

import argparse
import logging
import os
import time
from pathlib import Path

import httpx

logger = logging.getLogger("mukana.auto_scrape")

SERVER = os.getenv("MUKANA_SERVER_URL", "https://mukana.mikeyverse.co.zw").rstrip("/")
INTERVAL = int(os.getenv("MUKANA_SCRAPE_INTERVAL_HOURS", "6"))
SITES = [
    site.strip()
    for site in os.getenv("MUKANA_SCRAPE_SITES", "applynow,vacancymail").split(",")
    if site.strip()
]


def secret() -> str:
    value = os.getenv("AGENT_BOOTSTRAP_SECRET")
    if value:
        return value
    return (Path(os.environ["USERPROFILE"]) / ".mukana" / "bootstrap.secret").read_text(
        encoding="ascii"
    ).strip()


def queue() -> None:
    response = httpx.post(
        f"{SERVER}/api/agent/scrape",
        headers={"x-agent-bootstrap-secret": secret()},
        json={"site_names": SITES, "max_pages": 1},
        timeout=30,
    )
    if response.status_code >= 400:
        logger.warning("Scrape queue failed: %s %s", response.status_code, response.text[:300])
        return
    logger.info("Scrape task queued for %s", ", ".join(SITES))


def main() -> None:
    parser = argparse.ArgumentParser(description="Queue Mukana scrape tasks")
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    while True:
        try:
            queue()
        except Exception:
            logger.exception("Could not queue scrape")
        if args.once:
            break
        time.sleep(max(600, INTERVAL * 3600))


if __name__ == "__main__":
    main()
