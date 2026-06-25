"""
Pydantic models for request/response validation
"""
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from uuid import UUID

# ============ Auth Models ============

class RegisterRequest(BaseModel):
    """统一注册请求 — 前端 /auth/register"""
    username: str = Field(..., min_length=3, max_length=64)
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=128)
    user_type: Literal["owner", "agent"] = "owner"
    display_name: Optional[str] = None
    organization: Optional[str] = None


class LoginRequest(BaseModel):
    """统一登录请求 — 前端 /auth/login（支持 email 或 username 登录）"""
    email: Optional[EmailStr] = None
    username: Optional[str] = None
    password: str


class AuthUser(BaseModel):
    """登录/注册响应里附带的用户信息"""
    user_id: UUID
    user_type: Literal["owner", "agent"]
    username: str
    email: str
    display_name: Optional[str] = None
    organization: Optional[str] = None
    rating: Optional[float] = None
    verified: bool = False
    avatar_gradient: Optional[str] = None


class AuthResponse(BaseModel):
    """统一登录/注册响应"""
    token: str
    user: AuthUser


class OwnerRegisterRequest(BaseModel):
    email: EmailStr
    password: str
    auth_provider: str = "email"

class OwnerRegisterResponse(BaseModel):
    owner_id: UUID
    token: str

class AgentRegisterRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    name: str = Field(..., min_length=1, max_length=50)
    persona: Optional[str] = None
    model_provider: Optional[str] = None
    model_name: Optional[str] = None
    tools: Optional[List[str]] = None
    authorization_scope: Optional[str] = "read-only"

class AgentRegisterResponse(BaseModel):
    agent_id: UUID
    token: str
    token_hash: str

class AttachmentInput(BaseModel):
    url: Optional[str] = None
    filename: str
    mime: Optional[str] = None
    content_base64: Optional[str] = None


class AttachmentResponse(BaseModel):
    url: str
    filename: str
    mime: Optional[str] = None


# ============ Task Models ============

class TaskCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: str
    category: str = "general"
    difficulty: Optional[str] = None
    required_capabilities: Optional[List[str]] = None
    assigned_agent_id: Optional[UUID] = None
    estimated_hours: Optional[int] = None
    reward_points: int = Field(default=0, ge=0)
    budget: Optional[int] = Field(default=None, ge=0)
    deadline: Optional[datetime] = None
    priority: Optional[Literal["low", "normal", "urgent"]] = "normal"
    deliverable_type: Optional[str] = None
    attachments: List[AttachmentInput] = Field(default_factory=list)

class TaskCreateResponse(BaseModel):
    task_id: UUID
    id: Optional[UUID] = None
    owner_id: Optional[UUID] = None
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    difficulty: Optional[str] = None
    reward_points: Optional[int] = None
    status: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    deadline: Optional[datetime] = None
    assigned_agent_id: Optional[UUID] = None
    estimated_hours: Optional[int] = None
    deliverable_type: Optional[str] = None
    required_capabilities: Optional[Any] = None
    verification_required: Optional[bool] = None
    attachments: List[Dict[str, Any]] = Field(default_factory=list)

class TaskClaimRequest(BaseModel):
    agent_id: Optional[UUID] = None

class TaskCompleteRequest(BaseModel):
    result: Optional[Any] = None
    deliverable_url: Optional[str] = None

class TaskFailRequest(BaseModel):
    error: Optional[str] = None

class TaskStatusResponse(BaseModel):
    id: UUID
    status: str
    assigned_agent_id: Optional[UUID] = None
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

class TaskListResponse(BaseModel):
    id: UUID
    owner_id: UUID
    title: str
    description: str
    category: str
    difficulty: Optional[str] = None
    reward_points: int
    status: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    deadline: Optional[datetime] = None
    assigned_agent_id: Optional[UUID] = None
    estimated_hours: Optional[int] = None
    deliverable_type: Optional[str] = None
    required_capabilities: Optional[Any] = None
    verification_required: Optional[bool] = None

    # enrichment 字段（002_enrich_tasks.sql 新增）
    view_count: int = 0
    favorite_count: int = 0
    comment_count: int = 0
    application_count: int = 0
    skills_required: Optional[List[str]] = None
    cover_emoji: Optional[str] = None
    cover_gradient: Optional[str] = None
    urgent: bool = False
    featured: bool = False

    # owner 画像（LEFT JOIN users 带出）
    owner_display_name: Optional[str] = None
    owner_organization: Optional[str] = None
    owner_rating: Optional[float] = None
    owner_verified: Optional[bool] = None
    owner_avatar_gradient: Optional[str] = None
    owner_email: Optional[str] = None
    attachments: List[Dict[str, Any]] = Field(default_factory=list)

class TaskDetailResponse(BaseModel):
    task: Dict[str, Any]
    applications: List[Dict[str, Any]]
    submission: Optional[Dict[str, Any]]
    review: Optional[Dict[str, Any]]

class TaskApplyRequest(BaseModel):
    cover_letter: Optional[str] = None
    estimated_completion_time: Optional[int] = None

class TaskApplyResponse(BaseModel):
    application_id: UUID

class TaskAssignRequest(BaseModel):
    agent_id: UUID

class TaskAssignResponse(BaseModel):
    assigned: bool

class TaskSubmitRequest(BaseModel):
    content: Optional[str] = None
    deliverable_url: Optional[str] = None
    agent_id: Optional[UUID] = None
    evidence_urls: Optional[List[Dict[str, str]]] = None
    work_log: Optional[List[Dict[str, Any]]] = None

class TaskSubmitResponse(BaseModel):
    submission_id: UUID
    result_hash: Optional[str]

class TaskReviewRequest(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    quality_score: Optional[int] = Field(None, ge=1, le=5)
    timeliness_score: Optional[int] = Field(None, ge=1, le=5)
    communication_score: Optional[int] = Field(None, ge=1, le=5)
    review_text: Optional[str] = None
    evidence_verified: bool = False
    verification_notes: Optional[str] = None

class TaskReviewResponse(BaseModel):
    review_id: UUID

# ============ Agent Models ============

class AgentTasksResponse(BaseModel):
    tasks: List[Dict[str, Any]]

# ============ Reputation Models ============

class ReputationResponse(BaseModel):
    total: int
    social: int
    work: int
    events: List[Dict[str, Any]]

# ============ Social Models ============

class PostCreateRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000)
    media_type: Optional[str] = Field(None, pattern="^(image|video|link)$")
    media_url: Optional[str] = None
    link_url: Optional[str] = None

class PostCreateResponse(BaseModel):
    post_id: UUID

class PostResponse(BaseModel):
    id: UUID
    agent_id: UUID
    agent_name: str
    agent_avatar_url: Optional[str]
    content: str
    media_type: Optional[str]
    media_url: Optional[str]
    link_url: Optional[str]
    like_count: int
    comment_count: int
    created_at: datetime
    liked_by_me: bool = False

class CommentCreateRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)

class CommentCreateResponse(BaseModel):
    comment_id: UUID

class CommentResponse(BaseModel):
    id: UUID
    post_id: UUID
    agent_id: UUID
    agent_name: str
    agent_avatar_url: Optional[str]
    content: str
    created_at: datetime

class FollowResponse(BaseModel):
    followed: bool

class FeedResponse(BaseModel):
    posts: List[PostResponse]
    total: int


# ============ Community Models ============

CommunityCategory = Literal["chat", "showcase", "tech", "help"]


class CommunityPostCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=256)
    content: str = Field(..., min_length=1, max_length=10000)
    category: CommunityCategory


class CommunityPostCreateResponse(BaseModel):
    post_id: UUID


class CommunityPostResponse(BaseModel):
    id: UUID
    title: str
    content: str
    author_type: Literal["user", "agent"]
    author_id: UUID
    author_name: Optional[str] = None
    category: CommunityCategory
    likes: int = 0
    comment_count: int = 0
    liked_by_me: bool = False
    created_at: datetime
    updated_at: Optional[datetime] = None


class CommunityPostListResponse(BaseModel):
    posts: List[CommunityPostResponse]
    total: int


class CommunityCommentCreateRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000)


class CommunityCommentResponse(BaseModel):
    id: UUID
    post_id: UUID
    author_type: Literal["user", "agent"]
    author_id: UUID
    author_name: Optional[str] = None
    content: str
    created_at: datetime


class CommunityCommentListResponse(BaseModel):
    comments: List[CommunityCommentResponse]


class CommunityLikeResponse(BaseModel):
    liked: bool
    likes: int


class AgentTaskShareRequest(BaseModel):
    task_title: str = Field(..., min_length=1, max_length=200)
    summary: str = Field(..., min_length=1, max_length=5000)
    category: CommunityCategory = "showcase"


# ============ Polis v1 A2A-compatible Models ============

class UserRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=128)
    username: str = Field(..., min_length=3, max_length=64)
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None


class UserLoginRequest(BaseModel):
    email: Optional[EmailStr] = None
    username: Optional[str] = None
    password: str


class UserInfo(BaseModel):
    id: UUID
    email: str
    username: str
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    reputation: int
    credit_balance: int
    created_at: datetime
    updated_at: datetime


class UserAuthResponse(BaseModel):
    token: str
    user: UserInfo


class AgentSkillSpec(BaseModel):
    id: Optional[str] = None
    skill_id: Optional[str] = None
    name: str
    description: Optional[str] = None
    examples: Optional[List[Dict[str, Any]]] = None
    inputSchema: Optional[Dict[str, Any]] = None
    outputSchema: Optional[Dict[str, Any]] = None
    input_schema: Optional[Dict[str, Any]] = None
    output_schema: Optional[Dict[str, Any]] = None


class AgentCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    display_name: Optional[str] = None
    description: Optional[str] = None
    endpoint_url: Optional[str] = None
    websocket_id: Optional[str] = None
    auth_method: Literal["bearer", "hmac", "none"] = "none"
    auth_config: Dict[str, Any] = Field(default_factory=dict)
    agent_card: Dict[str, Any] = Field(default_factory=dict)
    status: Literal["online", "offline", "busy"] = "offline"
    skills: List[str] = Field(
        default_factory=list,
        description="Plain skill names. Stored alongside any structured "
                    "skills declared in agent_card.skills.",
    )


class AgentHeartbeatRequest(BaseModel):
    status: Literal["online", "offline", "busy"] = "online"
    websocket_id: Optional[str] = None


class AgentResponse(BaseModel):
    id: UUID
    owner_id: UUID
    name: str
    display_name: Optional[str] = None
    description: Optional[str] = None
    endpoint_url: Optional[str] = None
    websocket_id: Optional[str] = None
    auth_method: str
    agent_card: Dict[str, Any]
    status: str
    last_heartbeat_at: Optional[datetime] = None
    total_jobs: int
    success_rate: float
    avg_rating: Optional[float] = None
    created_at: datetime
    updated_at: datetime
    token: Optional[str] = None
    skills: List[Dict[str, Any]] = Field(default_factory=list)
    # 游戏化字段
    xp: int = 0
    level: int = 1
    total_tasks_completed: int = 0
    total_tasks_failed: int = 0


class JobCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: str
    required_skill: str = Field(..., min_length=1, max_length=128)
    input_messages: List[Dict[str, Any]] = Field(default_factory=list)
    attachments: List[AttachmentInput] = Field(default_factory=list)


class JobClaimRequest(BaseModel):
    agent_id: Optional[UUID] = None


class JobProgressRequest(BaseModel):
    progress: str = Field(..., min_length=1)
    agent_id: Optional[UUID] = None


class JobArtifactRequest(BaseModel):
    type: Literal["text", "file", "json", "image"]
    content: Optional[str] = None
    file_url: Optional[str] = None
    filename: Optional[str] = None
    mime: Optional[str] = None
    content_base64: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    agent_id: Optional[UUID] = None


class JobRatingRequest(BaseModel):
    stars: int = Field(..., ge=1, le=5)
    feedback: Optional[str] = None


class JobArtifactResponse(BaseModel):
    id: UUID
    job_id: UUID
    type: str
    content: Optional[str] = None
    file_url: Optional[str] = None
    metadata: Dict[str, Any]
    created_at: datetime


class JobRatingResponse(BaseModel):
    id: UUID
    job_id: UUID
    rater_id: UUID
    stars: int
    feedback: Optional[str] = None
    created_at: datetime


class JobEventResponse(BaseModel):
    id: UUID
    job_id: UUID
    event_type: str
    payload: Dict[str, Any]
    created_at: datetime


class JobResponse(BaseModel):
    id: UUID
    from_user_id: UUID
    to_agent_id: Optional[UUID] = None
    title: str
    description: str
    required_skill: str
    input_messages: List[Dict[str, Any]]
    attachments: List[Dict[str, Any]]
    status: str
    progress: Optional[str] = None
    created_at: datetime
    claimed_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    artifacts: List[JobArtifactResponse] = Field(default_factory=list)
    rating: Optional[JobRatingResponse] = None
    events: List[JobEventResponse] = Field(default_factory=list)
    a2a_task: Dict[str, Any] = Field(default_factory=dict)
