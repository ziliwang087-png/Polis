# L25 BYOA — 三方协作分支状态

> 临时文档，等三方都完工合并后删掉。

## 三个分支

- **`L25-byoa-core`**（JARVIS 写的后端核心，1 commit）
  - `backend/byoa/agent.py` —— 单文件 stdlib agent（JARVIS 版）
  - `backend/app/routes/agents.py` —— `POST /agents/{id}/install-token`
  - `backend/scripts/loop/verify_install_token.py` —— 6/6 PASS
  - `backend/scripts/loop/verify_byoa_agent_smoke.py` —— 6/6 PASS
  - pytest 47/47 ✅

- **`byoa-installer`**（Claude Code 写的安装器 + JARVIS 写的前端 wizard）
  - `backend/byoa/install.sh` —— Claude
  - `backend/byoa/bootstrap.py` —— Claude
  - `backend/byoa/agent.py` —— **Claude 写了一份**（和 L25-byoa-core 那份冲突）
  - `backend/byoa/autostart/` —— LaunchAgent / systemd / Task Scheduler / register-windows.bat
  - `backend/byoa/TROUBLESHOOTING.md` —— Claude
  - `backend/byoa/WINDOWS-TEST.md` —— Claude
  - `frontend/app/agents/[id]/install/page.tsx` —— JARVIS（commit `053013e`）
  - `frontend/lib/api/agents.ts` —— `issueInstallToken` —— JARVIS
  - `frontend/app/agents/page.tsx` —— "接入电脑" 按钮 —— JARVIS

- **`main`** —— 还没动

## 待办

1. 等 Claude Code 完工 commit（它的 evaluator 1-11 全绿才停）
2. 跑 codex review prompt（本文档对应的 prompt 在 chat 里）
3. 合并策略：
   - `byoa-installer` 的 agent.py vs `L25-byoa-core` 的 agent.py —— **二选一**
     - 看哪个更全：humanize_llm_error / SIGTERM / install token decode 谁实现得好
     - 评估器对哪份的覆盖率高
   - install token 的字段名是否对齐：bootstrap.py 解码出来的字段 == agent.py 期待的字段 == 后端发出的字段
4. cherry-pick `L25-byoa-core` 的后端 commit `5874d38` 到 `byoa-installer`
5. push `byoa-installer` 到 origin（不是 main，PR 形式）
6. 部署 prod 前要：测试 install token bundle 兼容、agent.py 能用 install token 启动、调用真 LLM

## 接口契约（双方必须一致）

- 后端 `/agents/{id}/install-token` 返回的 base64 bundle 字段：
  - `api` — backend base URL
  - `token` — JWT
  - `agent_id` — UUID
  - `agent_name` — string
- bootstrap.py / install.sh 收到 install_token 后：
  - 解码 → 写入 `~/.polis/config.json`（权限 0600）
  - 启动 agent.py 时通过 env 变量传入

## 风险

- 双方 agent.py 字段名/逻辑可能不一致，合并要逐项 diff
- 双方各自的评估器可能测不同维度，合并时两个都要保留
