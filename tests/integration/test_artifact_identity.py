"""R09 additive migration and constraint falsifiers on real PostgreSQL."""

from __future__ import annotations

import itertools
import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

from analysis.artifact_identity import GRAPH_V2, SLICE_V2, ArtifactIdentity
from tests.integration.test_fnd_specs import _require_database_url, _seed_and_insert

pytestmark = pytest.mark.integration
ROOT = Path(__file__).resolve().parents[2]


def _migrate(url, direction, target, *, succeeds=True):
    result = subprocess.run(
        [sys.executable, "-m", "alembic", direction, target],
        cwd=ROOT,
        env={**os.environ, "SCANIPY_DATABASE_URL": url},
        capture_output=True,
        text=True,
        check=False,
    )
    assert (result.returncode == 0) is succeeds, result.stderr
    return result


def _v2(graph_class="strong", slice_class="weak"):
    return {
        "identity_schema_version": 2,
        "fingerprint_class": None,
        "cpg_order_class": graph_class,
        "slice_fingerprint_class": slice_class,
        "cpg_order_status": "completed",
        "slice_status": "completed",
        "cpg_order_namespace": GRAPH_V2,
        "slice_namespace": SLICE_V2,
    }


def _insert_copy(cur, old_id, overrides):
    from psycopg2.extras import Json

    cur.execute(
        """
        INSERT INTO findings
        SELECT (jsonb_populate_record(NULL::findings,
          to_jsonb(f) || %s::jsonb)).* FROM findings f WHERE id = %s
    """,
        (Json({"id": str(uuid.uuid4()), **overrides}), old_id),
    )


def test_additive_migration_preserves_history_and_enforces_independent_evidence():
    import psycopg2
    from psycopg2.extras import Json

    url = _require_database_url("R09 migration/history/independent-class falsifiers")
    _migrate(url, "upgrade", "20260524_0002")
    conn = psycopg2.connect(url)
    old_id = str(uuid.uuid4())
    finding_ids = []
    record_ids = []
    try:
        with conn.cursor() as cur:
            _seed_and_insert(cur, {"id": old_id})
            # Store recognizable signed-history bytes using the same real FK chain.
            cur.execute(
                """
                INSERT INTO provenance_records (
                  id, record_type, org_id, codebase_id, commit_sha, scm_provider,
                  scan_id, finding_id, snapshot_id, snapshot_digest, precondition_status,
                  "S_version", env_digest, cpg_order_hash, fingerprint_class, slice_fingerprint,
                  origin, determinism_partition, kms_key_arn, kms_key_version,
                  signature, signature_alg, claim_label
                ) SELECT id, 'chain', org_id, codebase_id, commit_sha, 'github', scan_id,
                  id, snapshot_id, env_digest, precondition_status, "S_version", env_digest,
                  cpg_order_hash, fingerprint_class, slice_fingerprint, origin,
                  determinism_partition, 'test-key', 'original-key-version', %s,
                  'RSASSA_PSS_SHA_256', 'CONDITIONAL_THEOREM'
                FROM findings WHERE id = %s
            """,
                (b"original-signature-input-history", old_id),
            )
        conn.commit()
        _migrate(url, "upgrade", "head")
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT identity_schema_version, fingerprint_class, cpg_order_class,
                  slice_fingerprint_class, cpg_order_status, slice_status,
                  encode(cpg_order_hash, 'hex'), encode(slice_fingerprint, 'hex')
                FROM findings WHERE id = %s
            """,
                (old_id,),
            )
            assert cur.fetchone() == (
                1,
                "strong",
                None,
                None,
                "legacy-ambiguous",
                "legacy-ambiguous",
                "00" * 32,
                "01" * 32,
            )
            cur.execute(
                """
                SELECT record_schema_version, artifact_identity, signature, kms_key_version,
                  fingerprint_class FROM provenance_records WHERE id = %s
            """,
                (old_id,),
            )
            history = cur.fetchone()
            assert history[:2] == (1, None)
            assert bytes(history[2]) == b"original-signature-input-history"
            assert history[3:] == ("original-key-version", "strong")

            for graph_class, slice_class in itertools.product(("strong", "weak"), repeat=2):
                row_id = str(uuid.uuid4())
                finding_ids.append(row_id)
                _insert_copy(cur, old_id, {**_v2(graph_class, slice_class), "id": row_id})
                cur.execute(
                    "SELECT cpg_order_class, slice_fingerprint_class FROM findings WHERE id = %s",
                    (row_id,),
                )
                assert cur.fetchone() == (graph_class, slice_class)

            oracle = {
                **_v2(),
                "origin": "oracle-passthrough",
                "determinism_partition": "oracle-passthrough",
                "engine": "semgrep",
                "cpg_order_hash": None,
                "slice_fingerprint": None,
                "cpg_order_class": None,
                "slice_fingerprint_class": None,
                "cpg_order_namespace": None,
                "slice_namespace": None,
                "cpg_order_status": "not-applicable",
                "slice_status": "not-applicable",
                "precondition_status": None,
            }
            oracle_id = str(uuid.uuid4())
            finding_ids.append(oracle_id)
            _insert_copy(cur, old_id, {**oracle, "id": oracle_id})

            for bad in (
                {**_v2(), "slice_fingerprint_class": None},
                {**_v2(), "cpg_order_namespace": ""},
                {**oracle, "origin": "deterministic-core"},
                {**_v2(), "slice_status": "failed"},
                {"cpg_order_class": "strong"},  # never infer a v1 class
                {**_v2(), "precondition_status": None},
            ):
                cur.execute("SAVEPOINT invalid_finding")
                with pytest.raises(psycopg2.IntegrityError) as exc:
                    _insert_copy(cur, old_id, bad)
                assert exc.value.pgcode == "23514"
                cur.execute("ROLLBACK TO SAVEPOINT invalid_finding")

            metadata = {
                "schema_version": 2,
                "cpg_order": ArtifactIdentity("completed", "00" * 32, "strong", GRAPH_V2).to_dict(),
                "slice": ArtifactIdentity("completed", "01" * 32, "weak", SLICE_V2).to_dict(),
            }
            # Cloning a signed v1 row into a new envelope is only test data here;
            # production appends a newly signed v2 record, never edits old bytes.
            record_id = str(uuid.uuid4())
            record_ids.append(record_id)
            cur.execute(
                """
                INSERT INTO provenance_records
                SELECT (jsonb_populate_record(NULL::provenance_records,
                  to_jsonb(p) || %s::jsonb)).* FROM provenance_records p WHERE id = %s
            """,
                (
                    Json(
                        {
                            "id": record_id,
                            "record_schema_version": 2,
                            "fingerprint_class": None,
                            "artifact_identity": metadata,
                        }
                    ),
                    old_id,
                ),
            )
            for malformed in ({}, {"schema_version": 2}, {**metadata, "slice": {}}):
                cur.execute("SAVEPOINT invalid_provenance")
                with pytest.raises(psycopg2.IntegrityError) as exc:
                    cur.execute(
                        """
                        INSERT INTO provenance_records
                        SELECT (jsonb_populate_record(NULL::provenance_records,
                          to_jsonb(p) || %s::jsonb)).* FROM provenance_records p WHERE id = %s
                    """,
                        (
                            Json(
                                {
                                    "id": str(uuid.uuid4()),
                                    "record_schema_version": 2,
                                    "fingerprint_class": None,
                                    "artifact_identity": malformed,
                                }
                            ),
                            old_id,
                        ),
                    )
                assert exc.value.pgcode == "23514"
                cur.execute("ROLLBACK TO SAVEPOINT invalid_provenance")
            oracle_record_id = str(uuid.uuid4())
            record_ids.append(oracle_record_id)
            cur.execute(
                """
                INSERT INTO provenance_records
                SELECT (jsonb_populate_record(NULL::provenance_records,
                  to_jsonb(p) || %s::jsonb)).* FROM provenance_records p WHERE id = %s
            """,
                (
                    Json(
                        {
                            "id": oracle_record_id,
                            "record_schema_version": 2,
                            "origin": "oracle-passthrough",
                            "determinism_partition": "oracle-passthrough",
                            "claim_label": "EMPIRICAL",
                            "precondition_status": None,
                            "cpg_order_hash": None,
                            "slice_fingerprint": None,
                            "fingerprint_class": None,
                            "artifact_identity": {
                                "schema_version": 2,
                                "cpg_order": ArtifactIdentity("not-applicable").to_dict(),
                                "slice": ArtifactIdentity("not-applicable").to_dict(),
                            },
                        }
                    ),
                    old_id,
                ),
            )
        conn.commit()
        refused = _migrate(url, "downgrade", "20260524_0002", succeeds=False)
        assert "cannot downgrade while v2 artifact records exist" in refused.stderr
    finally:
        conn.rollback()
        # All rows belong to this disposable test database. Remove only v2 rows
        # created by this test, allowing ordinary test-schema teardown afterward.
        with conn.cursor() as cur:
            cur.execute("DELETE FROM provenance_records WHERE id = ANY(%s::uuid[])", (record_ids,))
            cur.execute("DELETE FROM findings WHERE id = ANY(%s::uuid[])", (finding_ids,))
        conn.commit()
        conn.close()
        _migrate(url, "downgrade", "base")
