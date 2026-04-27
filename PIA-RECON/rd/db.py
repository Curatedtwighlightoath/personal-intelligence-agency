"""
R&D DB wrappers — thin SQL over the shared `memory_items` table.

Public surface:
    ingest(text, metadata)        full pipeline: chunk → embed → store
                                  doc rows → extract facts → store fact rows
    add_doc_chunks(chunks, ...)   lower-level: persist pre-chunked text
    add_fact(...)                 persist a single manually-asserted fact
    search(query, ...)            cosine-distance retrieval with kind filter
    supersede(old_id, new_id)     mark an old fact replaced by a new one

Conventions:
- Department is always 'rd' here. The same table backs other departments
  (Watchdog can write `kind='hit'` rows from its own module later);
  this module only owns the R&D slice.
- Each ingest call mints a `source_id` (uuid). Every chunk row from that
  call carries `metadata.source_id = <uuid>`; every fact extracted from
  that text carries `metadata.source_doc_id = <same uuid>`. This is a
  metadata-only convention, not a FK — promote to a real column when
  fact-from-doc joins become hot (see MIGRATION_HANDOFF.md).
- pgvector adapter is registered per-connection. db.py registers
  JsonbDumper for `list` globally, so we MUST pass numpy arrays (not
  list[float]) for vector params, or they'd be sent as jsonb.
"""

import uuid
from typing import Any, Optional

import numpy as np
from pgvector.psycopg import register_vector

from db import get_connection, now_utc

from .chunker import chunk_text
from .embeddings import embed
from .extractor import extract_facts

DEPARTMENT = "rd"


# ── Internals ────────────────────────────────────────────────────────────────

def _connect():
    """Open a connection with pgvector adapter registered for this session."""
    conn = get_connection()
    register_vector(conn)
    return conn


def _row_to_dict(row) -> dict:
    """Convert a memory_items row to a plain dict, decoding the embedding."""
    d = dict(row)
    emb = d.get("embedding")
    if isinstance(emb, np.ndarray):
        # Don't ship raw vectors over the API by default — they're ~6KB
        # of float per row and clients almost never want them. Callers
        # that do can re-fetch with embedding included.
        d["embedding"] = None
    return d


# ── Doc chunks ──────────────────────────────────────────────────────────────

async def add_doc_chunks(
    chunks: list[str],
    metadata: Optional[dict] = None,
    model_ref: Optional[str] = None,
) -> list[str]:
    """
    Embed and persist a list of pre-chunked text fragments. Returns the
    new row ids in the same order as the inputs. Caller owns chunking.
    """
    if not chunks:
        return []

    embeddings = await embed(chunks)
    base_meta = dict(metadata or {})
    ts = now_utc()
    ids: list[str] = []

    conn = _connect()
    try:
        for i, (chunk, vec) in enumerate(zip(chunks, embeddings)):
            row_id = str(uuid.uuid4())
            row_meta = {**base_meta, "chunk_index": i}
            conn.execute(
                """
                INSERT INTO memory_items
                    (id, department, kind, subject, text, embedding,
                     model_ref, metadata, confidence, asserted_at,
                     created_at, updated_at)
                VALUES (%s, %s, 'doc', NULL, %s, %s,
                        %s, %s, NULL, %s, %s, %s)
                """,
                (row_id, DEPARTMENT, chunk, vec, model_ref, row_meta, ts, ts, ts),
            )
            ids.append(row_id)
        conn.commit()
    finally:
        conn.close()
    return ids


# ── Facts ────────────────────────────────────────────────────────────────────

async def add_fact(
    subject: str,
    statement: str,
    confidence: float,
    metadata: Optional[dict] = None,
    model_ref: Optional[str] = None,
) -> str:
    """
    Persist a single fact row with its embedding. Returns the new id.

    `subject` populates the indexed column; `statement` becomes the row's
    `text` and is what gets embedded for retrieval. Confidence is clamped
    to [0, 1] at write time so callers don't have to.
    """
    if not subject.strip() or not statement.strip():
        raise ValueError("subject and statement must be non-empty.")

    confidence = max(0.0, min(1.0, float(confidence)))
    [vec] = await embed([statement])

    row_id = str(uuid.uuid4())
    ts = now_utc()
    conn = _connect()
    try:
        conn.execute(
            """
            INSERT INTO memory_items
                (id, department, kind, subject, text, embedding,
                 model_ref, metadata, confidence, asserted_at,
                 created_at, updated_at)
            VALUES (%s, %s, 'fact', %s, %s, %s,
                    %s, %s, %s, %s, %s, %s)
            """,
            (
                row_id, DEPARTMENT, subject.strip(), statement.strip(), vec,
                model_ref, dict(metadata or {}), confidence, ts, ts, ts,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return row_id


def supersede(old_id: str, new_id: str) -> bool:
    """
    Mark `old_id` as superseded by `new_id`. Returns True if a row was
    updated. Both rows must already exist; ON DELETE SET NULL on the FK
    handles cleanup if the new row is later deleted.
    """
    if old_id == new_id:
        raise ValueError("A row cannot supersede itself.")
    conn = get_connection()
    try:
        cur = conn.execute(
            """
            UPDATE memory_items
               SET superseded_by = %s, updated_at = %s
             WHERE id = %s
            """,
            (new_id, now_utc(), old_id),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


# ── Ingest pipeline ──────────────────────────────────────────────────────────

async def ingest(text: str, metadata: Optional[dict] = None) -> dict:
    """
    Full ingest: chunk → embed → store doc rows → extract facts → store
    fact rows. Returns a summary the API can hand back to the caller.

    All chunks and facts from a single call share a `source_id` in their
    metadata so they can be retrieved as a group later. The extractor
    runs against the original (un-chunked) text — chunking is for
    retrieval granularity, not for context-window management.
    """
    if not text or not text.strip():
        raise ValueError("Cannot ingest empty text.")

    chunks = chunk_text(text)
    if not chunks:
        raise ValueError("Chunker produced no chunks from the provided text.")

    source_id = str(uuid.uuid4())
    base_meta = dict(metadata or {})
    base_meta["source_id"] = source_id

    chunk_ids = await add_doc_chunks(chunks, metadata=base_meta)

    facts = await extract_facts(text)
    fact_ids: list[str] = []
    for f in facts:
        fact_meta = {**(metadata or {}), "source_doc_id": source_id}
        fact_id = await add_fact(
            subject=f.subject,
            statement=f.statement,
            confidence=f.confidence,
            metadata=fact_meta,
        )
        fact_ids.append(fact_id)

    return {
        "source_id": source_id,
        "chunks": len(chunk_ids),
        "facts": len(fact_ids),
        "chunk_ids": chunk_ids,
        "fact_ids": fact_ids,
    }


# ── Search ───────────────────────────────────────────────────────────────────

async def search(
    query: str,
    kind: Optional[str] = None,
    k: int = 10,
    include_superseded: bool = False,
) -> list[dict]:
    """
    Cosine-distance search over R&D memory. `kind` filters to 'doc' or
    'fact' (or None for both). Superseded facts are hidden by default.

    Returns rows enriched with a `distance` field (lower is better;
    cosine distance is in [0, 2]). Embeddings are stripped from the
    response — callers that need them can fetch the row by id.
    """
    if not query or not query.strip():
        raise ValueError("Cannot search with an empty query.")
    if k < 1 or k > 200:
        raise ValueError("k must be between 1 and 200.")
    if kind is not None and kind not in ("doc", "fact"):
        raise ValueError(f"Unsupported kind {kind!r}. Use 'doc' or 'fact'.")

    [qvec] = await embed([query])

    clauses = ["department = %s", "embedding IS NOT NULL"]
    args: list[Any] = [DEPARTMENT]
    if kind is not None:
        clauses.append("kind = %s")
        args.append(kind)
    if not include_superseded:
        clauses.append("superseded_by IS NULL")

    sql = f"""
        SELECT id, department, kind, subject, text, metadata, confidence,
               asserted_at, superseded_by, created_at, updated_at,
               embedding <=> %s AS distance
          FROM memory_items
         WHERE {' AND '.join(clauses)}
         ORDER BY embedding <=> %s
         LIMIT %s
    """
    # qvec appears twice: once for the SELECT distance, once for ORDER BY.
    params = [qvec] + args + [qvec, k]

    conn = _connect()
    try:
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()

    return [_row_to_dict(r) for r in rows]
