"""
PIA Dispatch API — FastAPI bridge to the Watchdog Postgres database.

Sits alongside the existing MCP server and run_checks.py.
All three share the same Postgres instance via db.py.

Usage:
    uvicorn api:app --host 0.0.0.0 --port 8000 --reload
"""

import os
import sys
import uuid
import asyncio
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from db import get_connection, init_db, now_utc
from models import WatchTarget, Hit, RawItem
from providers import ALLOWED_PROVIDERS
from scheduler import start_scheduler, shutdown_scheduler, reload_from_db


def _log_env_presence() -> None:
    """
    Log which api_key_ref env vars referenced by department_config are set.
    Prints only NAME=present|missing — never the value, length, or prefix.
    A missing value means the provider for that department will fail at
    first call; fix by exporting the var before launching uvicorn.
    """
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT DISTINCT api_key_ref FROM department_config "
            "WHERE api_key_ref IS NOT NULL AND api_key_ref != ''"
        ).fetchall()
    finally:
        conn.close()
    if not rows:
        return
    parts = [
        f"{r['api_key_ref']}={'present' if os.environ.get(r['api_key_ref']) else 'missing'}"
        for r in rows
    ]
    print("env check: " + " ".join(parts), flush=True)


# ── Init ────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(_app: FastAPI):
    # APScheduler is started here (not in server.py) because the MCP server
    # is for stdio tool calls, not long-running background work. Running
    # both `uvicorn api:app` and the MCP server in separate processes is
    # the intended deployment — only api.py owns the schedule.
    init_db()
    _log_env_presence()
    start_scheduler()
    try:
        yield
    finally:
        shutdown_scheduler()


app = FastAPI(title="PIA Dispatch API", version="0.1.0", lifespan=lifespan)

# CORS — allow Vite dev server. In production behind the proxy this is unnecessary.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

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

class DepartmentConfigUpdate(BaseModel):
    provider: str
    model: str
    api_key_ref: Optional[str] = None
    base_url: Optional[str] = None
    extra: Optional[dict] = None


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
            "SELECT * FROM watch_targets WHERE id = %s", (target_id,)
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
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            target.to_row(),
        )
        conn.commit()
        # Re-fetch to get created_at/updated_at
        row = conn.execute(
            "SELECT * FROM watch_targets WHERE id = %s", (target.id,)
        ).fetchone()
        result = WatchTarget.from_row(row).to_dict()
    finally:
        conn.close()
    reload_from_db()
    return result


@app.put("/api/targets/{target_id}")
def update_target(target_id: str, body: TargetUpdate):
    """Update fields on an existing target."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM watch_targets WHERE id = %s", (target_id,)
        ).fetchone()
        if not row:
            raise HTTPException(404, f"Target not found: {target_id}")

        updates = body.model_dump(exclude_none=True)
        if not updates:
            raise HTTPException(400, "No fields to update")

        set_clauses = []
        values = []
        for field, value in updates.items():
            set_clauses.append(f"{field} = %s")
            values.append(value)

        set_clauses.append("updated_at = %s")
        values.append(now_utc())
        values.append(target_id)

        conn.execute(
            f"UPDATE watch_targets SET {', '.join(set_clauses)} WHERE id = %s",
            values,
        )
        conn.commit()

        row = conn.execute(
            "SELECT * FROM watch_targets WHERE id = %s", (target_id,)
        ).fetchone()
        result = WatchTarget.from_row(row).to_dict()
    finally:
        conn.close()
    reload_from_db()
    return result


@app.delete("/api/targets/{target_id}")
def delete_target(target_id: str):
    """Permanently delete a target and its associated hits and seen_items."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM watch_targets WHERE id = %s", (target_id,)
        ).fetchone()
        if not row:
            raise HTTPException(404, f"Target not found: {target_id}")

        name = row["name"]
        conn.execute("DELETE FROM hits WHERE target_id = %s", (target_id,))
        conn.execute("DELETE FROM seen_items WHERE target_id = %s", (target_id,))
        conn.execute("DELETE FROM watch_targets WHERE id = %s", (target_id,))
        conn.commit()
    finally:
        conn.close()
    reload_from_db()
    return {"status": "deleted", "target_id": target_id, "name": name}


@app.post("/api/targets/{target_id}/toggle")
def toggle_target(target_id: str):
    """Toggle enabled/disabled on a target."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM watch_targets WHERE id = %s", (target_id,)
        ).fetchone()
        if not row:
            raise HTTPException(404, f"Target not found: {target_id}")

        new_enabled = not bool(row["enabled"])
        conn.execute(
            "UPDATE watch_targets SET enabled = %s, updated_at = %s WHERE id = %s",
            (new_enabled, now_utc(), target_id),
        )
        conn.commit()

        row = conn.execute(
            "SELECT * FROM watch_targets WHERE id = %s", (target_id,)
        ).fetchone()
        result = WatchTarget.from_row(row).to_dict()
    finally:
        conn.close()
    reload_from_db()
    return result


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
            conditions.append("h.target_id = %s")
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
            LIMIT %s
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
        row = conn.execute("SELECT * FROM hits WHERE id = %s", (hit_id,)).fetchone()
        if not row:
            raise HTTPException(404, f"Hit not found: {hit_id}")

        conn.execute(
            "UPDATE hits SET rating = %s, seen = TRUE WHERE id = %s",
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
        row = conn.execute("SELECT * FROM hits WHERE id = %s", (hit_id,)).fetchone()
        if not row:
            raise HTTPException(404, f"Hit not found: {hit_id}")

        conn.execute("UPDATE hits SET seen = TRUE WHERE id = %s", (hit_id,))
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
        row = conn.execute("SELECT * FROM hits WHERE id = %s", (hit_id,)).fetchone()
        if not row:
            raise HTTPException(404, f"Hit not found: {hit_id}")

        conn.execute("DELETE FROM hits WHERE id = %s", (hit_id,))
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
                "SELECT * FROM watch_targets WHERE id = %s AND enabled = TRUE",
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
                "SELECT id FROM watch_targets WHERE name = %s", (target.name,)
            ).fetchone()
            if existing:
                skipped += 1
                continue

            conn.execute(
                """INSERT INTO watch_targets
                   (id, name, source_type, source_config, match_criteria, cadence,
                    enabled, last_checked_at, last_hit_at, consecutive_failures)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                target.to_row(),
            )
            added += 1

        conn.commit()
        return {"status": "ok", "added": added, "skipped": skipped}
    finally:
        conn.close()


# ── Scheduler ───────────────────────────────────────────────────────────────

@app.post("/api/scheduler/reload")
def api_scheduler_reload():
    """Resync scheduler with the DB — call after external edits."""
    count = reload_from_db()
    return {"status": "ok", "active_jobs": count}


# ── Department Config ───────────────────────────────────────────────────────
# Stores provider/model/api-key-env-var-name per department. Secrets are
# NEVER stored or returned — only the env var name the backend should read.

def _config_row_to_dict(row) -> dict:
    return {
        "department":  row["department"],
        "provider":    row["provider"],
        "model":       row["model"],
        "api_key_ref": row["api_key_ref"],
        "base_url":    row["base_url"],
        "extra":       row["extra"] or {},
        "updated_at":  row["updated_at"],
    }


@app.get("/api/departments")
def list_department_configs():
    """List all department configs. Does not resolve or return secrets."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM department_config ORDER BY department"
        ).fetchall()
        return [_config_row_to_dict(r) for r in rows]
    finally:
        conn.close()


@app.get("/api/departments/{name}/config")
def get_department_config(name: str):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM department_config WHERE department = %s", (name,)
        ).fetchone()
        if not row:
            raise HTTPException(404, f"No config for department '{name}'")
        return _config_row_to_dict(row)
    finally:
        conn.close()


@app.put("/api/departments/{name}/config")
def update_department_config(name: str, body: DepartmentConfigUpdate):
    if body.provider not in ALLOWED_PROVIDERS:
        raise HTTPException(
            400,
            f"provider must be one of {ALLOWED_PROVIDERS}, got '{body.provider}'",
        )

    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT 1 FROM department_config WHERE department = %s", (name,)
        ).fetchone()
        if not row:
            # Allow creating new department rows so future departments
            # (marketing, rd) can be configured before their code ships.
            conn.execute(
                """INSERT INTO department_config
                   (department, provider, model, api_key_ref, base_url, extra)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (
                    name, body.provider, body.model,
                    body.api_key_ref, body.base_url,
                    body.extra or {},
                ),
            )
        else:
            conn.execute(
                """UPDATE department_config
                   SET provider = %s, model = %s, api_key_ref = %s,
                       base_url = %s, extra = %s, updated_at = %s
                   WHERE department = %s""",
                (
                    body.provider, body.model, body.api_key_ref,
                    body.base_url, body.extra or {},
                    now_utc(), name,
                ),
            )
        conn.commit()

        row = conn.execute(
            "SELECT * FROM department_config WHERE department = %s", (name,)
        ).fetchone()
        return _config_row_to_dict(row)
    finally:
        conn.close()


@app.post("/api/departments/{name}/test")
async def test_department_config(name: str):
    """
    Round-trip a tiny prompt through the configured provider for this
    department. Reports latency and any error message. Does not write to
    hits or watch_targets.
    """
    import time
    from providers import get_provider
    from providers.base import ProviderError

    dummy_item = RawItem(
        title="Anthropic releases Claude 4.6",
        source_url="https://example.com/claude-4-6",
        content="Anthropic announced Claude 4.6 with improved reasoning.",
        published_at=None,
    )

    try:
        provider = get_provider(name)
    except ProviderError as e:
        return {"ok": False, "error": str(e)}

    from matcher import _evaluate_chunk

    start = time.monotonic()
    try:
        results = await _evaluate_chunk(
            [dummy_item], "AI model releases", provider,
        )
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
    latency_ms = int((time.monotonic() - start) * 1000)

    # _evaluate_chunk swallows provider exceptions and returns a sentinel
    # MatchResult with reason prefixed "Provider error: ...". Detect that
    # so the Test button doesn't falsely report success.
    reason = results[0].reason or ""
    if reason.startswith("Provider error:") or reason.startswith("Evaluation failed"):
        return {"ok": False, "latency_ms": latency_ms, "error": reason}

    return {
        "ok": True,
        "latency_ms": latency_ms,
        "sample": {
            "matched": results[0].matched,
            "score": results[0].relevance_score,
            "reason": reason,
        },
    }


# ── Marketing ───────────────────────────────────────────────────────────────
# Product profile (singleton) + ad-hoc social-post drafting. LLM calls route
# through the `marketing` department's configured provider.

from marketing import db as mdb
from marketing.platforms import PLATFORMS
from marketing.drafter import draft_posts as _draft_posts


class ProductBody(BaseModel):
    name: str
    one_liner: Optional[str] = ""
    audience: Optional[str] = ""
    tone: Optional[str] = ""
    key_messages: Optional[list[str]] = None
    links: Optional[list[dict]] = None


class DraftRequest(BaseModel):
    platform: str
    topic: str
    variants: int = 3


class DraftUpdate(BaseModel):
    content: Optional[str] = None
    status: Optional[str] = None
    rating: Optional[int] = None
    notes: Optional[str] = None


@app.get("/api/marketing/platforms")
def marketing_platforms():
    """Static platform metadata — used by the UI to label selects and show char limits."""
    return [
        {
            "id": key,
            "label": spec.label,
            "char_limit": spec.char_limit,
            "format_rules": spec.format_rules,
        }
        for key, spec in PLATFORMS.items()
    ]


@app.get("/api/marketing/product")
def marketing_get_product():
    product = mdb.get_product()
    if not product:
        raise HTTPException(404, "No product row found")
    return product


@app.put("/api/marketing/product")
def marketing_put_product(body: ProductBody):
    return mdb.upsert_product(
        name=body.name,
        one_liner=body.one_liner or "",
        audience=body.audience or "",
        tone=body.tone or "",
        key_messages=body.key_messages or [],
        links=body.links or [],
    )


@app.post("/api/marketing/draft")
async def marketing_draft(body: DraftRequest):
    if body.platform not in PLATFORMS:
        raise HTTPException(400, f"Unknown platform '{body.platform}'")
    if not (1 <= body.variants <= 5):
        raise HTTPException(400, "variants must be between 1 and 5")

    product = mdb.get_product() or {
        "name": "(unset)", "one_liner": "", "audience": "", "tone": "",
        "key_messages": [], "links": [],
    }
    try:
        drafts = await _draft_posts(
            platform=body.platform,
            topic=body.topic,
            product=product,
            variants=body.variants,
        )
    except Exception as e:
        raise HTTPException(500, f"Draft generation failed: {e}")

    return mdb.save_drafts(body.platform, body.topic, drafts)


@app.get("/api/marketing/drafts")
def marketing_list_drafts(
    platform: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
):
    try:
        return mdb.list_drafts(platform=platform, status=status, limit=limit)
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/api/marketing/drafts/{draft_id}")
def marketing_get_draft(draft_id: str):
    draft = mdb.get_draft(draft_id)
    if not draft:
        raise HTTPException(404, f"Draft not found: {draft_id}")
    return draft


@app.put("/api/marketing/drafts/{draft_id}")
def marketing_update_draft(draft_id: str, body: DraftUpdate):
    try:
        updated = mdb.update_draft(
            draft_id,
            content=body.content,
            status=body.status,
            rating=body.rating,
            notes=body.notes,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    if not updated:
        raise HTTPException(404, f"Draft not found: {draft_id}")
    return updated


@app.delete("/api/marketing/drafts/{draft_id}")
def marketing_delete_draft(draft_id: str):
    if not mdb.delete_draft(draft_id):
        raise HTTPException(404, f"Draft not found: {draft_id}")
    return {"status": "deleted", "draft_id": draft_id}


# ── Health ──────────────────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    return {"status": "ok", "service": "pia-dispatch-api"}
