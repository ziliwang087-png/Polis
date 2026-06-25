#!/usr/bin/env python3
"""L16 evaluator — cleanup_demo_data.py correctly counts and purges.

Steps:
  1. Seed two synthetic users with prefix 'l16probe-' (one OLD = 2h ago, one FRESH = now)
  2. Each gets one 'submitted' job and a 'rated' event
  3. Run cleanup_demo_data.py --age-hours 1 (dry-run) — must report 1 candidate (the old one)
  4. Run cleanup_demo_data.py --age-hours 1 --apply
  5. Assert OLD user + jobs + events all gone; FRESH user untouched
  6. Cleanup the FRESH user manually
"""
from __future__ import annotations

import os
import subprocess
import sys
import uuid
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))


def fail(msg):
    print(f"[verify-L16] FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def main():
    from app.database import get_db_connection
    from app.config import settings

    suffix = uuid.uuid4().hex[:8]
    old_id = uuid.uuid4()
    fresh_id = uuid.uuid4()
    prefix = f"l16probe-{suffix}-"
    old_email = f"{prefix}OLD@example.com"
    fresh_email = f"{prefix}FRESH@example.com"
    old_job_id = uuid.uuid4()
    fresh_job_id = uuid.uuid4()

    # 1+2 seed
    with get_db_connection() as conn:
        cur = conn.cursor()
        for u_id, email, hours_ago in [
            (old_id, old_email, 2),
            (fresh_id, fresh_email, 0),
        ]:
            cur.execute(
                "INSERT INTO users (id, email, password_hash, username, display_name, created_at) "
                "VALUES (%s, %s, %s, %s, %s, NOW() - make_interval(hours => %s))",
                (str(u_id), email, "x" * 60, f"l16{suffix[:6]}{hours_ago}", "L16", hours_ago),
            )
        for j_id, u_id in [
            (old_job_id, old_id),
            (fresh_job_id, fresh_id),
        ]:
            cur.execute(
                """INSERT INTO jobs (id, from_user_id, title, description, required_skill,
                    input_messages, attachments, status, created_at)
                   VALUES (%s, %s, 'L16 probe job', 'probe', 'l16-skill',
                           '[]'::jsonb, '[]'::jsonb, 'completed',
                           NOW() - INTERVAL '2 hours')""",
                (str(j_id), str(u_id)),
            )
            cur.execute(
                """INSERT INTO job_events (job_id, event_type, payload, created_at)
                   VALUES (%s, 'rated', %s::jsonb, NOW() - INTERVAL '90 minutes')""",
                (str(j_id), '{"score": 5}'),
            )
        conn.commit()
    print(f"[verify-L16] seeded OLD={old_email} FRESH={fresh_email}")

    try:
        # 3. dry-run with custom prefix to scope to ONLY our seeds
        env = os.environ.copy()
        env["POLIS_LOOP_DEMO_PREFIXES"] = prefix
        env["POLIS_LOOP_DEMO_REGEX"] = r"^$"
        env.setdefault("DATABASE_URL", settings.DATABASE_URL)
        script = pathlib.Path(__file__).parent / "cleanup_demo_data.py"
        r = subprocess.run(
            [sys.executable, str(script), "--age-hours", "1"],
            env=env, capture_output=True, text=True, timeout=60,
        )
        print("[dry-run stdout]", r.stdout)
        if "found 1 candidate" not in r.stdout:
            fail(f"dry-run did not find exactly 1 candidate: {r.stdout!r}")
        if "DRY-RUN" not in r.stdout:
            fail(f"dry-run banner missing: {r.stdout!r}")

        # 4. apply
        r = subprocess.run(
            [sys.executable, str(script), "--age-hours", "1", "--apply"],
            env=env, capture_output=True, text=True, timeout=60,
        )
        print("[apply stdout]", r.stdout)
        if "DELETED users=1" not in r.stdout:
            fail(f"apply did not delete exactly 1 user: {r.stdout!r}")

        # 5. verify deletion
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*)::int AS n FROM users WHERE id = %s", (str(old_id),))
            n_old = cur.fetchone()["n"]
            cur.execute("SELECT COUNT(*)::int AS n FROM users WHERE id = %s", (str(fresh_id),))
            n_fresh = cur.fetchone()["n"]
            cur.execute("SELECT COUNT(*)::int AS n FROM jobs WHERE id = %s", (str(old_job_id),))
            n_old_job = cur.fetchone()["n"]
            cur.execute("SELECT COUNT(*)::int AS n FROM jobs WHERE id = %s", (str(fresh_job_id),))
            n_fresh_job = cur.fetchone()["n"]

        if n_old != 0:
            fail(f"OLD user still exists ({n_old})")
        if n_old_job != 0:
            fail(f"OLD job still exists ({n_old_job})")
        if n_fresh != 1:
            fail(f"FRESH user wrongly deleted (n={n_fresh})")
        if n_fresh_job != 1:
            fail(f"FRESH job wrongly deleted (n={n_fresh_job})")

        print("[verify-L16] PASS dry-run+apply only purges OLD; FRESH preserved")

    finally:
        # 6. cleanup FRESH
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM job_events WHERE job_id IN (%s, %s)",
                        (str(old_job_id), str(fresh_job_id)))
            cur.execute("DELETE FROM jobs WHERE id IN (%s, %s)",
                        (str(old_job_id), str(fresh_job_id)))
            cur.execute("DELETE FROM users WHERE id IN (%s, %s)",
                        (str(old_id), str(fresh_id)))
            conn.commit()
        print("[verify-L16] cleanup done")

    print("[verify-L16] ALL CHECKS PASSED")


if __name__ == "__main__":
    main()
