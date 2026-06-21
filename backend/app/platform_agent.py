"""
Polis 内置平台 Agent
=====================

启动时自登记一个由平台托管的 agent（slug=polis-platform-py），订阅自己的 inbox，
收到任务后调 OpenAI 兼容 LLM endpoint，把回答作为 artifact 交付。

环境变量（全部可选，缺任一就跳过启动，不影响 web 服务）：
    POLIS_PLATFORM_AGENT_ENABLED   "1" 才启用
    POLIS_PLATFORM_AGENT_USER_EMAIL 平台 owner 账号邮箱
    POLIS_PLATFORM_AGENT_USER_PASSWORD
    POLIS_PLATFORM_AGENT_LLM_BASE  OpenAI 兼容 base URL，例如 https://chat.aiprox.net/v1
    POLIS_PLATFORM_AGENT_LLM_KEY   API key
    POLIS_PLATFORM_AGENT_LLM_MODEL 默认 gpt-4o-mini
    POLIS_PLATFORM_AGENT_SKILLS    逗号分隔，默认 "python,write,review,research"
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

from psycopg2.extras import Json

from app.database import get_db_connection
from app import worker_heartbeat

logger = logging.getLogger("polis.platform_agent")

DEFAULT_SKILLS = ["python", "write", "review", "research"]
DEFAULT_PLATFORM_PROMPT = """你是 Polis 任务网络上的一个 AI agent。
用户发任务给你，你按要求干活，直接返回结果。

规则：
- 直接返回最终结果，不要寒暄、不要"好的我来"、不要解释你怎么做的
- 任务要代码就只返回代码块（用 ``` 包），任务要翻译就只返回译文
- 看不懂任务就说"任务描述不清晰，请补充：……"
- 任务跟你能力无关（比如要你订机票），返回"这个任务超出 agent 能力范围"
"""
TRANSLATOR_PROMPT = """你是 Polis 任务网络上的专业翻译 agent。
只处理翻译任务，把用户给出的文本翻译成目标语言。

规则：
- 只输出译文，不要解释、不要寒暄、不要加标题
- 如果目标语言没说清楚，默认翻译成英文
- 保留数字、专有名词和技术术语的准确含义
- 不要输出原文，除非原文中的专有名词本来就该保留
"""

REQUEST_TIMEOUT = 60
INBOX_TIMEOUT = 600
RECONNECT_DELAY = 3
MAX_DESC_CHARS = 8000


def _http(method, url, *, token=None, body=None, stream=False, timeout=REQUEST_TIMEOUT):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, method=method, headers=headers, data=data)
    resp = urllib.request.urlopen(req, timeout=timeout)
    if stream:
        return resp
    raw = resp.read().decode()
    return json.loads(raw) if raw else None


def _login_or_register(api, email, password, username):
    try:
        return _http("POST", f"{api}/api/v1/auth/login",
                     body={"email": email, "password": password})["token"]
    except urllib.error.HTTPError as e:
        if e.code != 401:
            raise
    return _http("POST", f"{api}/api/v1/auth/register", body={
        "email": email, "password": password, "username": username,
        "display_name": "Polis Platform"
    })["token"]


def _builtin_agents() -> List[Dict[str, Any]]:
    platform_skills_raw = os.getenv("POLIS_PLATFORM_AGENT_SKILLS", ",".join(DEFAULT_SKILLS))
    platform_skills = [s.strip() for s in platform_skills_raw.split(",") if s.strip()]
    return [
        {
            "name": os.getenv("POLIS_PLATFORM_AGENT_NAME", "polis-platform-py"),
            "display_name": "Polis 官方 AI Agent",
            "description": "平台内置 agent，可写代码 / 改文 / review。任务发到这就行，几秒回。",
            "skills": platform_skills,
            "system_prompt": DEFAULT_PLATFORM_PROMPT,
        },
        {
            "name": "polis-platform-translator",
            "display_name": "Polis 官方翻译 Agent",
            "description": "平台内置翻译 agent，专门处理 translate 技能任务。",
            "skills": ["translate"],
            "system_prompt": TRANSLATOR_PROMPT,
        },
    ]


def _sync_agent_record(agent_id: str, spec: Dict[str, Any]):
    skills = spec["skills"]
    agent_card = {
        "version": "1.0",
        "name": spec["name"],
        "description": spec["description"],
        "skills": skills,
    }
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE agents
            SET display_name = %s,
                description = %s,
                agent_card = %s,
                status = 'online',
                updated_at = NOW()
            WHERE id = %s
            """,
            (spec["display_name"], spec["description"], Json(agent_card), agent_id),
        )
        cur.execute(
            "DELETE FROM agent_skills WHERE agent_id = %s AND NOT (skill_id = ANY(%s::text[]))",
            (agent_id, skills),
        )
        for skill in skills:
            cur.execute(
                """
                INSERT INTO agent_skills (
                    agent_id, skill_id, name, description, examples,
                    input_schema, output_schema
                )
                VALUES (%s, %s, %s, NULL, NULL, NULL, NULL)
                ON CONFLICT (agent_id, skill_id) DO UPDATE SET
                    name = EXCLUDED.name,
                    description = EXCLUDED.description,
                    examples = EXCLUDED.examples,
                    input_schema = EXCLUDED.input_schema,
                    output_schema = EXCLUDED.output_schema
                """,
                (agent_id, skill, skill),
            )


def _ensure_agent(api, user_token, spec):
    existing = _http("GET", f"{api}/api/v1/agents?mine=true", token=user_token) or []
    for a in existing:
        if a["name"] == spec["name"]:
            _sync_agent_record(a["id"], spec)
            return a["id"]
    payload = {
        "name": spec["name"],
        "display_name": spec["display_name"],
        "description": spec["description"],
        "auth_method": "none",
        "skills": spec["skills"],
        "agent_card": {
            "version": "1.0",
            "name": spec["name"],
            "description": spec["description"],
            "skills": spec["skills"],
        },
        "status": "online",
    }
    a = _http("POST", f"{api}/api/v1/agents", token=user_token, body=payload)
    _sync_agent_record(a["id"], spec)
    return a["id"]


def _heartbeat(api, agent_id, token):
    try:
        _http("POST", f"{api}/api/v1/agents/{agent_id}/heartbeat",
              token=token, body={"status": "online"})
    except Exception as e:
        logger.warning("heartbeat failed: %s", e)


def _call_llm(base_url, api_key, model, system_prompt, user_text):
    url = base_url.rstrip("/") + "/chat/completions"
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text[:MAX_DESC_CHARS]},
        ],
        "temperature": 0.4,
    }
    req = urllib.request.Request(url, method="POST", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json",
                                          "Authorization": f"Bearer {api_key}"})
    resp = urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT)
    data = json.loads(resp.read())
    return data["choices"][0]["message"]["content"]


def _parse_sse(stream):
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


def _work_one(api, agent_id, token, agent_spec, job, llm_cfg):
    job_id = job["id"]
    title = job.get("title") or "(untitled)"
    skill = job.get("required_skill")
    desc = job.get("description") or ""
    logger.info("[platform-agent] claim job=%s skill=%s title=%s", job_id, skill, title[:60])

    try:
        _http("POST", f"{api}/api/v1/jobs/{job_id}/claim",
              token=token, body={"agent_id": agent_id})
    except urllib.error.HTTPError as e:
        if e.code in (409, 410):
            logger.info("[platform-agent] job=%s already claimed/closed (%s), skip", job_id, e.code)
            return
        raise

    try:
        _http("POST", f"{api}/api/v1/jobs/{job_id}/progress",
              token=token, body={"agent_id": agent_id, "progress": "thinking..."})
    except Exception:
        pass

    try:
        prompt = f"任务标题：{title}\n必需技能：{skill}\n\n任务描述：\n{desc}"
        result = _call_llm(
            llm_cfg["base"],
            llm_cfg["key"],
            llm_cfg["model"],
            agent_spec["system_prompt"],
            prompt,
        )
    except Exception as e:
        logger.exception("[platform-agent] LLM call failed: %s", e)
        result = f"[platform-agent] 调用 LLM 失败：{type(e).__name__}: {e}"

    _http("POST", f"{api}/api/v1/jobs/{job_id}/artifacts",
          token=token, body={
              "agent_id": agent_id,
              "type": "text",
              "content": result,
              "metadata": {"by": agent_spec["name"], "model": llm_cfg["model"]},
          })
    logger.info("[platform-agent] delivered job=%s len=%s", job_id, len(result))


def _worker_loop(api, agent_id, token, agent_spec, llm_cfg):
    name = agent_spec["name"]
    worker_heartbeat.register(name, agent_id=agent_id)
    while True:
        try:
            stream = _http("GET", f"{api}/api/v1/agents/{agent_id}/inbox",
                           token=token, stream=True, timeout=INBOX_TIMEOUT)
            worker_heartbeat.beat_connected(name)
            logger.info("[platform-agent] inbox connected name=%s", name)
            for event, payload in _parse_sse(stream):
                if event != "job.available":
                    continue
                try:
                    job = json.loads(payload)
                    worker_heartbeat.beat_job_received(name, job_id=str(job.get("id", "")))
                    _work_one(api, agent_id, token, agent_spec, job, llm_cfg)
                    worker_heartbeat.beat_job_done(name)
                except Exception as e:
                    worker_heartbeat.beat_error(name, repr(e))
                    logger.exception("[platform-agent] work failed: %s", e)
        except Exception as e:
            worker_heartbeat.beat_disconnected(name, error=repr(e))
            logger.warning(
                "[platform-agent] inbox dropped name=%s: %s -- reconnect in %ds",
                name,
                e,
                RECONNECT_DELAY,
            )
            time.sleep(RECONNECT_DELAY)


def maybe_start_platform_agent():
    if os.getenv("POLIS_PLATFORM_AGENT_ENABLED") != "1":
        logger.info("[platform-agent] disabled (POLIS_PLATFORM_AGENT_ENABLED != 1)")
        return

    email = os.getenv("POLIS_PLATFORM_AGENT_USER_EMAIL")
    password = os.getenv("POLIS_PLATFORM_AGENT_USER_PASSWORD")
    llm_base = os.getenv("POLIS_PLATFORM_AGENT_LLM_BASE")
    llm_key = os.getenv("POLIS_PLATFORM_AGENT_LLM_KEY")
    llm_model = os.getenv("POLIS_PLATFORM_AGENT_LLM_MODEL", "gpt-4o-mini")
    missing = [k for k, v in {
        "POLIS_PLATFORM_AGENT_USER_EMAIL": email,
        "POLIS_PLATFORM_AGENT_USER_PASSWORD": password,
        "POLIS_PLATFORM_AGENT_LLM_BASE": llm_base,
        "POLIS_PLATFORM_AGENT_LLM_KEY": llm_key,
    }.items() if not v]
    if missing:
        logger.warning("[platform-agent] missing env: %s -- not starting", missing)
        return

    api = os.getenv("PUBLIC_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    username = os.getenv("POLIS_PLATFORM_AGENT_USERNAME", "polis_platform")
    llm_cfg = {"base": llm_base, "key": llm_key, "model": llm_model}
    agent_specs = _builtin_agents()

    def _bootstrap():
        time.sleep(3)
        try:
            user_token = _login_or_register(api, email, password, username)
            for spec in agent_specs:
                agent_id = _ensure_agent(api, user_token, spec)
                _heartbeat(api, agent_id, user_token)
                logger.info(
                    "[platform-agent] live name=%s agent_id=%s skills=%s model=%s",
                    spec["name"],
                    agent_id,
                    spec["skills"],
                    llm_model,
                )
                threading.Thread(
                    target=_worker_loop,
                    args=(api, agent_id, user_token, spec, llm_cfg),
                    name=f"polis-platform-agent-{spec['name']}",
                    daemon=True,
                ).start()
        except Exception as e:
            logger.exception("[platform-agent] bootstrap failed, giving up: %s", e)

    t = threading.Thread(target=_bootstrap, name="polis-platform-agent", daemon=True)
    t.start()
