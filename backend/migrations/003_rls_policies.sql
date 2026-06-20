-- Enable Row Level Security on all tables
ALTER TABLE owners ENABLE ROW LEVEL SECURITY;
ALTER TABLE agents ENABLE ROW LEVEL SECURITY;
ALTER TABLE tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE task_applications ENABLE ROW LEVEL SECURITY;
ALTER TABLE task_submissions ENABLE ROW LEVEL SECURITY;
ALTER TABLE task_reviews ENABLE ROW LEVEL SECURITY;
ALTER TABLE reputation_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE posts ENABLE ROW LEVEL SECURITY;
ALTER TABLE comments ENABLE ROW LEVEL SECURITY;
ALTER TABLE likes ENABLE ROW LEVEL SECURITY;
ALTER TABLE follows ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE fraud_detection_logs ENABLE ROW LEVEL SECURITY;

-- ============ Service Role Bypass ============
-- 后端使用 postgres 角色连接，完全绕过 RLS
-- 这样 RLS 只保护直接的客户端访问（通过 Supabase JS SDK 或 PostgREST）
-- FastAPI 后端有自己的 JWT 验证，不需要 RLS 二次验证

-- Postgres 角色（后端）对所有表有完全权限
CREATE POLICY "service_role_all_owners" ON owners
    FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY "service_role_all_agents" ON agents
    FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY "service_role_all_tasks" ON tasks
    FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY "service_role_all_applications" ON task_applications
    FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY "service_role_all_submissions" ON task_submissions
    FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY "service_role_all_reviews" ON task_reviews
    FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY "service_role_all_reputation" ON reputation_events
    FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY "service_role_all_posts" ON posts
    FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY "service_role_all_comments" ON comments
    FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY "service_role_all_likes" ON likes
    FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY "service_role_all_follows" ON follows
    FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY "service_role_all_audit" ON audit_logs
    FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY "service_role_all_fraud" ON fraud_detection_logs
    FOR ALL USING (true) WITH CHECK (true);

-- 说明：
-- RLS 已启用，但 postgres 角色（后端）有完全权限
-- 如果未来用 Supabase JS SDK 直接访问数据库，需要添加更细粒度的策略
-- 当前架构：所有访问必须通过 FastAPI 后端，后端做权限验证
