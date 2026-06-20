# Polis v1 — Progress Log

时间倒序。每条带证据（commit / 文件 / 端口 / curl 响应）。

---

## 2026-06-20（Sat）AEST

### 20:50  Agent Inbox 接口（**核心基建**）
- 新接口：`GET /api/v1/agents/{agent_id}/inbox` (SSE)
- commit `4dd583e feat(backend): GET /agents/{id}/inbox` → merged `eb0bcfe`
- **行为**：
  - Phase 1 backlog：当前所有 `status=submitted` 且 `required_skill ∈ agent.skills` 的任务用 `event: job.available` 发给 agent
  - Phase 2 live：每 2 秒轮询 DB，新匹配任务推送同样事件
  - 每 15 秒 heartbeat，10 分钟流上限（client 用 Last-Event-ID 续）
- **架构权衡**：原计划 PG LISTEN/NOTIFY，但 Supabase 的 pgbouncer transaction mode（端口 6543）不支持 session 级 LISTEN，**改为 DB 轮询**。延迟 ~2s，对任务市场可接受，且跨 PG 部署可移植。
- **副作用修复**：`AgentCreateRequest` 加 `skills: List[str]` 顶层字段。原本 codex 严格按 A2A spec 要求 skills 是 dict 对象，但 `["code_review","python"]` 这种字符串列表是常见 UX，现在两种形态都吃。
- **端到端验证**：bob 注册 agent（skills=`code_review/python/translation`），开 inbox 长连接 → alice 30s 内连发 4 个不同技能的任务 → agent 在 SSE 里看到 3 个匹配的（code_review/translation/python），sql 被过滤掉。**全对**。
- **意义**：UUMit 没有这个能力（首页 0+ Agent 0+ 任务）。Polis 现在有"任务自动喂到 agent 嘴边"的水管。下一步写 demo agent 把这条管子喝起来。

### 20:32  竞品扫描 + 定位钉死（用户主导）
- 用户提出："去看看 UUMit"
- JARVIS 调研：uumit.com / 搜狐报道 → 自称"行业首个 A2A 能力网络平台"，2025 年 10 月发布
- **判定**：UUMit ≠ 我们竞品，路线根本不同
  - UUMit = A2A 协议 + UT 代币 + C 端宽口能力市集（卖数据库/课程/社群/陪练/找人/监督早起）
  - Polis = 任务网络 + 信誉 + AI 工程师内部网（PR review / 报告 / 代码 / 数据等真任务）
- **可疑信号**：UUMit 首页计数器 0+ Agent / 0+ UT / 0+ 活跃，市集精品全是 100-200 次购买的预制内容，可能没真活跃
- **正向信号**：他们走代币付费路线，间接说明纯信誉路线没人验证过 —— 我们的路差异化清晰
- **行动**：把定位钉到 STATE.md + POLIS_V1_PLAN.md
  - 三条差异化锚点：任务驱动 / 信誉驱动 / AI 工程师网络
  - 四条红线：不做代币 / 不做能力商品 / 不做 C 端撮合 / 不做平台托管 agent
  - 竞品对照表写进文档，每周复查
- **结论**：继续干。下一步 OAuth + 部署。

### 20:19  事实层同步
- 项目登记进 `~/projects/registry.yaml`（id=`polis`）
- 创建 `STATE.md` + `docs/progress.md`（本文件）
- 触发人：JARVIS

### 20:00–20:19  端到端验收 + bug 修复（JARVIS）

**起点**：codex 报后端完成（`f293e2a`），claude-code 报前端完成（`fa607ba`）。
**JARVIS 不接受口头交付，跑真验**：

1. merge 双分支到 `main`，**0 冲突**（shared/ 契约策略生效）
2. backend 装依赖 → 撞坑：venv 的 shebang 还指向旧路径 `/Users/a1111/projects/...`（搬到 Desktop 后失效）
   - 修：`rm -rf venv && python3 -m venv venv && pip install -r requirements.txt`
3. alembic 迁移 → 撞坑：`type "agent_auth_method" already exists`（codex 漏写 `create_type=False`，column 引用时二次触发 CREATE TYPE）
   - 修：5 个 enum 加 `create_type=False`
4. uvicorn 启动 → 撞坑：`No module named 'email_validator'`（codex 漏依赖）
   - 修：`requirements.txt` 加 `email-validator>=2.0`
5. 端到端真流程跑通：
   - 注册 alice/bob ✅（注意：email-validator 拒 `.test` TLD，用 `@example.com`）
   - 登录拿 JWT，字段名 `token`（不是 `access_token`，前后端契约一致 ✅）
   - 注册 agent ✅（agent_card 存 JSONB，含 url/name/version/skills/description）
   - 发任务 ✅ → 自动生成 `a2a_task` 结构 + `events` 时间线
   - 抢单 ✅ row lock 起作用，状态 `submitted → claimed`
   - 进度更新 → 撞坑：`/progress` 不接受 `agent_id`（codex 把 user-token 路径写死 `None`）
     - 修：`JobProgressRequest` 加 `agent_id` 字段，`_agent_for_token(cur, auth, request.agent_id)`
   - 提交产物 → 同样的坑（`/artifacts`）
     - 修：`JobArtifactRequest` 加 `agent_id` 字段
   - 评分 ✅ 字段名 `stars`（不是 `score`），`feedback`（不是 `comment`）
6. 最终验证：`status: completed`，artifacts 1 条，rating 5 星，5 个事件全发（created/claimed/progress/delivered/rated）

**修复 commit**：`677c111 fix(backend): allow user-token submitters to pass agent_id...`
**merge to main**：`19d30da merge: backend bugfixes`

服务状态：
- backend :8000 ✅ HTTP 200
- frontend :3000 ✅ HTTP 200（首页/jobs/new/agents/new/me 全 200）

### 19:52  claude-code 交付前端（V1）
- commit `fa607ba frontend: rewrite UI for Polis v1 A2A protocol`
- diff: +2376/-1548（24 文件）
- 删除：所有社交残骸（TaskCard / CoverIllustration / profile/[user_type] / tasks/*）
- 新增：6 个 v1 页面，4 个 lib/api 模块，types.ts（手写过渡，待 codegen 覆盖）
- 自验：tsc --noEmit clean，next build 10/10 routes ok

### 19:59  codex 交付后端（V1）
- commit `f293e2a feat(backend): implement Polis v1 A2A APIs`
- diff: +4100/-375（16 文件）
- 7 表迁移、9 路由、A2A 协议投影、Supabase Storage、pytest 3/3 通过
- 自验：pytest pass

### 19:39  工作区搬桌面
- 从 `/Users/a1111/projects/ai-society/` 整体 mv 到 `~/Desktop/ai-society/`
- git 历史 / 分支 / 工作树完整保留
- 后续坑：venv shebang 失效（见 20:00 验收）

### 19:34  setup 共享契约目录
- 建 `shared/`（contract zone for OpenAPI）
- 在 main 分支 commit；后续 cherry-pick 到 polis-v1-backend / polis-v1-frontend，三分支同步

### 19:30  V1 重写起点（snapshot）
- commit `de31cf0 chore: snapshot before Polis v1 A2A rewrite (2026-06-20 19:30 AEST)`
- 作为回滚锚点

### 早些时候  产品方向 pivot
- 推翻原 "owner 发任务 + agent 投标" 设计（=Upwork+AI / Coze 山寨）
- 调研：A2A Registry / NANDA / AgentScope，确认协议层成熟，**中文消费级产品壳无人做**
- 拍板 v1 范围：A2A 兼容 / AI 工程师内测 / 无支付 / 信誉驱动 / 4 原语
- 写 `POLIS_V1_PLAN.md`（14.7KB，含 §4 schema、§6.A 后端、§6.B 前端、§7 时间线）

---

## 历史（pre-pivot，已废弃）

- 2026-06-19 之前：v0.3 社交版（owner/agent 双角色 + 点赞/评论/follow/feed/leaderboard/anti-fraud），不再维护，已删表/删页。

---

## 下一里程碑候选（按优先）

1. **接 OAuth**（GitHub / 飞书） — 让 AI 工程师能用 GH 账号一键登录
2. **建 Supabase Storage bucket `polis-attachments`** — 跑一遍真附件上传
3. **真注册一个 Hermes agent 进去跑一单** — 不靠 mock 验通联
4. **部署**（Vercel 前端 + Render/Fly.io 后端） — 拿到公网 URL
5. **polis-cli v1.5** — agent 自动 register + heartbeat
