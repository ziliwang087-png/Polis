#!/usr/bin/env python3
"""LOOP-3 evaluator: a SECOND built-in agent (polis-platform-translator) handles a translate job.

Conditions:
  1) /health 200
  2) agents listing has BOTH polis-platform-py and polis-platform-translator online
  3) test user submits skill=translate job (zh->en)
  4) within 60s job=completed, artifact.metadata.by == 'polis-platform-translator'
  5) artifact has english (alpha+space) characters and not just chinese
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
    print(f"[verify-3] FAIL: {msg}", file=sys.stderr); sys.exit(code)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://127.0.0.1:8765")
    ap.add_argument("--user-email", default="alice2@example.com")
    ap.add_argument("--user-password", default="Alice2Pass-123")
    ap.add_argument("--watch-secs", type=int, default=60)
    args = ap.parse_args()
    api = args.api.rstrip("/")

    try:
        h = http("GET", f"{api}/health", timeout=5)
    except Exception as e:
        fail(f"backend unreachable: {e}", code=2)

    agents = http("GET", f"{api}/api/v1/agents")
    names = {a["name"]: a for a in agents}
    for needed in ("polis-platform-py", "polis-platform-translator"):
        a = names.get(needed)
        if not a:
            fail(f"{needed!r} not registered")
        if a.get("status") != "online":
            fail(f"{needed!r} status={a.get('status')}, want online")
    print("[verify-3] (1) both built-in agents online")

    try:
        tok = http("POST", f"{api}/api/v1/auth/login",
                   body={"email": args.user_email, "password": args.user_password})["token"]
    except urllib.error.HTTPError:
        tok = http("POST", f"{api}/api/v1/auth/register",
                   body={"email": args.user_email, "password": args.user_password,
                         "username": "alice2_loop"})["token"]

    body = {
        "title": "Loop verify: translate",
        "description": "Translate to English: 这家公司今年的目标是把代码审查的平均周期从 48 小时缩短到 6 小时。Output the English translation only.",
        "required_skill": "translate",
        "input_messages": [{"role": "user", "parts": [{"kind": "text", "text": "translate"}]}],
        "attachments": [],
    }
    job = http("POST", f"{api}/api/v1/jobs", token=tok, body=body, timeout=15)
    job_id = job["id"]
    print(f"[verify-3] (2) submitted {job_id[:8]}")

    deadline = time.time() + args.watch_secs
    detail, last = None, None
    while time.time() < deadline:
        time.sleep(2)
        detail = http("GET", f"{api}/api/v1/jobs/{job_id}", timeout=10)
        st = detail["status"]
        if st != last:
            print(f"[verify-3]   status={st}"); last = st
        if st == "completed": break
        if st in ("failed","canceled"): fail(f"job ended {st}")
    else:
        fail(f"not completed in {args.watch_secs}s")

    arts = detail.get("artifacts") or []
    art = next((a for a in arts
                if (a.get("metadata") or {}).get("by") == "polis-platform-translator"), None)
    if not art:
        seen = [(a.get("metadata") or {}).get("by") for a in arts]
        fail(f"no artifact from polis-platform-translator. seen: {seen}")
    print("[verify-3] (3) artifact from translator present")

    content = art.get("content") or ""
    if len(content) < 30:
        fail(f"artifact too short: {content!r}")
    import re
    eng_chars = sum(1 for c in content if re.match(r"[A-Za-z]", c))
    if eng_chars < 20:
        fail(f"artifact lacks english chars ({eng_chars}): {content[:200]!r}")
    print(f"[verify-3] (4) english chars={eng_chars}")
    print(f"[verify-3] PASS\n--- {content[:300]} ---")
    sys.exit(0)


if __name__ == "__main__":
    main()
