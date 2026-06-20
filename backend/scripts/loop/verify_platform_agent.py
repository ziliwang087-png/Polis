#!/usr/bin/env python3
"""LOOP-1 evaluator: platform agent really claims a job and produces a real LLM artifact.

8 mechanical conditions, all must hold to exit 0:
  1) /health 200
  2) /api/v1/agents has name=polis-platform-py status=online
  3) test user login (auto-register fallback once)
  4) test user submits a fizzbuzz job (skill=python)
  5) within --watch-secs the job reaches status=completed
  6) at least one artifact with metadata.by == polis-platform-py
  7) artifact.content >= 80 chars, no failure/fake markers
  8) artifact.content contains both 'fizz' and 'buzz' (case-insensitive)

Exit codes: 0 pass | 1 logic fail | 2 environment error.

This script is the LOOP ground truth. Fix code, do NOT modify this file.
"""
from __future__ import annotations
import argparse, json, sys, time, urllib.error, urllib.request


def http(method, url, *, token=None, body=None, timeout=10):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, method=method, headers=headers, data=data)
    raw = urllib.request.urlopen(req, timeout=timeout).read().decode()
    return json.loads(raw) if raw else None


def fail(msg, code=1):
    print(f"[verify-1] FAIL: {msg}", file=sys.stderr)
    sys.exit(code)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://127.0.0.1:8765")
    ap.add_argument("--user-email", default="alice2@example.com")
    ap.add_argument("--user-password", default="Alice2Pass-123")
    ap.add_argument("--watch-secs", type=int, default=45)
    args = ap.parse_args()
    api = args.api.rstrip("/")

    try:
        h = http("GET", f"{api}/health", timeout=5)
    except Exception as e:
        fail(f"backend /health unreachable at {api}: {e}", code=2)
    if h.get("status") != "healthy":
        fail(f"/health not healthy: {h}", code=2)
    print("[verify-1] (1/8) backend healthy")

    agents = http("GET", f"{api}/api/v1/agents")
    plat = next((a for a in agents if a.get("name") == "polis-platform-py"), None)
    if not plat:
        fail("'polis-platform-py' not registered (check POLIS_PLATFORM_AGENT_ENABLED)")
    if plat.get("status") != "online":
        fail(f"platform agent status={plat.get('status')}, want online")
    print(f"[verify-1] (2/8) platform agent online id={plat['id'][:8]}")

    try:
        tok = http("POST", f"{api}/api/v1/auth/login",
                   body={"email": args.user_email, "password": args.user_password})["token"]
    except urllib.error.HTTPError as e:
        if e.code == 401:
            try:
                tok = http("POST", f"{api}/api/v1/auth/register",
                           body={"email": args.user_email, "password": args.user_password,
                                 "username": "alice2_loop"})["token"]
            except Exception as e2:
                fail(f"cannot create test user: {e2}", code=2)
        else:
            fail(f"test user login HTTP {e.code}", code=2)
    print("[verify-1] (3/8) test user authenticated")

    # 3.5) ensure test user has credit (loop runs many times; auto-topup)
    try:
        import sys, pathlib as _p
        sys.path.insert(0, str(_p.Path(__file__).resolve().parents[2]))
        from app.database import get_db_connection  # type: ignore
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE users SET credit_balance = GREATEST(credit_balance, 50) WHERE email = %s",
                (args.user_email,),
            )
        print("[verify-1] (3.5/8) topped up credit_balance to >=50")
    except Exception as e:
        print(f"[verify-1] WARN: could not topup credit: {e}", file=sys.stderr)

    body = {
        "title": "Loop verify: fizzbuzz",
        "description": "Write a standard FizzBuzz in Python from 1 to 30. Multiples of 3 -> Fizz, of 5 -> Buzz, of 15 -> FizzBuzz, else the number. Provide a complete runnable code block.",
        "required_skill": "python",
        "input_messages": [{"role": "user", "parts": [{"kind": "text", "text": "fizzbuzz"}]}],
        "attachments": [],
    }
    job = http("POST", f"{api}/api/v1/jobs", token=tok, body=body, timeout=15)
    job_id = job["id"]
    print(f"[verify-1] (4/8) job submitted {job_id[:8]}")

    deadline = time.time() + args.watch_secs
    detail, last = None, None
    while time.time() < deadline:
        time.sleep(2)
        detail = http("GET", f"{api}/api/v1/jobs/{job_id}", timeout=10)
        st = detail["status"]
        if st != last:
            print(f"[verify-1]   ... status={st}  progress={detail.get('progress') or '-'}")
            last = st
        if st == "completed":
            break
        if st in ("failed", "canceled"):
            fail(f"job ended with status={st}")
    else:
        fail(f"job not completed within {args.watch_secs}s (last status={last})")
    print("[verify-1] (5/8) job=completed")

    arts = detail.get("artifacts") or []
    if not arts:
        fail("no artifacts on completed job")
    plat_art = next((a for a in arts
                     if (a.get("metadata") or {}).get("by") == "polis-platform-py"), None)
    if not plat_art:
        produced = [(a.get("metadata") or {}).get("by") for a in arts]
        fail(f"no artifact from platform agent. seen: {produced}")
    print("[verify-1] (6/8) artifact from polis-platform-py present")

    content = plat_art.get("content") or ""
    if len(content) < 80:
        fail(f"artifact too short ({len(content)}): {content!r}")
    bad = ["LLM call failed", "[demo-bot]", "demo-bot handled"]
    for m in bad:
        if m in content:
            fail(f"artifact contains failure marker {m!r}: {content[:300]!r}")
    print(f"[verify-1] (7/8) artifact length={len(content)} no failure markers")

    low = content.lower()
    if "fizz" not in low or "buzz" not in low:
        fail(f"artifact missing fizz/buzz: {content[:300]!r}")
    print("[verify-1] (8/8) artifact mentions fizz+buzz")

    print()
    print(f"[verify-1] PASS - model={(plat_art.get('metadata') or {}).get('model')!r}")
    print(f"---preview---\n{content[:600]}\n---")
    sys.exit(0)


if __name__ == "__main__":
    main()
