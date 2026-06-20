#!/bin/bash
# Restart the local Polis backend with platform-agent env, wait for /health.
set -e
export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

PORT="${PORT:-8765}"
ROOT="/Users/a1111/Desktop/ai-society/backend"
LOG="/tmp/polis-loop-backend.log"
PID="/tmp/polis-loop-backend.pid"

# 1. kill previous
if [ -f "$PID" ]; then
    OLD=$(cat "$PID" 2>/dev/null || true)
    if [ -n "$OLD" ] && ps -p "$OLD" > /dev/null 2>&1; then
        kill "$OLD" 2>/dev/null || true
        sleep 1
        kill -9 "$OLD" 2>/dev/null || true
    fi
    rm -f "$PID"
fi
EXISTING=$(lsof -t -i ":$PORT" 2>/dev/null || true)
for p in $EXISTING; do kill -9 "$p" 2>/dev/null || true; done

# 2. read LLM key from hermes config
LLM_KEY=$(python3 - <<'PY'
import re, pathlib
t = (pathlib.Path.home() / ".hermes" / "config.yaml").read_text()
m = re.search(r"^model:\s*\n((?:  .*\n)+)", t, re.M)
print(re.search(r"api_key:\s*(\S+)", m.group(1)).group(1))
PY
)
if [ -z "$LLM_KEY" ]; then
    echo "[start] FATAL: cannot read LLM key from ~/.hermes/config.yaml" >&2
    exit 2
fi

LLM_BASE=$(python3 - <<'PY'
import re, pathlib
t = (pathlib.Path.home() / ".hermes" / "config.yaml").read_text()
m = re.search(r"^model:\s*\n((?:  .*\n)+)", t, re.M)
mb = re.search(r"base_url:\s*(\S+)", m.group(1))
print(mb.group(1) if mb else "")
PY
)
LLM_MODEL=$(python3 - <<'PY'
import re, pathlib
t = (pathlib.Path.home() / ".hermes" / "config.yaml").read_text()
mm = re.search(r"^  default:\s*(\S+)", t, re.M)
print(mm.group(1) if mm else "claude-opus-4-7")
PY
)
LLM_BASE="${LLM_BASE:-https://chat.aiprox.net/v1}"
LLM_MODEL="${LLM_MODEL:-claude-opus-4-7}"

cd "$ROOT"

if [ -f "$ROOT/scripts/loop/.env.loop" ]; then
    set -a
    . "$ROOT/scripts/loop/.env.loop"
    set +a
fi

: "${POLIS_PLATFORM_AGENT_USER_EMAIL:=polis-platform-bot@polisapp.com}"
if [ -z "${POLIS_PLATFORM_AGENT_USER_PASSWORD:-}" ]; then
    echo "[start] FATAL: POLIS_PLATFORM_AGENT_USER_PASSWORD missing; put it in scripts/loop/.env.loop" >&2
    exit 2
fi

echo "[start] launching uvicorn on :$PORT  model=$LLM_MODEL  base=$LLM_BASE"
POLIS_PLATFORM_AGENT_ENABLED=1 \
POLIS_PLATFORM_AGENT_USER_EMAIL="$POLIS_PLATFORM_AGENT_USER_EMAIL" \
POLIS_PLATFORM_AGENT_USER_PASSWORD="$POLIS_PLATFORM_AGENT_USER_PASSWORD" \
POLIS_PLATFORM_AGENT_LLM_BASE="$LLM_BASE" \
POLIS_PLATFORM_AGENT_LLM_KEY="$LLM_KEY" \
POLIS_PLATFORM_AGENT_LLM_MODEL="$LLM_MODEL" \
PUBLIC_BASE_URL="http://127.0.0.1:$PORT" \
nohup ./venv/bin/uvicorn app.main:app --host 127.0.0.1 --port "$PORT" --log-level info \
    > "$LOG" 2>&1 &

echo $! > "$PID"
echo "[start] pid=$(cat $PID) log=$LOG"

for i in $(seq 1 30); do
    if curl -sf "http://127.0.0.1:$PORT/health" > /dev/null 2>&1; then
        echo "[start] backend ready after ${i}s"
        sleep 4
        exit 0
    fi
    sleep 1
done

echo "[start] FATAL: backend did not become healthy in 30s. tail log:" >&2
tail -n 30 "$LOG" >&2 || true
exit 2
