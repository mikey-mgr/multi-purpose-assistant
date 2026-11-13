"""Start the matcher with every secret it needs.

The matcher calls Gemini directly, so it needs GEMINI_API_KEY in its own
environment. Secrets are cached in ~/.mukana/matcher.env; that file is the
source of truth so restarts work offline.
"""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\mmash\Desktop\Projects\Automated Job Application Assistant")
CACHE = Path.home() / ".mukana" / "matcher.env"


def load(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


env = dict(os.environ)
# .env files first, then the cached secrets win (they hold what Cloudflare has).
env.update(load(ROOT / "web" / ".env"))
env.update(load(ROOT / ".env"))
env.update(load(CACHE))

missing = [k for k in ("DATABASE_URL", "MATCH_TRIGGER_SECRET", "GEMINI_API_KEY") if not env.get(k)]
if missing:
    print("missing secrets:", missing)
    print(f"Add them to {CACHE} — this launcher will not guess them.")
    sys.exit(1)

env.setdefault("PYTHONUNBUFFERED", "1")
print("starting matcher on 127.0.0.1:8090")
subprocess.run(
    [sys.executable, "-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", "8090"],
    cwd=str(ROOT / "containers" / "matcher"),
    env=env,
)
