from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend"


def test_agent_registration_page_no_longer_collects_manual_skills():
    page = (FRONTEND / "app/agents/new/page.tsx").read_text()

    assert "SUGGESTED_SKILLS" not in page
    assert "skillInput" not in page
    assert "至少 1 个技能" not in page
    assert "--skills" not in page
    assert "Agent 会根据任务描述自主判断能力，无需手动配置技能" in page


def test_task_publish_page_and_client_exist():
    task_page = FRONTEND / "app/tasks/new/page.tsx"
    task_client = FRONTEND / "lib/api/tasks.ts"

    assert task_page.exists()
    assert task_client.exists()

    page = task_page.read_text()
    client = task_client.read_text()

    assert "已发布，等待 agent 接单" in page
    assert "title" in page
    assert "description" in page
    assert "assigned_agent_id" in page
    assert "apiClient.post" in client
    assert "'/tasks'" in client
