"""
Thin helpers over the `chunks` table. Departments may also write inline SQL
when they need joins or filters not covered here — these helpers exist for
the common cases (insert, fetch by id, list-by-kind, update fields, delete).
"""

import json
import sqlite3
from typing import Any, Optional

from db import get_connection, now_utc
from models import Chunk


_INSERT_COLUMNS = (
    "id", "department", "kind", "title", "content",
    "source_kind", "source_ref", "repo_ref", "commit_sha",
    "metadata", "parent_id", "rating", "status", "seen",
)
_INSERT_SQL = (
    f"INSERT INTO chunks ({', '.join(_INSERT_COLUMNS)}) "
    f"VALUES ({', '.join(['?'] * len(_INSERT_COLUMNS))})"
)


def insert_chunk(chunk: Chunk, conn: Optional[sqlite3.Connection] = None) -> Chunk:
    """Persist a Chunk and return it with created_at/updated_at populated."""
    own = conn is None
    if own:
        conn = get_connection()
    try:
        conn.execute(_INSERT_SQL, chunk.to_row())
        if own:
            conn.commit()
        row = conn.execute(
            "SELECT * FROM chunks WHERE id = ?", (chunk.id,)
        ).fetchone()
        return Chunk.from_row(row)
    finally:
        if own:
            conn.close()


def get_chunk(chunk_id: str) -> Optional[Chunk]:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM chunks WHERE id = ?", (chunk_id,)
        ).fetchone()
        return Chunk.from_row(row) if row else None
    finally:
        conn.close()


def list_chunks(
    department: Optional[str] = None,
    kind: Optional[str] = None,
    status: Optional[str] = None,
    repo_ref: Optional[str] = None,
    limit: int = 100,
) -> list[Chunk]:
    clauses: list[str] = []
    args: list[Any] = []
    if department:
        clauses.append("department = ?"); args.append(department)
    if kind:
        clauses.append("kind = ?"); args.append(kind)
    if status:
        clauses.append("status = ?"); args.append(status)
    if repo_ref:
        clauses.append("repo_ref = ?"); args.append(repo_ref)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    args.append(limit)

    conn = get_connection()
    try:
        rows = conn.execute(
            f"SELECT * FROM chunks {where} ORDER BY created_at DESC LIMIT ?",
            args,
        ).fetchall()
        return [Chunk.from_row(r) for r in rows]
    finally:
        conn.close()


def update_chunk(
    chunk_id: str,
    *,
    content: Optional[str] = None,
    title: Optional[str] = None,
    status: Optional[str] = None,
    rating: Optional[int] = None,
    seen: Optional[bool] = None,
    metadata_patch: Optional[dict] = None,
    commit_sha: Optional[str] = None,
) -> Optional[Chunk]:
    """
    Update specified fields on a chunk. `metadata_patch` is shallow-merged
    into the existing metadata dict (pass {key: None} to clear a key).
    """
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM chunks WHERE id = ?", (chunk_id,)
        ).fetchone()
        if not row:
            return None

        fields: list[str] = []
        args: list[Any] = []
        if content is not None:
            fields.append("content = ?"); args.append(content)
        if title is not None:
            fields.append("title = ?"); args.append(title)
        if status is not None:
            fields.append("status = ?"); args.append(status)
        if rating is not None:
            fields.append("rating = ?"); args.append(rating)
        if seen is not None:
            fields.append("seen = ?"); args.append(seen)
        if commit_sha is not None:
            fields.append("commit_sha = ?"); args.append(commit_sha)
        if metadata_patch is not None:
            existing = json.loads(row["metadata"]) if row["metadata"] else {}
            existing.update(metadata_patch)
            fields.append("metadata = ?"); args.append(json.dumps(existing))

        if not fields:
            return Chunk.from_row(row)

        fields.append("updated_at = ?"); args.append(now_utc())
        args.append(chunk_id)
        conn.execute(
            f"UPDATE chunks SET {', '.join(fields)} WHERE id = ?", args,
        )
        conn.commit()

        row = conn.execute(
            "SELECT * FROM chunks WHERE id = ?", (chunk_id,)
        ).fetchone()
        return Chunk.from_row(row)
    finally:
        conn.close()


def delete_chunk(chunk_id: str) -> bool:
    conn = get_connection()
    try:
        cur = conn.execute("DELETE FROM chunks WHERE id = ?", (chunk_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()
