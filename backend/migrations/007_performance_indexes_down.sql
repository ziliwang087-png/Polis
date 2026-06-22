-- 007_performance_indexes_down.sql
-- 回滚性能优化索引

DROP INDEX IF EXISTS idx_job_artifacts_job_id;
DROP INDEX IF EXISTS idx_job_ratings_job_id;
DROP INDEX IF EXISTS idx_job_events_job_id_created_at;
DROP INDEX IF EXISTS idx_post_likes_post_id_user_id;
DROP INDEX IF EXISTS idx_jobs_created_at_desc;
DROP INDEX IF EXISTS idx_posts_created_at_desc;
