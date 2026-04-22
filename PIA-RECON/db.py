"""
Postgres + pgvector database layer. Thin wrapper over psycopg3.
Single file, no ORM. SQL lives next to the callers.

Public surface kept identical to the prior SQLite module:
    get_connection() -> psycopg.Connection   (row_factory=dict_row)
    init_db()                                 (delegates to migrations.runner)
    now_utc()         -> datetime             (tz-aware UTC)

Placeholders are '%s' (not '?'). jsonb columns adapt to/from Python
dicts and lists automatically — callers should not json.dumps() them.
"""

import os
from datetime import datetime, timezone

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import JsonbDumper

# Map Python dict/list → jsonb on writes. Without this, psycopg3 sends
# dicts as `json` (works against jsonb via implicit cast) but lists are
# treated as Postgres arrays and fail on jsonb columns. Reads come back
# as Python dict/list automatically via the JsonbLoader.
psycopg.adapters.register_dumper(dict, JsonbDumper)
psycopg.adapters.register_dumper(list, JsonbDumper)


def _database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. Copy .env.example to .env, fill in "
            "DATABASE_URL, and export it before starting the API."
        )
    return url


def get_connection() -> psycopg.Connection:
    """
    Open a Postgres connection with dict-like row access. Matches the
    row['col'] pattern callers were using under sqlite3's Row factory.

    Autocommit is off — writes require explicit .commit(), same as the
    prior sqlite3 convention. Closing a connection rolls back any open
    transaction, so read-only callers that just .close() are safe.
    """
    return psycopg.connect(_database_url(), row_factory=dict_row)


def init_db() -> None:
    """
    Apply any pending migrations. Kept under this name for drop-in
    compatibility with existing callers (api.py lifespan, run_checks.py,
    seed_targets.py, providers/cli.py). Migrations live under
    PIA-RECON/migrations/NNNN_*.sql and are tracked in schema_migrations.
    """
    from migrations.runner import apply_pending
    apply_pending()


def now_utc() -> datetime:
    """
    Timezone-aware UTC datetime. psycopg3 adapts this into timestamptz
    on write. Previously returned an ISO string under SQLite; call sites
    that pass it straight into a parameter work unchanged.
    """
    return datetime.now(timezone.utc)
