"""
Anti-Fraud Service (`app/services/anti_fraud.py`)
==================================================

实现 5 种作弊检测规则。每条规则是一个**纯函数**，输入数据类，输出可选 Alert。
DB 适配层只负责组装规则输入和持久化告警，便于单元测试 mock。

5 种规则：
    rule_left_to_right    左手倒右手：同 owner 反复给同 agent 高分
    rule_mutual_review    互刷：A↔B 互相发任务并互相打高分
    rule_empty_task       空任务：描述/产出极简但奖励高
    rule_sock_puppet      马甲账号：同 IP 注册的 owner 给对方 agent 评分
    rule_time_anomaly     时间异常：任务创建到完成 < 5 分钟

调用入口：
    check_review_for_fraud(conn, owner_id, agent_id, task_id) -> List[Alert]
        遍历规则、写入 fraud_alerts、返回触发列表

    compute_fraud_penalty(conn, agent_id) -> float (0.3 - 1.0)
        聚合 agent 的待处理告警 → 信誉折扣
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional, Sequence, Any
from uuid import UUID
import json
import logging

logger = logging.getLogger(__name__)


# ===================================================================
# 数据类
# ===================================================================
@dataclass
class ReviewContext:
    """单次 review 的快照（用于规则推理）"""
    owner_id: UUID
    agent_id: UUID
    task_id: UUID
    rating: int                          # 1-5
    task_created_at: datetime
    task_completed_at: datetime
    task_description: str
    submission_content: str              # task_submissions.content
    reward_points: int


@dataclass
class ReviewerHistory:
    """owner 的相关历史"""
    # owner -> agent: 最近 30 天的所有任务（含本次）
    recent_tasks_with_agent: List[dict] = field(default_factory=list)
    # 互刷检测：agent 的 owner 反向给 owner 的 agent 发过的任务
    mutual_review_tasks: List[dict] = field(default_factory=list)


@dataclass
class IPRegistration:
    """马甲检测必需"""
    owner_signup_ip: Optional[str]
    agent_owner_signup_ip: Optional[str]


@dataclass
class Alert:
    rule_name: str
    severity: float   # 0.0 - 1.0
    evidence: dict


# ===================================================================
# 规则常量（集中调参）
# ===================================================================
LEFT_TO_RIGHT_MIN_TASKS = 3            # 30 天内 owner→agent 任务数阈值
LEFT_TO_RIGHT_AVG_RATING = 4.5         # 平均评分阈值（>= 视为可疑）
MUTUAL_REVIEW_HIGH_RATING = 4          # 互刷判定的"高分"阈值
EMPTY_TASK_DESC_LEN = 30               # 任务描述最短字符
EMPTY_TASK_SUB_LEN = 50                # 提交内容最短字符
EMPTY_TASK_HIGH_REWARD = 50            # "高奖励"阈值
TIME_ANOMALY_MIN_MINUTES = 5           # 任务完成最短时长


# ===================================================================
# 5 条纯函数规则
# ===================================================================
def rule_left_to_right(
    ctx: ReviewContext,
    history: ReviewerHistory,
) -> Optional[Alert]:
    """
    左手倒右手：同一 owner 反复给同一 agent 高分。
    触发：30 天内 owner→agent 任务数 ≥ 3 且 平均评分 ≥ 4.5
    严重度：0.3 + 0.1 × min(count - 3, 5)，封顶 0.8
    """
    tasks = history.recent_tasks_with_agent
    if len(tasks) < LEFT_TO_RIGHT_MIN_TASKS:
        return None

    rated = [t for t in tasks if t.get("rating") is not None]
    if not rated:
        return None
    avg = sum(t["rating"] for t in rated) / len(rated)
    if avg < LEFT_TO_RIGHT_AVG_RATING:
        return None

    severity = min(0.3 + 0.1 * max(0, len(tasks) - LEFT_TO_RIGHT_MIN_TASKS), 0.8)
    return Alert(
        rule_name="left_to_right",
        severity=severity,
        evidence={
            "task_count_30d": len(tasks),
            "avg_rating": round(avg, 2),
            "owner_id": str(ctx.owner_id),
            "agent_id": str(ctx.agent_id),
        },
    )


def rule_mutual_review(
    ctx: ReviewContext,
    history: ReviewerHistory,
) -> Optional[Alert]:
    """
    互刷：A 的 owner 给 B 的 agent 发任务并打高分；同时 B 的 owner 也给 A 的 agent 发任务并打高分。
    触发：mutual_review_tasks 非空且包含 ≥1 条评分 ≥ 4 的反向任务，且本次评分 ≥ 4
    严重度：0.5（强信号）
    """
    if ctx.rating < MUTUAL_REVIEW_HIGH_RATING:
        return None
    reverse = [t for t in history.mutual_review_tasks
               if t.get("rating") is not None and t["rating"] >= MUTUAL_REVIEW_HIGH_RATING]
    if not reverse:
        return None

    severity = 0.5 + 0.1 * min(len(reverse) - 1, 3)  # 0.5 - 0.8
    return Alert(
        rule_name="mutual_review",
        severity=min(severity, 0.8),
        evidence={
            "this_review_rating": ctx.rating,
            "reverse_task_count": len(reverse),
            "reverse_avg_rating": round(
                sum(t["rating"] for t in reverse) / len(reverse), 2
            ),
            "reverse_task_ids": [str(t["task_id"]) for t in reverse[:5]],
        },
    )


def rule_empty_task(ctx: ReviewContext) -> Optional[Alert]:
    """
    空任务：描述或产出极简，但奖励高。
    触发：(描述 < 30 字 OR 提交 < 50 字) AND 奖励 ≥ 50
    严重度：0.4 基础，每短一档 +0.1
    """
    desc_len = len(ctx.task_description or "")
    sub_len = len(ctx.submission_content or "")
    short_desc = desc_len < EMPTY_TASK_DESC_LEN
    short_sub = sub_len < EMPTY_TASK_SUB_LEN
    high_reward = ctx.reward_points >= EMPTY_TASK_HIGH_REWARD

    if not high_reward:
        return None
    if not (short_desc or short_sub):
        return None

    severity = 0.4
    if short_desc and short_sub:
        severity += 0.2
    if ctx.reward_points >= EMPTY_TASK_HIGH_REWARD * 2:
        severity += 0.1
    severity = min(severity, 0.8)

    return Alert(
        rule_name="empty_task",
        severity=severity,
        evidence={
            "description_length": desc_len,
            "submission_length": sub_len,
            "reward_points": ctx.reward_points,
            "task_id": str(ctx.task_id),
        },
    )


def rule_sock_puppet(
    ctx: ReviewContext,
    ip_info: IPRegistration,
) -> Optional[Alert]:
    """
    马甲账号：评分 owner 与 agent 的 owner 注册时使用同一 IP。
    触发：两个 IP 都已知且相等
    严重度：0.6 基础；本次评分 ≥ 4 加 0.1
    """
    if not ip_info.owner_signup_ip or not ip_info.agent_owner_signup_ip:
        return None
    if ip_info.owner_signup_ip != ip_info.agent_owner_signup_ip:
        return None

    severity = 0.6
    if ctx.rating >= 4:
        severity += 0.1
    severity = min(severity, 0.9)

    return Alert(
        rule_name="sock_puppet",
        severity=severity,
        evidence={
            "shared_ip": ip_info.owner_signup_ip,
            "this_rating": ctx.rating,
            "owner_id": str(ctx.owner_id),
            "agent_id": str(ctx.agent_id),
        },
    )


def rule_time_anomaly(ctx: ReviewContext) -> Optional[Alert]:
    """
    时间异常：任务从创建到完成时间 < 5 分钟。
    触发：completed - created < 5 min
    严重度：0.4 基础；< 1 min 加 0.3，< 30 s 加 0.5
    """
    if not ctx.task_completed_at or not ctx.task_created_at:
        return None
    delta = ctx.task_completed_at - ctx.task_created_at
    minutes = delta.total_seconds() / 60.0
    if minutes >= TIME_ANOMALY_MIN_MINUTES:
        return None

    severity = 0.4
    if minutes < 1.0:
        severity += 0.3
    if delta.total_seconds() < 30:
        severity += 0.2
    severity = min(severity, 0.9)

    return Alert(
        rule_name="time_anomaly",
        severity=severity,
        evidence={
            "elapsed_minutes": round(minutes, 2),
            "elapsed_seconds": int(delta.total_seconds()),
            "task_id": str(ctx.task_id),
        },
    )


# ===================================================================
# 编排
# ===================================================================
def run_all_rules(
    ctx: ReviewContext,
    history: ReviewerHistory,
    ip_info: IPRegistration,
) -> List[Alert]:
    """跑全部规则，返回触发的告警列表"""
    candidates = [
        rule_left_to_right(ctx, history),
        rule_mutual_review(ctx, history),
        rule_empty_task(ctx),
        rule_sock_puppet(ctx, ip_info),
        rule_time_anomaly(ctx),
    ]
    return [a for a in candidates if a is not None]


def severity_to_penalty(total_severity: float) -> float:
    """
    把累积严重度映射到信誉折扣（0.3 - 1.0）。
    severity=0   → 1.0  无折扣
    severity=0.5 → ~0.7
    severity=1.0 → ~0.45
    severity=2.0+ → 0.3 (下限)
    """
    if total_severity <= 0.0:
        return 1.0
    # 线性 + 下限
    penalty = 1.0 - 0.5 * total_severity
    return max(0.3, min(1.0, penalty))


# ===================================================================
# DB 适配层（用 psycopg2 RealDictCursor 协议）
# ===================================================================
def _q(cur, sql: str, params: Sequence[Any] = ()) -> List[dict]:
    """执行查询，返回字典列表（适配 RealDictCursor）"""
    cur.execute(sql, params)
    rows = cur.fetchall()
    return [dict(r) for r in rows]


def gather_context(
    conn,
    owner_id: UUID,
    agent_id: UUID,
    task_id: UUID,
) -> tuple[Optional[ReviewContext], ReviewerHistory, IPRegistration]:
    """
    从 DB 组装规则需要的输入。任何缺失数据都会安全降级成 None / 空列表，
    让规则自身决定是否触发。
    """
    cur = conn.cursor()
    history = ReviewerHistory()
    ip_info = IPRegistration(owner_signup_ip=None, agent_owner_signup_ip=None)

    # 1. 本次 review 上下文
    rows = _q(cur, """
        SELECT t.id, t.description, t.reward_points,
               t.created_at AS task_created_at,
               t.completed_at AS task_completed_at,
               (SELECT MAX(rating) FROM task_reviews WHERE task_id = t.id) AS rating,
               (SELECT content FROM task_submissions
                WHERE task_id = t.id ORDER BY submitted_at DESC LIMIT 1) AS submission_content
        FROM tasks t WHERE t.id = %s
    """, (str(task_id),))
    if not rows:
        return None, history, ip_info
    r = rows[0]
    ctx = ReviewContext(
        owner_id=owner_id,
        agent_id=agent_id,
        task_id=task_id,
        rating=int(r["rating"] or 0),
        task_created_at=r["task_created_at"] or datetime.now(),
        task_completed_at=r["task_completed_at"] or datetime.now(),
        task_description=r["description"] or "",
        submission_content=r["submission_content"] or "",
        reward_points=int(r["reward_points"] or 0),
    )

    # 2. owner -> agent 的最近 30 天任务 + 评分
    history.recent_tasks_with_agent = _q(cur, """
        SELECT t.id AS task_id, t.created_at,
               (SELECT MAX(rating) FROM task_reviews tr WHERE tr.task_id = t.id) AS rating
        FROM tasks t
        WHERE t.owner_id = %s AND t.assigned_agent_id = %s
          AND t.created_at > NOW() - INTERVAL '30 days'
    """, (str(owner_id), str(agent_id)))

    # 3. 互刷：找 agent 的 owner，看其有没有给 owner 名下 agent 发过高分任务
    rows = _q(cur, "SELECT owner_id FROM agents WHERE id = %s", (str(agent_id),))
    if rows:
        agent_owner_id = rows[0]["owner_id"]
        history.mutual_review_tasks = _q(cur, """
            SELECT t.id AS task_id,
                   (SELECT MAX(rating) FROM task_reviews tr WHERE tr.task_id = t.id) AS rating
            FROM tasks t
            WHERE t.owner_id = %s
              AND t.assigned_agent_id IN (SELECT id FROM agents WHERE owner_id = %s)
              AND t.created_at > NOW() - INTERVAL '90 days'
        """, (str(agent_owner_id), str(owner_id)))

        # IP 信息（owner 双方 signup_ip）
        rows = _q(cur, "SELECT signup_ip FROM owners WHERE id = %s", (str(owner_id),))
        if rows:
            ip_info.owner_signup_ip = str(rows[0]["signup_ip"]) if rows[0]["signup_ip"] else None
        rows = _q(cur, "SELECT signup_ip FROM owners WHERE id = %s", (str(agent_owner_id),))
        if rows:
            ip_info.agent_owner_signup_ip = str(rows[0]["signup_ip"]) if rows[0]["signup_ip"] else None

    return ctx, history, ip_info


def persist_alerts(
    conn,
    alerts: List[Alert],
    owner_id: UUID,
    agent_id: UUID,
    task_id: UUID,
) -> List[str]:
    """写入 fraud_alerts 表，返回插入的 alert_id 列表"""
    if not alerts:
        return []
    cur = conn.cursor()
    ids: List[str] = []
    for a in alerts:
        cur.execute("""
            INSERT INTO fraud_alerts
                (agent_id, owner_id, task_id, rule_name, severity, evidence, status)
            VALUES (%s, %s, %s, %s, %s, %s, 'open')
            RETURNING id
        """, (
            str(agent_id), str(owner_id), str(task_id),
            a.rule_name, a.severity, json.dumps(a.evidence),
        ))
        row = cur.fetchone()
        if row:
            ids.append(str(row["id"] if isinstance(row, dict) else row[0]))
    return ids


def compute_fraud_penalty(conn, agent_id: UUID) -> float:
    """
    根据 agent 当前 open / confirmed 的告警，计算信誉折扣 0.3 - 1.0。
    严重度按规则唯一去重（每种规则取最严重一条），避免一次评论触发多条 sock_puppet 重复扣分。
    """
    cur = conn.cursor()
    rows = _q(cur, """
        SELECT rule_name, MAX(severity) AS severity
        FROM fraud_alerts
        WHERE agent_id = %s AND status IN ('open', 'confirmed')
        GROUP BY rule_name
    """, (str(agent_id),))
    total = sum(float(r["severity"]) for r in rows)
    return severity_to_penalty(total)


def update_reputation_score(conn, agent_id: UUID) -> dict:
    """
    重新计算 agent 的双轨声望并写入 reputation_scores。
    quality = sum(reputation_events.points where zone='work')
    social  = sum(reputation_events.points where zone='social')
    total   = (quality*0.7 + social*0.3) * fraud_penalty
    """
    cur = conn.cursor()
    rows = _q(cur, """
        SELECT zone, COALESCE(SUM(points), 0) AS pts
        FROM reputation_events
        WHERE agent_id = %s
        GROUP BY zone
    """, (str(agent_id),))
    quality = next((int(r["pts"]) for r in rows if r["zone"] == "work"), 0)
    social  = next((int(r["pts"]) for r in rows if r["zone"] == "social"), 0)

    fraud_penalty = compute_fraud_penalty(conn, agent_id)
    total = int((quality * 0.7 + social * 0.3) * fraud_penalty)

    cur.execute("""
        INSERT INTO reputation_scores
            (agent_id, quality_score, social_score, total_score, fraud_penalty, last_updated)
        VALUES (%s, %s, %s, %s, %s, NOW())
        ON CONFLICT (agent_id) DO UPDATE
        SET quality_score = EXCLUDED.quality_score,
            social_score  = EXCLUDED.social_score,
            total_score   = EXCLUDED.total_score,
            fraud_penalty = EXCLUDED.fraud_penalty,
            last_updated  = EXCLUDED.last_updated
    """, (str(agent_id), quality, social, total, fraud_penalty))

    return {
        "quality_score": quality,
        "social_score": social,
        "total_score": total,
        "fraud_penalty": fraud_penalty,
    }


def check_review_for_fraud(
    conn,
    owner_id: UUID,
    agent_id: UUID,
    task_id: UUID,
) -> List[Alert]:
    """
    主入口：组装上下文 → 跑全部规则 → 持久化 → 重算信誉 → 返回告警列表。
    在 task review API 中调用。
    """
    ctx, history, ip_info = gather_context(conn, owner_id, agent_id, task_id)
    if ctx is None:
        logger.warning("anti_fraud: task %s context missing, skipping", task_id)
        return []
    alerts = run_all_rules(ctx, history, ip_info)
    if alerts:
        persist_alerts(conn, alerts, owner_id, agent_id, task_id)
    update_reputation_score(conn, agent_id)
    return alerts
