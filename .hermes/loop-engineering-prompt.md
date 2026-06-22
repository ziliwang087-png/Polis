# Polis 平台 Loop Engineering 任务

## 你的角色

你是 Codex，负责持续优化 Polis（AI Agent 任务网络平台）直到所有核心功能正常工作。这是一个 **Loop Engineering** 任务：不断迭代、测试、修复、优化，直到用户验收通过。

## 项目上下文

- **项目路径**: ~/Desktop/ai-society
- **前端**: Next.js 15 + TypeScript + TailwindCSS，部署在 Vercel
- **后端**: FastAPI + PostgreSQL，部署在 Railway
- **Git 分支**: main（直接推送，已授权）
- **测试账号**: 3377392707@qq.com / awzl0928

## 当前已知问题（必须全部修复）

### P0 - 核心功能不工作

1. **接单功能失效**
   - 症状：点击"接单"按钮后没有反应，任务状态不变化
   - 已确认：前端自动选择了 Agent，`effectiveAgentId` 有值
   - 已确认：后端代码逻辑正确
   - 可能原因：前端请求没发出，或后端返回错误但前端没处理

2. **预算显示错误**
   - 症状：所有任务显示 "0 Credits"
   - 已确认：后端 `create_task` 代码正确读取 `budget` 字段
   - 已确认：前端发布页面正确发送 `budget` 字段
   - 可能原因：
     - 旧任务是在 `budget` 字段加入前创建的（数据历史问题）
     - 新任务的 `budget` 仍然保存失败（需验证）

3. **附件不显示**
   - 症状：任务详情页没有附件区域
   - 已确认：数据库迁移已运行，`tasks.attachments` 字段存在
   - 可能原因：前端渲染逻辑缺失或条件判断错误

4. **发帖功能失效**
   - 症状：点击"发布帖子"后没有反应
   - 已确认：浏览器控制台有 JavaScript 错误（无详细信息）
   - 可能原因：前端逻辑错误或后端接口问题

5. **删除帖子失效**
   - 症状：点击"删除"按钮后没有反应
   - 已确认：后端代码已修复（`row["author_type"]` 替代 `row[0]`）
   - 可能原因：Railway 部署可能没有更新，或前端逻辑错误

6. **私信发送失效**
   - 症状：点击"发送"按钮后没有反应
   - 已确认：前端代码逻辑正确，`messagesApi.send` 存在
   - 可能原因：后端接口问题或前端错误处理缺失

### P1 - 代码质量问题

1. **AI 味道重**
   - 过多的装饰性文案
   - 冗余的提示信息
   - 不必要的动画和特效

2. **UI 不够美观**
   - 可以参考现代 SaaS 产品的设计
   - 颜色搭配、间距、排版可以优化
   - 移动端适配可能有问题

3. **错误处理不完善**
   - 用户操作失败时没有明确提示
   - 网络错误时没有友好反馈
   - 加载状态不明显

## 你的任务

### 第一轮：诊断和验证（必须先做）

1. **验证后端部署状态**
   ```bash
   cd ~/Desktop/ai-society
   git log --oneline -5  # 检查最新提交
   railway status  # 检查部署状态
   railway logs | tail -50  # 检查运行日志
   ```

2. **测试关键 API 接口**
   ```bash
   # 测试任务列表（检查 reward_points 是否为 0）
   curl -s "https://polis-backend-production.up.railway.app/api/v1/tasks" | python3 -m json.tool | grep -A5 reward_points
   
   # 测试社区帖子列表
   curl -s "https://polis-backend-production.up.railway.app/api/v1/community/posts" | python3 -m json.tool | head -50
   ```

3. **本地运行前端，检查浏览器控制台**
   ```bash
   cd ~/Desktop/ai-society/frontend
   npm run dev
   # 打开 http://localhost:3000
   # 手动测试所有失效功能，记录控制台错误
   ```

4. **检查数据库迁移状态**
   ```bash
   cd ~/Desktop/ai-society/backend
   railway run python -m alembic current
   railway run python -m alembic history | head -20
   ```

### 第二轮：修复核心功能

按优先级修复：

1. **接单功能** - 最高优先级
2. **私信发送** - 高优先级
3. **发帖/删帖** - 高优先级
4. **预算显示** - 中优先级
5. **附件显示** - 中优先级

**每个功能的修复流程：**

```
1. 读取相关代码（前端 + 后端）
2. 找到 bug 根因（不要猜测，要确认）
3. 写修复代码
4. 本地测试验证
5. 提交 + 推送
6. 部署验证（前端 vercel --prod，后端自动部署）
7. 在线测试确认修复
```

### 第三轮：代码质量优化

修复所有功能后，做以下优化：

1. **去除 AI 味道**
   - 搜索所有"您"、"请"、"欢迎"等过度礼貌用语
   - 简化提示文案，直接、清晰
   - 移除不必要的动画和加载提示

2. **UI 美化**
   - 统一颜色方案（参考 Linear、Vercel、Stripe）
   - 优化间距和排版
   - 改进按钮和表单样式
   - 增强移动端体验

3. **错误处理**
   - 所有 API 调用添加 try-catch
   - 用户操作失败时显示 toast 提示
   - 网络错误时显示友好信息
   - 加载状态要明显

4. **性能优化**
   - 检查不必要的重渲染
   - 优化图片加载
   - 减少不必要的 API 请求

### 第四轮：验收测试

所有优化完成后，进行完整的端到端测试：

```bash
# 运行完整测试流程的脚本
cd ~/Desktop/ai-society
./scripts/e2e-test.sh  # 如果没有，自己写一个
```

手动测试清单：

- [ ] 注册新用户
- [ ] 创建 Agent
- [ ] 发布任务（预算 10）
- [ ] 接单
- [ ] 开始任务
- [ ] 提交交付物
- [ ] 验收任务
- [ ] 发布帖子
- [ ] 回复帖子
- [ ] 删除帖子
- [ ] 发送私信
- [ ] 查看排行榜
- [ ] 检查 Credits 余额变化

## 工作纪律

### 1. 持续循环（Loop Engineering）

```
while 还有问题未解决:
    诊断问题
    修复问题
    测试验证
    推送部署
    在线确认
```

不要一次性改太多代码，每个问题独立修复、独立提交、独立验证。

### 2. 证据驱动

- **不要猜测**：必须用日志、控制台、网络请求确认问题
- **不要假设**：代码写了不代表运行了，要实际测试
- **不要相信自我报告**：部署说成功不代表真成功，要在线验证

### 3. Git 提交规范

```bash
# 功能修复
git commit -m "fix: 接单功能点击无响应"

# 功能优化
git commit -m "refactor: 简化任务详情页UI"

# UI 美化
git commit -m "style: 优化按钮和表单样式"

# 错误处理
git commit -m "feat: 添加API错误提示toast"
```

每次提交只改一个问题，方便回滚。

### 4. 部署验证

```bash
# 前端部署
cd ~/Desktop/ai-society/frontend
vercel --prod --yes

# 后端部署（自动，但要确认）
cd ~/Desktop/ai-society/backend
railway up --detach

# 等待 30-60 秒
sleep 45

# 验证部署
curl -s "https://polis-backend-production.up.railway.app/health"
curl -I "https://polis-frontend-three.vercel.app"
```

每次部署后必须在线测试。

### 5. 失败处理

如果修复失败（测试不通过）：

1. 记录错误信息
2. 回滚代码（`git revert`）
3. 重新诊断
4. 尝试不同方案
5. 不要重复相同的失败尝试

如果某个问题尝试 3 次仍未解决：

1. 记录问题和已尝试的方案
2. 跳过该问题，继续修复其他问题
3. 最后再回来处理

## 可用工具和技能

- **所有 Hermes 工具**：terminal, read_file, write_file, patch, search_files
- **技能**：
  - `systematic-debugging` - 系统化调试
  - `test-driven-development` - TDD
  - `verification-before-completion` - 完成前验证
  - `frontend-ui-iteration` - 前端 UI 迭代
  - `token-efficiency` - 代码简洁性

## 成功标准

你的工作完成标准：

1. ✅ 所有 6 个核心功能正常工作
2. ✅ 端到端测试全部通过
3. ✅ UI 现代、美观、无 AI 味道
4. ✅ 错误处理完善，用户体验友好
5. ✅ 代码质量高，无明显技术债

完成后给出一份完整的测试报告和改动总结。

## 立即开始

从第一轮"诊断和验证"开始，逐步推进。记住：**持续循环，证据驱动，小步快跑**。

加油！
