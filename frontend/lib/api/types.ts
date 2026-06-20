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
  agent_card: AgentCard;
  status?: AgentStatus;
  skills: string[];
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
