"""Real isolated PostgreSQL function fence, durability and concurrency tests."""

from __future__ import annotations

import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Barrier
from uuid import UUID, uuid4

import psycopg2
import pytest
from psycopg2 import sql

from services.scan.occurrence_store.codec import decode_envelope, encode_envelope
from services.scan.occurrence_store.models import DetectionBatch, RawObservation
from tests.occurrence_store_fixtures import (
    attempt_policy,
    attempt_result,
    batch,
    capture_seal,
    envelope,
    invocation,
    request_input,
)

pytest_plugins = ["tests.occurrence_store_postgres"]

pytestmark = pytest.mark.integration


def start(pg, **options):
    org, codebase = pg.scope()
    requested = request_input(org, codebase, **options)
    with pg.repo("request", org) as repo:
        handle = repo.create_request(requested)
    with pg.repo("detector", org) as repo:
        claim = repo.claim(
            "capture_detection",
            attempt_policy(lease=options.get("lease", 300)),
            handle.work_item_id,
        )
        assert claim is not None
        captured = capture_seal(handle.request_id, requested)
        seal = repo.register_capture_and_seal(claim.fence, captured)
    return org, requested, handle, claim, seal


def retain(pg, org, claim, *, index=0, ordinal=0, count=1, failed=False, location=None):
    with pg.repo("detector", org) as repo:
        run = repo.begin_detector_run(claim.fence, invocation(index, ordinal))
        run_id = UUID(run["run_id"])
        observed = batch(run_id, count=count, failed=failed, location=location)
        retained = repo.retain_detection_batch(claim.fence, run_id, observed)
    return run_id, observed, retained


def stages(pg, request):
    return pg.rows(
        (
            "SELECT "
            "capture_state,detection_state,identity_state,finalization_state,lifecycle_state "
            "FROM scanipy_execution.scan_requests WHERE id=%s"
        ),
        (str(request),),
    )[0]


def failed_run(pg, org, claim, *, index=0, ordinal=0):
    raw = b"actual controlled failure\x00\xff"
    evidence = envelope(
        "run-failure",
        code="controlled",
        message="observed failure",
        prefix_sha256=hashlib.sha256(raw).hexdigest(),
        observed_byte_count=len(raw),
        truncated=False,
        observed_full_sha256=hashlib.sha256(raw).hexdigest(),
    )
    with pg.repo("detector", org) as repo:
        run = UUID(repo.begin_detector_run(claim.fence, invocation(index, ordinal))["run_id"])
        repo.fail_detector_run(claim.fence, run, evidence, raw)
    return run, evidence, raw


@pytest.mark.parametrize("field", ["argv", "cwd"])
@pytest.mark.parametrize("partial", [False, True])
def test_direct_sql_invocation_mismatch_rolls_back_then_exact_batch_replays(
    occurrence_pg, field, partial
):
    pg = occurrence_pg
    org, _, handle, claim, _ = start(pg)
    requested = invocation()
    with pg.repo("detector", org) as repo:
        run = UUID(repo.begin_detector_run(claim.fence, requested)["run_id"])
    observed = batch(run, failed=partial)
    value = observed.envelope.value
    value["actual_invocation"][field] = (
        list(reversed(value["actual_invocation"][field]))
        if field == "argv"
        else "unexpected-actual-workdir"
    )
    different = encode_envelope("detection-batch", value)
    with (
        pytest.raises(psycopg2.Error, match="actual invocation differs"),
        pg.repo("detector", org) as repo,
    ):
        cursor = repo.connection.cursor()
        try:
            cursor.execute(
                (
                    "SELECT scanipy_execution.retain_detection_batch_v1(%s,%s,%s,%s,%s,"
                    "%s,%s,%s,%s,%s,%s,%s)"
                ),
                (
                    str(org),
                    str(claim.fence.work_item_id),
                    str(claim.fence.attempt_id),
                    claim.fence.token,
                    claim.fence.revision,
                    str(run),
                    different.data,
                    different.digest,
                    observed.stdout,
                    observed.stderr,
                    [row.result for row in observed.observations],
                    [row.witness for row in observed.observations],
                ),
            )
        finally:
            cursor.close()
    assert pg.rows(
        "SELECT count(*) FROM scanipy_execution.detection_occurrences WHERE request_id=%s",
        (str(handle.request_id),),
    ) == [(0,)]
    assert pg.rows(
        "SELECT count(*) FROM scanipy_execution.work_items WHERE request_id=%s AND kind='identity'",
        (str(handle.request_id),),
    ) == [(0,)]
    state, result, stored_input = pg.rows(
        "SELECT state,result_bytes,input_bytes FROM scanipy_execution.detector_runs WHERE id=%s",
        (str(run),),
    )[0]
    assert state == "running" and result is None
    assert bytes(stored_input) == requested.data
    with pg.repo("detector", org) as repo:
        retained = repo.retain_detection_batch(claim.fence, run, observed)
        assert not retained.replayed and len(retained.occurrence_ids) == 1
        assert repo.retain_detection_batch(claim.fence, run, observed).replayed
    stored = pg.rows(
        "SELECT result_bytes FROM scanipy_execution.detector_runs WHERE id=%s", (str(run),)
    )[0][0]
    assert bytes(stored) == observed.envelope.data


def test_atomic_request_seal_batch_and_completed_projection(occurrence_pg):
    pg = occurrence_pg
    assert pg.round_trip_verified
    org, requested, handle, claim, _sealed = start(pg)
    with pg.repo("request", org) as repo:
        assert repo.create_request(requested).replayed
    run, observed, retained = retain(pg, org, claim, count=2)
    assert len(set(retained.occurrence_ids)) == len(set(retained.identity_work_ids)) == 2
    with pg.repo("detector", org) as repo:
        assert repo.retain_detection_batch(claim.fence, run, observed).replayed
        result = repo.finish(claim.fence, attempt_result(runs=(run,)))
        assert result["work_state"] == "completed"
    assert stages(pg, handle.request_id) == (
        "completed",
        "completed",
        "pending",
        "pending",
        "pending",
    )
    for work in retained.identity_work_ids:
        with pg.repo("identity", org) as repo:
            identity = repo.claim("identity", attempt_policy(), work)
            repo.finish(identity.fence, attempt_result(graph="strong", sliced="weak"))
    assert stages(pg, handle.request_id) == (
        "completed",
        "completed",
        "completed",
        "pending",
        "pending",
    )
    rows = pg.rows(
        (
            "SELECT "
            "raw_result_bytes,witness_bytes,origin,env_digest,full_env_digest "
            "FROM scanipy_execution.detection_occurrences WHERE request_id=%s "
            "ORDER BY tool_ordinal"
        ),
        (str(handle.request_id),),
    )
    assert bytes(rows[0][0]) == bytes(rows[1][0]) == observed.observations[0].result
    assert bytes(rows[0][1]) == observed.observations[0].witness
    assert rows[0][2] == "deterministic-core" and rows[0][4] is None
    assert pg.rows(
        "SELECT count(*) FROM public.findings WHERE codebase_id=%s",
        (requested.request.value["codebase_id"],),
    ) == [(0,)]


@pytest.mark.parametrize(
    "graph,sliced", [("strong", "strong"), ("strong", "weak"), ("weak", "strong"), ("weak", "weak")]
)
def test_identity_classes_remain_independent(occurrence_pg, graph, sliced):
    pg = occurrence_pg
    org, _, _, claim, _ = start(pg)
    _, _, kept = retain(pg, org, claim)
    with pg.repo("identity", org) as repo:
        identity = repo.claim("identity", attempt_policy(), kept.identity_work_ids[0])
        result = attempt_result(graph=graph, sliced=sliced)
        repo.finish(identity.fence, result)
    stored = bytes(
        pg.rows(
            "SELECT result_bytes FROM scanipy_execution.work_attempts WHERE id=%s",
            (str(identity.fence.attempt_id),),
        )[0][0]
    )
    value = decode_envelope("attempt-result", stored)
    assert value["identity"]["cpg_order"]["fingerprint_class"] == graph
    assert value["identity"]["slice"]["fingerprint_class"] == sliced


def test_failed_slice_does_not_lose_original_detection(occurrence_pg):
    pg = occurrence_pg
    org, _, handle, claim, _ = start(pg, bindings=2)
    _, _, kept = retain(pg, org, claim)
    with pg.repo("identity", org) as repo:
        identity = repo.claim("identity", attempt_policy(), kept.identity_work_ids[0])
        repo.finish(identity.fence, attempt_result(failed=True, graph="strong", sliced="failed"))
    _, _, second = retain(pg, org, claim, index=1)
    with pg.repo("identity", org) as repo:
        active = repo.claim("identity", attempt_policy(), second.identity_work_ids[0])
        assert active is not None
    assert stages(pg, handle.request_id)[2] == "failed"
    assert pg.rows(
        (
            "SELECT count(*),min(origin) FROM "
            "scanipy_execution.detection_occurrences WHERE request_id=%s"
        ),
        (str(handle.request_id),),
    ) == [(2, "deterministic-core")]


def test_partial_detection_failure_survives_identity_completion(occurrence_pg):
    pg = occurrence_pg
    org, _, handle, claim, _ = start(pg)
    run, _, kept = retain(pg, org, claim, failed=True)
    with pg.repo("identity", org) as repo:
        identity = repo.claim("identity", attempt_policy(), kept.identity_work_ids[0])
        repo.finish(identity.fence, attempt_result(graph="strong", sliced="strong"))
    assert stages(pg, handle.request_id)[1:3] == ("failed", "completed")
    with pytest.raises(psycopg2.Error), pg.repo("detector", org) as repo:
        repo.finish(claim.fence, attempt_result(runs=(run,)))
    with pg.repo("detector", org) as repo:
        settled = repo.finish(claim.fence, attempt_result(failed=True, retryable=True))
    assert settled["work_state"] == "failed"


def test_explicit_zero_occurrence_supersession_and_terminal_begin_rejection(occurrence_pg):
    pg = occurrence_pg
    org, _, handle, claim, _ = start(pg)
    previous, evidence, raw = failed_run(pg, org, claim)
    with pytest.raises(psycopg2.Error, match="terminal failed"), pg.repo("detector", org) as repo:
        repo.begin_detector_run(claim.fence, invocation())
    with pg.repo("detector", org) as repo:
        assert repo.fail_detector_run(claim.fence, previous, evidence, raw)["replayed"]
        next_run = UUID(repo.begin_detector_run(claim.fence, invocation(ordinal=1))["run_id"])
    assert stages(pg, handle.request_id)[1] == "failed"
    assert pg.rows(
        "SELECT supersedes_run_id FROM scanipy_execution.detector_runs WHERE id=%s",
        (str(next_run),),
    ) == [(str(previous),)]
    with pg.repo("detector", org) as repo:
        repo.retain_detection_batch(claim.fence, next_run, batch(next_run, count=0))
        repo.finish(claim.fence, attempt_result(runs=(next_run,)))
    assert stages(pg, handle.request_id) == (
        "completed",
        "completed",
        "completed",
        "pending",
        "pending",
    )


def test_supersession_follows_unique_history_leaf_not_caller_ordinals(occurrence_pg):
    pg = occurrence_pg
    org, _, handle, claim, _ = start(pg)
    first, _, _ = failed_run(pg, org, claim, ordinal=9)
    second, _, _ = failed_run(pg, org, claim, ordinal=4)
    final, _, _ = retain(pg, org, claim, ordinal=1, count=0)
    assert pg.rows(
        "SELECT supersedes_run_id FROM scanipy_execution.detector_runs WHERE id=%s", (str(second),)
    ) == [(str(first),)]
    assert pg.rows(
        "SELECT supersedes_run_id FROM scanipy_execution.detector_runs WHERE id=%s", (str(final),)
    ) == [(str(second),)]
    with pg.repo("detector", org) as repo:
        repo.finish(claim.fence, attempt_result(runs=(final,)))
    assert stages(pg, handle.request_id)[1] == "completed"


@pytest.mark.parametrize("prior_failure", [False, True])
def test_cancellation_is_distinct_without_hiding_prior_failure(occurrence_pg, prior_failure):
    pg = occurrence_pg
    org, _, handle, claim, _ = start(pg)
    if prior_failure:
        failed_run(pg, org, claim)
    with pg.repo("detector", org) as repo:
        repo.begin_detector_run(claim.fence, invocation(ordinal=1 if prior_failure else 0))
    revision = pg.rows(
        "SELECT revision FROM scanipy_execution.scan_requests WHERE id=%s",
        (str(handle.request_id),),
    )[0][0]
    cancellation = envelope(
        "cancellation", request_id=str(handle.request_id), reason="controlled cancellation"
    )
    with pg.repo("request", org) as repo:
        result = repo.cancel_request(handle.request_id, revision, cancellation)
        assert repo.cancel_request(handle.request_id, revision, cancellation)["replayed"]
    assert result["revision"] > revision
    assert stages(pg, handle.request_id)[1] == ("failed" if prior_failure else "cancelled")
    with pg.repo("detector", org) as repo:
        assert repo.claim("capture_detection", attempt_policy(), handle.work_item_id) is None


def test_batch_fault_rolls_back_occurrences_and_identity_scheduling(occurrence_pg):
    pg = occurrence_pg
    org, _, handle, claim, _ = start(pg)
    with pg.repo("detector", org) as repo:
        run = UUID(repo.begin_detector_run(claim.fence, invocation())["run_id"])
    observed = batch(run, count=2)
    with pytest.raises(RuntimeError, match="injected"), pg.repo("detector", org) as repo:
        repo.retain_detection_batch(claim.fence, run, observed)
        raise RuntimeError("injected before transaction commit")
    assert pg.rows(
        "SELECT count(*) FROM scanipy_execution.detection_occurrences WHERE request_id=%s",
        (str(handle.request_id),),
    ) == [(0,)]
    assert pg.rows(
        "SELECT count(*) FROM scanipy_execution.work_items WHERE request_id=%s AND kind='identity'",
        (str(handle.request_id),),
    ) == [(0,)]
    with pg.repo("detector", org) as repo:
        assert not repo.retain_detection_batch(claim.fence, run, observed).replayed


@pytest.mark.parametrize("field", ["tool_identity", "code_identity", "detector_env_digest"])
def test_mismatching_actual_pins_cannot_certify_batch(occurrence_pg, field):
    pg = occurrence_pg
    org, _, handle, claim, _ = start(pg)
    with pg.repo("detector", org) as repo:
        run = UUID(repo.begin_detector_run(claim.fence, invocation())["run_id"])
    observed = batch(run)
    value = observed.envelope.value
    if field.endswith("identity"):
        value[field]["artifact_digest"] = "b" * 64
    else:
        value[field] = "sha256:" + "b" * 64
    altered = replace(observed, envelope=encode_envelope("detection-batch", value))
    with pytest.raises(psycopg2.Error, match="artifact pins"), pg.repo("detector", org) as repo:
        repo.retain_detection_batch(claim.fence, run, altered)
    assert pg.rows(
        "SELECT count(*) FROM scanipy_execution.detection_occurrences WHERE request_id=%s",
        (str(handle.request_id),),
    ) == [(0,)]


@pytest.mark.parametrize("role", ["request", "detector", "identity", "cleanup", "read"])
def test_real_restricted_principals_cannot_mutate_tables_or_private_helpers(occurrence_pg, role):
    pg = occurrence_pg
    with pg.connection(role) as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT rolsuper,rolbypassrls,rolcreaterole,rolcreatedb FROM "
            "pg_roles WHERE rolname=current_user"
        )
        assert cursor.fetchone() == (False, False, False, False)
    for query in (
        "INSERT INTO scanipy_execution.scan_requests DEFAULT VALUES",
        "DELETE FROM scanipy_execution.scan_requests",
        "UPDATE scanipy_execution.scan_requests SET revision=revision+1",
        "TRUNCATE scanipy_execution.scan_requests",
        "SELECT scanipy_execution.v1_stages(gen_random_uuid())",
        "CREATE TABLE scanipy_execution.forbidden(id integer)",
        "SET ROLE scanipy_exec_owner",
    ):
        with (
            pytest.raises(psycopg2.errors.InsufficientPrivilege),
            pg.connection(role) as connection,
            connection.cursor() as cursor,
        ):
            cursor.execute(query)


@pytest.mark.parametrize("role", ["request", "detector", "identity", "cleanup", "read"])
def test_references_privilege_is_denied_independently_of_schema_create(occurrence_pg, role):
    pg = occurrence_pg
    namespace = "occurrence_reference_" + uuid4().hex
    with pg.admin() as admin, admin.cursor() as cursor:
        cursor.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(namespace)))
        cursor.execute(
            sql.SQL("GRANT USAGE,CREATE ON SCHEMA {} TO {}").format(
                sql.Identifier(namespace), sql.Identifier(pg.roles[role][0])
            )
        )
        admin.commit()
        try:
            with (
                pytest.raises(psycopg2.errors.InsufficientPrivilege),
                pg.connection(role) as connection,
                connection.cursor() as restricted,
            ):
                restricted.execute(
                    sql.SQL(
                        "CREATE TABLE {}.ref(id uuid REFERENCES "
                        "scanipy_execution.scan_requests(id))"
                    ).format(sql.Identifier(namespace))
                )
        finally:
            cursor.execute(sql.SQL("DROP SCHEMA {}").format(sql.Identifier(namespace)))
            admin.commit()


def test_hostile_default_acls_do_not_leak_into_new_namespace(occurrence_pg):
    pg = occurrence_pg
    for principal in (pg.hostile, "public"):
        rows = pg.rows(
            (
                "SELECT c.relname,ac.privilege_type FROM pg_class c JOIN "
                "pg_namespace n ON n.oid=c.relnamespace CROSS JOIN LATERAL "
                "aclexplode(c.relacl) ac WHERE n.nspname='scanipy_execution' AND "
                "ac.grantee=CASE WHEN %s='public' THEN 0 ELSE (SELECT oid FROM "
                "pg_roles WHERE rolname=%s) END"
            ),
            (principal, principal),
        )
        assert rows == []
        rows = pg.rows(
            (
                "SELECT p.proname FROM pg_proc p JOIN pg_namespace n ON "
                "n.oid=p.pronamespace CROSS JOIN LATERAL aclexplode(p.proacl) ac "
                "WHERE n.nspname='scanipy_execution' AND ac.grantee=CASE WHEN "
                "%s='public' THEN 0 ELSE (SELECT oid FROM pg_roles WHERE "
                "rolname=%s) END"
            ),
            (principal, principal),
        )
        assert rows == []


def test_tenant_binding_and_pooled_transaction_reset(occurrence_pg):
    pg = occurrence_pg
    org, _, handle, _, _ = start(pg)
    other, _ = pg.scope()
    with pg.connection("read") as connection, connection.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM scanipy_execution.scan_requests")
        assert cursor.fetchone() == (0,)
        cursor.execute("SELECT set_config('app.org_id',%s,true)", (str(org),))
        cursor.execute("SELECT id FROM scanipy_execution.scan_requests")
        assert cursor.fetchall() == [(str(handle.request_id),)]
        connection.commit()
        cursor.execute("SELECT count(*) FROM scanipy_execution.scan_requests")
        assert cursor.fetchone() == (0,)
        cursor.execute("SELECT set_config('app.org_id',%s,true)", (str(other),))
        cursor.execute("SELECT count(*) FROM scanipy_execution.scan_requests")
        assert cursor.fetchone() == (0,)


def test_concurrent_idempotent_request_and_single_claim(occurrence_pg):
    pg = occurrence_pg
    org, codebase = pg.scope()
    requested = request_input(org, codebase)
    barrier = Barrier(2)

    def create():
        barrier.wait(timeout=5)
        with pg.repo("request", org) as repo:
            return repo.create_request(requested)

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: create(), range(2)))
    assert results[0].request_id == results[1].request_id
    assert sorted(row.replayed for row in results) == [False, True]

    def claim():
        barrier.wait(timeout=5)
        with pg.repo("detector", org) as repo:
            return repo.claim("capture_detection", attempt_policy(), results[0].work_item_id)

    with ThreadPoolExecutor(max_workers=2) as executor:
        claims = list(executor.map(lambda _: claim(), range(2)))
    assert sum(item is not None for item in claims) == 1


@pytest.mark.parametrize(
    "token", [b'"\\u0000"', b'"\\ud800"', b'"\\udfff"', b"9223372036854775808", b"9" * 5000]
)
def test_direct_sql_rejects_nonportable_before_jsonb(occurrence_pg, token):
    data = b'{"files":[],"schema":' + token + b"}"
    digest = hashlib.sha256(b"scanipy-execution/source-inventory/1\n" + data).digest()
    with (
        pytest.raises(psycopg2.Error),
        occurrence_pg.admin() as connection,
        connection.cursor() as cursor,
    ):
        cursor.execute(
            "SELECT scanipy_execution.v1_envelope('source-inventory',%s,%s)", (data, digest)
        )


@pytest.mark.parametrize("nested", [False, True])
def test_near_limit_unknown_fields_rejected_under_bounded_deadline(occurrence_pg, nested):
    value = {"k" + str(index).zfill(5): 0 for index in range(90000)}
    if nested:
        value = {
            "files": [{"path": value, "sha256": "a" * 64, "size": 0}],
            "schema": "scanipy-execution/source-inventory/1",
        }
    else:
        value.update({"files": [], "schema": "scanipy-execution/source-inventory/1"})
    data = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    assert len(data) < 1048576
    digest = hashlib.sha256(b"scanipy-execution/source-inventory/1\n" + data).digest()
    with (
        pytest.raises(psycopg2.errors.InvalidParameterValue),
        occurrence_pg.admin() as connection,
        connection.cursor() as cursor,
    ):
        cursor.execute("SET LOCAL statement_timeout='3000ms'")
        cursor.execute(
            "SELECT scanipy_execution.v1_envelope('source-inventory',%s,%s)", (data, digest)
        )


def test_resume_reuses_completed_binding_without_duplicate_observations(occurrence_pg):
    pg = occurrence_pg
    org, _requested, handle, claim, _sealed = start(pg, bindings=2)
    run, observed, kept = retain(pg, org, claim)
    failure = attempt_result(failed=True, retryable=True)
    with pg.repo("detector", org) as repo:
        assert repo.finish(claim.fence, failure)["work_state"] == "pending"
    with pg.repo("detector", org) as repo:
        second = repo.claim("capture_detection", attempt_policy(), handle.work_item_id)
        resumed = repo.begin_detector_run(second.fence, invocation())
        assert resumed["completed"] and resumed["run_id"] == str(run)
        assert resumed["occurrence_ids"] == [str(value) for value in kept.occurrence_ids]
        assert repo.finish(claim.fence, failure)["replayed"]
        assert repo.retain_detection_batch(claim.fence, run, observed).replayed
    other, _, _ = retain(pg, org, second, index=1)
    with pg.repo("detector", org) as repo:
        repo.finish(second.fence, attempt_result(runs=(run, other)))
    assert stages(pg, handle.request_id)[1] == "completed"
    assert pg.rows(
        ("SELECT count(*) FROM scanipy_execution.scan_seals WHERE request_id=%s"),
        (str(handle.request_id),),
    ) == [(1,)]
    assert pg.rows(
        ("SELECT count(*) FROM scanipy_execution.detection_occurrences WHERE request_id=%s"),
        (str(handle.request_id),),
    ) == [(2,)]


def test_lease_expiry_fencing_retry_budget_and_terminal_replay(occurrence_pg):
    pg = occurrence_pg
    org, _, handle, claim, _ = start(pg, lease=1, max_attempts=2)
    time.sleep(1.05)
    with pytest.raises(psycopg2.Error, match="expired"), pg.repo("detector", org) as repo:
        repo.begin_detector_run(claim.fence, invocation())
    failure = attempt_result(failed=True, retryable=True)
    with pg.repo("detector", org) as repo:
        assert repo.expire(claim.fence, failure)["work_state"] == "pending"
        second = repo.claim("capture_detection", attempt_policy(lease=1), handle.work_item_id)
        assert second.fence.token == claim.fence.token + 1
        assert repo.expire(claim.fence, failure)["replayed"]
    with pytest.raises(psycopg2.Error), pg.repo("detector", org) as repo:
        repo.renew(claim.fence)
    with pg.repo("detector", org) as repo:
        assert repo.finish(second.fence, failure)["work_state"] == "failed"
        assert repo.claim("capture_detection", attempt_policy(lease=1), handle.work_item_id) is None


def test_fresh_clock_after_lock_wait_rejects_expired_writer(occurrence_pg):
    pg = occurrence_pg
    org, _, handle, claim, _ = start(pg, lease=1)
    # Hold the first protocol lock while the writer waits, then release only
    # after the real database lease expires. No persisted clock is rewritten.
    with pg.admin() as blocker, blocker.cursor() as cursor:
        cursor.execute(
            ("SELECT id FROM scanipy_execution.scan_requests WHERE id=%s FOR UPDATE"),
            (str(handle.request_id),),
        )

        def renew():
            with pg.repo("detector", org) as repo:
                return repo.renew(claim.fence)

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(renew)
            time.sleep(1.05)
            blocker.commit()
            with pytest.raises(psycopg2.Error, match="expired"):
                future.result(timeout=5)


def test_renewal_advances_revision_and_old_fence_fails(occurrence_pg):
    pg = occurrence_pg
    org, _, _, claim, _ = start(pg)
    with pg.repo("detector", org) as repo:
        renewed = repo.renew(claim.fence)
        assert renewed.revision == claim.fence.revision + 1
        assert repo.acquire_capture_lease(renewed)["replayed"]
        renewed_again = repo.renew_capture_lease(renewed)
    with pytest.raises(psycopg2.Error), pg.repo("detector", org) as repo:
        repo.begin_detector_run(claim.fence, invocation())
    with pg.repo("detector", org) as repo:
        repo.finish(renewed_again, attempt_result(failed=True))


def test_retirement_blocks_pending_identity_then_is_irreversible(occurrence_pg):
    pg = occurrence_pg
    org, _, handle, claim, sealed = start(pg)
    run, _, kept = retain(pg, org, claim)
    capture_id = UUID(sealed["capture_id"])
    with pg.repo("detector", org) as repo:
        repo.finish(claim.fence, attempt_result(runs=(run,)))
    with pytest.raises(psycopg2.Error, match="nonterminal"), pg.repo("cleanup", org) as repo:
        repo.claim_retirement(capture_id, 0)
    with pg.repo("identity", org) as repo:
        identity = repo.claim("identity", attempt_policy(), kept.identity_work_ids[0])
        repo.finish(identity.fence, attempt_result(failed=True))
    with pg.repo("cleanup", org) as repo:
        cleanup = repo.claim_retirement(capture_id, 0)
    assert cleanup["fencing_token"] == 1
    evidence = envelope(
        "retirement",
        capture_id=str(capture_id),
        storage_object_id=cleanup["storage_object_id"],
        token=1,
        reason="controlled object backend deletion acknowledgement",
        evidence_digest=hashlib.sha256(b"controlled deletion evidence").hexdigest(),
    )
    with pytest.raises(psycopg2.Error), pg.repo("cleanup", org) as repo:
        repo.claim_retirement(capture_id, cleanup["revision"])
    with pg.repo("cleanup", org) as repo:
        repo.finish_retirement(capture_id, cleanup["revision"], evidence)
        assert repo.finish_retirement(capture_id, cleanup["revision"], evidence)["replayed"]
    with pytest.raises(psycopg2.Error), pg.repo("cleanup", org) as repo:
        repo.claim_retirement(capture_id, cleanup["revision"] + 1)
    assert pg.rows(
        ("SELECT count(*) FROM scanipy_execution.detection_occurrences WHERE request_id=%s"),
        (str(handle.request_id),),
    ) == [(1,)]


def test_expired_unsettled_work_still_blocks_cleanup(occurrence_pg):
    pg = occurrence_pg
    org, _, _, claim, sealed = start(pg, lease=1)
    time.sleep(1.05)
    with pytest.raises(psycopg2.Error, match="nonterminal"), pg.repo("cleanup", org) as repo:
        repo.claim_retirement(UUID(sealed["capture_id"]), 0)
    with pg.repo("detector", org) as repo:
        repo.expire(claim.fence, attempt_result(failed=True))
    with pg.repo("cleanup", org) as repo:
        assert repo.claim_retirement(UUID(sealed["capture_id"]), 0)["fencing_token"] == 1


@pytest.mark.parametrize(
    "status,path,line",
    [("unknown", None, None), ("partial", "fixture.py", None), ("partial", None, 7)],
)
def test_real_storage_preserves_unknown_and_partial_locations(occurrence_pg, status, path, line):
    pg = occurrence_pg
    org, _, _, claim, _ = start(pg)
    location = {
        "status": status,
        "path": path,
        "start_line": line,
        "start_column": None,
        "end_line": None,
        "end_column": None,
    }
    _, _, kept = retain(pg, org, claim, location=location)
    assert pg.rows(
        ("SELECT physical_location FROM scanipy_execution.detection_occurrences WHERE id=%s"),
        (str(kept.occurrence_ids[0]),),
    ) == [(location,)]


def test_explicit_oracle_identity_not_applicable_policy(occurrence_pg):
    pg = occurrence_pg
    org, _, _, claim, _ = start(pg, identity_mode="not-applicable")
    with pg.repo("detector", org) as repo:
        run = UUID(repo.begin_detector_run(claim.fence, invocation())["run_id"])
        kept = repo.retain_detection_batch(claim.fence, run, batch(run, engine="semgrep"))
    with pg.repo("identity", org) as repo:
        identity = repo.claim("identity", attempt_policy(), kept.identity_work_ids[0])
        repo.finish(identity.fence, attempt_result(not_applicable=True))
    assert pg.rows(
        (
            "SELECT origin,determinism_partition FROM "
            "scanipy_execution.detection_occurrences WHERE id=%s"
        ),
        (str(kept.occurrence_ids[0]),),
    ) == [("oracle-passthrough", "oracle-passthrough")]


def test_required_identity_and_actual_runner_pins_are_enforced(occurrence_pg):
    pg = occurrence_pg
    org, _, _, claim, _ = start(pg)
    _, _, kept = retain(pg, org, claim)
    with pg.repo("identity", org) as repo:
        identity = repo.claim("identity", attempt_policy(), kept.identity_work_ids[0])
    for value in (
        attempt_result(not_applicable=True).value,
        {**attempt_result(graph="strong", sliced="strong").value, "actual_code_digest": "a" * 64},
    ):
        with pytest.raises(psycopg2.Error), pg.repo("identity", org) as repo:
            repo.finish(identity.fence, encode_envelope("attempt-result", value))
    with pg.repo("identity", org) as repo:
        repo.finish(identity.fence, attempt_result(failed=True))


def test_scope_and_capability_confusion_are_rejected(occurrence_pg):
    pg = occurrence_pg
    org, requested, handle, claim, _ = start(pg)
    other_org, other_codebase = pg.scope()
    with pytest.raises(psycopg2.Error), pg.repo("detector", other_org) as repo:
        repo.renew(claim.fence)
    with pytest.raises(psycopg2.errors.InsufficientPrivilege), pg.repo("identity", org) as repo:
        repo.claim("capture_detection", attempt_policy(), handle.work_item_id)
    with pytest.raises(psycopg2.errors.ForeignKeyViolation), pg.repo("request", org) as repo:
        repo.create_request(request_input(org, other_codebase))
    conflicting = requested.request.value
    conflicting["source_selector"]["value"] = "different-ref"
    with pytest.raises(psycopg2.Error, match="idempotency"), pg.repo("request", org) as repo:
        repo.create_request(replace(requested, request=encode_envelope("request", conflicting)))


def test_execution_history_prevents_cascading_parent_deletion_and_rewrite(occurrence_pg):
    pg = occurrence_pg
    org, requested, handle, claim, _ = start(pg)
    run, _, kept = retain(pg, org, claim)
    for query, value in (
        ("DELETE FROM public.codebases WHERE id=%s", requested.request.value["codebase_id"]),
        (
            (
                "UPDATE scanipy_execution.detection_occurrences SET "
                "origin='oracle-passthrough' WHERE id=%s"
            ),
            str(kept.occurrence_ids[0]),
        ),
        (
            "DELETE FROM scanipy_execution.detection_occurrences WHERE id=%s",
            str(kept.occurrence_ids[0]),
        ),
        ("UPDATE scanipy_execution.detector_runs SET state='running' WHERE id=%s", str(run)),
    ):
        with pytest.raises(psycopg2.Error), pg.admin() as connection, connection.cursor() as cursor:
            cursor.execute(query, (value,))
    assert pg.rows(
        ("SELECT count(*) FROM scanipy_execution.detection_occurrences WHERE request_id=%s"),
        (str(handle.request_id),),
    ) == [(1,)]


@pytest.mark.parametrize(
    "table,column",
    [("scan_seals", "accepted_spec_bytes"), ("detection_occurrences", "raw_result_bytes")],
)
def test_zero_mutable_trigger_arguments_still_protect_all_evidence(occurrence_pg, table, column):
    pg = occurrence_pg
    org, _, handle, claim, _ = start(pg)
    retain(pg, org, claim)
    before = pg.rows(
        f"SELECT {column} FROM scanipy_execution.{table} WHERE request_id=%s",
        (str(handle.request_id),),
    )
    with (
        pytest.raises(psycopg2.Error, match="immutable execution content"),
        pg.admin() as connection,
        connection.cursor() as cursor,
    ):
        cursor.execute(
            f"UPDATE scanipy_execution.{table} SET {column}=%s WHERE request_id=%s",
            (b"altered valid bytes", str(handle.request_id)),
        )
    assert (
        pg.rows(
            f"SELECT {column} FROM scanipy_execution.{table} WHERE request_id=%s",
            (str(handle.request_id),),
        )
        == before
    )


def test_mid_function_identity_insert_fault_rolls_back_entire_batch(occurrence_pg):
    pg = occurrence_pg
    org, _, handle, claim, _ = start(pg)
    with pg.repo("detector", org) as repo:
        run = UUID(repo.begin_detector_run(claim.fence, invocation())["run_id"])
    observed = batch(run, count=2)
    # Task-private trigger fails exactly AFTER occurrence insertion but BEFORE
    # its identity item and the run inventory seal. No production seam altered.
    with pg.admin() as admin, admin.cursor() as cursor:
        cursor.execute("""CREATE FUNCTION pg_temp.occurrence_identity_fault() RETURNS trigger
            LANGUAGE plpgsql AS $$ BEGIN IF NEW.kind='identity' THEN
            RAISE EXCEPTION 'injected identity scheduling failure'; END IF; RETURN NEW; END $$""")
        cursor.execute(
            "CREATE TRIGGER occurrence_identity_fault BEFORE INSERT ON "
            "scanipy_execution.work_items FOR EACH ROW EXECUTE FUNCTION "
            "pg_temp.occurrence_identity_fault()"
        )
        admin.commit()
        try:
            with (
                pytest.raises(psycopg2.Error, match="injected identity"),
                pg.repo("detector", org) as repo,
            ):
                repo.retain_detection_batch(claim.fence, run, observed)
            assert pg.rows(
                "SELECT count(*) FROM scanipy_execution.detection_occurrences WHERE request_id=%s",
                (str(handle.request_id),),
            ) == [(0,)]
            assert pg.rows(
                "SELECT state,result_bytes FROM scanipy_execution.detector_runs WHERE id=%s",
                (str(run),),
            ) == [("running", None)]
            assert pg.rows(
                (
                    "SELECT count(*) FROM scanipy_execution.work_items WHERE "
                    "request_id=%s AND kind='identity'"
                ),
                (str(handle.request_id),),
            ) == [(0,)]
        finally:
            cursor.execute("DROP TRIGGER occurrence_identity_fault ON scanipy_execution.work_items")
            cursor.execute("DROP FUNCTION pg_temp.occurrence_identity_fault()")
            admin.commit()
    with pg.repo("detector", org) as repo:
        assert len(repo.retain_detection_batch(claim.fence, run, observed).occurrence_ids) == 2


def test_nonempty_downgrade_refuses_without_losing_history_or_security(occurrence_pg):
    pg = occurrence_pg
    org, _, handle, claim, _ = start(pg)
    retain(pg, org, claim)
    before = pg.rows(
        "SELECT request_bytes FROM scanipy_execution.scan_requests WHERE id=%s",
        (str(handle.request_id),),
    )
    result = pg.migrate("20260925_0003", action="downgrade", expect_success=False)
    assert result.returncode and "nonempty execution history" in result.stderr
    assert (
        pg.rows(
            "SELECT request_bytes FROM scanipy_execution.scan_requests WHERE id=%s",
            (str(handle.request_id),),
        )
        == before
    )
    assert pg.rows(
        "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON "
        "n.oid=c.relnamespace WHERE n.nspname='scanipy_execution' AND "
        "c.relkind='r' AND c.relrowsecurity AND c.relforcerowsecurity"
    ) == [(8,)]


def test_temporary_shadow_objects_cannot_redirect_definer_writes(occurrence_pg):
    pg = occurrence_pg
    org, codebase = pg.scope()
    with pg.repo("request", org) as repo:
        cursor = repo.connection.cursor()
        try:
            cursor.execute("CREATE TEMP TABLE scan_requests(id uuid)")
            cursor.execute("CREATE TEMP TABLE work_items(id uuid)")
            cursor.execute("SET LOCAL search_path=pg_temp,public")
            handle = repo.create_request(request_input(org, codebase))
            cursor.execute("SELECT count(*) FROM pg_temp.scan_requests")
            assert cursor.fetchone() == (0,)
        finally:
            cursor.close()
    assert pg.rows(
        "SELECT count(*) FROM scanipy_execution.scan_requests WHERE id=%s",
        (str(handle.request_id),),
    ) == [(1,)]


@pytest.mark.parametrize(
    "operation",
    [
        "finish",
        "expire",
        "renew",
        "acquire_capture_lease",
        "renew_capture_lease",
        "release_capture_lease",
    ],
)
def test_cross_kind_valid_foreign_tokens_cannot_reach_worker_functions(occurrence_pg, operation):
    pg = occurrence_pg
    org, _, _, claim, _ = start(pg)
    foreign = replace(claim.fence, kind="identity")
    arguments = ()
    if operation in ("finish", "expire"):
        arguments = (attempt_result(failed=True),)
    elif operation == "release_capture_lease":
        arguments = (
            envelope(
                "lease-release",
                attempt_id=str(foreign.attempt_id),
                token=foreign.token,
                reason="controlled",
            ),
        )
    with pytest.raises(psycopg2.Error, match="wrong kind"), pg.repo("identity", org) as repo:
        getattr(repo, operation)(foreign, *arguments)


def test_changed_terminal_payload_conflicts_even_when_status_matches(occurrence_pg):
    pg = occurrence_pg
    org, _, _, claim, _ = start(pg)
    run, observed, _ = retain(pg, org, claim)
    complete = attempt_result(runs=(run,))
    with pg.repo("detector", org) as repo:
        repo.finish(claim.fence, complete)
    changed = {**complete.value, "actual_code_digest": "b" * 64}
    with pytest.raises(psycopg2.Error, match="replay conflict"), pg.repo("detector", org) as repo:
        repo.finish(claim.fence, encode_envelope("attempt-result", changed))
    changed = observed.envelope.value
    changed["full_env_digest"] = "sha256:" + "c" * 64
    with pytest.raises(psycopg2.Error, match="replay conflict"), pg.repo("detector", org) as repo:
        repo.retain_detection_batch(
            claim.fence,
            run,
            replace(observed, envelope=encode_envelope("detection-batch", changed)),
        )


def test_retirement_consumer_race_and_late_cleaner_fence(occurrence_pg):
    pg = occurrence_pg
    org, requested, handle, claim, sealed = start(pg)
    run, _, kept = retain(pg, org, claim)
    with pg.repo("detector", org) as repo:
        repo.finish(claim.fence, attempt_result(runs=(run,)))
    barrier = Barrier(2)

    def consumer():
        barrier.wait(timeout=5)
        with pg.repo("identity", org) as repo:
            return repo.claim("identity", attempt_policy(), kept.identity_work_ids[0])

    def cleanup():
        barrier.wait(timeout=5)
        try:
            with pg.repo("cleanup", org) as repo:
                return repo.claim_retirement(UUID(sealed["capture_id"]), 0)
        except psycopg2.Error:
            return None

    with ThreadPoolExecutor(max_workers=2) as executor:
        pending_consumer, pending_cleanup = executor.submit(consumer), executor.submit(cleanup)
        identity, denied = pending_consumer.result(timeout=5), pending_cleanup.result(timeout=5)
    assert identity is not None and denied is None
    with pg.repo("identity", org) as repo:
        repo.finish(identity.fence, attempt_result(failed=True))
    capture_id = UUID(sealed["capture_id"])
    with pg.repo("cleanup", org) as repo:
        old = repo.claim_retirement(capture_id, 0)
    # Explicit test-only clock fixture: age the 300s cleanup lease, preserving
    # token/object/state. This tests fencing, not a real 300-second clock wait.
    with pg.admin() as connection, connection.cursor() as cursor:
        cursor.execute(
            (
                "UPDATE scanipy_execution.source_captures SET "
                "cleanup_expires_at=clock_timestamp()-interval '1 second',"
                "revision=revision+1 WHERE id=%s"
            ),
            (str(capture_id),),
        )
        connection.commit()
    with pg.repo("cleanup", org) as repo:
        newer = repo.claim_retirement(capture_id, old["revision"] + 1)
    assert newer["fencing_token"] == 2 and newer["storage_object_id"] == old["storage_object_id"]
    old_evidence = envelope(
        "retirement",
        capture_id=str(capture_id),
        storage_object_id=old["storage_object_id"],
        token=1,
        reason="late",
        evidence_digest="a" * 64,
    )
    with pytest.raises(psycopg2.Error, match="stale cleanup"), pg.repo("cleanup", org) as repo:
        repo.finish_retirement(capture_id, old["revision"], old_evidence)
    successor = request_input(
        org,
        UUID(requested.request.value["codebase_id"]),
        predecessor=handle.request_id,
        lineage=UUID(requested.request.value["lineage_id"]),
    )
    with pg.repo("request", org) as repo:
        successor_handle = repo.create_request(successor)
    with pg.repo("detector", org) as repo:
        successor_claim = repo.claim(
            "capture_detection", attempt_policy(), successor_handle.work_item_id
        )
        successor_seal = repo.register_capture_and_seal(
            successor_claim.fence, capture_seal(successor_handle.request_id, successor)
        )
    assert successor_seal["capture_id"] != str(capture_id)
    assert pg.rows(
        "SELECT retention_state FROM scanipy_execution.source_captures WHERE id=%s",
        (successor_seal["capture_id"],),
    ) == [("active",)]


def test_legacy_triage_write_still_works_without_new_execution_authority(occurrence_pg):
    pg = occurrence_pg
    org = UUID(
        pg.rows("SELECT org_id FROM public.findings WHERE id=%s", (pg.legacy_finding,))[0][0]
    )
    with pg.repo("legacy_triage", org) as repo:
        cursor = repo.connection.cursor()
        try:
            cursor.execute(
                (
                    "INSERT INTO public.triage_scores(org_id,finding_id,triage_score,"
                    'triage_reason,model_id,model_version,"S_version",env_digest) '
                    "VALUES(%s,%s,0.5,%s,%s,%s,%s,%s)"
                ),
                (
                    str(org),
                    pg.legacy_finding,
                    "controlled prior surface",
                    "controlled",
                    "1",
                    "1.0.0",
                    "sha256:" + "a" * 64,
                ),
            )
        finally:
            cursor.close()
    with (
        pytest.raises(psycopg2.errors.InsufficientPrivilege),
        pg.connection("legacy_triage") as connection,
        connection.cursor() as cursor,
    ):
        cursor.execute("SELECT * FROM scanipy_execution.scan_requests")


def test_seal_is_independent_of_mutable_legacy_registry_and_changed_replay_fails(occurrence_pg):
    pg = occurrence_pg
    org, requested, handle, claim, _ = start(pg)
    with pg.admin() as connection, connection.cursor() as cursor:
        cursor.execute(
            (
                'INSERT INTO public.spec_versions(org_id,"S_version",scope,'
                "spec_set,spec_provenance) VALUES(%s,%s,%s,%s,%s)"
            ),
            (str(org), "1.0.0", "customer", '{"controlled":"old"}', "customer"),
        )
        connection.commit()
    original = pg.rows(
        (
            "SELECT seal_bytes,accepted_spec_bytes,accepted_detector_bytes,"
            "accepted_rule_bytes FROM scanipy_execution.scan_seals WHERE "
            "request_id=%s"
        ),
        (str(handle.request_id),),
    )
    with pg.admin() as connection, connection.cursor() as cursor:
        cursor.execute(
            "UPDATE public.spec_versions SET spec_set=%s WHERE org_id=%s",
            ('{"controlled":"new"}', str(org)),
        )
        connection.commit()
    assert (
        pg.rows(
            (
                "SELECT seal_bytes,accepted_spec_bytes,accepted_detector_bytes,"
                "accepted_rule_bytes FROM scanipy_execution.scan_seals WHERE "
                "request_id=%s"
            ),
            (str(handle.request_id),),
        )
        == original
    )
    with pytest.raises(psycopg2.Error, match="conflicting seal"), pg.repo("detector", org) as repo:
        repo.register_capture_and_seal(claim.fence, capture_seal(handle.request_id, requested))


@pytest.mark.parametrize(
    "field", ["expected_tool_digest", "expected_code_digest", "expected_image_digest"]
)
def test_missing_planned_pins_keep_intent_but_cannot_complete_detection(occurrence_pg, field):
    pg = occurrence_pg
    org, codebase = pg.scope()
    requested = request_input(org, codebase)
    policy = requested.planned_policy.value
    policy["bindings"][0][field] = None
    planned = encode_envelope("planned-policy", policy)
    requested = replace(
        requested,
        request=encode_envelope(
            "request", {**requested.request.value, "requested_policy_digest": planned.digest.hex()}
        ),
        planned_policy=planned,
    )
    with pg.repo("request", org) as repo:
        handle = repo.create_request(requested)
    with pg.repo("detector", org) as repo:
        claim = repo.claim("capture_detection", attempt_policy(), handle.work_item_id)
        repo.register_capture_and_seal(claim.fence, capture_seal(handle.request_id, requested))
        run = UUID(repo.begin_detector_run(claim.fence, invocation())["run_id"])
    with pytest.raises(psycopg2.Error, match="artifact pins"), pg.repo("detector", org) as repo:
        repo.retain_detection_batch(claim.fence, run, batch(run))
    with pg.repo("detector", org) as repo:
        repo.finish(claim.fence, attempt_result(failed=True))
    assert stages(pg, handle.request_id)[1] == "failed"


@pytest.mark.parametrize("change", ["lease", "code", "environment"])
def test_attempt_claim_rejects_policy_changes(occurrence_pg, change):
    pg = occurrence_pg
    org, codebase = pg.scope()
    with pg.repo("request", org) as repo:
        handle = repo.create_request(request_input(org, codebase))
    policy = attempt_policy().value
    policy[
        {
            "lease": "lease_seconds",
            "code": "code_policy_digest",
            "environment": "environment_policy_digest",
        }[change]
    ] = 299 if change == "lease" else "d" * 64
    with pytest.raises(psycopg2.Error, match="policy"), pg.repo("detector", org) as repo:
        repo.claim(
            "capture_detection", encode_envelope("attempt-policy", policy), handle.work_item_id
        )


@pytest.mark.parametrize(
    "change",
    [
        "duplicate",
        "nested_duplicate",
        "whitespace",
        "escaped",
        "float",
        "bool_integer",
        "negative_zero",
        "digest",
    ],
)
def test_sql_and_python_reject_ambiguous_canonical_bytes(occurrence_pg, change):
    valid = envelope("source-inventory", files=[{"path": "é.py", "size": 0, "sha256": "a" * 64}])
    data = valid.data
    if change == "duplicate":
        data = b'{"files":[],' + data[1:]
    elif change == "nested_duplicate":
        data = data.replace(b'"size":0', b'"size":0,"size":0')
    elif change == "whitespace":
        data += b"\n"
    elif change == "escaped":
        data = data.replace("é".encode(), b"\\u00e9")
    elif change == "float":
        data = data.replace(b'"size":0', b'"size":0.0')
    elif change == "bool_integer":
        data = data.replace(b'"size":0', b'"size":false')
    elif change == "negative_zero":
        data = data.replace(b'"size":0', b'"size":-0')
    digest = hashlib.sha256(b"scanipy-execution/source-inventory/1\n" + data).digest()
    if change == "digest":
        digest = b"x" * 32
    with pytest.raises(ValueError):
        decode_envelope("source-inventory", data, digest)
    with (
        pytest.raises(psycopg2.Error),
        occurrence_pg.admin() as connection,
        connection.cursor() as cursor,
    ):
        cursor.execute(
            "SELECT scanipy_execution.v1_envelope('source-inventory',%s,%s)", (data, digest)
        )


@pytest.mark.parametrize("path,size", [("é.py", 0), ("😀.py", 2**63 - 1), ("control\n.py", 1)])
def test_sql_python_portable_canonical_positive_vectors(occurrence_pg, path, size):
    value = envelope("source-inventory", files=[{"path": path, "size": size, "sha256": "a" * 64}])
    with occurrence_pg.admin() as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT scanipy_execution.v1_envelope('source-inventory',%s,%s)",
            (value.data, value.digest),
        )
        assert cursor.fetchone()[0] == value.value
        cursor.execute(
            "SELECT scanipy_execution.v1_canonical(%s::json,0)", ('{"value":-9223372036854775808}',)
        )
        assert cursor.fetchone()[0] == '{"value":-9223372036854775808}'


@pytest.mark.parametrize("array_shape", ["ARRAY[1],ARRAY[0]", "ARRAY[1,1]"])
def test_direct_sql_cannot_drop_nonstandard_nullable_witness_array(occurrence_pg, array_shape):
    pg = occurrence_pg
    org, _, handle, claim, _ = start(pg)
    with pg.repo("detector", org) as repo:
        run = UUID(repo.begin_detector_run(claim.fence, invocation())["run_id"])
    observed = batch(run)
    value = observed.envelope.value
    value["occurrences"][0]["witness_sha256"] = None
    value["inventory_digest"] = envelope(
        "occurrence-inventory", occurrences=value["occurrences"]
    ).digest.hex()
    missing = DetectionBatch(
        encode_envelope("detection-batch", value),
        observed.stdout,
        observed.stderr,
        (RawObservation(observed.observations[0].result),),
    )
    with pytest.raises(psycopg2.Error, match="byte-array wire"), pg.repo("detector", org) as repo:
        cursor = repo.connection.cursor()
        try:
            cursor.execute(
                (
                    "SELECT scanipy_execution.retain_detection_batch_v1(%s,%s,%s,%s,%s,"
                    "%s,%s,%s,%s,%s,%s,array_fill(%s::bytea,"
                )
                + array_shape
                + "))",
                (
                    str(org),
                    str(claim.fence.work_item_id),
                    str(claim.fence.attempt_id),
                    claim.fence.token,
                    claim.fence.revision,
                    str(run),
                    missing.envelope.data,
                    missing.envelope.digest,
                    missing.stdout,
                    missing.stderr,
                    [missing.observations[0].result],
                    b"supplied witness must not disappear",
                ),
            )
        finally:
            cursor.close()
    assert pg.rows(
        "SELECT count(*) FROM scanipy_execution.detection_occurrences WHERE request_id=%s",
        (str(handle.request_id),),
    ) == [(0,)]
    with pg.repo("detector", org) as repo:
        kept = repo.retain_detection_batch(claim.fence, run, missing)
    assert pg.rows(
        (
            "SELECT witness_bytes,witness_digest FROM "
            "scanipy_execution.detection_occurrences WHERE id=%s"
        ),
        (str(kept.occurrence_ids[0]),),
    ) == [(None, None)]


@pytest.mark.parametrize("array_shape", ["ARRAY[1],ARRAY[0]", "ARRAY[1,1]"])
def test_direct_sql_rejects_nonstandard_accepted_content_array(occurrence_pg, array_shape):
    pg = occurrence_pg
    org, requested, handle, claim, _ = start(pg)
    capture = capture_seal(handle.request_id, requested)
    with pytest.raises(psycopg2.Error, match="byte-array wire"), pg.repo("detector", org) as repo:
        cursor = repo.connection.cursor()
        try:
            cursor.execute(
                (
                    "SELECT scanipy_execution.register_capture_and_seal_v1(%s,%s,%s,%s,"
                    "%s,%s,%s,%s,%s,%s,%s,%s,array_fill(%s::bytea,"
                )
                + array_shape
                + "),%s,%s)",
                (
                    str(org),
                    str(claim.fence.work_item_id),
                    str(claim.fence.attempt_id),
                    claim.fence.token,
                    claim.fence.revision,
                    capture.seal.data,
                    capture.seal.digest,
                    capture.inventory.data,
                    capture.inventory.digest,
                    capture.accepted_content.data,
                    capture.accepted_content.digest,
                    capture.spec,
                    capture.detectors[0],
                    list(capture.rules),
                    capture.authority_evidence,
                ),
            )
        finally:
            cursor.close()


def test_direct_sql_size_limits_fail_without_truncation(occurrence_pg):
    pg = occurrence_pg
    org, _, handle, claim, _ = start(pg)
    with pg.repo("detector", org) as repo:
        run = UUID(repo.begin_detector_run(claim.fence, invocation())["run_id"])
    observed = batch(run)
    with (
        pytest.raises(psycopg2.Error, match="occurrence raw byte limit"),
        pg.repo("detector", org) as repo,
    ):
        cursor = repo.connection.cursor()
        try:
            cursor.execute(
                (
                    "SELECT scanipy_execution.retain_detection_batch_v1(%s,%s,%s,%s,%s,"
                    "%s,%s,%s,%s,%s,ARRAY[convert_to(repeat('x',16777217),'UTF8')],%s)"
                ),
                (
                    str(org),
                    str(claim.fence.work_item_id),
                    str(claim.fence.attempt_id),
                    claim.fence.token,
                    claim.fence.revision,
                    str(run),
                    observed.envelope.data,
                    observed.envelope.digest,
                    observed.stdout,
                    observed.stderr,
                    [observed.observations[0].witness],
                ),
            )
        finally:
            cursor.close()
    with (
        pytest.raises(psycopg2.Error, match="batch raw byte limit"),
        pg.repo("detector", org) as repo,
    ):
        cursor = repo.connection.cursor()
        try:
            cursor.execute(
                (
                    "SELECT scanipy_execution.retain_detection_batch_v1(%s,%s,%s,%s,%s,"
                    "%s,%s,%s,convert_to(repeat('x',67108865),'UTF8'),%s,%s,%s)"
                ),
                (
                    str(org),
                    str(claim.fence.work_item_id),
                    str(claim.fence.attempt_id),
                    claim.fence.token,
                    claim.fence.revision,
                    str(run),
                    observed.envelope.data,
                    observed.envelope.digest,
                    observed.stderr,
                    [observed.observations[0].result],
                    [observed.observations[0].witness],
                ),
            )
        finally:
            cursor.close()
    with (
        pytest.raises(psycopg2.Error, match="envelope size"),
        pg.admin() as connection,
        connection.cursor() as cursor,
    ):
        cursor.execute(
            (
                "SELECT scanipy_execution.v1_envelope('source-inventory',"
                "convert_to(repeat('x',1048577),'UTF8'),%s)"
            ),
            (b"x" * 32,),
        )
    assert pg.rows(
        "SELECT state,result_bytes FROM scanipy_execution.detector_runs WHERE id=%s", (str(run),)
    ) == [("running", None)]
    assert pg.rows(
        "SELECT count(*) FROM scanipy_execution.detection_occurrences WHERE request_id=%s",
        (str(handle.request_id),),
    ) == [(0,)]
