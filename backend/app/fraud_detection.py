"""
Fraud Detection Module
Implements collusion detection and reputation calculation algorithms
"""
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import json
import logging
from uuid import UUID

from app.database import get_db

logger = logging.getLogger(__name__)


def detect_collusion(owner_id: UUID, agent_id: UUID, task_id: UUID) -> float:
    """
    检测 owner 和 agent 是否串通刷分
    
    返回 risk_score (0.0 - 1.0)，> 0.7 自动记录到 fraud_detection_logs
    
    修复要点：
    1. agent.owner_id → 从数据库查询
    2. risk_score 限制在 1.0
    3. 处理 base_score = 0 的情况
    """
    db = next(get_db())
    risk_score = 0.0
    evidence = {}
    
    try:
        # 1. 合作频率检测
        result = db.execute(
            """
            SELECT COUNT(*) as cnt FROM tasks 
            WHERE owner_id = %s AND assigned_agent_id = %s 
            AND created_at > NOW() - INTERVAL '30 days'
            """,
            (str(owner_id), str(agent_id))
        )
        recent_tasks = result.fetchone()[0]
        
        if recent_tasks > 5:
            risk_score += 0.3
            evidence['repeated_collaboration'] = recent_tasks
        
        # 2. 评分模式检测
        result = db.execute(
            """
            SELECT rating FROM task_reviews 
            WHERE reviewer_id = %s 
            ORDER BY reviewed_at DESC LIMIT 10
            """,
            (str(owner_id),)
        )
        ratings = [row[0] for row in result.fetchall()]
        
        if len(ratings) >= 3 and all(r == 5 for r in ratings):
            risk_score += 0.3
            evidence['always_max_rating'] = len(ratings)
        
        # 3. 交付时间检测
        result = db.execute(
            """
            SELECT t.created_at, s.submitted_at 
            FROM tasks t
            JOIN task_submissions s ON s.task_id = t.id
            WHERE t.id = %s
            """,
            (str(task_id),)
        )
        row = result.fetchone()
        
        if row:
            task_created, submission_time = row
            time_spent = submission_time - task_created
            if time_spent < timedelta(minutes=10):
                risk_score += 0.4
                evidence['instant_completion_minutes'] = time_spent.total_seconds() / 60
        
        # 4. IP 地址检测（修复：agent.owner_id → 从数据库查）
        result = db.execute(
            """
            SELECT ip_address FROM audit_logs 
            WHERE agent_id = (SELECT id FROM agents WHERE owner_id = %s LIMIT 1)
            ORDER BY created_at DESC LIMIT 1
            """,
            (str(owner_id),)
        )
        owner_ip_row = result.fetchone()
        owner_ip = owner_ip_row[0] if owner_ip_row else None
        
        result = db.execute(
            "SELECT owner_id FROM agents WHERE id = %s",
            (str(agent_id),)
        )
        agent_owner_row = result.fetchone()
        agent_owner_id = agent_owner_row[0] if agent_owner_row else None
        
        if agent_owner_id:
            result = db.execute(
                """
                SELECT ip_address FROM audit_logs 
                WHERE agent_id = (SELECT id FROM agents WHERE owner_id = %s LIMIT 1)
                ORDER BY created_at DESC LIMIT 1
                """,
                (str(agent_owner_id),)
            )
            agent_owner_ip_row = result.fetchone()
            agent_owner_ip = agent_owner_ip_row[0] if agent_owner_ip_row else None
            
            if owner_ip and agent_owner_ip and owner_ip == agent_owner_ip:
                risk_score += 0.5
                evidence['same_ip'] = str(owner_ip)
        
        # 修复：限制 risk_score 在 1.0 以内
        risk_score = min(risk_score, 1.0)
        
        # 记录高风险情况
        if risk_score > 0.7:
            db.execute(
                """
                INSERT INTO fraud_detection_logs 
                (agent_id, owner_id, fraud_type, risk_score, evidence, status)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    str(agent_id),
                    str(owner_id),
                    'collusion',
                    risk_score,
                    json.dumps(evidence),
                    'pending'
                )
            )
            db.commit()
            logger.warning(f"High collusion risk detected: {risk_score:.2f} for owner={owner_id}, agent={agent_id}")
        
        return risk_score
        
    except Exception as e:
        logger.error(f"Error in collusion detection: {e}")
        db.rollback()
        return 0.0
    finally:
        db.close()


def is_evidence_verified(source_id: Optional[UUID]) -> bool:
    """检查 evidence 是否被验证（查询 task_reviews.evidence_verified）"""
    if not source_id:
        return False
    
    db = next(get_db())
    try:
        result = db.execute(
            "SELECT evidence_verified FROM task_reviews WHERE id = %s",
            (str(source_id),)
        )
        row = result.fetchone()
        return row[0] if row else False
    except Exception as e:
        logger.error(f"Error checking evidence verification: {e}")
        return False
    finally:
        db.close()


def calculate_work_reputation(agent_id: UUID) -> int:
    """
    计算工作声望（修复 base_score = 0 的情况）
    
    公式：base_score × verification_discount × diversity_bonus × recency_weight
    """
    db = next(get_db())
    
    try:
        # 获取所有工作区 reputation_events
        result = db.execute(
            """
            SELECT id, points, verifiable, source_id, created_at 
            FROM reputation_events 
            WHERE agent_id = %s AND zone = 'work'
            ORDER BY created_at DESC
            """,
            (str(agent_id),)
        )
        events = result.fetchall()
        
        if not events:
            return 0
        
        base_score = sum(e[1] for e in events)  # e[1] = points
        
        # 修复：base_score <= 0 直接返回
        if base_score <= 0:
            return 0
        
        # 1. 验证折扣
        verifiable_events = [e for e in events if e[2]]  # e[2] = verifiable
        if not verifiable_events:
            verification_discount = 1.0
        else:
            verified_count = sum(1 for e in verifiable_events if is_evidence_verified(e[3]))  # e[3] = source_id
            verification_discount = 0.5 + 0.5 * (verified_count / len(verifiable_events))
        
        # 2. 多样性加成
        result = db.execute(
            """
            SELECT COUNT(DISTINCT owner_id) 
            FROM tasks 
            WHERE assigned_agent_id = %s
            """,
            (str(agent_id),)
        )
        unique_owners = result.fetchone()[0]
        diversity_bonus = min(1.0 + unique_owners * 0.1, 2.0)
        
        # 3. 时间衰减（修复：半衰期公式）
        now = datetime.now()
        weighted_sum = 0
        for e in events:
            created_at = e[4]  # e[4] = created_at
            days_ago = (now - created_at).days
            weight = 0.5 ** (days_ago / 180)  # 180天半衰期
            weighted_sum += e[1] * weight  # e[1] = points
        
        recency_weight = weighted_sum / base_score if base_score > 0 else 1.0
        
        final_score = base_score * verification_discount * diversity_bonus * recency_weight
        return int(final_score)
        
    except Exception as e:
        logger.error(f"Error calculating work reputation: {e}")
        return 0
    finally:
        db.close()


def calculate_total_reputation(agent_id: UUID) -> int:
    """
    总声望 = 社交 30% + 工作 70%
    """
    db = next(get_db())
    
    try:
        result = db.execute(
            "SELECT social_reputation FROM agents WHERE id = %s",
            (str(agent_id),)
        )
        row = result.fetchone()
        social = row[0] if row else 0
        
        work = calculate_work_reputation(agent_id)
        
        return int(social * 0.3 + work * 0.7)
        
    except Exception as e:
        logger.error(f"Error calculating total reputation: {e}")
        return 0
    finally:
        db.close()


def calculate_social_reputation(agent_id: UUID) -> int:
    """
    计算社交声望
    
    基于社交互动的 reputation_events (zone='social')
    应用时间衰减，近期活跃度更高
    """
    db = next(get_db())
    
    try:
        # 获取所有社交区 reputation_events
        result = db.execute(
            """
            SELECT points, created_at 
            FROM reputation_events 
            WHERE agent_id = %s AND zone = 'social'
            ORDER BY created_at DESC
            """,
            (str(agent_id),)
        )
        events = result.fetchall()
        
        if not events:
            return 0
        
        base_score = sum(e[0] for e in events)  # e[0] = points
        
        if base_score <= 0:
            return 0
        
        # 时间衰减（90天半衰期，比工作声望更短，鼓励持续活跃）
        now = datetime.now()
        weighted_sum = 0
        for e in events:
            created_at = e[1]  # e[1] = created_at
            days_ago = (now - created_at).days
            weight = 0.5 ** (days_ago / 90)  # 90天半衰期
            weighted_sum += e[0] * weight  # e[0] = points
        
        recency_weight = weighted_sum / base_score if base_score > 0 else 1.0
        
        final_score = base_score * recency_weight
        return int(final_score)
        
    except Exception as e:
        logger.error(f"Error calculating social reputation: {e}")
        return 0
    finally:
        db.close()

