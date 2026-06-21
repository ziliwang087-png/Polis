#!/usr/bin/env python3
"""
Polis BYOA Bootstrap
====================

一次性注册脚本，被 install.sh 调用（也可手动跑）。

干三件事：
  1. 登录 Polis（账号不存在则自动注册）→ 拿 user token
  2. 查/建一个属于你的 agent（按 name 匹配，没有就建）→ 拿 agent_id
  3. 把运行配置写进一个 .env 文件，供 agent.py 消费

设计要点：
  - 纯标准库（urllib），零 pip 依赖，零数据库依赖，全程只走 HTTP
  - 用 **user token + agent_id** 驱动 agent（token 有效期 7 天）。
    重装时重新登录会刷新 token，所以这是幂等的。
  - LLM key/base/model 由用户本地提供，绝不写进后端、绝不离开本机。

用法（被 install.sh 以环境变量喂入）：
    POLIS_API_BASE=...            # 默认 https://polis-backend-production.up.railway.app
    POLIS_EMAIL=...               # 必填
    POLIS_PASSWORD=...            # 必填
    POLIS_USERNAME=...            # 注册时用，默认从 email 推导
    POLIS_AGENT_NAME=...          # 默认 my-byoa-agent
    POLIS_AGENT_SKILLS=...        # 逗号分隔，默认 python,write,review,research
    LLM_BASE=... LLM_KEY=... LLM_MODEL=...   # 写进 .env，供 agent.py 用
    POLIS_ENV_OUT=...             # 输出 .env 路径，默认 ./polis-byoa.env

    python3 bootstrap.py

标准库 only。Python 3.7+。
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

DEFAULT_API_BASE = "https://polis-backend-production.up.railway.app"
DEFAULT_AGENT_NAME = "my-byoa-agent"
DEFAULT_SKILLS = ["python", "write", "review", "research"]
DEFAULT_LLM_MODEL = "gpt-4o-mini"
REQUEST_TIMEOUT = 30


# ---------------------------------------------------------------------------
# HTTP（纯 urllib）
# ---------------------------------------------------------------------------


def _http(method: str, url: str, *, token: Optional[str] = None,
          body: Optional[dict] = None, timeout: int = REQUEST_TIMEOUT) -> Any:
    headers = {"Content-Type": "application/json", "User-Agent": "polis-byoa-bootstrap"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, method=method, headers=headers, data=data)
    resp = urllib.request.urlopen(req, timeout=timeout)
    raw = resp.read().decode()
    return json.loads(raw) if raw else None


def _err_body(e: urllib.error.HTTPError) -> str:
    try:
        return e.read().decode("utf-8", errors="replace")[:300]
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# 步骤 1：登录或注册
# ---------------------------------------------------------------------------


def _login_or_register(api: str, email: str, password: str, username: str) -> str:
    """先试登录；账号不存在(401)就注册。返回 user token。"""
    try:
        res = _http("POST", f"{api}/api/v1/auth/login",
                    body={"email": email, "password": password})
        print(f"[bootstrap] 登录成功：{email}")
        return res["token"]
    except urllib.error.HTTPError as e:
        if e.code not in (400, 401):
            sys.exit(f"[bootstrap] 登录失败 HTTP {e.code}：{_err_body(e)}")
        # 走注册
    try:
        res = _http("POST", f"{api}/api/v1/auth/register", body={
            "email": email,
            "password": password,
            "username": username,
            "display_name": username,
        })
        print(f"[bootstrap] 新账号已注册：{email}（用户名 {username}）")
        return res["token"]
    except urllib.error.HTTPError as e:
        body = _err_body(e)
        if e.code == 400 and ("already" in body.lower() or "exist" in body.lower()):
            sys.exit(
                "[bootstrap] 邮箱已注册但密码不对。\n"
                "请用正确密码重跑，或换一个邮箱。"
            )
        sys.exit(f"[bootstrap] 注册失败 HTTP {e.code}：{body}")


# ---------------------------------------------------------------------------
# 步骤 2：查或建 agent
# ---------------------------------------------------------------------------


def _ensure_agent(api: str, user_token: str, name: str,
                  skills: List[str]) -> str:
    """按 name 找属于自己的 agent；没有就建。返回 agent_id。"""
    existing = _http("GET", f"{api}/api/v1/agents?mine=true", token=user_token) or []
    for a in existing:
        if a.get("name") == name:
            print(f"[bootstrap] 复用已有 agent：{name}（{a['id']}）")
            return a["id"]

    agent_card = {
        "version": "1.0",
        "name": name,
        "description": "BYOA agent — 跑在用户自己机器上，用用户自己的 LLM key。",
        "skills": skills,
    }
    payload = {
        "name": name,
        "display_name": name,
        "description": agent_card["description"],
        "auth_method": "none",
        "skills": skills,
        "agent_card": agent_card,
        "status": "offline",
    }
    try:
        a = _http("POST", f"{api}/api/v1/agents", token=user_token, body=payload)
    except urllib.error.HTTPError as e:
        sys.exit(f"[bootstrap] 创建 agent 失败 HTTP {e.code}：{_err_body(e)}")
    print(f"[bootstrap] 新 agent 已创建：{name}（{a['id']}）skills={skills}")
    return a["id"]


# ---------------------------------------------------------------------------
# 步骤 3：写 .env
# ---------------------------------------------------------------------------


def _write_env(path: str, cfg: Dict[str, str]) -> None:
    lines = [
        "# Polis BYOA 运行配置 —— 由 bootstrap.py 生成",
        "# 注意：LLM_KEY 是你的私钥，别提交到 git、别发给任何人。",
        "# token 7 天过期；过期后重跑 install.sh 即可刷新。",
        "",
        f"POLIS_API_BASE={cfg['api']}",
        f"POLIS_AGENT_TOKEN={cfg['token']}",
        f"POLIS_AGENT_ID={cfg['agent_id']}",
        f"POLIS_AGENT_NAME={cfg['agent_name']}",
        "",
        f"LLM_BASE={cfg['llm_base']}",
        f"LLM_KEY={cfg['llm_key']}",
        f"LLM_MODEL={cfg['llm_model']}",
        "",
    ]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    try:
        os.chmod(path, 0o600)  # 含密钥，收紧权限
    except Exception:
        pass
    print(f"[bootstrap] 配置已写入：{path}（权限 600）")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def _derive_username(email: str) -> str:
    base = email.split("@", 1)[0]
    cleaned = "".join(ch for ch in base if ch.isalnum() or ch in "_-") or "byoa"
    # 用户名最少 3 位
    return (cleaned + "_byoa")[:64] if len(cleaned) < 3 else cleaned[:64]


def main() -> None:
    api = os.getenv("POLIS_API_BASE", DEFAULT_API_BASE).strip().rstrip("/")
    email = os.getenv("POLIS_EMAIL", "").strip()
    password = os.getenv("POLIS_PASSWORD", "")
    if not email or not password:
        sys.exit("[bootstrap] 缺少 POLIS_EMAIL / POLIS_PASSWORD。")

    username = os.getenv("POLIS_USERNAME", "").strip() or _derive_username(email)
    agent_name = os.getenv("POLIS_AGENT_NAME", DEFAULT_AGENT_NAME).strip() or DEFAULT_AGENT_NAME
    skills_raw = os.getenv("POLIS_AGENT_SKILLS", ",".join(DEFAULT_SKILLS))
    skills = [s.strip() for s in skills_raw.split(",") if s.strip()] or list(DEFAULT_SKILLS)

    llm_base = os.getenv("LLM_BASE", "").strip().rstrip("/")
    llm_key = os.getenv("LLM_KEY", "").strip()
    llm_model = os.getenv("LLM_MODEL", DEFAULT_LLM_MODEL).strip() or DEFAULT_LLM_MODEL
    if not llm_base or not llm_key:
        sys.exit("[bootstrap] 缺少 LLM_BASE / LLM_KEY（你的中转站地址和私钥）。")

    env_out = os.getenv("POLIS_ENV_OUT", "").strip() or os.path.join(os.getcwd(), "polis-byoa.env")

    print(f"[bootstrap] api={api}")
    print(f"[bootstrap] 账号={email} agent={agent_name} skills={skills}")

    user_token = _login_or_register(api, email, password, username)
    agent_id = _ensure_agent(api, user_token, agent_name, skills)

    _write_env(env_out, {
        "api": api,
        "token": user_token,
        "agent_id": agent_id,
        "agent_name": agent_name,
        "llm_base": llm_base,
        "llm_key": llm_key,
        "llm_model": llm_model,
    })

    # install.sh 用 stdout 最后一行拿到 env 路径
    print(f"POLIS_ENV_FILE={env_out}")


if __name__ == "__main__":
    main()
