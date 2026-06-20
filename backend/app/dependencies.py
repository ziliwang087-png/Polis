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
    """Dependency: extract owner UUID from a JWT bearer token (type=owner)."""
    token = _extract_bearer(authorization)
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    if payload.get("type") not in (None, "owner"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Owner token required",
        )
    owner_id = payload.get("sub")
    if not owner_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )
    return UUID(owner_id)


def get_current_agent(authorization: Optional[str] = Header(None)) -> UUID:
    """Dependency: extract agent UUID.

    支持两种 token：
    1. JWT 的 type=agent（新统一注册流程发的）
    2. agent_token + token_hash 查询（旧 agent SDK 流程）
    """
    token = _extract_bearer(authorization)

    # 1) 先尝试 JWT
    payload = decode_access_token(token)
    if payload and payload.get("type") == "agent":
        agent_id = payload.get("sub")
        if not agent_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
            )
        return UUID(agent_id)

    # 2) 旧 agent token：用 sha256 hash 查 agents 表
    token_hash = hash_agent_token(token)
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id FROM agents WHERE token_hash = %s",
            (token_hash,),
        )
        result = cur.fetchone()
        if not result:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid agent token",
            )
        return result['id']


def get_current_user(authorization: Optional[str] = Header(None)) -> Tuple[UUID, str]:
    """统一身份解析：返回 (user_id, user_type)。
    优先解析 JWT type 字段；如果是旧 agent token，返回 ('agent', uuid)。
    """
    token = _extract_bearer(authorization)
    payload = decode_access_token(token)
    if payload:
        user_type = payload.get("type", "owner")
        sub = payload.get("sub")
        if not sub:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
            )
        if user_type not in ("owner", "agent"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
            )
        return UUID(sub), user_type

    # fallback: 旧 agent token
    token_hash = hash_agent_token(token)
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id FROM agents WHERE token_hash = %s",
            (token_hash,),
        )
        row = cur.fetchone()
        if row:
            return row['id'], 'agent'
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid token",
    )
