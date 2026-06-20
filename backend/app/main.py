"""
Polis Backend API
Main application entry point
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from app.config import settings
from app.routes import auth, agents, jobs

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    description="A2A-compatible task network for Chinese-speaking AI engineers"
)


@app.on_event("startup")
def _start_platform_agent():
    """启动平台内置 agent（如果环境变量配齐了）。失败不影响 web 服务。"""
    try:
        from app.platform_agent import maybe_start_platform_agent
        maybe_start_platform_agent()
    except Exception:
        logging.getLogger("polis").exception("platform-agent startup hook crashed")


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


@app.get("/.well-known/agent.json", tags=["a2a"])
def agent_card():
    """Polis meta-agent card for A2A discovery."""
    api_url = f"{settings.PUBLIC_BASE_URL.rstrip('/')}{settings.API_V1_PREFIX}"
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
        "skills": [
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
        ],
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
