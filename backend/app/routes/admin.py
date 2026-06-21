"""
Admin routes
- GET  /api/v1/admin/fraud-alerts                查可疑事件
- POST /api/v1/admin/fraud-review/{alert_id}     人工审核
- GET  /api/v1/admin/reaper/stats                stale-claim reaper 统计
- GET  /api/v1/admin/reaper/recent                最近 N 条 reaper 审计事件

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


# -------------------------------------------------------------------
# GET /admin/reaper/stats
# -------------------------------------------------------------------
class ReaperStatsResponse(BaseModel):
    state: dict
    last_24h_reaped: int
    by_agent: List[dict]


@router.get("/reaper/stats", response_model=ReaperStatsResponse)
def reaper_stats(
    _: UUID = Depends(get_current_owner),
):
    """Operator dashboard data for the stale-claim reaper.

    Returns:
        state: live counters from app.stale_claim_reaper.get_state()
        last_24h_reaped: rows count for stale_claim_reaped events in last 24h
        by_agent: top 10 previous_agent_id × reap_count over last 24h
    """
    try:
        from app.stale_claim_reaper import get_state as _reaper_state
        live = _reaper_state()
    except Exception as exc:
        live = {"error": repr(exc)[:300]}

    by_agent: List[dict] = []
    last_24h_reaped = 0
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT COUNT(*)::int AS n
              FROM job_events
             WHERE event_type = 'stale_claim_reaped'
               AND created_at >= NOW() - INTERVAL '24 hours'
            """
        )
        row = cur.fetchone() or {}
        last_24h_reaped = int(row.get("n", 0))

        cur.execute(
            """
            SELECT (payload->>'previous_agent_id') AS agent_id,
                   COUNT(*)::int AS reap_count,
                   MAX(created_at) AS last_reaped_at
              FROM job_events
             WHERE event_type = 'stale_claim_reaped'
               AND created_at >= NOW() - INTERVAL '24 hours'
               AND payload ? 'previous_agent_id'
             GROUP BY (payload->>'previous_agent_id')
             ORDER BY reap_count DESC, last_reaped_at DESC
             LIMIT 10
            """
        )
        for r in cur.fetchall():
            by_agent.append({
                "agent_id": r["agent_id"],
                "reap_count": int(r["reap_count"]),
                "last_reaped_at": (
                    r["last_reaped_at"].isoformat()
                    if r["last_reaped_at"] else None
                ),
            })

    return ReaperStatsResponse(
        state=live,
        last_24h_reaped=last_24h_reaped,
        by_agent=by_agent,
    )


# -------------------------------------------------------------------
# GET /admin/reaper/recent
# -------------------------------------------------------------------
class ReaperEventOut(BaseModel):
    job_id: UUID
    previous_agent_id: Optional[str] = None
    reaped_at: str
    payload: dict


@router.get("/reaper/recent", response_model=List[ReaperEventOut])
def reaper_recent(
    limit: int = Query(50, ge=1, le=500),
    _: UUID = Depends(get_current_owner),
):
    """Most recent stale_claim_reaped events for forensic review."""
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT job_id, payload, created_at
              FROM job_events
             WHERE event_type = 'stale_claim_reaped'
             ORDER BY created_at DESC
             LIMIT %s
            """,
            (limit,),
        )
        rows = cur.fetchall()

    return [
        ReaperEventOut(
            job_id=r["job_id"],
            previous_agent_id=(
                r["payload"].get("previous_agent_id")
                if isinstance(r["payload"], dict) else None
            ),
            reaped_at=r["created_at"].isoformat() if r["created_at"] else "",
            payload=r["payload"] if isinstance(r["payload"], dict) else {},
        )
        for r in rows
    ]
