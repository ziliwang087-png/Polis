from __future__ import annotations

from contextlib import contextmanager
import importlib
import os
import sys
import types
from datetime import datetime
from uuid import uuid4

import pytest
from fastapi import HTTPException

os.environ.setdefault("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/postgres")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")


class StatusCursor:
    def __init__(self, task: dict):
        self.task = task
        self._rows: list[dict] = []

    def execute(self, sql: str, params=None):
        compact = " ".join(sql.lower().split())
        params = list(params or [])

        if compact.startswith("select id, status, assigned_agent_id"):
            self._rows = [self.task]
            return
        if compact.startswith("select assigned_agent_id, status"):
            self._rows = [self.task]
            return
        if compact.startswith("select owner_id, status, assigned_agent_id"):
            self._rows = [self.task]
            return
        if compact.startswith("select owner_id, assigned_agent_id"):
            self._rows = [self.task]
            return

        if "set assigned_agent_id = %s, status = 'claimed'" in compact:
            self.task["assigned_agent_id"] = params[0]
            self.task["status"] = "claimed"
            self.task["updated_at"] = datetime.now()
            self._rows = [self.task]
            return
        if "set status = 'in_progress'" in compact:
            self.task["status"] = "in_progress"
            self.task["updated_at"] = datetime.now()
            self._rows = [self.task]
            return
        if "set status = 'submitted'" in compact:
            self.task["status"] = "submitted"
            self.task["updated_at"] = datetime.now()
            self._rows = [self.task]
            return
        if "set status = 'completed'" in compact:
            self.task["status"] = "completed"
            self.task["updated_at"] = datetime.now()
            self.task["completed_at"] = datetime.now()
            self._rows = [self.task]
            return
        if "set status = 'cancelled'" in compact:
            self.task["status"] = "cancelled"
            self.task["updated_at"] = datetime.now()
            self._rows = [self.task]
            return
        if "insert into task_submissions" in compact:
            self._rows = [{"id": uuid4()}]
            return
        self._rows = []

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return self._rows


class StatusConnection:
    def __init__(self, task: dict):
        self.task = task

    def cursor(self):
        return StatusCursor(self.task)


def import_tasks(monkeypatch, task: dict):
    fake_database = types.ModuleType("app.database")

    @contextmanager
    def fake_db():
        yield StatusConnection(task)

    fake_database.get_db_connection = fake_db
    fake_database.get_db = lambda: iter([StatusConnection(task)])
    monkeypatch.setitem(sys.modules, "app.database", fake_database)
    sys.modules.pop("app.routes.tasks", None)
    module = importlib.import_module("app.routes.tasks")
    monkeypatch.setattr(module, "create_notification", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "_check_and_award_badges", lambda *args, **kwargs: None)
    return module


def make_task(owner_id, agent_id=None, status="open"):
    return {
        "id": uuid4(),
        "owner_id": owner_id,
        "assigned_agent_id": agent_id,
        "status": status,
        "title": "Status flow task",
        "updated_at": None,
        "completed_at": None,
    }


def test_agent_advances_open_to_submitted_but_not_completed(monkeypatch):
    owner_id = uuid4()
    agent_id = uuid4()
    task = make_task(owner_id)
    routes = import_tasks(monkeypatch, task)

    claimed = routes.claim_task(task["id"], agent_id=agent_id)
    assert claimed.status == "claimed"
    assert claimed.assigned_agent_id == agent_id

    started = routes.start_task(task["id"], agent_id=agent_id)
    assert started.status == "in_progress"

    submitted = routes.submit_task(task["id"], routes.TaskSubmitRequest(content="done"), agent_id=agent_id)
    assert submitted.submission_id
    assert task["status"] == "submitted"

    with pytest.raises(HTTPException) as exc:
        routes.complete_task(task["id"], routes.TaskCompleteRequest(result={}), agent_id=agent_id)
    assert exc.value.status_code == 403


def test_owner_accepts_revises_or_cancels_submitted_task(monkeypatch):
    owner_id = uuid4()
    agent_id = uuid4()
    task = make_task(owner_id, agent_id, status="submitted")
    routes = import_tasks(monkeypatch, task)

    revised = routes.request_revision_task(task["id"], owner_id=owner_id)
    assert revised.status == "in_progress"

    task["status"] = "submitted"
    accepted = routes.accept_task(task["id"], owner_id=owner_id)
    assert accepted.status == "completed"

    task["status"] = "open"
    cancelled = routes.cancel_task(task["id"], owner_id=owner_id)
    assert cancelled.status == "cancelled"


def test_non_owner_cannot_cancel_task(monkeypatch):
    owner_id = uuid4()
    task = make_task(owner_id, status="open")
    routes = import_tasks(monkeypatch, task)

    with pytest.raises(HTTPException) as exc:
        routes.cancel_task(task["id"], owner_id=uuid4())
    assert exc.value.status_code == 403
