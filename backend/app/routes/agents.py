"""
Polis v1 A2A agent routes.
"""
import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, status, Depends, Query
from psycopg2.extras import Json
from starlette.responses import StreamingResponse

from app.auth import create_access_token
from app.database import get_db_connection
from app.dependencies import get_current_owner, get_current_user
from app.models import AgentCreateRequest, AgentHeartbeatRequest, AgentResponse

router = APIRouter(prefix="/agents", tags=["agents"])
logger = logging.getLogger(__name__)


def _agent_response(row, token: Optional[str] = None) -> AgentResponse:
    return AgentResponse(
        id=row["id"],
        owner_id=row["owner_id"],
        name=row["name"],
        display_name=row.get("display_name"),
        description=row.get("description"),
        endpoint_url=row.get("endpoint_url"),
        websocket_id=row.get("websocket_id"),
        auth_method=row.get("auth_method", "none"),
        agent_card=row.get("agent_card") or {},
        status=row.get("status", "offline"),
        last_heartbeat_at=row.get("last_heartbeat_at"),
        total_jobs=row.get("total_jobs", 0),
        success_rate=float(row.get("success_rate") or 0),
        avg_rating=row.get("avg_rating"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        token=token,
    )


def _card_skills(agent_card: Dict[str, Any]) -> List[Dict[str, Any]]:
    skills = agent_card.get("skills") or []
    return [skill for skill in skills if isinstance(skill, dict)]


@router.post("", response_model=AgentResponse)
def create_agent(
    request: AgentCreateRequest,
    owner_id: UUID = Depends(get_current_owner),
):
    agent_card = dict(request.agent_card)
    agent_card.setdefault("name", request.name)
    if request.description:
        agent_card.setdefault("description", request.description)
    if request.endpoint_url:
        agent_card.setdefault("url", request.endpoint_url)

    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT id FROM agents WHERE owner_id = %s AND name = %s",
                (str(owner_id), request.name),
            )
            if cur.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Agent name already registered for this user",
                )

            cur.execute(
                """
                INSERT INTO agents (
                    owner_id, name, display_name, description, endpoint_url,
                    websocket_id, auth_method, auth_config, agent_card, status
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING *
                """,
                (
                    str(owner_id),
                    request.name,
                    request.display_name,
                    request.description,
                    request.endpoint_url,
                    request.websocket_id,
                    request.auth_method,
                    Json(request.auth_config),
                    Json(agent_card),
                    request.status,
                ),
            )
            row = cur.fetchone()

            # Collect skill names from two sources:
            # 1) request.skills (plain string list — newcomer UX)
            # 2) request.agent_card.skills (mixed: A2A structured dicts OR strings)
            seen_skill_ids = set()

            for plain in request.skills:
                if not plain:
                    continue
                sk = plain.strip()
                if not sk or sk in seen_skill_ids:
                    continue
                seen_skill_ids.add(sk)
                cur.execute(
                    """
                    INSERT INTO agent_skills (
                        agent_id, skill_id, name, description, examples,
                        input_schema, output_schema
                    )
                    VALUES (%s, %s, %s, NULL, NULL, NULL, NULL)
                    ON CONFLICT (agent_id, skill_id) DO NOTHING
                    """,
                    (str(row["id"]), sk, sk),
                )

            for raw in (agent_card.get("skills") or []):
                # A2A structured form
                if isinstance(raw, dict):
                    skill_id = raw.get("id") or raw.get("skill_id") or raw.get("name")
                    skill_name = raw.get("name")
                    if not skill_id or not skill_name or skill_id in seen_skill_ids:
                        continue
                    seen_skill_ids.add(skill_id)
                    cur.execute(
                        """
                        INSERT INTO agent_skills (
                            agent_id, skill_id, name, description, examples,
                            input_schema, output_schema
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (agent_id, skill_id) DO UPDATE SET
                            name = EXCLUDED.name,
                            description = EXCLUDED.description,
                            examples = EXCLUDED.examples,
                            input_schema = EXCLUDED.input_schema,
                            output_schema = EXCLUDED.output_schema
                        """,
                        (
                            str(row["id"]),
                            skill_id,
                            skill_name,
                            raw.get("description"),
                            Json(raw.get("examples")),
                            Json(raw.get("inputSchema") or raw.get("input_schema")),
                            Json(raw.get("outputSchema") or raw.get("output_schema")),
                        ),
                    )
                # Plain string form (UUMit-style UX)
                elif isinstance(raw, str) and raw.strip():
                    sk = raw.strip()
                    if sk in seen_skill_ids:
                        continue
                    seen_skill_ids.add(sk)
                    cur.execute(
                        """
                        INSERT INTO agent_skills (
                            agent_id, skill_id, name, description, examples,
                            input_schema, output_schema
                        )
                        VALUES (%s, %s, %s, NULL, NULL, NULL, NULL)
                        ON CONFLICT (agent_id, skill_id) DO NOTHING
                        """,
                        (str(row["id"]), sk, sk),
                    )

        token = create_access_token({"sub": str(row["id"]), "type": "agent"})
        return _agent_response(row, token=token)

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Agent registration failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent registration failed: {exc}",
        )


@router.get("", response_model=List[AgentResponse])
def list_agents():
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM agents ORDER BY created_at DESC")
        return [_agent_response(row) for row in cur.fetchall()]


@router.get("/{agent_id}", response_model=AgentResponse)
def get_agent(agent_id: UUID):
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM agents WHERE id = %s", (str(agent_id),))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Agent not found")
        return _agent_response(row)


@router.post("/{agent_id}/heartbeat", response_model=AgentResponse)
def heartbeat(
    agent_id: UUID,
    request: AgentHeartbeatRequest,
    authorization: Optional[str] = Header(None),
):
    subject_id, subject_type = get_current_user(authorization)

    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM agents WHERE id = %s", (str(agent_id),))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Agent not found")

        if subject_type == "agent" and row["id"] != subject_id:
            raise HTTPException(status_code=403, detail="Agent token mismatch")
        if subject_type == "user" and row["owner_id"] != subject_id:
            raise HTTPException(status_code=403, detail="You do not own this agent")

        if request.websocket_id:
            cur.execute(
                """
                UPDATE agents
                SET status = %s, websocket_id = %s, last_heartbeat_at = NOW(),
                    updated_at = NOW()
                WHERE id = %s
                RETURNING *
                """,
                (request.status, request.websocket_id, str(agent_id)),
            )
        else:
            cur.execute(
                """
                UPDATE agents
                SET status = %s, last_heartbeat_at = NOW(), updated_at = NOW()
                WHERE id = %s
                RETURNING *
                """,
                (request.status, str(agent_id)),
            )
        return _agent_response(cur.fetchone())


@router.delete("/{agent_id}", response_model=dict)
def delete_agent(agent_id: UUID, owner_id: UUID = Depends(get_current_owner)):
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM agents WHERE id = %s AND owner_id = %s RETURNING id",
            (str(agent_id), str(owner_id)),
        )
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Agent not found")
        return {"deleted": True}


@router.get("/{agent_id}/inbox")
async def stream_agent_inbox(
    agent_id: UUID,
    authorization: Optional[str] = Header(None),
    once: bool = Query(False, description="Return current matches then close"),
):
    """
    SSE stream of jobs matching this agent's skills.

    Auth: agent JWT or owner user JWT.
    Behaviour:
      1. Phase 1 — Backlog: emit every currently-`submitted` job whose
         `required_skill` is in this agent's declared skill set as
         `event: job.available`.
      2. Phase 2 — Live: LISTEN polis_jobs and forward every newly-created
         matching job (also `event: job.available`).
      3. Heartbeat every 15s (`event: heartbeat`). Stream caps at 10 minutes.

    Pass `?once=true` to skip phase 2 (useful for HTTP smoke tests).
    """
    from app.routes.jobs import _build_inbox_generator, _agent_skill_set, _agent_owned_by, _sse_raw

    subject_id, subject_type = get_current_user(authorization)

    with get_db_connection() as conn:
        cur = conn.cursor()
        _agent_owned_by(cur, agent_id, subject_id, subject_type)
        skills = _agent_skill_set(cur, agent_id)

    if not skills:
        async def empty_stream():
            yield _sse_raw("info", {"reason": "agent has no skills declared"})
        return StreamingResponse(empty_stream(), media_type="text/event-stream")

    generator = _build_inbox_generator(agent_id, list(skills), skills, once)
    return StreamingResponse(generator(), media_type="text/event-stream")
