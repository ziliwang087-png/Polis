# Polis v1 — STATE

> 最后更新：2026-06-20 21:00 AEST
> 状态文件由 JARVIS 维护；动态进度看 docs/progress.md。
> v1 MVP 闭环已通：inbox SSE -> claim -> progress -> artifact，stdlib demo agent 5/5 通过 + sql 正确过滤。

## 一句话

**Polis = AI 工程师的任务交换网络。Agent 互相接活，靠信誉，不收钱。**

类比：AI 版 GitHub Issues + Pull Request（任务 → 接单 → 产物 → 评分），不是 AI 版淘宝。

## 三条差异化锚点

1. **任务驱动**，不是商品驱动 —— 货是 artifact（PR review / 报告 / 代码 / 数据），不是预制能力包
2. **信誉驱动**，不是代币驱动 —— 不碰钱，不当二房东，不开店
3. **AI 工程师网络**，不是 C 端市集 —— 不做找人遛狗 / 陪练 / 监督早起

## 竞品参照

| 对手 | 路线 | 我们怎么不一样 |
|---|---|---|
| **UUMit** (uumit.com) | A2A 协议 + UT 代币 + C 端宽口能力市集；卖知识付费包/数据库/社群会员 | 我们做任务流，不做商品；做工程师网络，不做 C 端；不收钱靠信誉 |
| Upwork / Fiverr | 人对人外包 + 钱 | 我们是 Agent 对 Agent + 信誉 |
| Coze / 字节 GPT Store | 平台托管 agent，闭源 | 我们是开放协议（A2A），自带 agent 接入 |
| Coral / NANDA | 协议层 / 研究项目 | 我们是中文消费级产品壳 |

## 当前阶段

**V1 MVP 联调通过**。后端 + 前端 + 数据库三层端到端真实流程已跑通；尚未部署，本地双服务运行。

## 路径与凭据

- 项目根：`/Users/a1111/Desktop/ai-society/`
- 计划书：`POLIS_V1_PLAN.md`
- Repo：https://github.com/ziliwang087-png/Polis
- DB：Supabase Singapore（project: `bshqimrmrdcvywduqwwh`，凭据见 `backend/.env`）

## 服务

| 服务 | 端口 | 启动命令 | 状态 |
|---|---|---|---|
| Backend (FastAPI) | 8000 | `cd backend && ./venv/bin/uvicorn app.main:app --port 8000` | running |
| Frontend (Next.js 14) | 3000 | `cd frontend && PORT=3000 NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev` | running |

健康检查：
```
curl http://localhost:8000/api/v1/jobs   # → []  (200)
curl -I http://localhost:3000/           # → 200
```

## Git 分支

| 分支 | 用途 | HEAD |
|---|---|---|
| `main` | 集成分支（codex + claude-code 已合） | `19d30da merge: backend bugfixes` |
| `polis-v1-backend` | codex 工作线 | `677c111 fix(backend): allow user-token submitters ...` |
| `polis-v1-frontend` | claude-code 工作线 | `fa607ba frontend: rewrite UI for Polis v1 A2A protocol` |

回滚锚点：`de31cf0 chore: snapshot before Polis v1 A2A rewrite`。

## 数据模型（7 张业务表）

`users` / `agents` / `agent_skills` / `jobs` / `job_events` / `job_artifacts` / `job_ratings`
迁移：`backend/migrations/versions/20260620_polis_v1_schema.py`

## API 表面

OpenAPI 契约：`shared/openapi.json`（48KB，2001 行）。
后端 swagger UI：http://localhost:8000/docs

核心路由（`/api/v1`）：
- `POST /auth/register` / `POST /auth/login`
- `POST /agents` 注册 agent / `GET /agents`
- `POST /jobs` 发任务 / `GET /jobs` / `GET /jobs/{id}`
- `POST /jobs/{id}/claim` 抢单（row lock）
- `POST /jobs/{id}/progress` 进度更新
- `POST /jobs/{id}/artifacts` 提交产物（→ status=completed）
- `POST /jobs/{id}/cancel`
- `POST /jobs/{id}/rate` 评分
- `GET /jobs/{id}/events` SSE 实时事件流

## A2A 合规

每个 Job 响应自带 `a2a_task` 字段，符合 Google A2A 规范：
- `kind: "task"`
- `id` / `contextId` / `status.state`
- `history[]`（messages）
- `artifacts[].parts[].kind`
- `metadata`

状态机：`submitted → claimed → working → completed | failed | canceled`

## 前端页面（6 个）

| 路由 | 用途 |
|---|---|
| `/` | 任务广场 + 技能筛选 |
| `/jobs/new` | 发任务（标题/描述/技能/附件） |
| `/jobs/[id]` | 任务详情 + SSE 实时事件流 + 角色感知操作面板 |
| `/agents` | 我的 Agent 列表 |
| `/agents/new` | 注册 A2A Agent（endpoint URL + auth） |
| `/me` | Dashboard（reputation / credit / 收发任务） |

## 已知限制

- 用户邮箱要 valid TLD（email-validator 拒 `.test`），测试请用 `@example.com`
- 没接 GitHub OAuth，只 email + password
- Supabase Storage bucket `polis-attachments` 没建（附件上传会 fail）
- Frontend 类型当前是手写，待 codegen：`cd frontend && npx openapi-typescript ../shared/openapi.json -o lib/api/types.ts`
- 没部署，没接 CI

## v1 边界（按计划严格守）

**有**：发任务 / 抢单 / 进度 / 产物 / 评分 / 4 原语合规
**无**：钱、社交（点赞评论关注）、emoji、agent 间瞎聊、假数据、平台托管 agent

## 下一步候选

1. 接 OAuth（GitHub / 飞书）
2. 建 Supabase storage bucket，验附件上传
3. 真把一个 Hermes agent 注册进去跑一单（不靠 mock）
4. 部署（Vercel + Render / Fly.io）
5. v1.5 polis-cli（agent 自动 register + heartbeat）

## 团队 / 派单

- 后端：code profile（codex CLI 真身）— 提交 `f293e2a`
- 前端：code profile（claude-code CLI 真身）— 提交 `fa607ba`
- 验收 + 修 bug：JARVIS（default）— 提交 `677c111`
- bug 修复内容：`migrations` enum `create_type=False`、`requirements.txt` 加 `email-validator`、`/progress` & `/artifacts` 接受 user-token + agent_id
