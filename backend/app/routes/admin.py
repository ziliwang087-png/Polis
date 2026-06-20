"""
Admin routes
- GET  /api/v1/admin/fraud-alerts                查可疑事件
- POST /api/v1/admin/fraud-review/{alert_id}     人工审核

注意：现阶段仅做 owner 鉴权占位（要求 owner JWT），生产环境需要专门的 admin role。
出网暴露的接口需要鉴权 — 已 flag。
"""
from __future__ import annotations

from typing import Optional, List
from uuid import UUID
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from app.database import get_db_connection
from app.dependencies import get_current_owner
from app.services import anti_fraud

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


# -------------------------------------------------------------------
# DTO
# -------------------------------------------------------------------
class FraudAlertOut(BaseModel):
    id: UUID
    rule_name: str
    severity: float
    evidence: dict
    status: str
    agent_id: Optional[UUID] = None
    owner_id: Optional[UUID] = None
    task_id: Optional[UUID] = None
    detected_at: str
    reviewed_at: Optional[str] = None
    reviewer_note: Optional[str] = None


class FraudReviewRequest(BaseModel):
    decision: str            # 'confirmed' | 'dismissed'
    note: Optional[str] = None


class FraudReviewResponse(BaseModel):
    alert_id: UUID
    status: str
    new_fraud_penalty: float
    new_total_score: int


# -------------------------------------------------------------------
# GET /admin/fraud-alerts
# -------------------------------------------------------------------
@router.get("/fraud-alerts", response_model=List[FraudAlertOut])
def list_fraud_alerts(
    status_filter: Optional[str] = Query(None, alias="status"),
    rule_name: Optional[str] = None,
    min_severity: float = Query(0.0, ge=0.0, le=1.0),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _: UUID = Depends(get_current_owner),  # 鉴权占位
):
    """列出待人工审核的可疑事件，按 detected_at desc 排序。"""
    with get_db_connection() as conn:
        cur = conn.cursor()
        sql = "SELECT * FROM fraud_alerts WHERE severity >= %s"
        params: list = [min_severity]
        if status_filter:
            sql += " AND status = %s"
            params.append(status_filter)
        if rule_name:
            sql += " AND rule_name = %s"
            params.append(rule_name)
        sql += " ORDER BY detected_at DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])
        cur.execute(sql, params)
        rows = cur.fetchall()

        return [
            FraudAlertOut(
                id=r["id"],
                rule_name=r["rule_name"],
                severity=float(r["severity"]),
                evidence=r["evidence"] if isinstance(r["evidence"], dict) else dict(r["evidence"] or {}),
                status=r["status"],
                agent_id=r["agent_id"],
                owner_id=r["owner_id"],
                task_id=r["task_id"],
                detected_at=r["detected_at"].isoformat() if r["detected_at"] else "",
                reviewed_at=r["reviewed_at"].isoformat() if r["reviewed_at"] else None,
                reviewer_note=r["reviewer_note"],
            )
            for r in rows
        ]


# -------------------------------------------------------------------
# POST /admin/fraud-review/{alert_id}
# -------------------------------------------------------------------
@router.post("/fraud-review/{alert_id}", response_model=FraudReviewResponse)
def review_fraud_alert(
    alert_id: UUID,
    request: FraudReviewRequest,
    reviewer_id: UUID = Depends(get_current_owner),
):
    """人工标记 confirmed 或 dismissed，并刷新对应 agent 的信誉折扣。"""
    if request.decision not in ("confirmed", "dismissed"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="decision must be 'confirmed' or 'dismissed'",
        )

    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT agent_id, status FROM fraud_alerts WHERE id = %s", (str(alert_id),))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Alert not found")
        if row["status"] not in ("open",):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Alert already in status '{row['status']}'",
            )

        agent_id = row["agent_id"]
        cur.execute("""
            UPDATE fraud_alerts
            SET status = %s,
                reviewer_id = %s,
                reviewer_note = %s,
                reviewed_at = NOW()
            WHERE id = %s
        """, (request.decision, str(reviewer_id), request.note, str(alert_id)))

        # 重算 agent 的 reputation_scores
        rep = anti_fraud.update_reputation_score(conn, agent_id) if agent_id else {}

    return FraudReviewResponse(
        alert_id=alert_id,
        status=request.decision,
        new_fraud_penalty=rep.get("fraud_penalty", 1.0),
        new_total_score=rep.get("total_score", 0),
    )
