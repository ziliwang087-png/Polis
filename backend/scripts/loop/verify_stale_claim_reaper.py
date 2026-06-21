#!/usr/bin/env python3
"""LOOP-11 evaluator: stale-claim reaper actually reaps.

机械验证条件:
  1. 准备 db: 注册一个 fresh user 和 fresh agent
  2. SQL 直接 INSERT 一条 jobs 行,status='claimed',
     to_agent_id=fresh_agent, claimed_at=NOW() - 10 minutes,
     不写 progress event
  3. 同进程 import app.stale_claim_reaper.reap_once,跑一次
  4. 该任务必须变 status='submitted',to_agent_id=NULL
  5. 该任务的 job_events 表新增一条 event_type='stale_claim_reaped'
     payload.previous_agent_id=fresh_agent 的事件
  6. 不会误杀: 第二个新鲜 claim(claimed_at=NOW())不被重置;
     第三个 5 分钟前 claim 但 4 分钟前有 progress 的也不被重置
"""
from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

# 让 `import app.*` 工作
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))


def fail(msg):
    print(f"[verify-stale-claim-reaper] FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def main():
    os.environ.setdefault("POLIS_STALE_CLAIM_AGE_SECS", "300")  # 5 min default
    from app.database import get_db_connection
    from app import stale_claim_reaper

    suffix = uuid.uuid4().hex[:10]
    owner_id = uuid.uuid4()
    agent_id = uuid.uuid4()
    user_email = f"l11-stale-{suffix}@example.com"

    stale_job_id = uuid.uuid4()
    fresh_job_id = uuid.uuid4()
    progressing_job_id = uuid.uuid4()

    # 1. seed user + agent + 3 jobs
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO users (id, email, password_hash, username, display_name) VALUES (%s, %s, %s, %s, %s)",
            (str(owner_id), user_email, "x" * 60, f"l11{suffix[:8]}", "L11 Probe"),
        )
        cur.execute(
            """INSERT INTO agents (id, owner_id, name, display_name, description,
                endpoint_url, websocket_id, auth_method, auth_config, agent_card, status)
               VALUES (%s, %s, %s, %s, %s, NULL, NULL, 'none', '{}'::jsonb, '{}'::jsonb, 'offline')""",
            (str(agent_id), str(owner_id), f"l11-agent-{suffix}", "L11", "stub"),
        )

        # job A: stale claim (older than 5 min, no progress)
        cur.execute(
            """INSERT INTO jobs (id, from_user_id, to_agent_id, title, description,
                required_skill, input_messages, attachments, status,
                claimed_at, started_at, created_at)
               VALUES (%s, %s, %s, 'L11 stale', 'stale', 'l11-skill',
                       '[]'::jsonb, '[]'::jsonb, 'claimed',
                       NOW() - interval '10 minutes',
                       NOW() - interval '10 minutes',
                       NOW() - interval '11 minutes')""",
            (str(stale_job_id), str(owner_id), str(agent_id)),
        )

        # job B: fresh claim (10s ago) — must NOT be reaped
        cur.execute(
            """INSERT INTO jobs (id, from_user_id, to_agent_id, title, description,
                required_skill, input_messages, attachments, status,
                claimed_at, started_at, created_at)
               VALUES (%s, %s, %s, 'L11 fresh', 'fresh', 'l11-skill',
                       '[]'::jsonb, '[]'::jsonb, 'claimed',
                       NOW() - interval '10 seconds',
                       NOW() - interval '10 seconds',
                       NOW() - interval '15 seconds')""",
            (str(fresh_job_id), str(owner_id), str(agent_id)),
        )

        # job C: stale claim BUT recent progress event — must NOT be reaped
        cur.execute(
            """INSERT INTO jobs (id, from_user_id, to_agent_id, title, description,
                required_skill, input_messages, attachments, status, progress,
                claimed_at, started_at, created_at)
               VALUES (%s, %s, %s, 'L11 progressing', 'progressing', 'l11-skill',
                       '[]'::jsonb, '[]'::jsonb, 'working', 'thinking...',
                       NOW() - interval '10 minutes',
                       NOW() - interval '10 minutes',
                       NOW() - interval '11 minutes')""",
            (str(progressing_job_id), str(owner_id), str(agent_id)),
        )
        cur.execute(
            """INSERT INTO job_events (job_id, event_type, payload, created_at)
               VALUES (%s, 'progress', %s::jsonb, NOW() - interval '30 seconds')""",
            (str(progressing_job_id), '{"progress": "thinking..."}'),
        )
        conn.commit()
    print(f"[verify-stale-claim-reaper] seeded user={str(owner_id)[:8]} agent={str(agent_id)[:8]}")
    print(f"  stale job:       {str(stale_job_id)[:8]}")
    print(f"  fresh job:       {str(fresh_job_id)[:8]}")
    print(f"  progressing job: {str(progressing_job_id)[:8]}")

    # 2. invoke reap_once
    try:
        reaped = stale_claim_reaper.reap_once()
        print(f"[verify-stale-claim-reaper] reap_once returned {reaped}")

        # 3. assert stale was reaped
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT id::text, status, to_agent_id::text, progress FROM jobs WHERE id::text = ANY(%s)",
                ([str(stale_job_id), str(fresh_job_id), str(progressing_job_id)],),
            )
            rows = {r["id"]: r for r in cur.fetchall()}

        s = rows[str(stale_job_id)]
        if s["status"] != "submitted":
            fail(f"stale job not reset: status={s['status']}")
        if s["to_agent_id"] is not None:
            fail(f"stale job to_agent_id not cleared: {s['to_agent_id']}")
        print("[verify-stale-claim-reaper] PASS: stale job reset to submitted")

        f = rows[str(fresh_job_id)]
        if f["status"] != "claimed":
            fail(f"fresh job wrongly reaped! status={f['status']}")
        print("[verify-stale-claim-reaper] PASS: fresh claim left alone")

        p = rows[str(progressing_job_id)]
        if p["status"] != "working":
            fail(f"progressing job wrongly reaped! status={p['status']}")
        print("[verify-stale-claim-reaper] PASS: actively-progressing job left alone")

        # 4. audit event present (uses dedicated 'stale_claim_reaped'
        # event_type after migration 20260621_stale_claim_reaped)
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """SELECT event_type, payload FROM job_events
                   WHERE job_id = %s AND event_type = 'stale_claim_reaped'""",
                (str(stale_job_id),),
            )
            evs = cur.fetchall()
        if not evs:
            fail("no stale_claim_reaped event written for stale job")
        if evs[0]["payload"].get("previous_agent_id") != str(agent_id):
            fail(f"audit event missing previous_agent_id; got {evs[0]['payload']}")
        print("[verify-stale-claim-reaper] PASS: audit event recorded with reason+previous_agent_id")

        print("[verify-stale-claim-reaper] ALL CHECKS PASSED")

    finally:
        # cleanup
        try:
            with get_db_connection() as conn:
                cur = conn.cursor()
                cur.execute("DELETE FROM job_events WHERE job_id = ANY(%s::uuid[])",
                            ([str(stale_job_id), str(fresh_job_id), str(progressing_job_id)],))
                cur.execute("DELETE FROM jobs WHERE id::text = ANY(%s)",
                            ([str(stale_job_id), str(fresh_job_id), str(progressing_job_id)],))
                cur.execute("DELETE FROM agents WHERE id = %s", (str(agent_id),))
                cur.execute("DELETE FROM users WHERE id = %s", (str(owner_id),))
                conn.commit()
            print("[verify-stale-claim-reaper] cleanup done")
        except Exception as e:
            print(f"[verify-stale-claim-reaper] cleanup warning: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
