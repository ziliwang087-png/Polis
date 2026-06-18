-- Polis v5.2 Initial Schema Rollback
-- Created: 2026-06-18

-- Drop tables in reverse order (respecting foreign key dependencies)
DROP TABLE IF EXISTS fraud_detection_logs CASCADE;
DROP TABLE IF EXISTS task_reviews CASCADE;
DROP TABLE IF EXISTS task_submissions CASCADE;
DROP TABLE IF EXISTS task_applications CASCADE;
DROP TABLE IF EXISTS tasks CASCADE;
DROP TABLE IF EXISTS audit_logs CASCADE;
DROP TABLE IF EXISTS reputation_events CASCADE;
DROP TABLE IF EXISTS agents CASCADE;
DROP TABLE IF EXISTS owners CASCADE;
