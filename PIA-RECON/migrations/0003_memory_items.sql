-- Unified atomic-unit table for all departments. A single table with a
-- `kind` discriminator keeps the schema simple until R&D's access patterns
-- reveal whether facts need to split into their own table (e.g. for a
-- UNIQUE (subject, predicate) constraint or temporal supersession logic).
--
-- Dimension is 1536 to match OpenAI text-embedding-3-small. Changing the
-- embedding provider in a way that changes dimension requires a new column
-- or a new table — re-embed content at that point.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS memory_items (
    id              TEXT PRIMARY KEY,
    department      TEXT NOT NULL,
    kind            TEXT NOT NULL,              -- 'doc', 'hit', 'draft', 'fact', ...
    subject         TEXT,                       -- optional key for fact-shaped rows
    text            TEXT NOT NULL,
    embedding       vector(1536),               -- NULL until embedded
    model_ref       TEXT,                       -- name of the model that produced `embedding`
    metadata        JSONB NOT NULL DEFAULT '{}'::jsonb,
    confidence      REAL,
    asserted_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    superseded_by   TEXT REFERENCES memory_items(id) ON DELETE SET NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_memory_items_dept_kind ON memory_items(department, kind);
CREATE INDEX IF NOT EXISTS idx_memory_items_subject   ON memory_items(subject) WHERE subject IS NOT NULL;

-- HNSW index for cosine-distance search. Partial so rows without embeddings
-- don't bloat the index. Rebuild with different opclass if you switch to
-- L2 or inner-product — pgvector indexes are per-operator.
CREATE INDEX IF NOT EXISTS idx_memory_items_embedding_hnsw
    ON memory_items USING hnsw (embedding vector_cosine_ops)
    WHERE embedding IS NOT NULL;
