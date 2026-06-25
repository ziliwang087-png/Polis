#!/usr/bin/env python3
"""LOOP-4 evaluator: hit every public frontend route, fail on 5xx or React error boundary."""
from __future__ import annotations
import argparse, sys, urllib.request

ROUTES = ["/", "/agents", "/agents/new", "/tasks", "/tasks/new", "/login", "/register", "/me"]
CRASH_MARKERS = ["This page couldn't load", "Application error", "Internal Server Error"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="https://polis-frontend-three.vercel.app")
    args = ap.parse_args()

    failed = []
    for r in ROUTES:
        url = args.base.rstrip("/") + r
        try:
            resp = urllib.request.urlopen(url, timeout=15)
            html = resp.read().decode("utf-8", errors="replace")
        except Exception as e:
            failed.append((r, f"fetch error: {e}")); continue
        for m in CRASH_MARKERS:
            if m in html:
                failed.append((r, f"crash marker: {m!r}")); break

    if failed:
        for r, why in failed:
            print(f"[verify-4] FAIL {r}: {why}", file=sys.stderr)
        sys.exit(1)

    print(f"[verify-4] PASS - {len(ROUTES)} routes clean")
    sys.exit(0)


if __name__ == "__main__":
    main()
