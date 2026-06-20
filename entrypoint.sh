#!/bin/sh
set -e

echo "[entrypoint] running alembic upgrade head..."
if alembic upgrade head; then
    echo "[entrypoint] alembic OK"
else
    echo "[entrypoint] WARNING: alembic failed — starting anyway, fix DATABASE_URL and redeploy"
fi

echo "[entrypoint] starting uvicorn on port ${PORT:-8000}"
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
