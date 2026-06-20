"""
Polis v5.2 — 种子数据脚本
向数据库插入 20 条丰富的真实风格测试任务，让前端任务广场卡片有内容可展示。

设计目标：
- 7 个类别（医学/AI/设计/Web3/开发/调研/翻译）覆盖
- 难度分布：easy/medium/hard/expert 都有
- 信誉奖励 10–50
- 配套 cover_emoji + cover_gradient + skills_required
- 配套发布者画像（display_name / organization / rating / verified / avatar_gradient）
- 部分标记 urgent / featured
- view_count / favorite_count / comment_count / application_count 真实分布
- created_at 从几小时前到几天前散开

边界（来自任务卡）：
- 不删除 / 不修改原 2 条数据，只 INSERT 新增
- 数据库密码取自 .env，不写死
- 多次运行幂等：通过 title+owner_id 唯一性检测跳过已插入条目
"""
import os
import random
import sys
from datetime import datetime, timedelta

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL not set in .env", file=sys.stderr)
    sys.exit(1)

# ----------------------------------------------------------------
# 发布者画像池：6 个典型 owner，前端能看到不同组织背书
# ----------------------------------------------------------------
OWNER_PROFILES = [
    {
        "email": "research@stanford.med",
        "display_name": "Sarah Chen",
        "organization": "Stanford Medical Center",
        "rating": 4.9,
        "verified": True,
        "avatar_gradient": "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
    },
    {
        "email": "lab@deepmind.ai",
        "display_name": "Alex Rivera",
        "organization": "DeepMind Research",
        "rating": 4.8,
        "verified": True,
        "avatar_gradient": "linear-gradient(135deg, #f093fb 0%, #f5576c 100%)",
    },
    {
        "email": "studio@figma.design",
        "display_name": "Mika Tanaka",
        "organization": "Figma Studio Asia",
        "rating": 4.7,
        "verified": True,
        "avatar_gradient": "linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)",
    },
    {
        "email": "build@uniswap.web3",
        "display_name": "DAO Builder",
        "organization": "Uniswap Foundation",
        "rating": 4.6,
        "verified": True,
        "avatar_gradient": "linear-gradient(135deg, #fa709a 0%, #fee140 100%)",
    },
    {
        "email": "tech@earlystage.io",
        "display_name": "Lin Wei",
        "organization": "EarlyStage Ventures",
        "rating": 4.5,
        "verified": False,
        "avatar_gradient": "linear-gradient(135deg, #30cfd0 0%, #330867 100%)",
    },
    {
        "email": "ops@globalvoice.cn",
        "display_name": "Hiro Sato",
        "organization": "Global Voice Translations",
        "rating": 4.4,
        "verified": True,
        "avatar_gradient": "linear-gradient(135deg, #a8edea 0%, #fed6e3 100%)",
    },
]

# ----------------------------------------------------------------
# 20 条任务种子
# 字段：title / description / category / difficulty / reward_points
#      cover_emoji / cover_gradient / skills_required
#      view_count / favorite_count / comment_count / application_count
#      urgent / featured / hours_ago / owner_idx (索引到 OWNER_PROFILES)
# ----------------------------------------------------------------
SEED_TASKS = [
    {  # 1. 医学
        "title": "整理 100 篇 mRNA 疫苗最新论文摘要",
        "description": "需要从 PubMed/bioRxiv 抓取 2024-2026 关于 mRNA 疫苗递送系统的论文，整理结构化摘要（机制/适应症/临床阶段）。输出 markdown 表格。",
        "category": "research", "difficulty": "hard", "reward_points": 45,
        "cover_emoji": "🧬", "cover_gradient": "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
        "skills_required": ["literature-review", "biomedicine", "structured-extraction"],
        "view_count": 1247, "favorite_count": 89, "comment_count": 23, "application_count": 12,
        "urgent": False, "featured": True, "hours_ago": 4, "owner_idx": 0,
    },
    {  # 2. 医学
        "title": "临床数据脱敏 + 统计学 P 值复核",
        "description": "对一组 2300 行病例数据做 HIPAA 合规脱敏（PHI 18 项），并用 R/python 复核原稿的 t-test / chi-square 计算。",
        "category": "research", "difficulty": "expert", "reward_points": 50,
        "cover_emoji": "🩺", "cover_gradient": "linear-gradient(135deg, #fa709a 0%, #fee140 100%)",
        "skills_required": ["statistics", "data-privacy", "R", "pandas"],
        "view_count": 532, "favorite_count": 41, "comment_count": 8, "application_count": 5,
        "urgent": True, "featured": False, "hours_ago": 9, "owner_idx": 0,
    },
    {  # 3. AI
        "title": "训练一个领域专属 RAG 微调模型",
        "description": "基于 Qwen2.5-7B 做法律领域 LoRA 微调，提供 10k 条 SFT 数据。要求 lm-eval-harness 上 LegalBench 提升 ≥5 分。",
        "category": "ai", "difficulty": "expert", "reward_points": 50,
        "cover_emoji": "🤖", "cover_gradient": "linear-gradient(135deg, #f093fb 0%, #f5576c 100%)",
        "skills_required": ["LLM", "LoRA", "RAG", "evaluation"],
        "view_count": 2103, "favorite_count": 178, "comment_count": 45, "application_count": 23,
        "urgent": False, "featured": True, "hours_ago": 6, "owner_idx": 1,
    },
    {  # 4. AI
        "title": "用 DSPy 重写 prompt 链路提升准确率",
        "description": "现有 4 段手写 prompt（客服分类→意图抽取→回复生成→质检），用 DSPy 重写并自动优化，目标 F1 +0.08。",
        "category": "ai", "difficulty": "medium", "reward_points": 30,
        "cover_emoji": "✨", "cover_gradient": "linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)",
        "skills_required": ["DSPy", "prompt-engineering", "Python"],
        "view_count": 891, "favorite_count": 62, "comment_count": 14, "application_count": 9,
        "urgent": False, "featured": False, "hours_ago": 18, "owner_idx": 1,
    },
    {  # 5. AI
        "title": "实现一个 Agent 协作调度器原型",
        "description": "Python + asyncio，支持 ≥5 agent 并行 / 超时重试 / 任务依赖 DAG。提交可运行 demo 与 README。",
        "category": "ai", "difficulty": "hard", "reward_points": 40,
        "cover_emoji": "🧠", "cover_gradient": "linear-gradient(135deg, #30cfd0 0%, #330867 100%)",
        "skills_required": ["Python", "asyncio", "multi-agent", "system-design"],
        "view_count": 1445, "favorite_count": 113, "comment_count": 28, "application_count": 17,
        "urgent": False, "featured": True, "hours_ago": 30, "owner_idx": 4,
    },
    {  # 6. 设计
        "title": "为 fintech 钱包 App 设计 12 个图标",
        "description": "Material 风格，2 套主题（亮 / 暗），导出 SVG + PNG@3x。要求统一描边粗细 1.5px，圆角 4px。",
        "category": "design", "difficulty": "medium", "reward_points": 25,
        "cover_emoji": "🎨", "cover_gradient": "linear-gradient(135deg, #f093fb 0%, #f5576c 100%)",
        "skills_required": ["icon-design", "Figma", "SVG"],
        "view_count": 678, "favorite_count": 51, "comment_count": 11, "application_count": 8,
        "urgent": False, "featured": False, "hours_ago": 12, "owner_idx": 2,
    },
    {  # 7. 设计
        "title": "Landing Page 重设计（A/B 两套）",
        "description": "现有落地页转化率 1.8%，重新设计两版方向（极简 vs 视觉冲击），提供 Figma 链接和 desktop+mobile mockup。",
        "category": "design", "difficulty": "medium", "reward_points": 35,
        "cover_emoji": "🖼️", "cover_gradient": "linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)",
        "skills_required": ["UI", "Figma", "conversion-optimization"],
        "view_count": 1012, "favorite_count": 78, "comment_count": 19, "application_count": 14,
        "urgent": True, "featured": True, "hours_ago": 22, "owner_idx": 2,
    },
    {  # 8. 设计
        "title": "品牌 VI 视觉规范手册",
        "description": "为初创 SaaS 品牌制作 24 页 VI 规范（logo / 配色 / 字体 / 组件 / 物料），交付 PDF + 源文件。",
        "category": "design", "difficulty": "hard", "reward_points": 45,
        "cover_emoji": "💎", "cover_gradient": "linear-gradient(135deg, #a8edea 0%, #fed6e3 100%)",
        "skills_required": ["branding", "design-system", "typography"],
        "view_count": 567, "favorite_count": 44, "comment_count": 9, "application_count": 6,
        "urgent": False, "featured": False, "hours_ago": 48, "owner_idx": 2,
    },
    {  # 9. Web3
        "title": "审计 Solidity 借贷合约（2 周）",
        "description": "约 1200 行 Solidity，使用 Foundry + Slither + 手工审计，输出 PDF 报告（H/M/L/Info 分级）。",
        "category": "web3", "difficulty": "expert", "reward_points": 50,
        "cover_emoji": "🛡️", "cover_gradient": "linear-gradient(135deg, #fa709a 0%, #fee140 100%)",
        "skills_required": ["Solidity", "smart-contract-audit", "Foundry"],
        "view_count": 1893, "favorite_count": 167, "comment_count": 38, "application_count": 11,
        "urgent": True, "featured": True, "hours_ago": 3, "owner_idx": 3,
    },
    {  # 10. Web3
        "title": "搭一个 NFT mint dApp 前端",
        "description": "Next.js + wagmi + viem，连接 ERC-721 合约（已部署 Sepolia）。包含 wallet 连接、白名单、数量限制。",
        "category": "web3", "difficulty": "medium", "reward_points": 30,
        "cover_emoji": "🪙", "cover_gradient": "linear-gradient(135deg, #f093fb 0%, #f5576c 100%)",
        "skills_required": ["Next.js", "wagmi", "ERC-721"],
        "view_count": 745, "favorite_count": 56, "comment_count": 12, "application_count": 10,
        "urgent": False, "featured": False, "hours_ago": 36, "owner_idx": 3,
    },
    {  # 11. 开发
        "title": "把 monolith 拆成 3 个微服务",
        "description": "现有 Flask 单体（25 路由），按 user/order/billing 三个 bounded context 拆成 FastAPI 微服务，gRPC 通信，docker-compose 跑通。",
        "category": "development", "difficulty": "expert", "reward_points": 50,
        "cover_emoji": "⚙️", "cover_gradient": "linear-gradient(135deg, #30cfd0 0%, #330867 100%)",
        "skills_required": ["FastAPI", "gRPC", "Docker", "system-design"],
        "view_count": 2287, "favorite_count": 201, "comment_count": 52, "application_count": 19,
        "urgent": False, "featured": True, "hours_ago": 8, "owner_idx": 4,
    },
    {  # 12. 开发
        "title": "PostgreSQL 慢查询优化（5 个 SQL）",
        "description": "5 条核心查询执行时间从 2-12s 优化到 <300ms。允许加索引、改 schema、改写 SQL，提交 EXPLAIN ANALYZE 对比。",
        "category": "development", "difficulty": "hard", "reward_points": 35,
        "cover_emoji": "🗄️", "cover_gradient": "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
        "skills_required": ["PostgreSQL", "query-optimization", "indexing"],
        "view_count": 1156, "favorite_count": 87, "comment_count": 21, "application_count": 13,
        "urgent": True, "featured": False, "hours_ago": 14, "owner_idx": 4,
    },
    {  # 13. 开发
        "title": "GitHub Actions CI/CD 流水线搭建",
        "description": "Monorepo（python + node + go），要求：lint→test→build→docker push→k8s rollout，含 PR 预览环境。",
        "category": "development", "difficulty": "medium", "reward_points": 25,
        "cover_emoji": "🔧", "cover_gradient": "linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)",
        "skills_required": ["GitHub-Actions", "Docker", "Kubernetes"],
        "view_count": 623, "favorite_count": 42, "comment_count": 9, "application_count": 7,
        "urgent": False, "featured": False, "hours_ago": 26, "owner_idx": 4,
    },
    {  # 14. 开发
        "title": "修一个老 React 项目的内存泄漏",
        "description": "线上 SPA，浏览器持续运行 30 分钟内存涨到 1.2GB。提供 Chrome heap snapshot，找出泄漏 root 并修复。",
        "category": "development", "difficulty": "hard", "reward_points": 40,
        "cover_emoji": "🐛", "cover_gradient": "linear-gradient(135deg, #fa709a 0%, #fee140 100%)",
        "skills_required": ["React", "Chrome-DevTools", "performance"],
        "view_count": 834, "favorite_count": 64, "comment_count": 15, "application_count": 9,
        "urgent": True, "featured": False, "hours_ago": 5, "owner_idx": 4,
    },
    {  # 15. 调研
        "title": "全球 LLM 推理引擎横评",
        "description": "对比 vLLM / SGLang / TGI / Tensorrt-LLM 在 70B 模型上的吞吐 / 延迟 / 显存占用，写一份 8 页报告 + 复现脚本。",
        "category": "research", "difficulty": "hard", "reward_points": 40,
        "cover_emoji": "📊", "cover_gradient": "linear-gradient(135deg, #f093fb 0%, #f5576c 100%)",
        "skills_required": ["LLM-inference", "benchmarking", "technical-writing"],
        "view_count": 1768, "favorite_count": 142, "comment_count": 31, "application_count": 16,
        "urgent": False, "featured": True, "hours_ago": 16, "owner_idx": 1,
    },
    {  # 16. 调研
        "title": "AI Agent 商业化案例 12 篇深度调研",
        "description": "选 12 家已商业化的 AI Agent 公司（Cursor/Devin/Cognition...），每家 1500 字深度分析（团队/产品/收入/护城河）。",
        "category": "research", "difficulty": "medium", "reward_points": 35,
        "cover_emoji": "🔍", "cover_gradient": "linear-gradient(135deg, #a8edea 0%, #fed6e3 100%)",
        "skills_required": ["market-research", "writing", "AI-industry"],
        "view_count": 945, "favorite_count": 73, "comment_count": 17, "application_count": 11,
        "urgent": False, "featured": False, "hours_ago": 40, "owner_idx": 4,
    },
    {  # 17. 翻译
        "title": "技术博客中译英（10 篇 × 1500 字）",
        "description": "公司技术博客 10 篇中译英，要求术语一致、保留代码片段、保持原作者第一人称口吻。",
        "category": "translation", "difficulty": "easy", "reward_points": 15,
        "cover_emoji": "🌐", "cover_gradient": "linear-gradient(135deg, #a8edea 0%, #fed6e3 100%)",
        "skills_required": ["translation", "technical-writing", "EN-CN"],
        "view_count": 412, "favorite_count": 28, "comment_count": 6, "application_count": 14,
        "urgent": False, "featured": False, "hours_ago": 20, "owner_idx": 5,
    },
    {  # 18. 翻译
        "title": "白皮书日译英 + 排版（DeFi 项目）",
        "description": "一份 32 页日文 DeFi 白皮书译成英文，保持原 LaTeX 排版与公式编号。",
        "category": "translation", "difficulty": "medium", "reward_points": 30,
        "cover_emoji": "📄", "cover_gradient": "linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)",
        "skills_required": ["JA-EN-translation", "DeFi", "LaTeX"],
        "view_count": 287, "favorite_count": 19, "comment_count": 4, "application_count": 6,
        "urgent": False, "featured": False, "hours_ago": 60, "owner_idx": 5,
    },
    {  # 19. 翻译
        "title": "社区公告紧急多语种翻译（6 语种）",
        "description": "一份 800 字紧急公告译成 EN/JA/KO/ES/DE/FR 6 个语种。24 小时内交付。",
        "category": "translation", "difficulty": "easy", "reward_points": 10,
        "cover_emoji": "⚡", "cover_gradient": "linear-gradient(135deg, #fa709a 0%, #fee140 100%)",
        "skills_required": ["multilingual", "fast-turnaround"],
        "view_count": 156, "favorite_count": 11, "comment_count": 2, "application_count": 4,
        "urgent": True, "featured": False, "hours_ago": 2, "owner_idx": 5,
    },
    {  # 20. 设计 / Web3 复合
        "title": "DAO 治理仪表盘可视化设计",
        "description": "为 DAO 设计一个治理仪表盘（投票 / 提案 / 国库），D3.js 或 ECharts 实现 4 种图表，含 Figma 高保真 + 静态原型。",
        "category": "design", "difficulty": "hard", "reward_points": 40,
        "cover_emoji": "📈", "cover_gradient": "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
        "skills_required": ["data-viz", "D3.js", "Figma", "DAO"],
        "view_count": 1334, "favorite_count": 105, "comment_count": 24, "application_count": 13,
        "urgent": False, "featured": True, "hours_ago": 11, "owner_idx": 3,
    },
]


def ensure_owners(conn):
    """为种子任务确保 6 个 owner 存在并补全画像字段。返回 email→id 映射。"""
    cur = conn.cursor()
    email_to_id = {}
    for prof in OWNER_PROFILES:
        cur.execute(
            "SELECT id FROM owners WHERE email = %s",
            (prof["email"],),
        )
        row = cur.fetchone()
        if row:
            owner_id = row["id"]
            cur.execute(
                """UPDATE owners SET
                    display_name=%s, organization=%s, rating=%s,
                    verified=%s, avatar_gradient=%s
                  WHERE id=%s""",
                (prof["display_name"], prof["organization"], prof["rating"],
                 prof["verified"], prof["avatar_gradient"], owner_id),
            )
        else:
            cur.execute(
                """INSERT INTO owners
                    (email, auth_provider, display_name, organization, rating, verified, avatar_gradient)
                   VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id""",
                (prof["email"], "seed", prof["display_name"], prof["organization"],
                 prof["rating"], prof["verified"], prof["avatar_gradient"]),
            )
            owner_id = cur.fetchone()["id"]
        email_to_id[prof["email"]] = owner_id
    return email_to_id


def insert_tasks(conn, owner_ids):
    """插入 20 条种子任务。已存在则跳过（按 title+owner_id 去重）。"""
    cur = conn.cursor()
    inserted = 0
    skipped = 0
    now = datetime.utcnow()
    for t in SEED_TASKS:
        owner_email = OWNER_PROFILES[t["owner_idx"]]["email"]
        owner_id = owner_ids[owner_email]
        # 幂等检查
        cur.execute(
            "SELECT id FROM tasks WHERE title = %s AND owner_id = %s",
            (t["title"], owner_id),
        )
        if cur.fetchone():
            skipped += 1
            continue
        created_at = now - timedelta(hours=t["hours_ago"])
        # deadline 散布在创建之后 3–14 天
        deadline = created_at + timedelta(days=random.randint(3, 14))
        cur.execute(
            """INSERT INTO tasks (
                owner_id, title, description, category, difficulty, reward_points,
                status, view_count, favorite_count, comment_count, application_count,
                skills_required, cover_emoji, cover_gradient, deadline,
                urgent, featured, created_at, updated_at
            ) VALUES (%s,%s,%s,%s,%s,%s,'open',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (
                owner_id, t["title"], t["description"], t["category"],
                t["difficulty"], t["reward_points"],
                t["view_count"], t["favorite_count"], t["comment_count"], t["application_count"],
                t["skills_required"], t["cover_emoji"], t["cover_gradient"], deadline,
                t["urgent"], t["featured"], created_at, created_at,
            ),
        )
        inserted += 1
    return inserted, skipped


def main():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    try:
        owner_ids = ensure_owners(conn)
        inserted, skipped = insert_tasks(conn, owner_ids)
        conn.commit()
        # 汇总
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) AS c FROM tasks")
        total = cur.fetchone()["c"]
        print(f"owners ensured:  {len(owner_ids)}")
        print(f"tasks inserted:  {inserted}")
        print(f"tasks skipped:   {skipped} (already present)")
        print(f"tasks total now: {total}")
    except Exception as e:
        conn.rollback()
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
