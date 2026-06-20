#!/bin/bash
export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"
PID="/tmp/polis-loop-backend.pid"
if [ -f "$PID" ]; then
    OLD=$(cat "$PID" 2>/dev/null || true)
    if [ -n "$OLD" ]; then
        kill "$OLD" 2>/dev/null || true
        sleep 1
        kill -9 "$OLD" 2>/dev/null || true
    fi
    rm -f "$PID"
fi
EXISTING=$(lsof -t -i :8765 2>/dev/null || true)
for p in $EXISTING; do kill -9 "$p" 2>/dev/null || true; done
echo "[stop] backend stopped"
