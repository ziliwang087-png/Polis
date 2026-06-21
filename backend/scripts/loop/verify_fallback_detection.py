#!/usr/bin/env python3
"""LOOP-10 evaluator: demo_e2e fail-fast on fallback artifacts (unit-level).

Background: this used to be an end-to-end test that started a backend
with an invalid LLM key and watched demo_e2e abort. That approach is
not viable on this dev machine because the local backend shares its
Supabase Postgres with prod, so the prod platform-agents claim the
test jobs and deliver real artifacts before the local broken agent
can fall back. The behaviour we actually care about — `demo_e2e` not
silently swallowing the platform-agent's fallback string — is purely
local logic in `detect_fallback_artifact`. So we test that directly.

机械验证条件:
  1. demo_e2e.detect_fallback_artifact returns None for a real artifact
  2. detect_fallback_artifact returns a snippet for each of the four
     known fallback markers (case-insensitive)
  3. assert_real_artifact raises SystemExit on a fallback artifact
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def fail(msg):
    print(f"[verify-fallback-detection] FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def load_demo_e2e():
    here = Path(__file__).resolve()
    demo_path = here.parent / "demo_e2e.py"
    spec = importlib.util.spec_from_file_location("demo_e2e_under_test", demo_path)
    if spec is None or spec.loader is None:
        fail(f"cannot import {demo_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    demo = load_demo_e2e()

    # 1. real artifact -> None
    real_detail = {
        "artifacts": [{
            "content": "Here is your fizzbuzz:\n```python\nfor i in range(1, 31): ...\n```",
            "metadata": {"by": "polis-platform-py"},
        }]
    }
    if demo.detect_fallback_artifact(real_detail) is not None:
        fail("real artifact wrongly flagged as fallback")
    print("[verify-fallback-detection] PASS: real artifact accepted")

    # 2. each known marker is detected
    markers = (
        "[platform-agent] 调用 LLM 失败：HTTPError: 401 Unauthorized",
        "[platform-agent] LLM call failed: HTTPError 503",
        "[demo-bot] handled task: foo",
        "demo-bot handled fizzbuzz",
        "Some prefix; LLM CALL FAILED downstream",  # case-insensitive
    )
    for m in markers:
        d = {"artifacts": [{"content": m}]}
        snippet = demo.detect_fallback_artifact(d)
        if snippet is None:
            fail(f"marker not detected: {m!r}")
    print(f"[verify-fallback-detection] PASS: all {len(markers)} fallback markers detected")

    # 3. assert_real_artifact must SystemExit on fallback content
    fallback_job = {
        "artifacts": [{
            "content": "[platform-agent] 调用 LLM 失败：HTTPError: HTTP Error 503: Service Unavailable",
            "metadata": {"by": "polis-platform-py"},
        }]
    }
    fake_task = {"title": "Demo: any", "checks": ()}
    try:
        demo.assert_real_artifact(fallback_job, fake_task)
    except SystemExit as e:
        if e.code == 0:
            fail("assert_real_artifact exited 0 on fallback artifact")
    else:
        fail("assert_real_artifact did not raise on fallback artifact")
    print("[verify-fallback-detection] PASS: assert_real_artifact rejects fallback content")

    # 4. empty artifacts list -> None (don't crash)
    empty = {"artifacts": []}
    if demo.detect_fallback_artifact(empty) is not None:
        fail("empty artifacts list should yield None")
    no_arts = {}
    if demo.detect_fallback_artifact(no_arts) is not None:
        fail("missing artifacts key should yield None")
    print("[verify-fallback-detection] PASS: empty / missing artifacts handled")

    print("[verify-fallback-detection] ALL CHECKS PASSED")


if __name__ == "__main__":
    main()
