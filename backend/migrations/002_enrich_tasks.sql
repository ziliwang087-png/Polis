-- Polis v5.2 — Task Enrichment Migration
-- Created: 2026-06-20
-- 用途：扩展 tasks / owners / agents 表，让前端能展示完整社交风格信息
--
-- 边界：所有新增字段全部使用 ADD COLUMN IF NOT EXISTS，幂等。
--       不修改任何已有字段定义；不删除任何已有数据；不动其他 12 张表。

-- =========================================================
-- 1. tasks 表新增字段
-- =========================================================
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS view_count        INT          NOT NULL DEFAULT 0;
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS favorite_count    INT          NOT NULL DEFAULT 0;
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS comment_count     INT          NOT NULL DEFAULT 0;
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS application_count INT          NOT NULL DEFAULT 0;
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS skills_required   TEXT[];
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS cover_emoji       VARCHAR(8);
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS cover_gradient    VARCHAR(128);
-- deadline 字段已存在（001_initial_schema.sql 第 93 行），跳过
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS urgent            BOOLEAN      NOT NULL DEFAULT false;
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS featured          BOOLEAN      NOT NULL DEFAULT false;

-- 索引：前端常按 featured / urgent / created_at 筛选与排序
CREATE INDEX IF NOT EXISTS idx_tasks_featured ON tasks(featured) WHERE featured = true;
CREATE INDEX IF NOT EXISTS idx_tasks_urgent   ON tasks(urgent)   WHERE urgent   = true;

-- =========================================================
-- 2. application_count 自动维护 trigger
--   说明：task_applications 表 INSERT/DELETE 时同步 tasks.application_count
-- =========================================================
CREATE OR REPLACE FUNCTION sync_task_application_count() RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        UPDATE tasks SET application_count = application_count + 1 WHERE id = NEW.task_id;
        RETURN NEW;
    ELSIF TG_OP = 'DELETE' THEN
        UPDATE tasks SET application_count = GREATEST(application_count - 1, 0) WHERE id = OLD.task_id;
        RETURN OLD;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_sync_task_application_count ON task_applications;
CREATE TRIGGER trg_sync_task_application_count
AFTER INSERT OR DELETE ON task_applications
FOR EACH ROW EXECUTE FUNCTION sync_task_application_count();

-- =========================================================
-- 3. owners 表新增字段（task body 提到的 "users / agents"，本仓库是 owners）
-- =========================================================
ALTER TABLE owners ADD COLUMN IF NOT EXISTS display_name     VARCHAR(64);
ALTER TABLE owners ADD COLUMN IF NOT EXISTS organization     VARCHAR(128);
ALTER TABLE owners ADD COLUMN IF NOT EXISTS rating           NUMERIC(2,1) NOT NULL DEFAULT 5.0;
ALTER TABLE owners ADD COLUMN IF NOT EXISTS verified         BOOLEAN      NOT NULL DEFAULT false;
ALTER TABLE owners ADD COLUMN IF NOT EXISTS avatar_gradient  VARCHAR(128);

-- =========================================================
-- 4. agents 表新增字段（保持与 owners 一致，方便前端统一渲染发布者卡片）
-- =========================================================
ALTER TABLE agents ADD COLUMN IF NOT EXISTS display_name     VARCHAR(64);
ALTER TABLE agents ADD COLUMN IF NOT EXISTS organization     VARCHAR(128);
ALTER TABLE agents ADD COLUMN IF NOT EXISTS rating           NUMERIC(2,1) NOT NULL DEFAULT 5.0;
ALTER TABLE agents ADD COLUMN IF NOT EXISTS verified         BOOLEAN      NOT NULL DEFAULT false;
ALTER TABLE agents ADD COLUMN IF NOT EXISTS avatar_gradient  VARCHAR(128);
