#!/usr/bin/env python3
"""LOOP-5 evaluator: /.well-known/agent.json exposes real marketplace skills."""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request


def fail(msg):
    print(f"[verify-5] FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="https://polis-backend-production.up.railway.app")
    args = ap.parse_args()
    api = args.api.rstrip("/")

    data = json.loads(urllib.request.urlopen(f"{api}/.well-known/agent.json", timeout=12).read().decode())
    skills = data.get("skills") or []
    ids = [s.get("id") or s.get("skill_id") or s.get("name") for s in skills if isinstance(s, dict)]
    real = [sid for sid in ids if sid and not str(sid).startswith("polis.jobs.")]

    if not skills:
        fail("skills list is empty")
    if len(real) < 5:
        fail(f"expected at least 5 real marketplace skills, got {len(real)}: {ids}")
    for needed in ("python", "translate"):
        if needed not in real:
            fail(f"missing expected real skill {needed!r}; got {real}")

    print(f"[verify-5] PASS - {len(real)} real skills exposed: {', '.join(real[:12])}")


if __name__ == "__main__":
    main()
