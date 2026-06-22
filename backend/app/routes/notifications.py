"""
Notification API routes
"""
from fastapi import APIRouter, HTTPException, status, Depends, Query
from uuid import UUID
from typing import List, Optional
from app.database import get_db_connection
from app.dependencies import get_current_user
import logging

router = APIRouter(prefix="/notifications", tags=["notifications"])
logger = logging.getLogger(__name__)


@router.get("")
def list_notifications(
    read: Optional[bool] = Query(None),
    limit: int = Query(20, le=100),
    user_id: UUID = Depends(get_current_user)
):
    """查询当前用户的通知"""
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()

            query = """
                SELECT id, user_id, type, title, message, link, read, created_at
                FROM notifications
                WHERE user_id = %s
            """
            params = [str(user_id)]

            if read is not None:
                query += " AND read = %s"
                params.append(read)

            query += " ORDER BY created_at DESC LIMIT %s"
            params.append(limit)

            cur.execute(query, params)
            notifications = cur.fetchall()

            return [dict(n) for n in notifications]

    except Exception as e:
        logger.error(f"Notification listing failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Notification listing failed: {str(e)}"
        )


@router.post("/{notification_id}/read")
def mark_notification_read(
    notification_id: UUID,
    user_id: UUID = Depends(get_current_user)
):
    """标记通知为已读"""
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()

            # 验证通知属于当前用户
            cur.execute(
                "SELECT user_id FROM notifications WHERE id = %s",
                (str(notification_id),)
            )
            notification = cur.fetchone()

            if not notification:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Notification not found"
                )

            if notification['user_id'] != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not your notification"
                )

            # 标记已读
            cur.execute(
                "UPDATE notifications SET read = TRUE WHERE id = %s",
                (str(notification_id),)
            )

            return {"success": True}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Mark notification read failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Mark notification read failed"
        )


@router.post("/read-all")
def mark_all_notifications_read(user_id: UUID = Depends(get_current_user)):
    """标记所有通知为已读"""
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()

            cur.execute(
                "UPDATE notifications SET read = TRUE WHERE user_id = %s AND read = FALSE",
                (str(user_id),)
            )

            return {"success": True}

    except Exception as e:
        logger.error(f"Mark all notifications read failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Mark all notifications read failed"
        )


@router.get("/unread-count")
def get_unread_count(user_id: UUID = Depends(get_current_user)):
    """获取未读通知数量"""
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()

            cur.execute(
                "SELECT COUNT(*) as count FROM notifications WHERE user_id = %s AND read = FALSE",
                (str(user_id),)
            )
            result = cur.fetchone()

            return {"count": result['count']}

    except Exception as e:
        logger.error(f"Get unread count failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Get unread count failed"
        )


def create_notification(conn, user_id: UUID, type: str, title: str, message: str, link: str = None):
    """创建通知的工具函数（供其他模块调用）"""
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO notifications (user_id, type, title, message, link)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
            """,
            (str(user_id), type, title, message, link)
        )
        result = cur.fetchone()
        logger.info(f"Notification created: {result['id']} for user {user_id}")
        return result['id']
    except Exception as e:
        logger.error(f"Create notification failed: {e}")
        raise
