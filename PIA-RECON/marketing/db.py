"""
Marketing DB helpers — thin SQL wrappers over the shared Postgres connection.

Product is a singleton (id='default'). draft_posts rows are keyed by UUIDs
generated at insert time, consistent with watch_targets/hits.
"""

import uuid
from typing import Any, Optional

from db import get_connection, now_utc
from .platforms import PLATFORMS

VALID_STATUSES = ("draft", "approved", "rejected", "posted")


# ── Product (singleton) ──────────────────────────────────────────────────────

def _row_to_product(row) -> dict:
    d = dict(row)
    for key in ("key_messages", "links"):
        if d.get(key) is None:
            d[key] = []
    return d


def get_product(product_id: str = "default") -> Optional[dict]:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM product WHERE id = %s", (product_id,)
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
    km = key_messages or []
    ln = links or []
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO product (id, name, one_liner, audience, tone,
                                 key_messages, links, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
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


# ── Drafts ───────────────────────────────────────────────────────────────────

def save_drafts(platform: str, topic: str, drafts: list[dict]) -> list[dict]:
    """Persist a batch of freshly generated drafts. Returns the saved rows."""
    if platform not in PLATFORMS:
        raise ValueError(f"Unknown platform {platform!r}")

    saved_ids: list[str] = []
    ts = now_utc()
    conn = get_connection()
    try:
        for d in drafts:
            draft_id = str(uuid.uuid4())
            conn.execute(
                """
                INSERT INTO draft_posts
                    (id, platform, topic, content, rationale,
                     variant_index, status, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, 'draft', %s, %s)
                """,
                (
                    draft_id, platform, topic,
                    d.get("content", ""),
                    d.get("rationale", ""),
                    int(d.get("variant_index", 0)),
                    ts, ts,
                ),
            )
            saved_ids.append(draft_id)
        conn.commit()
    finally:
        conn.close()

    return [get_draft(i) for i in saved_ids if get_draft(i) is not None]  # type: ignore[misc]


def get_draft(draft_id: str) -> Optional[dict]:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM draft_posts WHERE id = %s", (draft_id,)
        ).fetchone()
        return dict(row) if row else None
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

    sql = "SELECT * FROM draft_posts"
    clauses: list[str] = []
    args: list[Any] = []
    if platform:
        clauses.append("platform = %s"); args.append(platform)
    if status:
        clauses.append("status = %s"); args.append(status)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY created_at DESC LIMIT %s"
    args.append(limit)

    conn = get_connection()
    try:
        rows = conn.execute(sql, args).fetchall()
        return [dict(r) for r in rows]
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

    fields: list[str] = []
    args: list[Any] = []
    if content is not None:
        fields.append("content = %s"); args.append(content)
    if status is not None:
        fields.append("status = %s"); args.append(status)
    if rating is not None:
        fields.append("rating = %s"); args.append(rating)
    if notes is not None:
        fields.append("notes = %s"); args.append(notes)

    if not fields:
        return get_draft(draft_id)

    fields.append("updated_at = %s"); args.append(now_utc())
    args.append(draft_id)

    conn = get_connection()
    try:
        cur = conn.execute(
            f"UPDATE draft_posts SET {', '.join(fields)} WHERE id = %s", args
        )
        conn.commit()
        if cur.rowcount == 0:
            return None
    finally:
        conn.close()

    return get_draft(draft_id)


def delete_draft(draft_id: str) -> bool:
    conn = get_connection()
    try:
        cur = conn.execute("DELETE FROM draft_posts WHERE id = %s", (draft_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()
