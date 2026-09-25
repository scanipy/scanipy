"""Add provisional occurrence history: shape only, no runtime grants or RLS.

Revision ID: 20260925_0004
Revises: 20260925_0003
"""

from pathlib import Path

from alembic import op

revision = "20260925_0004"
down_revision = "20260925_0003"
branch_labels = None
depends_on = None

TABLES = (
    "scan_requests",
    "source_captures",
    "scan_seals",
    "work_items",
    "work_attempts",
    "detector_runs",
    "detection_occurrences",
    "capture_leases",
)


def upgrade() -> None:
    op.execute("CREATE SCHEMA scanipy_execution")
    op.execute(
        "ALTER TABLE public.codebases ADD CONSTRAINT "
        "codebases_execution_scope_key UNIQUE (org_id,id)"
    )
    op.execute(Path(__file__).with_name("execution_v1_tables.sql").read_text(encoding="utf-8"))
    op.execute(Path(__file__).with_name("execution_v1_history.sql").read_text(encoding="utf-8"))
    mutable_columns = {
        "scan_requests": [
            "revision",
            "capture_state",
            "detection_state",
            "identity_state",
            "active_detection_work_id",
            "error_reference",
            "cancellation_bytes",
        ],
        "source_captures": [
            "revision",
            "retention_state",
            "cleanup_token",
            "cleanup_expires_at",
            "retirement_bytes",
            "retirement_digest",
        ],
        "scan_seals": [],
        "detection_occurrences": [],
        "work_items": [
            "revision",
            "state",
            "active_attempt_id",
            "fencing_token",
            "next_attempt_at",
            "terminal_bytes",
            "terminal_digest",
        ],
        "work_attempts": [
            "lease_expires_at",
            "state",
            "terminal_at",
            "result_schema",
            "result_bytes",
            "result_digest",
        ],
        "detector_runs": [
            "state",
            "terminal_at",
            "result_schema",
            "result_bytes",
            "result_digest",
            "stdout",
            "stderr",
            "failure_prefix",
            "result_count",
            "inventory_digest",
        ],
        "capture_leases": ["expires_at", "released_at", "release_bytes", "release_digest"],
    }
    for table, columns in mutable_columns.items():
        args = ",".join("'" + column + "'" for column in columns)
        op.execute(
            "CREATE TRIGGER immutable_execution_row BEFORE UPDATE OR DELETE "
            f"ON scanipy_execution.{table} FOR EACH ROW "
            f"EXECUTE FUNCTION scanipy_execution.immutable_history_guard({args})"
        )
        op.execute(
            "CREATE TRIGGER immutable_execution_truncate BEFORE TRUNCATE "
            f"ON scanipy_execution.{table} FOR EACH STATEMENT "
            "EXECUTE FUNCTION scanipy_execution.immutable_history_guard()"
        )
    op.execute(Path(__file__).with_name("execution_v1_acl.sql").read_text(encoding="utf-8"))


def downgrade() -> None:
    op.execute("SET LOCAL row_security=off")
    for table in TABLES:
        op.execute(
            f"DO $$ BEGIN IF EXISTS(SELECT 1 FROM scanipy_execution.{table}) "  # noqa: S608 -- fixed migration identifiers
            "THEN RAISE EXCEPTION 'cannot downgrade nonempty execution history'; END IF; END $$"
        )
    op.execute(
        "ALTER TABLE scanipy_execution.scan_requests DROP CONSTRAINT execution_detection_work_fk"
    )
    op.execute(
        "ALTER TABLE scanipy_execution.work_items DROP CONSTRAINT execution_active_attempt_fk"
    )
    op.execute(
        "ALTER TABLE scanipy_execution.work_items DROP CONSTRAINT execution_identity_occurrence_fk"
    )
    for table in (
        "capture_leases",
        "detection_occurrences",
        "detector_runs",
        "work_attempts",
        "work_items",
        "scan_seals",
        "source_captures",
        "scan_requests",
    ):
        op.execute(f"DROP TABLE scanipy_execution.{table}")
    op.execute("DROP FUNCTION scanipy_execution.immutable_history_guard()")
    op.execute("DROP SCHEMA scanipy_execution")
    op.execute("ALTER TABLE public.codebases DROP CONSTRAINT codebases_execution_scope_key")
