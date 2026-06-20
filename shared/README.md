# 共享接口契约目录（shared/）

> 这个目录用于在 backend 和 frontend 之间传递接口契约，避免两个 worker 撞车。
> 编写时间：2026-06-20 19:35 AEST

## 文件清单

| 文件 | 写入方 | 读取方 | 说明 |
|---|---|---|---|
| `openapi.json` | codex（后端） | claude-code（前端） | 后端跑起来后导出，前端用 openapi-typescript 生成 types |
| `types.ts` | claude-code 自动生成 | claude-code 自己用 | 不用手动维护 |
| `events.md` | codex | claude-code | SSE 事件格式说明（如果 OpenAPI 表达不了） |
| `seed-data.md` | codex | claude-code | 测试用的种子数据（用户、agent、capability） |

## 工作流

1. codex 后端跑起来后：
   ```bash
   cd /Users/a1111/projects/ai-society/backend
   curl http://localhost:8000/openapi.json > ../shared/openapi.json
   git add ../shared/openapi.json
   git commit -m "feat(shared): export OpenAPI schema for frontend"
   ```

2. claude-code 前端拿到后：
   ```bash
   cd /Users/a1111/projects/ai-society/frontend
   npx openapi-typescript ../shared/openapi.json -o lib/api/types.ts
   ```

3. jarvis 协调：
   - 等 codex commit openapi.json 后，立刻通知 claude-code
   - claude-code 拿到后端 schema 才开始写 API 调用层

## 禁止

- ❌ codex 不要碰 frontend/ 任何文件
- ❌ claude-code 不要碰 backend/ 任何文件
- ❌ 两个都不要碰 shared/ 之外的根目录配置（git、rm、Makefile 等由 jarvis 处理）
