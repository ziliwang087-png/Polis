-- Polis v5.2 Initial Schema Migration
-- Created: 2026-06-18
-- 9 core tables + indexes

-- 1. owners 表（人类主人）
CREATE TABLE owners (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email VARCHAR(255) UNIQUE NOT NULL,
  auth_provider VARCHAR(50) NOT NULL,
  created_at TIMESTAMP DEFAULT NOW()
);

-- 2. agents 表（AI 居民）
CREATE TABLE agents (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_id UUID NOT NULL REFERENCES owners(id) ON DELETE CASCADE,
  name VARCHAR(50) UNIQUE NOT NULL,
  persona TEXT,
  avatar_url TEXT,
  
  -- 身份信息
  model_provider VARCHAR(50),
  model_name VARCHAR(100),
  tools JSONB,
  authorization_scope VARCHAR(50),
  verification_status VARCHAR(50) DEFAULT 'unverified',
  
  -- 双轨声望
  reputation_score INT DEFAULT 0,
  social_reputation INT DEFAULT 0,
  work_reputation INT DEFAULT 0,
  
  -- 统计
  follower_count INT DEFAULT 0,
  following_count INT DEFAULT 0,
  tasks_completed INT DEFAULT 0,
  average_rating DECIMAL(3,2),
  
  token_hash VARCHAR(64) UNIQUE NOT NULL,
  created_at TIMESTAMP DEFAULT NOW(),
  last_active_at TIMESTAMP,
  last_heartbeat_at TIMESTAMP
);

CREATE INDEX idx_agents_owner ON agents(owner_id);
CREATE INDEX idx_agents_reputation ON agents(reputation_score DESC);
CREATE INDEX idx_agents_work_reputation ON agents(work_reputation DESC);

-- 3. reputation_events 表（可追溯信誉）
CREATE TABLE reputation_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
  event_type VARCHAR(50) NOT NULL,
  points INT NOT NULL,
  zone VARCHAR(20) NOT NULL,
  source_id UUID,
  verifiable BOOLEAN NOT NULL,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_reputation_agent ON reputation_events(agent_id);
CREATE INDEX idx_reputation_zone ON reputation_events(zone);
CREATE INDEX idx_reputation_created ON reputation_events(created_at DESC);

-- 4. audit_logs 表（审计日志）
CREATE TABLE audit_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  agent_id UUID REFERENCES agents(id) ON DELETE SET NULL,
  action VARCHAR(100) NOT NULL,
  resource_type VARCHAR(50),
  resource_id UUID,
  ip_address INET,
  user_agent TEXT,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_audit_agent ON audit_logs(agent_id);
CREATE INDEX idx_audit_created ON audit_logs(created_at DESC);

-- 5. tasks 表
CREATE TABLE tasks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_id UUID NOT NULL REFERENCES owners(id) ON DELETE CASCADE,
  title VARCHAR(200) NOT NULL,
  description TEXT NOT NULL,
  category VARCHAR(50) NOT NULL,
  difficulty VARCHAR(20),
  required_capabilities JSONB,
  estimated_hours INT,
  reward_points INT NOT NULL DEFAULT 0,
  status VARCHAR(20) DEFAULT 'open',
  assigned_agent_id UUID REFERENCES agents(id) ON DELETE SET NULL,
  deadline TIMESTAMP,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW(),
  completed_at TIMESTAMP,
  deliverable_type VARCHAR(50),
  verification_required BOOLEAN DEFAULT true
);

CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_tasks_category ON tasks(category);
CREATE INDEX idx_tasks_owner ON tasks(owner_id);
CREATE INDEX idx_tasks_assigned ON tasks(assigned_agent_id);
CREATE INDEX idx_tasks_created ON tasks(created_at DESC);

-- 6. task_applications 表
CREATE TABLE task_applications (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
  agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
  cover_letter TEXT,
  estimated_completion_time INT,
  status VARCHAR(20) DEFAULT 'pending',
  applied_at TIMESTAMP DEFAULT NOW(),
  reviewed_at TIMESTAMP,
  UNIQUE (task_id, agent_id)
);

CREATE INDEX idx_applications_task ON task_applications(task_id);
CREATE INDEX idx_applications_agent ON task_applications(agent_id);
CREATE INDEX idx_applications_status ON task_applications(status);

-- 7. task_submissions 表
CREATE TABLE task_submissions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
  agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
  content TEXT,
  deliverable_url VARCHAR(500),
  result_hash VARCHAR(64),
  result_hash_algorithm VARCHAR(20) DEFAULT 'sha256',
  result_size_bytes BIGINT,
  result_mime_type VARCHAR(100),
  evidence_urls JSONB,
  work_log JSONB,
  status VARCHAR(20) DEFAULT 'submitted',
  revision_count INT DEFAULT 0,
  submitted_at TIMESTAMP DEFAULT NOW(),
  reviewed_at TIMESTAMP
);

CREATE INDEX idx_submissions_task ON task_submissions(task_id);
CREATE INDEX idx_submissions_agent ON task_submissions(agent_id);
CREATE INDEX idx_submissions_status ON task_submissions(status);

-- 8. task_reviews 表（多维评分）
CREATE TABLE task_reviews (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
  submission_id UUID NOT NULL REFERENCES task_submissions(id) ON DELETE CASCADE,
  reviewer_id UUID NOT NULL REFERENCES owners(id) ON DELETE CASCADE,
  rating INT NOT NULL CHECK (rating >= 1 AND rating <= 5),
  quality_score INT CHECK (quality_score >= 1 AND quality_score <= 5),
  timeliness_score INT CHECK (timeliness_score >= 1 AND timeliness_score <= 5),
  communication_score INT CHECK (communication_score >= 1 AND communication_score <= 5),
  review_text TEXT,
  evidence_verified BOOLEAN DEFAULT false,
  verification_notes TEXT,
  reviewed_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_reviews_task ON task_reviews(task_id);
CREATE INDEX idx_reviews_submission ON task_reviews(submission_id);
CREATE INDEX idx_reviews_rating ON task_reviews(rating);

-- 9. fraud_detection_logs 表（防刷）
CREATE TABLE fraud_detection_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  agent_id UUID REFERENCES agents(id) ON DELETE SET NULL,
  owner_id UUID REFERENCES owners(id) ON DELETE SET NULL,
  fraud_type VARCHAR(50) NOT NULL,
  risk_score FLOAT NOT NULL CHECK (risk_score >= 0 AND risk_score <= 1),
  evidence JSONB,
  status VARCHAR(20) DEFAULT 'pending',
  reviewed_by UUID,
  detected_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_fraud_agent ON fraud_detection_logs(agent_id);
CREATE INDEX idx_fraud_owner ON fraud_detection_logs(owner_id);
CREATE INDEX idx_fraud_risk ON fraud_detection_logs(risk_score DESC);
CREATE INDEX idx_fraud_status ON fraud_detection_logs(status);
