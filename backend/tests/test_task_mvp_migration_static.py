from pathlib import Path


MIGRATIONS = Path(__file__).resolve().parents[1] / "migrations" / "versions"


def test_task_mvp_alembic_migration_creates_tasks_table():
    migration = MIGRATIONS / "20260622_task_mvp.py"

    assert migration.exists()
    text = migration.read_text()
    assert 'revision: str = "20260622_task_mvp"' in text
    assert 'down_revision: Union[str, None] = "20260621_stale_claim_reaped"' in text
    assert 'CREATE TABLE IF NOT EXISTS tasks' in text
    assert 'CREATE INDEX IF NOT EXISTS idx_tasks_status' in text
    assert 'DROP TABLE IF EXISTS tasks' in text
