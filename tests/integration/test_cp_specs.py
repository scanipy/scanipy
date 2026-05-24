"""Phase-1 TST-AC specs for the Control Plane & Attestation family — INTEGRATION side.

Spec-first TDD: production code for CMP-CP-* does not exist yet. Each test is a
registered stub (`xfail(strict=False)` + `pytest.skip`) that flips red→green when
the implementation lands. Mirrors `tests/unit/test_dsl_proofs.py`.

Scope of this file (disjoint from the unit file):
  - TST-AC-CP-02a   [INTEGRATION] credentials unreadable at rest without managed key;
                     rotation supported (RULE-9 Security Analyst review applies)
  - TST-AC-CP-03a   [INTEGRATION] migrations apply forward and roll back cleanly
  - TST-AC-CP-04a   [INTEGRATION] SSO sign-up provisions org row + first-admin membership
  - TST-AC-CP-05c   [INTEGRATION] CI runs both pipelines on canary corpus on every
                     detector/engine/Env change (Gate 3)

Marker set is closed (`--strict-markers`). The WBS "Kind tag" lives in the docstring.
"""

import os
import subprocess
from pathlib import Path

import pytest

# Repo root = three levels up from tests/integration/test_cp_specs.py.
_REPO_ROOT = Path(__file__).resolve().parents[2]

# Every table the CMP-CP-03 migration set must materialize on `upgrade head`
# (DOC-DB §4 topological order). Used by the AC-CP-03a round-trip assertions.
_CP03_TABLES = (
    "orgs",
    "memberships",
    "projects",
    "codebases",
    "scm_credentials",
    "org_policies",
    "snapshots",
    "proposed_specs",
    "spec_versions",
    "scans",
    "attestations",
    "findings",
    "provenance_records",
    "triage_scores",
    "repartition_events",
)


def _alembic(command: list[str], database_url: str) -> subprocess.CompletedProcess[str]:
    """Run an Alembic subcommand from the repo root with the DB URL injected."""
    env = {**os.environ, "SCANIPY_DATABASE_URL": database_url}
    return subprocess.run(
        ["alembic", *command],
        cwd=_REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.integration
@pytest.mark.xfail(
    reason="CMP-CP-02 (credential encryption service) not yet implemented — spec stub",
    strict=False,
)
def test_cp02a_credentials_unreadable_at_rest_and_rotatable() -> None:
    """Credentials are unreadable at rest without the managed key; rotation is supported.

    Test id:      TST-AC-CP-02a
    Maps to AC:   AC-CP-02a (SDD §10 CMP-CP-02)
    Kind tag:     [INTEGRATION]
    Inputs:       Plaintext SCM credential bytes + an org_id; the
                  CredentialEncryptionService (KMS envelope encryption per
                  CLAR-DEPLOY-04: per-tenant CMK wraps a per-credential data key).
    Outputs:      EncryptedCredential persisted to scm_credentials (DOC-DB §4.5); the
                  ciphertext at rest; a rotate_cmk(org_id) operation.
    Pass criteria: (1) The at-rest ciphertext is not equal to the plaintext and cannot be
                  decrypted without the managed CMK (decrypt without/with-wrong key fails;
                  decrypt via the service round-trips to the original plaintext).
                  (2) rotate_cmk(org_id) succeeds and credentials remain decryptable
                  afterward (forced-rotation path; annual rotation is AWS-KMS-managed).
    Frequency:    every CI run
    Hard gate?:   yes — Stage-A GA process gate; INV-3-adjacent credential handling.
    Notes:        RULE-9 — CMP-CP-02 touches credential material; this spec requires
                  Security Analyst sign-off before the implementing PR merges.
    """
    # TODO: import CredentialEncryptionService from the CP-02 module when DONE; assert
    # at-rest ciphertext != plaintext, decrypt without managed key fails, round-trip
    # succeeds, and rotate_cmk(org_id) preserves decryptability. May use a KMS local
    # stub/moto for the integration harness.
    pytest.skip("CMP-CP-02 not implemented yet")


@pytest.mark.integration
def test_cp03a_migrations_apply_forward_and_roll_back_cleanly() -> None:
    """Migrations apply forward and roll back cleanly on a fresh database.

    Test id:      TST-AC-CP-03a
    Maps to AC:   AC-CP-03a (SDD §10 CMP-CP-03)
    Kind tag:     [INTEGRATION]
    Inputs:       A fresh PostgreSQL 16 database; the Alembic migration sequence under
                  db/migrations/versions/ (DOC-DB §2; DOC-CMP-CP-03 §3).
    Outputs:      `alembic upgrade head` then `alembic downgrade base` applied to the
                  fresh DB; resulting schema state.
    Pass criteria: `upgrade head` creates every SDD-enumerated table (orgs, projects,
                  codebases, scm_credentials, org_policies, memberships, snapshots,
                  proposed_specs, spec_versions, attestations) plus invariant tables;
                  `downgrade base` removes them leaving no residual objects; the round
                  trip exits cleanly (no errors) and is idempotent on a fresh DB.
    Frequency:    every CI run
    Hard gate?:   yes — Stage-A GA process gate (schema must materialize cleanly).

    Environment: requires a live PostgreSQL 16 via SCANIPY_DATABASE_URL (the CI
    `integration-tests` job provides a `postgres:16` service). When the URL is
    absent (e.g. the local sandbox has no Postgres), the test SKIPS with an
    explicit env-gap reason rather than asserting a false pass.

    NOTE: RLS session-variable *semantics* (app.org_id/user_id/role) are DEFERRED
    via CLAR-DB-02; this spec asserts migration up/down cleanliness — that the RLS
    catalog objects are both created on upgrade and fully removed on downgrade
    (the AC-CP-03a "no residual objects" falsifier) — not RLS access behaviour.
    """
    database_url = os.environ.get("SCANIPY_DATABASE_URL")
    if not database_url:
        pytest.skip(
            "SCANIPY_DATABASE_URL not configured — live PostgreSQL 16 integration "
            "env gap; AC-CP-03a runs in the CI integration-tests job."
        )

    import psycopg2  # imported lazily so collection does not require the driver

    def _table_count() -> int:
        with psycopg2.connect(database_url) as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public' "
                "AND tablename = ANY(%s);",
                (list(_CP03_TABLES),),
            )
            return len(cur.fetchall())

    def _residual_object_count() -> tuple[int, int, int]:
        """(public tables, RLS policies, set_updated_at functions) still present.

        `alembic_version` is Alembic's own bookkeeping table (created on the
        first upgrade and retained at `base`); it is not a CMP-CP-03 object, so
        it is excluded from the residual-table count.
        """

        def _scalar(cur: "psycopg2.extensions.cursor") -> int:
            row = cur.fetchone()
            assert row is not None, "COUNT(*) query unexpectedly returned no row"
            return int(row[0])

        with psycopg2.connect(database_url) as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM pg_tables WHERE schemaname = 'public' "
                "AND tablename <> 'alembic_version';"
            )
            tables = _scalar(cur)
            cur.execute("SELECT count(*) FROM pg_policies;")
            policies = _scalar(cur)
            cur.execute("SELECT count(*) FROM pg_proc WHERE proname = 'set_updated_at';")
            functions = _scalar(cur)
            return tables, policies, functions

    # Start from a known-clean state so the assertions are unambiguous.
    base = _alembic(["downgrade", "base"], database_url)
    assert base.returncode == 0, f"pre-test downgrade failed:\n{base.stderr}"

    # 1. upgrade head — every CP-03 table materializes.
    up = _alembic(["upgrade", "head"], database_url)
    assert up.returncode == 0, f"alembic upgrade head failed:\n{up.stderr}"
    assert _table_count() == len(_CP03_TABLES), (
        f"upgrade head did not create every CMP-CP-03 table ({_table_count()}/{len(_CP03_TABLES)})"
    )

    # 2. downgrade base — no residual tables, policies, or functions.
    down = _alembic(["downgrade", "base"], database_url)
    assert down.returncode == 0, f"alembic downgrade base failed:\n{down.stderr}"
    residual_tables, residual_policies, residual_functions = _residual_object_count()
    assert residual_tables == 0, f"{residual_tables} residual table(s) after downgrade"
    assert residual_policies == 0, f"{residual_policies} residual RLS policy(ies) after downgrade"
    assert residual_functions == 0, (
        f"{residual_functions} residual set_updated_at function(s) after downgrade"
    )

    # 3. idempotent re-application on the now-clean DB.
    reup = _alembic(["upgrade", "head"], database_url)
    assert reup.returncode == 0, f"re-applied upgrade head failed:\n{reup.stderr}"
    assert _table_count() == len(_CP03_TABLES), "re-applied upgrade is not idempotent"

    # Leave the DB clean for any subsequent test in the session.
    final = _alembic(["downgrade", "base"], database_url)
    assert final.returncode == 0, f"final downgrade base failed:\n{final.stderr}"


@pytest.mark.integration
@pytest.mark.xfail(
    reason="CMP-CP-04 (auth + dashboard) not yet implemented — spec stub",
    strict=False,
)
def test_cp04a_sso_signup_provisions_org_and_first_admin() -> None:
    """SSO sign-up provisions an org row plus first-admin membership.

    Test id:      TST-AC-CP-04a
    Maps to AC:   AC-CP-04a (SDD §10 CMP-CP-04)
    Kind tag:     [INTEGRATION]
    Inputs:       A first-time Auth0 (OIDC) sign-in for a new tenant (JWT with sub,
                  org_id, role claims per DOC-API §2.1 / CLAR-DEPLOY-10); the
                  provisioning flow (DOC-CMP-CP-04 §2).
    Outputs:      A new `orgs` row and a `memberships` row binding the first user as
                  org-admin.
    Pass criteria: After first SSO sign-in, exactly one orgs row exists for the tenant
                  and exactly one memberships row links the signing user with
                  role=org-admin (CLAR-DEPLOY-12); a second sign-in of the same tenant
                  does not duplicate the org or re-provision a second admin.
    Frequency:    every CI run
    Hard gate?:   yes — Stage-A GA process gate (tenant onboarding correctness).
    """
    # TODO: drive the provisioning flow with a mock Auth0 JWT for a new tenant; assert a
    # single orgs row + first-admin memberships row are created and that re-sign-in is
    # idempotent, once CMP-CP-04 is DONE.
    pytest.skip("CMP-CP-04 not implemented yet")


@pytest.mark.integration
@pytest.mark.xfail(
    reason="CMP-CP-05 (Determinism Attestor) not yet implemented — spec stub",
    strict=False,
)
def test_cp05c_ci_runs_both_pipelines_on_canary_on_change() -> None:
    """CI runs both pipelines on the canary corpus on every detector/engine/Env change.

    Test id:      TST-AC-CP-05c
    Maps to AC:   AC-CP-05c (SDD §10 CMP-CP-05)
    Kind tag:     [INTEGRATION]
    Inputs:       .github/workflows/attestor.yml; its trigger `paths:` filter and job
                  definitions (DOC-CMP-CP-05 §3/§6).
    Outputs:      Parsed workflow: jobs `attestor-core` (required status check) and
                  `determinism-canary` (informational), and the path-trigger set.
    Pass criteria: attestor.yml defines both the `attestor-core` and `determinism-canary`
                  jobs over the canary corpus; the trigger path-filter covers
                  detector/engine/Env change surfaces (detectors/**, analysis/**,
                  workers/**, services/scan/**, services/snapshot/**); the core job is a
                  required status check on `main`.
    Frequency:    every CI run
    Hard gate?:   yes — Gate 3 (Attestor required status check, CLAUDE.md §15).
    Notes:        Env-change cadence/path-coverage edge cases are tracked under
                  CLAR-CP-05-02 (e.g. Env pins outside workers/**); this spec asserts the
                  documented path set, not the open-CLAR extension.
    """
    # TODO: parse .github/workflows/attestor.yml; assert both jobs exist, the path filter
    # covers the documented change surfaces, and attestor-core is wired as the required
    # check, once CMP-CP-05 is DONE.
    pytest.skip("CMP-CP-05 not implemented yet")
