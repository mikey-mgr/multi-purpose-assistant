"""Create a compressed logical backup of the Neon database under data/backups."""

import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKUP_DIR = ROOT / "data" / "backups"
KEEP = int(os.getenv("BACKUP_KEEP", "14"))


def database_url() -> str:
    value = os.getenv("DATABASE_URL")
    if value:
        return value
    env_file = ROOT / "web" / ".env"
    for line in env_file.read_text(encoding="utf-8").splitlines():
        if line.startswith("DATABASE_URL="):
            return line.split("=", 1)[1].strip().strip('"')
    raise SystemExit("DATABASE_URL not found")


def main() -> None:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    target = BACKUP_DIR / f"mukana-neon-{stamp}.dump"
    subprocess.run(
        [
            "pg_dump",
            "--format=custom",
            "--no-owner",
            "--no-privileges",
            "--no-password",
            "--file",
            str(target),
            database_url(),
        ],
        check=True,
        env={**os.environ, "PGCONNECT_TIMEOUT": "15"},
    )
    print(f"backup written: {target} ({target.stat().st_size} bytes)")

    backups = sorted(BACKUP_DIR.glob("mukana-neon-*.dump"), key=lambda path: path.stat().st_mtime)
    for old in backups[:-KEEP]:
        old.unlink()
        print(f"removed old backup: {old.name}")


if __name__ == "__main__":
    main()
