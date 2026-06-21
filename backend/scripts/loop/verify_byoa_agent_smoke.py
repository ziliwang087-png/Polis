#!/usr/bin/env python3
"""
verify_byoa_agent_smoke.py — L25 evaluator

Smoke-tests backend/byoa/agent.py without actually running the worker loop:
  1. _decode_install_token round-trip (encode → decode = original)
  2. _resolve_config picks up POLIS_INSTALL_TOKEN
  3. _resolve_config falls back to env vars when no install token
  4. _resolve_config exits cleanly when missing required fields
  5. _humanize_llm_error returns Chinese for known HTTP codes
  6. _parse_sse handles event/data/heartbeat shapes
"""
from __future__ import annotations

import base64
import io
import json
import os
import sys
import urllib.error
from pathlib import Path

# Make backend/byoa importable.
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "byoa"))

import agent  # type: ignore


def encode_bundle(api: str, token: str, agent_id: str, agent_name: str) -> str:
    raw = json.dumps({"api": api, "token": token, "agent_id": agent_id, "agent_name": agent_name}).encode()
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def t1_decode_round_trip():
    encoded = encode_bundle("https://example.com", "tok-abc", "uuid-1", "byoa-1")
    out = agent._decode_install_token(encoded)
    assert out["api"] == "https://example.com", out
    assert out["token"] == "tok-abc"
    assert out["agent_id"] == "uuid-1"
    assert out["agent_name"] == "byoa-1"
    print("[L25] PASS: T1 install token decode round-trip")


def t2_resolve_with_install_token():
    encoded = encode_bundle("https://api.example", "tok-xyz", "uuid-2", "byoa-2")
    keys_to_clear = [k for k in os.environ if k.startswith(("POLIS_", "LLM_"))]
    for k in keys_to_clear:
        os.environ.pop(k, None)
    os.environ["POLIS_INSTALL_TOKEN"] = encoded
    os.environ["LLM_BASE"] = "https://chat.aiprox.net/v1"
    os.environ["LLM_KEY"] = "sk-test"
    os.environ["LLM_MODEL"] = "gpt-4o-mini"
    cfg = agent._resolve_config()
    assert cfg["api"] == "https://api.example", cfg
    assert cfg["agent_id"] == "uuid-2"
    assert cfg["llm_model"] == "gpt-4o-mini"
    print("[L25] PASS: T2 resolve picks up install token + LLM env")


def t3_resolve_fallback():
    keys_to_clear = [k for k in os.environ if k.startswith(("POLIS_", "LLM_"))]
    for k in keys_to_clear:
        os.environ.pop(k, None)
    os.environ["POLIS_API_BASE"] = "https://manual.example"
    os.environ["POLIS_AGENT_TOKEN"] = "manual-tok"
    os.environ["POLIS_AGENT_ID"] = "manual-uuid"
    os.environ["POLIS_AGENT_NAME"] = "manual-name"
    os.environ["LLM_BASE"] = "https://manual-llm/v1"
    os.environ["LLM_KEY"] = "sk-manual"
    cfg = agent._resolve_config()
    assert cfg["api"] == "https://manual.example", cfg
    assert cfg["agent_name"] == "manual-name"
    assert cfg["llm_model"] == "gpt-4o-mini"  # default
    print("[L25] PASS: T3 resolve fallback to explicit env")


def t4_resolve_missing_field_exits():
    keys_to_clear = [k for k in os.environ if k.startswith(("POLIS_", "LLM_"))]
    for k in keys_to_clear:
        os.environ.pop(k, None)
    os.environ["POLIS_API_BASE"] = "https://x.example"
    # Missing token, agent_id, llm_base, llm_key.
    try:
        agent._resolve_config()
    except SystemExit as e:
        msg = str(e)
        # Claude 版本用 "缺少配置"，旧版本用 "缺少必要配置"
        assert ("缺少配置" in msg) or ("缺少必要配置" in msg), msg
        print("[L25] PASS: T4 missing fields → SystemExit with Chinese message")
        return
    raise AssertionError("expected SystemExit, got success")


def t5_humanize_llm_error():
    e401 = urllib.error.HTTPError("u", 401, "Unauthorized", {}, io.BytesIO(b"bad key"))
    msg401 = agent._humanize_llm_error(e401)
    # Claude: "LLM key 无效或已过期", 旧版: "LLM Key 不对"
    assert ("无效" in msg401 or "不对" in msg401), msg401

    e429 = urllib.error.HTTPError("u", 429, "Too Many", {}, io.BytesIO(b""))
    msg429 = agent._humanize_llm_error(e429)
    # Claude: "限流", 旧版: "太频繁"
    assert ("限流" in msg429 or "频繁" in msg429), msg429

    eurl = urllib.error.URLError("Name or service not known")
    msg_dns = agent._humanize_llm_error(eurl)
    assert ("DNS" in msg_dns or "解析" in msg_dns), msg_dns

    print("[L25] PASS: T5 humanize_llm_error returns Chinese for 401/429/DNS")


def t6_parse_sse():
    raw = b"event: heartbeat\ndata: {}\n\nevent: job.available\ndata: {\"id\":\"j-1\"}\n\n"
    stream = io.BytesIO(raw)
    events = list(agent._parse_sse(stream))
    assert len(events) == 2, events
    assert events[0][0] == "heartbeat"
    assert events[1][0] == "job.available"
    assert json.loads(events[1][1])["id"] == "j-1"
    print("[L25] PASS: T6 SSE parser handles event/data/blank")


def main():
    print("[L25] verify_byoa_agent_smoke")
    t1_decode_round_trip()
    t2_resolve_with_install_token()
    t3_resolve_fallback()
    t4_resolve_missing_field_exits()
    t5_humanize_llm_error()
    t6_parse_sse()
    print("[L25] ALL GREEN — agent.py smoke 6/6")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as e:
        print(f"[L25] FAIL: {e}")
        sys.exit(1)
