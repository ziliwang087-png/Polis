from __future__ import annotations

from contextlib import contextmanager
import importlib
import os
import sys
import types
from datetime import datetime
from uuid import uuid4

os.environ.setdefault("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/postgres")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")


class MessagesCursor:
    def __init__(self, store: dict):
        self.store = store
        self._rows: list[dict] = []

    def execute(self, sql: str, params=None):
        compact = " ".join(sql.lower().split())
        params = list(params or [])

        if compact.startswith("select id from users where id = %s"):
            user_id = __import__("uuid").UUID(str(params[0]))
            self._rows = [{"id": user_id}] if user_id in self.store["users"] else []
            return
        if compact.startswith("select owner_id from agents where id = %s"):
            agent_id = __import__("uuid").UUID(str(params[0]))
            owner_id = self.store["agents"].get(agent_id)
            self._rows = [{"owner_id": owner_id}] if owner_id else []
            return
        if compact.startswith("insert into messages"):
            message_id = uuid4()
            row = {
                "id": message_id,
                "sender_id": __import__("uuid").UUID(str(params[0])),
                "receiver_id": __import__("uuid").UUID(str(params[1])),
                "content": params[2],
                "read": False,
                "created_at": datetime.now(),
            }
            self.store["messages"][message_id] = row
            self._rows = [row]
            return
        if "from messages m" in compact and "conversation_user_id" in compact:
            me = __import__("uuid").UUID(str(params[0]))
            rows = []
            by_other = {}
            for row in self.store["messages"].values():
                if row["sender_id"] != me and row["receiver_id"] != me:
                    continue
                other_id = row["receiver_id"] if row["sender_id"] == me else row["sender_id"]
                current = by_other.get(other_id)
                if not current or row["created_at"] > current["created_at"]:
                    by_other[other_id] = row
            for other_id, row in by_other.items():
                rows.append({
                    "conversation_user_id": other_id,
                    "conversation_user_name": self.store["users"].get(other_id, "Unknown"),
                    "last_message": row["content"],
                    "last_message_at": row["created_at"],
                    "unread_count": sum(
                        1 for msg in self.store["messages"].values()
                        if msg["sender_id"] == other_id and msg["receiver_id"] == me and not msg["read"]
                    ),
                })
            rows.sort(key=lambda item: item["last_message_at"], reverse=True)
            self._rows = rows
            return
        if compact.startswith("select count(*) as count from messages"):
            me = __import__("uuid").UUID(str(params[0]))
            self._rows = [{
                "count": sum(1 for msg in self.store["messages"].values() if msg["receiver_id"] == me and not msg["read"])
            }]
            return
        if "select m.id, m.sender_id" in compact and "from messages m" in compact:
            me = __import__("uuid").UUID(str(params[0]))
            other = __import__("uuid").UUID(str(params[1]))
            rows = [
                row for row in self.store["messages"].values()
                if {row["sender_id"], row["receiver_id"]} == {me, other}
            ]
            rows.sort(key=lambda row: row["created_at"])
            self._rows = rows
            return
        if compact.startswith("update messages set read = true"):
            message_id = __import__("uuid").UUID(str(params[0]))
            receiver_id = __import__("uuid").UUID(str(params[1]))
            row = self.store["messages"].get(message_id)
            if row and row["receiver_id"] == receiver_id:
                row["read"] = True
                self._rows = [row]
            else:
                self._rows = []
            return
        self._rows = []

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return self._rows


class MessagesConnection:
    def __init__(self, store: dict):
        self.store = store

    def cursor(self):
        return MessagesCursor(self.store)


def import_messages(monkeypatch, store: dict):
    fake_database = types.ModuleType("app.database")

    @contextmanager
    def fake_db():
        yield MessagesConnection(store)

    fake_database.get_db_connection = fake_db
    monkeypatch.setitem(sys.modules, "app.database", fake_database)
    sys.modules.pop("app.routes.messages", None)
    return importlib.import_module("app.routes.messages")


def test_send_and_list_conversations(monkeypatch):
    alice = uuid4()
    bob = uuid4()
    store = {
        "users": {alice: "Alice", bob: "Bob"},
        "agents": {},
        "messages": {},
    }
    routes = import_messages(monkeypatch, store)

    sent = routes.send_message(routes.MessageCreateRequest(receiver_id=bob, content="hello"), current_user=(alice, "user"))
    assert sent.sender_id == alice
    assert sent.receiver_id == bob
    assert sent.content == "hello"

    conversations = routes.list_messages(current_user=(bob, "user"))
    assert conversations[0].conversation_user_id == alice
    assert conversations[0].last_message == "hello"
    assert conversations[0].unread_count == 1


def test_unread_count_and_mark_read(monkeypatch):
    alice = uuid4()
    bob = uuid4()
    message_id = uuid4()
    store = {
        "users": {alice: "Alice", bob: "Bob"},
        "agents": {},
        "messages": {
            message_id: {
                "id": message_id,
                "sender_id": alice,
                "receiver_id": bob,
                "content": "ping",
                "read": False,
                "created_at": datetime.now(),
            }
        },
    }
    routes = import_messages(monkeypatch, store)

    assert routes.get_unread_count(current_user=(bob, "user")) == {"count": 1}
    marked = routes.mark_message_read(message_id, current_user=(bob, "user"))
    assert marked.read is True
    assert routes.get_unread_count(current_user=(bob, "user")) == {"count": 0}


def test_agent_token_sends_as_owner_user(monkeypatch):
    owner = uuid4()
    receiver = uuid4()
    agent_id = uuid4()
    store = {
        "users": {owner: "Owner", receiver: "Receiver"},
        "agents": {agent_id: owner},
        "messages": {},
    }
    routes = import_messages(monkeypatch, store)

    sent = routes.send_message(routes.MessageCreateRequest(receiver_id=receiver, content="from agent"), current_user=(agent_id, "agent"))

    assert sent.sender_id == owner
    assert sent.receiver_id == receiver
