"""
Authentication API routes
"""
from fastapi import APIRouter, HTTPException, status, Depends, Header
from uuid import UUID
from typing import Optional
import logging
import random

from app.models import (
    OwnerRegisterRequest, OwnerRegisterResponse,
    AgentRegisterRequest, AgentRegisterResponse,
    RegisterRequest, LoginRequest, AuthResponse, AuthUser,
)
from app.auth import (
    create_access_token, generate_agent_token,
    hash_password, verify_password,
)
from app.database import get_db_connection
from app.dependencies import get_current_owner, get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)


# ============ 默认头像渐变（注册时随机分配，纯前端展示用） ============
_DEFAULT_GRADIENTS = [
    "linear-gradient(135deg, #ff8a95, #ffc3c8)",
    "linear-gradient(135deg, #ffb74d, #ffa726)",
    "linear-gradient(135deg, #64b5f6, #42a5f5)",
    "linear-gradient(135deg, #ba68c8, #ab47bc)",
    "linear-gradient(135deg, #4db6ac, #26a69a)",
    "linear-gradient(135deg, #f06292, #ec407a)",
    "linear-gradient(135deg, #81c784, #66bb6a)",
    "linear-gradient(135deg, #fdd835, #fbc02d)",
]


def _row_to_auth_user(row, user_type: str) -> AuthUser:
    """把 owners/agents 的行转成 AuthUser，rating 等字段做兼容。"""
    rating = row.get("rating")
    if rating is not None:
        rating = float(rating)
    if user_type == "owner":
        username = row.get("username") or row.get("email", "").split("@")[0]
        email = row.get("email", "")
    else:
        # agent: name 字段当 username
        username = row.get("username") or row.get("name")
        email = row.get("email") or ""
    return AuthUser(
        user_id=row["id"],
        user_type=user_type,
        username=username,
        email=email,
        display_name=row.get("display_name"),
        organization=row.get("organization"),
        rating=rating,
        verified=bool(row.get("verified") or False),
        avatar_gradient=row.get("avatar_gradient"),
    )


# ============ 统一注册 / 登录（前端唯一使用的接口） ============

@router.post("/register", response_model=AuthResponse)
def register(request: RegisterRequest):
    """统一注册：根据 user_type 把记录写到 owners 或 agents 表。

    - owner: 写 owners(email, username, password_hash, ...)
    - agent: 写 agents(name=username, email, password_hash, ...)
              owner_id / token_hash 都允许为空
    """
    pwd_hash = hash_password(request.password)
    avatar = random.choice(_DEFAULT_GRADIENTS)
    display_name = request.display_name or request.username

    try:
        with get_db_connection() as conn:
            cur = conn.cursor()

            if request.user_type == "owner":
                # 检查 email / username 唯一性
                cur.execute(
                    "SELECT id FROM owners WHERE email = %s OR username = %s",
                    (request.email, request.username),
                )
                if cur.fetchone():
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Email or username already registered",
                    )

                cur.execute(
                    """
                    INSERT INTO owners (email, auth_provider, username, password_hash,
                                        display_name, organization, avatar_gradient)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING *
                    """,
                    (
                        request.email, "email", request.username, pwd_hash,
                        display_name, request.organization, avatar,
                    ),
                )
                row = cur.fetchone()
                token = create_access_token({"sub": str(row["id"]), "type": "owner"})
                logger.info(f"Owner registered: {row['id']} ({request.username})")
                return AuthResponse(token=token, user=_row_to_auth_user(row, "owner"))

            # agent
            cur.execute(
                "SELECT id FROM agents WHERE name = %s OR email = %s",
                (request.username, request.email),
            )
            if cur.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email or username already registered",
                )

            cur.execute(
                """
                INSERT INTO agents (name, email, password_hash, display_name,
                                    organization, avatar_gradient,
                                    authorization_scope, persona)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING *
                """,
                (
                    request.username, request.email, pwd_hash, display_name,
                    request.organization, avatar, "read-only", None,
                ),
            )
            row = cur.fetchone()
            token = create_access_token({"sub": str(row["id"]), "type": "agent"})
            logger.info(f"Agent registered: {row['id']} ({request.username})")
            return AuthResponse(token=token, user=_row_to_auth_user(row, "agent"))

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        logger.error(f"Register failed: {e}\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration failed: {e}",
        )


@router.post("/login", response_model=AuthResponse)
def login(request: LoginRequest):
    """统一登录：先在 owners 找匹配 email/username，再在 agents 找。"""
    if not request.email and not request.username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="email or username required",
        )

    identifier = request.email or request.username
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()

            # ---- owners ----
            cur.execute(
                "SELECT * FROM owners WHERE email = %s OR username = %s",
                (identifier, identifier),
            )
            row = cur.fetchone()
            if row:
                if not row.get("password_hash"):
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Account has no password set, please re-register",
                    )
                if not verify_password(request.password, row["password_hash"]):
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Invalid email or password",
                    )
                token = create_access_token({"sub": str(row["id"]), "type": "owner"})
                return AuthResponse(token=token, user=_row_to_auth_user(row, "owner"))

            # ---- agents ----
            cur.execute(
                "SELECT * FROM agents WHERE email = %s OR name = %s",
                (identifier, identifier),
            )
            row = cur.fetchone()
            if row and row.get("password_hash"):
                if not verify_password(request.password, row["password_hash"]):
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Invalid email or password",
                    )
                token = create_access_token({"sub": str(row["id"]), "type": "agent"})
                return AuthResponse(token=token, user=_row_to_auth_user(row, "agent"))

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed",
        )


@router.get("/me", response_model=AuthUser)
def me(authorization: Optional[str] = Header(None)):
    """根据 Authorization Bearer token 返回当前用户信息。"""
    user_id, user_type = get_current_user(authorization)
    with get_db_connection() as conn:
        cur = conn.cursor()
        if user_type == "owner":
            cur.execute("SELECT * FROM owners WHERE id = %s", (str(user_id),))
        else:
            cur.execute("SELECT * FROM agents WHERE id = %s", (str(user_id),))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="User not found")
        return _row_to_auth_user(row, user_type)


# ============ 兼容旧端点 ============

@router.post("/owner/register", response_model=OwnerRegisterResponse)
def register_owner(request: OwnerRegisterRequest):
    """[Legacy] 老的 owner 注册路径，保留以兼容已有调用方。"""
    try:
        pwd_hash = hash_password(request.password)
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT id FROM owners WHERE email = %s", (request.email,))
            if cur.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already registered",
                )
            cur.execute(
                """
                INSERT INTO owners (email, auth_provider, password_hash)
                VALUES (%s, %s, %s)
                RETURNING id
                """,
                (request.email, request.auth_provider, pwd_hash),
            )
            owner_id = cur.fetchone()['id']
            token = create_access_token({"sub": str(owner_id), "type": "owner"})
            return OwnerRegisterResponse(owner_id=owner_id, token=token)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Owner registration failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed",
        )


@router.post("/agents/register", response_model=AgentRegisterResponse)
def register_agent(
    request: AgentRegisterRequest,
    owner_id: UUID = Depends(get_current_owner),
):
    """[Legacy] owner 给自己创建一个 agent 子账号（保留以兼容）。"""
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT id FROM agents WHERE name = %s", (request.name,))
            if cur.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Agent name already taken",
                )
            token, token_hash = generate_agent_token()
            tools_json = request.tools if request.tools else []
            cur.execute(
                """
                INSERT INTO agents (
                    owner_id, name, persona, model_provider, model_name,
                    tools, authorization_scope, token_hash
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    str(owner_id), request.name, request.persona,
                    request.model_provider, request.model_name,
                    tools_json, request.authorization_scope, token_hash,
                ),
            )
            agent_id = cur.fetchone()['id']
            return AgentRegisterResponse(
                agent_id=agent_id, token=token, token_hash=token_hash,
            )
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        logger.error(f"Agent registration failed: {e}\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration failed: {e}",
        )
