from __future__ import annotations

import asyncio
import base64
import json
import os
import re
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")


def _plain(value: Any) -> Any:
    if hasattr(value, "adapted"):
        return value.adapted
    return value


class FakePolisStore:
    def __init__(self):
        self.users: dict[uuid.UUID, dict[str, Any]] = {}
        self.agents: dict[uuid.UUID, dict[str, Any]] = {}
        self.agent_skills: dict[uuid.UUID, dict[str, Any]] = {}
        self.tasks: dict[uuid.UUID, dict[str, Any]] = {}
        self.task_submissions: dict[uuid.UUID, dict[str, Any]] = {}
        self.jobs: dict[uuid.UUID, dict[str, Any]] = {}
        self.job_artifacts: dict[uuid.UUID, dict[str, Any]] = {}
        self.job_ratings: dict[uuid.UUID, dict[str, Any]] = {}
        self.job_events: dict[uuid.UUID, dict[str, Any]] = {}
        self.community_posts: dict[uuid.UUID, dict[str, Any]] = {}
        self.community_comments: dict[uuid.UUID, dict[str, Any]] = {}
        self.post_likes: set[tuple[uuid.UUID, uuid.UUID]] = set()
        self.queries: list[str] = []
        self.notifications: list[dict[str, Any]] = []
        self.uploads: list[dict[str, Any]] = []

    def now(self) -> datetime:
        return datetime.now(timezone.utc).replace(tzinfo=None)

    def add_event(self, job_id: uuid.UUID, event_type: str, payload: dict[str, Any]):
        event_id = uuid.uuid4()
        row = {
            "id": event_id,
            "job_id": job_id,
            "event_type": event_type,
            "payload": payload,
            "created_at": self.now(),
        }
        self.job_events[event_id] = row
        return row


class FakeCursor:
    def __init__(self, store: FakePolisStore):
        self.store = store
        self._rows: list[dict[str, Any]] = []

    def fetchone(self):
        return self._rows.pop(0) if self._rows else None

    def fetchall(self):
        rows = self._rows
        self._rows = []
        return rows

    def execute(self, sql: str, params: tuple | list | None = None):
        params = list(params or [])
        compact = re.sub(r"\s+", " ", sql.strip()).lower()
        self.store.queries.append(compact)

        # users
        if "select id from users where email = %s or username = %s" in compact:
            email, username = params
            self._rows = [
                {"id": row["id"]}
                for row in self.store.users.values()
                if row["email"] == email or row["username"] == username
            ]
            return

        if compact.startswith("insert into users"):
            email, password_hash, username, display_name, avatar_url = params[:5]
            uid = uuid.uuid4()
            row = {
                "id": uid,
                "email": email,
                "password_hash": password_hash,
                "username": username,
                "display_name": display_name,
                "avatar_url": avatar_url,
                "reputation": 0,
                "credit_balance": 10,
                "created_at": self.store.now(),
                "updated_at": self.store.now(),
            }
            self.store.users[uid] = row
            self._rows = [row]
            return

        if "select * from users where email = %s or username = %s" in compact:
            email, username = params
            self._rows = [
                row for row in self.store.users.values()
                if row["email"] == email or row["username"] == username
            ][:1]
            return

        if "select * from users where id = %s" in compact:
            uid = uuid.UUID(str(params[0]))
            self._rows = [self.store.users[uid]] if uid in self.store.users else []
            return

        if "update users set credit_balance = credit_balance - 1" in compact:
            uid = uuid.UUID(str(params[0]))
            row = self.store.users.get(uid)
            if row and row["credit_balance"] > 0:
                row["credit_balance"] -= 1
                row["updated_at"] = self.store.now()
                self._rows = [{"credit_balance": row["credit_balance"]}]
            else:
                self._rows = []
            return

        if "update users set credit_balance = credit_balance + 1" in compact:
            uid = uuid.UUID(str(params[0]))
            if uid in self.store.users:
                self.store.users[uid]["credit_balance"] += 1
            self._rows = []
            return

        # agents
        if "select id from agents where owner_id = %s and name = %s" in compact:
            owner_id, name = uuid.UUID(str(params[0])), params[1]
            self._rows = [
                {"id": row["id"]}
                for row in self.store.agents.values()
                if row["owner_id"] == owner_id and row["name"] == name
            ]
            return

        if compact.startswith("insert into agents"):
            (
                owner_id, name, display_name, description, endpoint_url, websocket_id,
                auth_method, auth_config, agent_card, status,
            ) = params[:10]
            aid = uuid.uuid4()
            row = {
                "id": aid,
                "owner_id": uuid.UUID(str(owner_id)),
                "name": name,
                "display_name": display_name,
                "description": description,
                "endpoint_url": endpoint_url,
                "websocket_id": websocket_id,
                "auth_method": auth_method,
                "auth_config": _plain(auth_config),
                "agent_card": _plain(agent_card),
                "status": status,
                "last_heartbeat_at": None,
                "total_jobs": 0,
                "success_rate": 0.0,
                "avg_rating": None,
                "xp": 0,
                "level": 1,
                "total_tasks_completed": 0,
                "total_tasks_failed": 0,
                "badge_count": 0,
                "created_at": self.store.now(),
                "updated_at": self.store.now(),
            }
            self.store.agents[aid] = row
            self._rows = [row]
            return

        if compact.startswith("insert into agent_skills"):
            if len(params) >= 7:
                agent_id, skill_id, name, description, examples, input_schema, output_schema = params[:7]
            else:
                agent_id, skill_id, name = params[:3]
                description = examples = input_schema = output_schema = None
            sid = uuid.uuid4()
            self.store.agent_skills[sid] = {
                "id": sid,
                "agent_id": uuid.UUID(str(agent_id)),
                "skill_id": skill_id,
                "name": name,
                "description": description,
                "examples": _plain(examples),
                "input_schema": _plain(input_schema),
                "output_schema": _plain(output_schema),
            }
            self._rows = []
            return

        if "select * from agents where id = %s" in compact:
            aid = uuid.UUID(str(params[0]))
            self._rows = [self.store.agents[aid]] if aid in self.store.agents else []
            return

        if compact == "select status from agents where id = %s":
            aid = uuid.UUID(str(params[0]))
            row = self.store.agents.get(aid)
            self._rows = [{"status": row["status"]}] if row else []
            return

        if compact == "select total_tasks_completed from agents where id = %s":
            aid = uuid.UUID(str(params[0]))
            row = self.store.agents.get(aid)
            self._rows = [{"total_tasks_completed": row.get("total_tasks_completed", 0)}] if row else []
            return

        if "select * from agents where owner_id = %s" in compact:
            owner_id = uuid.UUID(str(params[0]))
            self._rows = [row for row in self.store.agents.values() if row["owner_id"] == owner_id]
            return

        if "select skill_id, name, description, examples, input_schema, output_schema from agent_skills where agent_id = %s" in compact:
            agent_id = uuid.UUID(str(params[0]))
            self._rows = [
                {
                    "skill_id": row["skill_id"],
                    "name": row["name"],
                    "description": row["description"],
                    "examples": row["examples"],
                    "input_schema": row["input_schema"],
                    "output_schema": row["output_schema"],
                }
                for row in self.store.agent_skills.values()
                if row["agent_id"] == agent_id
            ]
            return

        if "select * from agents" in compact and "where" not in compact:
            self._rows = list(self.store.agents.values())
            return

        if compact.startswith("update agents set status = %s, last_heartbeat_at"):
            status_value, aid = params[0], uuid.UUID(str(params[1]))
            self.store.agents[aid]["status"] = status_value
            self.store.agents[aid]["last_heartbeat_at"] = self.store.now()
            self.store.agents[aid]["updated_at"] = self.store.now()
            self._rows = [self.store.agents[aid]]
            return

        if compact.startswith("update agents set total_jobs = total_jobs + 1"):
            aid = uuid.UUID(str(params[0]))
            self.store.agents[aid]["total_jobs"] += 1
            self._rows = []
            return

        if compact.startswith("update agents set avg_rating"):
            aid = uuid.UUID(str(params[0]))
            ratings = [
                row["stars"]
                for row in self.store.job_ratings.values()
                if self.store.jobs[row["job_id"]]["to_agent_id"] == aid
            ]
            self.store.agents[aid]["avg_rating"] = sum(ratings) / len(ratings)
            self.store.agents[aid]["success_rate"] = 1.0
            self._rows = []
            return

        if compact.startswith("update agents set xp = xp + %s"):
            xp_gain, level_xp_gain, aid = int(params[0]), int(params[1]), uuid.UUID(str(params[2]))
            row = self.store.agents[aid]
            row["xp"] = row.get("xp", 0) + xp_gain
            row["level"] = int((row["xp"]) / 100.0) + 1
            if "total_tasks_completed = total_tasks_completed + 1" in compact:
                row["total_tasks_completed"] = row.get("total_tasks_completed", 0) + 1
            self._rows = [{
                "xp": row["xp"],
                "level": row["level"],
                "total_tasks_completed": row.get("total_tasks_completed", 0),
            }]
            assert xp_gain == level_xp_gain
            return

        if compact.startswith("insert into badges"):
            self._rows = []
            return

        if compact.startswith("delete from agents"):
            aid, owner_id = uuid.UUID(str(params[0])), uuid.UUID(str(params[1]))
            row = self.store.agents.get(aid)
            if row and row["owner_id"] == owner_id:
                del self.store.agents[aid]
                self._rows = [{"id": aid}]
            else:
                self._rows = []
            return

        # community
        if compact.startswith("insert into posts") and "title, content, author_type, author_id, category" in compact:
            title, content, author_id, category = params[:4]
            author_type = "agent" if "'agent'" in compact else "user"
            pid = uuid.uuid4()
            row = {
                "id": pid,
                "title": title,
                "content": content,
                "author_type": author_type,
                "author_id": uuid.UUID(str(author_id)),
                "category": category,
                "likes": 0,
                "created_at": self.store.now(),
                "updated_at": self.store.now(),
            }
            self.store.community_posts[pid] = row
            self._rows = [{"id": pid}]
            return

        if compact.startswith("select p.id, p.title, p.content") and "from posts p" in compact:
            rows = list(self.store.community_posts.values())
            if "where p.category = %s" in compact:
                rows = [row for row in rows if row["category"] == params[0]]
            elif "where p.id = %s" in compact:
                pid = uuid.UUID(str(params[0]))
                rows = [self.store.community_posts[pid]] if pid in self.store.community_posts else []
            rows.sort(key=lambda row: row["created_at"], reverse=True)
            out = []
            for row in rows:
                author_name = None
                if row["author_type"] == "user":
                    user = self.store.users.get(row["author_id"])
                    if user:
                        author_name = user.get("display_name") or user.get("username")
                else:
                    agent = self.store.agents.get(row["author_id"])
                    if agent:
                        author_name = agent.get("display_name") or agent.get("name")
                out.append({
                    **row,
                    "author_name": author_name,
                    "comment_count": len([
                        c for c in self.store.community_comments.values()
                        if c["post_id"] == row["id"]
                    ]),
                })
            self._rows = out
            return

        if compact.startswith("select count(*) as count from posts p"):
            rows = list(self.store.community_posts.values())
            if "where p.category = %s" in compact:
                rows = [row for row in rows if row["category"] == params[0]]
            self._rows = [{"count": len(rows)}]
            return

        if compact.startswith("select 1 from posts where id = %s"):
            pid = uuid.UUID(str(params[0]))
            self._rows = [{"?column?": 1}] if pid in self.store.community_posts else []
            return

        if compact.startswith("insert into comments"):
            post_id, author_type, author_id, content = params[:4]
            cid = uuid.uuid4()
            row = {
                "id": cid,
                "post_id": uuid.UUID(str(post_id)),
                "author_type": author_type,
                "author_id": uuid.UUID(str(author_id)),
                "content": content,
                "created_at": self.store.now(),
            }
            self.store.community_comments[cid] = row
            self._rows = [row]
            return

        if compact.startswith("select c.id, c.post_id, c.author_type"):
            pid = uuid.UUID(str(params[0]))
            rows = [
                row for row in self.store.community_comments.values()
                if row["post_id"] == pid
            ]
            rows.sort(key=lambda row: row["created_at"])
            out = []
            for row in rows:
                if row["author_type"] == "user":
                    author = self.store.users.get(row["author_id"])
                    name = author.get("display_name") or author.get("username") if author else None
                else:
                    author = self.store.agents.get(row["author_id"])
                    name = author.get("display_name") or author.get("name") if author else None
                out.append({**row, "author_name": name})
            self._rows = out
            return

        if compact.startswith("select coalesce(display_name, username) as name from users where id = %s"):
            uid = uuid.UUID(str(params[0]))
            user = self.store.users.get(uid)
            self._rows = [{"name": user.get("display_name") or user.get("username")}] if user else []
            return

        if compact.startswith("select coalesce(display_name, name) as name from agents where id = %s"):
            aid = uuid.UUID(str(params[0]))
            agent = self.store.agents.get(aid)
            self._rows = [{"name": agent.get("display_name") or agent.get("name")}] if agent else []
            return

        if compact.startswith("select 1 from post_likes"):
            post_id, user_id = uuid.UUID(str(params[0])), uuid.UUID(str(params[1]))
            self._rows = [{"?column?": 1}] if (post_id, user_id) in self.store.post_likes else []
            return

        if compact.startswith("select post_id from post_likes where post_id = any"):
            post_ids = {uuid.UUID(str(post_id)) for post_id in params[0]}
            user_id = uuid.UUID(str(params[1]))
            self._rows = [
                {"post_id": post_id}
                for post_id, liked_user_id in self.store.post_likes
                if post_id in post_ids and liked_user_id == user_id
            ]
            return

        if compact.startswith("insert into post_likes"):
            post_id, user_id = uuid.UUID(str(params[0])), uuid.UUID(str(params[1]))
            self.store.post_likes.add((post_id, user_id))
            self._rows = []
            return

        if compact.startswith("delete from post_likes where post_id = %s and user_id = %s"):
            post_id, user_id = uuid.UUID(str(params[0])), uuid.UUID(str(params[1]))
            self.store.post_likes.discard((post_id, user_id))
            self._rows = []
            return

        if compact.startswith("select count(*) as count from post_likes where post_id = %s"):
            pid = uuid.UUID(str(params[0]))
            self._rows = [{"count": len([1 for post_id, _ in self.store.post_likes if post_id == pid])}]
            return

        if compact.startswith("update posts set likes = %s where id = %s"):
            likes, pid = int(params[0]), uuid.UUID(str(params[1]))
            self.store.community_posts[pid]["likes"] = likes
            self._rows = []
            return

        # tasks
        if compact.startswith("insert into tasks"):
            (
                owner_id, title, description, category, difficulty,
                required_capabilities, estimated_hours, reward_points,
                deadline, deliverable_type, assigned_agent_id,
            ) = params[:11]
            tid = uuid.uuid4()
            row = {
                "id": tid,
                "owner_id": uuid.UUID(str(owner_id)),
                "title": title,
                "description": description,
                "category": category,
                "difficulty": difficulty,
                "required_capabilities": _plain(required_capabilities),
                "estimated_hours": estimated_hours,
                "reward_points": reward_points,
                "status": "open",
                "assigned_agent_id": uuid.UUID(str(assigned_agent_id)) if assigned_agent_id else None,
                "deadline": deadline,
                "created_at": self.store.now(),
                "updated_at": self.store.now(),
                "completed_at": None,
                "deliverable_type": deliverable_type,
                "verification_required": True,
            }
            self.store.tasks[tid] = row
            self._rows = [{"id": tid}]
            return

        if compact.startswith("select t.id, t.owner_id") and "from tasks t where 1=1" in compact:
            rows = list(self.store.tasks.values())
            idx = 0
            if "t.status = %s" in compact:
                rows = [row for row in rows if row["status"] == params[idx]]
                idx += 1
            if "t.category = %s" in compact:
                rows = [row for row in rows if row["category"] == params[idx]]
            rows.sort(key=lambda row: row["created_at"], reverse=True)
            self._rows = rows
            return

        if compact.startswith("select t.id, t.owner_id") and "from tasks t where t.status = 'open'" in compact:
            rows = [
                row for row in self.store.tasks.values()
                if row["status"] == "open"
            ]
            priority = {"urgent": 0, "normal": 1, "low": 2}
            rows.sort(key=lambda row: (priority.get(row.get("difficulty") or "normal", 1), row["created_at"]))
            self._rows = rows
            return

        if (
            compact.startswith("select id, status, assigned_agent_id")
            and "from tasks where id = %s for update" in compact
        ) or (
            compact.startswith("select id, status, assigned_agent_id, owner_id, title")
            and "from tasks where id = %s for update" in compact
        ):
            tid = uuid.UUID(str(params[0]))
            row = self.store.tasks.get(tid)
            self._rows = [
                {
                    "id": row["id"],
                    "status": row["status"],
                    "assigned_agent_id": row["assigned_agent_id"],
                    "owner_id": row["owner_id"],
                    "title": row["title"],
                }
            ] if row else []
            return

        if compact.startswith("select assigned_agent_id, status from tasks where id = %s"):
            tid = uuid.UUID(str(params[0]))
            row = self.store.tasks.get(tid)
            self._rows = [
                {
                    "assigned_agent_id": row["assigned_agent_id"],
                    "status": row["status"],
                }
            ] if row else []
            return

        if compact.startswith("update tasks set assigned_agent_id = %s, status = 'claimed'"):
            agent_id, tid = uuid.UUID(str(params[0])), uuid.UUID(str(params[1]))
            row = self.store.tasks[tid]
            row["assigned_agent_id"] = agent_id
            row["status"] = "claimed"
            row["updated_at"] = self.store.now()
            self._rows = [row]
            return

        if compact.startswith("update tasks set assigned_agent_id = %s, status = 'in_progress'"):
            agent_id, tid = uuid.UUID(str(params[0])), uuid.UUID(str(params[1]))
            row = self.store.tasks[tid]
            row["assigned_agent_id"] = agent_id
            row["status"] = "in_progress"
            row["updated_at"] = self.store.now()
            self._rows = [row]
            return

        if compact.startswith("update tasks set status = 'in_progress'"):
            tid = uuid.UUID(str(params[0]))
            row = self.store.tasks[tid]
            row["status"] = "in_progress"
            row["updated_at"] = self.store.now()
            self._rows = [row]
            return

        if compact.startswith("update tasks set status = 'submitted'"):
            tid = uuid.UUID(str(params[0]))
            row = self.store.tasks[tid]
            row["status"] = "submitted"
            row["updated_at"] = self.store.now()
            self._rows = [row]
            return

        if compact.startswith("update tasks set status = 'completed'"):
            tid = uuid.UUID(str(params[0]))
            row = self.store.tasks[tid]
            row["status"] = "completed"
            row["completed_at"] = self.store.now()
            row["updated_at"] = self.store.now()
            self._rows = [row]
            return

        if compact.startswith("update tasks set status = 'failed'"):
            tid = uuid.UUID(str(params[0]))
            row = self.store.tasks[tid]
            row["status"] = "failed"
            row["updated_at"] = self.store.now()
            self._rows = [row]
            return

        if "select * from tasks where id = %s" in compact:
            tid = uuid.UUID(str(params[0]))
            self._rows = [self.store.tasks[tid]] if tid in self.store.tasks else []
            return

        if "from task_applications where task_id = %s" in compact:
            self._rows = []
            return

        if "from task_submissions where task_id = %s" in compact:
            tid = uuid.UUID(str(params[0]))
            self._rows = [
                row for row in self.store.task_submissions.values()
                if row["task_id"] == tid
            ]
            return

        if compact.startswith("insert into task_submissions"):
            task_id, agent_id, content, deliverable_url, result_hash, evidence_urls, work_log = params[:7]
            sid = uuid.uuid4()
            row = {
                "id": sid,
                "task_id": uuid.UUID(str(task_id)),
                "agent_id": uuid.UUID(str(agent_id)),
                "content": content,
                "deliverable_url": deliverable_url,
                "result_hash": result_hash,
                "evidence_urls": _plain(evidence_urls),
                "work_log": _plain(work_log),
                "submitted_at": self.store.now(),
            }
            self.store.task_submissions[sid] = row
            self._rows = [{"id": sid}]
            return

        if "from task_ratings" in compact and "select count(*) as count" in compact:
            self._rows = [{"count": 0}]
            return

        # notifications
        if compact.startswith("insert into notifications"):
            user_id, notification_type, title, message, link = params[:5]
            nid = uuid.uuid4()
            row = {
                "id": nid,
                "user_id": uuid.UUID(str(user_id)),
                "type": notification_type,
                "title": title,
                "message": message,
                "link": link,
                "read": False,
                "created_at": self.store.now(),
            }
            self.store.notifications.append(row)
            self._rows = [{"id": nid}]
            return

        # jobs
        if compact.startswith("insert into jobs"):
            from_user_id, title, description, required_skill, input_messages, attachments, status_value = params[:7]
            jid = uuid.uuid4()
            row = {
                "id": jid,
                "from_user_id": uuid.UUID(str(from_user_id)),
                "to_agent_id": None,
                "title": title,
                "description": description,
                "required_skill": required_skill,
                "input_messages": _plain(input_messages),
                "attachments": _plain(attachments),
                "status": status_value,
                "progress": None,
                "created_at": self.store.now(),
                "claimed_at": None,
                "started_at": None,
                "completed_at": None,
            }
            self.store.jobs[jid] = row
            self._rows = [row]
            return

        if "select * from jobs where id = %s for update" in compact:
            jid = uuid.UUID(str(params[0]))
            self._rows = [self.store.jobs[jid]] if jid in self.store.jobs else []
            return

        if "select * from jobs where id = %s" in compact:
            jid = uuid.UUID(str(params[0]))
            self._rows = [self.store.jobs[jid]] if jid in self.store.jobs else []
            return

        if compact.startswith("select * from jobs where 1=1"):
            rows = list(self.store.jobs.values())
            idx = 0
            if "status = %s" in compact:
                rows = [row for row in rows if row["status"] == params[idx]]
                idx += 1
            if "required_skill = %s" in compact:
                skill = params[idx]
                idx += 1
                rows = [row for row in rows if row["required_skill"] == skill]
            if "from_user_id = %s" in compact:
                user_id = uuid.UUID(str(params[idx]))
                idx += 1
                rows = [row for row in rows if row["from_user_id"] == user_id]
            if "to_agent_id = any(%s::uuid[])" in compact:
                agent_ids = {uuid.UUID(str(agent_id)) for agent_id in params[idx]}
                rows = [row for row in rows if row["to_agent_id"] in agent_ids]
            self._rows = rows
            return

        if compact.startswith("select * from jobs where status = 'submitted'"):
            skill_values = set(params[0])
            rows = [
                row for row in self.store.jobs.values()
                if row["status"] == "submitted" and row["required_skill"] in skill_values
            ]
            if "not (id = any(%s::uuid[]))" in compact:
                seen_ids = {uuid.UUID(str(job_id)) for job_id in params[1]}
                rows = [row for row in rows if row["id"] not in seen_ids]
            self._rows = rows
            return

        if compact.startswith("select id from agents where owner_id = %s"):
            owner_id = uuid.UUID(str(params[0]))
            self._rows = [
                {"id": row["id"]}
                for row in self.store.agents.values()
                if row["owner_id"] == owner_id
            ]
            return

        if compact.startswith("update jobs set to_agent_id"):
            agent_id, jid = uuid.UUID(str(params[0])), uuid.UUID(str(params[1]))
            row = self.store.jobs[jid]
            row.update({
                "to_agent_id": agent_id,
                "status": "claimed",
                "claimed_at": self.store.now(),
                "started_at": self.store.now(),
            })
            self._rows = [row]
            return

        if compact.startswith("update jobs set progress"):
            progress, jid = params[0], uuid.UUID(str(params[1]))
            row = self.store.jobs[jid]
            row["progress"] = progress
            row["status"] = "working"
            self._rows = [row]
            return

        if compact.startswith("update jobs set status = 'completed'"):
            jid = uuid.UUID(str(params[0]))
            row = self.store.jobs[jid]
            row["status"] = "completed"
            row["completed_at"] = self.store.now()
            self._rows = [row]
            return

        if compact.startswith("update jobs set status = 'canceled'"):
            jid = uuid.UUID(str(params[0]))
            row = self.store.jobs[jid]
            row["status"] = "canceled"
            self._rows = [row]
            return

        if compact.startswith("insert into job_artifacts"):
            job_id, artifact_type, content, file_url, metadata = params[:5]
            aid = uuid.uuid4()
            row = {
                "id": aid,
                "job_id": uuid.UUID(str(job_id)),
                "type": artifact_type,
                "content": content,
                "file_url": file_url,
                "metadata": _plain(metadata),
                "created_at": self.store.now(),
            }
            self.store.job_artifacts[aid] = row
            self._rows = [row]
            return

        if "select * from job_artifacts where job_id = %s" in compact:
            jid = uuid.UUID(str(params[0]))
            self._rows = [row for row in self.store.job_artifacts.values() if row["job_id"] == jid]
            return

        if "select * from job_artifacts" in compact and "job_id = any(%s::uuid[])" in compact:
            job_ids = {uuid.UUID(str(job_id)) for job_id in params[0]}
            self._rows = [
                row for row in self.store.job_artifacts.values()
                if row["job_id"] in job_ids
            ]
            self._rows.sort(key=lambda row: (row["job_id"], row["created_at"]))
            return

        if compact.startswith("insert into job_ratings"):
            job_id, rater_id, stars, feedback = params[:4]
            rid = uuid.uuid4()
            row = {
                "id": rid,
                "job_id": uuid.UUID(str(job_id)),
                "rater_id": uuid.UUID(str(rater_id)),
                "stars": stars,
                "feedback": feedback,
                "created_at": self.store.now(),
            }
            self.store.job_ratings[rid] = row
            self._rows = [row]
            return

        if "select * from job_ratings where job_id = %s" in compact:
            jid = uuid.UUID(str(params[0]))
            self._rows = [row for row in self.store.job_ratings.values() if row["job_id"] == jid][:1]
            return

        if "select * from job_ratings where job_id = any(%s::uuid[])" in compact:
            job_ids = {uuid.UUID(str(job_id)) for job_id in params[0]}
            self._rows = [
                row for row in self.store.job_ratings.values()
                if row["job_id"] in job_ids
            ]
            return

        if compact.startswith("insert into job_events"):
            job_id, event_type, payload = params[:3]
            self._rows = [self.store.add_event(uuid.UUID(str(job_id)), event_type, _plain(payload))]
            return

        if "select * from job_events where job_id = %s" in compact:
            jid = uuid.UUID(str(params[0]))
            self._rows = [
                row for row in self.store.job_events.values() if row["job_id"] == jid
            ]
            self._rows.sort(key=lambda row: row["created_at"])
            return

        if "select * from job_events" in compact and "job_id = any(%s::uuid[])" in compact:
            job_ids = {uuid.UUID(str(job_id)) for job_id in params[0]}
            self._rows = [
                row for row in self.store.job_events.values()
                if row["job_id"] in job_ids
            ]
            self._rows.sort(key=lambda row: (row["job_id"], row["created_at"]))
            return

        if "pg_notify" in compact:
            channel, payload = params[:2]
            self.store.notifications.append({"channel": channel, "payload": json.loads(payload)})
            self._rows = []
            return

        raise AssertionError(f"Unhandled SQL: {sql} params={params}")


class FakeConnection:
    def __init__(self, store: FakePolisStore):
        self.store = store

    def cursor(self):
        return FakeCursor(self.store)

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


@contextmanager
def fake_connection(store: FakePolisStore):
    yield FakeConnection(store)


@pytest.fixture()
def polis_client(monkeypatch):
    from psycopg2 import pool

    class NoopConnectionPool:
        def __init__(self, *args, **kwargs):
            pass

        def getconn(self):
            return None

        def putconn(self, conn):
            pass

    monkeypatch.setattr(pool, "ThreadedConnectionPool", NoopConnectionPool)

    from app.main import app
    from app.routes import agents as agents_routes
    from app.routes import auth as auth_routes
    from app.routes import community as community_routes
    from app.routes import jobs as jobs_routes
    from app.routes import tasks as tasks_routes
    import app.dependencies as dependencies

    store = FakePolisStore()

    def connection_factory():
        return fake_connection(store)

    monkeypatch.setattr(auth_routes, "get_db_connection", connection_factory)
    monkeypatch.setattr(agents_routes, "get_db_connection", connection_factory)
    monkeypatch.setattr(community_routes, "get_db_connection", connection_factory)
    monkeypatch.setattr(jobs_routes, "get_db_connection", connection_factory)
    monkeypatch.setattr(tasks_routes, "get_db_connection", connection_factory)
    monkeypatch.setattr(dependencies, "get_db_connection", connection_factory)

    def fake_upload(*, data: bytes, filename: str, content_type: str, owner_id: uuid.UUID):
        upload = {
            "bucket": "polis-attachments",
            "filename": filename,
            "content_type": content_type,
            "owner_id": owner_id,
            "data": data,
        }
        store.uploads.append(upload)
        return f"https://storage.example/polis-attachments/{owner_id}/{filename}"

    monkeypatch.setattr(jobs_routes.storage, "upload_bytes", fake_upload)

    client = TestClient(app)
    client.store = store
    return client


def test_agent_registration_does_not_require_manual_skills_or_capabilities(polis_client):
    user_response = polis_client.post(
        "/api/v1/auth/register",
        json={
            "email": "noskills@example.com",
            "password": "secret123",
            "username": "noskills",
        },
    )
    assert user_response.status_code == 200
    token = user_response.json()["token"]

    create_response = polis_client.post(
        "/api/v1/agents",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "generalist",
            "display_name": "Generalist",
            "description": "Reads task descriptions and decides whether to act.",
            "endpoint_url": "https://agent.example/a2a",
            "auth_method": "none",
        },
    )

    assert create_response.status_code == 200
    body = create_response.json()
    assert body["agent_card"]["name"] == "generalist"
    assert body["agent_card"]["description"] == "Reads task descriptions and decides whether to act."
    assert body["agent_card"]["url"] == "https://agent.example/a2a"
    assert "capabilities" not in body["agent_card"]
    assert body["skills"] == []


def test_task_mvp_lifecycle_with_pending_claim_complete_and_fail(polis_client):
    owner_response = polis_client.post(
        "/api/v1/auth/register",
        json={
            "email": "task-owner@example.com",
            "password": "secret123",
            "username": "taskowner",
        },
    )
    assert owner_response.status_code == 200
    owner_token = owner_response.json()["token"]

    agent_response = polis_client.post(
        "/api/v1/agents",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={
            "name": "task-runner",
            "display_name": "Task Runner",
            "description": "Handles general tasks from descriptions.",
            "auth_method": "none",
        },
    )
    assert agent_response.status_code == 200
    agent = agent_response.json()
    agent_token = agent["token"]

    create_response = polis_client.post(
        "/api/v1/tasks",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={
            "title": "Summarize a short brief",
            "description": "Read the brief and return three bullets.",
            "assigned_agent_id": agent["id"],
            "budget": 12,
            "priority": "urgent",
            "deadline": "2026-07-01T09:30:00Z",
        },
    )
    assert create_response.status_code == 200
    task_id = create_response.json()["task_id"]
    created_task = polis_client.store.tasks[uuid.UUID(task_id)]
    assert created_task["assigned_agent_id"] is None
    assert created_task["reward_points"] == 12
    assert created_task["difficulty"] == "urgent"

    pending_response = polis_client.get(
        "/api/v1/tasks/pending",
        headers={"Authorization": f"Bearer {agent_token}"},
    )
    assert pending_response.status_code == 200
    pending = pending_response.json()
    assert [task["id"] for task in pending] == [task_id]
    assert pending[0]["status"] == "open"
    assert pending[0]["assigned_agent_id"] is None
    assert pending[0]["reward_points"] == 12
    assert pending[0]["difficulty"] == "urgent"

    claim_response = polis_client.post(
        f"/api/v1/tasks/{task_id}/claim",
        headers={"Authorization": f"Bearer {agent_token}"},
    )
    assert claim_response.status_code == 200
    assert claim_response.json()["status"] == "claimed"
    assert claim_response.json()["assigned_agent_id"] == agent["id"]

    start_response = polis_client.post(
        f"/api/v1/tasks/{task_id}/start",
        headers={"Authorization": f"Bearer {agent_token}"},
    )
    assert start_response.status_code == 200
    assert start_response.json()["status"] == "in_progress"

    submit_response = polis_client.post(
        f"/api/v1/tasks/{task_id}/submit",
        headers={"Authorization": f"Bearer {agent_token}"},
        json={"content": "one\ntwo\nthree"},
    )
    assert submit_response.status_code == 200
    assert polis_client.store.tasks[uuid.UUID(task_id)]["status"] == "submitted"

    accept_response = polis_client.post(
        f"/api/v1/tasks/{task_id}/accept",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert accept_response.status_code == 200
    assert accept_response.json()["status"] == "completed"

    failed_task = polis_client.post(
        "/api/v1/tasks",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={
            "title": "Impossible task",
            "description": "Try a task that will fail.",
        },
    ).json()
    fail_claim = polis_client.post(
        f"/api/v1/tasks/{failed_task['task_id']}/claim",
        headers={"Authorization": f"Bearer {agent_token}"},
    )
    assert fail_claim.status_code == 200
    fail_start = polis_client.post(
        f"/api/v1/tasks/{failed_task['task_id']}/start",
        headers={"Authorization": f"Bearer {agent_token}"},
    )
    assert fail_start.status_code == 200

    fail_response = polis_client.post(
        f"/api/v1/tasks/{failed_task['task_id']}/fail",
        headers={"Authorization": f"Bearer {agent_token}"},
        json={"error": "Input was missing."},
    )
    assert fail_response.status_code == 200
    assert fail_response.json()["status"] == "failed"


def test_community_posts_comments_likes_and_agent_task_share(polis_client):
    owner_response = polis_client.post(
        "/api/v1/auth/register",
        json={
            "email": "community-owner@example.com",
            "password": "secret123",
            "username": "communityowner",
            "display_name": "Community Owner",
        },
    )
    assert owner_response.status_code == 200
    owner_token = owner_response.json()["token"]

    agent_response = polis_client.post(
        "/api/v1/agents",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={
            "name": "community-agent",
            "display_name": "Community Agent",
            "description": "Shares useful task notes.",
            "auth_method": "none",
        },
    )
    assert agent_response.status_code == 200
    agent = agent_response.json()
    agent_token = agent["token"]

    post_response = polis_client.post(
        "/api/v1/community/posts",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={
            "title": "How should agents describe their work?",
            "content": "Looking for examples from agents that completed real tasks.",
            "category": "tech",
        },
    )
    assert post_response.status_code == 200
    post_id = post_response.json()["post_id"]

    list_response = polis_client.get("/api/v1/community/posts", params={"category": "tech"})
    assert list_response.status_code == 200
    posts = list_response.json()["posts"]
    assert [post["id"] for post in posts] == [post_id]
    assert posts[0]["author_type"] == "user"
    assert posts[0]["author_name"] == "Community Owner"
    assert posts[0]["category"] == "tech"
    assert posts[0]["likes"] == 0

    comment_response = polis_client.post(
        f"/api/v1/community/posts/{post_id}/comments",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"content": "A short result summary and a failure note both help."},
    )
    assert comment_response.status_code == 200

    comments_response = polis_client.get(f"/api/v1/community/posts/{post_id}/comments")
    assert comments_response.status_code == 200
    assert comments_response.json()["comments"][0]["content"] == "A short result summary and a failure note both help."

    first_like = polis_client.post(
        f"/api/v1/community/posts/{post_id}/like",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    second_like = polis_client.post(
        f"/api/v1/community/posts/{post_id}/like",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert first_like.status_code == 200
    assert second_like.status_code == 200
    assert first_like.json()["likes"] == 1
    assert second_like.json()["likes"] == 1

    unlike = polis_client.delete(
        f"/api/v1/community/posts/{post_id}/like",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    unlike_again = polis_client.delete(
        f"/api/v1/community/posts/{post_id}/like",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert unlike.status_code == 200
    assert unlike.json() == {"liked": False, "likes": 0}
    assert unlike_again.status_code == 200
    assert unlike_again.json() == {"liked": False, "likes": 0}

    share_response = polis_client.post(
        "/api/v1/community/agent/task-share",
        headers={"Authorization": f"Bearer {agent_token}"},
        json={
            "task_title": "Summarize API notes",
            "summary": "Finished a concise API summary with three implementation risks.",
            "category": "showcase",
        },
    )
    assert share_response.status_code == 200
    showcase_response = polis_client.get("/api/v1/community/posts", params={"category": "showcase"})
    assert showcase_response.status_code == 200
    showcase = showcase_response.json()["posts"][0]
    assert showcase["author_type"] == "agent"
    assert showcase["author_id"] == agent["id"]
    assert showcase["title"] == "完成任务：Summarize API notes"


def test_polis_v1_happy_path_and_concurrency_guard(polis_client):
    user_response = polis_client.post(
        "/api/v1/auth/register",
        json={
            "email": "alice@example.com",
            "password": "secret123",
            "username": "alice",
            "display_name": "Alice",
        },
    )
    assert user_response.status_code == 200
    user_token = user_response.json()["token"]

    agent_card = {
        "name": "alice-translator",
        "description": "Chinese-English translation agent",
        "url": "https://agent.example/a2a",
        "version": "1.0.0",
        "capabilities": {"streaming": True},
        "skills": [
            {
                "id": "translate-zh-en",
                "name": "Translate zh to en",
                "description": "Translate Chinese text into English",
                "examples": [{"input": "你好", "output": "Hello"}],
                "inputSchema": {"type": "object"},
                "outputSchema": {"type": "object"},
            }
        ],
    }
    agent_response = polis_client.post(
        "/api/v1/agents",
        headers={"Authorization": f"Bearer {user_token}"},
        json={
            "name": "alice-translator",
            "display_name": "Alice Translator",
            "description": "Chinese-English translation agent",
            "endpoint_url": "https://agent.example/a2a",
            "auth_method": "bearer",
            "auth_config": {"token": "agent-secret"},
            "agent_card": agent_card,
        },
    )
    assert agent_response.status_code == 200
    agent_token = agent_response.json()["token"]

    payload = base64.b64encode(b"source text").decode("ascii")
    job_response = polis_client.post(
        "/api/v1/jobs",
        headers={"Authorization": f"Bearer {user_token}"},
        json={
            "title": "Translate product copy",
            "description": "Translate this launch copy into English.",
            "required_skill": "translate-zh-en",
            "input_messages": [
                {
                    "role": "user",
                    "parts": [{"kind": "text", "text": "你好，世界"}],
                }
            ],
            "attachments": [
                {
                    "filename": "source.txt",
                    "mime": "text/plain",
                    "content_base64": payload,
                }
            ],
        },
    )
    assert job_response.status_code == 200
    job = job_response.json()
    job_id = job["id"]
    assert job["status"] == "submitted"
    assert job["attachments"][0]["url"].startswith("https://storage.example/polis-attachments/")
    assert polis_client.store.uploads[0]["bucket"] == "polis-attachments"
    assert polis_client.store.notifications[0]["channel"] == "polis_jobs"

    claim_response = polis_client.post(
        f"/api/v1/jobs/{job_id}/claim",
        headers={"Authorization": f"Bearer {agent_token}"},
    )
    assert claim_response.status_code == 200
    assert claim_response.json()["status"] == "claimed"
    assert any("for update" in query for query in polis_client.store.queries)

    second_claim = polis_client.post(
        f"/api/v1/jobs/{job_id}/claim",
        headers={"Authorization": f"Bearer {agent_token}"},
    )
    assert second_claim.status_code == 409

    progress_response = polis_client.post(
        f"/api/v1/jobs/{job_id}/progress",
        headers={"Authorization": f"Bearer {agent_token}"},
        json={"progress": "Halfway through translation"},
    )
    assert progress_response.status_code == 200
    assert progress_response.json()["status"] == "working"

    artifact_response = polis_client.post(
        f"/api/v1/jobs/{job_id}/artifacts",
        headers={"Authorization": f"Bearer {agent_token}"},
        json={"type": "text", "content": "Hello, world", "metadata": {"lang": "en"}},
    )
    assert artifact_response.status_code == 200
    assert artifact_response.json()["status"] == "completed"

    rating_response = polis_client.post(
        f"/api/v1/jobs/{job_id}/rate",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"stars": 5, "feedback": "Clean delivery"},
    )
    assert rating_response.status_code == 200

    detail_response = polis_client.get(
        f"/api/v1/jobs/{job_id}",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["status"] == "completed"
    assert detail["artifacts"][0]["content"] == "Hello, world"
    assert detail["rating"]["stars"] == 5
    assert [event["event_type"] for event in detail["events"]] == [
        "created",
        "claimed",
        "progress",
        "delivered",
        "rated",
    ]


def test_agent_card_discovery_is_a2a_compatible(polis_client):
    response = polis_client.get("/.well-known/agent.json")
    assert response.status_code == 200
    card = response.json()
    assert card["name"] == "Polis"
    assert card["url"].endswith("/api/v1")
    assert card["capabilities"]["streaming"] is True
    assert any(skill["id"] == "polis.jobs.create" for skill in card["skills"])


def test_agent_responses_include_normalized_skills(polis_client):
    user_response = polis_client.post(
        "/api/v1/auth/register",
        json={
            "email": "agent-owner@example.com",
            "password": "secret123",
            "username": "agentowner",
        },
    )
    token = user_response.json()["token"]

    create_response = polis_client.post(
        "/api/v1/agents",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "worker",
            "display_name": "Worker",
            "description": "Does useful work",
            "auth_method": "none",
            "agent_card": {"version": "1.0", "skills": ["python"]},
            "skills": ["translation"],
        },
    )
    assert create_response.status_code == 200
    assert {skill["skill_id"] for skill in create_response.json()["skills"]} == {
        "python",
        "translation",
    }

    list_response = polis_client.get(
        "/api/v1/agents",
        headers={"Authorization": f"Bearer {token}"},
        params={"mine": "true"},
    )
    assert list_response.status_code == 200
    assert {skill["skill_id"] for skill in list_response.json()[0]["skills"]} == {
        "python",
        "translation",
    }


def test_job_events_require_authorized_query_token_for_eventsource(polis_client):
    user_response = polis_client.post(
        "/api/v1/auth/register",
        json={
            "email": "events@example.com",
            "password": "secret123",
            "username": "events",
        },
    )
    token = user_response.json()["token"]
    job_response = polis_client.post(
        "/api/v1/jobs",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "Private event stream",
            "description": "Only the owner can read events.",
            "required_skill": "privacy",
            "input_messages": [],
            "attachments": [],
        },
    )
    job_id = job_response.json()["id"]

    unauth_response = polis_client.get(f"/api/v1/jobs/{job_id}/events?once=true")
    assert unauth_response.status_code == 401

    auth_response = polis_client.get(
        f"/api/v1/jobs/{job_id}/events",
        params={"once": "true", "token": token},
    )
    assert auth_response.status_code == 200
    assert "event: created" in auth_response.text


def test_job_mine_filters_dashboard_sent_and_received(polis_client):
    alice_response = polis_client.post(
        "/api/v1/auth/register",
        json={
            "email": "alice-dashboard@example.com",
            "password": "secret123",
            "username": "alicedash",
        },
    )
    bob_response = polis_client.post(
        "/api/v1/auth/register",
        json={
            "email": "bob-dashboard@example.com",
            "password": "secret123",
            "username": "bobdash",
        },
    )
    alice_token = alice_response.json()["token"]
    bob_token = bob_response.json()["token"]

    agent_response = polis_client.post(
        "/api/v1/agents",
        headers={"Authorization": f"Bearer {bob_token}"},
        json={
            "name": "bob-worker",
            "display_name": "Bob Worker",
            "description": "Claims dashboard jobs",
            "auth_method": "none",
            "agent_card": {"version": "1.0", "skills": ["python"]},
            "skills": ["python"],
        },
    )
    bob_agent_id = agent_response.json()["id"]

    alice_job = polis_client.post(
        "/api/v1/jobs",
        headers={"Authorization": f"Bearer {alice_token}"},
        json={
            "title": "Alice job",
            "description": "Sent by Alice",
            "required_skill": "python",
            "input_messages": [],
            "attachments": [],
        },
    ).json()
    bob_job = polis_client.post(
        "/api/v1/jobs",
        headers={"Authorization": f"Bearer {bob_token}"},
        json={
            "title": "Bob job",
            "description": "Sent by Bob",
            "required_skill": "python",
            "input_messages": [],
            "attachments": [],
        },
    ).json()

    claim_response = polis_client.post(
        f"/api/v1/jobs/{alice_job['id']}/claim",
        headers={"Authorization": f"Bearer {bob_token}"},
        json={"agent_id": bob_agent_id},
    )
    assert claim_response.status_code == 200

    sent = polis_client.get(
        "/api/v1/jobs",
        headers={"Authorization": f"Bearer {alice_token}"},
        params={"mine": "sent"},
    ).json()
    received = polis_client.get(
        "/api/v1/jobs",
        headers={"Authorization": f"Bearer {bob_token}"},
        params={"mine": "received"},
    ).json()

    assert [job["id"] for job in sent] == [alice_job["id"]]
    assert [job["id"] for job in received] == [alice_job["id"]]
    assert bob_job["id"] not in {job["id"] for job in sent + received}


def test_agent_inbox_queries_cast_postgres_array_params(polis_client):
    from app.routes.jobs import _build_inbox_generator

    agent_id = uuid.uuid4()
    polis_client.store.agents[agent_id] = {
        "id": agent_id, "owner_id": uuid.uuid4(), "name": "stub",
        "status": "online", "skills": ["python"],
    }
    generator = _build_inbox_generator(
        agent_id,
        ["python"],
        {"python"},
        once=True,
    )

    with pytest.raises(StopAsyncIteration):
        generator().__anext__().send(None)

    assert any("required_skill = any(%s::text[])" in query for query in polis_client.store.queries)
    assert not any("required_skill = any(%s)" in query for query in polis_client.store.queries)


def test_agent_inbox_live_query_casts_seen_uuid_array(polis_client):
    from app.routes.jobs import _build_inbox_generator

    owner_id = uuid.uuid4()
    agent_id = uuid.uuid4()
    polis_client.store.agents[agent_id] = {
        "id": agent_id, "owner_id": owner_id, "name": "stub",
        "status": "online", "skills": ["python"],
    }

    def add_submitted_job(title: str) -> uuid.UUID:
        job_id = uuid.uuid4()
        polis_client.store.jobs[job_id] = {
            "id": job_id,
            "from_user_id": owner_id,
            "to_agent_id": None,
            "title": title,
            "description": title,
            "required_skill": "python",
            "input_messages": [],
            "attachments": [],
            "status": "submitted",
            "progress": None,
            "created_at": polis_client.store.now(),
            "claimed_at": None,
            "started_at": None,
            "completed_at": None,
        }
        return job_id

    add_submitted_job("first")
    generator = _build_inbox_generator(
        agent_id,
        ["python"],
        {"python"},
        once=False,
    )()

    first_event = asyncio.run(generator.__anext__())
    assert "first" in first_event

    add_submitted_job("second")
    second_event = asyncio.run(generator.__anext__())

    assert "second" in second_event
    assert any("not (id = any(%s::uuid[]))" in query for query in polis_client.store.queries)


def test_polis_v1_alembic_migration_declares_exact_schema_contract():
    versions_dir = Path(__file__).resolve().parents[1] / "migrations" / "versions"
    version_files = list(versions_dir.glob("*polis_v1*.py"))
    assert version_files, "Expected an Alembic version file for Polis v1"

    source = "\n".join(path.read_text() for path in version_files)
    expected_tables = [
        "users",
        "agents",
        "agent_skills",
        "jobs",
        "job_artifacts",
        "job_ratings",
        "job_events",
    ]
    for table_name in expected_tables:
        assert f'"{table_name}"' in source or f"'{table_name}'" in source

    assert "task_%" in source
    assert "agent_follows" in source
    assert "feed_%" in source
    assert "polis-attachments" in source
