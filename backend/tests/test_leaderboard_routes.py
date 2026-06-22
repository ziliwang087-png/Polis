from __future__ import annotations

from contextlib import contextmanager
import importlib
import os
import sys
import types
from uuid import uuid4

os.environ.setdefault("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/postgres")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")


def import_leaderboard(monkeypatch):
    fake_database = types.ModuleType("app.database")
    fake_database.get_db_connection = lambda: None
    monkeypatch.setitem(sys.modules, "app.database", fake_database)
    sys.modules.pop("app.routes.leaderboard", None)
    return importlib.import_module("app.routes.leaderboard")


class LeaderboardCursor:
    def __init__(self, rows_by_query: dict[str, list[dict]]):
        self.rows_by_query = rows_by_query
        self.last_sql = ""
        self._rows: list[dict] = []

    def execute(self, sql: str, params=None):
        self.last_sql = " ".join(sql.lower().split())
        if "from users" in self.last_sql and "published_tasks" in self.last_sql:
            self._rows = self.rows_by_query["tasks"]
        elif "from agents" in self.last_sql and "total_tasks_completed" in self.last_sql:
            self._rows = self.rows_by_query["agents"]
        elif "from agents" in self.last_sql and "coalesce(a.xp" in self.last_sql:
            self._rows = self.rows_by_query["xp"]
        else:
            self._rows = []

    def fetchall(self):
        return self._rows


class LeaderboardConnection:
    def __init__(self, rows_by_query: dict[str, list[dict]]):
        self.rows_by_query = rows_by_query

    def cursor(self):
        return LeaderboardCursor(self.rows_by_query)


def test_xp_leaderboard_returns_ranked_rows_and_current_user(monkeypatch):
    leaderboard = import_leaderboard(monkeypatch)

    current_owner_id = uuid4()
    current_agent_id = uuid4()
    rows = [
        {
            "rank": 1,
            "id": uuid4(),
            "owner_id": uuid4(),
            "name": "top-agent",
            "display_name": "Top Agent",
            "metric_value": 900,
            "level": 9,
            "badge_count": 3,
        },
        {
            "rank": 2,
            "id": current_agent_id,
            "owner_id": current_owner_id,
            "name": "mine",
            "display_name": "Mine",
            "metric_value": 300,
            "level": 4,
            "badge_count": 1,
        },
    ]

    @contextmanager
    def fake_db():
        yield LeaderboardConnection({"xp": rows, "agents": [], "tasks": []})

    monkeypatch.setattr(leaderboard, "get_db_connection", fake_db)

    result = leaderboard.get_xp_leaderboard(limit=50, current_user=(current_owner_id, "user"))

    assert result["type"] == "xp"
    assert result["leaders"][0]["rank"] == 1
    assert result["leaders"][0]["metric_value"] == 900
    assert result["current_user"]["id"] == current_agent_id
    assert result["current_user"]["rank"] == 2


def test_agents_and_tasks_leaderboards_have_required_metrics(monkeypatch):
    leaderboard = import_leaderboard(monkeypatch)

    owner_id = uuid4()
    agent_id = uuid4()
    agent_rows = [
        {
            "rank": 1,
            "id": agent_id,
            "owner_id": owner_id,
            "name": "worker",
            "display_name": "Worker",
            "metric_value": 12,
            "level": 5,
            "badge_count": 2,
        }
    ]
    task_rows = [
        {
            "rank": 1,
            "id": owner_id,
            "owner_id": owner_id,
            "name": "owner",
            "display_name": "Owner",
            "metric_value": 7,
            "level": None,
            "badge_count": 0,
        }
    ]

    @contextmanager
    def fake_db():
        yield LeaderboardConnection({"xp": [], "agents": agent_rows, "tasks": task_rows})

    monkeypatch.setattr(leaderboard, "get_db_connection", fake_db)

    agents = leaderboard.get_agent_leaderboard(limit=50, current_user=(owner_id, "user"))
    tasks = leaderboard.get_task_publisher_leaderboard(limit=50, current_user=(owner_id, "user"))

    assert agents["type"] == "agents"
    assert agents["leaders"][0]["metric_label"] == "完成任务"
    assert agents["current_user"]["id"] == agent_id
    assert tasks["type"] == "tasks"
    assert tasks["leaders"][0]["metric_label"] == "发布任务"
    assert tasks["current_user"]["id"] == owner_id
