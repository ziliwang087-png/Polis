# 第一轮前端代码审查 - 发现问题汇总

## 严重问题（必须立即修复）

### 1. messages/[user_id]/page.tsx - useEffect 依赖和内存泄漏
**位置**: 第 47-57 行
**问题**:
- useEffect 依赖数组缺少 `messagesApi`，违反 exhaustive-deps 规则
- forEach 循环中执行异步操作且没有错误处理
- markRead 请求失败会静默
- 组件卸载时请求可能仍在进行，导致内存泄漏

**影响**: 内存泄漏、控制台警告、功能可能失效
**优先级**: P0 - 立即修复

### 2. tasks/new/page.tsx - 文件上传无大小限制
**位置**: 第 20-30 行、第 46-50 行
**问题**:
- `readFileAsBase64` 函数没有文件大小限制
- 多个文件并行读取没有总大小限制
- 大文件可能导致浏览器内存耗尽或超出后端限制

**影响**: 用户体验差、可能导致浏览器崩溃
**优先级**: P1 - 高优先级

## 中等问题（应该修复）

### 3. tasks/new/page.tsx - budget 输入验证缺失
**位置**: 第 55 行
**问题**: `Number(budget)` 可能返回 NaN，没有验证
**影响**: 后端可能收到无效数据
**优先级**: P2 - 中优先级

### 4. agents/page.tsx 和 community/page.tsx - 用户体验问题
**位置**: 
- agents/page.tsx 第 215 行
- community/page.tsx 第 315 行
**问题**: 使用原生 `confirm()` 对话框，用户体验不佳
**影响**: 用户体验
**优先级**: P2 - 中优先级

### 5. agents/page.tsx - mutation 缺少反馈
**位置**: 第 205-212 行
**问题**: 
- heartbeat 和 remove mutation 缺少 onError 处理
- heartbeat 成功后没有 toast 提示
**影响**: 用户不知道操作是否成功/失败
**优先级**: P2 - 中优先级

## 低优先级问题

### 6. tasks/[id]/page.tsx - UI 逻辑不合理
**位置**: 第 96-98 行、第 334 行
**问题**: 
- 下拉框有空 option，但代码会自动选择第一个 agent
- 用户无法真正清空选择
**影响**: 用户体验轻微不一致
**优先级**: P3 - 低优先级

### 7. community/page.tsx - 多余括号
**位置**: 第 311 行
**问题**: `user && (user.id === post.author_id)` 有多余括号
**影响**: 无实际影响，代码风格
**优先级**: P3 - 低优先级

---

## 修复计划

### 立即修复（P0-P1）:
1. ✅ messages useEffect 内存泄漏
2. ✅ 文件上传大小限制

### 后续修复（P2-P3）:
3. budget NaN 验证
4. 改进 confirm 对话框
5. 添加 mutation 错误处理和反馈
6. 优化 agent 选择逻辑
7. 清理多余括号
