"""
R&D markdown notes.

Notes are written as `.md` files on disk and indexed as `chunks` rows
(department='rd', kind='rd_note'). The file is canonical — the chunk row
mirrors `content` for retrieval and stamps the commit SHA the note was
written against so future R&D sessions can detect staleness.

Layout:
    <repo_root>/.pia/notes/<slug>.md         when repo_root is given
    PIA-RECON/.pia/notes/_global/<slug>.md   when repo_root is None
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Optional

from db import DB_PATH, get_connection
from models import Chunk
from chunks import insert_chunk, update_chunk, get_chunk

NOTES_DIRNAME = ".pia/notes"
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(title: str) -> str:
    s = _SLUG_RE.sub("-", title.lower()).strip("-")
    return s or "note"


def _repo_head(repo_root: Path) -> Optional[str]:
    """Return the current HEAD SHA, or None if not a git repo."""
    try:
        out = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True, timeout=5,
        )
        return out.stdout.strip() or None
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return None


def _resolve_root(repo_root: Optional[Path]) -> tuple[Path, Optional[str], Optional[str]]:
    """
    Pick the directory the .pia/notes tree lives under, plus the repo_ref
    label and commit SHA to stamp on the chunk. Notes without a repo land
    under PIA-RECON/.pia/notes/_global/.
    """
    if repo_root is None:
        base = DB_PATH.parent / NOTES_DIRNAME / "_global"
        return base, None, None
    root = Path(repo_root).resolve()
    return root / NOTES_DIRNAME, root.name, _repo_head(root)


def _frontmatter(chunk: Chunk, tags: list[str]) -> str:
    lines = [
        "---",
        f"id: {chunk.id}",
        f"title: {chunk.title or ''}",
        f"repo: {chunk.repo_ref or ''}",
        f"commit_sha: {chunk.commit_sha or ''}",
        f"created_at: {chunk.created_at or ''}",
        f"tags: [{', '.join(tags)}]",
        "---",
        "",
    ]
    return "\n".join(lines)


def write_note(
    title: str,
    body: str,
    repo_root: Optional[Path | str] = None,
    tags: Optional[list[str]] = None,
) -> Chunk:
    """
    Persist a new R&D note. Creates the .md file under .pia/notes/, then
    inserts a chunk row pointing at it. Returns the persisted Chunk.
    """
    tags = tags or []
    base, repo_ref, commit_sha = _resolve_root(
        Path(repo_root) if repo_root else None
    )
    base.mkdir(parents=True, exist_ok=True)

    # The chunk id is client-generated, so we can derive the filename
    # before inserting and persist source_ref + metadata.file_path in one
    # write. Slug is for human readability; the id suffix is the stable
    # handle so on-disk renames never orphan the DB pointer.
    chunk = Chunk(
        department="rd",
        kind="rd_note",
        title=title,
        content=body,
        source_kind="file",
        repo_ref=repo_ref,
        commit_sha=commit_sha,
        metadata={"tags": tags},
    )
    slug = _slugify(title)
    filename = f"{slug}-{chunk.id[:8]}.md"
    file_path = base / filename
    rel_path = f"{NOTES_DIRNAME}/{'_global/' if repo_ref is None else ''}{filename}"

    chunk.source_ref = rel_path
    chunk.metadata["file_path"] = str(file_path)

    persisted = insert_chunk(chunk)
    file_path.write_text(_frontmatter(persisted, tags) + body, encoding="utf-8")
    return persisted


def update_note(
    chunk_id: str,
    body: Optional[str] = None,
    title: Optional[str] = None,
    tags: Optional[list[str]] = None,
    repo_root: Optional[Path | str] = None,
) -> Optional[Chunk]:
    """
    Re-write a note's body/title/tags. Re-stamps commit_sha (so the note
    advertises freshness against the repo it was edited under). The file
    on disk is rewritten in place using the existing source_ref.
    """
    existing = get_chunk(chunk_id)
    if existing is None or existing.kind != "rd_note":
        return None

    new_body = body if body is not None else existing.content
    new_title = title if title is not None else existing.title
    new_tags = tags if tags is not None else existing.metadata.get("tags", [])

    commit_sha = existing.commit_sha
    if repo_root is not None:
        commit_sha = _repo_head(Path(repo_root).resolve())

    metadata_patch = {"tags": new_tags}
    updated = update_chunk(
        chunk_id,
        content=new_body,
        title=new_title,
        commit_sha=commit_sha,
        metadata_patch=metadata_patch,
    )
    if updated is None:
        return None

    file_path = updated.metadata.get("file_path")
    if file_path:
        Path(file_path).write_text(
            _frontmatter(updated, new_tags) + new_body, encoding="utf-8"
        )
    return updated


def list_notes(repo_ref: Optional[str] = None) -> list[Chunk]:
    """Return rd_note chunks, optionally filtered to one repo."""
    sql = "SELECT * FROM chunks WHERE department = 'rd' AND kind = 'rd_note'"
    args: list = []
    if repo_ref is not None:
        sql += " AND repo_ref = ?"
        args.append(repo_ref)
    sql += " ORDER BY created_at DESC"
    conn = get_connection()
    try:
        rows = conn.execute(sql, args).fetchall()
        return [Chunk.from_row(r) for r in rows]
    finally:
        conn.close()
