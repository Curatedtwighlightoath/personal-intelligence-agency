"""
PIA data models. Plain dataclasses, no Pydantic overhead.

`Chunk` is the universal atomic unit shared across departments. Subtype-
specific fields live in `metadata`. `WatchTarget` and `RawItem` remain
watchdog-specific (config and pre-evaluation transport, respectively).
"""

from dataclasses import dataclass, field, asdict
from typing import Any, Optional
import json
import uuid


@dataclass
class WatchTarget:
    name: str
    source_type: str  # 'rss', 'github_api'
    source_config: dict  # Source-specific config (URL, search params, etc.)
    match_criteria: str  # Natural language criteria for LLM matching
    cadence: str = "0 */6 * * *"  # Default: every 6 hours
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    enabled: bool = True
    last_checked_at: Optional[str] = None
    last_hit_at: Optional[str] = None
    consecutive_failures: int = 0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def to_row(self) -> tuple:
        """Return values tuple for SQLite INSERT."""
        return (
            self.id,
            self.name,
            self.source_type,
            json.dumps(self.source_config),
            self.match_criteria,
            self.cadence,
            self.enabled,
            self.last_checked_at,
            self.last_hit_at,
            self.consecutive_failures,
        )

    @classmethod
    def from_row(cls, row) -> "WatchTarget":
        """Construct from a sqlite3.Row."""
        return cls(
            id=row["id"],
            name=row["name"],
            source_type=row["source_type"],
            source_config=json.loads(row["source_config"]),
            match_criteria=row["match_criteria"],
            cadence=row["cadence"],
            enabled=bool(row["enabled"]),
            last_checked_at=row["last_checked_at"],
            last_hit_at=row["last_hit_at"],
            consecutive_failures=row["consecutive_failures"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Chunk:
    """
    Universal atomic unit. Persisted in the `chunks` table; subtype-specific
    fields live in `metadata`. Construct via the helpers in chunks.py rather
    than instantiating directly when possible.
    """
    department: str        # 'watchdog' | 'marketing' | 'rd'
    kind: str              # 'hit' | 'draft_post' | 'rd_note' | ...
    content: str = ""
    title: Optional[str] = None
    source_kind: Optional[str] = None   # 'url' | 'file' | 'manual' | ...
    source_ref: Optional[str] = None
    repo_ref: Optional[str] = None
    commit_sha: Optional[str] = None
    metadata: dict = field(default_factory=dict)
    parent_id: Optional[str] = None
    rating: Optional[int] = None
    status: str = "active"
    seen: bool = False
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def to_row(self) -> tuple:
        """Values tuple for the INSERT in chunks.insert_chunk."""
        return (
            self.id, self.department, self.kind, self.title, self.content,
            self.source_kind, self.source_ref, self.repo_ref, self.commit_sha,
            json.dumps(self.metadata or {}), self.parent_id,
            self.rating, self.status, self.seen,
        )

    @classmethod
    def from_row(cls, row) -> "Chunk":
        meta = row["metadata"]
        return cls(
            id=row["id"],
            department=row["department"],
            kind=row["kind"],
            title=row["title"],
            content=row["content"],
            source_kind=row["source_kind"],
            source_ref=row["source_ref"],
            repo_ref=row["repo_ref"],
            commit_sha=row["commit_sha"],
            metadata=json.loads(meta) if meta else {},
            parent_id=row["parent_id"],
            rating=row["rating"],
            status=row["status"],
            seen=bool(row["seen"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RawItem:
    """Normalized item returned by a source adapter, before LLM evaluation."""
    source_url: str
    title: str
    content: str  # Body text, description, or summary from source
    published_at: Optional[str] = None
    item_hash: str = ""  # For dedup — adapter should populate this
    raw_data: Optional[dict] = None  # Full original data for storage


# ── API-shape mappers ────────────────────────────────────────────────────────
# The frontend was built against pre-pivot Hit/Draft shapes. Map chunk rows
# back to those shapes here so the React side doesn't need to know we
# collapsed everything into `chunks`.

def chunk_row_to_hit_dict(row, target_name: Optional[str] = None) -> dict:
    """Map a chunks row (kind='hit') to the legacy Hit API shape."""
    meta = json.loads(row["metadata"]) if row["metadata"] else {}
    raw = meta.get("raw_data")
    out = {
        "id": row["id"],
        "target_id": meta.get("target_id"),
        "source_url": row["source_ref"],
        "title": row["title"],
        "summary": row["content"],
        "match_reason": meta.get("match_reason"),
        "relevance_score": meta.get("relevance_score"),
        "raw_data": raw,
        "surfaced_at": row["created_at"],
        "seen": bool(row["seen"]),
        "rating": row["rating"],
    }
    if target_name is not None:
        out["target_name"] = target_name
    return out


def chunk_row_to_draft_dict(row) -> dict:
    """Map a chunks row (kind='draft_post') to the legacy Draft API shape."""
    meta = json.loads(row["metadata"]) if row["metadata"] else {}
    return {
        "id": row["id"],
        "platform": meta.get("platform"),
        "topic": meta.get("topic", row["title"]),
        "content": row["content"],
        "rationale": meta.get("rationale"),
        "variant_index": int(meta.get("variant_index", 0)),
        "status": row["status"],
        "rating": row["rating"],
        "notes": meta.get("notes"),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
