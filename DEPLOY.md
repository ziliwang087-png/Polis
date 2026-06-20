# Polis Deploy Guide

## Backend → Railway

**Files**: `Dockerfile`, `railway.json`, `entrypoint.sh` (repo root)

**Steps** (Railway dashboard or CLI):
1. New Project → Deploy from GitHub → pick `Polis` repo, branch `main`
2. Railway auto-detects Dockerfile in repo root
3. Add env vars (Variables tab):
   - `DATABASE_URL` — Supabase pooler URL (port 6543, transaction mode)
   - `JWT_SECRET_KEY` — `openssl rand -hex 32`
   - `PUBLIC_BASE_URL` — your Railway public URL (set after first deploy)
   - `CORS_ORIGINS` — comma-separated, e.g. `https://polis.vercel.app,http://localhost:3000`
   - `SUPABASE_URL` (optional, for storage)
   - `SUPABASE_SERVICE_ROLE_KEY` (optional, for storage)
4. Settings → Networking → Generate Domain. Copy the URL.
5. Update `PUBLIC_BASE_URL` env var to that URL → redeploy.
6. Verify: `curl https://<your-url>/health` → `{"status":"healthy"}`

**alembic on startup**: `entrypoint.sh` runs `alembic upgrade head`. Failures
are warnings, not fatal — the API still serves so `/health` returns 200 and
you can debug from logs.

## Frontend → Vercel

**No vercel.json needed.** Configure via dashboard:

1. New Project → Import `Polis` repo
2. **Root Directory: `frontend`** (critical — monorepo)
3. Framework Preset: Next.js (auto-detected)
4. Env vars (Settings → Environment Variables):
   - `NEXT_PUBLIC_API_URL` = `https://<railway-backend-url>/api/v1`
5. Deploy.

## Order matters

1. Deploy backend first → get Railway URL
2. Deploy frontend with `NEXT_PUBLIC_API_URL` pointing at Railway
3. Add Vercel domain to backend's `CORS_ORIGINS` env var → redeploy backend
