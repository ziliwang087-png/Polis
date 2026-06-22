-- 007_performance_indexes.sql
-- 性能优化索引：消除 N+1 查询的外键索引

-- job_artifacts 表：job_id 外键索引
CREATE INDEX IF NOT EXISTS idx_job_artifacts_job_id ON job_artifacts(job_id);

-- job_ratings 表：job_id 外键索引
CREATE INDEX IF NOT EXISTS idx_job_ratings_job_id ON job_ratings(job_id);

-- job_events 表：job_id 外键索引 + 时间排序
CREATE INDEX IF NOT EXISTS idx_job_events_job_id_created_at ON job_events(job_id, created_at);

-- post_likes 表：post_id + user_id 组合索引（支持批量查询 liked_by_me）
CREATE INDEX IF NOT EXISTS idx_post_likes_post_id_user_id ON post_likes(post_id, user_id);

-- jobs 表：created_at 降序索引（支持 ORDER BY created_at DESC）
CREATE INDEX IF NOT EXISTS idx_jobs_created_at_desc ON jobs(created_at DESC);

-- posts 表：created_at 降序索引
CREATE INDEX IF NOT EXISTS idx_posts_created_at_desc ON posts(created_at DESC);
