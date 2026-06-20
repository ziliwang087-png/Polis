# Polis v1 重写计划书

> 编写时间：2026-06-20 19:26 AEST
> 项目位置：`/Users/a1111/projects/ai-society/`
> 决策依据：今晚跟用户从 Owner→Agent 模型 → AI 评审团 → 最终敲定 A2A 协议 + 产品壳 的全过程复盘

---

## 1. 一句话定位

**Polis = 中文世界面向 AI 工程师的 A2A 协议任务网站。**

- 用户挂自己的 agent（Hermes / Lobster / Cursor / 自建）到平台
- 别人发任务 → 自己 agent 接 → 干完返回结果
- 协议层 100% 兼容 A2A（Google + Linux 基金会标准）
- 产品壳：中文 web UI、任务广场、信誉系统

---

## 2. 为什么是这个方向（5 步复盘）

| 检查项 | 结果 |
|---|---|
| 1. 痛点真假 | ✅ AI 工程师有自带 agent，想互调；普通人想发任务给别人 agent |
| 2. 有人做了吗 | ✅ 国外有 a2aregistry.org（开发者向）；**国内零产品** |
| 3. 有现成基建吗 | ✅ A2A 协议（Google + Linux Foundation） + ~3700 个现成 agent |
| 4. 差异化 | ✅ 中文化 + 普通人能用的 web UI（A2A registry 是开发者工具） |
| 5. 分阶段 | ✅ v1 闭门给 AI 工程师 → v2 开放发任务 → v3 平台代管 |

**砍掉的方向**（防止反复）：
- ❌ AI 评审团（普通 LLM 能做、伪需求）
- ❌ Owner 雇佣 Agent 模型（=Upwork+AI、没差异化）
- ❌ 多 agent 互相聊天功能（产品定位杂质）
- ❌ 自建协议（A2A 已经是事实标准，造轮子=送命）

---

## 3. v1 范围（2 周内出 demo）

### 必须做（MVP）
1. 用户注册 / 登录
2. 注册 agent（按 A2A Agent Card 标准）
3. 发任务（任务表单 + 附件上传）
4. 任务广播 + agent 抢单
5. agent 提交结果（标准 Artifact 格式）
6. owner 查看结果 + 下载 + 评分
7. 我的 dashboard（我发的 / 我接的 / 我的 agent）

### 必须砍（v1 不做）
- ❌ 钱、积分、收益
- ❌ 社交：关注、动态、点赞、评论
- ❌ 任务申请审批流（先来先得就行）
- ❌ 智能匹配 / 推荐算法（按 capability 标签筛就行）
- ❌ MCP 兼容（v2 加）
- ❌ 普通用户发任务（v1 必须挂 agent 才能用）

### v2 - v3 路线（远景）
- v2：开放给普通用户发任务，AI 工程师 agent 接（双边市场）
- v3：平台代管 agent（用户填 prompt + API key，平台调 LLM 替他跑）
- v4：MCP 兼容、企业级、agent 协作复杂工作流

---

## 4. 数据模型（A2A 兼容）

```sql
-- 用户表
users (
  id uuid pk,
  email, password_hash, username,
  display_name, avatar_url,
  reputation int default 0,        -- 信用分（不是钱）
  credit_balance int default 10,   -- 互助余额（发任务-1，接任务+1）
  created_at, updated_at
)

-- Agent 表（一个 user 可挂多个 agent）
-- 完全对齐 A2A Agent Card 规范
agents (
  id uuid pk,
  owner_id uuid -> users,
  name varchar,                    -- "alice-translator"
  display_name varchar,            -- "Alice 的翻译助手"
  description text,
  endpoint_url text,               -- 用户自己的 webhook（A 路径）
  websocket_id varchar,            -- 长连接 session（C 路径）
  auth_method enum,                -- bearer | hmac | none
  auth_config jsonb,               -- 加密存储凭证
  agent_card jsonb,                -- 完整 A2A Agent Card JSON
  status enum,                     -- online | offline | busy
  last_heartbeat_at timestamp,
  total_jobs int,
  success_rate float,
  avg_rating float,
  created_at, updated_at
)

-- 能力（A2A skill）
agent_skills (
  id uuid pk,
  agent_id uuid -> agents,
  skill_id varchar,                -- "translate-zh-en" / "code-review"
  name varchar,
  description text,
  examples jsonb,                  -- 示范输入输出
  input_schema jsonb,
  output_schema jsonb
)

-- 任务（A2A Task 对象）
jobs (
  id uuid pk,
  from_user_id uuid -> users,      -- 发任务方
  to_agent_id uuid -> agents,      -- 接任务方（接单后填）
  title varchar,
  description text,
  required_skill varchar,          -- 需要哪个 capability
  input_messages jsonb,            -- A2A messages 格式
  attachments jsonb,               -- [{url, filename, mime}]
  status enum,                     -- submitted|claimed|working|completed|failed|canceled
  progress text,                   -- agent 主动更新的进度文本
  created_at, claimed_at, started_at, completed_at
)

-- 交付物（A2A Artifact）
job_artifacts (
  id uuid pk,
  job_id uuid -> jobs,
  type enum,                       -- text|file|json|image
  content text,                    -- 文本/JSON 直接存
  file_url text,                   -- 文件存 Supabase Storage
  metadata jsonb,
  created_at
)

-- 评分
job_ratings (
  id uuid pk,
  job_id uuid -> jobs unique,
  rater_id uuid -> users,
  stars int,                       -- 1-5
  feedback text,
  created_at
)

-- 任务事件流（审计 + SSE 推送）
job_events (
  id uuid pk,
  job_id uuid -> jobs,
  event_type enum,                 -- created|claimed|progress|delivered|rated|canceled
  payload jsonb,
  created_at
)
```

**砍掉的旧表**（一律删）：
- task_social（点赞收藏评论）
- agent_follows（关注关系）
- feed_items（动态流）
- 任何 task_* 加了奇怪后缀的表

---

## 5. 三个并行任务（派给 sibling agents）

### 🔴 任务 A：后端 + A2A 协议实现 → **派给 codex**
**workdir**: `/Users/a1111/projects/ai-society/backend`
**预计**: 4-6 小时
**deliverable**: 跑得通的 FastAPI 服务，能让 Polis 网络作为标准 A2A 节点工作

详见 §6.A 子任务清单。

---

### 🟢 任务 B：前端 Web UI → **派给 claude-code**
**workdir**: `/Users/a1111/projects/ai-society/frontend`
**预计**: 4-6 小时
**deliverable**: Next.js 网页，5 个核心页面跑通端到端

详见 §6.B 子任务清单。

---

### 🟡 任务 C：polis-cli + 接入 SDK → **派给 opencode 或 lobster**
**workdir**: `/Users/a1111/projects/ai-society/polis-cli`（新建）
**预计**: 2-3 小时
**deliverable**: `pip install polis` 一行命令，让 Hermes/Lobster 用户挂自己的 agent

详见 §6.C 子任务清单。

---

## 6. 三份子任务详细规格

### 6.A 后端任务 → codex

#### 范围
1. **清空旧数据库**：删掉所有 task_*、agent_follows、feed_* 表
2. **建新 schema**：按 §4 创建新表，写 Alembic migration
3. **A2A 协议实现**：
   - `GET /.well-known/agent.json` —— Polis 作为元 agent 的 card
   - `POST /api/v1/jobs` —— 创建任务
   - `GET /api/v1/jobs/{id}` —— 查任务
   - `POST /api/v1/jobs/{id}/claim` —— agent 抢单
   - `POST /api/v1/jobs/{id}/artifacts` —— agent 提交结果
   - `POST /api/v1/jobs/{id}/progress` —— agent 推进度（SSE）
   - `GET /api/v1/jobs/{id}/events` —— SSE 流
   - `POST /api/v1/jobs/{id}/rate` —— 评分
4. **Agent 注册接口**：
   - `POST /api/v1/agents` —— 注册（含 Agent Card）
   - `POST /api/v1/agents/{id}/heartbeat` —— 心跳
   - `GET /api/v1/agents` —— 列出 agent
5. **任务广播**：用 PostgreSQL LISTEN/NOTIFY 或 Redis pub/sub，新任务推给所有 online agent
6. **抢单防并发**：用数据库 row lock 或乐观锁，避免两个 agent 抢到同一任务
7. **附件存储**：用 Supabase Storage（已配过），新建 bucket `polis-attachments`
8. **测试**：pytest 单元测试 + 端到端 happy path

#### 验收标准
- `pytest backend/tests/` 全绿
- curl 能完整跑通：创建用户 → 注册 agent → 发任务 → 抢单 → 提交结果 → 查看结果
- A2A 协议合规：能用官方 a2a-cli 或 a2aregistry 验证器跑通

#### 跟前端的接口契约
- 见 §7 API spec

---

### 6.B 前端任务 → claude-code

#### 范围
基于现有 Next.js 项目，**重写**所有页面（不是改）：

1. **删除旧页面/组件**：
   - 整个 task 详情那套（cover_emoji、social 互动）
   - 任何含 social 字眼的组件
2. **新建页面**：
   - `/` —— 任务广场（按 capability 筛选 + 任务卡片列表）
   - `/jobs/new` —— 发任务（title + description + 选 capability + 上传附件 + 期望输出格式）
   - `/jobs/[id]` —— 任务详情（状态时间线 + 抢单按钮 / 结果展示 + 评分）
   - `/agents` —— 我的 agent 列表
   - `/agents/new` —— 注册 agent（填 Agent Card 字段 + 选接入方式）
   - `/me` —— dashboard（我发的 / 我接的 / 信誉分 / credit 余额）
   - `/login` `/register` —— 保留，简化文案
3. **统一导航 + 风格**：
   - 用今天 jarvis 已经替换好的 SVG 图标库（不要重新发明）
   - 保留 Polis 品牌色 + 渐变
4. **核心交互**：
   - 任务详情页用 SSE 实时显示 agent 进度
   - 接到推送时浏览器通知（可选）
5. **零虚假数据**：所有页面真连后端 API

#### 验收标准
- 5 个页面全部 200 响应
- 端到端用户旅程跑通：注册 → 注册 agent → 发任务 → （切到另一个用户）抢单 → 提交结果 → 评分
- TypeScript 0 错误，next build 0 错误
- 0 emoji（continue 用 SVG 图标）

#### 不要做的事
- ❌ 不要造任何假数据 / 占位文案 / 虚构任务
- ❌ 不要做社交功能（点赞、关注、评论）
- ❌ 不要乱加自己的产品功能，严格按规格做

---

### 6.C polis-cli 任务 → opencode 或 lobster

#### 范围
新项目 `/Users/a1111/projects/ai-society/polis-cli`：

1. **Python 包结构**：
   ```
   polis-cli/
     polis/
       __init__.py
       cli.py              # click 入口
       agent.py            # Agent 类
       transport.py        # webhook + websocket 双模式
       a2a.py              # A2A 协议封装
     setup.py / pyproject.toml
     README.md
   ```
2. **核心命令**：
   - `polis login` —— 浏览器 OAuth 或 token 登录
   - `polis agent register --name xxx --skills "translate,summary"` —— 注册 agent
   - `polis agent serve` —— 启动接任务（webhook 或 websocket 模式）
   - `polis agent list` —— 列出我的 agent
   - `polis job send <agent> <text>` —— 发测试任务
3. **Hermes 集成**：
   - 提供 `polis.hermes` 子模块
   - 让 Hermes 用户写：`@agent.skill("code-review")` 装饰器，把 Hermes 的某个 skill 暴露成 A2A capability
4. **示例 agent**：写 3 个示范 agent，能立刻跑：
   - `examples/translator.py` —— 中英翻译
   - `examples/summarizer.py` —— 文本总结
   - `examples/code_reviewer.py` —— 代码审查

#### 验收标准
- `pip install -e .` 能装上
- `polis agent serve` 能连上后端，收到任务能返回结果
- 3 个示范 agent 都能跑

---

## 7. 三方接口契约（避免合并地狱）

### 后端 ↔ 前端
**OpenAPI 自动生成**，前端从 `http://localhost:8000/openapi.json` 拿 schema，用 `openapi-typescript` 生成类型。

### 后端 ↔ CLI
**A2A 协议标准**，CLI 完全按 A2A 客户端规范调后端，后端是 A2A server。

### 关键 API 列表
```
# Auth
POST /api/v1/auth/register
POST /api/v1/auth/login

# Agents
POST /api/v1/agents
GET  /api/v1/agents
GET  /api/v1/agents/{id}
POST /api/v1/agents/{id}/heartbeat
DELETE /api/v1/agents/{id}

# Jobs（标准 A2A）
POST /api/v1/jobs
GET  /api/v1/jobs?status=&skill=
GET  /api/v1/jobs/{id}
POST /api/v1/jobs/{id}/claim
POST /api/v1/jobs/{id}/artifacts
POST /api/v1/jobs/{id}/progress
POST /api/v1/jobs/{id}/cancel
POST /api/v1/jobs/{id}/rate

# SSE
GET  /api/v1/jobs/{id}/events  (text/event-stream)

# A2A 标准发现
GET  /.well-known/agent.json
```

---

## 8. 时间线

| 时间 | 事件 |
|---|---|
| 19:30 | 派 3 个任务给 sibling agents |
| +1h (20:30) | 三方进度 check-in |
| +2h (21:30) | 后端 + 前端的接口对齐（jarvis 协调） |
| +3h (22:30) | 后端 happy path 跑通 |
| +4h (23:30) | 前端 5 页面跑通 |
| +5h (00:30) | CLI 跑通 |
| +6h (01:30) | 三方端到端联调 |
| +7h (02:30) | demo 给用户验收 |

最坏情况翻倍 = 14 小时，明天中午前完事。

---

## 9. 风险 + 缓解

| 风险 | 缓解 |
|---|---|
| 三方进度不一致 | jarvis 每小时一次 check-in，谁堵了立刻调资源 |
| A2A 协议理解偏差 | 派任务前给 codex 发 A2A spec 链接，要求严格按 spec 实现 |
| 旧数据库 / 旧代码删错 | git commit 当前状态作为回滚点 |
| sibling agent 自由发挥加奇怪功能 | 任务规格里**明确写出"不要做"的事** |
| 接口契约不一致 | 强制后端先出 OpenAPI，前端基于 OpenAPI 生成类型 |

---

## 10. 派任务的话术（你直接复制给 sibling agent）

### 给 codex 的
> Codex，你接 Polis v1 的后端任务。读 `/Users/a1111/projects/ai-society/POLIS_V1_PLAN.md` 的 §4、§6.A、§7。严格按 spec 做，不要自由发挥加功能。先 git commit 当前 backend 状态作为回滚点，然后清旧 schema、建新 schema、实现 §6.A 的 8 项接口、写测试。完事 ping jarvis（@henry-jarvis）验收。

### 给 claude-code 的
> Claude Code，你接 Polis v1 的前端任务。读 `/Users/a1111/projects/ai-society/POLIS_V1_PLAN.md` 的 §6.B、§7。严格按 spec 做，**不要造假数据 / 不要做社交功能**。基于 frontend 现有 Next.js 项目重写 5 个页面。等后端 OpenAPI ready 后用 openapi-typescript 生成类型。完事 ping jarvis 验收。

### 给 opencode / lobster 的
> 你接 Polis v1 的 CLI 任务。读 `/Users/a1111/projects/ai-society/POLIS_V1_PLAN.md` 的 §6.C。在 `/Users/a1111/projects/ai-society/polis-cli` 新建 Python 包，实现 5 个命令 + 3 个示范 agent。完事 ping jarvis 验收。

---

## 11. 验收清单（最后 demo 的）

- [ ] 用户 A 注册账号，注册一个 "translator" agent，写一段 prompt 接 Claude API
- [ ] 用户 B 注册账号，发任务"把这段中文翻成英文：今天天气很好"
- [ ] 任务广场能看到 B 的任务，A 的 agent 收到推送
- [ ] A 抢单成功，agent 调 Claude，5 秒后返回结果
- [ ] B 在前端看到结果"Today's weather is great"
- [ ] B 给 5 星评分
- [ ] A 的信誉分 +1，credit_balance +1
- [ ] B 的 credit_balance -1
- [ ] 整个流程不超过 30 秒
- [ ] 没有任何假数据 / mock / 占位文案
- [ ] A2A spec 验证器能验证 Polis 是合规节点

---

## 12. 我的角色（jarvis）

- 写 spec、派任务、协调
- 监控三方进度，每小时 check-in
- 解决卡点（接口对不上、依赖缺失等）
- 端到端联调 + 给你 demo
- **不写代码**，全权交给 sibling agents

你的角色：
- 派 codex / claude-code / opencode（你说现在就干，所以你来派）
- 验收 demo
- 拍板新需求
- 不动键盘
