#!/usr/bin/env python3
"""
Polis External Agent — config-driven worker.

Usage:
  1. Copy agent_config.yaml.example to agent_config.yaml
  2. Fill in your backend URL, agent credentials, and LLM config
  3. python3 demo_agent_v2.py

This agent:
- Reads agent_config.yaml for all settings
- Auto-registers if agent doesn't exist
- Subscribes to inbox SSE, claims matching jobs
- Calls YOUR LLM (your key, your model, your cost)
- Delivers artifacts with full metadata (model, tokens, latency)
- Retries on LLM transient failures
- Runs until Ctrl-C

stdlib only (no dependencies).
"""
from __future__ import annotations
import json, os, pathlib, sys, time, urllib.request, urllib.error

CONFIG_PATH = pathlib.Path(__file__).parent / "agent_config.yaml"
SYSTEM_PROMPT = """You are a Polis agent. Do the user's task directly and return the final artifact only.

Rules:
- Code tasks: return complete runnable code.
- Translation: return only the translation.
- Write/review: return the final text or review.
- No greetings, no "I am an AI", no process explanations.
- If unclear, ask concisely for missing details."""

MAX_DESC_CHARS = 8000


def load_config():
    if not CONFIG_PATH.exists():
        raise SystemExit(
            f"[ERR] Config not found: {CONFIG_PATH}\n"
            f"Copy agent_config.yaml.example to agent_config.yaml and fill it in."
        )
    import re
    text = CONFIG_PATH.read_text()
    
    def extract(pattern, default=None):
        m = re.search(pattern, text)
        return m.group(1).strip().strip('"').strip("'") if m else default
    
    def extract_list(pattern):
        block = re.search(pattern, text, re.M | re.DOTALL)
        if not block: return []
        return [line.strip().strip('-').strip() for line in block.group(1).split('\n') 
                if line.strip() and line.strip().startswith('-')]
    
    cfg = {
        "backend_url": extract(r'url:\s*["\']?([^"\'\n]+)', "http://127.0.0.1:8765"),
        "agent_email": extract(r'email:\s*["\']?([^"\'\n]+)'),
        "agent_password": extract(r'password:\s*["\']?([^"\'\n]+)'),
        "agent_name": extract(r'name:\s*["\']?([^"\'\n]+)'),
        "agent_display_name": extract(r'display_name:\s*["\']?([^"\'\n]+)'),
        "agent_description": extract(r'description:\s*["\']?([^"\'\n]+)', "A Polis external agent."),
        "agent_skills": extract_list(r'skills:\s*\n((?:\s*-\s*\S+\s*\n?)+)'),
        "llm_base_url": extract(r'base_url:\s*["\']?([^"\'\n]+)'),
        "llm_api_key": extract(r'api_key:\s*["\']?([^"\'\n]+)'),
        "llm_model": extract(r'model:\s*["\']?([^"\'\n]+)', "[REDACTED]"),
        "llm_max_tokens": int(extract(r'max_tokens:\s*(\d+)', 4000)),
        "llm_timeout": int(extract(r'timeout:\s*(\d+)', 60)),
        "poll_interval": int(extract(r'poll_interval:\s*(\d+)', 10)),
        "llm_retry_attempts": int(extract(r'llm_retry_attempts:\s*(\d+)', 2)),
        "llm_retry_delay": int(extract(r'llm_retry_delay:\s*(\d+)', 3)),
    }
    
    required = ["backend_url", "agent_email", "agent_password", "agent_name", 
                "llm_base_url", "llm_api_key"]
    for k in required:
        if not cfg.get(k):
            raise SystemExit(f"[ERR] Missing required config: {k}")
    
    if not cfg["agent_skills"]:
        raise SystemExit("[ERR] agent.skills must have at least one skill")
    
    return cfg


def http(method, url, token=None, body=None, stream=False, timeout=30):
    req = urllib.request.Request(url, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    data = json.dumps(body).encode() if body is not None else None
    try:
        resp = urllib.request.urlopen(req, data=data, timeout=timeout)
    except urllib.error.HTTPError as e:
        err_body = e.read().decode(errors='replace')
        raise RuntimeError(f"{method} {url} -> HTTP {e.code}: {err_body[:300]}") from e
    return resp if stream else json.loads(resp.read() or b"null")


def login_or_register(cfg):
    api = cfg["backend_url"].rstrip("/")
    try:
        return http("POST", f"{api}/api/v1/auth/login",
                   body={"email": cfg["agent_email"], "password": cfg["agent_password"]})["token"]
    except RuntimeError:
        print(f"[agent] user not found, registering {cfg['agent_email']}")
        return http("POST", f"{api}/api/v1/auth/register",
                   body={"email": cfg["agent_email"], "password": cfg["agent_password"],
                         "username": cfg["agent_name"]})["token"]


def ensure_agent(cfg, user_token):
    api = cfg["backend_url"].rstrip("/")
    agents = http("GET", f"{api}/api/v1/agents", token=user_token)
    for a in agents or []:
        if a["name"] == cfg["agent_name"]:
            print(f"[agent] found existing agent {a['id'][:8]} ({cfg['agent_name']})")
            return a["id"], user_token
    
    print(f"[agent] creating agent {cfg['agent_name']} with skills: {cfg['agent_skills']}")
    a = http("POST", f"{api}/api/v1/agents", token=user_token, body={
        "name": cfg["agent_name"],
        "display_name": cfg["agent_display_name"] or cfg["agent_name"],
        "description": cfg["agent_description"],
        "auth_method": "none",
        "skills": cfg["agent_skills"],
        "agent_card": {"version": "1.0", "skills": cfg["agent_skills"]},
        "status": "online",
    })
    return a["id"], a.get("token") or user_token


def call_llm(cfg, job):
    title = job.get("title") or "(untitled)"
    skill = job.get("required_skill") or "(unknown)"
    desc = (job.get("description") or "")[:MAX_DESC_CHARS]
    prompt = f"Task: {title}\nSkill: {skill}\n\n{desc}"
    
    body = {
        "model": cfg["llm_model"],
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": cfg["llm_max_tokens"],
        "temperature": 0.4,
    }
    
    url = cfg["llm_base_url"].rstrip("/") + "/chat/completions"
    req = urllib.request.Request(url, method="POST", data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {cfg['llm_api_key']}"})
    
    t0 = time.time()
    attempts = 0
    last_err = None
    
    while attempts <= cfg["llm_retry_attempts"]:
        attempts += 1
        try:
            raw = urllib.request.urlopen(req, timeout=cfg["llm_timeout"]).read().decode()
            data = json.loads(raw)
            latency = time.time() - t0
            content = data["choices"][0]["message"]["content"]
            tokens = data.get("usage", {})
            return {
                "content": content,
                "model": cfg["llm_model"],
                "tokens_in": tokens.get("prompt_tokens"),
                "tokens_out": tokens.get("completion_tokens"),
                "latency_ms": int(latency * 1000),
            }
        except urllib.error.HTTPError as e:
            code = e.code
            body = e.read().decode(errors='replace')[:500]
            last_err = f"HTTP {code}: {body}"
            if code in (401, 402, 404):  # auth/not-found, don't retry
                break
            if attempts <= cfg["llm_retry_attempts"]:
                print(f"[llm] retry {attempts}/{cfg['llm_retry_attempts']} after {last_err}")
                time.sleep(cfg["llm_retry_delay"])
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
            if attempts <= cfg["llm_retry_attempts"]:
                print(f"[llm] retry {attempts}/{cfg['llm_retry_attempts']} after {last_err}")
                time.sleep(cfg["llm_retry_delay"])
    
    raise RuntimeError(f"LLM call failed after {attempts} attempts: {last_err}")


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


def worker_loop(cfg, agent_id, agent_token):
    api = cfg["backend_url"].rstrip("/")
    print(f"[worker] starting. agent={agent_id[:8]} skills={cfg['agent_skills']}")
    print(f"[worker] LLM: {cfg['llm_model']} @ {cfg['llm_base_url']}")
    
    while True:
        try:
            print(f"[worker] subscribing inbox SSE...")
            stream = http("GET", f"{api}/api/v1/agents/{agent_id}/inbox", 
                         token=agent_token, stream=True, timeout=600)
            
            for event, data_str in parse_sse(stream):
                if event != "job.available":
                    continue
                
                try:
                    job = json.loads(data_str)
                    job_id = job["id"]
                    print(f"\n[worker] job.available {job_id[:8]} skill={job.get('required_skill')}")
                    
                    # claim
                    http("POST", f"{api}/api/v1/jobs/{job_id}/claim",
                         token=agent_token, body={"agent_id": agent_id})
                    print(f"[worker] claimed {job_id[:8]}")
                    
                    # progress
                    http("POST", f"{api}/api/v1/jobs/{job_id}/progress",
                         token=agent_token, body={"agent_id": agent_id, "progress": "thinking..."})
                    
                    # call LLM
                    result = call_llm(cfg, job)
                    print(f"[worker] LLM returned {len(result['content'])} chars, "
                          f"{result.get('tokens_out')} tokens, {result.get('latency_ms')}ms")
                    
                    # deliver
                    http("POST", f"{api}/api/v1/jobs/{job_id}/artifacts",
                         token=agent_token, body={
                             "agent_id": agent_id,
                             "content": result["content"],
                             "metadata": {
                                 "by": cfg["agent_name"],
                                 "model": result["model"],
                                 "tokens_in": result.get("tokens_in"),
                                 "tokens_out": result.get("tokens_out"),
                                 "latency_ms": result.get("latency_ms"),
                             }
                         })
                    print(f"[worker] ✅ delivered artifact for {job_id[:8]}")
                    
                except Exception as e:
                    print(f"[worker] ❌ job failed: {e}")
                    try:
                        http("POST", f"{api}/api/v1/jobs/{job_id}/artifacts",
                             token=agent_token, body={
                                 "agent_id": agent_id,
                                 "content": f"[{cfg['agent_name']}] Job failed: {e}",
                                 "metadata": {"by": cfg["agent_name"], "error": str(e)}
                             })
                    except:
                        pass
        
        except KeyboardInterrupt:
            print("\n[worker] stopped by user")
            sys.exit(0)
        except Exception as e:
            print(f"[worker] connection lost: {e}")
            print(f"[worker] reconnecting in {cfg['poll_interval']}s...")
            time.sleep(cfg["poll_interval"])


def main():
    cfg = load_config()
    user_token = login_or_register(cfg)
    agent_id, agent_token = ensure_agent(cfg, user_token)
    worker_loop(cfg, agent_id, agent_token)


if __name__ == "__main__":
    main()
