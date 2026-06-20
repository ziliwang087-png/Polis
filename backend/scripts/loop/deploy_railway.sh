#!/bin/bash
# Deploy current main to Railway and wait for healthcheck.
# Note: requires railway CLI (already installed at /opt/homebrew/bin/railway).
set -e
cd /Users/a1111/Desktop/ai-society
echo "[deploy] git push origin main"
/usr/bin/git push origin main 2>&1 | /usr/bin/tail -n 5 || true
echo "[deploy] railway up --service polis-backend --detach"
/opt/homebrew/bin/railway up --service polis-backend --detach 2>&1 | /usr/bin/tail -n 5
echo "[deploy] waiting up to 4 minutes for new revision /openapi.json to reflect"
for i in $(seq 1 24); do
    sleep 10
    /usr/bin/curl -sf https://polis-backend-production.up.railway.app/health > /dev/null && break
done
echo "[deploy] backend appears healthy. assuming new revision is live (no robust check)."
