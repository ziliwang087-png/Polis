"""Stale-claim reaper.

Background asyncio loop that periodically scans `jobs` and resets
claims that look abandoned, so a dead/disappeared agent cannot block
a job forever.

A claim is considered stale when:
  - status is 'claimed' or 'working'
  - claimed_at older than STALE_CLAIM_AGE_SECS
  - the most recent `progress` event for the job is also older than
    STALE_CLAIM_AGE_SECS (so an agent that's actively making progress
    on a long task is NOT reaped)

When stale, the reaper:
  - sets status='submitted', clears to_agent_id/claimed_at/started_at/progress
  - inserts a `stale_claim_reaped` job event with the previous agent's id
    so the audit trail stays intact

Tunable via env:
  - POLIS_STALE_CLAIM_REAPER_ENABLED: '1' to enable (default '1')
  - POLIS_STALE_CLAIM_AGE_SECS: how old before claim is stale (default 300)
  - POLIS_STALE_CLAIM_TICK_SECS: how often to scan (default 60)
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Optional

from app.database import get_db_connection

logger = logging.getLogger("polis.stale_claim_reaper")


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if not raw:
        return default
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def reap_once() -> int:
    """Run a single sweep. Return number of jobs reaped.

    Synchronous so it can be unit-tested without an event loop.
    """
    age = _env_int("POLIS_STALE_CLAIM_AGE_SECS", 300)
    with get_db_connection() as conn:
        cur = conn.cursor()
        # CTE 1: jobs with claim older than threshold
        # CTE 2: jobs whose most recent progress event is also older
        # Final: intersect them, reset status, insert audit event
        cur.execute(
            """
            WITH stale_jobs AS (
              SELECT j.id, j.to_agent_id
              FROM jobs j
              WHERE j.status IN ('claimed', 'working')
                AND j.claimed_at IS NOT NULL
                AND j.claimed_at < NOW() - make_interval(secs => %s)
                AND NOT EXISTS (
                  SELECT 1 FROM job_events e
                  WHERE e.job_id = j.id
                    AND e.event_type = 'progress'
                    AND e.created_at >= NOW() - make_interval(secs => %s)
                )
            ),
            reset AS (
              UPDATE jobs SET
                status = 'submitted',
                to_agent_id = NULL,
                claimed_at = NULL,
                started_at = NULL,
                progress = NULL
              WHERE id IN (SELECT id FROM stale_jobs)
              RETURNING id
            )
            SELECT s.id::text, s.to_agent_id::text FROM stale_jobs s
            JOIN reset r ON r.id = s.id
            """,
            (age, age),
        )
        reaped = cur.fetchall()
        for row in reaped:
            cur.execute(
                """
                INSERT INTO job_events (job_id, event_type, payload)
                VALUES (%s, 'canceled', %s::jsonb)
                """,
                (
                    row["id"],
                    json.dumps({
                        "reason": "stale_claim_reaped",
                        "previous_agent_id": row["to_agent_id"],
                    }),
                ),
            )
        if reaped:
            logger.info(
                "[stale-claim-reaper] reaped %d stale jobs: %s",
                len(reaped),
                [r["id"][:8] for r in reaped],
            )
        return len(reaped)


_running_task: Optional[asyncio.Task] = None

# Public, read-only state for /health/deep
_state: dict = {
    "enabled": False,
    "running": False,
    "tick_secs": _env_int("POLIS_STALE_CLAIM_TICK_SECS", 60),
    "age_secs": _env_int("POLIS_STALE_CLAIM_AGE_SECS", 300),
    "last_tick_at": None,         # epoch seconds
    "last_reap_count": 0,
    "total_reaped": 0,
    "tick_errors": 0,
    "last_error": None,
    "started_at": None,
}


def get_state() -> dict:
    """Snapshot reaper state. Used by /health/deep."""
    import time as _t
    snap = dict(_state)
    if snap.get("last_tick_at"):
        snap["seconds_since_last_tick"] = max(0, int(_t.time() - snap["last_tick_at"]))
    else:
        snap["seconds_since_last_tick"] = None
    return snap


async def _reaper_loop():
    import time as _t
    tick = _env_int("POLIS_STALE_CLAIM_TICK_SECS", 60)
    age = _env_int("POLIS_STALE_CLAIM_AGE_SECS", 300)
    _state.update(
        running=True,
        tick_secs=tick,
        age_secs=age,
        started_at=int(_t.time()),
    )
    logger.info("[stale-claim-reaper] loop started, tick=%ds, age=%ds", tick, age)
    try:
        while True:
            try:
                count = reap_once()
                _state["last_tick_at"] = int(_t.time())
                _state["last_reap_count"] = count
                _state["total_reaped"] += count
                _state["last_error"] = None
            except Exception as exc:
                _state["tick_errors"] += 1
                _state["last_error"] = repr(exc)[:300]
                logger.exception("[stale-claim-reaper] tick failed (will retry)")
            await asyncio.sleep(tick)
    finally:
        _state["running"] = False


def maybe_start_reaper():
    """Start the reaper loop as an asyncio Task on the running event loop.

    Called from FastAPI startup hook, so a running loop is guaranteed.
    Safe to call once per process; idempotent.
    """
    global _running_task
    if os.getenv("POLIS_STALE_CLAIM_REAPER_ENABLED", "1") != "1":
        _state["enabled"] = False
        logger.info("[stale-claim-reaper] disabled via env")
        return
    _state["enabled"] = True
    if _running_task is not None and not _running_task.done():
        logger.info("[stale-claim-reaper] already running, skip")
        return
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        logger.warning("[stale-claim-reaper] no running event loop, skip")
        return
    _running_task = loop.create_task(_reaper_loop())
    logger.info("[stale-claim-reaper] task scheduled")
