"""
Pydantic models for request/response validation
"""
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID

# ============ Auth Models ============

class OwnerRegisterRequest(BaseModel):
    email: EmailStr
    password: str
    auth_provider: str = "email"

class OwnerRegisterResponse(BaseModel):
    owner_id: UUID
    token: str

class AgentRegisterRequest(BaseModel):
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

# ============ Task Models ============

class TaskCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: str
    category: str
    difficulty: Optional[str] = None
    required_capabilities: Optional[List[str]] = None
    estimated_hours: Optional[int] = None
    reward_points: int = Field(default=0, ge=0)
    deadline: Optional[datetime] = None
    deliverable_type: Optional[str] = None

class TaskCreateResponse(BaseModel):
    task_id: UUID

class TaskListResponse(BaseModel):
    id: UUID
    owner_id: UUID
    title: str
    description: str
    category: str
    difficulty: Optional[str]
    reward_points: int
    status: str
    created_at: datetime

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
