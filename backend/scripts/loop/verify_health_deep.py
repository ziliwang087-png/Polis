"""L13 evaluator — verify /health/deep returns db + reaper state.

Hits /health/deep on the configured base URL and asserts:

  * HTTP 200
  * status field present and one of {ok, degraded, unhealthy}
  * db.ok == True (db is reachable)
  * reaper.enabled / reaper.running keys present
  * if reaper enabled → seconds_since_last_tick <= 3 * tick_secs

Base URL precedence: --base flag > PUBLIC_BASE_URL env > prod default.
Default points at the real Polis backend on Railway.
Exit 0 on PASS, non-zero on FAIL. Prints a one-screen summary either way.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request


DEFAULT_BASE = "https://polis-backend-production.up.railway.app"


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--base",
        default=os.getenv("PUBLIC_BASE_URL", DEFAULT_BASE),
        help=f"Base URL to test (default: env PUBLIC_BASE_URL or {DEFAULT_BASE})",
    )
    args = ap.parse_args()
    base = args.base.rstrip("/")
    url = f"{base}/health/deep"
    print(f"GET {url}")
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read().decode()
            status_code = resp.status
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        status_code = e.code
    except Exception as e:
        fail(f"request failed: {e!r}")
        return

    if status_code != 200:
        fail(f"status={status_code} body={body[:300]}")

    try:
        data = json.loads(body)
    except Exception as e:
        fail(f"non-json body: {e!r} body={body[:200]}")
        return

    print(json.dumps(data, indent=2, ensure_ascii=False))

    status = data.get("status")
    if status not in ("ok", "degraded", "unhealthy"):
        fail(f"bad status field: {status!r}")

    db = data.get("db") or {}
    if not db.get("ok"):
        fail(f"db not ok: {db}")

    reaper = data.get("reaper") or {}
    for k in ("enabled", "running", "tick_secs", "age_secs"):
        if k not in reaper:
            fail(f"reaper missing key {k!r}: {reaper}")

    if reaper.get("enabled"):
        if not reaper.get("running"):
            fail(f"reaper enabled but not running: {reaper}")
        secs = reaper.get("seconds_since_last_tick")
        tick = reaper.get("tick_secs", 60) or 60
        if secs is not None and secs > tick * 3:
            fail(f"reaper stale: {secs}s > 3*{tick}s")

    print(f"PASS: /health/deep status={status}, db_ok={db.get('ok')}, reaper={reaper.get('running')}")


if __name__ == "__main__":
    main()
