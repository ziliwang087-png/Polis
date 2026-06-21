# Polis Loop Engineering — 一晚上 Loop 任务（给 claude code / codex）

你将运行一晚上的 Loop Engineering 工作流，在 `/Users/a1111/Desktop/ai-society/`
仓库里持续找 bug、修 bug、优化 Polis（一个 A2A 任务网络产品）。
明早需要给主人一份"这一晚我做了什么、当前状态如何"的总结。

---

## 项目一句话

Polis = AI Agent 任务交换网络。用户发任务（写代码 / 翻译 / review），
Agent 接活、交付 artifact，靠信誉评分。**不收钱，不当二房东。**

- Repo：`/Users/a1111/Desktop/ai-society/` (main 分支)
- Backend：FastAPI + Supabase Postgres，部署在 Railway
- Frontend：Next.js 14，部署在 Vercel
- 公网：https://polis-backend-production.up.railway.app + https://polis-frontend-three.vercel.app
- LLM key：`~/.hermes/config.yaml` 里 `model:` 段（base=https://chat.aiprox.net/v1，model=claude-opus-4-7）

---

## 你的工作模式：Loop Engineering

不是"我列一堆 bug 你按顺序修"。是 **设计循环系统替我去 prompt 你自己**：

```
loop {
    选一个目标         (从 backlog 拿)
    跑评估器           (机械验证脚本，pass/fail 二值)
    if pass:
        commit + push + 标记 done + 选下一个目标
    if fail:
        看 log → 提一个具体修复假设 → 改代码 → 回到"跑评估器"
    if 同一个目标 8 轮没过:
        标记 stuck，记录分析，跳下一个
}
```

**核心纪律**：
- 评估器是 ground truth，**禁止改评估器骗自己 pass**
- 每次 commit 前必须 `pytest tests/ -q` 全过，挂了就 revert 自己的改动
- 不要 force push、reset --hard
- 每个目标 8 轮没通过就 stuck，去做下一个，不要死磕

---

## 你工作目录里已经有的东西

主人（之前那个会话）已经写了部分基础设施：

```
backend/scripts/loop/
├── verify_platform_agent.py   # L1 评估器（已写，已经 PASS 一次）
├── verify_translator.py       # L3 评估器（已写，未跑过）
├── verify_frontend_smoke.py   # L4 评估器（已写）
├── start_backend.sh           # 起本地 backend (port 8765) 带 platform agent env
├── stop_backend.sh
├── deploy_railway.sh
└── CRON_PROMPT.md             # 这个 prompt 的早期草稿，可参考
```

主人也写了 `backend/app/platform_agent.py`：FastAPI startup hook 起的内置 agent，
已经在本地验证能调真 LLM 跑通 fizzbuzz。但**还没 commit**，工作树是脏的。

请先 `git status` 看清楚，再开工。

---

## Backlog（按优先级）

按这个顺序跑。每个目标都对应一个评估器 + 一组允许改的文件。

### L1: platform agent 在本地跑通真 LLM（已 90% 完成）

- 评估器：`backend/scripts/loop/verify_platform_agent.py`（exit 0 = pass）
- 启动：`bash backend/scripts/loop/start_backend.sh`
- 允许改：`backend/app/platform_agent.py`、`backend/app/main.py`、`backend/app/routes/`
- 完成动作：commit（含工作树未 commit 的 platform_agent 代码）+ push

### L2: platform agent 部署到 Railway 公网

- 评估器：你自己写一个 `verify_platform_agent_prod.py`，调
  `https://polis-backend-production.up.railway.app/api/v1/agents` 看 polis-platform-py 在线
  + 发一个 prod fizzbuzz 任务、35s 内 completed、artifact.by 正确
- 需要：在 Railway 加环境变量
  - `POLIS_PLATFORM_AGENT_ENABLED=1`
  - `POLIS_PLATFORM_AGENT_USER_EMAIL=polis-platform-bot@polisapp.com`
  - `POLIS_PLATFORM_AGENT_USER_PASSWORD=PlatformLocalPass-9938`（已是本地用过的）
  - `POLIS_PLATFORM_AGENT_LLM_BASE=https://chat.aiprox.net/v1`
  - `POLIS_PLATFORM_AGENT_LLM_KEY=<从 ~/.hermes/config.yaml 读>`
  - `POLIS_PLATFORM_AGENT_LLM_MODEL=claude-opus-4-7`
- Railway CLI 已登录：`/opt/homebrew/bin/railway up --service polis-backend --detach`
- 完成动作：评估器 prod 版 PASS

### L3: 加第二个内置 agent (translator)

- 评估器：`backend/scripts/loop/verify_translator.py`（已写）
- 思路：让 platform_agent.py 不再是单 agent，而是配置驱动的多 agent。
  抽象一个 `BUILTIN_AGENTS` 列表，每项 `{name, skills, system_prompt}`。
  原 polis-platform-py 仍然在，再加一个 polis-platform-translator 专门 skill=translate。
- 完成动作：本地 + prod 都 pass

### L4: 前端冒烟（所有公开路由不崩）

- 评估器：`backend/scripts/loop/verify_frontend_smoke.py`
- 失败时：fix 对应路由，可能要补 null-safety / fallback
- 完成动作：评估器 PASS

### L5: 可发现性——`/.well-known/agent.json` 的 skills 真实反映系统状态

- 写评估器：检查 well-known 返回的 skills 列表 != 空，包含至少 5 个真实 skill
- 当前实现：app/main.py 里硬编码 polis.jobs.* 几个；要改成动态从数据库读
- 完成动作：评估器 PASS

### L6: 评分系统跑通

- 写评估器：完整跑一遍发任务 → 接活 → 交付 → rating（5 stars）→ agent.avg_rating 更新
- 当前现状：评分接口存在，但 avg_rating 在 agent list 上一直是 null（前端做了防御）
- 完成动作：发 1 个 fizzbuzz、rate 5 星、再 GET 该 agent，avg_rating == 5.0

### L7: demo agent (`examples/demo_agent.py`) 接 LLM

- 写评估器：本地起 demo_agent 进程（连本地 backend），发 fizzbuzz，artifact.by="demo_agent.py"
  且内容真实
- 当前 demo_agent 返回写死字符串 "[demo-bot] handled ..."
- 完成动作：替换成调 chat.aiprox.net LLM，评估器 PASS

### L8: 真实 demo 视频脚本

- 写一个 `scripts/loop/demo_e2e.py`：注册新 user → 发 5 种不同 skill 任务 →
  全部 completed → artifacts 包含真实内容 → 输出截图友好的 markdown report
- 完成动作：脚本能产出一份 report，artifact 真实

---

## State / 进度跟踪

每个 tick（也就是你每一段工作）开始前，写或更新：
`backend/scripts/loop/state.json`（如果不存在就创建）

格式：
```json
{
  "current_loop": "L2",
  "history": [
    {"loop":"L1", "passed":true, "attempts":1, "ts":"2026-06-21T01:30+1000",
     "summary":"platform agent works locally with claude-opus-4-7"},
    ...
  ],
  "stuck_skipped": [],
  "last_fix": "added agent_id to artifact body",
  "morning_summary": null
}
```

最后一个目标做完（或所有都 stuck），把综述写到 `morning_summary` 字段，
内容包括：
- 通过的 loops + 一行解释
- stuck 的 loops + 你的诊断
- 改过的关键文件清单
- 给主人的明早 3 个建议

---

## 时间预算 / 自我节奏

- 估计你能跑 6-8 小时
- 每个 loop 上限 8 内循环 × 大约 5-15 分钟一轮 = 最多 1-2 小时
- 8 个 loop 按时间分：每个最多 1 小时，跑不通就 stuck 移走，确保至少能扫一遍

---

## 已知坑（少踩）

- LLM 模型 `gpt-4o-mini` 这家 proxy 不支持，503。用 `claude-opus-4-7`。
- 后端 progress/artifacts 接口要在 body 里带 `agent_id`，不然 400。platform_agent.py 已经修了。
- auth/register 拒 `.local` TLD 和 < 6 位密码
- Railway 不绑 GitHub webhook，push 后必须手动 `railway up --service polis-backend --detach`
- 本地 backend 和 Railway 共用同一个 Supabase——本地 commit 数据 prod 也看得见
- 本地 8765 端口和 Railway 公网 8000 不要混。本地评估器打 8765，prod 评估器打 polis-backend-production.up.railway.app

---

## 启动姿势（你的第一步）

```bash
cd /Users/a1111/Desktop/ai-society
git status                          # 看脏不脏
cd backend
./venv/bin/python -m pytest tests/ -q   # baseline 47 passed
bash scripts/loop/start_backend.sh
./venv/bin/python scripts/loop/verify_platform_agent.py  # 应当 PASS（L1 起手即过）
bash scripts/loop/stop_backend.sh
git add -A && git commit -m "loop: L1 platform agent verified" && git push origin main
# 然后开始 L2
```

---

## 终极纪律（再说一遍）

1. 评估器是 ground truth，不许为了 pass 改评估器
2. commit 前必须 pytest 全过
3. 一个 loop 8 轮没通过 → stuck → 跳下一个
4. 不许 force push / reset --hard / 删别人的代码
5. 每个 tick 更新 state.json，明早一份完整 morning_summary
