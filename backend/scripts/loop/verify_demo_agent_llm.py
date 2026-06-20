#!/usr/bin/env python3
"""LOOP-7 evaluator: examples/demo_agent.py calls an LLM and delivers real output."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


def http(method, url, *, token=None, body=None, timeout=10):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, method=method, headers=headers, data=data)
    raw = urllib.request.urlopen(req, timeout=timeout).read().decode()
    return json.loads(raw) if raw else None


def fail(msg):
    print(f"[verify-7] FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://127.0.0.1:8765")
    ap.add_argument("--watch-secs", type=int, default=70)
    args = ap.parse_args()
    api = args.api.rstrip("/")
    suffix = str(int(time.time()))
    root = Path(__file__).resolve().parents[3]
    demo = root / "examples" / "demo_agent.py"
    agent_name = f"loop-demo-agent-{suffix}"
    skill = f"demo-python-{suffix}"

    proc = subprocess.Popen(
        [
            sys.executable,
            str(demo),
            "--api",
            api,
            "--email",
            f"loop-demo-agent-{suffix}@example.com",
            "--password",
            "LoopDemoAgentPass-123",
            "--username",
            f"loopdemoagent{suffix[-8:]}",
            "--agent-name",
            agent_name,
            "--skills",
            skill,
            "--max-jobs",
            "1",
        ],
        cwd=str(root),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        deadline = time.time() + 25
        agent_id = None
        while time.time() < deadline:
            if proc.poll() is not None:
                out = proc.stdout.read() if proc.stdout else ""
                fail(f"demo_agent exited before registering agent:\n{out}")
            agents = http("GET", f"{api}/api/v1/agents", timeout=10)
            match = next((a for a in agents if a.get("name") == agent_name), None)
            if match and match.get("status") == "online":
                agent_id = match["id"]
                break
            time.sleep(1)
        if not agent_id:
            fail(f"demo agent {agent_name} did not come online")
        print(f"[verify-7] (1/5) demo agent online {agent_id[:8]}")

        auth = http(
            "POST",
            f"{api}/api/v1/auth/register",
            body={
                "email": f"loop-demo-user-{suffix}@example.com",
                "password": "LoopDemoUserPass-123",
                "username": f"loopdemouser{suffix[-8:]}",
            },
            timeout=15,
        )
        token = auth["token"]
        job = http(
            "POST",
            f"{api}/api/v1/jobs",
            token=token,
            body={
                "title": "Demo agent fizzbuzz",
                "description": (
                    "Write a standard FizzBuzz in Python from 1 to 30. "
                    "Multiples of 3 -> Fizz, of 5 -> Buzz, of 15 -> FizzBuzz, "
                    "else the number. Provide a complete runnable code block."
                ),
                "required_skill": skill,
                "input_messages": [],
                "attachments": [],
            },
            timeout=15,
        )
        job_id = job["id"]
        print(f"[verify-7] (2/5) job submitted {job_id[:8]}")

        deadline = time.time() + args.watch_secs
        detail, last = None, None
        while time.time() < deadline:
            time.sleep(2)
            detail = http("GET", f"{api}/api/v1/jobs/{job_id}", timeout=12)
            status = detail["status"]
            if status != last:
                print(f"[verify-7]   ... status={status} progress={detail.get('progress') or '-'}")
                last = status
            if status == "completed":
                break
            if status in ("failed", "canceled"):
                fail(f"job ended with status={status}")
        else:
            fail(f"job not completed within {args.watch_secs}s (last status={last})")
        print("[verify-7] (3/5) job completed")

        art = next(
            (
                a for a in (detail.get("artifacts") or [])
                if (a.get("metadata") or {}).get("by") == "demo_agent.py"
            ),
            None,
        )
        if not art:
            seen = [(a.get("metadata") or {}).get("by") for a in (detail.get("artifacts") or [])]
            fail(f"no artifact from demo_agent.py. seen: {seen}")
        print("[verify-7] (4/5) artifact from demo_agent.py present")

        content = art.get("content") or ""
        bad = ("[demo-bot]", "demo-bot handled", "LLM call failed", "调用 LLM 失败")
        if len(content) < 80:
            fail(f"artifact too short ({len(content)}): {content!r}")
        for marker in bad:
            if marker in content:
                fail(f"artifact contains fake/failure marker {marker!r}: {content[:300]!r}")
        low = content.lower()
        if "fizz" not in low or "buzz" not in low:
            fail(f"artifact missing fizz/buzz: {content[:300]!r}")
        print("[verify-7] (5/5) artifact content is real fizzbuzz output")
        print(f"[verify-7] PASS\n---preview---\n{content[:600]}\n---")
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()


if __name__ == "__main__":
    main()
