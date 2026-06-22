from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_messages_frontend_pages_and_client_exist():
    list_page = ROOT / "frontend" / "app" / "messages" / "page.tsx"
    chat_page = ROOT / "frontend" / "app" / "messages" / "[user_id]" / "page.tsx"
    api = ROOT / "frontend" / "lib" / "api" / "messages.ts"
    navbar = ROOT / "frontend" / "components" / "Navbar.tsx"
    migration = ROOT / "backend" / "migrations" / "versions" / "20260622_messages.py"

    assert list_page.exists()
    assert chat_page.exists()

    list_text = list_page.read_text()
    assert "最近聊天" in list_text
    assert "unread_count" in list_text
    assert "messagesApi.list" in list_text

    chat_text = chat_page.read_text()
    assert "messagesApi.thread" in chat_text
    assert "messagesApi.send" in chat_text
    assert "messagesApi.markRead" in chat_text

    api_text = api.read_text()
    assert "/messages/unread" in api_text
    assert "/messages" in api_text
    assert "markRead" in api_text

    nav_text = navbar.read_text()
    assert "messagesApi.unread" in nav_text
    assert "/messages" in nav_text
    assert "hasUnreadMessages" in nav_text

    assert migration.exists()
    assert "CREATE TABLE IF NOT EXISTS messages" in migration.read_text()
