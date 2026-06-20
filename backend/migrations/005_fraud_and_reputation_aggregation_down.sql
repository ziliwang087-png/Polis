-- Polis v5.2 - 004 down
-- Reverse anti-fraud + reputation aggregation tables

DROP TABLE IF EXISTS task_comments  CASCADE;
DROP TABLE IF EXISTS task_favorites CASCADE;
DROP TABLE IF EXISTS task_likes     CASCADE;
DROP TABLE IF EXISTS fraud_alerts   CASCADE;
DROP TABLE IF EXISTS reputation_scores CASCADE;

ALTER TABLE owners DROP COLUMN IF EXISTS signup_ip;
ALTER TABLE agents DROP COLUMN IF EXISTS signup_ip;

ALTER TABLE tasks
  DROP COLUMN IF EXISTS like_count,
  DROP COLUMN IF EXISTS favorite_count,
  DROP COLUMN IF EXISTS comment_count;
