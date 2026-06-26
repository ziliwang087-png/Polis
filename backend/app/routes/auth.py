"""
Polis v1 user authentication routes.
"""
import logging

from fastapi import APIRouter, Cookie, HTTPException, status, Header, Request, Response
from slowapi import Limiter
from slowapi.util import get_remote_address
from typing import Optional

from app.auth import create_access_token, hash_password, verify_password
from app.config import settings
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

limiter = Limiter(key_func=get_remote_address, enabled=settings.RATE_LIMIT_ENABLED)


def _cookie_secure() -> bool:
    if settings.AUTH_COOKIE_SECURE is not None:
        return bool(settings.AUTH_COOKIE_SECURE)
    return settings.ENV == "production"


def _cookie_samesite() -> str:
    if settings.AUTH_COOKIE_SAMESITE:
        return settings.AUTH_COOKIE_SAMESITE
    return "none" if settings.ENV == "production" else "lax"


def _set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        settings.AUTH_COOKIE_NAME,
        token,
        max_age=settings.AUTH_COOKIE_MAX_AGE_SECONDS,
        httponly=True,
        secure=_cookie_secure(),
        samesite=_cookie_samesite(),
        path="/",
    )


def _user_response(row) -> UserInfo:
    return UserInfo(
        id=row["id"],
        email=row["email"],
        username=row["username"],
        display_name=row.get("display_name"),
        avatar_url=row.get("avatar_url"),
        reputation=row.get("reputation", 0),
        credit_balance=row.get("credit_balance", 100),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


@router.post("/register", response_model=UserAuthResponse)
@limiter.limit("3/hour")  # 防止批量注册
def register(register_request: UserRegisterRequest, request: Request, response: Response):
    password_hash = hash_password(register_request.password)
    display_name = register_request.display_name or register_request.username

    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT id FROM users WHERE email = %s OR username = %s",
                (register_request.email, register_request.username),
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
                    register_request.email,
                    password_hash,
                    register_request.username,
                    display_name,
                    register_request.avatar_url,
                ),
            )
            row = cur.fetchone()

        token = create_access_token({"sub": str(row["id"]), "type": "user"})
        _set_auth_cookie(response, token)
        return UserAuthResponse(token=token, user=_user_response(row))

    except HTTPException:
        raise
    except Exception:
        logger.exception("User registration failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed",
        )


@router.post("/login", response_model=UserAuthResponse)
@limiter.limit("5/minute")  # 防止暴力破解
def login(login_request: UserLoginRequest, request: Request, response: Response):
    if not login_request.email and not login_request.username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="email or username required",
        )

    identifier = login_request.email or login_request.username
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT * FROM users WHERE email = %s OR username = %s",
                (identifier, identifier),
            )
            row = cur.fetchone()

        if not row or not verify_password(login_request.password, row["password_hash"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        token = create_access_token({"sub": str(row["id"]), "type": "user"})
        _set_auth_cookie(response, token)
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
def me(
    authorization: Optional[str] = Header(None),
    polis_token: Optional[str] = Cookie(None),
):
    user_id, user_type = get_current_user(authorization, polis_token)
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


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(settings.AUTH_COOKIE_NAME, path="/")
    return {"ok": True}
