"""
Lightweight in-process heartbeat registry for platform-agent worker threads.

The platform-agent runs each agent in its own daemon thread (long-lived SSE
connection to /inbox + LLM calls). There is no native FastAPI signal that
those threads are alive. This module gives worker_loop a one-line "I'm alive"
hook and exposes the snapshot to /health/deep.

Design:
- One dict keyed by worker name (e.g. "polis_python", "polis_translator").
- Each beat records timestamps for connect / job_received / job_done / error.
- Pure stdlib, no external state, safe to call from any thread.
- Read path is used by /health/deep so it MUST never raise.
"""
from __future__ import annotations

import os
import threading
import time
from typing import Any, Dict, Optional

_lock = threading.Lock()
_workers: Dict[str, Dict[str, Any]] = {}


def _now() -> int:
    return int(time.time())


def register(name: str, agent_id: Optional[str] = None) -> None:
    """Called once when a worker thread first starts."""
    with _lock:
        existing = _workers.get(name) or {}
        existing.update(
            {
                "name": name,
                "agent_id": agent_id or existing.get("agent_id"),
                "started_at": existing.get("started_at") or _now(),
                "last_seen_at": _now(),
                "connected": False,
                "last_connected_at": existing.get("last_connected_at"),
                "last_job_received_at": existing.get("last_job_received_at"),
                "last_job_done_at": existing.get("last_job_done_at"),
                "jobs_received": existing.get("jobs_received", 0),
                "jobs_done": existing.get("jobs_done", 0),
                "errors": existing.get("errors", 0),
                "last_error": existing.get("last_error"),
            }
        )
        _workers[name] = existing


def beat_connected(name: str) -> None:
    """Called every time the SSE inbox connection is (re)established."""
    with _lock:
        w = _workers.setdefault(name, {"name": name, "started_at": _now()})
        now = _now()
        w["connected"] = True
        w["last_connected_at"] = now
        w["last_seen_at"] = now


def beat_disconnected(name: str, error: str = "") -> None:
    with _lock:
        w = _workers.setdefault(name, {"name": name, "started_at": _now()})
        w["connected"] = False
        w["last_seen_at"] = _now()
        if error:
            w["last_error"] = str(error)[:300]
            w["errors"] = int(w.get("errors", 0)) + 1


def beat_job_received(name: str, job_id: str = "") -> None:
    with _lock:
        w = _workers.setdefault(name, {"name": name, "started_at": _now()})
        now = _now()
        w["last_job_received_at"] = now
        w["last_seen_at"] = now
        w["jobs_received"] = int(w.get("jobs_received", 0)) + 1
        if job_id:
            w["last_job_id"] = job_id


def beat_job_done(name: str) -> None:
    with _lock:
        w = _workers.setdefault(name, {"name": name, "started_at": _now()})
        now = _now()
        w["last_job_done_at"] = now
        w["last_seen_at"] = now
        w["jobs_done"] = int(w.get("jobs_done", 0)) + 1


def beat_error(name: str, error: str) -> None:
    with _lock:
        w = _workers.setdefault(name, {"name": name, "started_at": _now()})
        w["last_error"] = str(error)[:300]
        w["last_seen_at"] = _now()
        w["errors"] = int(w.get("errors", 0)) + 1


def snapshot() -> Dict[str, Any]:
    """Return a JSON-safe snapshot for /health/deep.

    Adds derived fields:
      - seconds_since_last_seen
      - is_fresh: True if seen within freshness window
    Reads POLIS_WORKER_FRESHNESS_SECS (default 600s = 10min) — long enough
    that an idle worker waiting on inbox SSE is still "fresh", but short
    enough to detect a fully dead thread.
    """
    try:
        fresh_threshold = int(os.getenv("POLIS_WORKER_FRESHNESS_SECS", "600"))
    except (TypeError, ValueError):
        fresh_threshold = 600

    out: Dict[str, Any] = {}
    now = _now()
    with _lock:
        for name, w in _workers.items():
            d = dict(w)
            last_seen = d.get("last_seen_at")
            if last_seen:
                d["seconds_since_last_seen"] = max(0, now - int(last_seen))
                d["is_fresh"] = d["seconds_since_last_seen"] <= fresh_threshold
            else:
                d["seconds_since_last_seen"] = None
                d["is_fresh"] = False
            out[name] = d
    return out


def aggregate() -> Dict[str, Any]:
    """Concise summary suitable for /health/deep status decision."""
    snap = snapshot()
    workers = list(snap.values())
    total = len(workers)
    fresh = sum(1 for w in workers if w.get("is_fresh"))
    connected = sum(1 for w in workers if w.get("connected"))
    return {
        "total": total,
        "fresh": fresh,
        "connected": connected,
        "all_fresh": total > 0 and fresh == total,
        "any_registered": total > 0,
        "workers": workers,
    }
