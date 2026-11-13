"""Shared authenticated HTTP client and polling loop for local Mukana agents."""

import json
import logging
import os
import time
from pathlib import Path

import httpx

logger = logging.getLogger("mukana.agent")

DEFAULT_SERVER = "https://mukana.mikeyverse.co.zw"
CONFIG_PATH = Path(
    os.getenv("MUKANA_AGENT_CONFIG", str(Path.home() / ".mukana" / "agent.json"))
)


def load_agent_config(path: Path = CONFIG_PATH) -> dict:
    if not path.exists():
        raise SystemExit(
            f"Agent config not found at {path}. Run scripts/agent_register.py first."
        )
    return json.loads(path.read_text(encoding="utf-8"))


class AgentClient:
    def __init__(self, server_url: str, agent_id: str, agent_key: str):
        self.server_url = server_url.rstrip("/")
        self.agent_id = agent_id
        self.agent_key = agent_key
        self.http = httpx.Client(
            base_url=self.server_url,
            headers={
                "x-agent-id": self.agent_id,
                "x-agent-key": self.agent_key,
            },
            timeout=30,
        )

    def heartbeat(self) -> dict:
        response = self.http.post("/api/agent/heartbeat", json={})
        response.raise_for_status()
        return response.json()

    def claim(self, kind: str) -> dict | None:
        response = self.http.get("/api/agent/tasks/next", params={"kind": kind})
        response.raise_for_status()
        return response.json().get("task")

    def complete(self, task_id: str, status: str, result: dict) -> dict:
        response = self.http.post(
            f"/api/agent/tasks/{task_id}/result",
            json={"status": status, "result": result},
        )
        response.raise_for_status()
        return response.json()

    def application_kit(self, kit_id: str, legacy_user_id: str) -> dict:
        response = self.http.get(
            f"/api/agent/applications/{kit_id}",
            params={"legacy_user_id": legacy_user_id},
        )
        response.raise_for_status()
        return response.json()

    def mark_application_sent(self, kit_id: str, payload: dict) -> dict:
        response = self.http.post(
            f"/api/agent/applications/{kit_id}/sent", json=payload
        )
        response.raise_for_status()
        return response.json()

    def close(self):
        self.http.close()


def run_agent(kind: str, handler, once: bool = False, poll_seconds: int = 10):
    config = load_agent_config()
    required_kind = "scraper" if kind == "scrape" else "apply"
    if config.get("kind") not in (required_kind, "both"):
        raise SystemExit(
            f"This agent is registered as '{config.get('kind')}', not '{required_kind}'."
        )

    client = AgentClient(
        config.get("server_url", DEFAULT_SERVER),
        config["agent_id"],
        config["agent_key"],
    )
    logger.info("Agent %s (%s) polling %s", config.get("name"), kind, client.server_url)

    last_heartbeat = 0.0
    try:
        while True:
            now = time.time()
            if now - last_heartbeat >= 60:
                try:
                    client.heartbeat()
                    last_heartbeat = now
                except Exception as exc:
                    logger.warning("Heartbeat failed: %s", exc)

            try:
                task = client.claim(kind)
            except Exception as exc:
                logger.warning("Claim failed: %s", exc)
                task = None

            if task:
                task_id = task["id"]
                logger.info("Claimed task %s (attempt %s)", task_id, task.get("attempts"))
                try:
                    result = handler(task.get("payload") or {}) or {}
                    client.complete(task_id, "completed", result)
                    logger.info("Task %s completed", task_id)
                except Exception as exc:
                    logger.exception("Task %s failed", task_id)
                    client.complete(task_id, "failed", {"error": str(exc)[:1000]})
                if once:
                    break
            else:
                if once:
                    logger.info("No pending %s tasks.", kind)
                    break
                time.sleep(poll_seconds)
    except KeyboardInterrupt:
        logger.info("Agent stopped.")
    finally:
        client.close()
