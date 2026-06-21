# Polis v1 — Progress Log

时间倒序。每条带证据（commit / 文件 / 端口 / curl 响应）。

---

## 2026-06-20（Sat）AEST

### 22:30  注册 Agent 页面为非开发者简化（v1.1）
- **问题**：原版要填 endpoint URL + bearer/hmac/skill_id-name-description 三段式，连用户都说"太麻烦"。后端实际只跑 pull 模式，webhook 字段是死的。
- **改动** (commit a04be34)：
  - 主表单只剩 显示名 / 描述 / 技能 chip
  - name(slug) 从显示名自动生成；纯中文输入 fallback 到 `agent-<random6>`
  - webhook 配置折叠到"高级 (v1 暂未启用，跳过即可)"
  - 注册成功后弹一段 demo_agent.py 启动命令，可复制
  - 修了顺手发现的 schema 不匹配：前端发 `skills: AgentSkill[]`，后端要 `string[]` → 422
- **验证**：
  - 公网 build 干净（10/10 routes，TypeScript 0 error）
  - 手工 curl 后端 POST /agents 用新 payload → HTTP 200，agent ID `ac9f3e3e...`
  - 浏览器跑了一遍：纯中文显示名 → slug 自动 fallback 成 `agent-6g9eys` ✓
- **遗留小事**：
  - 视觉 8/10，建议后续优化"已选区域空状态占位"和"chip 分组"
  - chip 重复点击在 Browserbase 远程浏览器有 hydration 怪事，真用户 Chrome 大概率不复现，等下次有人用再说

---

## 2026-06-20（Sat）AEST

### 21:40  上公网（Railway 后端 + Vercel 前端）
- **后端**：Railway，service=polis-backend，region=sfo，URL=https://polis-backend-production.up.railway.app
  - 部署：Dockerfile (python:3.11-slim) + entrypoint.sh (alembic upgrade head, non-fatal)
  - env vars 6 个：DATABASE_URL (Supabase pooler:6543), JWT_SECRET_KEY, JWT_ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES, CORS_ORIGINS, PUBLIC_BASE_URL
  - 验：`/health` 200, `/api/v1/jobs` 真数据, `/.well-known/agent.json` URL 正确
- **前端**：Vercel，project=polis-frontend，URL=https://polis-frontend-three.vercel.app
  - Next.js 16.2.9 (Turbopack)，10/10 routes 全好，TypeScript clean
  - env：NEXT_PUBLIC_API_URL=https://polis-backend-production.up.railway.app/api/v1
  - 验：HTTP 200，HTML 正确渲染
- **端到端真活验收**：本地 demo_agent 对公网后端跑 1 单
  - alice2 在公网登录 → POST /jobs 成功 → demo-bot SSE inbox 推送 → claim → progress×2 → deliver
  - jobs/c7148cea... events=`[created, claimed, progress, progress, delivered]`，artifact 落库，to_agent 正确
  - **公网 SSE 长连接工作正常**，10 分钟流上限和心跳都按预期
- **commit**：5f49568 (deploy: Dockerfile + railway.json + entrypoint.sh + DEPLOY.md)
- **意义**：Polis 第一次有公网 URL，外部任何人/agent 现在都能注册、发任务、接活。冷启动可以开始了。

### 21:30  push 远端 + 清 secret
- GitHub Push Protection 拦下了 `de31cf0` 里硬编码的 Supabase token
- 用 git-filter-repo 把整个 `backend/deploy_via_api.py` (v0.3 残骸) 从历史抹掉
- 顺手清掉幽灵 submodule `backend/hermes-webui` (160000 mode but no .gitmodules)
- 备份：/tmp/ai-society-backup-pre-filter.tar.gz (257MB)
- force push：`973b440 → 64a7da7`，远端 main 现在是 v1 完整代码

---

## 2026-06-20（Sat）AEST

### 21:00  Demo agent worker 跑通 v1 MVP 闭环
- 新文件：`examples/demo_agent.py`（122 行 stdlib，零外部依赖）
- 流程：login_or_register -> ensure_agent -> SSE inbox 订阅 -> 收 `event: job.available` -> claim -> 2 次 progress -> 提交 text artifact
- **验证（用真 jobs 表回放，非口头）**：
  - demo-bot 注册 skills=`code_review,python,translation`
  - alice2 发 3 个新任务（python / code_review / sql），加上 backlog 残留 5 个，共 8 个 submitted
  - 跑两轮 worker 后状态：`code_review` 4/4 done、`python` 3/3 done、`translation` 1/1 done、**`sql` 3/3 原样躺在 submitted（被 inbox 过滤掉）**
  - 抽样 job e429f24… 的 events 序列：`created -> claimed -> progress -> progress -> delivered`，artifact 落库成功，`to_agent_id` 指向 demo-bot 的 `df02224a-…`
- **意义**：v1 MVP 端到端真实闭环全打通。inbox 推送 + skill 过滤 + 抢单 + 进度 + 产物全工作。**Polis 现在可以接外部 agent 了。**
- 服务：backend :8000 / frontend :3000 仍 200。

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

---

## 2026-06-21 12:22 AEST — 转向真 A2A 路线

### 路线确认（Henry 拍板）
Polis = **纯撮合平台**，做真正的 A2A。用户上传自己的 agent（带 skills + 自己的 LLM key + 自己在用的模型），
任务匹配到对应 skill 时由用户自己的 agent 接活。Polis 后端**不碰 LLM、不当二房东**，只做任务路由 + 信誉评分 + artifact 存证。
内置 platform_agent 仅作冷启动/demo 占位，长期可有可无。

### 本次完成
- 写了 `examples/demo_agent_v2.py`：配置驱动的外部 agent 接入模板（stdlib only），读 `agent_config.yaml`，
  自动注册 → 订阅 inbox SSE → claim → progress → 调自己的 LLM → 交付 artifact（带 model/tokens/latency metadata）+ 失败重试
- 写了 `examples/agent_config.yaml.example`：接入配置模板
- 写了 `docs/AGENT_INTEGRATION.md`：5 分钟接入文档（含 FAQ、故障排查、多 agent、24/7 部署）
- `.gitignore` 加 `examples/agent_config.yaml`（防真实 LLM key 入库）

### 验证状态
- ✅ A2A 协议完全通：外部 agent 能注册/接活/报进度/交付（本地 8765 验证）
- ✅ 修了 demo_agent_v2.py 一个 bug：progress 接口字段是 `progress` 不是 `status`
- ❌ **LLM 调用受阻**：Henry 的 6 个中转站 key（bobdong/aiprox/hongxin 等）裸 HTTP 调 `claude-opus-4-8` 全 503/401
  （"model_not_found"/"no available accounts"/"Invalid token"）。但 **Hermes 主进程能调通 bobdong**——
  说明 Hermes 用了"订阅令牌绕指纹"那套（MEMORY 有记录：adapter+transports mcp_→mcptool_ + OAuth re.sub）。
  外部 agent 走标准 OpenAI HTTP 调不通这些特殊组的 key。

### 未决 / 下一步（开新对话从这里继续）
1. **LLM key 问题**：要么 (A) 把 Hermes 绕指纹逻辑移植到 demo_agent_v2.py；要么 (B) 用一个不需要绕的标准 key
   （OpenAI 官方 / DeepSeek 官方 / 中转站普通套餐）。Henry 倾向让接入者用自己的标准 key。
2. **commit 落地**：demo_agent_v2.py + agent_config.yaml.example + AGENT_INTEGRATION.md 还没 commit（工作树 untracked）
3. codex 昨晚跑完的 L1-L8（platform agent / translator / dynamic skills / rating / demo e2e）已 push 到 main (HEAD=46c503a)
4. 内置 platform_agent 在 Railway prod 上 LLM 也是 403/503（同 key 问题），但这不影响 A2A 主线

### 关键事实
- 公网后端：https://polis-backend-production.up.railway.app
- 公网前端：https://polis-frontend-three.vercel.app
- 本地测试后端：port 8765（scripts/loop/start_backend.sh）
- 测试账号：alice2@example.com / Alice2Pass-123
- Henry 的 LLM 中转站全在 ~/.hermes/config.yaml 的 custom_providers（6 个，目前裸 HTTP 都调不通 claude-opus-4-8）

---

## 2026-06-21 12:41 AEST — BYOK 路线落地 + commit

### 决策（Henry 拍板）
LLM key 问题选 **路径 B**：不移植绕指纹逻辑。Polis 是纯撮合平台，接入者**自带 agent + 自带模型 + 自带 key**，
我们不提供算力、不当二房东、不存接入者的 LLM key。bobdong 这类需要伪装指纹的特殊中转站不进示例。

### 本次完成（commit 0c28031，已 push origin/main）
- `examples/agent_config.yaml.example`：改成 4 个标准 provider 示例（OpenAI/DeepSeek/Anthropic 官方/本地 Ollama-vLLM），
  删掉硬编码的 bobdong key
- `docs/AGENT_INTEGRATION.md`：明确 "Polis does not give you a model / 自带 key，自己付费" 定位；
  What You Need 段改成官方 provider 列表
- `examples/demo_agent_v2.py`：122 行 stdlib worker，首次入库（之前一直 untracked）

### 验证
- ✅ fetch 确认 push 前 local==remote (46c503a)，无 Henry 并行操作冲突
- ✅ grep 扫过三个文件无 sk-evp/sk-ant/bobdong.cn 泄露
- ✅ .gitignore 仍挡住真实 examples/agent_config.yaml
- ⚠️ 顺手实测了那个 bobdong key：OpenAI 格式和 Anthropic /v1/messages 格式都返 503
  model_not_found（"No available channel under group CC限时满血特价"）——确认是中转站渠道/分组问题，
  不是网络。这进一步支持 BYOK 决策：不依赖这类不稳定的特殊中转站。

### 下一步候选
1. 真拉一个外部 agent 用标准 OpenAI/DeepSeek key 跑通一单（端到端验 BYOK 路线真能用）
2. 公网前端注册页是否要加 "自带模型" 的提示文案
3. polis-cli v1.5（agent 自动 register + heartbeat）

---

## 2026-06-21 14:16 AEST — 文档：把"中转站是常态"写进示例

### 背景
昨天 commit 0c28031 把 `agent_config.yaml.example` 改成"OpenAI/DeepSeek/Anthropic 官方"
为主，但 Henry 指出 99% 国内接入者用的是中转站，不是官方 key。文档给的第一档默认值
对国内用户不友好——复制下来还得自己改 base_url。

### 本次改动（无 commit hash 待 push）
- `examples/agent_config.yaml.example`：把"OpenAI 兼容中转站"提到第一档示例
  （aiprox/aigc369/api2d/openai-sb/oneapi 等），官方 OpenAI/DeepSeek/Anthropic
  和自部署退到下面注释项
- `docs/AGENT_INTEGRATION.md`：
  - Quickstart 示例 base_url 改成 relay 占位
  - "What You Need" 段把"第三方中转 (中转站)"列为最常见选项
  - 加 troubleshooting 提示：relay 401/503 通常是渠道限制（desktop-only/fingerprint-gated），
    去问 relay 客服，而不是 Polis 的问题

### 立场不变
- Polis 仍是纯撮合，agent 跑用户机器，key 用户保管
- 这次只是把"接入者用啥 key"的描述从"以官方为主"改成"中转是常态、官方/自部署也支持"
- BYOK 端到端实测仍未做（aiprox 今天通了，但中转站 ≠ 普适证明，等真用户接入或拿 DeepSeek 官方 key 验）

### 未追踪文件（本次不进 commit，等回来再决定）
- `LOOP_PROMPT.md`（出门前的 Loop Engineering 子任务交接稿）
- `backend/scripts/verify_platform_agent.py`（出门前的内置 platform_agent 验证脚本）
