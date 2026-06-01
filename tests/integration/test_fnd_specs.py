"""FND-family integration specs — live-PostgreSQL schema falsifiers + TST-AC-FND-03a.

Spec-first TDD: this file holds the **live-PostgreSQL** half of the CMP-FND-02
schema invariants plus the CMP-FND-03 end-to-end verifiability stub.

Why these tests live here and not in ``tests/unit/test_fnd_specs.py``:
the four schema falsifiers below assert real PostgreSQL constraint behaviour
(NOT NULL ``23502`` / CHECK ``23514`` SQLSTATEs) by applying the CP-03 Alembic
migration to a live ``postgres:16`` and attempting failing INSERTs. CI's
``unit-tests`` job has **no database**, and CI's ``integration-tests`` job runs
``pytest tests/integration/ -m integration`` against a ``postgres:16`` service
(``.github/workflows/ci.yml``). Keeping these falsifiers under
``tests/unit/`` (where they only ever ``pytest.skip`` for lack of a DB) means
the INV-1/INV-2/INV-5 hard gates would **never execute in CI**. Marking them
``integration`` and placing them here makes CI's postgres job run them.

The metadata-introspection half of each invariant (column nullability,
``CheckConstraint`` sqltext, index columns — all no-DB) stays in
``tests/unit/test_fnd_specs.py`` so the fast unit job still asserts the schema
shape on every run.

These live-PG tests still ``pytest.skip`` gracefully when
``SCANIPY_DATABASE_URL`` is unset (local dev without a DB); they run under CI's
postgres service, which sets that env var.

Covers:
  - TST-AC-FND-02b   [INVARIANT][live-PG] — non-null origin/S_version/env_digest
  - TST-INV-1-FND-02 [INVARIANT][live-PG] — origin NOT NULL + enum CHECK (no 'mixed')
  - TST-INV-2-FND-02 [INVARIANT][live-PG] — S_version/env_digest NOT NULL + format CHECK
  - TST-INV-5-FND-02 [INVARIANT][live-PG] — cpg_order_hash_annotation NOT NULL + literal CHECK
  - TST-AC-FND-03a   [INTEGRATION] — record independently verifiable, no re-run
"""

import os
import subprocess
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from services.scan.models.findings import CPG_ORDER_HASH_ANNOTATION

if TYPE_CHECKING:
    import psycopg2.extensions

# Repo root = three levels up from tests/integration/test_fnd_specs.py.
_REPO_ROOT = Path(__file__).resolve().parents[2]

# The exact INV-5 annotation literal pinned by the
# findings_cpg_order_hash_annotation_chk CHECK constraint (DOC-DB sec 4.12).
_ANNOTATION = "canonical iff fingerprint_class = strong"


def _alembic_upgrade_head(database_url: str) -> None:
    """Apply the CP-03 migration (the FND-02 vehicle) to a live database."""
    env = {**os.environ, "SCANIPY_DATABASE_URL": database_url}
    result = subprocess.run(
        ["alembic", "upgrade", "head"],
        cwd=_REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"alembic upgrade head failed:\n{result.stderr}"


def _alembic_downgrade_base(database_url: str) -> None:
    """Tear the schema back down so the live test leaves the DB clean."""
    env = {**os.environ, "SCANIPY_DATABASE_URL": database_url}
    subprocess.run(
        ["alembic", "downgrade", "base"],
        cwd=_REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _seed_and_insert(
    cur: "psycopg2.extensions.cursor",
    overrides: dict[str, object] | None = None,
    omit: str | None = None,
) -> None:
    """Seed the FK chain (org->codebase->snapshot->scan) then INSERT one finding.

    ``overrides`` replaces individual finding column values; ``omit`` drops a
    column entirely (to exercise NOT NULL). Raises whatever ``psycopg2`` raises
    on a constraint violation; the caller asserts on the SQLSTATE.
    """
    overrides = overrides or {}
    sha40 = "a" * 40
    digest = "sha256:" + ("b" * 64)
    org_id = str(uuid.uuid4())
    codebase_id = str(uuid.uuid4())
    snapshot_id = str(uuid.uuid4())
    scan_id = str(uuid.uuid4())

    cur.execute("INSERT INTO orgs (id, name) VALUES (%s, %s);", (org_id, "t"))
    cur.execute(
        "INSERT INTO codebases (id, org_id, name, scm_provider, scm_repo_url) "
        "VALUES (%s, %s, %s, %s, %s);",
        (codebase_id, org_id, "c", "github", "https://example/r"),
    )
    cur.execute(
        "INSERT INTO snapshots (id, org_id, codebase_id, commit_sha, env_digest, "
        "precondition_status, cpg_tarball_uri, reverse_symbol_index_uri, "
        "dynamic_call_graph_uri, precondition_status_record_uri) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s);",
        (
            snapshot_id,
            org_id,
            codebase_id,
            sha40,
            digest,
            "closed-world",
            "s3://x",
            "s3://y",
            "s3://z",
            "s3://w",
        ),
    )
    cur.execute(
        "INSERT INTO scans (id, org_id, codebase_id, snapshot_id, commit_sha, "
        '"S_version", env_digest, detector_ids) '
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s);",
        (scan_id, org_id, codebase_id, snapshot_id, sha40, "1.0.0", digest, ["d"]),
    )

    values: dict[str, object] = {
        "id": str(uuid.uuid4()),
        "org_id": org_id,
        "codebase_id": codebase_id,
        "scan_id": scan_id,
        "snapshot_id": snapshot_id,
        "commit_sha": sha40,
        "class": "injection",
        "rule_id": "R1",
        "severity": "high",
        "message": "m",
        "physical_location": "{}",
        "origin": "deterministic-core",
        "determinism_partition": "deterministic-core",
        "engine": "ifds",
        "S_version": "1.0.0",
        "env_digest": digest,
        "cpg_order_hash": memoryview(b"\x00" * 32),
        "cpg_order_hash_annotation": _ANNOTATION,
        "fingerprint_class": "strong",
        "slice_fingerprint": memoryview(b"\x01" * 32),
        "precondition_status": "closed-world",
        "status": "open",
    }
    values.update(overrides)
    if omit is not None:
        values.pop(omit)

    cols = ", ".join('"S_version"' if k == "S_version" else f'"{k}"' for k in values)
    placeholders = ", ".join(["%s"] * len(values))
    cur.execute(
        f"INSERT INTO findings ({cols}) VALUES ({placeholders});",
        tuple(values.values()),
    )


def _require_database_url(detail: str) -> str:
    """Return SCANIPY_DATABASE_URL or skip with an explicit env-gap reason."""
    database_url = os.environ.get("SCANIPY_DATABASE_URL")
    if not database_url:
        pytest.skip(
            "SCANIPY_DATABASE_URL not configured -- live PostgreSQL 16 env gap. "
            f"{detail} runs in the CI postgres:16 integration job. No sqlite "
            "shim is used: sqlite silently ignores the regex/octet_length/enum "
            "CHECKs and would yield a false green."
        )
    return database_url


@pytest.mark.integration
def test_fnd_02b_every_row_carries_nonnull_origin_sversion_envdigest_live_pg() -> None:
    """Live-PG: INSERT omitting origin/S_version/env_digest raises 23502.

    Test id:        TST-AC-FND-02b (live-PostgreSQL half)
    Maps to AC:     AC-FND-02b -- "Every row carries a non-null origin,
                    S_version, env_digest (INV-1, INV-2)."
    Kind tag:       [INVARIANT][live-PG]
    Pass criteria:  An INSERT omitting origin, S_version or env_digest raises a
                    NOT NULL violation (SQLSTATE 23502). The column-level
                    nullability metadata is asserted in the unit half in
                    tests/unit/test_fnd_specs.py.
    Frequency:      every CI integration run (postgres:16)
    Hard gate?:     yes -- schema NOT NULL gate for CMP-FND-02.
    """
    database_url = _require_database_url(
        "The NOT NULL 23502 falsifier for findings.origin/S_version/env_digest"
    )

    import psycopg2  # imported lazily so collection does not require the driver
    from psycopg2 import errors

    _alembic_upgrade_head(database_url)
    try:
        for omitted in ("origin", "S_version", "env_digest"):
            conn = psycopg2.connect(database_url)
            try:
                with conn, conn.cursor() as cur:
                    with pytest.raises(errors.NotNullViolation) as exc:
                        _seed_and_insert(cur, omit=omitted)
                    assert exc.value.pgcode == "23502", (
                        f"omitting {omitted} must raise 23502 NOT NULL violation"
                    )
            finally:
                conn.close()
    finally:
        _alembic_downgrade_base(database_url)


@pytest.mark.integration
def test_inv_5_fnd_02_cpg_order_hash_annotation_persisted_at_schema_live_pg() -> None:
    """Live-PG: cpg_order_hash_annotation rejects NULL (23502) and wrong literal (23514).

    Test id:        TST-INV-5-FND-02 (live-PostgreSQL half)
    Maps to AC:     INV-5 (conditional labels self-describing) for CMP-FND-02.
    Kind tag:       [INVARIANT][live-PG]
    Pass criteria:  An INSERT with a NULL annotation raises 23502 (NOT NULL); an
                    INSERT with any other annotation string raises a CHECK
                    violation (23514) from findings_cpg_order_hash_annotation_chk.
                    The NOT NULL + literal-CHECK metadata is asserted in the unit
                    half in tests/unit/test_fnd_specs.py.
    Frequency:      every CI integration run (postgres:16)
    Hard gate?:     yes -- schema INV-5 gate for CMP-FND-02.
    """
    database_url = _require_database_url(
        "The 23502 (omit annotation) and 23514 (wrong annotation literal) falsifiers"
    )

    import psycopg2  # imported lazily so collection does not require the driver
    from psycopg2 import errors

    _alembic_upgrade_head(database_url)
    try:
        # (a) An explicit NULL annotation is rejected by NOT NULL (23502).
        conn = psycopg2.connect(database_url)
        try:
            with conn, conn.cursor() as cur:
                with pytest.raises(errors.NotNullViolation) as exc_null:
                    _seed_and_insert(cur, overrides={"cpg_order_hash_annotation": None})
                assert exc_null.value.pgcode == "23502"
        finally:
            conn.close()

        # (b) A non-conforming annotation is rejected by the literal CHECK (23514).
        conn = psycopg2.connect(database_url)
        try:
            with conn, conn.cursor() as cur:
                with pytest.raises(errors.CheckViolation) as exc_chk:
                    _seed_and_insert(
                        cur,
                        overrides={"cpg_order_hash_annotation": "canonical"},
                    )
                assert exc_chk.value.pgcode == "23514"
        finally:
            conn.close()
    finally:
        _alembic_downgrade_base(database_url)


@pytest.mark.integration
def test_inv_1_fnd_02_origin_partition_at_store_live_pg() -> None:
    """Live-PG: origin rejects NULL (23502) and 'mixed' (23514 enum CHECK).

    Test id:        TST-INV-1-FND-02 (live-PostgreSQL half)
    Maps to AC:     INV-1 (CMP-FND-02 schema) -- schema-level discharge of the
                    determinism partition.
    Kind tag:       [INVARIANT][live-PG]
    Pass criteria:  INSERT omitting origin raises a NOT NULL violation
                    (SQLSTATE 23502); INSERT with origin='mixed' is rejected by
                    the findings_origin_chk CHECK constraint (only
                    deterministic-core / oracle-passthrough permitted). The
                    enum-domain metadata is asserted in the unit half in
                    tests/unit/test_fnd_specs.py.
    Frequency:      every CI integration run (postgres:16)
    Hard gate?:     yes -- schema INV-1 gate for CMP-FND-02.
    """
    database_url = _require_database_url(
        "The 23502 (omit origin) and 23514 (origin='mixed') falsifiers"
    )

    import psycopg2  # imported lazily so collection does not require the driver
    from psycopg2 import errors

    _alembic_upgrade_head(database_url)
    try:
        # (a) Omitting origin -> NOT NULL violation (23502).
        conn = psycopg2.connect(database_url)
        try:
            with conn, conn.cursor() as cur:
                with pytest.raises(errors.NotNullViolation) as exc_null:
                    _seed_and_insert(cur, omit="origin")
                assert exc_null.value.pgcode == "23502"
        finally:
            conn.close()

        # (b) origin='mixed' -> enum CHECK violation (23514).
        conn = psycopg2.connect(database_url)
        try:
            with conn, conn.cursor() as cur:
                with pytest.raises(errors.CheckViolation) as exc_chk:
                    _seed_and_insert(cur, overrides={"origin": "mixed"})
                assert exc_chk.value.pgcode == "23514"
        finally:
            conn.close()
    finally:
        _alembic_downgrade_base(database_url)


@pytest.mark.integration
def test_inv_2_fnd_02_nonnull_sversion_envdigest_at_schema_level_live_pg() -> None:
    """Live-PG: S_version/env_digest reject NULL (23502); malformed env_digest (23514).

    Test id:        TST-INV-2-FND-02 (live-PostgreSQL half)
    Maps to AC:     INV-2 (CMP-FND-02 schema) -- versioned parameters enforced at
                    the SQL constraint level.
    Kind tag:       [INVARIANT][live-PG]
    Pass criteria:  INSERT omitting S_version or env_digest raises a NOT NULL
                    violation (SQLSTATE 23502); INSERT with env_digest not
                    matching ^sha256:[0-9a-f]{64}$ is rejected by the
                    findings_env_digest_chk CHECK (23514). The NOT NULL +
                    format-CHECK metadata is asserted in the unit half in
                    tests/unit/test_fnd_specs.py.
    Frequency:      every CI integration run (postgres:16)
    Hard gate?:     yes -- schema INV-2 gate for CMP-FND-02.
    """
    database_url = _require_database_url(
        "The 23502 (omit S_version/env_digest) and 23514 (malformed env_digest) falsifiers"
    )

    import psycopg2  # imported lazily so collection does not require the driver
    from psycopg2 import errors

    _alembic_upgrade_head(database_url)
    try:
        # (a) Omitting S_version or env_digest -> NOT NULL violation (23502).
        for omitted in ("S_version", "env_digest"):
            conn = psycopg2.connect(database_url)
            try:
                with conn, conn.cursor() as cur:
                    with pytest.raises(errors.NotNullViolation) as exc_null:
                        _seed_and_insert(cur, omit=omitted)
                    assert exc_null.value.pgcode == "23502"
            finally:
                conn.close()

        # (b) Malformed env_digest -> CHECK violation (23514).
        conn = psycopg2.connect(database_url)
        try:
            with conn, conn.cursor() as cur:
                with pytest.raises(errors.CheckViolation) as exc_chk:
                    _seed_and_insert(cur, overrides={"env_digest": "not-a-digest"})
                assert exc_chk.value.pgcode == "23514"
        finally:
            conn.close()
    finally:
        _alembic_downgrade_base(database_url)


# The annotation literal asserted in _seed_and_insert must equal the constant
# the ORM/DDL pin (defence against a silent literal drift in this fixture).
assert CPG_ORDER_HASH_ANNOTATION == _ANNOTATION


@pytest.mark.integration
def test_fnd_03a_record_independently_verifiable_without_rerun() -> None:
    """The signed record is independently verifiable from stored artefacts.

    Test id:        TST-AC-FND-03a
    Maps to AC:     AC-FND-03a -- "The record is independently verifiable from
                    stored artifacts without re-running analysis."
    Kind tag:       [INTEGRATION]
    Pass criteria:  verify_chain returns "VERIFIED" for the untampered record and
                    "TAMPERED" for the mutated one, reconstructing canonical_bytes,
                    verifying the RSASSA_PSS signature, and recomputing sarif_hash
                    / snapshot_digest from the stored blobs. The procedure invokes
                    NO IFDS solver, NO Algorithm 5 run, NO detector.
    Frequency:      every CI run
    Hard gate?:     yes -- component acceptance gate for CMP-FND-03 (AC-FND-03a).

    Hermetic by construction: the signer is an offline software RSASSA-PSS fake
    and the artefact store is in-memory, so this runs green with NO database and
    NO AWS (unlike the live-PG FND-02 falsifiers above, which skip locally). It
    therefore must NOT be gated on SCANIPY_DATABASE_URL.
    """
    import dataclasses
    import sys

    from services.scan.provenance import sign_provenance, verify_chain
    from tests.fnd03_fakes import (
        InMemoryArtifactStore,
        InMemoryProvenanceStore,
        SoftwareKMSSigner,
        make_chain_record,
    )

    signer = SoftwareKMSSigner()
    store = InMemoryProvenanceStore()
    artifacts = InMemoryArtifactStore()
    kms_key_arn = "arn:aws:kms:us-east-1:000000000000:key/fnd03"

    # Build a chain record whose sarif_hash matches a stored SARIF blob.
    sarif_blob = b'{"version":"2.1.0","runs":[]}'
    record = make_chain_record(sarif_bytes=sarif_blob)
    artifacts.put(
        f"orgs/{record.org_id}/codebases/{record.codebase_id}/sarif/{record.scan_id}.sarif.json",
        sarif_blob,
    )

    signed = sign_provenance(record, signer=signer, kms_key_arn=kms_key_arn, store=store)
    assert signed.signature_alg == "RSASSA_PSS_SHA_256"

    # (1) Untampered record verifies, recomputing canonical bytes + sarif digest.
    #     Snapshot the IFDS/detector modules around the call and assert the DELTA
    #     is empty: verification re-runs NO analysis (AC-FND-03a). A delta (not an
    #     absolute-absence) assertion is collection-safe — a sibling integration
    #     module that imports analysis.ifds/detectors at module scope would
    #     otherwise pre-populate sys.modules and break an absolute check.
    before = {m for m in sys.modules if m.startswith(("analysis.ifds", "detectors"))}
    assert verify_chain(signed, signer=signer, artifacts=artifacts, store=store) == "VERIFIED"
    after = {m for m in sys.modules if m.startswith(("analysis.ifds", "detectors"))}
    assert after == before, (
        f"AC-FND-03a: verification must not import IFDS/detector modules; "
        f"new modules pulled in: {after - before}"
    )

    # (2) A mutated signed field (S_version) — keeping the original signature —
    #     makes the recomputed canonical bytes differ, so the RSASSA-PSS
    #     signature no longer verifies: TAMPERED. The verifier recomputes bytes
    #     from record.record; it never trusts the stored canonical_bytes.
    tampered = dataclasses.replace(
        signed,
        record=dataclasses.replace(signed.record, S_version="9.9.9"),  # type: ignore[arg-type]
    )
    assert verify_chain(tampered, signer=signer, artifacts=artifacts, store=store) == "TAMPERED"

    # (3) A missing SARIF artefact yields ARTIFACT_MISSING (not a re-run).
    empty_artifacts = InMemoryArtifactStore()
    assert (
        verify_chain(signed, signer=signer, artifacts=empty_artifacts, store=store)
        == "ARTIFACT_MISSING"
    )
