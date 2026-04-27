"""
Marketing DB helpers — thin SQL wrappers over the shared SQLite connection.

Product is a singleton (id='default') and stays in its own table because it
is form-edited config, not retrievable content. Drafts are stored as
`chunks` rows with kind='draft_post'; subtype fields (platform, topic,
variant_index, rationale, notes) live in `chunks.metadata`.
"""

import json
from typing import Any, Optional

from db import get_connection, now_utc
from models import Chunk, chunk_row_to_draft_dict
from chunks import insert_chunk, update_chunk as _update_chunk, delete_chunk as _delete_chunk
from .platforms import PLATFORMS

VALID_STATUSES = ("draft", "approved", "rejected", "posted")


# ── Product (singleton) ──────────────────────────────────────────────────────

def _row_to_product(row) -> dict:
    d = dict(row)
    for key in ("key_messages", "links"):
        val = d.get(key)
        if isinstance(val, str):
            try:
                d[key] = json.loads(val)
            except json.JSONDecodeError:
                d[key] = []
        elif val is None:
            d[key] = []
    return d


def get_product(product_id: str = "default") -> Optional[dict]:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM product WHERE id = ?", (product_id,)
        ).fetchone()
        return _row_to_product(row) if row else None
    finally:
        conn.close()


def upsert_product(
    name: str,
    one_liner: str = "",
    audience: str = "",
    tone: str = "",
    key_messages: Optional[list[str]] = None,
    links: Optional[list[dict]] = None,
    product_id: str = "default",
) -> dict:
    km = json.dumps(key_messages or [])
    ln = json.dumps(links or [])
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO product (id, name, one_liner, audience, tone,
                                 key_messages, links, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name,
                one_liner=excluded.one_liner,
                audience=excluded.audience,
                tone=excluded.tone,
                key_messages=excluded.key_messages,
                links=excluded.links,
                updated_at=excluded.updated_at
            """,
            (product_id, name, one_liner, audience, tone, km, ln, now_utc()),
        )
        conn.commit()
    finally:
        conn.close()
    return get_product(product_id)  # type: ignore[return-value]


# ── Drafts (stored as chunks where kind='draft_post') ────────────────────────

def save_drafts(platform: str, topic: str, drafts: list[dict]) -> list[dict]:
    """Persist a batch of freshly generated drafts. Returns the saved rows."""
    if platform not in PLATFORMS:
        raise ValueError(f"Unknown platform {platform!r}")

    saved: list[dict] = []
    for d in drafts:
        chunk = Chunk(
            department="marketing",
            kind="draft_post",
            title=topic,
            content=d.get("content", ""),
            source_kind="manual",
            metadata={
                "platform": platform,
                "topic": topic,
                "variant_index": int(d.get("variant_index", 0)),
                "rationale": d.get("rationale", ""),
                "notes": None,
            },
            status="draft",
        )
        persisted = insert_chunk(chunk)
        saved.append(_chunk_to_draft_dict_via_id(persisted.id))
    return [s for s in saved if s is not None]


def _chunk_to_draft_dict_via_id(chunk_id: str) -> Optional[dict]:
    """Re-read a chunk row from disk and map it to the Draft API shape."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM chunks WHERE id = ?", (chunk_id,)
        ).fetchone()
        return chunk_row_to_draft_dict(row) if row else None
    finally:
        conn.close()


def get_draft(draft_id: str) -> Optional[dict]:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM chunks WHERE id = ? AND kind = 'draft_post'",
            (draft_id,),
        ).fetchone()
        return chunk_row_to_draft_dict(row) if row else None
    finally:
        conn.close()


def list_drafts(
    platform: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
) -> list[dict]:
    if platform is not None and platform not in PLATFORMS:
        raise ValueError(f"Unknown platform {platform!r}")
    if status is not None and status not in VALID_STATUSES:
        raise ValueError(f"Unknown status {status!r}")
    if limit < 1 or limit > 500:
        raise ValueError("limit must be between 1 and 500")

    sql = "SELECT * FROM chunks WHERE department = 'marketing' AND kind = 'draft_post'"
    args: list[Any] = []
    if platform:
        # Filter on the JSON-encoded metadata column. SQLite ships json_extract
        # by default, so this works without extensions.
        sql += " AND json_extract(metadata, '$.platform') = ?"
        args.append(platform)
    if status:
        sql += " AND status = ?"
        args.append(status)
    sql += " ORDER BY created_at DESC LIMIT ?"
    args.append(limit)

    conn = get_connection()
    try:
        rows = conn.execute(sql, args).fetchall()
        return [chunk_row_to_draft_dict(r) for r in rows]
    finally:
        conn.close()


def update_draft(
    draft_id: str,
    content: Optional[str] = None,
    status: Optional[str] = None,
    rating: Optional[int] = None,
    notes: Optional[str] = None,
) -> Optional[dict]:
    if status is not None and status not in VALID_STATUSES:
        raise ValueError(f"Unknown status {status!r}")
    if rating is not None and not (1 <= rating <= 5):
        raise ValueError("rating must be 1-5")

    metadata_patch = {"notes": notes} if notes is not None else None
    updated = _update_chunk(
        draft_id,
        content=content,
        status=status,
        rating=rating,
        metadata_patch=metadata_patch,
    )
    if updated is None or updated.kind != "draft_post":
        return None
    return get_draft(draft_id)


def delete_draft(draft_id: str) -> bool:
    # Guard against deleting non-draft chunks via the marketing endpoint.
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT 1 FROM chunks WHERE id = ? AND kind = 'draft_post'",
            (draft_id,),
        ).fetchone()
        if not row:
            return False
    finally:
        conn.close()
    return _delete_chunk(draft_id)
