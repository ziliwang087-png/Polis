from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_task_status_frontend_controls_exist():
    page = ROOT / "frontend" / "app" / "tasks" / "[id]" / "page.tsx"
    tasks_api = ROOT / "frontend" / "lib" / "api" / "tasks.ts"
    types = ROOT / "frontend" / "lib" / "api" / "types.ts"

    page_text = page.read_text()
    assert "STATUS_STEPS" in page_text
    assert "已发布" in page_text
    assert "已接单" in page_text
    assert "开始工作" in page_text
    assert "提交交付物" in page_text
    assert "canSubmitTask" in page_text
    assert "task.assigned_agent_id" in page_text
    assert "验收通过" in page_text
    assert "打回重做" in page_text
    assert "取消任务" in page_text

    api_text = tasks_api.read_text()
    assert "start:" in api_text
    assert "/start" in api_text
    assert "submit:" in api_text
    assert "/submit" in api_text
    assert "agent_id?: string" in api_text
    assert "accept:" in api_text
    assert "/accept" in api_text
    assert "requestRevision:" in api_text
    assert "/request-revision" in api_text
    assert "cancel:" in api_text
    assert "/cancel" in api_text

    type_text = types.read_text()
    assert "'claimed'" in type_text
    assert "'cancelled'" in type_text


def test_task_rating_frontend_is_owner_only():
    page = ROOT / "frontend" / "app" / "tasks" / "[id]" / "page.tsx"

    page_text = page.read_text()
    assert "canRateTask" in page_text
    assert "Boolean(isTaskOwner && task?.status === 'completed')" in page_text
    assert "{canRateTask && (" in page_text
    assert "只有任务发布者可以评分" in page_text


def test_task_status_migration_allows_new_states():
    migration = ROOT / "backend" / "migrations" / "versions" / "20260622_task_status_flow.py"

    assert migration.exists()
    text = migration.read_text()
    assert "chk_tasks_status" in text
    assert "'claimed'" in text
    assert "'submitted'" in text
    assert "'cancelled'" in text
