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
    assert "预算（Credits）" in page
    assert "截止时间" in page
    assert "优先级" in page
    assert "建议设置截止时间，帮助 Agent 评估优先级" in page
    assert "紧急任务在任务广场置顶" in page
    assert "assigned_agent_id" not in page
    assert "指定 Agent" not in page
    assert "apiClient.post" in client
    assert "'/tasks'" in client


def test_task_marketplace_page_uses_tasks_api_not_legacy_jobs():
    page_path = FRONTEND / "app/tasks/page.tsx"

    assert page_path.exists()
    page = page_path.read_text()

    assert "任务广场" in page
    assert "tasksApi.list" in page
    assert "priorityRank" in page
    assert "jobsApi" not in page
    assert "JobCard" not in page
    assert "agentsApi.listPublic" not in page
