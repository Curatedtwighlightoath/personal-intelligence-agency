"""
PIA Dispatch API — FastAPI bridge to the Watchdog SQLite database.

Sits alongside the existing MCP server and run_checks.py.
All three share the same watchdog.db via db.py.

Usage:
    uvicorn api:app --host 0.0.0.0 --port 8000 --reload
"""

import json
import sys
import uuid
import asyncio
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from db import get_connection, init_db, now_utc
from models import WatchTarget, Hit

# ── Init ────────────────────────────────────────────────────────────────────

app = FastAPI(title="PIA Dispatch API", version="0.1.0")

# CORS — allow Vite dev server. In production behind the proxy this is unnecessary.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()


# ── Pydantic Models (request bodies) ───────────────────────────────────────

class TargetCreate(BaseModel):
    name: str
    source_type: str  # "rss" or "github_api"
    source_config: dict
    match_criteria: str
    cadence: str = "0 */6 * * *"

class TargetUpdate(BaseModel):
    name: Optional[str] = None
    source_config: Optional[dict] = None
    match_criteria: Optional[str] = None
    cadence: Optional[str] = None
    enabled: Optional[bool] = None

class RateBody(BaseModel):
    rating: int


# ── Targets ─────────────────────────────────────────────────────────────────

@app.get("/api/targets")
def list_targets():
    """Return all watch targets."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM watch_targets ORDER BY created_at DESC"
        ).fetchall()
        return [WatchTarget.from_row(r).to_dict() for r in rows]
    finally:
        conn.close()


@app.get("/api/targets/{target_id}")
def get_target(target_id: str):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM watch_targets WHERE id = ?", (target_id,)
        ).fetchone()
        if not row:
            raise HTTPException(404, f"Target not found: {target_id}")
        return WatchTarget.from_row(row).to_dict()
    finally:
        conn.close()


@app.post("/api/targets")
def create_target(body: TargetCreate):
    """Register a new watch target."""
    target = WatchTarget(
        name=body.name,
        source_type=body.source_type,
        source_config=body.source_config,
        match_criteria=body.match_criteria,
        cadence=body.cadence,
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
        # Re-fetch to get created_at/updated_at
        row = conn.execute(
            "SELECT * FROM watch_targets WHERE id = ?", (target.id,)
        ).fetchone()
        return WatchTarget.from_row(row).to_dict()
    finally:
        conn.close()


@app.put("/api/targets/{target_id}")
def update_target(target_id: str, body: TargetUpdate):
    """Update fields on an existing target."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM watch_targets WHERE id = ?", (target_id,)
        ).fetchone()
        if not row:
            raise HTTPException(404, f"Target not found: {target_id}")

        updates = body.model_dump(exclude_none=True)
        if not updates:
            raise HTTPException(400, "No fields to update")

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

        row = conn.execute(
            "SELECT * FROM watch_targets WHERE id = ?", (target_id,)
        ).fetchone()
        return WatchTarget.from_row(row).to_dict()
    finally:
        conn.close()


@app.delete("/api/targets/{target_id}")
def delete_target(target_id: str):
    """Permanently delete a target and its associated hits and seen_items."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM watch_targets WHERE id = ?", (target_id,)
        ).fetchone()
        if not row:
            raise HTTPException(404, f"Target not found: {target_id}")

        name = row["name"]
        conn.execute("DELETE FROM hits WHERE target_id = ?", (target_id,))
        conn.execute("DELETE FROM seen_items WHERE target_id = ?", (target_id,))
        conn.execute("DELETE FROM watch_targets WHERE id = ?", (target_id,))
        conn.commit()
        return {"status": "deleted", "target_id": target_id, "name": name}
    finally:
        conn.close()


@app.post("/api/targets/{target_id}/toggle")
def toggle_target(target_id: str):
    """Toggle enabled/disabled on a target."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM watch_targets WHERE id = ?", (target_id,)
        ).fetchone()
        if not row:
            raise HTTPException(404, f"Target not found: {target_id}")

        new_enabled = not bool(row["enabled"])
        conn.execute(
            "UPDATE watch_targets SET enabled = ?, updated_at = ? WHERE id = ?",
            (new_enabled, now_utc(), target_id),
        )
        conn.commit()

        row = conn.execute(
            "SELECT * FROM watch_targets WHERE id = ?", (target_id,)
        ).fetchone()
        return WatchTarget.from_row(row).to_dict()
    finally:
        conn.close()


# ── Hits ────────────────────────────────────────────────────────────────────

@app.get("/api/hits")
def list_hits(
    target_id: Optional[str] = None,
    unseen_only: bool = False,
    limit: int = 100,
):
    """Retrieve hits with optional filters. Includes target_name."""
    conn = get_connection()
    try:
        conditions = []
        params = []

        if target_id:
            conditions.append("h.target_id = ?")
            params.append(target_id)
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


@app.post("/api/hits/{hit_id}/rate")
def rate_hit(hit_id: str, body: RateBody):
    """Rate a hit 1-5 and mark as seen."""
    if not 1 <= body.rating <= 5:
        raise HTTPException(400, "Rating must be 1-5")

    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM hits WHERE id = ?", (hit_id,)).fetchone()
        if not row:
            raise HTTPException(404, f"Hit not found: {hit_id}")

        conn.execute(
            "UPDATE hits SET rating = ?, seen = TRUE WHERE id = ?",
            (body.rating, hit_id),
        )
        conn.commit()
        return {"status": "rated", "hit_id": hit_id, "rating": body.rating}
    finally:
        conn.close()


@app.post("/api/hits/{hit_id}/seen")
def mark_seen(hit_id: str):
    """Mark a single hit as seen."""
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM hits WHERE id = ?", (hit_id,)).fetchone()
        if not row:
            raise HTTPException(404, f"Hit not found: {hit_id}")

        conn.execute("UPDATE hits SET seen = TRUE WHERE id = ?", (hit_id,))
        conn.commit()
        return {"status": "seen", "hit_id": hit_id}
    finally:
        conn.close()


@app.post("/api/hits/mark-all-seen")
def mark_all_seen():
    """Mark all hits as seen."""
    conn = get_connection()
    try:
        result = conn.execute("UPDATE hits SET seen = TRUE WHERE seen = FALSE")
        conn.commit()
        return {"status": "ok", "updated": result.rowcount}
    finally:
        conn.close()


@app.delete("/api/hits/{hit_id}")
def delete_hit(hit_id: str):
    """Delete a single hit."""
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM hits WHERE id = ?", (hit_id,)).fetchone()
        if not row:
            raise HTTPException(404, f"Hit not found: {hit_id}")

        conn.execute("DELETE FROM hits WHERE id = ?", (hit_id,))
        conn.commit()
        return {"status": "deleted", "hit_id": hit_id}
    finally:
        conn.close()


# ── Run Checks ──────────────────────────────────────────────────────────────

@app.post("/api/run-check")
async def api_run_check(target_id: Optional[str] = None):
    """
    Trigger a check. Imports _check_single_target from server.py.
    Requires ANTHROPIC_API_KEY in environment for LLM matching.
    """
    # Lazy import to avoid loading MCP server machinery at API startup
    from server import _check_single_target

    conn = get_connection()
    try:
        if target_id:
            rows = conn.execute(
                "SELECT * FROM watch_targets WHERE id = ? AND enabled = TRUE",
                (target_id,),
            ).fetchall()
            if not rows:
                raise HTTPException(404, f"No enabled target: {target_id}")
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


# ── Stats ───────────────────────────────────────────────────────────────────

@app.get("/api/stats")
def get_stats():
    """Quick stats for the dashboard."""
    conn = get_connection()
    try:
        targets_total = conn.execute("SELECT COUNT(*) as c FROM watch_targets").fetchone()["c"]
        targets_active = conn.execute("SELECT COUNT(*) as c FROM watch_targets WHERE enabled = TRUE").fetchone()["c"]
        hits_total = conn.execute("SELECT COUNT(*) as c FROM hits").fetchone()["c"]
        hits_unseen = conn.execute("SELECT COUNT(*) as c FROM hits WHERE seen = FALSE").fetchone()["c"]
        seen_items = conn.execute("SELECT COUNT(*) as c FROM seen_items").fetchone()["c"]
        total_failures = conn.execute("SELECT COALESCE(SUM(consecutive_failures), 0) as c FROM watch_targets").fetchone()["c"]

        return {
            "targets_total": targets_total,
            "targets_active": targets_active,
            "hits_total": hits_total,
            "hits_unseen": hits_unseen,
            "seen_items": seen_items,
            "total_failures": total_failures,
        }
    finally:
        conn.close()


# ── Seed Import ─────────────────────────────────────────────────────────────

@app.post("/api/import-seed")
def import_seed():
    """Import targets from seed_targets.py, skipping duplicates by name."""
    from seed_targets import TARGETS as SEED_TARGETS

    conn = get_connection()
    try:
        added = 0
        skipped = 0
        for target in SEED_TARGETS:
            existing = conn.execute(
                "SELECT id FROM watch_targets WHERE name = ?", (target.name,)
            ).fetchone()
            if existing:
                skipped += 1
                continue

            conn.execute(
                """INSERT INTO watch_targets
                   (id, name, source_type, source_config, match_criteria, cadence,
                    enabled, last_checked_at, last_hit_at, consecutive_failures)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                target.to_row(),
            )
            added += 1

        conn.commit()
        return {"status": "ok", "added": added, "skipped": skipped}
    finally:
        conn.close()


# ── Health ──────────────────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    return {"status": "ok", "service": "pia-dispatch-api"}
