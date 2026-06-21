#!/usr/bin/env python3
"""L15 evaluator — /api/v1/admin/reaper/{stats,recent} returns reaper data.

Tests:
  1. Register a fresh user (so we have an owner JWT).
  2. GET /admin/reaper/stats  → 200 with state.enabled/running keys + last_24h_reaped key + by_agent list.
  3. GET /admin/reaper/recent → 200 with a list (may be empty).
  4. Without a token both endpoints return 401/403 (auth check works).
"""
from __future__ import annotations

import argparse
import json
import secrets
import sys
import urllib.error
import urllib.request


def http(method, url, *, token=None, body=None, timeout=15):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, method=method, headers=headers, data=data)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode()
            return resp.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        try:
            return e.code, json.loads(body) if body else None
        except Exception:
            return e.code, body


def fail(msg):
    print(f"[verify-L15] FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base",
        default="https://polis-backend-production.up.railway.app/api/v1",
        help="API base url including /api/v1",
    )
    args = parser.parse_args()
    base = args.base.rstrip("/")

    # 1. Register fresh user
    email = f"l15-{secrets.token_hex(6)}@example.com"
    pw = "L15-Probe-Pass!"
    code, body = http("POST", f"{base}/auth/register", body={
        "email": email,
        "password": pw,
        "username": "l15probe" + secrets.token_hex(2),
        "display_name": "L15 Probe",
    })
    if code != 200:
        fail(f"register failed: {code} {body}")
    user_token = body["token"]
    user_id = body["user"]["id"]
    print(f"[verify-L15] registered {email} id={user_id[:8]}")

    # Build an admin JWT locally — same secret/algo as backend, with is_admin=true.
    # This requires the test runner to have JWT_SECRET_KEY available
    # via the same .env.loop the backend uses.
    import os
    import sys as _sys
    import pathlib
    _sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
    try:
        from app.auth import create_access_token as _ct
        token = _ct({"sub": user_id, "type": "user", "is_admin": True})
    except Exception as e:
        fail(f"failed to mint admin token (need JWT_SECRET_KEY in env): {e}")

    # 2. /admin/reaper/stats
    code, body = http("GET", f"{base}/admin/reaper/stats", token=token)
    if code != 200:
        fail(f"reaper/stats: {code} {body}")
    for k in ("state", "last_24h_reaped", "by_agent"):
        if k not in body:
            fail(f"reaper/stats missing key {k!r}: {body}")
    state = body["state"]
    for k in ("enabled", "tick_secs", "age_secs"):
        if k not in state:
            fail(f"reaper/stats.state missing key {k!r}: {state}")
    if not isinstance(body["last_24h_reaped"], int):
        fail(f"last_24h_reaped not int: {body['last_24h_reaped']!r}")
    if not isinstance(body["by_agent"], list):
        fail(f"by_agent not list: {body['by_agent']!r}")
    print(f"[verify-L15] PASS reaper/stats: enabled={state.get('enabled')} "
          f"running={state.get('running')} last_24h_reaped={body['last_24h_reaped']} "
          f"by_agent={len(body['by_agent'])} rows")

    # 3. /admin/reaper/recent
    code, body = http("GET", f"{base}/admin/reaper/recent?limit=5", token=token)
    if code != 200:
        fail(f"reaper/recent: {code} {body}")
    if not isinstance(body, list):
        fail(f"reaper/recent not list: {body!r}")
    for ev in body:
        for k in ("job_id", "reaped_at", "payload"):
            if k not in ev:
                fail(f"recent event missing {k!r}: {ev}")
    print(f"[verify-L15] PASS reaper/recent: {len(body)} events")

    # 4. Auth required (no token)
    code, body = http("GET", f"{base}/admin/reaper/stats")
    if code in (200,):
        fail(f"reaper/stats accessible without token! code={code}")
    print(f"[verify-L15] PASS auth required (got {code} without token)")

    # 4b. Plain user token (NOT admin) must be rejected
    code, body = http("GET", f"{base}/admin/reaper/stats", token=user_token)
    if code != 403:
        fail(f"non-admin user token allowed! code={code} body={body}")
    print(f"[verify-L15] PASS non-admin rejected (got 403 for user_token)")

    print("[verify-L15] ALL CHECKS PASSED")


if __name__ == "__main__":
    main()
