"""row-level security policies for multi-tenant tables

Revision ID: 20260524_0002
Revises: 20260524_0001
Create Date: 2026-05-24

CMP-CP-03 revision 2 of 2 — RLS POLICIES ONLY.

Split from the table-shape migration per DOC-CMP-CP-03 §3.1 / DOC-DB §2:
"Migrations that change RLS policies are split from migrations that change table
shape; never combined." This revision enables Row-Level Security and installs
the tenant-isolation policy pair (DOC-DB §3.3) on every multi-tenant table,
plus the four custom cases (DOC-CMP-CP-03 §3.3):

  * orgs               — RLS NOT enabled (this table defines tenancy).
  * spec_versions      — scope='global' rows universally readable.
  * scm_credentials    — standard template (the org-admin-only write + viewer
                         read-deny is an application-layer role gate; RLS here
                         enforces only the tenant boundary, per DOC-DB §4.5).
  * provenance_records — standard tenant template for SELECT/modify, but NO
                         UPDATE/DELETE is ever permitted (append-only,
                         DOC-DB §4.13). We add a restrictive policy that blocks
                         UPDATE/DELETE for everyone subject to RLS.

The RLS predicates key on the `app.org_id` session variable (CLAR-DB-02 working
assumption). A connection without the variable evaluates
`current_setting('app.org_id', true) IS NULL`, making the predicate false →
zero rows on SELECT and an RLS violation on write (the CLAR-DEPLOY-16 layer-2
backstop). The application-side setter contract (db/session.py) is a CMP-CP-01
follow-up and is out of scope for this migration.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260524_0002"
down_revision: str | None = "20260524_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Multi-tenant tables that receive the standard policy pair (DOC-DB §3.3).
# orgs is excluded (defines tenancy); spec_versions + provenance_records get
# custom handling below.
_STANDARD_RLS_TABLES = (
    "memberships",
    "projects",
    "codebases",
    "scm_credentials",
    "org_policies",
    "snapshots",
    "proposed_specs",
    "scans",
    "attestations",
    "findings",
    "triage_scores",
    "repartition_events",
)


def upgrade() -> None:
    for table in _STANDARD_RLS_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")
        op.execute(
            f"""
            CREATE POLICY tenant_isolation_select ON {table}
              FOR SELECT
              USING (org_id::text = current_setting('app.org_id', true));
            """
        )
        op.execute(
            f"""
            CREATE POLICY tenant_isolation_modify ON {table}
              FOR ALL
              USING (org_id::text = current_setting('app.org_id', true))
              WITH CHECK (org_id::text = current_setting('app.org_id', true));
            """
        )

    # spec_versions — custom: global rows universally readable (DOC-DB §4.9).
    op.execute("ALTER TABLE spec_versions ENABLE ROW LEVEL SECURITY;")
    op.execute(
        """
        CREATE POLICY spec_versions_select ON spec_versions
          FOR SELECT
          USING (scope = 'global'
              OR org_id::text = current_setting('app.org_id', true));
        """
    )
    op.execute(
        """
        CREATE POLICY spec_versions_modify ON spec_versions
          FOR ALL
          USING (org_id::text = current_setting('app.org_id', true))
          WITH CHECK (org_id::text = current_setting('app.org_id', true));
        """
    )

    # provenance_records — append-only (DOC-DB §4.13). Standard tenant
    # SELECT/INSERT policy, plus a RESTRICTIVE policy that blocks UPDATE and
    # DELETE for every role subject to RLS (the BYPASSRLS scanipy_system role is
    # unaffected; grant-level revokes are layered on top by CMP-FND-03).
    op.execute("ALTER TABLE provenance_records ENABLE ROW LEVEL SECURITY;")
    op.execute(
        """
        CREATE POLICY tenant_isolation_select ON provenance_records
          FOR SELECT
          USING (org_id::text = current_setting('app.org_id', true));
        """
    )
    op.execute(
        """
        CREATE POLICY tenant_isolation_insert ON provenance_records
          FOR INSERT
          WITH CHECK (org_id::text = current_setting('app.org_id', true));
        """
    )
    op.execute(
        """
        CREATE POLICY provenance_append_only_no_update ON provenance_records
          AS RESTRICTIVE
          FOR UPDATE
          USING (false);
        """
    )
    op.execute(
        """
        CREATE POLICY provenance_append_only_no_delete ON provenance_records
          AS RESTRICTIVE
          FOR DELETE
          USING (false);
        """
    )


def downgrade() -> None:
    # Drop every policy first, then disable RLS, leaving no residual catalog
    # rows (the AC-CP-03a "no orphan objects" reversal).
    op.execute("DROP POLICY provenance_append_only_no_delete ON provenance_records;")
    op.execute("DROP POLICY provenance_append_only_no_update ON provenance_records;")
    op.execute("DROP POLICY tenant_isolation_insert ON provenance_records;")
    op.execute("DROP POLICY tenant_isolation_select ON provenance_records;")
    op.execute("ALTER TABLE provenance_records DISABLE ROW LEVEL SECURITY;")

    op.execute("DROP POLICY spec_versions_modify ON spec_versions;")
    op.execute("DROP POLICY spec_versions_select ON spec_versions;")
    op.execute("ALTER TABLE spec_versions DISABLE ROW LEVEL SECURITY;")

    for table in reversed(_STANDARD_RLS_TABLES):
        op.execute(f"DROP POLICY tenant_isolation_modify ON {table};")
        op.execute(f"DROP POLICY tenant_isolation_select ON {table};")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;")
