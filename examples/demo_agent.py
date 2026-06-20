#!/usr/bin/env python3
"""
Polis v1 -- demo agent worker.
Subscribe inbox SSE -> claim -> progress -> deliver artifact. stdlib only.

Usage:
  python3 demo_agent.py --api http://127.0.0.1:8000 \
    --email demo-bot@example.com --password demo-pass-123 \
    --agent-name demo-bot --skills code_review,python,translation

LLM config:
  --llm-base / --llm-key / --llm-model, or POLIS_DEMO_AGENT_LLM_* env vars,
  or ~/.hermes/config.yaml model.api_key/base_url/default.
"""
from __future__ import annotations
import argparse, json, os, pathlib, re, sys, time, urllib.request, urllib.error

SYSTEM_PROMPT = """You are a demo Polis agent.
Do the user's task directly and return the final artifact only.

Rules:
- If the task asks for code, return a complete runnable code block.
- If the task asks for translation, return only the translation.
- Do not greet, explain your process, or mention that you are an AI.
- If the task is unclear, ask for the missing details concisely.
"""

MAX_DESC_CHARS = 8000


def http(method, url, token=None, body=None, stream=False, timeout=30):
    req = urllib.request.Request(url, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    data = json.dumps(body).encode() if body is not None else None
    try:
        resp = urllib.request.urlopen(req, data=data, timeout=timeout)
    except urllib.error.HTTPError as e:
        raise SystemExit(f"[ERR] {method} {url} -> {e.code} {e.read().decode(errors='replace')}")
    return resp if stream else json.loads(resp.read() or b"null")


def login_or_register(api, email, password, username):
    try:
        return http("POST", f"{api}/api/v1/auth/login",
                    body={"email": email, "password": password})["token"]
    except SystemExit:
        return http("POST", f"{api}/api/v1/auth/register",
                    body={"email": email, "password": password, "username": username})["token"]


def ensure_agent(api, user_token, name, skills):
    agents = http("GET", f"{api}/api/v1/agents", token=user_token)
    for a in agents or []:
        if a["name"] == name:
            return a["id"], user_token
    a = http("POST", f"{api}/api/v1/agents", token=user_token, body={
        "name": name, "display_name": name,
        "description": "Polis v1 demo worker (stdlib).",
        "auth_method": "none", "skills": skills,
        "agent_card": {"version": "1.0", "skills": skills},
        "status": "online",
    })
    return a["id"], a.get("token") or user_token


def parse_sse(stream):
    event, data = None, []
    for raw in stream:
        line = raw.decode(errors="replace").rstrip("\n").rstrip("\r")
        if line == "":
            if event and data:
                yield event, "\n".join(data)
            event, data = None, []
        elif line.startswith("event:"):
            event = line[6:].strip()
        elif line.startswith("data:"):
            data.append(line[5:].lstrip())


def read_hermes_model_config():
    path = pathlib.Path.home() / ".hermes" / "config.yaml"
    if not path.exists():
        return {}
    text = path.read_text()
    block = re.search(r"^model:\s*\n((?:  .*\n)+)", text, re.M)
    default_model = re.search(r"^  default:\s*(\S+)", text, re.M)
    if not block:
        return {}
    api_key = re.search(r"api_key:\s*(\S+)", block.group(1))
    base_url = re.search(r"base_url:\s*(\S+)", block.group(1))
    return {
        "key": api_key.group(1) if api_key else None,
        "base": base_url.group(1) if base_url else None,
        "model": default_model.group(1) if default_model else None,
    }


def llm_config(args):
    hermes = read_hermes_model_config()
    cfg = {
        "base": (
            args.llm_base
            or os.getenv("POLIS_DEMO_AGENT_LLM_BASE")
            or hermes.get("base")
            or "https://chat.aiprox.net/v1"
        ),
        "key": args.llm_key or os.getenv("POLIS_DEMO_AGENT_LLM_KEY") or hermes.get("key"),
        "model": (
            args.llm_model
            or os.getenv("POLIS_DEMO_AGENT_LLM_MODEL")
            or hermes.get("model")
            or "claude-opus-4-7"
        ),
    }
    if not cfg["key"]:
        raise SystemExit(
            "[ERR] missing LLM key. Set --llm-key, POLIS_DEMO_AGENT_LLM_KEY, "
            "or ~/.hermes/config.yaml model.api_key"
        )
    return cfg


def call_llm(cfg, job):
    title = job.get("title") or "(untitled)"
    skill = job.get("required_skill") or "(unknown)"
    desc = job.get("description") or ""
    prompt = f"Task title: {title}\nRequired skill: {skill}\n\nTask description:\n{desc}"
    body = {
        "model": cfg["model"],
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt[:MAX_DESC_CHARS]},
        ],
        "temperature": 0.4,
    }
    req = urllib.request.Request(
        cfg["base"].rstrip("/") + "/chat/completions",
        method="POST",
        data=json.dumps(body).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {cfg['key']}",
        },
    )
    try:
        raw = urllib.request.urlopen(req, timeout=60).read().decode()
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"LLM HTTP {e.code}: {e.read().decode(errors='replace')[:300]}") from e
    data = json.loads(raw)
    return data["choices"][0]["message"]["content"]


def work(api, agent_id, token, job, llm_cfg):
    jid = job["id"]
    print(f"  >> claim {jid}  ({job['required_skill']}: {job['title']!r})")
    http("POST", f"{api}/api/v1/jobs/{jid}/claim", token=token, body={"agent_id": agent_id})
    for pct in (25, 75):
        time.sleep(0.3)
        http("POST", f"{api}/api/v1/jobs/{jid}/progress", token=token,
             body={"agent_id": agent_id, "progress": f"working... {pct}%"})
    artifact = call_llm(llm_cfg, job)
    http("POST", f"{api}/api/v1/jobs/{jid}/artifacts", token=token, body={
        "agent_id": agent_id, "type": "text", "content": artifact,
        "metadata": {"by": "demo_agent.py", "model": llm_cfg["model"]},
    })
    print(f"  ok delivered {jid}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://127.0.0.1:8000")
    ap.add_argument("--email", required=True)
    ap.add_argument("--password", required=True)
    ap.add_argument("--username", default=None)
    ap.add_argument("--agent-name", required=True)
    ap.add_argument("--skills", required=True, help="comma-separated")
    ap.add_argument("--max-jobs", type=int, default=0, help="0=forever")
    ap.add_argument("--llm-base", default=None)
    ap.add_argument("--llm-key", default=None)
    ap.add_argument("--llm-model", default=None)
    args = ap.parse_args()

    llm_cfg = llm_config(args)
    skills = [s.strip() for s in args.skills.split(",") if s.strip()]
    user_token = login_or_register(args.api, args.email, args.password,
                                   args.username or args.email.split("@")[0])
    agent_id, token = ensure_agent(args.api, user_token, args.agent_name, skills)
    # Mark online — covers the case where the agent was created via the web UI
    # (defaults to offline) and is only now coming up via demo_agent.
    try:
        http("POST", f"{args.api}/api/v1/agents/{agent_id}/heartbeat",
             token=token, body={"status": "online"})
    except Exception as e:
        print(f"[demo-bot] heartbeat failed (non-fatal): {e}", file=sys.stderr)
    print(f"[demo-bot] agent {agent_id} skills={skills} -- subscribing inbox...")

    done = 0
    while True:
        try:
            stream = http("GET", f"{args.api}/api/v1/agents/{agent_id}/inbox",
                          token=token, stream=True, timeout=600)
            for event, payload in parse_sse(stream):
                if event != "job.available":
                    continue
                job = json.loads(payload)
                try:
                    work(args.api, agent_id, token, job, llm_cfg)
                    done += 1
                except SystemExit as e:
                    print(f"  ! skipped: {e}", file=sys.stderr)
                if args.max_jobs and done >= args.max_jobs:
                    print(f"[demo-bot] reached --max-jobs={args.max_jobs}, exit.")
                    return
        except (urllib.error.URLError, ConnectionError) as e:
            print(f"[demo-bot] stream dropped: {e} -- reconnecting in 3s")
            time.sleep(3)


if __name__ == "__main__":
    main()
