#!/usr/bin/env python3
"""LOOP-6 evaluator: completed job rating updates the assigned agent avg_rating."""
from __future__ import annotations

import argparse
import json
import math
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


def fail(msg):
    print(f"[verify-6] FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="https://polis-backend-production.up.railway.app")
    args = ap.parse_args()
    api = args.api.rstrip("/")
    suffix = str(int(time.time()))

    health = http("GET", f"{api}/health", timeout=8)
    if health.get("status") != "healthy":
        fail(f"/health not healthy: {health}")
    print("[verify-6] (1/7) backend healthy")

    auth = http(
        "POST",
        f"{api}/api/v1/auth/register",
        body={
            "email": f"loop-rating-{suffix}@example.com",
            "password": "LoopRatingPass-123",
            "username": f"looprating{suffix[-8:]}",
            "display_name": "Loop Rating",
        },
        timeout=15,
    )
    token = auth["token"]
    print("[verify-6] (2/7) user registered")

    agent = http(
        "POST",
        f"{api}/api/v1/agents",
        token=token,
        body={
            "name": f"loop-rating-agent-{suffix}",
            "display_name": "Loop Rating Agent",
            "description": "Fresh agent for rating flow verification",
            "auth_method": "none",
            "agent_card": {"version": "1.0", "skills": ["rating-check"]},
            "skills": ["rating-check"],
            "status": "online",
        },
        timeout=15,
    )
    agent_id = agent["id"]
    print(f"[verify-6] (3/7) agent registered {agent_id[:8]}")

    job = http(
        "POST",
        f"{api}/api/v1/jobs",
        token=token,
        body={
            "title": "Rating flow check",
            "description": "Deliver a tiny artifact so rating can be tested.",
            "required_skill": "rating-check",
            "input_messages": [],
            "attachments": [],
        },
        timeout=15,
    )
    job_id = job["id"]
    http("POST", f"{api}/api/v1/jobs/{job_id}/claim", token=token, body={"agent_id": agent_id}, timeout=15)
    print("[verify-6] (4/7) job claimed")

    completed = http(
        "POST",
        f"{api}/api/v1/jobs/{job_id}/artifacts",
        token=token,
        body={
            "agent_id": agent_id,
            "type": "text",
            "content": "rating flow artifact",
            "metadata": {"by": "verify_rating_flow.py"},
        },
        timeout=15,
    )
    if completed.get("status") != "completed":
        fail(f"artifact submit did not complete job: {completed}")
    print("[verify-6] (5/7) artifact submitted and job completed")

    rating = http(
        "POST",
        f"{api}/api/v1/jobs/{job_id}/rate",
        token=token,
        body={"stars": 5, "feedback": "loop rating check"},
        timeout=15,
    )
    if rating.get("stars") != 5:
        fail(f"rating response wrong: {rating}")
    print("[verify-6] (6/7) rating submitted")

    refreshed = http("GET", f"{api}/api/v1/agents/{agent_id}", timeout=15)
    avg = refreshed.get("avg_rating")
    if avg is None or not math.isclose(float(avg), 5.0, rel_tol=0, abs_tol=0.001):
        fail(f"avg_rating is {avg!r}, want 5.0")
    print("[verify-6] (7/7) avg_rating updated to 5.0")
    print("[verify-6] PASS")


if __name__ == "__main__":
    main()
