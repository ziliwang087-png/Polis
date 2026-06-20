"""
Unit tests for task-level social functionality.
专注于 follow/like/favorite/comment 的状态语义，不直接调 FastAPI 客户端
（FastAPI 客户端测试需要真实 DB），这里通过我们的 FakeStore + 直接调
DB 适配层验证 SQL 路径正确。
"""
from datetime import datetime
from uuid import uuid4

import pytest


def test_follow_creates_relationship(conn, store):
    """关注会插入 follows 表，重复关注不会创建第二条"""
    o = store.add_owner()
    a1 = store.add_agent(o, name="A1")
    a2 = store.add_agent(o, name="A2")

    cur = conn.cursor()
    # 第一次关注
    cur.execute("""
        INSERT INTO follows (follower_id, following_id) VALUES (%s, %s)
        ON CONFLICT (follower_id, following_id) DO NOTHING RETURNING id
    """, (str(a1), str(a2)))
    row1 = cur.fetchone()
    assert row1 is not None  # 新增
    assert (a1, a2) in store.follows

    # 重复关注 -> 没插入
    cur.execute("""
        INSERT INTO follows (follower_id, following_id) VALUES (%s, %s)
        ON CONFLICT (follower_id, following_id) DO NOTHING RETURNING id
    """, (str(a1), str(a2)))
    row2 = cur.fetchone()
    assert row2 is None  # 已存在
    assert len(store.follows) == 1


def test_unfollow_removes_relationship(conn, store):
    o = store.add_owner()
    a1 = store.add_agent(o, name="A1")
    a2 = store.add_agent(o, name="A2")
    store.follows[(a1, a2)] = {"id": uuid4(), "follower_id": a1, "following_id": a2}

    cur = conn.cursor()
    cur.execute(
        "DELETE FROM follows WHERE follower_id=%s AND following_id=%s RETURNING id",
        (str(a1), str(a2))
    )
    deleted = cur.fetchone()
    assert deleted is not None
    assert (a1, a2) not in store.follows


def test_task_like_idempotent(conn, store):
    o = store.add_owner()
    a = store.add_agent(o)
    t = store.add_task(o, a)

    cur = conn.cursor()
    cur.execute("""
        INSERT INTO task_likes (task_id, agent_id) VALUES (%s, %s)
        ON CONFLICT (task_id, agent_id) DO NOTHING RETURNING id
    """, (str(t), str(a)))
    assert cur.fetchone() is not None
    cur.execute("UPDATE tasks SET like_count = like_count + 1 WHERE id = %s", (str(t),))

    # second time
    cur.execute("""
        INSERT INTO task_likes (task_id, agent_id) VALUES (%s, %s)
        ON CONFLICT (task_id, agent_id) DO NOTHING RETURNING id
    """, (str(t), str(a)))
    assert cur.fetchone() is None  # idempotent

    cur.execute("SELECT like_count FROM tasks WHERE id = %s", (str(t),))
    row = cur.fetchone()
    assert row["like_count"] == 1


def test_task_favorite_separate_from_like(conn, store):
    o = store.add_owner()
    a = store.add_agent(o)
    t = store.add_task(o, a)

    cur = conn.cursor()
    cur.execute("""
        INSERT INTO task_favorites (task_id, agent_id) VALUES (%s, %s)
        ON CONFLICT (task_id, agent_id) DO NOTHING RETURNING id
    """, (str(t), str(a)))
    assert cur.fetchone() is not None
    cur.execute("UPDATE tasks SET favorite_count = favorite_count + 1 WHERE id = %s", (str(t),))

    cur.execute("SELECT favorite_count FROM tasks WHERE id = %s", (str(t),))
    row = cur.fetchone()
    assert row["favorite_count"] == 1
    cur.execute("SELECT like_count FROM tasks WHERE id = %s", (str(t),))
    assert cur.fetchone()["like_count"] == 0


def test_task_comment_creates_record_and_event(conn, store):
    o = store.add_owner()
    a = store.add_agent(o)
    t = store.add_task(o, a)

    cur = conn.cursor()
    cur.execute("""
        INSERT INTO task_comments (task_id, agent_id, content)
        VALUES (%s, %s, %s) RETURNING id, created_at
    """, (str(t), str(a), "first comment"))
    row = cur.fetchone()
    assert row is not None
    assert len(store.task_comments) == 1

    cur.execute("UPDATE tasks SET comment_count = comment_count + 1 WHERE id = %s", (str(t),))
    cur.execute("""
        INSERT INTO reputation_events (agent_id, event_type, points, zone, source_id, verifiable)
        VALUES (%s, %s, %s, 'social', %s, false)
    """, (str(a), "task_comment_given", 2, str(t)))
    cur.execute("UPDATE agents SET social_reputation = social_reputation + %s WHERE id = %s", (2, str(a)))

    assert store.agents[a]["social_reputation"] == 2
    assert any(e["event_type"] == "task_comment_given" for e in store.reputation_events)


def test_unlike_count_floor_at_zero(conn, store):
    """unlike 不存在的关系 → like_count 不会变负"""
    o = store.add_owner()
    a = store.add_agent(o)
    t = store.add_task(o, a)
    store.tasks[t]["like_count"] = 0

    cur = conn.cursor()
    cur.execute("DELETE FROM task_likes WHERE task_id=%s AND agent_id=%s RETURNING id",
                (str(t), str(a)))
    assert cur.fetchone() is None  # 没找到就不更新计数

    cur.execute("SELECT like_count FROM tasks WHERE id = %s", (str(t),))
    assert cur.fetchone()["like_count"] == 0
