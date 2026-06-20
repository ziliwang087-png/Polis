"""
Polis v1 user authentication routes.
"""
import logging

from fastapi import APIRouter, HTTPException, status, Header
from typing import Optional

from app.auth import create_access_token, hash_password, verify_password
from app.database import get_db_connection
from app.dependencies import get_current_user
from app.models import (
    UserAuthResponse,
    UserInfo,
    UserLoginRequest,
    UserRegisterRequest,
)

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)


def _user_response(row) -> UserInfo:
    return UserInfo(
        id=row["id"],
        email=row["email"],
        username=row["username"],
        display_name=row.get("display_name"),
        avatar_url=row.get("avatar_url"),
        reputation=row.get("reputation", 0),
        credit_balance=row.get("credit_balance", 10),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


@router.post("/register", response_model=UserAuthResponse)
def register(request: UserRegisterRequest):
    password_hash = hash_password(request.password)
    display_name = request.display_name or request.username

    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT id FROM users WHERE email = %s OR username = %s",
                (request.email, request.username),
            )
            if cur.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email or username already registered",
                )

            cur.execute(
                """
                INSERT INTO users (
                    email, password_hash, username, display_name, avatar_url
                )
                VALUES (%s, %s, %s, %s, %s)
                RETURNING *
                """,
                (
                    request.email,
                    password_hash,
                    request.username,
                    display_name,
                    request.avatar_url,
                ),
            )
            row = cur.fetchone()

        token = create_access_token({"sub": str(row["id"]), "type": "user"})
        return UserAuthResponse(token=token, user=_user_response(row))

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("User registration failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration failed: {exc}",
        )


@router.post("/login", response_model=UserAuthResponse)
def login(request: UserLoginRequest):
    if not request.email and not request.username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="email or username required",
        )

    identifier = request.email or request.username
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT * FROM users WHERE email = %s OR username = %s",
                (identifier, identifier),
            )
            row = cur.fetchone()

        if not row or not verify_password(request.password, row["password_hash"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        token = create_access_token({"sub": str(row["id"]), "type": "user"})
        return UserAuthResponse(token=token, user=_user_response(row))

    except HTTPException:
        raise
    except Exception:
        logger.exception("User login failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed",
        )


@router.get("/me", response_model=UserInfo)
def me(authorization: Optional[str] = Header(None)):
    user_id, user_type = get_current_user(authorization)
    if user_type != "user":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User token required",
        )

    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE id = %s", (str(user_id),))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="User not found")
        return _user_response(row)
