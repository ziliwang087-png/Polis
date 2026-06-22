# Polis Pivot 计划：从"任务市场"到"Agent 订阅平台"

## 🎯 核心问题
**致命矛盾：** 用户直接问 Claude 5分钟搞定，为什么要在 Polis 发任务等几小时？

## 💡 解决方案
从"一次性任务市场"变成"持续订阅服务平台"

```
❌ 旧：用户发任务 → Agent接单 → 等待 → 完成（单次）
✅ 新：用户订阅Agent → Agent 7x24 自动工作 → 持续推送结果
```

## 🎪 为什么这能成功？

| 维度 | Claude | 旧Polis | 新Polis |
|------|--------|---------|---------|
| 响应速度 | 5分钟 | 几小时 | **实时/自动** |
| 持续性 | ❌ 对话式 | ❌ 单次 | ✅ **7x24运行** |
| 适用场景 | 问答 | 单次任务 | **监控/自动化** |
| Claude能做吗 | ✅ | ✅ | ❌ **做不了** |

---

## 🚀 Phase 1：MVP 验证（本周完成）

### 方向1：价格监控平台（最推荐）

**产品定位：** AI Agent 帮你 7x24 监控商品价格

**用户场景：**
1. 电商从业者：监控竞品/供应商价格
2. 羊毛党：等商品降价/优惠
3. 采购员：监控原材料价格

**MVP 功能：**
- [ ] 创建监控任务：输入商品链接（京东/淘宝/1688）
- [ ] Agent 每小时自动检查价格
- [ ] 价格变化时微信/邮件通知
- [ ] 价格历史曲线图

**收费模式：**
- 免费版：监控 3 个商品
- 基础版：29元/月，监控 20 个商品
- 专业版：99元/月，监控 100 个商品 + API

**技术实现：**
- 复用现有 Task 表，增加 `recurring=true` 字段
- 增加 `subscriptions` 表记录订阅关系
- 写一个定时任务（Celery/APScheduler）执行 Agent
- 通知用企业微信/邮件/Webhook

**验证目标：**
- 找 10 个真实用户试用
- 至少 3 个愿意付费
- 每个用户平均创建 > 5 个监控任务

---

### 方向2：竞品监控平台

**产品定位：** 自动抓取竞品动态，生成分析报告

**用户场景：**
1. 创业者：监控竞品产品迭代
2. 产品经理：收集竞品信息
3. 市场部：监控竞品营销动作

**MVP 功能：**
- [ ] 添加竞品：输入官网/公众号/小红书账号
- [ ] Agent 每天抓取更新
- [ ] 生成每日/每周竞品报告
- [ ] 关键动作提醒（新功能/促销/融资）

**收费模式：**
- 99元/月/竞品
- 299元/月监控 5 个竞品

**验证目标：**
- 找 5 个创业者试用
- 至少 2 个愿意续费第二个月

---

### 方向3：社交媒体自动化

**产品定位：** AI Agent 自动运营你的社交媒体账号

**用户场景：**
1. 自媒体：自动发内容保持活跃
2. 企业：自动运营品牌账号
3. 个人IP：持续输出内容

**MVP 功能：**
- [ ] 设置账号和风格
- [ ] Agent 自动生成内容
- [ ] 定时发布（小红书/B站/公众号）
- [ ] 自动回复评论

**收费模式：**
- 199元/月/账号

**风险：** 平台可能封号，需要谨慎

---

## 🛠️ 技术改造（利用现有代码 80%）

### 改造1：任务模型支持订阅

**新增表：`subscriptions`**
```sql
CREATE TABLE subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES owners(id),
    agent_id UUID NOT NULL REFERENCES agents(id),
    subscription_type VARCHAR(50) NOT NULL, -- 'price_monitor', 'competitor_watch', 'social_auto'
    config JSONB NOT NULL DEFAULT '{}', -- 订阅配置（监控的商品/竞品/账号等）
    status VARCHAR(20) NOT NULL DEFAULT 'active', -- 'active', 'paused', 'expired'
    billing_cycle VARCHAR(20) DEFAULT 'monthly', -- 'monthly', 'yearly'
    price_cents INTEGER NOT NULL, -- 价格（分）
    next_billing_date TIMESTAMP,
    last_execution_at TIMESTAMP,
    execution_frequency VARCHAR(50) DEFAULT 'hourly', -- 'hourly', 'daily', 'weekly'
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_subscriptions_user ON subscriptions(user_id);
CREATE INDEX idx_subscriptions_agent ON subscriptions(agent_id);
CREATE INDEX idx_subscriptions_status ON subscriptions(status);
```

**修改 `tasks` 表：**
```sql
ALTER TABLE tasks ADD COLUMN recurring BOOLEAN DEFAULT FALSE;
ALTER TABLE tasks ADD COLUMN subscription_id UUID REFERENCES subscriptions(id);
ALTER TABLE tasks ADD COLUMN next_run_at TIMESTAMP;
```

### 改造2：增加订阅 API

**新建：`backend/app/routes/subscriptions.py`**
```python
from fastapi import APIRouter, Depends, HTTPException
from app.models import SubscriptionCreateRequest, SubscriptionResponse
from app.auth import get_current_user

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])

@router.post("/")
async def create_subscription(
    req: SubscriptionCreateRequest,
    current_user = Depends(get_current_user)
):
    """创建订阅"""
    # 1. 验证用户有足够余额/绑定了支付方式
    # 2. 创建订阅记录
    # 3. 创建第一个执行任务
    # 4. 返回订阅ID
    pass

@router.get("/")
async def list_subscriptions(current_user = Depends(get_current_user)):
    """查看我的订阅"""
    pass

@router.post("/{subscription_id}/pause")
async def pause_subscription(subscription_id: UUID, current_user = Depends(get_current_user)):
    """暂停订阅"""
    pass

@router.delete("/{subscription_id}")
async def cancel_subscription(subscription_id: UUID, current_user = Depends(get_current_user)):
    """取消订阅"""
    pass
```

### 改造3：定时任务调度器

**新建：`backend/app/scheduler.py`**
```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, timedelta

scheduler = AsyncIOScheduler()

async def execute_subscriptions():
    """每小时执行一次，检查需要运行的订阅"""
    # 1. 查询 status='active' 且 next_run_at <= now 的订阅
    # 2. 为每个订阅创建一个新的 task
    # 3. 触发对应的 Agent 执行
    # 4. 更新 last_execution_at 和 next_run_at
    pass

scheduler.add_job(execute_subscriptions, 'interval', hours=1)
```

### 改造4：通知系统

**复用现有 `notifications` 表，增加通知渠道**
```python
async def send_notification(user_id: UUID, title: str, content: str, type: str = "price_change"):
    # 1. 写入 notifications 表（现有）
    # 2. 发送微信模板消息（新增）
    # 3. 发送邮件（新增）
    pass
```

---

## 📊 Phase 2：数据验证（2周内）

### 关键指标
1. **注册用户数** ≥ 50
2. **活跃订阅数** ≥ 20
3. **付费转化率** ≥ 10%
4. **月留存率** ≥ 60%

### 如果失败
- 注册 < 50：推广渠道有问题，换渠道
- 订阅 < 20：产品价值不够，换方向
- 付费 < 10%：定价有问题或价值不够
- 留存 < 60%：Agent 质量差或通知打扰

---

## 💰 Phase 3：商业化（1个月内）

### 收入模式
1. **订阅费**（主要）：用户按月付费
2. **增值服务**：
   - API 调用：0.1元/次
   - 更高频率监控：hourly → every 10min
   - 历史数据导出
3. **企业版**：定制监控 + 私有部署

### 成本
- 服务器：100元/月（初期）
- 爬虫代理：500元/月
- AI 调用（Claude/GPT）：根据使用量，预估 1000元/月
- **总成本：1600元/月**

### 盈亏平衡
- 如果定价 29元/月
- 需要 **60 个付费用户** 即可盈亏平衡

---

## 🎬 本周行动清单

### Day 1-2：快速验证需求
- [ ] 在朋友圈/微信群发问卷：你会用价格监控工具吗？愿意付费吗？
- [ ] 找 10 个潜在用户深度访谈（30分钟/人）
- [ ] 确定最终方向（价格监控 / 竞品监控 / 社交自动化）

### Day 3-4：MVP 开发
- [ ] 数据库改造（增加 subscriptions 表）
- [ ] 订阅 API（创建/查看/暂停/取消）
- [ ] 定时任务调度器
- [ ] 简单的通知系统（邮件）

### Day 5-6：MVP 上线
- [ ] 找 5 个用户内测
- [ ] 收集反馈
- [ ] 快速迭代

### Day 7：决策
- [ ] 如果有 3+ 个人愿意付费 → 继续做
- [ ] 如果没人愿意付费 → Pivot 或放弃

---

## 🤔 为什么我推荐"价格监控"方向？

### 优势
1. ✅ **需求明确**：淘宝/京东商家每天都在监控竞品价格
2. ✅ **技术简单**：爬虫 + 定时任务，1周能做出来
3. ✅ **付费意愿强**：To B 场景，能帮商家赚钱
4. ✅ **冷启动容易**：你自己做几个示例，用户直接用
5. ✅ **Claude 做不了**：需要持续运行，Claude 只能对话

### 劣势
1. ⚠️ 反爬虫：需要代理IP，成本略高
2. ⚠️ 竞争：有一些现有工具（但大多针对 C 端，B 端机会大）

### 竞品分析
- **价格跟踪器**（Chrome插件）：针对 C 端，功能简单
- **店透视**：针对淘宝卖家，但很贵（几百/月）
- **你的机会**：做轻量级、便宜的 SaaS 版本

---

## 🎯 最终建议

**如果是我，我会：**

1. **本周末**：做一个最简单的 MVP
   - 用 Streamlit 做个简单前端
   - 手动运行爬虫脚本（不用定时任务）
   - 邮件通知（不用微信）
   
2. **下周**：找 10 个电商从业者试用
   - 去电商相关的微信群/知识星球发
   - 免费试用 1 个月，收集反馈
   
3. **2周后**：决定是否继续
   - 如果有 3+ 人愿意付费 → 继续做，全力投入
   - 如果没人愿意付费 → 换方向或放弃

**关键：不要花太多时间，快速验证需求真实性！**

---

## 📞 需要我帮你做什么？

1. **写 MVP 代码**：我可以帮你改造现有代码，增加订阅功能
2. **设计问卷/访谈提纲**：验证需求真实性
3. **爬虫脚本**：写个简单的价格爬虫
4. **前端页面**：用 Streamlit/React 做个简单界面
5. **推广文案**：写朋友圈/微信群的推广文案

你现在想：
- A. 立即开始改代码（我帮你写）
- B. 先验证需求（我帮你设计问卷）
- C. 深入分析某个具体方向
- D. 其他想法？
