"""
Polis Backend API
Main application entry point
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
import time

from app.config import settings
from app.database import get_db_connection
from app.routes import auth, agents, jobs, admin

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown for background workers.

    Runs both hooks; either failing must not stop the web service.
    """
    log = logging.getLogger("polis")

    # Platform agent (sync init returning quickly; spawns its own threads).
    try:
        from app.platform_agent import maybe_start_platform_agent
        maybe_start_platform_agent()
    except Exception:
        log.exception("platform-agent startup hook crashed")

    # Stale-claim reaper (asyncio Task on running loop).
    try:
        from app.stale_claim_reaper import maybe_start_reaper
        maybe_start_reaper()
    except Exception:
        log.exception("stale-claim-reaper startup hook crashed")

    yield
    # No teardown for now; daemon threads + asyncio loop teardown is fine.


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    description="A2A-compatible task network for Chinese-speaking AI engineers",
    lifespan=lifespan,
)


# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix=settings.API_V1_PREFIX)
app.include_router(agents.router, prefix=settings.API_V1_PREFIX)
app.include_router(jobs.router, prefix=settings.API_V1_PREFIX)
app.include_router(admin.router, prefix=settings.API_V1_PREFIX)

@app.get("/")
def root():
    """Health check endpoint"""
    return {
        "service": "Polis API",
        "version": "1.0.0",
        "status": "running"
    }

@app.get("/health")
def health():
    """Health check endpoint"""
    return {"status": "healthy"}


@app.get("/health/deep")
async def health_deep():
    """Deep health: db ping + reaper state.

    Status semantics:
      ok      — db reachable, reaper enabled+running with recent tick
      degraded — anything off (db slow, reaper not ticking, etc.)
      unhealthy — db unreachable
    """
    def _db_ping():
        t0 = time.perf_counter()
        try:
            with get_db_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT 1")
                cur.fetchone()
            return True, round((time.perf_counter() - t0) * 1000, 1), None
        except Exception as exc:
            return False, None, repr(exc)[:300]

    import asyncio
    db_ok, db_latency_ms, db_error = await asyncio.to_thread(_db_ping)

    try:
        from app.stale_claim_reaper import get_state as _reaper_state
        reaper = _reaper_state()
    except Exception as exc:
        reaper = {"error": repr(exc)[:300]}

    try:
        from app.worker_heartbeat import aggregate as _worker_agg
        workers = _worker_agg()
    except Exception as exc:
        workers = {"error": repr(exc)[:300]}

    if not db_ok:
        status = "unhealthy"
    else:
        # tick fresh? allow up to 3x tick before degraded.
        try:
            tick_threshold = int(reaper.get("tick_secs") or 60) * 3
        except (TypeError, ValueError):
            tick_threshold = 180
        secs_raw = reaper.get("seconds_since_last_tick")
        try:
            secs_val = int(secs_raw) if secs_raw is not None else None
        except (TypeError, ValueError):
            secs_val = None
        reaper_fresh = (
            reaper.get("enabled") is False  # disabled is fine
            or (
                reaper.get("running")
                and (secs_val is None or secs_val <= tick_threshold)
            )
        )
        # If platform-agent workers are registered, factor their health in.
        # No registrations (POLIS_PLATFORM_AGENT_ENABLED != 1) -> ignore.
        if isinstance(workers, dict) and workers.get("any_registered"):
            workers_fresh = bool(workers.get("all_fresh"))
        else:
            workers_fresh = True
        status = "ok" if (reaper_fresh and workers_fresh) else "degraded"

    return {
        "status": status,
        "version": "1.0.0",
        "db": {"ok": db_ok, "latency_ms": db_latency_ms, "error": db_error},
        "reaper": reaper,
        "workers": workers,
    }


@app.get("/.well-known/agent.json", tags=["a2a"])
def agent_card():
    """Polis meta-agent card for A2A discovery."""
    api_url = f"{settings.PUBLIC_BASE_URL.rstrip('/')}{settings.API_V1_PREFIX}"
    fallback_skills = [
        {
            "id": "polis.jobs.create",
            "name": "Create Polis job",
            "description": "Create an A2A task/job with messages and optional Supabase-backed attachments.",
            "inputModes": ["application/json"],
            "outputModes": ["application/json"],
        },
        {
            "id": "polis.jobs.claim",
            "name": "Claim Polis job",
            "description": "Claim submitted jobs with PostgreSQL row-lock concurrency protection.",
            "inputModes": ["application/json"],
            "outputModes": ["application/json"],
        },
        {
            "id": "polis.jobs.deliver",
            "name": "Deliver Polis artifact",
            "description": "Submit A2A artifacts and stream job events back to clients.",
            "inputModes": ["application/json"],
            "outputModes": ["application/json", "text/event-stream"],
        },
    ]
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT
                    s.skill_id,
                    COALESCE(MAX(NULLIF(s.name, '')), s.skill_id) AS name,
                    COUNT(DISTINCT s.agent_id) AS agent_count,
                    COUNT(DISTINCT s.agent_id) FILTER (
                        WHERE a.status IN ('online', 'busy')
                    ) AS online_agent_count
                FROM agent_skills s
                JOIN agents a ON a.id = s.agent_id
                GROUP BY s.skill_id
                HAVING COUNT(DISTINCT s.agent_id) FILTER (
                    WHERE a.status IN ('online', 'busy')
                ) > 0
                ORDER BY online_agent_count DESC, agent_count DESC, s.skill_id ASC
                LIMIT 50
                """
            )
            dynamic_skills = [
                {
                    "id": row["skill_id"],
                    "name": row["name"] or row["skill_id"],
                    "description": (
                        f"Available from {row['online_agent_count']} online Polis agent(s) "
                        f"and {row['agent_count']} registered agent(s)."
                    ),
                    "inputModes": ["text/plain", "application/json"],
                    "outputModes": ["text/plain", "application/json"],
                }
                for row in cur.fetchall()
            ]
    except Exception:
        logging.getLogger("polis").exception("failed to load dynamic agent-card skills")
        dynamic_skills = []

    return {
        "name": "Polis",
        "description": "Polis is an A2A-compatible job network for registering agents, broadcasting tasks, claiming work, and returning artifacts.",
        "url": api_url,
        "version": "1.0.0",
        "protocolVersion": "0.2.5",
        "capabilities": {
            "streaming": True,
            "pushNotifications": False,
        },
        "defaultInputModes": ["text/plain", "application/json"],
        "defaultOutputModes": ["text/plain", "application/json"],
        # Always include the platform's meta-skills (jobs.create/claim/deliver)
        # alongside any dynamic agent-skills harvested from the agent
        # registry. The two describe different layers — meta operations on
        # the Polis network vs. concrete capabilities of online agents —
        # so they should compose, not override.
        "skills": fallback_skills + dynamic_skills,
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
