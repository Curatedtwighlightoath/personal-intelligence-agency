"""
PIA SQLite database layer.
Single file, no ORM, no abstractions. Just SQL.

Atomic unit across all departments is `chunks`. Department-specific subtypes
live in `chunks.kind` ('hit', 'draft_post', 'rd_note', ...) with subtype
metadata stored as JSON in `chunks.metadata`. Config/state tables
(watch_targets, seen_items, department_config, product) stay separate
because they aren't retrievable content.
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime, timezone

# Default DB path — override via environment or config later if needed
DB_PATH = Path(__file__).parent / "watchdog.db"


def get_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    """Get a SQLite connection with row factory enabled."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(db_path: Path = DB_PATH) -> None:
    """Create tables if they don't exist."""
    conn = get_connection(db_path)
    try:
        # Drop the pre-pivot atomic tables. Their data was test-only and the
        # rows have been folded into `chunks`. Safe no-op on fresh DBs.
        conn.executescript("""
            DROP TABLE IF EXISTS hits;
            DROP TABLE IF EXISTS draft_posts;
        """)

        conn.executescript("""
            CREATE TABLE IF NOT EXISTS watch_targets (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                source_type TEXT NOT NULL,
                source_config JSON NOT NULL,
                match_criteria TEXT NOT NULL,
                cadence TEXT NOT NULL,
                enabled BOOLEAN DEFAULT TRUE,
                last_checked_at TIMESTAMP,
                last_hit_at TIMESTAMP,
                consecutive_failures INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS seen_items (
                target_id TEXT NOT NULL REFERENCES watch_targets(id),
                item_hash TEXT NOT NULL,
                first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (target_id, item_hash)
            );

            CREATE INDEX IF NOT EXISTS idx_seen_items_target ON seen_items(target_id);

            -- Universal atomic unit. Every retrievable piece of content from
            -- any department lives here. Subtype-specific fields go in
            -- `metadata` (JSON). Columns are reserved only for fields the
            -- query layer filters or sorts on directly.
            --
            -- kind values currently in use:
            --   'hit'        — watchdog match; metadata: {target_id,
            --                  match_reason, relevance_score, raw_data}
            --   'draft_post' — marketing post draft; metadata:
            --                  {platform, variant_index, topic, rationale,
            --                   notes}
            --   'rd_note'    — R&D markdown note; the .md file on disk is
            --                  canonical, this row is the index. content
            --                  mirrors the file body. source_ref is the
            --                  repo-relative path; commit_sha is the HEAD
            --                  the note was written against (staleness).
            CREATE TABLE IF NOT EXISTS chunks (
                id           TEXT PRIMARY KEY,
                department   TEXT NOT NULL,
                kind         TEXT NOT NULL,
                title        TEXT,
                content      TEXT NOT NULL DEFAULT '',
                source_kind  TEXT,
                source_ref   TEXT,
                repo_ref     TEXT,
                commit_sha   TEXT,
                metadata     TEXT NOT NULL DEFAULT '{}',
                parent_id    TEXT REFERENCES chunks(id),
                embedding    BLOB,
                rating       INTEGER,
                status       TEXT NOT NULL DEFAULT 'active',
                seen         BOOLEAN NOT NULL DEFAULT FALSE,
                created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_chunks_dept_kind  ON chunks(department, kind);
            CREATE INDEX IF NOT EXISTS idx_chunks_created    ON chunks(created_at);
            CREATE INDEX IF NOT EXISTS idx_chunks_status     ON chunks(status);
            CREATE INDEX IF NOT EXISTS idx_chunks_repo       ON chunks(repo_ref);

            -- Per-department LLM configuration. api_key_ref stores the NAME of
            -- an environment variable (e.g. "ANTHROPIC_API_KEY"), never the
            -- secret itself. registry.get_provider() resolves it at call time.
            CREATE TABLE IF NOT EXISTS department_config (
                department   TEXT PRIMARY KEY,
                provider     TEXT NOT NULL,
                model        TEXT NOT NULL,
                api_key_ref  TEXT,
                base_url     TEXT,
                extra        TEXT,
                updated_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            -- Marketing: singleton product profile. Edited as a form, not a
            -- chunk — it's input to the drafter, not retrievable content.
            CREATE TABLE IF NOT EXISTS product (
                id            TEXT PRIMARY KEY,
                name          TEXT NOT NULL,
                one_liner     TEXT,
                audience      TEXT,
                tone          TEXT,
                key_messages  TEXT,   -- JSON array of strings
                links         TEXT,   -- JSON array of {label,url}
                updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Seed defaults — INSERT OR IGNORE so we never clobber user edits.
        # Default to Haiku 4.5 across departments: fast, cheap, and during
        # initial testing Sonnet 4 hit sustained `overloaded_error` while
        # Haiku responded immediately. Swap per-department via the
        # Departments UI or the providers CLI.
        conn.executemany(
            """INSERT OR IGNORE INTO department_config
               (department, provider, model, api_key_ref, base_url, extra)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [
                ("watchdog",  "anthropic", "claude-haiku-4-5-20251001", "ANTHROPIC_API_KEY", None, "{}"),
                ("marketing", "anthropic", "claude-haiku-4-5-20251001", "ANTHROPIC_API_KEY", None, "{}"),
                ("rd",        "anthropic", "claude-haiku-4-5-20251001", "ANTHROPIC_API_KEY", None, "{}"),
            ],
        )

        # Seed default product row so the marketing UI has something to edit
        # on first boot. INSERT OR IGNORE preserves user edits on re-init.
        conn.execute(
            """INSERT OR IGNORE INTO product
               (id, name, one_liner, audience, tone, key_messages, links)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            ("default", "My Product", "", "", "", "[]", "[]"),
        )
        conn.commit()
    finally:
        conn.close()


def now_utc() -> str:
    """ISO format UTC timestamp for SQLite storage."""
    return datetime.now(timezone.utc).isoformat()
