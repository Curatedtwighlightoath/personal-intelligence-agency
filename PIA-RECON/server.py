"""
pia-recon-watchdog MCP Server

Exposes tools for managing watch targets and retrieving hits.
Run with: python server.py (stdio transport)
"""

import json
import sys
from pathlib import Path
from typing import Optional

from mcp.server.fastmcp import FastMCP

from db import get_connection, init_db, now_utc, DB_PATH
from models import WatchTarget, Hit
from adapters import fetch_source, ADAPTERS
from matcher import evaluate_batch

# ── Server Init ──────────────────────────────────────────────────────────────

mcp = FastMCP("pia-recon-watchdog")

# Initialize DB on import
init_db()


# ── Tools ────────────────────────────────────────────────────────────────────

@mcp.tool()
def add_watch_target(
    name: str,
    source_type: str,
    source_config: dict,
    match_criteria: str,
    cadence: str = "0 */6 * * *",
) -> dict:
    """
    Register a new watch target.

    Args:
        name: Human-readable label (e.g. "Anthropic Blog Releases")
        source_type: Adapter type — one of: rss, github_api
        source_config: Source-specific config dict. 
            For rss: {"feed_url": "https://...", "max_items": 20}
            For github_api: {"owner": "anthropics", "repo": "claude-code", "watch_type": "releases"}
        match_criteria: Natural language description of what constitutes a match.
            Example: "New releases related to Claude models or MCP protocol"
        cadence: Cron expression for check frequency. Default: every 6 hours.
    
    Returns:
        The created watch target as a dict.
    """
    if source_type not in ADAPTERS:
        available = ", ".join(ADAPTERS.keys())
        return {"error": f"Unknown source_type '{source_type}'. Available: {available}"}

    target = WatchTarget(
        name=name,
        source_type=source_type,
        source_config=source_config,
        match_criteria=match_criteria,
        cadence=cadence,
    )

    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO watch_targets 
               (id, name, source_type, source_config, match_criteria, cadence, 
                enabled, last_checked_at, last_hit_at, consecutive_failures)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            target.to_row(),
        )
        conn.commit()
    finally:
        conn.close()

    return target.to_dict()


@mcp.tool()
def list_watch_targets(enabled_only: bool = False) -> list[dict]:
    """
    List all watch targets with their current status.

    Args:
        enabled_only: If True, only return enabled targets.
    
    Returns:
        List of watch target dicts.
    """
    conn = get_connection()
    try:
        query = "SELECT * FROM watch_targets"
        if enabled_only:
            query += " WHERE enabled = TRUE"
        query += " ORDER BY created_at DESC"
        rows = conn.execute(query).fetchall()
        return [WatchTarget.from_row(r).to_dict() for r in rows]
    finally:
        conn.close()


@mcp.tool()
def update_watch_target(target_id: str, updates: dict) -> dict:
    """
    Modify a watch target's configuration.

    Args:
        target_id: UUID of the target to update.
        updates: Dict of fields to update. Valid fields: 
                 name, source_config, match_criteria, cadence, enabled

    Returns:
        The updated watch target dict, or error.
    """
    allowed_fields = {"name", "source_config", "match_criteria", "cadence", "enabled"}
    invalid = set(updates.keys()) - allowed_fields
    if invalid:
        return {"error": f"Cannot update fields: {invalid}. Allowed: {allowed_fields}"}

    conn = get_connection()
    try:
        # Check target exists
        row = conn.execute("SELECT * FROM watch_targets WHERE id = ?", (target_id,)).fetchone()
        if not row:
            return {"error": f"No target found with id: {target_id}"}

        # Build dynamic UPDATE
        set_clauses = []
        values = []
        for field, value in updates.items():
            if field == "source_config":
                value = json.dumps(value)
            set_clauses.append(f"{field} = ?")
            values.append(value)
        
        set_clauses.append("updated_at = ?")
        values.append(now_utc())
        values.append(target_id)

        conn.execute(
            f"UPDATE watch_targets SET {', '.join(set_clauses)} WHERE id = ?",
            values,
        )
        conn.commit()

        row = conn.execute("SELECT * FROM watch_targets WHERE id = ?", (target_id,)).fetchone()
        return WatchTarget.from_row(row).to_dict()
    finally:
        conn.close()


@mcp.tool()
def remove_watch_target(target_id: str) -> dict:
    """
    Deactivate a watch target (sets enabled=False, does not delete).

    Args:
        target_id: UUID of the target to deactivate.
    
    Returns:
        Confirmation dict.
    """
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM watch_targets WHERE id = ?", (target_id,)).fetchone()
        if not row:
            return {"error": f"No target found with id: {target_id}"}

        conn.execute(
            "UPDATE watch_targets SET enabled = FALSE, updated_at = ? WHERE id = ?",
            (now_utc(), target_id),
        )
        conn.commit()
        return {"status": "deactivated", "target_id": target_id, "name": row["name"]}
    finally:
        conn.close()


@mcp.tool()
async def run_check(target_id: Optional[str] = None) -> dict:
    """
    Manually trigger a check for one or all enabled targets.

    Args:
        target_id: UUID of a specific target, or None to check all enabled targets.
    
    Returns:
        Summary of check results including any new hits.
    """
    conn = get_connection()
    try:
        if target_id:
            rows = conn.execute(
                "SELECT * FROM watch_targets WHERE id = ? AND enabled = TRUE", 
                (target_id,)
            ).fetchall()
            if not rows:
                return {"error": f"No enabled target found with id: {target_id}"}
        else:
            rows = conn.execute(
                "SELECT * FROM watch_targets WHERE enabled = TRUE"
            ).fetchall()
        
        targets = [WatchTarget.from_row(r) for r in rows]
    finally:
        conn.close()

    results = []
    for target in targets:
        result = await _check_single_target(target)
        results.append(result)

    total_hits = sum(r.get("new_hits", 0) for r in results)
    return {
        "targets_checked": len(results),
        "total_new_hits": total_hits,
        "results": results,
    }


async def _check_single_target(target: WatchTarget) -> dict:
    """Run the full check loop for a single target."""
    conn = get_connection()
    try:
        # 1. Fetch raw items from source
        try:
            raw_items = await fetch_source(target.source_type, target.source_config)
        except NotImplementedError:
            return {
                "target": target.name,
                "status": "adapter_not_implemented",
                "message": f"Adapter '{target.source_type}' is stubbed out — implement it to run checks.",
            }
        except Exception as e:
            # Increment failure counter
            conn.execute(
                """UPDATE watch_targets 
                   SET consecutive_failures = consecutive_failures + 1,
                       last_checked_at = ?, updated_at = ?
                   WHERE id = ?""",
                (now_utc(), now_utc(), target.id),
            )
            conn.commit()
            return {"target": target.name, "status": "fetch_error", "error": str(e)}

        # 2. Dedup — filter out items we've already seen
        new_items = []
        for item in raw_items:
            if not item.item_hash:
                continue
            exists = conn.execute(
                "SELECT 1 FROM seen_items WHERE target_id = ? AND item_hash = ?",
                (target.id, item.item_hash),
            ).fetchone()
            if not exists:
                new_items.append(item)

        if not new_items:
            conn.execute(
                "UPDATE watch_targets SET last_checked_at = ?, consecutive_failures = 0, updated_at = ? WHERE id = ?",
                (now_utc(), now_utc(), target.id),
            )
            conn.commit()
            return {"target": target.name, "status": "ok", "new_items": 0, "new_hits": 0}

        # 3. LLM matching
        try:
            matches = await evaluate_batch(new_items, target.match_criteria)
        except NotImplementedError:
            return {
                "target": target.name,
                "status": "matcher_not_implemented",
                "new_items": len(new_items),
                "message": "LLM matcher is stubbed out — implement it to score items.",
            }

        # 4. Store hits and mark items as seen
        for item, match in matches:
            hit = Hit(
                target_id=target.id,
                title=item.title,
                summary=match.summary,
                match_reason=match.reason,
                relevance_score=match.relevance_score,
                source_url=item.source_url,
                raw_data=item.raw_data,
            )
            conn.execute(
                """INSERT INTO hits 
                   (id, target_id, source_url, title, summary, match_reason, relevance_score, raw_data)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                hit.to_row(),
            )

        # Mark all new items (matched or not) as seen
        for item in new_items:
            if item.item_hash:
                conn.execute(
                    "INSERT OR IGNORE INTO seen_items (target_id, item_hash) VALUES (?, ?)",
                    (target.id, item.item_hash),
                )

        # 5. Update target status
        update_fields = {
            "last_checked_at": now_utc(),
            "consecutive_failures": 0,
            "updated_at": now_utc(),
        }
        if matches:
            update_fields["last_hit_at"] = now_utc()

        conn.execute(
            """UPDATE watch_targets 
               SET last_checked_at = ?, consecutive_failures = 0, 
                   last_hit_at = COALESCE(?, last_hit_at), updated_at = ?
               WHERE id = ?""",
            (
                update_fields["last_checked_at"],
                update_fields.get("last_hit_at"),
                update_fields["updated_at"],
                target.id,
            ),
        )
        conn.commit()

        return {
            "target": target.name,
            "status": "ok",
            "new_items": len(new_items),
            "new_hits": len(matches),
            "hits": [
                {"title": item.title, "score": match.relevance_score, "reason": match.reason}
                for item, match in matches
            ],
        }
    finally:
        conn.close()


@mcp.tool()
def get_hits(
    target_id: Optional[str] = None,
    since: Optional[str] = None,
    unseen_only: bool = False,
    limit: int = 50,
) -> list[dict]:
    """
    Retrieve recent hits/matches.

    Args:
        target_id: Filter to a specific watch target. None for all.
        since: ISO datetime string — only return hits after this time.
        unseen_only: If True, only return hits Nick hasn't reviewed yet.
        limit: Max number of hits to return. Default 50.
    
    Returns:
        List of hit dicts, newest first.
    """
    conn = get_connection()
    try:
        conditions = []
        params = []

        if target_id:
            conditions.append("h.target_id = ?")
            params.append(target_id)
        if since:
            conditions.append("h.surfaced_at > ?")
            params.append(since)
        if unseen_only:
            conditions.append("h.seen = FALSE")

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        query = f"""
            SELECT h.*, wt.name as target_name 
            FROM hits h
            JOIN watch_targets wt ON h.target_id = wt.id
            {where}
            ORDER BY h.surfaced_at DESC
            LIMIT ?
        """
        params.append(limit)

        rows = conn.execute(query, params).fetchall()
        results = []
        for row in rows:
            hit = Hit.from_row(row)
            d = hit.to_dict()
            d["target_name"] = row["target_name"]
            results.append(d)
        return results
    finally:
        conn.close()


@mcp.tool()
def rate_hit(hit_id: str, rating: int) -> dict:
    """
    Rate a hit 1-5 for feedback/calibration.

    Args:
        hit_id: UUID of the hit to rate.
        rating: 1-5 score (1=irrelevant, 5=exactly what I wanted).
    
    Returns:
        Confirmation dict.
    """
    if not 1 <= rating <= 5:
        return {"error": "Rating must be between 1 and 5"}

    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM hits WHERE id = ?", (hit_id,)).fetchone()
        if not row:
            return {"error": f"No hit found with id: {hit_id}"}

        conn.execute(
            "UPDATE hits SET rating = ?, seen = TRUE WHERE id = ?",
            (rating, hit_id),
        )
        conn.commit()
        return {"status": "rated", "hit_id": hit_id, "rating": rating}
    finally:
        conn.close()


# ── Marketing Tools ──────────────────────────────────────────────────────────
# Mirror the HTTP API so agentic MCP clients can drive the marketing
# department directly. All helpers live in marketing/ — this file just
# wires them into FastMCP tool definitions.

from marketing import db as _mdb
from marketing.platforms import PLATFORMS as _PLATFORMS
from marketing.drafter import draft_posts as _draft_posts


@mcp.tool()
def get_product() -> dict:
    """Return the current product profile (singleton row id='default')."""
    product = _mdb.get_product()
    return product or {"error": "No product row found"}


@mcp.tool()
def set_product(
    name: str,
    one_liner: str = "",
    audience: str = "",
    tone: str = "",
    key_messages: Optional[list[str]] = None,
    links: Optional[list[dict]] = None,
) -> dict:
    """
    Upsert the singleton product profile used by the marketing drafter.

    Args:
        name: Product name (required).
        one_liner: One-sentence description.
        audience: Who the product is for.
        tone: Desired brand voice (e.g. "direct, technical").
        key_messages: List of short talking points.
        links: List of {label, url} dicts.
    """
    return _mdb.upsert_product(
        name=name,
        one_liner=one_liner,
        audience=audience,
        tone=tone,
        key_messages=key_messages or [],
        links=links or [],
    )


@mcp.tool()
async def draft_social_posts(
    platform: str,
    topic: str,
    variants: int = 3,
) -> list[dict]:
    """
    Generate and persist N social-post variants for a platform + topic.

    Args:
        platform: One of 'twitter', 'linkedin', 'instagram', 'tiktok'.
        topic: The angle or subject the post should cover.
        variants: Number of variants to generate (1-5).

    Returns:
        List of saved draft rows.
    """
    if platform not in _PLATFORMS:
        return [{"error": f"Unknown platform '{platform}'. "
                          f"Supported: {list(_PLATFORMS.keys())}"}]
    if not (1 <= variants <= 5):
        return [{"error": "variants must be between 1 and 5"}]

    product = _mdb.get_product() or {
        "name": "(unset)", "one_liner": "", "audience": "", "tone": "",
        "key_messages": [], "links": [],
    }
    try:
        drafts = await _draft_posts(
            platform=platform, topic=topic, product=product, variants=variants,
        )
    except Exception as e:
        return [{"error": f"Draft generation failed: {e}"}]

    return _mdb.save_drafts(platform, topic, drafts)


@mcp.tool()
def list_drafts(
    platform: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
) -> list[dict]:
    """List persisted draft posts, optionally filtered by platform/status."""
    try:
        return _mdb.list_drafts(platform=platform, status=status, limit=limit)
    except ValueError as e:
        return [{"error": str(e)}]


@mcp.tool()
def update_draft(
    draft_id: str,
    content: Optional[str] = None,
    status: Optional[str] = None,
    rating: Optional[int] = None,
    notes: Optional[str] = None,
) -> dict:
    """
    Update fields on a persisted draft.

    Args:
        draft_id: UUID of the draft.
        content: Overwrite the post text.
        status: One of 'draft', 'approved', 'rejected', 'posted'.
        rating: 1-5 user rating.
        notes: Freeform notes.
    """
    try:
        updated = _mdb.update_draft(
            draft_id, content=content, status=status, rating=rating, notes=notes,
        )
    except ValueError as e:
        return {"error": str(e)}
    return updated or {"error": f"Draft not found: {draft_id}"}


@mcp.tool()
def delete_draft(draft_id: str) -> dict:
    """Delete a draft post by id."""
    if not _mdb.delete_draft(draft_id):
        return {"error": f"Draft not found: {draft_id}"}
    return {"status": "deleted", "draft_id": draft_id}


# ── Entry Point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"[watchdog] Starting pia-recon-watchdog MCP server", file=sys.stderr)
    print(f"[watchdog] DB: {DB_PATH}", file=sys.stderr)
    print(f"[watchdog] Registered adapters: {list(ADAPTERS.keys())}", file=sys.stderr)
    mcp.run(transport="stdio")
