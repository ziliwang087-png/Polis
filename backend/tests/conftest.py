"""
Pytest conftest — 提供假 DB 给 anti_fraud 单元测试用。
不依赖真实 PostgreSQL，纯 Python 字典模拟 RealDictCursor。
"""
from __future__ import annotations

import re
import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

import pytest


class FakeCursor:
    """
    一个最小化的 psycopg2 RealDictCursor 兼容假货：
    - 支持 cur.execute(sql, params) / cur.fetchone() / cur.fetchall()
    - 通过 SQL 关键字粗匹配，把请求路由到内存 store 上
    - 仅覆盖 anti_fraud / task_social / admin 用到的查询
    """

    def __init__(self, store: "FakeStore"):
        self.store = store
        self._last: list[dict] = []
        self._idx = 0

    # --- helpers ---
    def _result(self, rows: list[dict]):
        self._last = rows
        self._idx = 0

    def fetchone(self):
        if self._idx >= len(self._last):
            return None
        row = self._last[self._idx]
        self._idx += 1
        return row

    def fetchall(self):
        rows = self._last[self._idx:]
        self._idx = len(self._last)
        return rows

    # --- main router ---
    def execute(self, sql: str, params: tuple | list = ()):
        s = sql.strip()
        sl = s.lower()
        params = list(params)

        # ====== TASK detail (gather_context: SELECT t.id, t.description ...) =====
        if "from tasks t where t.id = %s" in sl and "t.description" in sl and "select t.id" in sl:
            tid = uuid.UUID(params[0])
            t = self.store.tasks.get(tid)
            if not t:
                self._result([])
                return
            sub = self.store.latest_submission(tid)
            review_rating = self.store.latest_rating(tid)
            self._result([{
                "id": t["id"],
                "description": t["description"],
                "reward_points": t["reward_points"],
                "task_created_at": t["created_at"],
                "task_completed_at": t.get("completed_at"),
                "rating": review_rating,
                "submission_content": sub["content"] if sub else None,
            }])
            return

        # ====== owner→agent recent tasks =====
        if "select t.id as task_id, t.created_at" in sl and "where t.owner_id = %s and t.assigned_agent_id" in sl:
            owner_id = uuid.UUID(params[0])
            agent_id = uuid.UUID(params[1])
            cutoff = datetime.now() - timedelta(days=30)
            out = []
            for t in self.store.tasks.values():
                if t["owner_id"] != owner_id: continue
                if t.get("assigned_agent_id") != agent_id: continue
                if t["created_at"] < cutoff: continue
                out.append({
                    "task_id": t["id"],
                    "created_at": t["created_at"],
                    "rating": self.store.latest_rating(t["id"]),
                })
            self._result(out)
            return

        # ====== agent owner lookup =====
        if sl.startswith("select owner_id from agents where id = %s"):
            agent_id = uuid.UUID(params[0])
            a = self.store.agents.get(agent_id)
            self._result([{"owner_id": a["owner_id"]}] if a else [])
            return

        # ====== mutual review reverse query =====
        if "where t.owner_id = %s" in sl and "t.assigned_agent_id in (select id from agents where owner_id = %s)" in sl:
            other_owner_id = uuid.UUID(params[0])
            this_owner_id  = uuid.UUID(params[1])
            this_owners_agents = {a["id"] for a in self.store.agents.values() if a["owner_id"] == this_owner_id}
            cutoff = datetime.now() - timedelta(days=90)
            out = []
            for t in self.store.tasks.values():
                if t["owner_id"] != other_owner_id: continue
                if t.get("assigned_agent_id") not in this_owners_agents: continue
                if t["created_at"] < cutoff: continue
                out.append({
                    "task_id": t["id"],
                    "rating": self.store.latest_rating(t["id"]),
                })
            self._result(out)
            return

        # ====== owner signup_ip =====
        if sl.startswith("select signup_ip from owners where id = %s"):
            oid = uuid.UUID(params[0])
            o = self.store.owners.get(oid)
            self._result([{"signup_ip": o.get("signup_ip")}] if o else [])
            return

        # ====== INSERT INTO fraud_alerts =====
        if "insert into fraud_alerts" in sl:
            agent_id, owner_id, task_id, rule_name, severity, evidence_json = params[:6]
            new_id = uuid.uuid4()
            self.store.fraud_alerts[new_id] = {
                "id": new_id,
                "agent_id": uuid.UUID(agent_id) if agent_id else None,
                "owner_id": uuid.UUID(owner_id) if owner_id else None,
                "task_id": uuid.UUID(task_id) if task_id else None,
                "rule_name": rule_name,
                "severity": float(severity),
                "evidence": __import__("json").loads(evidence_json) if isinstance(evidence_json, str) else evidence_json,
                "status": "open",
                "reviewer_id": None,
                "reviewer_note": None,
                "detected_at": datetime.now(),
                "reviewed_at": None,
            }
            self._result([{"id": new_id}])
            return

        # ====== reputation_events sum by zone =====
        if "from reputation_events" in sl and "group by zone" in sl:
            agent_id = uuid.UUID(params[0])
            sums = defaultdict(int)
            for e in self.store.reputation_events:
                if e["agent_id"] == agent_id:
                    sums[e["zone"]] += e["points"]
            self._result([{"zone": z, "pts": p} for z, p in sums.items()])
            return

        # ====== fraud_alerts SUM (compute_fraud_penalty) =====
        if "from fraud_alerts" in sl and "group by rule_name" in sl:
            agent_id = uuid.UUID(params[0])
            grouped: dict[str, float] = {}
            for a in self.store.fraud_alerts.values():
                if a["agent_id"] != agent_id: continue
                if a["status"] not in ("open", "confirmed"): continue
                grouped[a["rule_name"]] = max(grouped.get(a["rule_name"], 0), a["severity"])
            self._result([{"rule_name": k, "severity": v} for k, v in grouped.items()])
            return

        # ====== INSERT INTO reputation_scores ... ON CONFLICT =====
        if "insert into reputation_scores" in sl:
            agent_id, quality, social, total, fraud_penalty = params[:5]
            self.store.reputation_scores[uuid.UUID(agent_id)] = {
                "quality_score": int(quality),
                "social_score": int(social),
                "total_score": int(total),
                "fraud_penalty": float(fraud_penalty),
            }
            self._result([])
            return

        # ====== INSERT INTO reputation_events =====
        if "insert into reputation_events" in sl:
            agent_id, event_type, points, zone = params[:4]
            self.store.reputation_events.append({
                "agent_id": uuid.UUID(agent_id),
                "event_type": event_type,
                "points": int(points),
                "zone": zone,
                "source_id": uuid.UUID(params[4]) if len(params) > 4 and params[4] else None,
                "verifiable": params[5] if len(params) > 5 else False,
                "created_at": datetime.now(),
            })
            self._result([])
            return

        # ====== UPDATE agents social_reputation =====
        if "update agents" in sl and "social_reputation" in sl:
            points, agent_id = params
            a = self.store.agents.get(uuid.UUID(agent_id))
            if a:
                a["social_reputation"] = a.get("social_reputation", 0) + int(points)
            self._result([])
            return

        # ====== INSERT INTO task_likes / task_favorites / task_comments / follows ON CONFLICT =====
        for tbl, store_attr, fields in [
            ("task_likes", "task_likes", ("task_id", "agent_id")),
            ("task_favorites", "task_favorites", ("task_id", "agent_id")),
            ("follows", "follows", ("follower_id", "following_id")),
        ]:
            if f"insert into {tbl}" in sl and "on conflict" in sl:
                key = tuple(uuid.UUID(p) for p in params[:len(fields)])
                store = getattr(self.store, store_attr)
                if key in store:
                    self._result([])  # no insert
                else:
                    new_id = uuid.uuid4()
                    store[key] = {"id": new_id, **dict(zip(fields, key))}
                    self._result([{"id": new_id}])
                return

        if "insert into task_comments" in sl:
            task_id, agent_id, content = params
            new_id = uuid.uuid4()
            now = datetime.now()
            self.store.task_comments[new_id] = {
                "id": new_id, "task_id": uuid.UUID(task_id),
                "agent_id": uuid.UUID(agent_id), "content": content, "created_at": now,
            }
            self._result([{"id": new_id, "created_at": now}])
            return

        # ====== UPDATE tasks like/favorite/comment count =====
        m = re.search(r"update tasks set (\w+) = (\w+) ([\+\-]) 1", sl)
        if m:
            field, _, op = m.groups()
            tid = uuid.UUID(params[0])
            t = self.store.tasks.get(tid)
            if t:
                t[field] = max(0, t.get(field, 0) + (1 if op == "+" else -1))
            self._result([])
            return
        # 兼容 GREATEST(... - 1, 0)
        m2 = re.search(r"update tasks set (\w+) = greatest\(\1 - 1, 0\)", sl)
        if m2:
            field = m2.group(1)
            tid = uuid.UUID(params[0])
            t = self.store.tasks.get(tid)
            if t:
                t[field] = max(0, t.get(field, 0) - 1)
            self._result([])
            return

        # ====== SELECT 1 FROM tasks WHERE id = %s =====
        if sl.startswith("select 1 from tasks where id = %s"):
            tid = uuid.UUID(params[0])
            self._result([{"?column?": 1}] if tid in self.store.tasks else [])
            return

        if sl.startswith("select 1 from agents where id = %s"):
            aid = uuid.UUID(params[0])
            self._result([{"?column?": 1}] if aid in self.store.agents else [])
            return

        # ====== SELECT like_count / favorite_count =====
        m = re.search(r"select (like_count|favorite_count|comment_count) from tasks where id = %s", sl)
        if m:
            field = m.group(1)
            tid = uuid.UUID(params[0])
            t = self.store.tasks.get(tid)
            self._result([{field: t.get(field, 0)}] if t else [])
            return

        # ====== SELECT name FROM agents =====
        if sl.startswith("select name from agents where id = %s"):
            aid = uuid.UUID(params[0])
            a = self.store.agents.get(aid)
            self._result([{"name": a["name"]}] if a else [])
            return

        # ====== DELETE follow / like / favorite =====
        for tbl, store_attr, fields in [
            ("task_likes", "task_likes", ("task_id", "agent_id")),
            ("task_favorites", "task_favorites", ("task_id", "agent_id")),
            ("follows", "follows", ("follower_id", "following_id")),
        ]:
            if f"delete from {tbl}" in sl:
                key = tuple(uuid.UUID(p) for p in params[:len(fields)])
                store = getattr(self.store, store_attr)
                row = store.pop(key, None)
                self._result([{"id": row["id"]}] if row else [])
                return

        # ====== UPDATE agents follow counts =====
        if "update agents set following_count" in sl or "update agents set follower_count" in sl:
            self._result([])
            return

        # ====== UPDATE fraud_alerts (人工审核) =====
        if sl.startswith("update fraud_alerts"):
            new_status, reviewer_id, note, alert_id = params
            a = self.store.fraud_alerts.get(uuid.UUID(alert_id))
            if a:
                a["status"] = new_status
                a["reviewer_id"] = uuid.UUID(reviewer_id) if reviewer_id else None
                a["reviewer_note"] = note
                a["reviewed_at"] = datetime.now()
            self._result([])
            return

        # ====== SELECT agent_id, status FROM fraud_alerts =====
        if sl.startswith("select agent_id, status from fraud_alerts where id = %s"):
            a = self.store.fraud_alerts.get(uuid.UUID(params[0]))
            if a:
                self._result([{"agent_id": a["agent_id"], "status": a["status"]}])
            else:
                self._result([])
            return

        # ====== fall-through =====
        # 未识别的 SQL 直接置空（测试只检查特定路径）
        self._result([])


class FakeConnection:
    def __init__(self, store: "FakeStore"):
        self.store = store

    def cursor(self):
        return FakeCursor(self.store)

    def commit(self): pass
    def rollback(self): pass
    def close(self): pass


class FakeStore:
    """全局测试数据存储"""
    def __init__(self):
        self.owners: dict[uuid.UUID, dict] = {}
        self.agents: dict[uuid.UUID, dict] = {}
        self.tasks: dict[uuid.UUID, dict] = {}
        self.task_submissions: list[dict] = []
        self.task_reviews: list[dict] = []
        self.reputation_events: list[dict] = []
        self.reputation_scores: dict[uuid.UUID, dict] = {}
        self.fraud_alerts: dict[uuid.UUID, dict] = {}
        self.task_likes: dict[tuple, dict] = {}
        self.task_favorites: dict[tuple, dict] = {}
        self.task_comments: dict[uuid.UUID, dict] = {}
        self.follows: dict[tuple, dict] = {}

    def add_owner(self, signup_ip: str | None = None) -> uuid.UUID:
        oid = uuid.uuid4()
        self.owners[oid] = {"id": oid, "signup_ip": signup_ip}
        return oid

    def add_agent(self, owner_id: uuid.UUID, name: str = "Bot") -> uuid.UUID:
        aid = uuid.uuid4()
        self.agents[aid] = {
            "id": aid, "owner_id": owner_id, "name": name,
            "social_reputation": 0,
        }
        return aid

    def add_task(self, owner_id: uuid.UUID, agent_id: uuid.UUID,
                 description: str = "Some task description that is long enough", reward_points: int = 10,
                 created_at: datetime | None = None,
                 completed_at: datetime | None = None) -> uuid.UUID:
        tid = uuid.uuid4()
        now = datetime.now()
        self.tasks[tid] = {
            "id": tid,
            "owner_id": owner_id,
            "assigned_agent_id": agent_id,
            "description": description,
            "reward_points": reward_points,
            "created_at": created_at or now,
            "completed_at": completed_at or now,
            "title": "test task",
            "like_count": 0,
            "favorite_count": 0,
            "comment_count": 0,
        }
        return tid

    def add_review(self, task_id: uuid.UUID, rating: int, submission_content: str = "Submission content of reasonable length"):
        sid = uuid.uuid4()
        rid = uuid.uuid4()
        now = datetime.now()
        self.task_submissions.append({
            "id": sid, "task_id": task_id, "content": submission_content,
            "submitted_at": now,
        })
        self.task_reviews.append({
            "id": rid, "task_id": task_id, "submission_id": sid,
            "rating": rating, "reviewed_at": now,
        })

    def latest_submission(self, task_id: uuid.UUID):
        subs = [s for s in self.task_submissions if s["task_id"] == task_id]
        return sorted(subs, key=lambda s: s["submitted_at"], reverse=True)[0] if subs else None

    def latest_rating(self, task_id: uuid.UUID):
        reviews = [r for r in self.task_reviews if r["task_id"] == task_id]
        if not reviews:
            return None
        return max(r["rating"] for r in reviews)


@pytest.fixture
def store() -> FakeStore:
    return FakeStore()


@pytest.fixture
def conn(store: FakeStore) -> FakeConnection:
    return FakeConnection(store)
