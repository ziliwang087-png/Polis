"""
L19 evaluator: /health/deep should expose worker heartbeat state.

Three scenarios:
  1) No workers registered -> response includes "workers" key with
     any_registered=False, status decision unaffected.
  2) Workers registered + fresh -> any_registered=True, all_fresh=True, status=ok.
  3) Workers registered + stale -> all_fresh=False, status=degraded.

Run from repo root:
    cd backend && python scripts/loop/verify_worker_heartbeat.py
"""
from __future__ import annotations

import os
import sys
import time
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from fastapi.testclient import TestClient


def _fresh_app(monkey_env=None):
    """Reload app modules with optional env overrides so /health/deep sees a clean slate."""
    if monkey_env:
        for k, v in monkey_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    # Drop cached modules to force fresh worker_heartbeat state per run.
    # Important: also drop the 'app' parent package so its attribute cache
    # (e.g. app.worker_heartbeat held as an attribute on app) gets rebuilt
    # in lockstep with the submodules. Otherwise different code paths can
    # see different module objects.
    for mod in list(sys.modules):
        if mod == "app" or mod.startswith("app."):
            sys.modules.pop(mod, None)
    from app.main import app  # noqa: WPS433  (intentional late import)
    # Return the freshly-loaded heartbeat module too -- /health/deep imports
    # it lazily inside the handler via app.worker_heartbeat, so the same
    # cached module object is shared.
    from app import worker_heartbeat as wh  # noqa: WPS433
    return app, wh


def scenario_no_workers():
    app, _wh = _fresh_app()
    client = TestClient(app)
    r = client.get("/health/deep")
    assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text[:200]}"
    body = r.json()
    assert "workers" in body, "missing 'workers' key in /health/deep"
    workers = body["workers"]
    assert workers.get("any_registered") is False, f"expected no workers, got {workers}"
    print("  [pass] no workers: any_registered=False, status=", body.get("status"))


def scenario_fresh_worker():
    app, worker_heartbeat = _fresh_app()
    worker_heartbeat.register("polis_python", agent_id="agent-uuid")
    worker_heartbeat.beat_connected("polis_python")
    worker_heartbeat.beat_job_received("polis_python", job_id="job-1")
    worker_heartbeat.beat_job_done("polis_python")

    client = TestClient(app)
    r = client.get("/health/deep")
    assert r.status_code == 200, r.text[:200]
    body = r.json()
    workers = body["workers"]
    assert workers.get("any_registered") is True, f"expected registered, got {workers}"
    assert workers.get("all_fresh") is True, f"expected fresh, got {workers}"
    assert workers.get("connected") == 1, f"expected connected=1, got {workers}"
    assert workers["workers"][0]["jobs_done"] == 1
    assert workers["workers"][0]["jobs_received"] == 1
    print("  [pass] fresh worker: all_fresh=True jobs_done=1")


def scenario_stale_worker():
    app, worker_heartbeat = _fresh_app({"POLIS_WORKER_FRESHNESS_SECS": "1"})
    worker_heartbeat.register("polis_python", agent_id="agent-uuid")
    worker_heartbeat.beat_connected("polis_python")
    # Force stale: rewrite last_seen_at to 5s ago
    worker_heartbeat._workers["polis_python"]["last_seen_at"] = int(time.time()) - 5

    client = TestClient(app)
    r = client.get("/health/deep")
    body = r.json()
    workers = body["workers"]
    assert workers.get("any_registered") is True
    assert workers.get("all_fresh") is False, f"expected stale, got {workers}"
    # Status should reflect the staleness (degraded), unless db is broken.
    if body.get("db", {}).get("ok"):
        assert body.get("status") == "degraded", (
            f"expected degraded with stale worker + ok db, got {body.get('status')}"
        )
    print("  [pass] stale worker: all_fresh=False status=", body.get("status"))


def main():
    failures = []
    for fn in (scenario_no_workers, scenario_fresh_worker, scenario_stale_worker):
        try:
            print(f"-> {fn.__name__}")
            fn()
        except Exception:
            failures.append(fn.__name__)
            traceback.print_exc()
    print("\nL19 worker-heartbeat evaluator:", "PASS" if not failures else f"FAIL {failures}")
    sys.exit(0 if not failures else 1)


if __name__ == "__main__":
    main()
