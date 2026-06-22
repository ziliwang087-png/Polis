from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_leaderboard_frontend_page_and_api_client_exist():
    page = ROOT / "frontend" / "app" / "leaderboard" / "page.tsx"
    tasks_api = ROOT / "frontend" / "lib" / "api" / "tasks.ts"
    types = ROOT / "frontend" / "lib" / "api" / "types.ts"
    navbar = ROOT / "frontend" / "components" / "Navbar.tsx"

    assert page.exists()
    page_text = page.read_text()
    assert "XP 排行" in page_text
    assert "Agent 排行" in page_text
    assert "用户排行" in page_text
    assert "leaderboardApi.xp" in page_text
    assert "leaderboardApi.agents" in page_text
    assert "leaderboardApi.tasks" in page_text

    api_text = tasks_api.read_text()
    assert "leaderboardApi" in api_text
    assert "/leaderboard/xp" in api_text
    assert "/leaderboard/agents" in api_text
    assert "/leaderboard/tasks" in api_text

    type_text = types.read_text()
    assert "LeaderboardTab" in type_text
    assert "LeaderboardResponse" in type_text

    nav_text = navbar.read_text()
    assert "/leaderboard" in nav_text
