# L25 BYOA — 最终交付报告

> 时间：2026-06-22 09:03 AEST  
> 分支：`byoa-installer`（已 push）  
> 状态：**开发完成，待合并到 main**  

---

## 一句话

**用户点网页"接入电脑" → 复制一行命令 → 粘贴到终端 → agent 自动跑在自己机器上，用自己的 LLM key 接 Polis 任务，LLM key 永远不离开本地。**

---

## 产物清单（3 commits）

### Commit 1: `f25e8a8` — 后端 install-token endpoint
- `backend/app/routes/agents.py`：POST `/api/v1/agents/{id}/install-token`
  - 生成 90 天 JWT（scope=byoa）
  - base64url 打包成 install_token（含 api / token / agent_id / agent_name）
  - 返回 install_command（curl GitHub raw install.sh | bash -s -- <token>）
- `backend/scripts/loop/verify_install_token.py`：6 项验收（auth / 跨 owner / bundle / JWT / command）
- `backend/scripts/loop/verify_byoa_agent_smoke.py`：6 项 agent.py 模块验收

### Commit 2: `892674e` — 前端 wizard + Claude 全套安装器
- `frontend/app/agents/[id]/install/page.tsx`：BYOA install wizard 单页
  - 步骤 1：生成 install_command
  - 步骤 2：粘贴到终端 + LLM 配置说明
  - 绿色安全声明卡片："LLM key 永远不离开你的机器"
  - 5 项 FAQ（key 安全 / 持久化 / 多机器 / token 轮换）
- `frontend/app/agents/page.tsx`：每张 agent 卡片加"接入电脑"按钮
- `frontend/lib/api/agents.ts`：`issueInstallToken` API
- `backend/byoa/`（Claude Code 产出）：
  - `agent.py`（403 行，纯标准库）：单文件 agent，支持 install_token + env 双模式
  - `install.sh`（304 行 bash）：**JARVIS 改造加快速 token 路径**
  - `bootstrap.py`（228 行）：终端登录 + 注册 agent 的兜底路径
  - `autostart/`：macOS LaunchAgent / Linux systemd / Windows Task Scheduler
  - `TROUBLESHOOTING.md` + `WINDOWS-TEST.md`

### Commit 3: `fb2fa6f` — STATE.md 更新

---

## 两条安装路径（共存）

### 路径 A：网页 token 快速模式（主推）
1. 用户在 `/agents` 页点自己 agent 的"接入电脑"
2. 进入 `/agents/{id}/install`，点"生成安装命令"
3. 后端返回打包好的 install_command（含 90 天 token）
4. 用户复制 → 粘贴到终端 → install.sh 检测到 token 参数
5. install.sh 跳过登录步骤，只问 LLM 配置（base / key / model）
6. 写 `~/.polis/polis-byoa.env`（权限 600）
7. 可选装开机自启 → agent.py 启动

### 路径 B：终端登录兜底模式（Claude 原方案）
1. 用户直接跑 `bash install.sh`（无 token 参数）
2. install.sh 进入交互向导，问邮箱密码
3. 调用 `bootstrap.py` 登录 Polis → 注册 / 查 agent → 写 .env
4. 后续同路径 A

**两条路径都写 .env，agent.py 同时支持 `POLIS_INSTALL_TOKEN` 和显式 env 变量。**

---

## 验收状态

| 检查项 | 结果 |
|---|---|
| pytest 47/47 | ✅ |
| verify_install_token 6/6 | ✅ |
| verify_byoa_agent_smoke 6/6 | ✅ |
| frontend `next build` | ✅ 10/10 pages |
| bash -n install.sh | ✅ 语法 OK |
| 端到端真机 install | ⏸️ 待 main 合并后测（GitHub raw URL 才生效）|

---

## 关键设计决策

### 1. install.sh 由 GitHub raw 提供，不走后端 `/byoa/get`
**原因**：后端是业务逻辑层，不托管 shell 脚本。GitHub 是 install.sh 的 SSoT。  
**好处**：用户看到的 install_command 永远指向 repo 最新版本，无需后端同步部署。

### 2. LLM key 永远不进 polis 后端
**设计**：install_token bundle 只含 `api / token / agent_id / agent_name`，不含 LLM key。  
用户本机 install.sh 问 LLM 配置，写进本地 .env（权限 600），agent.py 直接调用户的中转。  
**证据**：verify_install_token T4 验证 bundle 字段，无 llm_key。

### 3. agent.py 单文件 403 行，零 pip 依赖
**原因**：降低用户安装门槛，Python 3.7+ 标准库即可跑。  
**Claude 版 vs JARVIS 版**：最终用 Claude 版（更全）：
- 支持 `POLIS_INSTALL_TOKEN` + 显式 env 双路径
- 支持 `POLIS_BYOA_ENV_FILE` 给 systemd/launchd 用
- 中文错误翻译更全（401 / 403 / 429 / SSL / DNS）
- SIGTERM 优雅退出 + 心跳 + inbox SSE 自动重连

### 4. install_token 90 天 TTL
**权衡**：够长（用户不用频繁重装），够短（泄露后风险有限）。  
**缓解**：用户可随时去 `/agents` 删 agent 重建，旧 token 立即失效。

---

## 未测 / 未动项

### 未测（等 main 合并）
1. 端到端真机 install：curl GitHub raw URL → install.sh → agent.py 启动 → 接到任务 → 交付 artifact
2. 开机自启真实验证（LaunchAgent / systemd）
3. Windows Git Bash 兼容性
4. 多机器同时跑同一个 agent（理论支持，未验）

### 未动（高风险，等你确认）
1. 合并 `byoa-installer` 到 `main`
2. Railway auto-deploy（main push 触发）
3. 前端 Vercel 部署
4. prod e2e 验证

---

## 下一步（你醒来后）

1. **审查分支** `byoa-installer`：
   - GitHub：https://github.com/ziliwang087-png/Polis/tree/byoa-installer
   - PR：https://github.com/ziliwang087-png/Polis/pull/new/byoa-installer
2. **本地 review**（可选）：
   ```bash
   cd ~/Desktop/ai-society
   git checkout byoa-installer
   git log --oneline -5
   git diff main...byoa-installer --stat
   ```
3. **端到端测（main 合并前）**：
   - 方案 A：手动把 install.sh 传到临时 gist，改 agents.py 的 GitHub raw URL 指向 gist，本地跑一遍
   - 方案 B：直接合并 main，Railway 部署后真机测，坏了回滚
4. **合并 + 部署**：
   ```bash
   git checkout main
   git merge byoa-installer --no-ff
   git push origin main  # 触发 Railway auto-deploy
   ```
5. **prod 验证**：
   - 登录 prod 前端 → 建一个 agent → 点"接入电脑" → 复制命令
   - 本机粘贴跑（真 LLM key） → 观察 agent 上线
   - prod 发一个任务 → 看 agent 是否接单 + 交付

---

## 团队协作记录

| 角色 | 产出 | 备注 |
|---|---|---|
| **Claude Code** | install.sh / bootstrap.py / agent.py / autostart/ / 文档 | 完整的交互式安装器 + 三大 OS 自启 |
| **JARVIS** | install.sh token 路径 / 前端 wizard / 后端 endpoint / verify 脚本 | 融合 Claude 产出 + 网页快速路径 |

**协作模式**：Claude 在 `byoa-installer` 分支写完整套，JARVIS 后 cherry-pick 后端 + 改 install.sh 支持 token 模式 + 写前端。最终 agent.py 用 Claude 版（更全），install.sh 用 JARVIS 改造版（双路径）。

---

## 已知问题 / 待优化

1. **install_command 太长**（~635 字符）：
   - 现状：`curl -fsSL https://raw.githubusercontent.com/ziliwang087-png/Polis/main/backend/byoa/install.sh | bash -s -- <token>`
   - 优化：后续可做短链服务（polis.app/get → 重定向）
2. **token 泄露无主动撤销**：
   - 现状：用户只能删 agent 重建
   - 优化：加 `/agents/{id}/revoke-tokens` endpoint
3. **agent.py 日志没结构化**：
   - 现状：print 到 stdout / byoa.log
   - 优化：加 JSON Lines 格式 + rotating file handler
4. **frontend 没 agent 状态实时刷新**：
   - 现状：用户要手动刷页面看 agent 是否上线
   - 优化：加 WebSocket / SSE 推送 agent 状态变更

---

## 总结

✅ **L25 BYOA 核心功能开发完成**  
✅ **两条安装路径融合（网页 token 快速 + 终端登录兜底）**  
✅ **验收 6/6 + 6/6 + pytest 47/47**  
✅ **分支已 push，STATE.md 已更新**  
⏸️ **等你审查 + 合并 main + 部署 prod + 端到端真机测**

**现在可以做的低风险操作**：
- 审查 PR diff
- 本地 checkout byoa-installer 跑 frontend dev server 看页面
- 读 agent.py / install.sh 代码

**等你确认后做的高风险操作**：
- 合并 main
- push main 触发 Railway 部署
- prod 真机 install 测试
