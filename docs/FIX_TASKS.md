# 修复任务清单

**目标**：修复端到端测试中发现的所有问题

---

## 问题 1：任务详情接口报错

**现象**：
```
GET /api/v1/tasks/{id}
返回：{"detail": "Task detail fetch failed"}
```

**任务**：
1. 检查 `backend/app/routes/tasks.py` 中的任务详情接口
2. 找到报错原因（可能是查询逻辑、字段名、权限检查）
3. 修复后确保返回完整任务信息

**验收标准**：
- `curl https://polis-backend-production.up.railway.app/api/v1/tasks/{id}` 返回完整任务数据
- 包含：title, description, status, assigned_agent_id, result/deliverable 等

---

## 问题 2：通知接口报错

**现象**：
```
GET /api/v1/notifications
返回：{"detail": "Notification listing failed"}
```

**任务**：
1. 检查 `backend/app/routes/notifications.py` 中的查询逻辑
2. 修复报错（数据库表已存在，应该是代码问题）
3. 确保接单/完成任务时触发通知创建

**验收标准**：
- `curl https://polis-backend-production.up.railway.app/api/v1/notifications` 返回通知列表（可以是空数组）
- Agent 接单时 → 创建通知
- Agent 完成任务时 → 创建通知
- 用户能查询到通知

---

## 问题 3：游戏化接口 404

**现象**：
```
GET /api/v1/gamification/agent/{id}/stats
返回：{"detail": "Not Found"}
```

**任务**：
1. 检查路由是否正确注册（`app/main.py`）
2. 检查 `backend/app/routes/gamification.py` 的路由定义
3. 确保返回 agent 的 xp, level, total_tasks_completed, badges 等

**验收标准**：
- 接口返回正常数据
- 包含：xp, level, total_tasks_completed, badges 数组

---

## 问题 4：完成任务后不奖励 XP

**现象**：
Agent 完成任务后，xp 没有增加，不会升级，不会获得徽章

**任务**：
1. 在 `backend/app/routes/tasks.py` 的 `complete_task` 函数中
2. 调用 `gamification.py` 的 `award_xp()` 函数
3. 调用 `check_badges()` 检查徽章
4. 确保 `agents` 表的 xp/level/total_tasks_completed 字段正确更新

**验收标准**：
- Agent 完成任务后，查询 agent 数据，xp 增加 50
- 达到阈值时，level 自动升级
- 完成第 1 个任务获得徽章 "初出茅庐"
- 完成第 10 个任务获得徽章 "十全十美"

---

## 问题 5：Agent API 返回数据缺少游戏化字段

**现象**：
```json
{
  "id": "...",
  "name": "...",
  // 缺少 xp, level, total_tasks_completed
}
```

**任务**：
1. 检查 `backend/app/routes/agents.py` 的返回数据
2. 确保包含：xp, level, total_tasks_completed, total_tasks_failed
3. 修改 `app/models.py` 的 AgentResponse 模型

**验收标准**：
- `GET /api/v1/agents/{id}` 返回数据包含游戏化字段
- 创建 agent 时这些字段有默认值（xp=0, level=1）

---

## 问题 6：初始 Credits 不对

**现象**：
注册用户的 `credit_balance = 10`（应该是 0 或 500）

**任务**：
1. 检查 `backend/app/routes/auth.py` 的注册逻辑
2. 设置初始余额为 **0**（暂时不实现 Credits 系统）
3. 或者改成 **500**（如果要启用 Credits）

**验收标准**：
- 新注册用户的 credit_balance 是确定的值（0 或 500）

---

## 问题 7：表结构字段名不一致

**现象**：
数据库用 `owner_id`, `reward_points`, `deliverable`  
但前端可能期望 `creator_id`, `reward_credits`, `result`

**任务**：
1. **决定**：统一用旧字段还是新字段
2. **如果用旧字段**（推荐，因为数据库已经是旧的）：
   - 检查 `frontend/lib/api/tasks.ts` 和所有前端代码
   - 确保用 `owner_id`, `reward_points`, `deliverable`
3. **如果用新字段**：
   - 写 migration 重命名字段
   - 修改所有后端代码

**建议**：用旧字段，改前端（改动小）

**验收标准**：
- 前后端字段名一致
- 任务详情页能显示结果

---

## 实现顺序

### 优先级 P0（最重要）
1. 修复任务详情接口 → 用户能看到结果
2. 修复通知接口 → 用户知道任务进度

### 优先级 P1
3. 修复游戏化接口 404
4. 完成任务后奖励 XP
5. Agent API 返回游戏化字段

### 优先级 P2
6. 初始 Credits 值
7. 字段名统一

---

## 部署流程

修复完成后：
1. `git add -A && git commit -m "fix: 修复端到端测试问题"`
2. `git push origin main`
3. `cd backend && railway up`（手动触发部署）
4. 等待 2 分钟
5. 重新跑端到端测试验证

---

## 验收标准（完整流程）

修复完成后，这个流程应该能完整跑通：

```bash
# 1. 注册
curl -X POST .../auth/register -d '{...}'

# 2. 创建 Agent
curl -X POST .../agents -H "Authorization: Bearer $TOKEN" -d '{...}'

# 3. 发布任务
curl -X POST .../tasks -H "Authorization: Bearer $TOKEN" -d '{...}'

# 4. Agent 接单
curl -X POST .../tasks/{id}/claim -H "Authorization: Bearer $AGENT_TOKEN"

# 5. Agent 完成任务
curl -X POST .../tasks/{id}/complete -H "Authorization: Bearer $AGENT_TOKEN" -d '{...}'

# 6. 查看任务详情（✅ 应该能看到结果）
curl .../tasks/{id} -H "Authorization: Bearer $TOKEN"

# 7. 查看通知（✅ 应该有 2 条：接单 + 完成）
curl .../notifications -H "Authorization: Bearer $TOKEN"

# 8. 查看 Agent 统计（✅ 应该显示 xp=50, level=1 或 2）
curl .../gamification/agent/{agent_id}/stats
```

所有接口都应该返回正常数据，不能有报错！
