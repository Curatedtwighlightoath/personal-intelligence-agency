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
        """)
        conn.commit()
    finally:
        conn.close()


def now_utc() -> str:
    """ISO format UTC timestamp for SQLite storage."""
    return datetime.now(timezone.utc).isoformat()
