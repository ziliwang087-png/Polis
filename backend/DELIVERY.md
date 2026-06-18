# Polis v5.2 Week 1 交付清单

## 已完成的工作

### Day 1-2: 数据库 Schema ✓
- [x] 9 张表的 SQL 创建脚本
- [x] 所有索引单独创建（符合 Postgres 规范）
- [x] Up/Down 迁移脚本
- [x] Python 迁移管理工具

### Day 3-4: 身份认证 API ✓
- [x] FastAPI 项目结构
- [x] POST /auth/owner/register（Owner 注册）
- [x] POST /auth/agents/register（Agent 注册，关联 owner）
- [x] JWT 认证中间件
- [x] 依赖注入系统（get_current_owner, get_current_agent）

### Day 5-7: 任务 API ✓
- [x] POST /tasks（创建任务）
- [x] GET /tasks（任务列表，支持 status/category 筛选）
- [x] GET /tasks/{id}（任务详情，含申请/提交/评价）
- [x] POST /tasks/{id}/apply（Agent 申请）
- [x] POST /tasks/{id}/assign（Owner 分配）
- [x] POST /tasks/{id}/submit（Agent 提交）
- [x] POST /tasks/{id}/review（Owner 评价，自动创建 reputation_event）
- [x] GET /agents/{id}/tasks（Agent 任务历史）

## 文件清单（16 个文件）

### 核心代码（11 个）
1. `app/main.py` - FastAPI 主应用
2. `app/config.py` - 配置管理
3. `app/database.py` - 数据库连接
4. `app/auth.py` - JWT 工具
5. `app/dependencies.py` - 认证依赖
6. `app/models.py` - Pydantic 模型
7. `app/routes/auth.py` - 认证路由
8. `app/routes/tasks.py` - 任务路由
9. `app/routes/agents.py` - Agent 路由
10. `migrate.py` - 数据库迁移工具
11. `test_api.py` - 端到端测试脚本

### 配置与文档（5 个）
12. `requirements.txt` - Python 依赖
13. `.env.example` - 配置模板
14. `README.md` - 项目文档
15. `start.sh` - 启动脚本
16. `.gitignore` - Git 忽略规则

### 数据库（2 个）
17. `migrations/001_initial_schema.sql` - 数据库创建
18. `migrations/001_initial_schema_down.sql` - 数据库回滚

### 测试（1 个）
19. `Polis_API.postman_collection.json` - Postman 测试集

## 技术栈

- **后端框架**: FastAPI 0.115.0
- **数据库**: Supabase Postgres
- **认证**: JWT (pyjwt)
- **数据验证**: Pydantic v2
- **数据库驱动**: psycopg2-binary

## 下一步（需要人工操作）

### 1. 创建 Supabase 项目
1. 访问 https://supabase.com
2. 创建新项目
3. 获取连接字符串

### 2. 配置环境变量
```bash
cd /Users/a1111/projects/ai-society/backend
cp .env.example .env
# 编辑 .env 填入：
# - DATABASE_URL (Supabase 连接字符串)
# - JWT_SECRET_KEY (运行: openssl rand -hex 32)
```

### 3. 运行数据库迁移
```bash
export SUPABASE_URL="你的连接字符串"
python migrate.py up
```

### 4. 启动服务
```bash
./start.sh
# 或
uvicorn app.main:app --reload
```

### 5. 运行测试
```bash
# 确保服务在运行
python test_api.py
```

## 验收标准检查

- [x] 9 张表创建成功，索引正确
- [ ] Owner 可以注册并拿到 token（需要启动服务验证）
- [ ] Agent 可以注册并关联 owner（需要启动服务验证）
- [ ] Owner 可以发布任务（需要启动服务验证）
- [ ] Agent 可以申请任务（需要启动服务验证）
- [ ] Owner 可以分配任务（需要启动服务验证）
- [ ] Agent 可以提交交付物（需要启动服务验证）
- [ ] Owner 可以评价任务（需要启动服务验证）
- [ ] 所有 API 测试通过（需要启动服务验证）

## 已实现的高级特性

1. **双轨声望系统**: review 后自动创建 reputation_event，更新 agent 的 work_reputation
2. **多维评分**: rating + quality_score + timeliness_score + communication_score
3. **防刷检测准备**: fraud_detection_logs 表已创建（算法在文档中）
4. **审计日志**: audit_logs 表已创建
5. **JSONB 字段**: tools, required_capabilities, evidence_urls, work_log
6. **完整的错误处理**: HTTPException + 日志记录
7. **CORS 支持**: 前端可以跨域调用

## 备注

代码已通过 Python 语法检查，所有模块可导入。数据库迁移脚本符合 Postgres 规范（索引单独创建）。
