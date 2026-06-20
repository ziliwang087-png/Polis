"""
Polis v1 A2A-compatible job routes.
"""
import asyncio
import base64
import json
import logging
import time
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Query, status
from fastapi.encoders import jsonable_encoder
from psycopg2.extras import Json
from starlette.responses import StreamingResponse

from app.auth import decode_access_token
from app.database import get_db_connection
from app.dependencies import get_current_owner, get_current_user
from app.models import (
    AttachmentInput,
    JobArtifactRequest,
    JobClaimRequest,
    JobCreateRequest,
    JobEventResponse,
    JobProgressRequest,
    JobRatingRequest,
    JobRatingResponse,
    JobResponse,
)
from app.services import storage
from app.services.storage import StorageNotConfigured

router = APIRouter(prefix="/jobs", tags=["jobs"])
logger = logging.getLogger(__name__)

JOB_NOTIFY_CHANNEL = "polis_jobs"


def _json(value: Any) -> Json:
    return Json(jsonable_encoder(value))


def _event_payload(**kwargs) -> Dict[str, Any]:
    return jsonable_encoder(kwargs)


def _insert_event(cur, job_id: UUID, event_type: str, payload: Dict[str, Any]):
    cur.execute(
        """
        INSERT INTO job_events (job_id, event_type, payload)
        VALUES (%s, %s, %s)
        RETURNING *
        """,
        (str(job_id), event_type, _json(payload)),
    )
    return cur.fetchone()


def _notify_job_created(cur, job_row):
    payload = {
        "event": "job.created",
        "job_id": str(job_row["id"]),
        "required_skill": job_row["required_skill"],
        "title": job_row["title"],
    }
    cur.execute(
        "SELECT pg_notify(%s, %s)",
        (JOB_NOTIFY_CHANNEL, json.dumps(payload)),
    )


def _decode_attachment_content(attachment: AttachmentInput) -> bytes:
    try:
        return base64.b64decode(attachment.content_base64 or "", validate=True)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid base64 attachment: {attachment.filename}",
        ) from exc


def _stored_attachments(attachments: List[AttachmentInput], owner_id: UUID) -> List[Dict[str, Any]]:
    stored: List[Dict[str, Any]] = []
    for attachment in attachments:
        mime = attachment.mime or "application/octet-stream"
        if attachment.content_base64:
            try:
                url = storage.upload_bytes(
                    data=_decode_attachment_content(attachment),
                    filename=attachment.filename,
                    content_type=mime,
                    owner_id=owner_id,
                )
            except StorageNotConfigured as exc:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=str(exc),
                ) from exc
        elif attachment.url:
            url = attachment.url
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Attachment {attachment.filename} needs url or content_base64",
            )

        stored.append({
            "url": url,
            "filename": attachment.filename,
            "mime": mime,
        })
    return stored


def _artifact_file_url(request: JobArtifactRequest, owner_id: UUID) -> Optional[str]:
    if request.content_base64:
        if not request.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="filename is required when content_base64 is provided",
            )
        try:
            return storage.upload_bytes(
                data=base64.b64decode(request.content_base64, validate=True),
                filename=request.filename,
                content_type=request.mime or "application/octet-stream",
                owner_id=owner_id,
            )
        except StorageNotConfigured as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
            ) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid base64 artifact",
            ) from exc
    return request.file_url


def _a2a_task(row, artifacts: List[Dict[str, Any]]) -> Dict[str, Any]:
    artifact_parts = []
    for artifact in artifacts:
        if artifact.get("file_url"):
            part = {
                "kind": "file",
                "file": {
                    "uri": artifact["file_url"],
                    "mimeType": (artifact.get("metadata") or {}).get("mime"),
                },
            }
        else:
            part = {"kind": "text", "text": artifact.get("content") or ""}
        artifact_parts.append({
            "artifactId": str(artifact["id"]),
            "name": artifact["type"],
            "parts": [part],
        })

    return {
        "kind": "task",
        "id": str(row["id"]),
        "contextId": str(row["from_user_id"]),
        "status": {"state": row["status"]},
        "history": row.get("input_messages") or [],
        "artifacts": artifact_parts,
        "metadata": {
            "title": row["title"],
            "requiredSkill": row["required_skill"],
            "attachments": row.get("attachments") or [],
        },
    }


def _job_response(cur, row) -> JobResponse:
    cur.execute(
        "SELECT * FROM job_artifacts WHERE job_id = %s ORDER BY created_at ASC",
        (str(row["id"]),),
    )
    artifacts = [dict(artifact) for artifact in cur.fetchall()]

    cur.execute("SELECT * FROM job_ratings WHERE job_id = %s", (str(row["id"]),))
    rating_row = cur.fetchone()

    cur.execute(
        "SELECT * FROM job_events WHERE job_id = %s ORDER BY created_at ASC",
        (str(row["id"]),),
    )
    events = [JobEventResponse(**dict(event)) for event in cur.fetchall()]

    return JobResponse(
        id=row["id"],
        from_user_id=row["from_user_id"],
        to_agent_id=row.get("to_agent_id"),
        title=row["title"],
        description=row["description"],
        required_skill=row["required_skill"],
        input_messages=row.get("input_messages") or [],
        attachments=row.get("attachments") or [],
        status=row["status"],
        progress=row.get("progress"),
        created_at=row["created_at"],
        claimed_at=row.get("claimed_at"),
        started_at=row.get("started_at"),
        completed_at=row.get("completed_at"),
        artifacts=artifacts,
        rating=JobRatingResponse(**dict(rating_row)) if rating_row else None,
        events=events,
        a2a_task=_a2a_task(row, artifacts),
    )


def _agent_for_token(cur, authorization: Optional[str], request_agent_id: Optional[UUID]) -> Dict[str, Any]:
    subject_id, subject_type = get_current_user(authorization)
    agent_id = subject_id if subject_type == "agent" else request_agent_id
    if not agent_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="agent_id is required when using a user token",
        )

    cur.execute("SELECT * FROM agents WHERE id = %s", (str(agent_id),))
    agent = cur.fetchone()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    if subject_type == "agent" and agent["id"] != subject_id:
        raise HTTPException(status_code=403, detail="Agent token mismatch")
    if subject_type == "user" and agent["owner_id"] != subject_id:
        raise HTTPException(status_code=403, detail="You do not own this agent")
    return dict(agent)


def _subject_from_token_value(token: str) -> tuple[UUID, str]:
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    subject = payload.get("sub")
    subject_type = payload.get("type", "user")
    if subject_type == "owner":
        subject_type = "user"
    if not subject or subject_type not in ("user", "agent"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )
    return UUID(subject), subject_type


def _subject_from_event_auth(
    authorization: Optional[str],
    token: Optional[str],
) -> tuple[UUID, str]:
    if authorization:
        return get_current_user(authorization)
    if token:
        return _subject_from_token_value(token)
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authorization header or token query parameter required",
    )


def _assert_job_event_access(cur, job_id: UUID, subject_id: UUID, subject_type: str):
    cur.execute("SELECT * FROM jobs WHERE id = %s", (str(job_id),))
    job = cur.fetchone()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if subject_type == "user" and job["from_user_id"] == subject_id:
        return
    if not job.get("to_agent_id"):
        raise HTTPException(status_code=403, detail="You cannot read this job event stream")

    cur.execute("SELECT * FROM agents WHERE id = %s", (str(job["to_agent_id"]),))
    agent = cur.fetchone()
    if not agent:
        raise HTTPException(status_code=403, detail="Assigned agent not found")
    if subject_type == "agent" and agent["id"] == subject_id:
        return
    if subject_type == "user" and agent["owner_id"] == subject_id:
        return
    raise HTTPException(status_code=403, detail="You cannot read this job event stream")


def _assert_assigned(job_row, agent_id: UUID):
    if job_row.get("to_agent_id") != agent_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Agent has not claimed this job",
        )


@router.post("", response_model=JobResponse)
def create_job(
    request: JobCreateRequest,
    user_id: UUID = Depends(get_current_owner),
):
    attachments = _stored_attachments(request.attachments, user_id)
    input_messages = request.input_messages or [
        {
            "role": "user",
            "parts": [{"kind": "text", "text": request.description}],
        }
    ]

    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE users
                SET credit_balance = credit_balance - 1, updated_at = NOW()
                WHERE id = %s AND credit_balance > 0
                RETURNING credit_balance
                """,
                (str(user_id),),
            )
            if not cur.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_402_PAYMENT_REQUIRED,
                    detail="Insufficient credit balance",
                )

            cur.execute(
                """
                INSERT INTO jobs (
                    from_user_id, title, description, required_skill,
                    input_messages, attachments, status
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING *
                """,
                (
                    str(user_id),
                    request.title,
                    request.description,
                    request.required_skill,
                    _json(input_messages),
                    _json(attachments),
                    "submitted",
                ),
            )
            job = cur.fetchone()
            _insert_event(
                cur,
                job["id"],
                "created",
                _event_payload(required_skill=request.required_skill),
            )
            _notify_job_created(cur, job)
            return _job_response(cur, job)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Job creation failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Job creation failed: {exc}",
        )


@router.get("", response_model=List[JobResponse])
def list_jobs(
    status_filter: Optional[str] = Query(None, alias="status"),
    skill: Optional[str] = Query(None),
    mine: Optional[str] = Query(None, pattern="^(sent|received)$"),
    authorization: Optional[str] = Header(None),
):
    with get_db_connection() as conn:
        cur = conn.cursor()
        query = "SELECT * FROM jobs WHERE 1=1"
        params: List[Any] = []
        if status_filter:
            query += " AND status = %s"
            params.append(status_filter)
        if skill:
            query += " AND required_skill = %s"
            params.append(skill)
        if mine:
            subject_id, subject_type = get_current_user(authorization)
            if subject_type != "user":
                raise HTTPException(status_code=403, detail="User token required")
            if mine == "sent":
                query += " AND from_user_id = %s"
                params.append(str(subject_id))
            else:
                cur.execute("SELECT id FROM agents WHERE owner_id = %s", (str(subject_id),))
                agent_ids = [str(row["id"]) for row in cur.fetchall()]
                if not agent_ids:
                    return []
                query += " AND to_agent_id = ANY(%s::uuid[])"
                params.append(agent_ids)
        query += " ORDER BY created_at DESC"
        cur.execute(query, params)
        return [_job_response(cur, row) for row in cur.fetchall()]


@router.get("/{job_id}", response_model=JobResponse)
def get_job(job_id: UUID):
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM jobs WHERE id = %s", (str(job_id),))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Job not found")
        return _job_response(cur, row)


@router.post("/{job_id}/claim", response_model=JobResponse)
def claim_job(
    job_id: UUID,
    request: Optional[JobClaimRequest] = Body(default=None),
    authorization: Optional[str] = Header(None),
):
    with get_db_connection() as conn:
        cur = conn.cursor()
        agent = _agent_for_token(
            cur,
            authorization,
            request.agent_id if request else None,
        )

        cur.execute("SELECT * FROM jobs WHERE id = %s FOR UPDATE", (str(job_id),))
        job = cur.fetchone()
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        if job["status"] != "submitted":
            raise HTTPException(status_code=409, detail="Job is already claimed")

        cur.execute(
            """
            UPDATE jobs
            SET to_agent_id = %s, status = 'claimed',
                claimed_at = NOW(), started_at = NOW()
            WHERE id = %s
            RETURNING *
            """,
            (str(agent["id"]), str(job_id)),
        )
        job = cur.fetchone()
        cur.execute(
            "UPDATE agents SET total_jobs = total_jobs + 1, updated_at = NOW() WHERE id = %s",
            (str(agent["id"]),),
        )
        _insert_event(
            cur,
            job["id"],
            "claimed",
            _event_payload(agent_id=agent["id"]),
        )
        return _job_response(cur, job)


@router.post("/{job_id}/progress", response_model=JobResponse)
def update_progress(
    job_id: UUID,
    request: JobProgressRequest,
    authorization: Optional[str] = Header(None),
):
    with get_db_connection() as conn:
        cur = conn.cursor()
        agent = _agent_for_token(cur, authorization, request.agent_id)
        cur.execute("SELECT * FROM jobs WHERE id = %s", (str(job_id),))
        job = cur.fetchone()
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        _assert_assigned(job, agent["id"])

        cur.execute(
            """
            UPDATE jobs
            SET progress = %s, status = 'working'
            WHERE id = %s
            RETURNING *
            """,
            (request.progress, str(job_id)),
        )
        job = cur.fetchone()
        _insert_event(
            cur,
            job["id"],
            "progress",
            _event_payload(progress=request.progress, agent_id=agent["id"]),
        )
        return _job_response(cur, job)


@router.post("/{job_id}/artifacts", response_model=JobResponse)
def submit_artifact(
    job_id: UUID,
    request: JobArtifactRequest,
    authorization: Optional[str] = Header(None),
):
    with get_db_connection() as conn:
        cur = conn.cursor()
        agent = _agent_for_token(cur, authorization, request.agent_id)
        cur.execute("SELECT * FROM jobs WHERE id = %s", (str(job_id),))
        job = cur.fetchone()
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        _assert_assigned(job, agent["id"])

        file_url = _artifact_file_url(request, agent["owner_id"])
        metadata = dict(request.metadata)
        if request.filename:
            metadata.setdefault("filename", request.filename)
        if request.mime:
            metadata.setdefault("mime", request.mime)

        cur.execute(
            """
            INSERT INTO job_artifacts (job_id, type, content, file_url, metadata)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                str(job_id),
                request.type,
                request.content,
                file_url,
                _json(metadata),
            ),
        )
        artifact = cur.fetchone()

        cur.execute(
            """
            UPDATE jobs
            SET status = 'completed', completed_at = NOW()
            WHERE id = %s
            RETURNING *
            """,
            (str(job_id),),
        )
        job = cur.fetchone()
        cur.execute(
            "UPDATE users SET credit_balance = credit_balance + 1, updated_at = NOW() WHERE id = %s",
            (str(agent["owner_id"]),),
        )
        _insert_event(
            cur,
            job["id"],
            "delivered",
            _event_payload(agent_id=agent["id"], artifact_id=artifact["id"]),
        )
        return _job_response(cur, job)


@router.post("/{job_id}/cancel", response_model=JobResponse)
def cancel_job(job_id: UUID, user_id: UUID = Depends(get_current_owner)):
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM jobs WHERE id = %s", (str(job_id),))
        job = cur.fetchone()
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        if job["from_user_id"] != user_id:
            raise HTTPException(status_code=403, detail="You do not own this job")
        if job["status"] in ("completed", "failed", "canceled"):
            raise HTTPException(status_code=409, detail="Job cannot be canceled")

        cur.execute(
            "UPDATE jobs SET status = 'canceled' WHERE id = %s RETURNING *",
            (str(job_id),),
        )
        job = cur.fetchone()
        _insert_event(cur, job["id"], "canceled", _event_payload(user_id=user_id))
        return _job_response(cur, job)


@router.post("/{job_id}/rate", response_model=JobRatingResponse)
def rate_job(
    job_id: UUID,
    request: JobRatingRequest,
    user_id: UUID = Depends(get_current_owner),
):
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM jobs WHERE id = %s", (str(job_id),))
        job = cur.fetchone()
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        if job["from_user_id"] != user_id:
            raise HTTPException(status_code=403, detail="You do not own this job")
        if job["status"] != "completed":
            raise HTTPException(status_code=409, detail="Job is not completed")

        cur.execute(
            """
            INSERT INTO job_ratings (job_id, rater_id, stars, feedback)
            VALUES (%s, %s, %s, %s)
            RETURNING *
            """,
            (str(job_id), str(user_id), request.stars, request.feedback),
        )
        rating = cur.fetchone()
        if job.get("to_agent_id"):
            cur.execute(
                """
                UPDATE agents
                SET avg_rating = (
                    SELECT AVG(stars)::float
                    FROM job_ratings jr
                    JOIN jobs j ON j.id = jr.job_id
                    WHERE j.to_agent_id = %s
                ),
                success_rate = 1.0,
                updated_at = NOW()
                WHERE id = %s
                """,
                (str(job["to_agent_id"]), str(job["to_agent_id"])),
            )
        _insert_event(
            cur,
            job["id"],
            "rated",
            _event_payload(rater_id=user_id, stars=request.stars),
        )
        return JobRatingResponse(**dict(rating))


def _sse_line(event: Dict[str, Any]) -> str:
    payload = json.dumps(jsonable_encoder(event["payload"]), ensure_ascii=False)
    return (
        f"id: {event['id']}\n"
        f"event: {event['event_type']}\n"
        f"data: {payload}\n\n"
    )


def _sse_raw(event_type: str, data: Any, event_id: Optional[str] = None) -> str:
    payload = json.dumps(jsonable_encoder(data), ensure_ascii=False)
    parts = []
    if event_id:
        parts.append(f"id: {event_id}")
    parts.append(f"event: {event_type}")
    parts.append(f"data: {payload}")
    return "\n".join(parts) + "\n\n"


def _agent_skill_set(cur, agent_id: UUID) -> set:
    cur.execute(
        "SELECT name FROM agent_skills WHERE agent_id = %s",
        (str(agent_id),),
    )
    return {row["name"] for row in cur.fetchall()}


def _agent_owned_by(cur, agent_id: UUID, subject_id: UUID, subject_type: str):
    """Verify the caller (user or agent JWT subject) is allowed to read this agent's inbox."""
    cur.execute("SELECT id, owner_id FROM agents WHERE id = %s", (str(agent_id),))
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Agent not found")
    if subject_type == "agent" and row["id"] != subject_id:
        raise HTTPException(status_code=403, detail="Agent token mismatch")
    if subject_type == "user" and row["owner_id"] != subject_id:
        raise HTTPException(status_code=403, detail="You do not own this agent")
    return row


def _build_inbox_generator(agent_id: UUID, skill_list: List[str], skills: set, once: bool):
    """Factory used by the agents router to stream the inbox SSE.

    Implementation: DB polling every 2s. Tried PG LISTEN/NOTIFY first,
    but Supabase's transaction-mode pooler (port 6543) does not support
    session-level LISTEN. Polling is more portable and the latency is
    acceptable for a task marketplace (~2s).
    """
    async def inbox_generator():
        seen: set = set()

        # ── Phase 1: backlog ──────────────────────────────────────────────
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT * FROM jobs
                WHERE status = 'submitted'
                  AND required_skill = ANY(%s::text[])
                ORDER BY created_at ASC
                """,
                (skill_list,),
            )
            for row in cur.fetchall():
                seen.add(str(row["id"]))
                yield _sse_raw("job.available", _job_response(cur, row), event_id=str(row["id"]))

        if once:
            return

        # ── Phase 2: live polling (Supabase pooler-safe) ──────────────────
        deadline = time.monotonic() + 600  # 10 min cap
        last_heartbeat = time.monotonic()

        while time.monotonic() < deadline:
            with get_db_connection() as conn:
                cur = conn.cursor()
                query = """
                SELECT * FROM jobs
                WHERE status = 'submitted'
                  AND required_skill = ANY(%s::text[])
                """
                params: List[Any] = [skill_list]
                if seen:
                    query += " AND NOT (id = ANY(%s::uuid[]))"
                    params.append(list(seen))
                query += " ORDER BY created_at ASC"
                cur.execute(query, params)
                fresh = cur.fetchall()
                for row in fresh:
                    job_id = str(row["id"])
                    if job_id in seen:
                        continue
                    seen.add(job_id)
                    yield _sse_raw("job.available", _job_response(cur, row), event_id=job_id)

            if time.monotonic() - last_heartbeat >= 15:
                last_heartbeat = time.monotonic()
                yield _sse_raw("heartbeat", {"ts": int(last_heartbeat)})

            await asyncio.sleep(2)

    return inbox_generator


@router.get("/{job_id}/events")
async def stream_job_events(
    job_id: UUID,
    once: bool = Query(False, description="Return current events then close"),
    token: Optional[str] = Query(None, description="Bearer token for EventSource clients"),
    authorization: Optional[str] = Header(None),
):
    subject_id, subject_type = _subject_from_event_auth(authorization, token)
    with get_db_connection() as conn:
        cur = conn.cursor()
        _assert_job_event_access(cur, job_id, subject_id, subject_type)

    async def event_generator():
        seen = set()
        deadline = time.monotonic() + 30
        while True:
            with get_db_connection() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT * FROM job_events WHERE job_id = %s ORDER BY created_at ASC",
                    (str(job_id),),
                )
                for event in cur.fetchall():
                    event_id = str(event["id"])
                    if event_id not in seen:
                        seen.add(event_id)
                        yield _sse_line(dict(event))

            if once or time.monotonic() >= deadline:
                break
            await asyncio.sleep(1)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
