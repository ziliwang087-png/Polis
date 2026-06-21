#!/usr/bin/env python3
"""Evaluator suite runner — quick health check across all loop verifiers.

Splits evaluators into 3 tiers based on what they need:

  1. UNIT — pure, no I/O outside the local repo (TestClient, in-memory)
     Always safe to run; no DB write, no network.
  2. LOCAL_HTTP — needs a running backend at http://127.0.0.1:8765
     Run after `uvicorn` is up. Expected to register a few demo users
     in the dev DB; cleanup cron will reap them.
  3. PROD — hits public Polis prod URL
     Run only when you intend to verify a fresh deploy.

Usage:
    python scripts/loop/run_eval_suite.py            # UNIT tier only (default)
    python scripts/loop/run_eval_suite.py --local    # UNIT + LOCAL_HTTP
    python scripts/loop/run_eval_suite.py --prod     # UNIT + PROD
    python scripts/loop/run_eval_suite.py --all      # all three tiers

Each evaluator runs in its own subprocess; failures don't stop the suite.
Report at the end: PASS/FAIL counts + which ones failed.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]  # backend/

# Tier definitions. Each entry: (script_basename, description, [extra_args])
UNIT = [
    ("verify_worker_heartbeat.py", "L19/L21 worker heartbeat (TestClient)", []),
    ("verify_stale_claim_reaper.py", "L11/L18 reaper sync sweep (DB unit)", []),
]

LOCAL_HTTP = [
    ("verify_health_deep.py", "L13 /health/deep async + reaper state",
     ["--base", "http://127.0.0.1:8765"]),
    ("verify_reaper_admin_api.py", "L15/L18 admin reaper endpoints + auth",
     ["--base", "http://127.0.0.1:8765/api/v1"]),
    ("verify_admin_workers_api.py", "L20 admin workers endpoint + auth",
     ["--base", "http://127.0.0.1:8765/api/v1"]),
]

PROD = [
    ("verify_health_deep.py", "L13 /health/deep prod",
     ["--base", "https://polis-backend-production.up.railway.app"]),
    ("verify_reaper_admin_api.py", "L15/L18 admin reaper prod",
     ["--base", "https://polis-backend-production.up.railway.app/api/v1"]),
    ("verify_admin_workers_api.py", "L20 admin workers prod",
     ["--base", "https://polis-backend-production.up.railway.app/api/v1"]),
]


def run_one(script: str, desc: str, args: list[str], timeout: int = 60) -> tuple[bool, str]:
    path = REPO / "scripts" / "loop" / script
    if not path.exists():
        return False, f"NOT FOUND: {path}"
    cmd = [sys.executable, str(path), *args]
    t0 = time.time()
    try:
        r = subprocess.run(
            cmd,
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return False, f"TIMEOUT after {timeout}s"
    dt = time.time() - t0
    last_line = ""
    for line in (r.stdout or "").splitlines()[::-1]:
        if line.strip():
            last_line = line.strip()
            break
    if r.returncode == 0:
        return True, f"PASS ({dt:.1f}s) — {last_line[:120]}"
    err_tail = (r.stderr or r.stdout or "").splitlines()[-3:]
    return False, f"FAIL rc={r.returncode} ({dt:.1f}s) — {' | '.join(err_tail)[:300]}"


def run_tier(name: str, evals: list[tuple[str, str, list[str]]]) -> tuple[int, int, list[str]]:
    print(f"\n=== Tier: {name} ({len(evals)} evaluators) ===")
    passed = 0
    failed_names = []
    for script, desc, args in evals:
        ok, msg = run_one(script, desc, args)
        symbol = "✓" if ok else "✗"
        print(f"  {symbol} {script:38s} — {msg}")
        if ok:
            passed += 1
        else:
            failed_names.append(script)
    return passed, len(evals), failed_names


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--local", action="store_true",
                    help="Also run LOCAL_HTTP tier (needs backend on :8765)")
    ap.add_argument("--prod", action="store_true",
                    help="Also run PROD tier (hits public Railway URL)")
    ap.add_argument("--all", action="store_true",
                    help="Run all tiers (UNIT + LOCAL_HTTP + PROD)")
    args = ap.parse_args()

    do_local = args.local or args.all
    do_prod = args.prod or args.all

    total_pass = 0
    total = 0
    all_fails: list[str] = []

    p, n, fails = run_tier("UNIT", UNIT)
    total_pass += p
    total += n
    all_fails.extend(f"UNIT/{x}" for x in fails)

    if do_local:
        p, n, fails = run_tier("LOCAL_HTTP", LOCAL_HTTP)
        total_pass += p
        total += n
        all_fails.extend(f"LOCAL_HTTP/{x}" for x in fails)

    if do_prod:
        p, n, fails = run_tier("PROD", PROD)
        total_pass += p
        total += n
        all_fails.extend(f"PROD/{x}" for x in fails)

    print(f"\n{'='*60}")
    print(f"Summary: {total_pass}/{total} PASS")
    if all_fails:
        print(f"Failures: {', '.join(all_fails)}")
        sys.exit(1)
    print("ALL EVALUATORS GREEN")


if __name__ == "__main__":
    main()
