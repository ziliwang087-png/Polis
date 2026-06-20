#!/usr/bin/env python3
"""LOOP-8 demo: create 5 jobs, wait for real artifacts, emit markdown report."""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path


TASKS = [
    {
        "skill": "python",
        "title": "Demo: Python fizzbuzz",
        "description": "Write a complete runnable Python FizzBuzz from 1 to 30 as a code block.",
        "checks": ("fizz", "buzz"),
    },
    {
        "skill": "translate",
        "title": "Demo: translate launch sentence",
        "description": "Translate to English only: 我们正在把 AI agent 的任务交付流程变得更可靠、更透明。",
        "checks": ("agent", "reliable"),
    },
    {
        "skill": "write",
        "title": "Demo: write product update",
        "description": "Write a concise 4-sentence product update for Polis, an AI agent task network.",
        "checks": ("polis", "agent"),
    },
    {
        "skill": "review",
        "title": "Demo: review code snippet",
        "description": (
            "Review this Python snippet and point out the bug plus a fix:\n"
            "def average(xs):\n"
            "    return sum(xs) / len(xs)\n"
            "print(average([]))"
        ),
        "checks": ("zero", "empty"),
    },
    {
        "skill": "research",
        "title": "Demo: research deployment risk",
        "description": (
            "Summarize three concrete risks when using PostgreSQL LISTEN/NOTIFY "
            "through a transaction-pooling database proxy. Keep it practical."
        ),
        "checks": ("listen", "notify"),
    },
]


def http(method, url, *, token=None, body=None, timeout=10):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, method=method, headers=headers, data=data)
    raw = urllib.request.urlopen(req, timeout=timeout).read().decode()
    return json.loads(raw) if raw else None


def fail(msg):
    print(f"[demo-e2e] FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def assert_real_artifact(job, task):
    artifacts = job.get("artifacts") or []
    if not artifacts:
        fail(f"{task['title']}: no artifacts")
    artifact = artifacts[0]
    content = artifact.get("content") or ""
    if len(content) < 40:
        fail(f"{task['title']}: artifact too short: {content!r}")
    lowered = content.lower()
    for marker in ("llm call failed", "调用 llm 失败", "[demo-bot]", "demo-bot handled"):
        if marker in lowered:
            fail(f"{task['title']}: fake/failure marker {marker!r}: {content[:200]!r}")
    missing = [needle for needle in task["checks"] if needle not in lowered]
    if missing:
        fail(f"{task['title']}: missing expected terms {missing}: {content[:300]!r}")
    return artifact


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="https://polis-backend-production.up.railway.app")
    ap.add_argument("--watch-secs", type=int, default=150)
    ap.add_argument("--report", default="/tmp/polis-demo-e2e-report.md")
    args = ap.parse_args()
    api = args.api.rstrip("/")
    suffix = str(int(time.time()))

    health = http("GET", f"{api}/health", timeout=8)
    if health.get("status") != "healthy":
        fail(f"/health not healthy: {health}")

    auth = http(
        "POST",
        f"{api}/api/v1/auth/register",
        body={
            "email": f"loop-demo-e2e-{suffix}@example.com",
            "password": "LoopDemoE2EPass-123",
            "username": f"loopdemoe2e{suffix[-8:]}",
            "display_name": "Loop Demo E2E",
        },
        timeout=15,
    )
    token = auth["token"]
    print("[demo-e2e] user registered")

    jobs = []
    for task in TASKS:
        job = http(
            "POST",
            f"{api}/api/v1/jobs",
            token=token,
            body={
                "title": task["title"],
                "description": task["description"],
                "required_skill": task["skill"],
                "input_messages": [],
                "attachments": [],
            },
            timeout=15,
        )
        jobs.append({"task": task, "id": job["id"]})
        print(f"[demo-e2e] submitted {task['skill']}: {job['id'][:8]}")

    remaining = {job["id"] for job in jobs}
    details = {}
    deadline = time.time() + args.watch_secs
    while remaining and time.time() < deadline:
        time.sleep(3)
        for job in list(jobs):
            if job["id"] not in remaining:
                continue
            detail = http("GET", f"{api}/api/v1/jobs/{job['id']}", timeout=12)
            status = detail["status"]
            print(f"[demo-e2e] {job['task']['skill']} {job['id'][:8]} status={status}")
            if status == "completed":
                details[job["id"]] = detail
                remaining.remove(job["id"])
            elif status in ("failed", "canceled"):
                fail(f"{job['task']['title']} ended with status={status}")

    if remaining:
        fail(f"{len(remaining)} job(s) did not complete within {args.watch_secs}s: {sorted(remaining)}")

    rows = []
    for job in jobs:
        detail = details[job["id"]]
        artifact = assert_real_artifact(detail, job["task"])
        content = artifact.get("content") or ""
        rows.append({
            "skill": job["task"]["skill"],
            "title": job["task"]["title"],
            "job_id": job["id"],
            "by": (artifact.get("metadata") or {}).get("by"),
            "preview": " ".join(content.split())[:220],
        })

    lines = [
        "# Polis Demo E2E Report",
        "",
        f"- API: `{api}`",
        f"- Generated: `{time.strftime('%Y-%m-%d %H:%M:%S %z')}`",
        f"- Jobs completed: `{len(rows)}/{len(TASKS)}`",
        "",
        "| Skill | Job | Artifact by | Preview |",
        "|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| `{row['skill']}` | `{row['job_id'][:8]}` {row['title']} | "
            f"`{row['by']}` | {row['preview'].replace('|', '/')} |"
        )
    lines.append("")
    lines.append("All artifacts passed basic non-fake content checks.")
    report = "\n".join(lines) + "\n"
    Path(args.report).write_text(report)
    print(report)
    print(f"[demo-e2e] report written to {args.report}")


if __name__ == "__main__":
    main()
