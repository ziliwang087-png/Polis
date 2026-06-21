#!/usr/bin/env python3
"""L20 evaluator — /api/v1/admin/workers exposes worker heartbeat to admins.

Tests:
  1. Register a fresh user (so we have a non-admin owner JWT).
  2. Mint local admin JWT (is_admin=true) — same secret as backend.
  3. GET /admin/workers with admin token -> 200 with expected envelope.
  4. GET /admin/workers without token -> 401/403.
  5. GET /admin/workers with non-admin user token -> 403.
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
    print(f"[verify-L20] FAIL: {msg}", file=sys.stderr)
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
    email = f"l20-{secrets.token_hex(6)}@example.com"
    pw = "L20-Probe-Pass!"
    code, body = http("POST", f"{base}/auth/register", body={
        "email": email,
        "password": pw,
        "username": "l20probe" + secrets.token_hex(2),
        "display_name": "L20 Probe",
    })
    if code != 200:
        fail(f"register failed: {code} {body}")
    user_token = body["token"]
    user_id = body["user"]["id"]
    print(f"[verify-L20] registered {email} id={user_id[:8]}")

    # 2. Mint admin JWT locally
    import pathlib
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
    try:
        from app.auth import create_access_token as _ct
        admin_token = _ct({"sub": user_id, "type": "user", "is_admin": True})
    except Exception as e:
        fail(f"failed to mint admin token (need JWT_SECRET_KEY in env): {e}")

    # 3. /admin/workers with admin token
    code, body = http("GET", f"{base}/admin/workers", token=admin_token)
    if code != 200:
        fail(f"/admin/workers: {code} {body}")
    for k in ("total", "fresh", "connected", "all_fresh", "any_registered", "workers"):
        if k not in body:
            fail(f"/admin/workers missing key {k!r}: {body}")
    if not isinstance(body["workers"], list):
        fail(f"workers not list: {body['workers']!r}")
    # Each worker (if any registered) must have these fields
    for w in body["workers"]:
        for k in ("name", "is_fresh", "connected", "jobs_received", "jobs_done", "errors"):
            if k not in w:
                fail(f"worker missing {k!r}: {w}")
    print(
        f"[verify-L20] PASS /admin/workers: total={body['total']} fresh={body['fresh']} "
        f"connected={body['connected']} all_fresh={body['all_fresh']} "
        f"any_registered={body['any_registered']}"
    )

    # 4. No token
    code, body = http("GET", f"{base}/admin/workers")
    if code in (200,):
        fail(f"/admin/workers accessible without token! code={code}")
    print(f"[verify-L20] PASS auth required (got {code} without token)")

    # 5. Non-admin user token
    code, body = http("GET", f"{base}/admin/workers", token=user_token)
    if code != 403:
        fail(f"non-admin user token allowed! code={code} body={body}")
    print(f"[verify-L20] PASS non-admin rejected (got 403 for user_token)")

    print("[verify-L20] ALL CHECKS PASSED")


if __name__ == "__main__":
    main()
