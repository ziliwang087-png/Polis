from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_task_deliverables_frontend_controls_exist():
    page = ROOT / "frontend" / "app" / "tasks" / "[id]" / "page.tsx"
    api = ROOT / "frontend" / "lib" / "api" / "tasks.ts"
    types = ROOT / "frontend" / "lib" / "api" / "types.ts"
    migration = ROOT / "backend" / "migrations" / "versions" / "20260622_task_deliverables.py"

    page_text = page.read_text()
    assert "交付物" in page_text
    assert "type=\"file\"" in page_text
    assert "deliverablesApi.upload" in page_text
    assert "deliverablesApi.list" in page_text
    assert "canUploadDeliverable" in page_text
    assert "isTaskOwner" in page_text
    assert "下载" in page_text

    api_text = api.read_text()
    assert "deliverablesApi" in api_text
    assert "/deliverables" in api_text
    assert "FormData" in api_text

    type_text = types.read_text()
    assert "TaskDeliverable" in type_text
    assert "uploaded_by_type" in type_text

    assert migration.exists()
    migration_text = migration.read_text()
    assert "CREATE TABLE IF NOT EXISTS task_deliverables" in migration_text
    assert "task-deliverables" in migration_text
