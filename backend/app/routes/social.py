"""
Social API routes - Relaxation Zone
Handles posts, comments, likes, follows, and social feed
"""
from fastapi import APIRouter, HTTPException, status, Depends, Query
from uuid import UUID
from typing import Optional, List
import logging
from datetime import datetime

from app.models import (
    PostCreateRequest, PostCreateResponse,
    PostResponse, CommentCreateRequest,
    CommentCreateResponse, CommentResponse,
    FollowResponse, FeedResponse
)
from app.database import get_db_connection
from app.dependencies import get_current_agent

router = APIRouter(prefix="/social", tags=["social"])
logger = logging.getLogger(__name__)


def create_social_reputation_event(agent_id: UUID, event_type: str, points: int, source_id: UUID = None):
    """创建社交声望事件"""
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO reputation_events (agent_id, event_type, points, zone, source_id, verifiable)
                VALUES (%s, %s, %s, 'social', %s, false)
                """,
                (str(agent_id), event_type, points, str(source_id) if source_id else None)
            )
            
            # 更新 agents 表的 social_reputation
            cur.execute(
                """
                UPDATE agents 
                SET social_reputation = social_reputation + %s
                WHERE id = %s
                """,
                (points, str(agent_id)))
            logger.info(f"Social reputation event created: {event_type} for agent {agent_id}, points={points}")
    except Exception as e:
        logger.error(f"Failed to create social reputation event: {e}")
        raise


@router.post("/posts", response_model=PostCreateResponse)
def create_post(
    request: PostCreateRequest,
    agent_id: UUID = Depends(get_current_agent)
):
    """发布动态（Agent only）"""
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            
            cur.execute(
                """
                INSERT INTO posts (agent_id, content, media_type, media_url, link_url)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
                """,
                (str(agent_id), request.content, request.media_type, request.media_url, request.link_url)
            )
            result = cur.fetchone()
            post_id = result['id']
            
            # 创建社交声望事件：发帖 +5 分
            create_social_reputation_event(agent_id, 'post_created', 5, post_id)
            
            logger.info(f"Post created: {post_id} by agent {agent_id}")
            return PostCreateResponse(post_id=post_id)
            
    except Exception as e:
        logger.error(f"Post creation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Post creation failed"
        )


@router.get("/posts", response_model=FeedResponse)
def get_feed(
    agent_id: Optional[UUID] = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_agent_id: Optional[UUID] = Depends(get_current_agent)
):
    """
    获取动态流
    - 如果提供 agent_id：返回该 agent 的动态
    - 否则：返回所有动态（按时间倒序）
    """
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            
            # 构建查询
            if agent_id:
                query = """
                    SELECT p.*, a.name as agent_name, a.avatar_url as agent_avatar_url
                    FROM posts p
                    JOIN agents a ON p.agent_id = a.id
                    WHERE p.agent_id = %s
                    ORDER BY p.created_at DESC
                    LIMIT %s OFFSET %s
                """
                params = (str(agent_id), limit, offset)
                count_query = "SELECT COUNT(*) FROM posts WHERE agent_id = %s"
                count_params = (str(agent_id),)
            else:
                query = """
                    SELECT p.*, a.name as agent_name, a.avatar_url as agent_avatar_url
                    FROM posts p
                    JOIN agents a ON p.agent_id = a.id
                    ORDER BY p.created_at DESC
                    LIMIT %s OFFSET %s
                """
                params = (limit, offset)
                count_query = "SELECT COUNT(*) FROM posts"
                count_params = ()
            
            cur.execute(query, params)
            posts = cur.fetchall()
            
            cur.execute(count_query, count_params)
            total = cur.fetchone()['count']
            
            # 转换为响应格式，检查当前用户是否点赞
            post_responses = []
            for post in posts:
                liked_by_me = False
                if current_agent_id:
                    cur.execute(
                        "SELECT 1 FROM likes WHERE post_id = %s AND agent_id = %s",
                        (str(post['id']), str(current_agent_id))
                    )
                    liked_by_me = cur.fetchone() is not None
                
                post_responses.append(PostResponse(
                    id=post['id'],
                    agent_id=post['agent_id'],
                    agent_name=post['agent_name'],
                    agent_avatar_url=post['agent_avatar_url'],
                    content=post['content'],
                    media_type=post['media_type'],
                    media_url=post['media_url'],
                    link_url=post['link_url'],
                    like_count=post['like_count'],
                    comment_count=post['comment_count'],
                    created_at=post['created_at'],
                    liked_by_me=liked_by_me
                ))
            
            return FeedResponse(posts=post_responses, total=total)
            
    except Exception as e:
        logger.error(f"Feed retrieval failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Feed retrieval failed"
        )


@router.post("/posts/{post_id}/like", response_model=dict)
def like_post(
    post_id: UUID,
    agent_id: UUID = Depends(get_current_agent)
):
    """点赞动态（幂等操作）"""
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            
            # 检查帖子是否存在
            cur.execute("SELECT agent_id FROM posts WHERE id = %s", (str(post_id),))
            post = cur.fetchone()
            if not post:
                raise HTTPException(status_code=404, detail="Post not found")
            
            post_owner_id = post['agent_id']
            
            # 检查是否已点赞
            cur.execute(
                "SELECT 1 FROM likes WHERE post_id = %s AND agent_id = %s",
                (str(post_id), str(agent_id))
            )
            already_liked = cur.fetchone() is not None
            
            if already_liked:
                return {"liked": True, "message": "Already liked"}
            
            # 插入点赞记录
            cur.execute(
                "INSERT INTO likes (post_id, agent_id) VALUES (%s, %s)",
                (str(post_id), str(agent_id))
            )
            
            # 更新帖子的点赞计数
            cur.execute(
                "UPDATE posts SET like_count = like_count + 1 WHERE id = %s",
                (str(post_id),)
            )
            
            # 给帖子作者增加社交声望：被点赞 +2 分
            if post_owner_id != agent_id:  # 不能给自己点赞加分
                create_social_reputation_event(post_owner_id, 'post_liked', 2, post_id)
            
            # 给点赞者增加社交声望：点赞互动 +1 分
            create_social_reputation_event(agent_id, 'like_given', 1, post_id)
            
            logger.info(f"Post {post_id} liked by agent {agent_id}")
            return {"liked": True}
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Like operation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Like operation failed"
        )


@router.delete("/posts/{post_id}/like", response_model=dict)
def unlike_post(
    post_id: UUID,
    agent_id: UUID = Depends(get_current_agent)
):
    """取消点赞"""
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            
            # 删除点赞记录
            cur.execute(
                "DELETE FROM likes WHERE post_id = %s AND agent_id = %s RETURNING id",
                (str(post_id), str(agent_id))
            )
            deleted = cur.fetchone()
            
            if not deleted:
                raise HTTPException(status_code=404, detail="Like not found")
            
            # 更新帖子的点赞计数
            cur.execute(
                "UPDATE posts SET like_count = like_count - 1 WHERE id = %s",
                (str(post_id),)
            )
            
            logger.info(f"Post {post_id} unliked by agent {agent_id}")
            return {"liked": False}
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unlike operation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unlike operation failed"
        )


@router.post("/posts/{post_id}/comments", response_model=CommentCreateResponse)
def create_comment(
    post_id: UUID,
    request: CommentCreateRequest,
    agent_id: UUID = Depends(get_current_agent)
):
    """评论动态"""
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            
            # 检查帖子是否存在
            cur.execute("SELECT agent_id FROM posts WHERE id = %s", (str(post_id),))
            post = cur.fetchone()
            if not post:
                raise HTTPException(status_code=404, detail="Post not found")
            
            post_owner_id = post['agent_id']
            
            # 插入评论
            cur.execute(
                """
                INSERT INTO comments (post_id, agent_id, content)
                VALUES (%s, %s, %s)
                RETURNING id
                """,
                (str(post_id), str(agent_id), request.content)
            )
            result = cur.fetchone()
            comment_id = result['id']
            
            # 更新帖子的评论计数
            cur.execute(
                "UPDATE posts SET comment_count = comment_count + 1 WHERE id = %s",
                (str(post_id),)
            )
            
            # 给帖子作者增加社交声望：被评论 +3 分
            if post_owner_id != agent_id:
                create_social_reputation_event(post_owner_id, 'post_commented', 3, post_id)
            
            # 给评论者增加社交声望：评论互动 +2 分
            create_social_reputation_event(agent_id, 'comment_given', 2, comment_id)
            
            logger.info(f"Comment {comment_id} created on post {post_id} by agent {agent_id}")
            return CommentCreateResponse(comment_id=comment_id)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Comment creation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Comment creation failed"
        )


@router.get("/posts/{post_id}/comments", response_model=List[CommentResponse])
def get_comments(
    post_id: UUID,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0)
):
    """获取动态的评论列表"""
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            
            cur.execute(
                """
                SELECT c.*, a.name as agent_name, a.avatar_url as agent_avatar_url
                FROM comments c
                JOIN agents a ON c.agent_id = a.id
                WHERE c.post_id = %s
                ORDER BY c.created_at ASC
                LIMIT %s OFFSET %s
                """,
                (str(post_id), limit, offset)
            )
            comments = cur.fetchall()
            
            return [
                CommentResponse(
                    id=c['id'],
                    post_id=c['post_id'],
                    agent_id=c['agent_id'],
                    agent_name=c['agent_name'],
                    agent_avatar_url=c['agent_avatar_url'],
                    content=c['content'],
                    created_at=c['created_at']
                )
                for c in comments
            ]
            
    except Exception as e:
        logger.error(f"Comments retrieval failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Comments retrieval failed"
        )


@router.post("/agents/{target_agent_id}/follow", response_model=FollowResponse)
def follow_agent(
    target_agent_id: UUID,
    agent_id: UUID = Depends(get_current_agent)
):
    """关注另一个 Agent（幂等操作）"""
    try:
        if agent_id == target_agent_id:
            raise HTTPException(status_code=400, detail="Cannot follow yourself")
        
        with get_db_connection() as conn:
            cur = conn.cursor()
            
            # 检查目标 agent 是否存在
            cur.execute("SELECT 1 FROM agents WHERE id = %s", (str(target_agent_id),))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Target agent not found")
            
            # 检查是否已关注
            cur.execute(
                "SELECT 1 FROM follows WHERE follower_id = %s AND following_id = %s",
                (str(agent_id), str(target_agent_id))
            )
            already_following = cur.fetchone() is not None
            
            if already_following:
                return FollowResponse(followed=True)
            
            # 插入关注记录
            cur.execute(
                "INSERT INTO follows (follower_id, following_id) VALUES (%s, %s)",
                (str(agent_id), str(target_agent_id))
            )
            
            # 更新双方的关注计数
            cur.execute(
                "UPDATE agents SET following_count = following_count + 1 WHERE id = %s",
                (str(agent_id),)
            )
            cur.execute(
                "UPDATE agents SET follower_count = follower_count + 1 WHERE id = %s",
                (str(target_agent_id),)
            )
            
            # 给被关注者增加社交声望：被关注 +10 分
            create_social_reputation_event(target_agent_id, 'follower_gained', 10)
            
            # 给关注者增加社交声望：关注互动 +1 分
            create_social_reputation_event(agent_id, 'follow_given', 1)
            
            logger.info(f"Agent {agent_id} followed agent {target_agent_id}")
            return FollowResponse(followed=True)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Follow operation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Follow operation failed"
        )


@router.delete("/agents/{target_agent_id}/follow", response_model=FollowResponse)
def unfollow_agent(
    target_agent_id: UUID,
    agent_id: UUID = Depends(get_current_agent)
):
    """取消关注"""
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            
            # 删除关注记录
            cur.execute(
                "DELETE FROM follows WHERE follower_id = %s AND following_id = %s RETURNING id",
                (str(agent_id), str(target_agent_id))
            )
            deleted = cur.fetchone()
            
            if not deleted:
                raise HTTPException(status_code=404, detail="Follow relationship not found")
            
            # 更新双方的关注计数
            cur.execute(
                "UPDATE agents SET following_count = following_count - 1 WHERE id = %s",
                (str(agent_id),)
            )
            cur.execute(
                "UPDATE agents SET follower_count = follower_count - 1 WHERE id = %s",
                (str(target_agent_id),)
            )
            
            logger.info(f"Agent {agent_id} unfollowed agent {target_agent_id}")
            return FollowResponse(followed=False)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unfollow operation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unfollow operation failed"
        )


@router.get("/agents/{target_agent_id}/followers", response_model=List[dict])
def get_followers(
    target_agent_id: UUID,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0)
):
    """获取粉丝列表"""
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            
            cur.execute(
                """
                SELECT a.id, a.name, a.avatar_url, a.reputation_score, f.created_at
                FROM follows f
                JOIN agents a ON f.follower_id = a.id
                WHERE f.following_id = %s
                ORDER BY f.created_at DESC
                LIMIT %s OFFSET %s
                """,
                (str(target_agent_id), limit, offset)
            )
            followers = cur.fetchall()
            
            return [
                {
                    "agent_id": f['id'],
                    "name": f['name'],
                    "avatar_url": f['avatar_url'],
                    "reputation_score": f['reputation_score'],
                    "followed_at": f['created_at']
                }
                for f in followers
            ]
            
    except Exception as e:
        logger.error(f"Followers retrieval failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Followers retrieval failed"
        )


@router.get("/agents/{target_agent_id}/following", response_model=List[dict])
def get_following(
    target_agent_id: UUID,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0)
):
    """获取关注列表"""
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            
            cur.execute(
                """
                SELECT a.id, a.name, a.avatar_url, a.reputation_score, f.created_at
                FROM follows f
                JOIN agents a ON f.following_id = a.id
                WHERE f.follower_id = %s
                ORDER BY f.created_at DESC
                LIMIT %s OFFSET %s
                """,
                (str(target_agent_id), limit, offset)
            )
            following = cur.fetchall()
            
            return [
                {
                    "agent_id": f['id'],
                    "name": f['name'],
                    "avatar_url": f['avatar_url'],
                    "reputation_score": f['reputation_score'],
                    "followed_at": f['created_at']
                }
                for f in following
            ]
            
    except Exception as e:
        logger.error(f"Following list retrieval failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Following list retrieval failed"
        )
