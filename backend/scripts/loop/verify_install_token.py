#!/usr/bin/env python3
"""
verify_install_token.py — L25 evaluator

Verifies the BYOA `/api/v1/agents/{id}/install-token` endpoint:
  1. Auth required: no token → 401
  2. Owner-only: another user's token → 404 (not 200)
  3. Owner happy path → 200 with valid base64 bundle
  4. Bundle decodes → has api/token/agent_id/agent_name
  5. Embedded JWT is valid + scope=byoa + ~90d TTL
  6. install_command starts with `curl -fsSL` and ends with the token

Run against any environment:
  python verify_install_token.py --base http://127.0.0.1:8000
  python verify_install_token.py --base https://polis-backend-production.up.railway.app
"""
from __future__ import annotations

import argparse
import base64
import json
import secrets
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

DEFAULT_BASE = "http://127.0.0.1:8000"


def _http(method: str, url: str, *, token: Optional[str] = None,
          body: Optional[Dict[str, Any]] = None, expect: int = 200) -> Any:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, method=method, headers=headers, data=data)
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        status = resp.status
        raw = resp.read().decode()
        payload = json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        status = e.code
        raw = e.read().decode(errors="replace")
        try:
            payload = json.loads(raw)
        except Exception:
            payload = {"_raw": raw}
    if status != expect:
        raise AssertionError(f"{method} {url} -> {status} (expected {expect}): {payload}")
    return payload


def register(base: str) -> Dict[str, str]:
    suffix = secrets.token_hex(4)
    creds = {
        "email": f"l25probe-{suffix}@example.com",
        "password": "Probe-12345",
        "username": f"l25probe{suffix}",
        "display_name": "L25 Probe",
    }
    r = _http("POST", f"{base}/api/v1/auth/register", body=creds)
    creds["token"] = r["token"]
    creds["user_id"] = r.get("user", {}).get("id") or r.get("id")
    return creds


def create_agent(base: str, user_token: str, suffix: str) -> Dict[str, Any]:
    r = _http("POST", f"{base}/api/v1/agents", token=user_token, body={
        "name": f"l25-byoa-{suffix}",
        "display_name": "L25 BYOA probe",
        "description": "BYOA install-token verifier",
        "auth_method": "none",
        "skills": ["python"],
        "agent_card": {"version": "1.0", "skills": ["python"]},
        "status": "online",
    })
    return r


def decode_jwt_payload(jwt_token: str) -> Dict[str, Any]:
    """Decode JWT payload without signature verification (for assertion only)."""
    parts = jwt_token.split(".")
    if len(parts) != 3:
        raise ValueError("not a JWT")
    pad = "=" * (-len(parts[1]) % 4)
    return json.loads(base64.urlsafe_b64decode(parts[1] + pad).decode())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=DEFAULT_BASE)
    args = ap.parse_args()

    base = args.base.rstrip("/")
    print(f"[L25] verify_install_token base={base}")

    # User A creates an agent.
    a = register(base)
    suffix = secrets.token_hex(3)
    agent = create_agent(base, a["token"], suffix)
    agent_id = agent["id"]
    print(f"[L25] user A created agent {agent_id}")

    # User B (a different user, used to test cross-owner access).
    b = register(base)

    # 1. No token → 401.
    _http("POST", f"{base}/api/v1/agents/{agent_id}/install-token", expect=401)
    print("[L25] PASS: no auth → 401")

    # 2. Cross-owner → 404 (not 200, not 403).
    _http("POST", f"{base}/api/v1/agents/{agent_id}/install-token",
          token=b["token"], expect=404)
    print("[L25] PASS: cross-owner → 404")

    # 3. Owner happy path → 200.
    r = _http("POST", f"{base}/api/v1/agents/{agent_id}/install-token",
              token=a["token"], expect=200)

    for k in ("install_token", "agent_id", "agent_name", "expires_in_days", "install_command"):
        if k not in r:
            raise AssertionError(f"missing key {k} in response: {r}")
    print(f"[L25] PASS: owner → 200, keys={sorted(r.keys())}")

    # 4. Bundle decodes.
    pad = "=" * (-len(r["install_token"]) % 4)
    raw = base64.urlsafe_b64decode(r["install_token"] + pad)
    bundle = json.loads(raw.decode())
    for k in ("api", "token", "agent_id", "agent_name"):
        if k not in bundle:
            raise AssertionError(f"bundle missing {k}: {bundle}")
    if bundle["agent_id"] != agent_id:
        raise AssertionError("bundle agent_id mismatch")
    print(f"[L25] PASS: bundle decoded api={bundle['api']} agent={bundle['agent_name']}")

    # 5. Embedded JWT is valid + scope=byoa + long TTL.
    jwt_payload = decode_jwt_payload(bundle["token"])
    if jwt_payload.get("scope") != "byoa":
        raise AssertionError(f"JWT scope wrong: {jwt_payload}")
    if jwt_payload.get("agent_id") != agent_id:
        raise AssertionError("JWT agent_id mismatch")
    exp = jwt_payload.get("exp")
    if not exp:
        raise AssertionError("JWT missing exp")
    seconds_left = exp - int(time.time())
    days_left = seconds_left / 86400.0
    if not (85 <= days_left <= 95):
        raise AssertionError(f"JWT TTL out of expected 85-95d: {days_left:.1f}d")
    print(f"[L25] PASS: JWT scope=byoa ttl={days_left:.1f}d agent_id matches")

    # 6. install_command shape.
    cmd = r["install_command"]
    if not cmd.startswith("curl -fsSL "):
        raise AssertionError(f"install_command bad prefix: {cmd}")
    if not cmd.endswith(r["install_token"]):
        raise AssertionError(f"install_command must end with token, got: {cmd[-80:]}")
    print(f"[L25] PASS: install_command shape ok ({len(cmd)} chars)")

    print("[L25] ALL GREEN — install-token endpoint behaves correctly")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as e:
        print(f"[L25] FAIL: {e}")
        sys.exit(1)
