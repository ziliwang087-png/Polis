#!/usr/bin/env python3
"""Demo data cleanup — keep prod Supabase from filling up with loop test users.

Targets test/demo data that meets ALL of these:
  - user.email matches a known demo prefix (loop-demo-e2e-, l1*-, inbox-probe-, l11-stale-, check-, l15-, l15probe@)
  - user is OLDER than --age-hours (default 24h)
  - user has no active claimed/working/submitted-with-progress jobs in last 1h

Then deletes (in order, due to FK cascade or explicit cleanup):
  - job_events for that user's jobs
  - artifacts for that user's jobs
  - jobs where from_user_id = user.id
  - agents owned by user (cascades to skills)
  - the user row itself

Default mode: --dry-run (only counts; no writes).
Add --apply to actually delete. Always prints a summary.

Usage:
  POLIS_LOOP_DEMO_PREFIXES="loop-demo-e2e-,inbox-probe-,l11-stale-,l15-,check-" \\
  python scripts/loop/cleanup_demo_data.py --age-hours 24 --apply
"""
from __future__ import annotations

import argparse
import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor


DEFAULT_PREFIXES = (
    "loop-demo-e2e-",
    "inbox-probe-",
    "l11-stale-",
    "l15-",
    "l15probe",
    "check-",
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--age-hours", type=int, default=24,
                    help="Only delete users older than N hours (default 24)")
    ap.add_argument("--apply", action="store_true",
                    help="Actually perform the deletes (default: dry-run)")
    ap.add_argument("--limit", type=int, default=200,
                    help="Max users to process per run (default 200)")
    args = ap.parse_args()

    prefixes_env = os.getenv("POLIS_LOOP_DEMO_PREFIXES")
    prefixes = (
        tuple(p.strip() for p in prefixes_env.split(",") if p.strip())
        if prefixes_env else DEFAULT_PREFIXES
    )
    print(f"[cleanup] prefixes={prefixes}")
    print(f"[cleanup] age_hours={args.age_hours}  mode={'APPLY' if args.apply else 'DRY-RUN'}")

    db = os.environ.get("DATABASE_URL")
    if not db:
        print("[cleanup] DATABASE_URL not set", file=sys.stderr)
        sys.exit(2)

    like_clauses = " OR ".join(["email LIKE %s"] * len(prefixes))
    like_params = [p + "%" for p in prefixes]

    with psycopg2.connect(db) as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # 1. Find candidate users
        cur.execute(
            f"""
            SELECT id::text AS id, email, created_at
              FROM users
             WHERE ({like_clauses})
               AND created_at < NOW() - make_interval(hours => %s)
             ORDER BY created_at ASC
             LIMIT %s
            """,
            (*like_params, args.age_hours, args.limit),
        )
        candidates = cur.fetchall()
        print(f"[cleanup] found {len(candidates)} candidate user(s)")
        if not candidates:
            return

        ids = [c["id"] for c in candidates]

        # 2. Recent activity guard: skip users with any active job in last 1h
        cur.execute(
            """
            SELECT DISTINCT from_user_id::text AS uid
              FROM jobs
             WHERE from_user_id::text = ANY(%s)
               AND (
                    (status IN ('claimed','working') AND claimed_at >= NOW() - INTERVAL '1 hour')
                 OR (status = 'submitted' AND created_at >= NOW() - INTERVAL '1 hour')
               )
            """,
            (ids,),
        )
        active_uids = {r["uid"] for r in cur.fetchall()}
        if active_uids:
            print(f"[cleanup] skipping {len(active_uids)} user(s) with active jobs (<1h)")
        purge = [c for c in candidates if c["id"] not in active_uids]
        print(f"[cleanup] will purge {len(purge)} user(s)")

        if not purge:
            return

        purge_ids = [c["id"] for c in purge]

        # 3. Pre-count what will be deleted
        cur.execute(
            "SELECT COUNT(*)::int AS n FROM jobs WHERE from_user_id::text = ANY(%s)",
            (purge_ids,),
        )
        njobs = cur.fetchone()["n"]
        cur.execute(
            "SELECT COUNT(*)::int AS n FROM agents WHERE owner_id::text = ANY(%s)",
            (purge_ids,),
        )
        nagents = cur.fetchone()["n"]
        cur.execute(
            """SELECT COUNT(*)::int AS n FROM job_events
                WHERE job_id IN (SELECT id FROM jobs WHERE from_user_id::text = ANY(%s))""",
            (purge_ids,),
        )
        nevents = cur.fetchone()["n"]

        print(f"[cleanup] would delete: users={len(purge)}  jobs={njobs}  "
              f"agents={nagents}  job_events={nevents}")

        if not args.apply:
            print("[cleanup] DRY-RUN — no changes written. Re-run with --apply to delete.")
            return

        # 4. Cascade delete (job_events first; jobs has FK from artifacts/job_events with ON DELETE CASCADE)
        cur.execute(
            """DELETE FROM job_events
                WHERE job_id IN (SELECT id FROM jobs WHERE from_user_id::text = ANY(%s))""",
            (purge_ids,),
        )
        cur.execute(
            "DELETE FROM jobs WHERE from_user_id::text = ANY(%s)",
            (purge_ids,),
        )
        cur.execute(
            "DELETE FROM agent_skills WHERE agent_id IN (SELECT id FROM agents WHERE owner_id::text = ANY(%s))",
            (purge_ids,),
        )
        cur.execute(
            "DELETE FROM agents WHERE owner_id::text = ANY(%s)",
            (purge_ids,),
        )
        cur.execute(
            "DELETE FROM users WHERE id::text = ANY(%s)",
            (purge_ids,),
        )
        conn.commit()
        print(f"[cleanup] DELETED users={len(purge)} jobs={njobs} agents={nagents} events={nevents}")


if __name__ == "__main__":
    main()
