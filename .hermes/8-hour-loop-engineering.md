# Polis 8 小时全方位 Loop Engineering

**开始时间**: 2026-06-22 23:08  
**结束时间**: 2026-06-23 07:08  
**总时长**: 8 小时

---

## 你的任务

你是 code profile worker，负责在接下来的 **8 小时内持续工作**，对 Polis 平台进行全方位的审查、优化和 bug 修复。

**重要规则：**
1. ⏰ **必须持续工作 8 小时** - 不是看工作量，是看时间
2. 🔄 **持续 Loop** - 完成一轮后立即开始下一轮
3. 🔍 **每轮深入审查** - 至少审查 3 遍，每遍关注不同维度
4. 📝 **每小时汇报进度** - 用 `hermes kanban comment <task_id> "进度更新"` 报告
5. 📊 **最后生成完整报告** - 包含所有发现的问题、修复记录、代码改进

---

## Loop 工作流程（持续 8 小时）

### 第一轮：深度代码审查（2 小时）

**目标：找出所有潜在 bug 和代码质量问题**

#### 1.1 前端代码审查（60 分钟）

逐文件检查：

**核心页面：**
- `app/tasks/[id]/page.tsx` - 任务详情
- `app/tasks/new/page.tsx` - 发布任务
- `app/community/page.tsx` - 社区
- `app/messages/[user_id]/page.tsx` - 私信
- `app/agents/page.tsx` - Agent 列表
- `app/leaderboard/page.tsx` - 排行榜

**检查维度：**
- [ ] TypeScript 类型安全（any 类型、类型断言）
- [ ] React Hooks 依赖数组正确性
- [ ] 内存泄漏风险（未清理的 useEffect）
- [ ] 边界条件处理（空数组、null、undefined）
- [ ] 错误处理完整性（所有 API 调用）
- [ ] 性能问题（不必要的重渲染、大列表）
- [ ] 安全隐患（XSS、注入、敏感信息）
- [ ] 可访问性（a11y）

**记录格式：**
```markdown
### 文件: app/tasks/[id]/page.tsx
- ❌ 第 123 行：useEffect 缺少清理函数，可能导致内存泄漏
- ⚠️ 第 234 行：使用 any 类型，应该定义具体类型
- ✅ 错误处理完整
```

#### 1.2 后端代码审查（60 分钟）

逐文件检查：

**核心模块：**
- `app/routes/tasks.py` - 任务接口
- `app/routes/agents.py` - Agent 接口
- `app/routes/community.py` - 社区接口
- `app/routes/messages.py` - 私信接口
- `app/routes/auth.py` - 认证接口
- `app/models.py` - 数据模型
- `app/database.py` - 数据库连接

**检查维度：**
- [ ] SQL 注入防护
- [ ] 身份验证和授权
- [ ] 输入验证（Pydantic 模型）
- [ ] 错误处理和日志
- [ ] 并发安全（事务、锁）
- [ ] N+1 查询问题
- [ ] 资源泄漏（数据库连接）
- [ ] API 响应格式一致性

---

### 第二轮：UI/UX 优化（2 小时）

**目标：去除 AI 味道，提升用户体验**

#### 2.1 去除 AI 味道（30 分钟）

**搜索并替换：**
```bash
# 搜索过度礼貌用语
rg -i "您|请|欢迎|尊敬的|亲爱的|感谢|荣幸" --glob "*.tsx" --glob "*.ts"

# 搜索冗余提示
rg -i "温馨提示|友情提醒|小贴士|注意事项" --glob "*.tsx"

# 搜索过度装饰
rg "✨|🎉|💡|⭐|👏" --glob "*.tsx"
```

**优化原则：**
- 直接、清晰、简洁
- 用"我"代替"您"
- 用祈使句代替请求句
- 去除表情符号和装饰文字

**示例：**
- ❌ "欢迎您使用 Polis 平台！"
- ✅ "Polis"

- ❌ "请您填写任务描述"
- ✅ "任务描述"

- ❌ "感谢您的反馈！我们会尽快处理"
- ✅ "已收到反馈"

#### 2.2 UI 美化（90 分钟）

**参考设计系统：**
- Linear - https://linear.app
- Vercel - https://vercel.com
- Stripe - https://stripe.com

**优化重点：**

1. **颜色系统统一**
   - 主色调：蓝色系
   - 辅助色：灰色系
   - 成功/警告/错误：语义化颜色
   - 减少颜色种类（最多 5-7 种）

2. **间距和排版**
   - 统一 spacing scale（4px 基准）
   - 行高：1.5-1.6
   - 字号：12/14/16/18/24/32/48
   - 容器最大宽度：1200px

3. **组件一致性**
   - 按钮统一样式（primary/secondary/ghost）
   - 表单输入统一高度（40px/44px）
   - 卡片统一圆角（8px）
   - 阴影统一（0-3 档）

4. **响应式优化**
   - 移动端断点：640px/768px/1024px
   - 触摸目标最小 44x44px
   - 移动端导航优化

5. **加载状态**
   - 骨架屏代替 loading spinner
   - 按钮 loading 状态清晰
   - 页面过渡动画流畅

---

### 第三轮：性能优化（2 小时）

**目标：提升应用性能和用户体验**

#### 3.1 前端性能（60 分钟）

**检查项：**
- [ ] React Query 缓存策略
- [ ] 图片懒加载和优化
- [ ] 代码分割（动态 import）
- [ ] 不必要的重渲染
- [ ] 大列表虚拟化
- [ ] Bundle 大小分析

**优化：**
1. **React Query 优化**
   ```typescript
   // 设置全局默认缓存策略
   const queryClient = new QueryClient({
     defaultOptions: {
       queries: {
         staleTime: 5 * 60 * 1000, // 5 分钟
         cacheTime: 10 * 60 * 1000, // 10 分钟
         refetchOnWindowFocus: false,
       },
     },
   });
   ```

2. **Image 优化**
   ```typescript
   // 使用 Next.js Image 组件
   import Image from 'next/image';
   <Image src="..." width={} height={} alt="" loading="lazy" />
   ```

3. **代码分割**
   ```typescript
   // 动态导入大组件
   const HeavyComponent = dynamic(() => import('./HeavyComponent'), {
     loading: () => <Skeleton />,
   });
   ```

#### 3.2 后端性能（60 分钟）

**检查项：**
- [ ] N+1 查询问题
- [ ] 缺少数据库索引
- [ ] 慢查询日志
- [ ] 连接池配置
- [ ] 缓存策略

**优化：**
1. **添加索引**
   ```sql
   -- 检查常用查询
   CREATE INDEX idx_tasks_status ON tasks(status);
   CREATE INDEX idx_tasks_owner ON tasks(owner_id);
   ```

2. **优化查询**
   ```python
   # 使用 JOIN 避免 N+1
   SELECT tasks.*, users.name 
   FROM tasks 
   LEFT JOIN users ON tasks.owner_id = users.id
   ```

---

### 第四轮：安全加固（1 小时）

**目标：消除安全隐患**

#### 4.1 前端安全（30 分钟）

**检查项：**
- [ ] XSS 防护（用户输入渲染）
- [ ] CSRF token
- [ ] 敏感信息泄漏（console.log）
- [ ] 客户端存储安全（localStorage）
- [ ] API key 暴露

**修复：**
```typescript
// 移除所有 dangerouslySetInnerHTML
// 清理 console.log
// 敏感信息用环境变量
```

#### 4.2 后端安全（30 分钟）

**检查项：**
- [ ] SQL 注入防护
- [ ] 身份验证完整性
- [ ] 授权检查（owner/agent 权限）
- [ ] 输入验证
- [ ] 密码存储（bcrypt）
- [ ] Rate limiting

**修复：**
```python
# 确保所有端点都有身份验证
# 确保授权检查（用户只能操作自己的资源）
# 添加 rate limiting
```

---

### 第五轮：测试覆盖（1 小时）

**目标：确保关键功能有测试保护**

#### 5.1 前端测试（30 分钟）

**优先级：**
1. 关键用户流程（发布任务、接单、验收）
2. 表单验证逻辑
3. API 错误处理

**示例：**
```typescript
// tests/tasks.test.tsx
describe('Task Creation', () => {
  it('should validate required fields', () => {
    // ...
  });
  
  it('should handle API errors', () => {
    // ...
  });
});
```

#### 5.2 后端测试（30 分钟）

**优先级：**
1. 核心 API 端点
2. 身份验证/授权
3. 边界条件

**示例：**
```python
# tests/test_tasks.py
def test_create_task_requires_auth():
    response = client.post("/api/v1/tasks", json={...})
    assert response.status_code == 401

def test_claim_task_checks_ownership():
    # ...
```

---

### 第六轮：文档和注释（30 分钟）

**目标：提升代码可维护性**

**检查项：**
- [ ] 关键函数有注释
- [ ] 复杂逻辑有说明
- [ ] API 端点有文档
- [ ] README 更新
- [ ] 环境变量文档

**添加：**
```typescript
/**
 * 处理任务接单逻辑
 * @param taskId - 任务 ID
 * @param agentId - Agent ID
 * @returns 更新后的任务对象
 * @throws {Error} 当任务不存在或已被接单时
 */
async function claimTask(taskId: string, agentId: string) {
  // ...
}
```

---

### 第七轮：最终验收（30 分钟）

**端到端测试：**

1. **用户注册/登录流程**
2. **创建 Agent**
3. **发布任务（预算 10）**
4. **Agent 接单**
5. **开始工作**
6. **提交交付物**
7. **Owner 验收**
8. **评分**
9. **发帖/评论/点赞**
10. **私信沟通**
11. **查看排行榜**
12. **检查 Credits 扣除/奖励**

**测试环境：**
- 浏览器：Chrome + Safari + Firefox
- 设备：Desktop + Mobile
- 网络：Fast 3G 模拟

---

## 每小时检查点

**在每个整点（00:08, 01:08, 02:08...）用这个命令报告进度：**

```bash
hermes kanban comment t_<task_id> "
【$(date '+%H:%M') 进度更新】
- 当前轮次：第 X 轮 / Y
- 已完成：...
- 发现问题：X 个
- 已修复：Y 个
- 下一步：...
"
```

---

## 工作纪律

### 持续 Loop 规则

```python
start_time = "23:08"
end_time = "07:08"  # 8 小时后

while current_time < end_time:
    # 执行当前轮次
    execute_current_round()
    
    # 完成后立即开始下一轮
    if all_rounds_completed():
        # 重新开始第一轮，更深入审查
        restart_from_round_1()
    
    # 每小时报告
    if is_full_hour():
        report_progress()
```

### 深度审查原则

1. **第一遍**：找明显问题（bug、错误、崩溃）
2. **第二遍**：找潜在问题（边界条件、性能、安全）
3. **第三遍**：找优化机会（代码质量、用户体验、可维护性）

### Git 提交原则

**小步提交，频繁推送：**

```bash
# 每修复一个问题立即提交
git add <files>
git commit -m "fix: 具体问题描述"
git push origin main

# 每完成一轮立即提交
git commit -m "refactor: 第 X 轮优化完成"
git push origin main
```

### 测试验证原则

**每次修改后必须：**

1. 本地测试验证
2. 构建测试（npm run build）
3. 类型检查（tsc --noEmit）
4. Linter 检查（npm run lint）
5. 推送部署
6. 在线验证

---

## 最终交付物

### 8 小时后必须提供：

1. **完整审查报告**
   - 发现的所有问题（分类、优先级）
   - 修复记录（每个问题的修复方案）
   - 未修复问题（原因说明）

2. **代码改动总结**
   - Git commit 历史
   - 修改文件统计
   - 新增/删除代码行数

3. **测试报告**
   - 端到端测试结果
   - 性能指标对比
   - 浏览器兼容性

4. **优化成果**
   - UI 改进前后对比
   - 性能提升数据
   - 代码质量指标

5. **建议清单**
   - 后续优化建议
   - 技术债务清单
   - 架构改进方向

---

## 成功标准

8 小时结束时，Polis 平台应该：

1. ✅ **零已知 bug** - 所有发现的 bug 都已修复
2. ✅ **高代码质量** - 无类型错误、无 linter 警告、无安全隐患
3. ✅ **现代 UI** - 无 AI 味道、美观、响应式
4. ✅ **良好性能** - 快速加载、流畅交互
5. ✅ **完善文档** - 代码注释、API 文档、README

---

## 开始工作

**当前时间**: 2026-06-22 23:08  
**结束时间**: 2026-06-23 07:08  

从第一轮"深度代码审查"开始，持续工作 8 小时。

**记住：不是看工作量，是看时间。必须持续 Loop 到 07:08。**

加油！💪
