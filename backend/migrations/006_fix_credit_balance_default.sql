-- 006_fix_credit_balance_default.sql
-- 修复 users 表的 credit_balance 默认值从 10 改为 0

BEGIN;

-- 修改 credit_balance 列的默认值为 0
ALTER TABLE users ALTER COLUMN credit_balance SET DEFAULT 0;

COMMIT;
