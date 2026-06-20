#!/usr/bin/env python3
"""LOOP-2 evaluator: Railway prod platform agent handles a real fizzbuzz job."""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request


def http(method, url, *, token=None, body=None, timeout=10):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, method=method, headers=headers, data=data)
    raw = urllib.request.urlopen(req, timeout=timeout).read().decode()
    return json.loads(raw) if raw else None


def fail(msg, code=1):
    print(f"[verify-2] FAIL: {msg}", file=sys.stderr)
    sys.exit(code)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="https://polis-backend-production.up.railway.app")
    ap.add_argument("--watch-secs", type=int, default=35)
    args = ap.parse_args()
    api = args.api.rstrip("/")

    try:
        health = http("GET", f"{api}/health", timeout=8)
    except Exception as exc:
        fail(f"backend /health unreachable at {api}: {exc}", code=2)
    if health.get("status") != "healthy":
        fail(f"/health not healthy: {health}", code=2)
    print("[verify-2] (1/7) prod backend healthy")

    agents = http("GET", f"{api}/api/v1/agents", timeout=12)
    plat = next((a for a in agents if a.get("name") == "polis-platform-py"), None)
    if not plat:
        fail("'polis-platform-py' not registered in prod")
    if plat.get("status") != "online":
        fail(f"platform agent status={plat.get('status')}, want online")
    print(f"[verify-2] (2/7) platform agent online id={plat['id'][:8]}")

    suffix = str(int(time.time()))
    auth = http(
        "POST",
        f"{api}/api/v1/auth/register",
        body={
            "email": f"loop-prod-{suffix}@example.com",
            "password": "LoopProdPass-123",
            "username": f"loopprod{suffix[-8:]}",
            "display_name": "Loop Prod",
        },
        timeout=15,
    )
    token = auth["token"]
    print("[verify-2] (3/7) throwaway prod user registered")

    job = http(
        "POST",
        f"{api}/api/v1/jobs",
        token=token,
        body={
            "title": "Prod loop verify: fizzbuzz",
            "description": (
                "Write a standard FizzBuzz in Python from 1 to 30. "
                "Multiples of 3 -> Fizz, of 5 -> Buzz, of 15 -> FizzBuzz, "
                "else the number. Provide a complete runnable code block."
            ),
            "required_skill": "python",
            "input_messages": [{"role": "user", "parts": [{"kind": "text", "text": "fizzbuzz"}]}],
            "attachments": [],
        },
        timeout=15,
    )
    job_id = job["id"]
    print(f"[verify-2] (4/7) job submitted {job_id[:8]}")

    deadline = time.time() + args.watch_secs
    detail, last = None, None
    while time.time() < deadline:
        time.sleep(2)
        detail = http("GET", f"{api}/api/v1/jobs/{job_id}", timeout=12)
        status = detail["status"]
        if status != last:
            print(f"[verify-2]   ... status={status} progress={detail.get('progress') or '-'}")
            last = status
        if status == "completed":
            break
        if status in ("failed", "canceled"):
            fail(f"job ended with status={status}")
    else:
        fail(f"job not completed within {args.watch_secs}s (last status={last})")
    print("[verify-2] (5/7) job=completed")

    artifacts = detail.get("artifacts") or []
    art = next((a for a in artifacts if (a.get("metadata") or {}).get("by") == "polis-platform-py"), None)
    if not art:
        seen = [(a.get("metadata") or {}).get("by") for a in artifacts]
        fail(f"no artifact from polis-platform-py. seen: {seen}")
    print("[verify-2] (6/7) artifact from polis-platform-py present")

    content = art.get("content") or ""
    if len(content) < 80:
        fail(f"artifact too short ({len(content)}): {content!r}")
    for marker in ("LLM call failed", "调用 LLM 失败", "[demo-bot]", "demo-bot handled"):
        if marker in content:
            fail(f"artifact contains failure marker {marker!r}: {content[:300]!r}")
    low = content.lower()
    if "fizz" not in low or "buzz" not in low:
        fail(f"artifact missing fizz/buzz: {content[:300]!r}")
    print("[verify-2] (7/7) artifact content looks real")
    print(f"[verify-2] PASS model={(art.get('metadata') or {}).get('model')!r}")
    print(f"---preview---\n{content[:600]}\n---")


if __name__ == "__main__":
    main()
