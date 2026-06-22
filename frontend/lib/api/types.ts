/**
 * Polis v1 类型定义（手写占位）
 *
 * 注意：本文件等待后端 OpenAPI 出现后由 openapi-typescript 覆盖：
 *   npx openapi-typescript ../shared/openapi.json -o lib/api/types.ts
 *
 * 设计依据：POLIS_V1_PLAN.md §4 数据模型 + §7 API 契约。
 * 跟后端字段名 1:1 对齐，避免到时改一遍。
 */

/* ------------------------- User ------------------------- */

export interface User {
  id: string;
  email: string;
  username: string;
  display_name: string | null;
  avatar_url: string | null;
  reputation: number;
  credit_balance: number;
  created_at: string;
  updated_at: string;
}

/* ------------------------- Auth ------------------------- */

export interface RegisterPayload {
  email: string;
  password: string;
  username: string;
  display_name?: string;
}

export interface LoginPayload {
  email: string;
  password: string;
}

export interface AuthResponse {
  token: string;
  user: User;
}

/* ------------------------- Agent ------------------------- */

export type AgentStatus = 'online' | 'offline' | 'busy';
export type AgentAuthMethod = 'bearer' | 'hmac' | 'none';

/** A2A skill —— 跟 §4 agent_skills 表对齐 */
export interface AgentSkill {
  skill_id: string;
  name: string;
  description?: string | null;
  examples?: Array<Record<string, unknown>> | null;
  input_schema?: Record<string, unknown> | null;
  output_schema?: Record<string, unknown> | null;
}

/** A2A Agent Card —— 完整 JSON 也存在 agents.agent_card */
export interface AgentCard {
  name?: string;
  description?: string;
  url?: string;
  version?: string;
  capabilities?: Record<string, unknown> | string[];
  skills?: Array<AgentSkill | string>;
  [key: string]: unknown;
}

export interface Agent {
  id: string;
  owner_id: string;
  name: string;
  display_name: string | null;
  description: string | null;
  endpoint_url: string | null;
  websocket_id: string | null;
  auth_method: AgentAuthMethod;
  agent_card: AgentCard;
  status: AgentStatus;
  last_heartbeat_at: string | null;
  total_jobs: number;
  success_rate: number;
  avg_rating: number | null;
  level?: number | null;
  xp?: number | null;
  total_tasks_completed?: number | null;
  total_tasks_failed?: number | null;
  badge_count?: number | null;
  skills: AgentSkill[];
  created_at: string;
  updated_at: string;
}

export interface AgentCreatePayload {
  name: string;
  display_name: string;
  description: string;
  endpoint_url?: string | null;
  websocket_id?: string | null;
  auth_method: AgentAuthMethod;
  auth_config?: Record<string, unknown>;
  agent_card?: AgentCard;
  status?: AgentStatus;
  skills?: string[];
}

/* ------------------------- Job ------------------------- */

export type JobStatus =
  | 'submitted'
  | 'claimed'
  | 'working'
  | 'completed'
  | 'failed'
  | 'canceled';

/** A2A 标准 message —— 多模态分块 */
export interface JobMessage {
  role: 'user' | 'agent';
  parts: Array<
    | { kind: 'text'; text: string }
    | { kind: 'file'; mime_type: string; url: string; name?: string }
    | { kind: 'data'; data: unknown }
  >;
}

export interface JobAttachment {
  url: string;
  filename: string;
  mime: string;
}

export interface AttachmentInput {
  url?: string;
  filename: string;
  mime?: string;
  content_base64?: string;
}

export interface TaskAttachment {
  url: string;
  filename: string;
  mime: string;
}

export interface Job {
  id: string;
  from_user_id: string;
  to_agent_id: string | null;
  title: string;
  description: string;
  required_skill: string;
  input_messages: JobMessage[];
  attachments: JobAttachment[];
  status: JobStatus;
  progress: string | null;
  created_at: string;
  claimed_at: string | null;
  started_at: string | null;
  completed_at: string | null;

  // 后端 enrich 后可能附带的字段
  from_user?: Pick<User, 'id' | 'username' | 'display_name' | 'avatar_url'>;
  to_agent?: Pick<Agent, 'id' | 'name' | 'display_name'> | null;
}

export interface JobCreatePayload {
  title: string;
  description: string;
  required_skill: string;
  input_messages: JobMessage[];
  attachments?: JobAttachment[];
}

/* ------------------------- Artifact ------------------------- */

export type ArtifactType = 'text' | 'file' | 'json' | 'image';

export interface JobArtifact {
  id: string;
  job_id: string;
  type: ArtifactType;
  content: string | null;
  file_url: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
}

/* ------------------------- Rating ------------------------- */

export interface JobRating {
  id: string;
  job_id: string;
  rater_id: string;
  stars: number;
  feedback: string | null;
  created_at: string;
}

export interface JobRatePayload {
  stars: number;
  feedback?: string;
}

/* ------------------------- Event (SSE) ------------------------- */

export type JobEventType =
  | 'created'
  | 'claimed'
  | 'progress'
  | 'delivered'
  | 'rated'
  | 'canceled';

export interface JobEvent {
  id: string;
  job_id: string;
  event_type: JobEventType;
  payload: Record<string, unknown>;
  created_at: string;
}

/* ------------------------- 详情聚合返回 ------------------------- */

export interface JobDetail {
  job: Job;
  artifacts: JobArtifact[];
  rating: JobRating | null;
  events: JobEvent[];
}

/* ------------------------- Task (MVP) ------------------------- */

export type TaskStatus = 'open' | 'claimed' | 'in_progress' | 'submitted' | 'completed' | 'cancelled' | 'failed';

export interface Task {
  id: string;
  owner_id: string;
  title: string;
  description: string;
  category: string;
  difficulty: string | null;
  reward_points: number;
  status: TaskStatus;
  assigned_agent_id: string | null;
  created_at: string;
  updated_at: string | null;
  completed_at: string | null;
  deadline: string | null;
  estimated_hours: number | null;
  deliverable_type: string | null;
  required_capabilities: string[] | null;
  verification_required: boolean | null;
  view_count?: number;
  favorite_count?: number;
  comment_count?: number;
  application_count?: number;
  skills_required?: string[] | null;
  cover_emoji?: string | null;
  cover_gradient?: string | null;
  urgent?: boolean;
  featured?: boolean;
  owner_display_name?: string | null;
  owner_organization?: string | null;
  owner_rating?: number | null;
  owner_verified?: boolean | null;
  owner_avatar_gradient?: string | null;
  owner_email?: string | null;
  attachments: TaskAttachment[];
}

export interface TaskCreatePayload {
  title: string;
  description: string;
  category?: string;
  difficulty?: string;
  required_capabilities?: string[];
  estimated_hours?: number;
  reward_points?: number;
  budget?: number;
  deadline?: string;
  priority?: 'low' | 'normal' | 'urgent';
  deliverable_type?: string;
  attachments?: AttachmentInput[];
}

export interface TaskCreateResponse {
  task_id: string;
  id?: string;
  owner_id?: string;
  title?: string;
  description?: string;
  category?: string;
  difficulty?: string | null;
  reward_points?: number;
  status?: TaskStatus;
  assigned_agent_id?: string | null;
  created_at?: string;
  updated_at?: string | null;
  completed_at?: string | null;
  deadline?: string | null;
  estimated_hours?: number | null;
  deliverable_type?: string | null;
  required_capabilities?: string[] | null;
  verification_required?: boolean | null;
  attachments?: TaskAttachment[];
}

export interface TaskRating {
  id: string;
  task_id: string;
  user_id: string;
  agent_id: string;
  rating: number;
  comment: string | null;
  created_at: string;
}

export interface TaskDeliverable {
  id: string;
  task_id: string;
  uploaded_by: string;
  file_name: string;
  file_url: string;
  file_size: number;
  description: string | null;
  created_at: string;
}

/* ------------------------- Notification ------------------------- */

export type NotificationType = 'task_accepted' | 'task_completed' | 'task_failed' | 'task_rated' | 'level_up' | 'badge_earned';

export interface Notification {
  id: string;
  user_id: string;
  type: NotificationType;
  title: string;
  message: string;
  link: string | null;
  read: boolean;
  created_at: string;
}

/* ------------------------- Gamification ------------------------- */

export interface Badge {
  badge_type: string;
  earned_at: string;
}

export interface AgentStats {
  agent_id: string;
  name: string;
  level: number;
  xp: number;
  xp_to_next_level: number;
  total_tasks_completed: number;
  total_tasks_failed: number;
  success_rate: number;
  avg_rating: number | null;
  badges: Badge[];
  recent_ratings: Array<{
    rating: number;
    comment: string | null;
    created_at: string;
  }>;
}

export interface LeaderboardEntry {
  id: string;
  name: string;
  level: number;
  xp: number;
  total_tasks_completed: number;
  avg_rating: number | null;
  period_tasks: number;
  period_avg_rating: number | null;
  badge_count: number;
}

export interface Leaderboard {
  period: 'week' | 'month' | 'all';
  leaders: LeaderboardEntry[];
}

export type LeaderboardTab = 'xp' | 'agents' | 'tasks';

export interface UnifiedLeaderboardEntry {
  rank: number;
  id: string;
  owner_id: string | null;
  name: string;
  handle: string | null;
  metric_value: number;
  metric_label: string;
  level: number | null;
  badge_count: number;
  type: LeaderboardTab;
}

export interface LeaderboardResponse {
  type: LeaderboardTab;
  metric_label: string;
  leaders: UnifiedLeaderboardEntry[];
  current_user: UnifiedLeaderboardEntry | null;
}

/* ------------------------- Community ------------------------- */

export type CommunityCategory = 'chat' | 'showcase' | 'tech' | 'help';
export type CommunityAuthorType = 'user' | 'agent';

export interface CommunityPost {
  id: string;
  title: string;
  content: string;
  author_type: CommunityAuthorType;
  author_id: string;
  author_name: string | null;
  category: CommunityCategory;
  likes: number;
  comment_count: number;
  liked_by_me: boolean;
  created_at: string;
  updated_at: string | null;
}

export interface CommunityPostCreatePayload {
  title: string;
  content: string;
  category: CommunityCategory;
}

export interface CommunityPostCreateResponse {
  post_id: string;
}

export interface CommunityPostListResponse {
  posts: CommunityPost[];
  total: number;
}

export interface CommunityComment {
  id: string;
  post_id: string;
  author_type: CommunityAuthorType;
  author_id: string;
  author_name: string | null;
  content: string;
  created_at: string;
}

export interface CommunityCommentListResponse {
  comments: CommunityComment[];
}

export interface CommunityLikeResponse {
  liked: boolean;
  likes: number;
}
