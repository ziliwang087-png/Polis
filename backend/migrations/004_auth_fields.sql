-- 004_auth_fields.sql
-- 给 owners / agents 加上"用户名 + 密码 + 展示信息"
-- 这是为了让前端走统一的 /auth/register + /auth/login 流程
-- 注意：本迁移只新增列，不修改既有列；可重复执行（IF NOT EXISTS）

BEGIN;

-- ============ owners ============
ALTER TABLE owners
  ADD COLUMN IF NOT EXISTS username      VARCHAR(64) UNIQUE,
  ADD COLUMN IF NOT EXISTS password_hash VARCHAR(128),
  ADD COLUMN IF NOT EXISTS display_name  VARCHAR(64),
  ADD COLUMN IF NOT EXISTS organization  VARCHAR(128),
  ADD COLUMN IF NOT EXISTS rating        NUMERIC(2,1) DEFAULT 5.0,
  ADD COLUMN IF NOT EXISTS verified      BOOLEAN DEFAULT false,
  ADD COLUMN IF NOT EXISTS avatar_gradient VARCHAR(128);

CREATE INDEX IF NOT EXISTS idx_owners_username ON owners(username);

-- ============ agents ============
-- agents 已有 name UNIQUE，复用为 username；只补 password 和 display 信息
ALTER TABLE agents
  ADD COLUMN IF NOT EXISTS email         VARCHAR(255) UNIQUE,
  ADD COLUMN IF NOT EXISTS password_hash VARCHAR(128),
  ADD COLUMN IF NOT EXISTS display_name  VARCHAR(64),
  ADD COLUMN IF NOT EXISTS organization  VARCHAR(128),
  ADD COLUMN IF NOT EXISTS rating        NUMERIC(2,1) DEFAULT 5.0,
  ADD COLUMN IF NOT EXISTS verified      BOOLEAN DEFAULT false,
  ADD COLUMN IF NOT EXISTS avatar_gradient VARCHAR(128);

-- agents.owner_id 当前是 NOT NULL，但走 self-register 路径时 agent 没有 owner
-- 改为可空（每个 self-registered agent 自动作为自己的"owner"代理）
ALTER TABLE agents ALTER COLUMN owner_id DROP NOT NULL;

-- agents.token_hash 当前是 NOT NULL；走 password 登录时不再用 agent_token，允许空
ALTER TABLE agents ALTER COLUMN token_hash DROP NOT NULL;

CREATE INDEX IF NOT EXISTS idx_agents_email ON agents(email);

COMMIT;
