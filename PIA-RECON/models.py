"""
Watchdog data models. Plain dataclasses, no Pydantic overhead.
"""

from dataclasses import dataclass, field, asdict
from typing import Optional
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
class Hit:
    target_id: str
    title: str
    summary: str
    match_reason: str
    relevance_score: float
    source_url: Optional[str] = None
    raw_data: Optional[dict] = None
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    surfaced_at: Optional[str] = None
    seen: bool = False
    rating: Optional[int] = None

    def to_row(self) -> tuple:
        return (
            self.id,
            self.target_id,
            self.source_url,
            self.title,
            self.summary,
            self.match_reason,
            self.relevance_score,
            json.dumps(self.raw_data) if self.raw_data else None,
        )

    @classmethod
    def from_row(cls, row) -> "Hit":
        raw = row["raw_data"]
        return cls(
            id=row["id"],
            target_id=row["target_id"],
            source_url=row["source_url"],
            title=row["title"],
            summary=row["summary"],
            match_reason=row["match_reason"],
            relevance_score=row["relevance_score"],
            raw_data=json.loads(raw) if raw else None,
            surfaced_at=row["surfaced_at"],
            seen=bool(row["seen"]),
            rating=row["rating"],
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
