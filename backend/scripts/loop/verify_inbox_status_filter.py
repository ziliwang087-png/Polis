#!/usr/bin/env python3
"""LOOP-9 evaluator: inbox SSE refuses to deliver to offline agents.

机械验证条件（全部满足才 pass）：
  1. /health 返 200
  2. 注册一个 fresh user
  3. 用该 user 注册两个 agent，都声明 skill='probe-skill-Lxx'(unique)
     - agent A status=online
     - agent B status=offline
  4. 该 user 发 1 个 required_skill='probe-skill-Lxx' 任务
  5. 同时打开 A 和 B 的 inbox(?once=true)：
     - A 收到 1 条 job.available 事件，event.id 等于该任务 UUID
     - B 不收到任何 job.available 事件，且收到 info 事件 reason=='agent offline'
  6. 把 A status 改为 offline，再开一次 ?once=true：
     - A 也不收到 job.available，转成 info 事件
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
import urllib.error
import uuid


def http(method, url, *, token=None, body=None, timeout=15):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, method=method, headers=headers, data=data)
    raw = urllib.request.urlopen(req, timeout=timeout).read().decode()
    return json.loads(raw) if raw else None


def fail(msg):
    print(f"[verify-inbox-filter] FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def parse_sse(text):
    """Parse SSE text into list of (event, data_dict) tuples."""
    events = []
    event = None
    data_lines = []
    for line in text.splitlines():
        if line.startswith("event:"):
            event = line.split(":", 1)[1].strip()
        elif line.startswith("data:"):
            data_lines.append(line.split(":", 1)[1].strip())
        elif line == "":
            if event and data_lines:
                payload = "\n".join(data_lines)
                try:
                    events.append((event, json.loads(payload)))
                except json.JSONDecodeError:
                    events.append((event, {"_raw": payload}))
            event = None
            data_lines = []
    return events


def fetch_inbox_once(api, agent_id, token):
    url = f"{api}/api/v1/agents/{agent_id}/inbox?once=true"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    raw = urllib.request.urlopen(req, timeout=20).read().decode()
    return parse_sse(raw)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://127.0.0.1:8765")
    args = ap.parse_args()
    api = args.api.rstrip("/")
    suffix = uuid.uuid4().hex[:10]
    skill_name = f"probe-skill-{suffix}"

    health = http("GET", f"{api}/health", timeout=8)
    if health.get("status") != "healthy":
        fail(f"/health not healthy: {health}")

    # 1. register user
    user = http("POST", f"{api}/api/v1/auth/register", body={
        "email": f"inbox-probe-{suffix}@example.com",
        "password": "InboxProbePass-123",
        "username": f"inboxp{suffix[:8]}",
        "display_name": "Inbox Probe",
    })
    user_token = user["token"]
    print(f"[verify-inbox-filter] user registered: {user.get('user',{}).get('id','?')[:8]}")

    # 2. create agent A (online) + B (offline)
    def make_agent(name, status):
        a = http("POST", f"{api}/api/v1/agents", token=user_token, body={
            "name": name,
            "display_name": name,
            "description": "L9 inbox filter probe",
            "agent_card": {"version": "1.0", "name": name, "skills": [skill_name]},
            "skills": [skill_name],
            "status": status,
            "auth_method": "none",
        })
        return a["id"]

    a_id = make_agent(f"l9-online-{suffix}", "online")
    b_id = make_agent(f"l9-offline-{suffix}", "offline")
    print(f"[verify-inbox-filter] agent A (online) = {a_id[:8]}")
    print(f"[verify-inbox-filter] agent B (offline) = {b_id[:8]}")

    # 3. submit job
    job = http("POST", f"{api}/api/v1/jobs", token=user_token, body={
        "title": "L9 inbox filter probe job",
        "description": "Just sit in the inbox; nobody needs to actually run me.",
        "required_skill": skill_name,
        "input_messages": [],
        "attachments": [],
    })
    job_id = job["id"]
    print(f"[verify-inbox-filter] job submitted: {job_id[:8]}")

    # Give backlog a moment to settle
    time.sleep(1)

    # 4. agent A online inbox should yield job.available
    ev_a = fetch_inbox_once(api, a_id, user_token)
    a_jobs = [e for e in ev_a if e[0] == "job.available"]
    a_infos = [e for e in ev_a if e[0] == "info"]
    if not a_jobs:
        fail(f"online agent A got NO job.available events. all events: {ev_a}")
    if not any(e[1].get("id") == job_id for e in a_jobs):
        fail(f"online agent A inbox missing the probe job {job_id}; got: {[e[1].get('id') for e in a_jobs]}")
    print(f"[verify-inbox-filter] PASS (A online): got {len(a_jobs)} job.available, includes probe job")

    # 5. agent B offline inbox should NOT yield job.available; should yield info=offline
    ev_b = fetch_inbox_once(api, b_id, user_token)
    b_jobs = [e for e in ev_b if e[0] == "job.available"]
    b_infos = [e for e in ev_b if e[0] == "info"]
    if b_jobs:
        fail(f"offline agent B leaked {len(b_jobs)} job.available events: {[e[1].get('id') for e in b_jobs]}")
    if not any(e[1].get("reason") == "agent offline" for e in b_infos):
        fail(f"offline agent B did not emit info reason=agent offline; got: {ev_b}")
    print(f"[verify-inbox-filter] PASS (B offline): zero job.available, info reason=agent offline received")

    # 6. flip A to offline, re-check
    http("POST", f"{api}/api/v1/agents/{a_id}/heartbeat", token=user_token, body={"status": "offline"})
    time.sleep(0.5)
    ev_a2 = fetch_inbox_once(api, a_id, user_token)
    a2_jobs = [e for e in ev_a2 if e[0] == "job.available"]
    a2_infos = [e for e in ev_a2 if e[0] == "info"]
    if a2_jobs:
        fail(f"agent A after flip-to-offline still leaks {len(a2_jobs)} job.available")
    if not any(e[1].get("reason") == "agent offline" for e in a2_infos):
        fail(f"agent A after flip-to-offline did not emit info=agent offline; got: {ev_a2}")
    print("[verify-inbox-filter] PASS (A flipped offline): inbox correctly suppressed")

    print("[verify-inbox-filter] ALL CHECKS PASSED")


if __name__ == "__main__":
    main()
