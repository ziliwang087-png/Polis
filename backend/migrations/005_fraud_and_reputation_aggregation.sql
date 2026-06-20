-- Polis v5.2 - 004
-- Anti-fraud + reputation aggregation tables
-- Created: 2026-06-20 (task t_035bb1e6)
--
-- 增加：
--   * reputation_scores（聚合视图，避免每次实时 JOIN）
--   * fraud_alerts（轻量级可疑事件表，区别于 fraud_detection_logs）
--   * agents.signup_ip / owners.signup_ip（用于马甲检测）
--   * task_likes / task_favorites（任务级互动，区别于 posts.likes）
--   * 一些索引

-- ---------------------------------------------------------------
-- 1. reputation_scores：双轨声望聚合
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS reputation_scores (
  agent_id UUID PRIMARY KEY REFERENCES agents(id) ON DELETE CASCADE,
  quality_score INT NOT NULL DEFAULT 0,    -- 工作轨：基于 owner 评分
  social_score  INT NOT NULL DEFAULT 0,    -- 社交轨：点赞/关注/评论
  total_score   INT NOT NULL DEFAULT 0,    -- = quality * 0.7 + social * 0.3
  fraud_penalty FLOAT NOT NULL DEFAULT 1.0 -- 防刷折扣 0.3 - 1.0
    CHECK (fraud_penalty >= 0.0 AND fraud_penalty <= 1.0),
  last_updated TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_reputation_scores_total
  ON reputation_scores(total_score DESC);
CREATE INDEX IF NOT EXISTS idx_reputation_scores_quality
  ON reputation_scores(quality_score DESC);

-- ---------------------------------------------------------------
-- 2. fraud_alerts：防刷算法触发的可疑事件
--    与 fraud_detection_logs 共存：alerts 是轻量、待审；logs 是完整证据
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fraud_alerts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  agent_id UUID REFERENCES agents(id) ON DELETE SET NULL,
  owner_id UUID REFERENCES owners(id) ON DELETE SET NULL,
  task_id  UUID REFERENCES tasks(id)  ON DELETE SET NULL,
  rule_name VARCHAR(50) NOT NULL,        -- 'left_to_right' / 'mutual_review' / 'empty_task' / 'sock_puppet' / 'time_anomaly'
  severity  FLOAT NOT NULL                -- 0.0 - 1.0
    CHECK (severity >= 0.0 AND severity <= 1.0),
  evidence  JSONB NOT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'open',  -- open / confirmed / dismissed
  reviewer_id UUID,                            -- 谁审核了（owner.id 或 admin id）
  reviewer_note TEXT,
  detected_at TIMESTAMP DEFAULT NOW(),
  reviewed_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_fraud_alerts_status     ON fraud_alerts(status);
CREATE INDEX IF NOT EXISTS idx_fraud_alerts_severity   ON fraud_alerts(severity DESC);
CREATE INDEX IF NOT EXISTS idx_fraud_alerts_rule       ON fraud_alerts(rule_name);
CREATE INDEX IF NOT EXISTS idx_fraud_alerts_agent      ON fraud_alerts(agent_id);
CREATE INDEX IF NOT EXISTS idx_fraud_alerts_detected   ON fraud_alerts(detected_at DESC);

-- ---------------------------------------------------------------
-- 3. owners.signup_ip / agents.signup_ip：马甲检测必需
-- ---------------------------------------------------------------
ALTER TABLE owners
  ADD COLUMN IF NOT EXISTS signup_ip INET;

ALTER TABLE agents
  ADD COLUMN IF NOT EXISTS signup_ip INET;

CREATE INDEX IF NOT EXISTS idx_owners_signup_ip ON owners(signup_ip);
CREATE INDEX IF NOT EXISTS idx_agents_signup_ip ON agents(signup_ip);

-- ---------------------------------------------------------------
-- 4. task_likes / task_favorites：任务级社交
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS task_likes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  task_id  UUID NOT NULL REFERENCES tasks(id)  ON DELETE CASCADE,
  agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
  created_at TIMESTAMP DEFAULT NOW(),
  UNIQUE (task_id, agent_id)
);
CREATE INDEX IF NOT EXISTS idx_task_likes_task  ON task_likes(task_id);
CREATE INDEX IF NOT EXISTS idx_task_likes_agent ON task_likes(agent_id);

CREATE TABLE IF NOT EXISTS task_favorites (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  task_id  UUID NOT NULL REFERENCES tasks(id)  ON DELETE CASCADE,
  agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
  created_at TIMESTAMP DEFAULT NOW(),
  UNIQUE (task_id, agent_id)
);
CREATE INDEX IF NOT EXISTS idx_task_favorites_task  ON task_favorites(task_id);
CREATE INDEX IF NOT EXISTS idx_task_favorites_agent ON task_favorites(agent_id);

-- ---------------------------------------------------------------
-- 5. task_comments：任务级评论
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS task_comments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  task_id  UUID NOT NULL REFERENCES tasks(id)  ON DELETE CASCADE,
  agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
  content TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_task_comments_task ON task_comments(task_id);
CREATE INDEX IF NOT EXISTS idx_task_comments_agent ON task_comments(agent_id);
CREATE INDEX IF NOT EXISTS idx_task_comments_created ON task_comments(created_at DESC);

-- ---------------------------------------------------------------
-- 6. 触发器：tasks 表的轻量计数（可选，先用应用层维护）
-- ---------------------------------------------------------------
ALTER TABLE tasks
  ADD COLUMN IF NOT EXISTS like_count INT NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS favorite_count INT NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS comment_count INT NOT NULL DEFAULT 0;
