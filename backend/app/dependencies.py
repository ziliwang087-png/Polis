"""
FastAPI dependencies for authentication
"""
from fastapi import Header, HTTPException, status
from typing import Optional, Tuple
from uuid import UUID
from app.auth import decode_access_token, hash_agent_token
from app.database import get_db_connection


def _extract_bearer(authorization: Optional[str]) -> str:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing",
        )
    try:
        scheme, token = authorization.split()
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format",
        )
    if scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication scheme",
        )
    return token


def get_current_owner(authorization: Optional[str] = Header(None)) -> UUID:
    """Dependency: extract a Polis user UUID from a JWT bearer token."""
    token = _extract_bearer(authorization)
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    if payload.get("type") not in (None, "owner", "user"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User token required",
        )
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )
    return UUID(user_id)


def get_current_agent(authorization: Optional[str] = Header(None)) -> UUID:
    """Dependency: extract an agent UUID from a JWT bearer token."""
    token = _extract_bearer(authorization)
    payload = decode_access_token(token)
    if payload and payload.get("type") == "agent":
        agent_id = payload.get("sub")
        if not agent_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
            )
        return UUID(agent_id)

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Agent token required",
    )


def get_current_user(authorization: Optional[str] = Header(None)) -> Tuple[UUID, str]:
    """Return (subject_id, token_type) for user or agent JWTs."""
    token = _extract_bearer(authorization)
    payload = decode_access_token(token)
    if payload:
        user_type = payload.get("type", "user")
        sub = payload.get("sub")
        if not sub:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
            )
        if user_type == "owner":
            user_type = "user"
        if user_type not in ("user", "agent"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
            )
        return UUID(sub), user_type

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid token",
    )
