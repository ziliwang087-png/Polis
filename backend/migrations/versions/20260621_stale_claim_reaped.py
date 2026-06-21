"""add stale_claim_reaped to job_event_type

Revision ID: 20260621_stale_claim_reaped
Revises: 20260620_polis_v1
Create Date: 2026-06-21

Adds 'stale_claim_reaped' value to the job_event_type enum so the
stale-claim reaper has a dedicated audit event_type instead of
multiplexing into 'canceled'.

NOTE: ALTER TYPE ... ADD VALUE cannot run inside a transaction in
PostgreSQL, so this migration uses op.execute with COMMIT statements
to break out of alembic's implicit transaction. The down migration
recreates the enum without the value (data using it must be migrated
to 'canceled' first; we do that defensively).
"""
from typing import Sequence, Union

from alembic import op


revision: str = "20260621_stale_claim_reaped"
down_revision: Union[str, None] = "20260620_polis_v1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ALTER TYPE ... ADD VALUE cannot run inside an implicit transaction
    # in some Postgres versions, so we COMMIT first, run the DDL on the
    # raw psycopg2 connection in autocommit mode, then continue.
    conn = op.get_bind()
    raw = conn.connection.driver_connection
    prev_isolation = getattr(raw, "isolation_level", None)
    try:
        raw.set_isolation_level(0)  # ISOLATION_LEVEL_AUTOCOMMIT
        cur = raw.cursor()
        cur.execute(
            "ALTER TYPE job_event_type ADD VALUE IF NOT EXISTS 'stale_claim_reaped'"
        )
        cur.close()
    finally:
        if prev_isolation is not None:
            raw.set_isolation_level(prev_isolation)


def downgrade() -> None:
    # Recreating an enum to remove a value is destructive; the safe path
    # is to first rewrite any rows using the new value back to 'canceled'.
    op.execute(
        "UPDATE job_events SET event_type = 'canceled' "
        "WHERE event_type = 'stale_claim_reaped'"
    )
    op.execute("ALTER TYPE job_event_type RENAME TO job_event_type_old")
    op.execute(
        "CREATE TYPE job_event_type AS ENUM ("
        "'created','claimed','progress','delivered','rated','canceled')"
    )
    op.execute(
        "ALTER TABLE job_events ALTER COLUMN event_type "
        "TYPE job_event_type USING event_type::text::job_event_type"
    )
    op.execute("DROP TYPE job_event_type_old")
