#!/usr/bin/env python3
"""
Polis BYOA Agent (Bring Your Own Agent)
========================================

Single-file Python agent that runs on a user's machine, connects to Polis,
and processes jobs using the user's own LLM provider (BYOK).

Usage:
    POLIS_INSTALL_TOKEN=<base64> \
    LLM_BASE=<openai-compatible-url> \
    LLM_KEY=<api-key> \
    LLM_MODEL=<model-name> \
    python3 agent.py

Or with explicit override:
    POLIS_API_BASE=https://polis-backend-production.up.railway.app \
    POLIS_AGENT_TOKEN=<jwt> \
    POLIS_AGENT_ID=<uuid> \
    POLIS_AGENT_NAME=<name> \
    LLM_BASE=... LLM_KEY=... python3 agent.py

Standard library only. Python 3.7+.
"""
from __future__ import annotations

import base64
import json
import logging
import os
import signal
import sys
import threading
import time
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VERSION = "0.1.0"
DEFAULT_API_BASE = "https://polis-backend-production.up.railway.app"
DEFAULT_LLM_MODEL = "gpt-4o-mini"
REQUEST_TIMEOUT = 60
INBOX_TIMEOUT = 600
RECONNECT_DELAY = 3
MAX_DESC_CHARS = 8000

DEFAULT_SYSTEM_PROMPT = """你是 Polis 任务网络上的一个 AI agent。
用户发任务给你，你按要求干活，直接返回结果。

规则：
- 直接返回最终结果，不要寒暄、不要"好的我来"、不要解释你怎么做的
- 任务要代码就只返回代码块（用 ``` 包），任务要翻译就只返回译文
- 看不懂任务就说"任务描述不清晰，请补充：……"
- 任务跟你能力无关（比如要你订机票），返回"这个任务超出 agent 能力范围"
"""

logger = logging.getLogger("polis.byoa")

# ---------------------------------------------------------------------------
# Install token
# ---------------------------------------------------------------------------


def _decode_install_token(install_token: str) -> Dict[str, str]:
    """Decode an install token produced by /api/v1/agents/{id}/install-token.

    Token format: base64url-encoded JSON with keys:
      - api: backend base URL
      - token: JWT access token (Bearer)
      - agent_id: UUID
      - agent_name: human-readable name
      - system_prompt: optional override
    """
    pad = "=" * (-len(install_token) % 4)
    raw = base64.urlsafe_b64decode(install_token + pad)
    payload = json.loads(raw.decode("utf-8"))
    required = ("api", "token", "agent_id", "agent_name")
    missing = [k for k in required if not payload.get(k)]
    if missing:
        raise ValueError(f"install_token missing keys: {missing}")
    return payload


def _resolve_config() -> Dict[str, str]:
    """Resolve runtime config from env, preferring POLIS_INSTALL_TOKEN.

    Falls back to explicit env (POLIS_API_BASE/POLIS_AGENT_TOKEN/...) so
    advanced users can plug in without going through the install flow.
    """
    cfg: Dict[str, str] = {}
    install_token = os.getenv("POLIS_INSTALL_TOKEN", "").strip()
    if install_token:
        try:
            cfg.update(_decode_install_token(install_token))
        except Exception as e:
            sys.exit(
                "[polis] POLIS_INSTALL_TOKEN 解码失败：%s\n"
                "请到 polis.app/agents 重新生成安装命令。" % e
            )

    cfg.setdefault("api", os.getenv("POLIS_API_BASE", DEFAULT_API_BASE))
    cfg.setdefault("token", os.getenv("POLIS_AGENT_TOKEN", ""))
    cfg.setdefault("agent_id", os.getenv("POLIS_AGENT_ID", ""))
    cfg.setdefault("agent_name", os.getenv("POLIS_AGENT_NAME", "polis-byoa-agent"))
    cfg.setdefault("system_prompt", os.getenv("POLIS_SYSTEM_PROMPT", DEFAULT_SYSTEM_PROMPT))

    cfg["llm_base"] = os.getenv("LLM_BASE", "").strip().rstrip("/")
    cfg["llm_key"] = os.getenv("LLM_KEY", "").strip()
    cfg["llm_model"] = os.getenv("LLM_MODEL", DEFAULT_LLM_MODEL).strip()

    missing = [k for k in ("api", "token", "agent_id", "llm_base", "llm_key") if not cfg.get(k)]
    if missing:
        sys.exit(
            "[polis] 缺少必要配置：%s\n"
            "请检查环境变量 POLIS_INSTALL_TOKEN / LLM_BASE / LLM_KEY。" % missing
        )
    cfg["api"] = cfg["api"].rstrip("/")
    return cfg


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------


def _http(method, url, *, token=None, body=None, stream=False, timeout=REQUEST_TIMEOUT):
    headers = {"Content-Type": "application/json", "User-Agent": f"polis-byoa/{VERSION}"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, method=method, headers=headers, data=data)
    resp = urllib.request.urlopen(req, timeout=timeout)
    if stream:
        return resp
    raw = resp.read().decode()
    return json.loads(raw) if raw else None


def _parse_sse(stream):
    """Parse Server-Sent Events from a urllib response stream."""
    event, data_lines = None, []
    for raw in stream:
        line = raw.decode(errors="replace").rstrip("\n").rstrip("\r")
        if line == "":
            if event and data_lines:
                yield event, "\n".join(data_lines)
            event, data_lines = None, []
        elif line.startswith("event:"):
            event = line[6:].strip()
        elif line.startswith("data:"):
            data_lines.append(line[5:].lstrip())


# ---------------------------------------------------------------------------
# LLM call (OpenAI-compatible)
# ---------------------------------------------------------------------------


def _call_llm(base_url: str, api_key: str, model: str, system_prompt: str, user_text: str) -> str:
    url = base_url.rstrip("/") + "/chat/completions"
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text[:MAX_DESC_CHARS]},
        ],
        "temperature": 0.4,
    }
    req = urllib.request.Request(
        url,
        method="POST",
        data=json.dumps(body).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "User-Agent": f"polis-byoa/{VERSION}",
        },
    )
    resp = urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT)
    data = json.loads(resp.read())
    return data["choices"][0]["message"]["content"]


def _humanize_llm_error(err: Exception) -> str:
    """Translate raw LLM errors into human-friendly Chinese."""
    if isinstance(err, urllib.error.HTTPError):
        code = err.code
        body_snippet = ""
        try:
            body_snippet = err.read().decode("utf-8", errors="replace")[:200]
        except Exception:
            pass
        table = {
            401: "你的 LLM Key 不对，去中转站重新复制一下。",
            403: "LLM 中转站拒绝了请求（403），可能 key 没权限或被封。",
            404: "LLM 端点找不到（404），检查 LLM_BASE 是否正确。",
            429: "中转站说你太频繁了（429），等 1 分钟再来。",
            500: "中转站内部错误（500），稍后重试。",
            502: "中转站网关错误（502），可能上游故障。",
            503: "中转站不可用（503），稍后重试。",
        }
        msg = table.get(code, f"中转站返回 HTTP {code}。")
        if body_snippet:
            msg += f"\n中转站原文：{body_snippet}"
        return msg
    if isinstance(err, urllib.error.URLError):
        reason = str(err.reason)
        if "ssl" in reason.lower():
            return "SSL 证书校验失败，检查中转站 URL 是否正确（是否 https）。"
        if "name or service not known" in reason.lower() or "nodename" in reason.lower():
            return "DNS 解析失败，LLM_BASE 域名打不开，检查拼写或换一家中转。"
        if "refused" in reason.lower():
            return "连不上中转站（连接被拒），可能服务挂了或地址不对。"
        if "timed out" in reason.lower():
            return "连接中转站超时，检查网络或换一家。"
        return f"网络错误：{reason}"
    return f"调用 LLM 失败：{type(err).__name__}: {err}"


# ---------------------------------------------------------------------------
# Job lifecycle
# ---------------------------------------------------------------------------


def _work_one(api: str, agent_id: str, token: str, agent_name: str,
              system_prompt: str, llm_cfg: Dict[str, str], job: Dict[str, Any]) -> bool:
    """Claim, work, deliver. Returns True on real artifact delivery,
    False when claim was skipped (already claimed by another agent).
    """
    job_id = job["id"]
    title = job.get("title") or "(untitled)"
    skill = job.get("required_skill")
    desc = job.get("description") or ""
    logger.info("[polis] claim job=%s skill=%s title=%s", job_id, skill, title[:60])

    try:
        _http("POST", f"{api}/api/v1/jobs/{job_id}/claim",
              token=token, body={"agent_id": agent_id})
    except urllib.error.HTTPError as e:
        if e.code in (409, 410):
            logger.info("[polis] job=%s already claimed/closed (%s), skip", job_id, e.code)
            return False
        raise

    try:
        _http("POST", f"{api}/api/v1/jobs/{job_id}/progress",
              token=token, body={"agent_id": agent_id, "progress": "thinking..."})
    except Exception:
        pass

    try:
        prompt = f"任务标题：{title}\n必需技能：{skill}\n\n任务描述：\n{desc}"
        result = _call_llm(
            llm_cfg["llm_base"], llm_cfg["llm_key"], llm_cfg["llm_model"],
            system_prompt, prompt,
        )
    except Exception as e:
        msg = _humanize_llm_error(e)
        logger.error("[polis] LLM call failed: %s", msg)
        result = f"[polis-byoa] 调用 LLM 失败：{msg}"

    _http("POST", f"{api}/api/v1/jobs/{job_id}/artifacts",
          token=token, body={
              "agent_id": agent_id, "type": "text", "content": result,
              "metadata": {"by": agent_name, "model": llm_cfg["llm_model"], "byoa_version": VERSION},
          })
    logger.info("[polis] delivered job=%s len=%s", job_id, len(result))
    return True


def _heartbeat(api: str, agent_id: str, token: str):
    try:
        _http("POST", f"{api}/api/v1/agents/{agent_id}/heartbeat",
              token=token, body={"status": "online"})
    except Exception as e:
        logger.warning("[polis] heartbeat failed: %s", e)


def _heartbeat_loop(api: str, agent_id: str, token: str, stop_event: threading.Event):
    """Send heartbeat every 30s so the dashboard shows online status."""
    while not stop_event.is_set():
        _heartbeat(api, agent_id, token)
        stop_event.wait(30)


def _worker_loop(cfg: Dict[str, str], stop_event: threading.Event):
    api = cfg["api"]
    agent_id = cfg["agent_id"]
    token = cfg["token"]
    agent_name = cfg["agent_name"]
    system_prompt = cfg["system_prompt"]
    llm_cfg = {"llm_base": cfg["llm_base"], "llm_key": cfg["llm_key"], "llm_model": cfg["llm_model"]}

    while not stop_event.is_set():
        try:
            stream = _http("GET", f"{api}/api/v1/agents/{agent_id}/inbox",
                           token=token, stream=True, timeout=INBOX_TIMEOUT)
            logger.info("[polis] inbox connected name=%s", agent_name)
            for event, payload in _parse_sse(stream):
                if stop_event.is_set():
                    break
                if event == "heartbeat":
                    continue
                if event != "job.available":
                    continue
                try:
                    job = json.loads(payload)
                    _work_one(api, agent_id, token, agent_name, system_prompt, llm_cfg, job)
                except Exception as e:
                    logger.exception("[polis] work failed: %s", e)
        except urllib.error.HTTPError as e:
            if e.code == 401:
                logger.error("[polis] 鉴权失败（401），install token 失效或被吊销。"
                             "请到 polis.app/agents 重新生成安装命令。")
                stop_event.set()
                return
            logger.warning("[polis] inbox dropped (HTTP %s) -- reconnect in %ds",
                           e.code, RECONNECT_DELAY)
        except Exception as e:
            logger.warning("[polis] inbox dropped: %s -- reconnect in %ds", e, RECONNECT_DELAY)
        if stop_event.is_set():
            break
        time.sleep(RECONNECT_DELAY)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main():
    logging.basicConfig(
        level=os.getenv("POLIS_LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(message)s",
    )
    cfg = _resolve_config()

    print(f"[polis] BYOA agent v{VERSION}")
    print(f"[polis] api={cfg['api']}")
    print(f"[polis] agent={cfg['agent_name']} ({cfg['agent_id']})")
    print(f"[polis] llm={cfg['llm_base']} model={cfg['llm_model']}")
    print(f"[polis] LLM key 永远不会发送到 polis 后端，只用于直接调中转站")

    stop_event = threading.Event()

    def _on_signal(signum, frame):
        logger.info("[polis] received signal %s, stopping...", signum)
        stop_event.set()

    signal.signal(signal.SIGINT, _on_signal)
    signal.signal(signal.SIGTERM, _on_signal)

    # Initial heartbeat to show online quickly.
    _heartbeat(cfg["api"], cfg["agent_id"], cfg["token"])

    hb_thread = threading.Thread(
        target=_heartbeat_loop,
        args=(cfg["api"], cfg["agent_id"], cfg["token"], stop_event),
        name="polis-heartbeat",
        daemon=True,
    )
    hb_thread.start()

    try:
        _worker_loop(cfg, stop_event)
    except KeyboardInterrupt:
        stop_event.set()

    print("[polis] agent 已下线")


if __name__ == "__main__":
    main()
