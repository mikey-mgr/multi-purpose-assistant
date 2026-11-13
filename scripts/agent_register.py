"""Register a local Mukana agent and store its credentials under ~/.mukana."""

import argparse
import json
import os
import socket
from pathlib import Path

import httpx

DEFAULT_SERVER = "https://mukana.mikeyverse.co.zw"
CONFIG_PATH = Path(
    os.getenv("MUKANA_AGENT_CONFIG", str(Path.home() / ".mukana" / "agent.json"))
)
BOOTSTRAP_PATH = Path.home() / ".mukana" / "bootstrap.secret"


def bootstrap_secret() -> str:
    value = os.getenv("AGENT_BOOTSTRAP_SECRET")
    if value:
        return value
    if BOOTSTRAP_PATH.exists():
        return BOOTSTRAP_PATH.read_text(encoding="utf-8").strip()
    raise SystemExit(
        "AGENT_BOOTSTRAP_SECRET is not set and ~/.mukana/bootstrap.secret does not exist."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Register a Mukana agent node.")
    parser.add_argument("--name", default=socket.gethostname())
    parser.add_argument("--kind", choices=["scraper", "apply", "both"], required=True)
    parser.add_argument("--server", default=os.getenv("AGENT_SERVER_URL", DEFAULT_SERVER))
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if CONFIG_PATH.exists() and not args.force:
        raise SystemExit(f"Agent config already exists at {CONFIG_PATH}. Use --force to replace.")

    response = httpx.post(
        f"{args.server.rstrip('/')}/api/agent/register",
        headers={"x-agent-bootstrap-secret": bootstrap_secret()},
        json={"name": args.name, "kind": args.kind},
        timeout=30,
    )
    if response.status_code >= 400:
        raise SystemExit(f"Registration failed ({response.status_code}): {response.text}")

    data = response.json()
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(
        json.dumps(
            {
                "server_url": args.server.rstrip("/"),
                "agent_id": data["agentId"],
                "agent_key": data["agentKey"],
                "kind": data["kind"],
                "name": data["name"],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Registered agent '{data['name']}' ({data['kind']}) at {CONFIG_PATH}")


if __name__ == "__main__":
    main()
