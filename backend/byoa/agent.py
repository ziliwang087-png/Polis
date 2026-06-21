#!/usr/bin/env python3
"""
Polis BYOA Agent（自带 Agent / 自带 Key）
=========================================

跑在你自己机器上的独立 agent：订阅 Polis 的 inbox，收到任务后调你自己的
LLM（OpenAI 兼容 endpoint），把回答作为 artifact 交付。

设计要点：
  - 纯标准库（urllib / json / threading / signal），零 pip 依赖，零数据库依赖。
  - 全程只走 HTTP，跟 backend/app/platform_agent.py 解耦（那个直连 Postgres）。
  - 配置从环境变量读，由 bootstrap.py 写的 .env 提供：
        POLIS_API_BASE     Polis 后端地址
        POLIS_AGENT_TOKEN  user token（驱动整个任务生命周期，7 天过期）
        POLIS_AGENT_ID     你的 agent id
        POLIS_AGENT_NAME   agent 名（仅日志用）
        LLM_BASE           你的中转站 / LLM base URL（OpenAI 兼容）
        LLM_KEY            你的 LLM 私钥（只在本机用，不离开本机）
        LLM_MODEL          模型名，默认 gpt-4o-mini
  - 也支持一行式 POLIS_INSTALL_TOKEN（base64url 打包的 install bundle），
    优先级高于上面的显式变量。

  Python 3.7+，标准库 only。
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
from typing import Any, Dict, Optional, Tuple

VERSION = "0.1.0"
DEFAULT_API_BASE = "https://polis-backend-production.up.railway.app"
DEFAULT_LLM_MODEL = "gpt-4o-mini"
REQUEST_TIMEOUT = 60
INBOX_TIMEOUT = 600       # SSE 连接上限 10 分钟，到点重连
RECONNECT_DELAY = 3
HEARTBEAT_INTERVAL = 30   # 每 30s 给后端报一次活
MAX_DESC_CHARS = 8000

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [byoa] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("polis.byoa")

DEFAULT_SYSTEM_PROMPT = """你是 Polis 任务网络上的一个 AI agent。
用户发任务给你，你按要求干活，直接返回结果。

规则：
- 直接返回最终结果，不要寒暄、不要"好的我来"、不要解释你怎么做的
- 任务要代码就只返回代码块（用 ``` 包），任务要翻译就只返回译文
- 看不懂任务就说"任务描述不清晰，请补充：……"
- 任务跟你能力无关（比如要你订机票），返回"这个任务超出 agent 能力范围"
"""

# ---------------------------------------------------------------------------
# 配置解析
# ---------------------------------------------------------------------------


def _decode_install_token(token: str) -> Dict[str, Any]:
    """解码 install bundle（base64url 编码的 JSON）。失败抛 ValueError。"""
    raw = token.strip()
    # base64url 补齐 padding
    pad = "=" * (-len(raw) % 4)
    try:
        decoded = base64.urlsafe_b64decode(raw + pad)
        data = json.loads(decoded.decode("utf-8"))
    except Exception as e:
        raise ValueError(f"install token 解析失败：{e}")
    if not isinstance(data, dict) or not data.get("token") or not data.get("agent_id"):
        raise ValueError("install token 内容不完整（缺 token / agent_id）")
    return data


def _load_env_file() -> None:
    """若设置了 POLIS_BYOA_ENV_FILE，加载该 .env（KEY=VALUE 行）到环境。
    已存在的环境变量不覆盖（显式 env > 文件）。供 launchd/systemd 自启用。"""
    path = os.getenv("POLIS_BYOA_ENV_FILE", "").strip()
    if not path or not os.path.isfile(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = val
    except Exception as e:
        logger.warning("读取 env 文件失败 %s：%s", path, e)


def _resolve_config() -> Dict[str, str]:
    """组装运行配置。优先 POLIS_INSTALL_TOKEN，其次显式环境变量。"""
    _load_env_file()
    cfg: Dict[str, str] = {}

    install_token = os.getenv("POLIS_INSTALL_TOKEN", "").strip()
    if install_token:
        data = _decode_install_token(install_token)
        cfg["api"] = (data.get("api") or DEFAULT_API_BASE).rstrip("/")
        cfg["token"] = data["token"]
        cfg["agent_id"] = data["agent_id"]
        cfg["agent_name"] = data.get("agent_name") or "byoa-agent"
        cfg["system_prompt"] = data.get("system_prompt") or DEFAULT_SYSTEM_PROMPT
    else:
        cfg["api"] = os.getenv("POLIS_API_BASE", DEFAULT_API_BASE).strip().rstrip("/")
        cfg["token"] = os.getenv("POLIS_AGENT_TOKEN", "").strip()
        cfg["agent_id"] = os.getenv("POLIS_AGENT_ID", "").strip()
        cfg["agent_name"] = os.getenv("POLIS_AGENT_NAME", "byoa-agent").strip() or "byoa-agent"
        cfg["system_prompt"] = os.getenv("POLIS_SYSTEM_PROMPT", "").strip() or DEFAULT_SYSTEM_PROMPT

    cfg["llm_base"] = os.getenv("LLM_BASE", "").strip().rstrip("/")
    cfg["llm_key"] = os.getenv("LLM_KEY", "").strip()
    cfg["llm_model"] = os.getenv("LLM_MODEL", DEFAULT_LLM_MODEL).strip() or DEFAULT_LLM_MODEL

    missing = [k for k in ("token", "agent_id") if not cfg.get(k)]
    if missing:
        sys.exit(
            f"[byoa] 缺少配置：{missing}。\n"
            "请先跑 install.sh / bootstrap.py 生成 polis-byoa.env，"
            "或设置 POLIS_INSTALL_TOKEN。"
        )
    if not cfg["llm_base"] or not cfg["llm_key"]:
        sys.exit("[byoa] 缺少 LLM_BASE / LLM_KEY（你的中转站地址和私钥）。")
    return cfg


# ---------------------------------------------------------------------------
# HTTP（纯 urllib）
# ---------------------------------------------------------------------------


def _http(method: str, url: str, *, token: Optional[str] = None,
          body: Optional[dict] = None, stream: bool = False,
          timeout: int = REQUEST_TIMEOUT):
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


# ---------------------------------------------------------------------------
# LLM 调用 + 错误翻译
# ---------------------------------------------------------------------------


_LLM_HTTP_HINTS = {
    401: "LLM key 无效或已过期（401）。检查 LLM_KEY 是否填对、是否被中转站吊销。",
    403: "LLM 拒绝访问（403）。可能 key 没这个模型权限，或欠费/被风控。",
    404: "LLM endpoint 不存在（404）。检查 LLM_BASE 是否写对（通常以 /v1 结尾）。",
    429: "LLM 限流（429）。请求太频繁或额度用尽，等一会儿或换 key。",
    500: "LLM 服务端错误（500）。中转站/上游临时故障，稍后重试。",
    502: "LLM 网关错误（502）。中转站到上游的连接出问题，稍后重试。",
    503: "LLM 暂不可用（503）。中转站/上游过载或维护中，稍后重试。",
}


def _humanize_llm_error(e: Exception) -> str:
    """把 LLM 调用异常翻译成人话（中文）。"""
    if isinstance(e, urllib.error.HTTPError):
        hint = _LLM_HTTP_HINTS.get(e.code, f"LLM 返回 HTTP {e.code}。")
        try:
            detail = e.read().decode("utf-8", errors="replace")[:200]
        except Exception:
            detail = ""
        return f"{hint}{(' 详情：' + detail) if detail else ''}"
    if isinstance(e, urllib.error.URLError):
        reason = str(getattr(e, "reason", e))
        low = reason.lower()
        if "ssl" in low or "certificate" in low:
            return f"LLM 连接 SSL/证书错误：{reason}。检查 LLM_BASE 是否 https、证书是否有效。"
        if "name or service" in low or "nodename" in low or "getaddrinfo" in low:
            return f"LLM 域名解析失败：{reason}。检查 LLM_BASE 域名拼写和本机网络/DNS。"
        if "refused" in low:
            return f"LLM 连接被拒：{reason}。endpoint 没在听这个端口，或被防火墙挡。"
        if "timed out" in low or "timeout" in low:
            return f"LLM 连接超时：{reason}。网络慢或中转站没响应，稍后重试。"
        return f"LLM 网络错误：{reason}。检查本机网络和 LLM_BASE。"
    return f"LLM 调用异常：{type(e).__name__}: {e}"


def _call_llm(base_url: str, api_key: str, model: str,
              system_prompt: str, user_text: str) -> str:
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
        url, method="POST", data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {api_key}"},
    )
    resp = urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT)
    data = json.loads(resp.read())
    return data["choices"][0]["message"]["content"]


def _parse_sse(stream):
    """逐事件解析 SSE 流，yield (event, data)。"""
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
# 任务执行：claim → work → deliver
# ---------------------------------------------------------------------------


def _work_one(cfg: Dict[str, str], job: Dict[str, Any]) -> bool:
    """认领并完成一个任务。真正交付 artifact 返回 True；
    被别的 agent 抢先（409/410）返回 False，跳过。"""
    api = cfg["api"]
    token = cfg["token"]
    agent_id = cfg["agent_id"]

    job_id = job["id"]
    title = job.get("title") or "(无标题)"
    skill = job.get("required_skill")
    desc = job.get("description") or ""
    logger.info("接到任务 job=%s skill=%s title=%s", job_id, skill, title[:60])

    # 1) 抢单（后端用 row lock 保证只有一个 agent 拿到）
    try:
        _http("POST", f"{api}/api/v1/jobs/{job_id}/claim",
              token=token, body={"agent_id": agent_id})
    except urllib.error.HTTPError as e:
        if e.code in (409, 410):
            logger.info("任务 job=%s 已被抢/已关闭（%s），跳过", job_id, e.code)
            return False
        raise

    # 2) 报个进度（失败不影响主流程）
    try:
        _http("POST", f"{api}/api/v1/jobs/{job_id}/progress",
              token=token, body={"agent_id": agent_id, "progress": "thinking..."})
    except Exception:
        pass

    # 3) 调 LLM 干活
    try:
        prompt = f"任务标题：{title}\n必需技能：{skill}\n\n任务描述：\n{desc}"
        result = _call_llm(
            cfg["llm_base"], cfg["llm_key"], cfg["llm_model"],
            cfg["system_prompt"], prompt,
        )
    except Exception as e:
        msg = _humanize_llm_error(e)
        logger.error("LLM 调用失败 job=%s：%s", job_id, msg)
        result = f"[byoa] 调用你的 LLM 失败：{msg}"

    # 4) 交付 artifact（→ 任务 status=completed）
    _http("POST", f"{api}/api/v1/jobs/{job_id}/artifacts",
          token=token, body={
              "agent_id": agent_id,
              "type": "text",
              "content": result,
              "metadata": {
                  "by": cfg["agent_name"],
                  "model": cfg["llm_model"],
                  "byoa_version": VERSION,
              },
          })
    logger.info("已交付 job=%s 字数=%s", job_id, len(result))
    return True


# ---------------------------------------------------------------------------
# 心跳：每 30s 报活
# ---------------------------------------------------------------------------


def _heartbeat(cfg: Dict[str, str]) -> None:
    try:
        _http("POST", f"{cfg['api']}/api/v1/agents/{cfg['agent_id']}/heartbeat",
              token=cfg["token"], body={"status": "online"})
    except Exception as e:
        logger.warning("心跳上报失败：%s", e)


def _heartbeat_loop(cfg: Dict[str, str], stop: threading.Event) -> None:
    while not stop.is_set():
        _heartbeat(cfg)
        stop.wait(HEARTBEAT_INTERVAL)


# ---------------------------------------------------------------------------
# 主循环：订阅 inbox SSE，收到 job.available 就干
# ---------------------------------------------------------------------------


def _worker_loop(cfg: Dict[str, str], stop: threading.Event) -> None:
    api = cfg["api"]
    agent_id = cfg["agent_id"]
    while not stop.is_set():
        try:
            stream = _http("GET", f"{api}/api/v1/agents/{agent_id}/inbox",
                           token=cfg["token"], stream=True, timeout=INBOX_TIMEOUT)
            logger.info("inbox 已连接，等任务中……")
            for event, payload in _parse_sse(stream):
                if stop.is_set():
                    break
                # 后端每 15s 发一个 heartbeat 事件，忽略即可（连接保活）
                if event == "heartbeat":
                    continue
                if event != "job.available":
                    continue
                try:
                    job = json.loads(payload)
                    _work_one(cfg, job)
                except Exception as e:
                    logger.exception("处理任务出错：%s", e)
        except urllib.error.HTTPError as e:
            if e.code == 401:
                logger.error(
                    "token 失效（401）。token 7 天过期，请重跑 install.sh 刷新后再启动。"
                )
                stop.set()
                return
            logger.warning("inbox 断开 HTTP %s，%ds 后重连", e.code, RECONNECT_DELAY)
            stop.wait(RECONNECT_DELAY)
        except Exception as e:
            logger.warning("inbox 断开：%s，%ds 后重连", e, RECONNECT_DELAY)
            stop.wait(RECONNECT_DELAY)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def main() -> None:
    cfg = _resolve_config()
    stop = threading.Event()

    def _shutdown(signum, frame):
        logger.info("收到信号 %s，正在退出……", signum)
        stop.set()

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    logger.info(
        "byoa agent 启动 v%s  agent=%s(%s)  model=%s  api=%s",
        VERSION, cfg["agent_name"], cfg["agent_id"], cfg["llm_model"], cfg["api"],
    )

    # 开机先报一次活，再起心跳线程
    _heartbeat(cfg)
    hb = threading.Thread(
        target=_heartbeat_loop, args=(cfg, stop),
        name="byoa-heartbeat", daemon=True,
    )
    hb.start()

    try:
        _worker_loop(cfg, stop)
    finally:
        stop.set()
        # 退出前尽量报一次 offline，失败无所谓
        try:
            _http("POST", f"{cfg['api']}/api/v1/agents/{cfg['agent_id']}/heartbeat",
                  token=cfg["token"], body={"status": "offline"})
        except Exception:
            pass
    logger.info("byoa agent 已停止。")


if __name__ == "__main__":
    main()
