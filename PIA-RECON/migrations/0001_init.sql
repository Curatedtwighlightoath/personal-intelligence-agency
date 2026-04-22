-- Initial schema. Parity with the old SQLite layout, with proper Postgres
-- types: jsonb, boolean, timestamptz. json column helpers in application
-- code (manual json.dumps/loads) can be removed — psycopg3 adapts dicts
-- directly into jsonb parameters and returns dicts on read.

CREATE TABLE IF NOT EXISTS watch_targets (
    id                    TEXT PRIMARY KEY,
    name                  TEXT NOT NULL,
    source_type           TEXT NOT NULL,
    source_config         JSONB NOT NULL,
    match_criteria        TEXT NOT NULL,
    cadence               TEXT NOT NULL,
    enabled               BOOLEAN NOT NULL DEFAULT TRUE,
    last_checked_at       TIMESTAMPTZ,
    last_hit_at           TIMESTAMPTZ,
    consecutive_failures  INTEGER NOT NULL DEFAULT 0,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS hits (
    id               TEXT PRIMARY KEY,
    target_id        TEXT NOT NULL REFERENCES watch_targets(id) ON DELETE CASCADE,
    source_url       TEXT,
    title            TEXT,
    summary          TEXT,
    match_reason     TEXT,
    relevance_score  REAL,
    raw_data         JSONB,
    surfaced_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    seen             BOOLEAN NOT NULL DEFAULT FALSE,
    rating           INTEGER
);

CREATE TABLE IF NOT EXISTS seen_items (
    target_id      TEXT NOT NULL REFERENCES watch_targets(id) ON DELETE CASCADE,
    item_hash      TEXT NOT NULL,
    first_seen_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (target_id, item_hash)
);

CREATE INDEX IF NOT EXISTS idx_hits_target_id    ON hits(target_id);
CREATE INDEX IF NOT EXISTS idx_hits_surfaced_at  ON hits(surfaced_at);
CREATE INDEX IF NOT EXISTS idx_seen_items_target ON seen_items(target_id);

-- Per-department LLM configuration. api_key_ref stores the NAME of an
-- environment variable (e.g. "ANTHROPIC_API_KEY"), never the secret itself.
-- providers.registry resolves it at call time.
CREATE TABLE IF NOT EXISTS department_config (
    department   TEXT PRIMARY KEY,
    provider     TEXT NOT NULL,
    model        TEXT NOT NULL,
    api_key_ref  TEXT,
    base_url     TEXT,
    extra        JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Marketing: singleton product profile. TEXT PK leaves room to expand to
-- multiple products later without a migration.
CREATE TABLE IF NOT EXISTS product (
    id            TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    one_liner     TEXT,
    audience      TEXT,
    tone          TEXT,
    key_messages  JSONB NOT NULL DEFAULT '[]'::jsonb,
    links         JSONB NOT NULL DEFAULT '[]'::jsonb,
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Marketing: generated social-post drafts.
CREATE TABLE IF NOT EXISTS draft_posts (
    id             TEXT PRIMARY KEY,
    platform       TEXT NOT NULL,
    topic          TEXT NOT NULL,
    content        TEXT NOT NULL,
    rationale      TEXT,
    variant_index  INTEGER NOT NULL DEFAULT 0,
    status         TEXT NOT NULL DEFAULT 'draft',
    rating         INTEGER,
    notes          TEXT,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_drafts_platform ON draft_posts(platform);
CREATE INDEX IF NOT EXISTS idx_drafts_status   ON draft_posts(status);
CREATE INDEX IF NOT EXISTS idx_drafts_created  ON draft_posts(created_at);
