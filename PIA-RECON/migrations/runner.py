"""
Tiny migration runner. Applies numbered *.sql files from this directory in
order, records each one in `schema_migrations`, and skips anything already
applied. Idempotent — safe to run on every boot.

Usage:
    python -m migrations.runner                # apply any pending
    python -m migrations.runner --status       # show applied vs pending
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import psycopg

MIGRATIONS_DIR = Path(__file__).parent
FILENAME_RE = re.compile(r"^(\d{4})_[a-z0-9_]+\.sql$")


def _database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        print(
            "DATABASE_URL is not set. Copy .env.example to .env, fill it in, "
            "and export it (bash: `set -a; source .env; set +a`).",
            file=sys.stderr,
        )
        sys.exit(2)
    return url


def _discover() -> list[Path]:
    files = []
    for p in sorted(MIGRATIONS_DIR.iterdir()):
        if p.is_file() and FILENAME_RE.match(p.name):
            files.append(p)
    return files


def _ensure_ledger(conn: psycopg.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version     TEXT PRIMARY KEY,
            filename    TEXT NOT NULL,
            applied_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )


def _applied(conn: psycopg.Connection) -> set[str]:
    rows = conn.execute("SELECT version FROM schema_migrations").fetchall()
    return {r[0] for r in rows}


def apply_pending(url: str | None = None) -> list[str]:
    """Apply every migration not yet in schema_migrations. Returns filenames applied."""
    url = url or _database_url()
    applied_now: list[str] = []
    with psycopg.connect(url, autocommit=False) as conn:
        _ensure_ledger(conn)
        conn.commit()
        done = _applied(conn)
        for path in _discover():
            version = FILENAME_RE.match(path.name).group(1)  # type: ignore[union-attr]
            if version in done:
                continue
            sql = path.read_text(encoding="utf-8")
            # Each migration runs in its own transaction; on failure nothing
            # from that file sticks and the ledger isn't updated.
            with conn.transaction():
                conn.execute(sql)  # type: ignore[arg-type]
                conn.execute(
                    "INSERT INTO schema_migrations (version, filename) VALUES (%s, %s)",
                    (version, path.name),
                )
            applied_now.append(path.name)
            print(f"[migrate] applied {path.name}")
    return applied_now


def status() -> None:
    url = _database_url()
    with psycopg.connect(url, autocommit=True) as conn:
        _ensure_ledger(conn)
        done = _applied(conn)
    files = _discover()
    if not files:
        print("(no migrations found)")
        return
    for path in files:
        version = FILENAME_RE.match(path.name).group(1)  # type: ignore[union-attr]
        mark = "applied" if version in done else "pending"
        print(f"  [{mark}] {path.name}")


if __name__ == "__main__":
    if "--status" in sys.argv:
        status()
    else:
        applied = apply_pending()
        if not applied:
            print("[migrate] nothing to apply")
        else:
            print(f"[migrate] done ({len(applied)} applied)")
