"""
Watchdog SQLite database layer.
Single file, no ORM, no abstractions. Just SQL.
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

            CREATE TABLE IF NOT EXISTS hits (
                id TEXT PRIMARY KEY,
                target_id TEXT NOT NULL REFERENCES watch_targets(id),
                source_url TEXT,
                title TEXT,
                summary TEXT,
                match_reason TEXT,
                relevance_score REAL,
                raw_data JSON,
                surfaced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                seen BOOLEAN DEFAULT FALSE,
                rating INTEGER
            );

            CREATE TABLE IF NOT EXISTS seen_items (
                target_id TEXT NOT NULL REFERENCES watch_targets(id),
                item_hash TEXT NOT NULL,
                first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (target_id, item_hash)
            );

            CREATE INDEX IF NOT EXISTS idx_hits_target_id ON hits(target_id);
            CREATE INDEX IF NOT EXISTS idx_hits_surfaced_at ON hits(surfaced_at);
            CREATE INDEX IF NOT EXISTS idx_seen_items_target ON seen_items(target_id);

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

            -- Marketing: singleton product profile. TEXT PK leaves room to
            -- expand to multiple products later without a migration.
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

            -- Marketing: generated social-post drafts.
            CREATE TABLE IF NOT EXISTS draft_posts (
                id             TEXT PRIMARY KEY,
                platform       TEXT NOT NULL,
                topic          TEXT NOT NULL,
                content        TEXT NOT NULL,
                rationale      TEXT,
                variant_index  INTEGER DEFAULT 0,
                status         TEXT DEFAULT 'draft',
                rating         INTEGER,
                notes          TEXT,
                created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_drafts_platform ON draft_posts(platform);
            CREATE INDEX IF NOT EXISTS idx_drafts_status   ON draft_posts(status);
            CREATE INDEX IF NOT EXISTS idx_drafts_created  ON draft_posts(created_at);
        """)

        # Seed defaults — INSERT OR IGNORE so we never clobber user edits.
        # Watchdog defaults to Anthropic Sonnet to preserve pre-refactor
        # behavior. Marketing/rd rows are placeholders until those
        # departments ship; they're safe to edit now.
        conn.executemany(
            """INSERT OR IGNORE INTO department_config
               (department, provider, model, api_key_ref, base_url, extra)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [
                ("watchdog",  "anthropic", "claude-sonnet-4-20250514", "ANTHROPIC_API_KEY", None, "{}"),
                ("marketing", "anthropic", "claude-sonnet-4-20250514", "ANTHROPIC_API_KEY", None, "{}"),
                ("rd",        "anthropic", "claude-sonnet-4-20250514", "ANTHROPIC_API_KEY", None, "{}"),
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
