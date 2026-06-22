"""
Private message routes.
"""
import logging
from datetime import datetime
from typing import List, Optional, Tuple
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.database import get_db_connection
from app.dependencies import get_current_user

router = APIRouter(prefix="/messages", tags=["messages"])
logger = logging.getLogger(__name__)

CurrentUser = Tuple[UUID, str]


class MessageCreateRequest(BaseModel):
    receiver_id: UUID
    content: str = Field(..., min_length=1, max_length=5000)


class MessageResponse(BaseModel):
    id: UUID
    sender_id: UUID
    receiver_id: UUID
    content: str
    read: bool
    created_at: datetime


class ConversationResponse(BaseModel):
    conversation_user_id: UUID
    conversation_user_name: Optional[str] = None
    last_message: str
    last_message_at: datetime
    unread_count: int = 0


def _resolve_user_id(cur, current_user: CurrentUser) -> UUID:
    subject_id, subject_type = current_user
    if subject_type == "user":
        return subject_id
    cur.execute("SELECT owner_id FROM agents WHERE id = %s", (str(subject_id),))
    agent = cur.fetchone()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent["owner_id"]


def _ensure_registered_user(cur, user_id: UUID):
    cur.execute("SELECT id FROM users WHERE id = %s", (str(user_id),))
    if not cur.fetchone():
        raise HTTPException(status_code=404, detail="User not found")


@router.post("", response_model=MessageResponse)
def send_message(
    request: MessageCreateRequest,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Send a private message to a registered user."""
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            sender_id = _resolve_user_id(cur, current_user)
            _ensure_registered_user(cur, request.receiver_id)
            if str(sender_id) == str(request.receiver_id):
                raise HTTPException(status_code=400, detail="Cannot message yourself")

            cur.execute(
                """
                INSERT INTO messages (sender_id, receiver_id, content)
                VALUES (%s, %s, %s)
                RETURNING id, sender_id, receiver_id, content, read, created_at
                """,
                (str(sender_id), str(request.receiver_id), request.content),
            )
            return MessageResponse(**dict(cur.fetchone()))
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Send message failed")
        raise HTTPException(status_code=500, detail=f"Send message failed: {exc}")


@router.get("", response_model=List[ConversationResponse])
def list_messages(current_user: CurrentUser = Depends(get_current_user)):
    """List conversations for the current user."""
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            user_id = _resolve_user_id(cur, current_user)
            cur.execute(
                """
                WITH scoped AS (
                    SELECT
                        m.*,
                        CASE
                            WHEN m.sender_id = %s THEN m.receiver_id
                            ELSE m.sender_id
                        END AS conversation_user_id
                    FROM messages m
                    WHERE m.sender_id = %s OR m.receiver_id = %s
                ),
                latest AS (
                    SELECT DISTINCT ON (conversation_user_id)
                        conversation_user_id,
                        content AS last_message,
                        created_at AS last_message_at
                    FROM scoped
                    ORDER BY conversation_user_id, created_at DESC
                )
                SELECT
                    latest.conversation_user_id,
                    COALESCE(u.display_name, u.username) AS conversation_user_name,
                    latest.last_message,
                    latest.last_message_at,
                    COUNT(unread.id) AS unread_count
                FROM latest
                JOIN users u ON u.id = latest.conversation_user_id
                LEFT JOIN messages unread
                    ON unread.sender_id = latest.conversation_user_id
                   AND unread.receiver_id = %s
                   AND unread.read = FALSE
                GROUP BY latest.conversation_user_id, u.display_name, u.username, latest.last_message, latest.last_message_at
                ORDER BY latest.last_message_at DESC
                """,
                (str(user_id), str(user_id), str(user_id), str(user_id)),
            )
            return [ConversationResponse(**dict(row)) for row in cur.fetchall()]
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("List messages failed")
        raise HTTPException(status_code=500, detail=f"List messages failed: {exc}")


@router.get("/unread")
def get_unread_count(current_user: CurrentUser = Depends(get_current_user)):
    """Return unread private message count."""
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            user_id = _resolve_user_id(cur, current_user)
            cur.execute(
                "SELECT COUNT(*) AS count FROM messages WHERE receiver_id = %s AND read = FALSE",
                (str(user_id),),
            )
            row = cur.fetchone()
            return {"count": row["count"] if row else 0}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unread count failed")
        raise HTTPException(status_code=500, detail=f"Unread count failed: {exc}")


@router.get("/{user_id}", response_model=List[MessageResponse])
def get_thread(
    user_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Return message history with one registered user."""
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            current_user_id = _resolve_user_id(cur, current_user)
            _ensure_registered_user(cur, user_id)
            cur.execute(
                """
                SELECT m.id, m.sender_id, m.receiver_id, m.content, m.read, m.created_at
                FROM messages m
                WHERE
                    (m.sender_id = %s AND m.receiver_id = %s)
                    OR
                    (m.sender_id = %s AND m.receiver_id = %s)
                ORDER BY m.created_at ASC
                """,
                (str(current_user_id), str(user_id), str(user_id), str(current_user_id)),
            )
            return [MessageResponse(**dict(row)) for row in cur.fetchall()]
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Thread fetch failed")
        raise HTTPException(status_code=500, detail=f"Thread fetch failed: {exc}")


@router.patch("/{message_id}/read", response_model=MessageResponse)
def mark_message_read(
    message_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Mark one received message as read."""
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            user_id = _resolve_user_id(cur, current_user)
            cur.execute(
                """
                UPDATE messages
                SET read = TRUE
                WHERE id = %s AND receiver_id = %s
                RETURNING id, sender_id, receiver_id, content, read, created_at
                """,
                (str(message_id), str(user_id)),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Message not found")
            return MessageResponse(**dict(row))
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Mark message read failed")
        raise HTTPException(status_code=500, detail=f"Mark message read failed: {exc}")
