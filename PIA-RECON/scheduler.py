"""
In-process scheduler for watch targets.

APScheduler reads each enabled target's `cadence` (cron string) and fires
`_check_single_target` on schedule. Deliberately chosen over the Claude
Agent SDK for coordination: no vendor lock-in at this layer, and the
watchdog runs fine single-process. If/when durability across restarts
matters (marketing/rd departments), promote to arq with ~50 LOC.

Lifecycle: started from api.py's FastAPI lifespan context. Call
reload_from_db() to pick up target CRUD.
"""

import logging
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from db import get_connection
from models import WatchTarget

logger = logging.getLogger("pia.scheduler")

_scheduler: Optional[AsyncIOScheduler] = None


def _job_id(target_id: str) -> str:
    return f"target:{target_id}"


async def _run_target(target_id: str) -> None:
    """Load the target fresh (config may have changed) and run a check."""
    from server import _check_single_target

    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM watch_targets WHERE id = ? AND enabled = TRUE",
            (target_id,),
        ).fetchone()
    finally:
        conn.close()

    if not row:
        logger.info("scheduler: target %s no longer enabled; skipping", target_id)
        return

    target = WatchTarget.from_row(row)
    result = await _check_single_target(target)
    logger.info(
        "scheduler: %s -> status=%s new_hits=%s",
        target.name, result.get("status"), result.get("new_hits", 0),
    )


def start_scheduler() -> AsyncIOScheduler:
    """Start (or return existing) scheduler and load all enabled targets."""
    global _scheduler
    if _scheduler and _scheduler.running:
        return _scheduler

    _scheduler = AsyncIOScheduler()
    _scheduler.start()
    reload_from_db()
    logger.info("scheduler: started with %d jobs", len(_scheduler.get_jobs()))
    return _scheduler


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("scheduler: stopped")
    _scheduler = None


def reload_from_db() -> int:
    """
    Resync the scheduler with the DB: add jobs for enabled targets, remove
    jobs for disabled/deleted ones. Returns the number of active jobs.
    """
    global _scheduler
    if _scheduler is None:
        raise RuntimeError("scheduler not started; call start_scheduler() first")

    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id, name, cadence, enabled FROM watch_targets"
        ).fetchall()
    finally:
        conn.close()

    wanted_ids = set()
    for row in rows:
        if not row["enabled"]:
            continue
        wanted_ids.add(row["id"])
        try:
            trigger = CronTrigger.from_crontab(row["cadence"])
        except Exception as e:
            logger.warning(
                "scheduler: bad cadence %r for %s: %s",
                row["cadence"], row["name"], e,
            )
            continue

        _scheduler.add_job(
            _run_target,
            trigger=trigger,
            args=[row["id"]],
            id=_job_id(row["id"]),
            replace_existing=True,
            coalesce=True,
            max_instances=1,
        )

    # Remove jobs for targets that are no longer enabled.
    for job in list(_scheduler.get_jobs()):
        if not job.id.startswith("target:"):
            continue
        tid = job.id.split(":", 1)[1]
        if tid not in wanted_ids:
            _scheduler.remove_job(job.id)

    return len(_scheduler.get_jobs())
