from __future__ import annotations

from contextlib import contextmanager
import asyncio
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


class DeliverableCursor:
    def __init__(self, store: dict):
        self.store = store
        self._rows: list[dict] = []

    def execute(self, sql: str, params=None):
        compact = " ".join(sql.lower().split())
        params = list(params or [])

        if compact.startswith("select id, owner_id, assigned_agent_id, status from tasks where id = %s"):
            task = self.store["tasks"].get(params[0]) or self.store["tasks"].get(__import__("uuid").UUID(str(params[0])))
            self._rows = [task] if task else []
            return
        if compact.startswith("insert into task_deliverables"):
            did = uuid4()
            row = {
                "id": did,
                "task_id": __import__("uuid").UUID(str(params[0])),
                "uploaded_by": __import__("uuid").UUID(str(params[1])),
                "file_name": params[2],
                "file_url": params[3],
                "file_size": params[4],
                "description": params[5],
                "created_at": datetime.now(),
            }
            self.store["deliverables"][did] = row
            self._rows = [row]
            return
        if "from task_deliverables" in compact and "where task_id = %s order by" in compact:
            task_id = __import__("uuid").UUID(str(params[0]))
            self._rows = [
                row for row in self.store["deliverables"].values()
                if row["task_id"] == task_id
            ]
            return
        if compact.startswith("select * from task_deliverables where id = %s and task_id = %s"):
            did = __import__("uuid").UUID(str(params[0]))
            task_id = __import__("uuid").UUID(str(params[1]))
            row = self.store["deliverables"].get(did)
            self._rows = [row] if row and row["task_id"] == task_id else []
            return
        if compact.startswith("delete from task_deliverables"):
            did = __import__("uuid").UUID(str(params[0]))
            task_id = __import__("uuid").UUID(str(params[1]))
            row = self.store["deliverables"].pop(did, None)
            self._rows = [row] if row and row["task_id"] == task_id else []
            return
        self._rows = []

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return self._rows


class DeliverableConnection:
    def __init__(self, store: dict):
        self.store = store

    def cursor(self):
        return DeliverableCursor(self.store)


class FakeUpload:
    filename = "result.md"
    content_type = "text/markdown"

    async def read(self):
        return b"# result"


def import_deliverables(monkeypatch, store: dict):
    fake_database = types.ModuleType("app.database")

    @contextmanager
    def fake_db():
        yield DeliverableConnection(store)

    fake_database.get_db_connection = fake_db
    monkeypatch.setitem(sys.modules, "app.database", fake_database)
    sys.modules.pop("app.routes.task_deliverables", None)
    module = importlib.import_module("app.routes.task_deliverables")
    monkeypatch.setattr(module.storage, "upload_bytes", lambda **kwargs: f"https://files.example/{kwargs['filename']}")
    return module


def test_assigned_agent_uploads_and_lists_deliverables(monkeypatch):
    owner_id = uuid4()
    agent_id = uuid4()
    task_id = uuid4()
    store = {
        "tasks": {
            task_id: {
                "id": task_id,
                "owner_id": owner_id,
                "assigned_agent_id": agent_id,
                "status": "in_progress",
            }
        },
        "deliverables": {},
    }
    routes = import_deliverables(monkeypatch, store)

    created = asyncio.run(
        routes.upload_deliverable(task_id, FakeUpload(), "first file", current_user=(agent_id, "agent"))
    )

    assert created.file_name == "result.md"
    assert created.file_url == "https://files.example/result.md"
    assert created.file_size == 8

    listed = routes.list_deliverables(task_id, current_user=(owner_id, "user"))
    assert [item.id for item in listed] == [created.id]


def test_unassigned_agent_cannot_upload(monkeypatch):
    owner_id = uuid4()
    agent_id = uuid4()
    task_id = uuid4()
    store = {
        "tasks": {
            task_id: {
                "id": task_id,
                "owner_id": owner_id,
                "assigned_agent_id": agent_id,
                "status": "in_progress",
            }
        },
        "deliverables": {},
    }
    routes = import_deliverables(monkeypatch, store)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(routes.upload_deliverable(task_id, FakeUpload(), None, current_user=(uuid4(), "agent")))
    assert exc.value.status_code == 403


def test_owner_can_delete_deliverable(monkeypatch):
    owner_id = uuid4()
    agent_id = uuid4()
    task_id = uuid4()
    deliverable_id = uuid4()
    store = {
        "tasks": {
            task_id: {
                "id": task_id,
                "owner_id": owner_id,
                "assigned_agent_id": agent_id,
                "status": "submitted",
            }
        },
        "deliverables": {
            deliverable_id: {
                "id": deliverable_id,
                "task_id": task_id,
                "uploaded_by": agent_id,
                "file_name": "result.zip",
                "file_url": "https://files.example/result.zip",
                "file_size": 123,
                "description": None,
                "created_at": datetime.now(),
            }
        },
    }
    routes = import_deliverables(monkeypatch, store)

    result = routes.delete_deliverable(task_id, deliverable_id, current_user=(owner_id, "user"))

    assert result == {"deleted": True}
    assert deliverable_id not in store["deliverables"]
