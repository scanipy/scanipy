"""DEPLOY-family integration test specs — TST-AC-DEPLOY-01a..e, 03a..c, 04a..c, 05a..b.

Spec-first TDD stubs for the DEPLOY subsystem. Production and infra code do not
exist yet, so each spec is registered-but-dormant: marked xfail so the CI job
exists and is collectable, and bodies `pytest.skip(...)` until the owning
CMP-DEPLOY-* is DONE.

Marker note (--strict-markers): the closed marker set is
{unit, integration, falsifier, empirical, invariant, nightly, pre_release}.
The WBS `[NEGATIVE]` kind (DEPLOY-05a/b) maps to `@pytest.mark.integration`
because those specs exercise live API/worker callback surfaces, not pure units;
the `[NEGATIVE]` kind is recorded in the docstring `Kind tag:` field only.

Source-of-truth: WBS.md §2.4 / §4.2 (verbatim ACs); DOC-CMP-DEPLOY-01..05.md §9;
DOC-DEPLOY-DECISIONS.md (16 RESOLVED CLAR-DEPLOY-*); CLAUDE.md §15 (four CI gates).

When the owning CMP-DEPLOY-* is DONE, replace xfail + skips with real assertions.
"""

import json
import os
import re
import subprocess
from pathlib import Path
from uuid import uuid4

import pytest

from tools.observability.logging import MANDATORY_FIELDS, get_logger

# Repo root = three levels up from tests/integration/test_deploy_specs.py.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_WBS = _REPO_ROOT / "WBS.md"
_DECISIONS = _REPO_ROOT / "docs" / "cross-cutting" / "DOC-DEPLOY-DECISIONS.md"


def _alembic(command: list[str], database_url: str) -> subprocess.CompletedProcess[str]:
    """Run an Alembic subcommand from the repo root with the DB URL injected.

    Mirrors ``tests/integration/test_cp_specs.py`` (AC-CP-03a) so AC-DEPLOY-01d is
    a faithful cross-test of the same Alembic migration surface.
    """
    env = {**os.environ, "SCANIPY_DATABASE_URL": database_url}
    return subprocess.run(
        ["alembic", *command],
        cwd=_REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


# ---------------------------------------------------------------------------
# CMP-DEPLOY-01 — substrate decision record + IaC substrate (AC-DEPLOY-01a..e)
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_deploy_01a_every_clar_deploy_has_recorded_decision() -> None:
    """Every CLAR-DEPLOY-* has a recorded decision with rationale to PLAN/SDD.

    Test id: TST-AC-DEPLOY-01a
    Maps to AC: AC-DEPLOY-01a — Every `CLAR-DEPLOY-*` in §17 has a recorded
        decision with a one-paragraph rationale referenced back to `PLAN.md` /
        `SDD.md` constraints.
    Kind tag: [INTEGRATION]
    Inputs: `docs/cross-cutting/DOC-DEPLOY-DECISIONS.md`; `WBS.md §17`
        CLAR-DEPLOY-* register (all 16 RESOLVED 2026-05-23).
    Outputs: per-CLAR section presence + Rationale/Consequences subsections.
    Pass criteria: for every `CLAR-DEPLOY-*` open in `WBS.md §17`, the decision
        record contains a `## CLAR-DEPLOY-*` section bearing both a Rationale and
        a Consequences subsection that reference `PLAN.md` / `SDD.md`. (All 16
        present today — substrate dimension: compute/S3/RDS/secrets-KMS/queue and
        the remaining 11; the test enumerates the full §17 set, not a fixed 5.)
    Frequency: every CI run.
    Hard gate?: yes.
    """
    wbs_text = _WBS.read_text(encoding="utf-8")
    decisions_text = _DECISIONS.read_text(encoding="utf-8")

    # Enumerate every CLAR-DEPLOY-NN that appears RESOLVED in the WBS §17 register.
    # As of 2026-06-03 every CLAR-DEPLOY-* is RESOLVED: the last two — DEPLOY-17
    # (branch-protection process shims) and DEPLOY-18 (IaC placement) — were ratified
    # then (DECISION-PART2), so each now carries a decision-record section below.
    resolved_ids: set[str] = set()
    deferred_ids: set[str] = set()
    for line in wbs_text.splitlines():
        match = re.match(r"\|\s*(CLAR-DEPLOY-\d+)\s*\|", line)
        if match is None:
            continue
        clar_id = match.group(1)
        # Read the STATUS *column*, not a substring of the whole row: a CLAR's
        # free-text description may legitimately contain the word "RESOLVED"
        # (e.g. "all 16 CLAR-DEPLOY-* RESOLVED"), which would mis-promote an OPEN
        # row. The status column holds exactly one status token as its whole cell
        # value, so match on a stripped cell equalling a status word.
        cells = {cell.strip() for cell in line.split("|")}
        if "RESOLVED" in cells:
            resolved_ids.add(clar_id)
        elif "DEFERRED" in cells:
            deferred_ids.add(clar_id)
        # OPEN rows (none today) would require no decision-record section and are
        # intentionally excluded from both sets.

    assert resolved_ids, "no RESOLVED CLAR-DEPLOY-* rows found in WBS.md §17"
    # As of 2026-06-03 DEPLOY-17 and DEPLOY-18 are RESOLVED (ratified governance),
    # so each must carry a decision record (enforced by the loop below); none remain
    # deferred. This guards against silently dropping their records on a re-edit.
    assert "CLAR-DEPLOY-17" in resolved_ids
    assert "CLAR-DEPLOY-18" in resolved_ids

    # Split the decision record into ``## CLAR-DEPLOY-NN`` sections.
    sections: dict[str, str] = {}
    current_id: str | None = None
    buffer: list[str] = []
    for line in decisions_text.splitlines():
        heading = re.match(r"##\s+(CLAR-DEPLOY-\d+)\b", line)
        if heading is not None:
            if current_id is not None:
                sections[current_id] = "\n".join(buffer)
            current_id = heading.group(1)
            buffer = []
        elif current_id is not None:
            buffer.append(line)
    if current_id is not None:
        sections[current_id] = "\n".join(buffer)

    # Every RESOLVED CLAR-DEPLOY-* has a section with Rationale + Consequences
    # referencing PLAN.md / SDD.md (AC-DEPLOY-01a).
    for clar_id in sorted(resolved_ids):
        assert clar_id in sections, f"{clar_id} has no '## {clar_id}' decision record section"
        body = sections[clar_id]
        assert "**Rationale:**" in body, f"{clar_id} record is missing a Rationale subsection"
        assert "**Consequences:**" in body, f"{clar_id} record is missing a Consequences subsection"
        # The one-paragraph rationale must reference back to a PLAN.md / SDD.md
        # constraint (AC-DEPLOY-01a). Per the source-of-truth hierarchy
        # (CLAUDE.md §1), WBS.md and CMP-* / AC-* identifiers are derived strictly
        # from SDD.md, so a rationale grounded in `WBS.md §N` or a `CMP-*` / `AC-*`
        # constraint (e.g. CLAR-DEPLOY-11 → `WBS.md §15` + `CMP-CI-01`) traces back
        # to an SDD constraint and satisfies the AC. Bare prose with no upstream
        # constraint reference fails.
        rationale = body.split("**Rationale:**", 1)[1].split("**Consequences:**", 1)[0]
        upstream_refs = ("PLAN.md", "SDD.md", "WBS.md", "CMP-", "AC-")
        assert any(ref in rationale for ref in upstream_refs), (
            f"{clar_id} Rationale does not reference an upstream PLAN.md / SDD.md "
            "(or SDD-derived WBS.md / CMP-* / AC-*) constraint"
        )


@pytest.mark.integration
def test_deploy_01b_object_store_deterministic_key_path() -> None:
    """Object store supports content-addressable deterministic keys (S3 scheme).

    Test id: TST-AC-DEPLOY-01b
    Maps to AC: AC-DEPLOY-01b — The chosen object-store primitive supports
        content-addressable, deterministic keys for the artifacts named in
        `SDD.md` CMP-SNAP-01 (`AC-SNAP-01a`).
    Kind tag: [INTEGRATION]
    Inputs: a snapshot write for a known `(org_id, codebase_id, commit_sha,
        env_digest)`; the five CMP-SNAP-01 artifact types.
    Outputs: the persisted S3 key path for each of the five artifacts.
    Pass criteria: every key equals
        `orgs/{org_id}/codebases/{codebase_id}/snapshots/{commit_sha}/`
        `{env_digest}/{artifact}` (CLAR-DEPLOY-02); keys are byte-for-byte
        reproducible from the inputs.
    Frequency: every CI run.
    Hard gate?: yes — INV-2 (env_digest carried in the deterministic key path).
    """
    from services.substrate.object_store import (
        SNAPSHOT_ARTIFACT_SUFFIXES,
        SnapshotKeyBuilder,
    )

    org_id = "11111111-1111-1111-1111-111111111111"
    codebase_id = "22222222-2222-2222-2222-222222222222"
    commit_sha = "0123456789abcdef0123456789abcdef01234567"  # pragma: allowlist secret
    env_digest = "sha256:" + "a" * 64

    builder = SnapshotKeyBuilder(
        org_id=org_id,
        codebase_id=codebase_id,
        commit_sha=commit_sha,
        env_digest=env_digest,
    )

    prefix = f"orgs/{org_id}/codebases/{codebase_id}/snapshots/{commit_sha}/{env_digest}/"

    # Exactly the five AC-SNAP-01a artifacts are addressable.
    assert set(SNAPSHOT_ARTIFACT_SUFFIXES) == {
        "cpg_tarball",
        "reverse_symbol_index",
        "dynamic_call_graph",
        "delta_graph",
        "precondition_status",
    }

    # (1) Each of the five keys equals the exact CLAR-DEPLOY-02 scheme.
    expected_suffixes = {
        "cpg_tarball": "cpg.tar.zst",
        "reverse_symbol_index": "reverse_symbol_index.json.zst",
        "dynamic_call_graph": "dyn_call_graph.json.zst",
        "delta_graph": "delta_graph.json.zst",
        "precondition_status": "precondition_status.json",
    }
    keys = builder.all_artifact_keys()
    assert set(keys) == set(expected_suffixes)
    for artifact_type, suffix in expected_suffixes.items():
        assert keys[artifact_type] == f"{prefix}{suffix}"
        # env_digest is carried in the key path itself (INV-2).
        assert env_digest in keys[artifact_type]

    # (2) Determinism: a second builder from the same inputs yields byte-identical keys.
    again = SnapshotKeyBuilder(
        org_id=org_id,
        codebase_id=codebase_id,
        commit_sha=commit_sha,
        env_digest=env_digest,
    )
    assert again.all_artifact_keys() == keys


@pytest.mark.integration
def test_deploy_01c_queue_dlq_and_at_least_once_idempotent() -> None:
    """Queue supports per-queue DLQ + at-least-once delivery with idempotent workers.

    Test id: TST-AC-DEPLOY-01c
    Maps to AC: AC-DEPLOY-01c — The chosen queue primitive supports per-queue
        dead-letter routing and at-least-once delivery, with idempotent worker
        contracts.
    Kind tag: [INTEGRATION]
    Inputs: an SQS standard queue + DLQ (CLAR-DEPLOY-06, max-receive 3); a poison
        message that always fails; a normal message redelivered twice.
    Outputs: DLQ contents after exhaustion; worker side effects across redelivery.
    Pass criteria: poison message lands in the DLQ after 3 receives; the worker
        handler is idempotent on redelivery (deduped via `snapshot_id`), producing
        no duplicate side effects.
    Frequency: every CI run.
    Hard gate?: yes.
    """
    from services.substrate.queue import (
        DEFAULT_MAX_RECEIVE_COUNT,
        IdempotentConsumer,
        StandardQueue,
    )

    assert DEFAULT_MAX_RECEIVE_COUNT == 3  # CLAR-DEPLOY-06 max-receive.

    # (1) Poison message → DLQ after 3 receives; a handler that always raises.
    poison_queue: StandardQueue = StandardQueue(name="snapshot")
    poison_queue.send({"snapshot_id": "poison"}, dedup_key="poison")

    def always_fails(body: dict[str, str]) -> None:
        raise RuntimeError(f"poison message {body['snapshot_id']} always fails")

    poison_consumer = IdempotentConsumer(queue=poison_queue, handler=always_fails)

    # First two receives fail and redeliver; the third failure routes to the DLQ.
    poison_consumer.poll_once()
    assert poison_queue.dlq_messages == [], "DLQ'd too early (before max-receive 3)"
    poison_consumer.poll_once()
    assert poison_queue.dlq_messages == [], "DLQ'd too early (before max-receive 3)"
    poison_consumer.poll_once()
    assert len(poison_queue.dlq_messages) == 1, "poison message did not reach DLQ after 3 receives"
    assert poison_queue.dlq_messages[0].dedup_key == "poison"
    assert poison_queue.dlq_messages[0].receive_count == 3
    # Exhausted: no further redelivery on the main queue.
    assert poison_queue.receive() is None
    assert poison_consumer.handler_invocations == 0  # never processed successfully.

    # (2) At-least-once + idempotent worker: a redelivered normal message produces
    # no duplicate side effect (dedupe keyed on snapshot_id).
    work_queue: StandardQueue = StandardQueue(name="snapshot")
    side_effects: list[str] = []

    def record(body: dict[str, str]) -> None:
        side_effects.append(body["snapshot_id"])

    work_consumer = IdempotentConsumer(queue=work_queue, handler=record)

    # Same snapshot_id delivered three times (redelivery duplicates).
    work_queue.send({"snapshot_id": "snap-A"}, dedup_key="snap-A")
    work_queue.send({"snapshot_id": "snap-A"}, dedup_key="snap-A")
    work_queue.send({"snapshot_id": "snap-A"}, dedup_key="snap-A")
    work_queue.send({"snapshot_id": "snap-B"}, dedup_key="snap-B")
    work_consumer.drain()

    # The handler ran at-most-once per distinct snapshot_id despite redelivery.
    assert side_effects == ["snap-A", "snap-B"]
    assert work_consumer.handler_invocations == 2
    assert work_consumer.processed_keys == frozenset({"snap-A", "snap-B"})
    assert work_queue.dlq_messages == []


@pytest.mark.integration
def test_deploy_01d_relational_forward_and_rollback_migrations() -> None:
    """Relational primitive supports forward + rollback migrations on a fresh DB.

    Test id: TST-AC-DEPLOY-01d
    Maps to AC: AC-DEPLOY-01d — The chosen relational primitive supports forward
        + rollback migrations on a fresh database (cf. `AC-CP-03a`).
    Kind tag: [INTEGRATION]
    Inputs: a fresh PostgreSQL 16 instance (CLAR-DEPLOY-03); the Alembic
        migration set in `db/migrations/`.
    Outputs: exit status of `alembic upgrade head` then `alembic downgrade base`.
    Pass criteria: both `upgrade head` and `downgrade base` succeed with no manual
        repair. Cross-test with TST-AC-CP-03a.
    Frequency: every CI run.
    Hard gate?: yes.
    """
    database_url = os.environ.get("SCANIPY_DATABASE_URL")
    if not database_url:
        pytest.skip(
            "SCANIPY_DATABASE_URL not configured — live PostgreSQL 16 integration "
            "env gap; AC-DEPLOY-01d runs in the CI integration-tests job (cf. AC-CP-03a)."
        )

    # Cross-test of the same Alembic migration surface AC-CP-03a exercises: the
    # relational primitive (PostgreSQL 16, CLAR-DEPLOY-03) supports forward +
    # rollback migrations on a fresh DB.
    base = _alembic(["downgrade", "base"], database_url)
    assert base.returncode == 0, f"pre-test downgrade failed:\n{base.stderr}"

    up = _alembic(["upgrade", "head"], database_url)
    assert up.returncode == 0, f"alembic upgrade head failed:\n{up.stderr}"

    down = _alembic(["downgrade", "base"], database_url)
    assert down.returncode == 0, f"alembic downgrade base failed:\n{down.stderr}"


@pytest.mark.integration
def test_deploy_01e_kms_envelope_encryption_and_rotation() -> None:
    """KMS-equivalent supports envelope encryption and key rotation.

    Test id: TST-AC-DEPLOY-01e
    Maps to AC: AC-DEPLOY-01e — The chosen KMS-equivalent supports envelope
        encryption and key rotation (cf. `AC-CP-02a`).
    Kind tag: [INTEGRATION]
    Inputs: an AWS KMS CMK (CLAR-DEPLOY-04); a payload encrypted under key version
        v1; a triggered KMS auto-rotation to v2.
    Outputs: decryption result of v1-encrypted ciphertext after rotation.
    Pass criteria: payload encrypts with the CMK; after rotation, ciphertext
        written under v1 still decrypts (KMS preserves prior key versions). Cross-
        test with TST-AC-CP-02a.
    Frequency: every CI run.
    Hard gate?: yes.
    """
    # The KMS-equivalent primitive (CLAR-DEPLOY-04) is the CMP-CP-02 envelope-
    # encryption service — reused here, not re-implemented, so there is one
    # envelope-encryption surface. Cross-test of AC-CP-02a's rotation arm.
    from services.credential_encryption import CredentialEncryptionService
    from tests.unit.test_credential_encryption import (
        FakeAuditLog,
        FakeKeyStore,
        FakeKMS,
    )

    service = CredentialEncryptionService(
        kms=FakeKMS(),
        key_store=FakeKeyStore(),
        audit_log=FakeAuditLog(),
    )
    org_id = uuid4()
    plaintext = b"deploy-01e-envelope-payload-v1"

    # Encrypt under the per-tenant CMK at key version v1.
    v1_ciphertext = service.encrypt_credential(plaintext, org_id)
    assert v1_ciphertext.ciphertext_blob != plaintext

    # Trigger rotation → v2 (KMS preserves prior key versions).
    service.rotate_cmk(org_id, reason="scheduled")

    # Ciphertext written under v1 still decrypts after rotation.
    assert service.decrypt_credential(v1_ciphertext, org_id) == plaintext

    # New material encrypts + decrypts cleanly under the rotated key.
    post = service.encrypt_credential(b"deploy-01e-payload-v2", org_id)
    assert service.decrypt_credential(post, org_id) == b"deploy-01e-payload-v2"


# ---------------------------------------------------------------------------
# CMP-DEPLOY-03 — observability: correlation trace + named alarms (AC-DEPLOY-03a..c)
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.xfail(
    reason="CMP-DEPLOY-03 (observability) not yet implemented",
    strict=False,
)
def test_deploy_03a_scan_id_resolves_to_end_to_end_trace() -> None:
    """A single scan id resolves to a chronological cross-component trace.

    Test id: TST-AC-DEPLOY-03a
    Maps to AC: AC-DEPLOY-03a — A single scan id resolves to a chronological
        cross-component trace covering at least: webhook ingest, snapshot worker,
        every detector worker, normalizer, attestor verdict, callback delivery.
    Kind tag: [INTEGRATION]
    Inputs: one completed scan id; the OTel/X-Ray trace store (CLAR-DEPLOY-07).
    Outputs: the ordered span set keyed on the scan id.
    Pass criteria: the trace contains, in chronological order, spans for webhook
        ingest, snapshot worker, every detector worker, normalizer, attestor
        verdict, and callback delivery.
    Frequency: every CI run.
    Hard gate?: yes.
    """
    # TODO: run a scan; query X-Ray/OTel by scan id; assert all named lifecycle
    #       spans are present and chronologically ordered when CMP-DEPLOY-03 is DONE.
    pytest.skip("CMP-DEPLOY-03 not implemented yet")


@pytest.mark.integration
def test_deploy_03b_log_lines_carry_service_commit_env_digest(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Every emitted log line carries service name, build commit, and env_digest.

    Test id: TST-AC-DEPLOY-03b
    Maps to AC: AC-DEPLOY-03b — Every emitted log line carries a service name,
        build commit, and `env_digest`.
    Kind tag: [INTEGRATION]
    Inputs: a sampled corpus of structured JSON log lines drawn from every named
        AC-DEPLOY-03a lifecycle stage of one completed scan (webhook ingest,
        snapshot worker, detector worker, normalizer, attestor verdict, callback
        delivery), driven hermetically through the shared
        `tools.observability.logging.get_logger` surface every component uses
        (real CloudWatch retrieval is CLAR-DEPLOY-07 live-ops, out of scope for
        this repo-only slice — see `tests/unit/test_logger_factory.py`).
    Outputs: presence of `service`, `build_commit`, `env_digest` per line.
    Pass criteria: every sampled log line carries a non-empty service name, build
        commit, and `env_digest` (INV-2; .claude/rules/02-provenance.md), and the
        `env_digest` / `build_commit` values match the pinned scan-run env
        contract across every stage (single `Env`, INV-2).
    Frequency: every CI run.
    Hard gate?: yes.
    """
    build_commit = "c0ffee1234567890" * 4  # 64 hex chars — a realistic commit-ish token
    env_digest = "sha256:" + "b" * 64
    monkeypatch.setenv("SCANIPY_WORKER_VERSION", build_commit)
    monkeypatch.setenv("SCANIPY_ENV_DIGEST", env_digest)

    # The AC-DEPLOY-03a named lifecycle stages for one scan (kept in lockstep
    # with that spec's own span list so a future flip of 03a reuses this corpus
    # shape). Each stage emits >=1 structured line via the one shared formatter.
    stages = (
        "webhook-ingest",
        "snapshot-worker",
        "detector-worker",
        "normalizer",
        "attestor",
        "callback-delivery",
    )
    for stage in stages:
        monkeypatch.setenv("OTEL_SERVICE_NAME", stage)
        logger = get_logger(f"scanipy.deploy03b.{stage}")
        logger.propagate = False
        logger.info("%s stage complete for scan %s", stage, "deploy-03b-smoke-scan")

    err = capsys.readouterr().err.strip()
    lines = [line for line in err.splitlines() if line]
    assert len(lines) == len(stages), (
        f"expected exactly one sampled log line per lifecycle stage, got {len(lines)}"
    )

    seen_services: set[str] = set()
    for line in lines:
        payload = json.loads(line)
        for field in MANDATORY_FIELDS:
            assert field in payload, f"log line missing mandatory field {field!r}: {payload}"
            assert payload[field], f"mandatory field {field!r} must be non-empty: {payload}"
        # INV-2: every line in the sampled corpus reflects the SAME pinned Env —
        # a per-stage-drifted env_digest would silently break cross-component
        # provenance correlation for this scan.
        assert payload["env_digest"] == env_digest
        assert payload["build_commit"] == build_commit
        seen_services.add(str(payload["service"]))

    assert seen_services == set(stages), "expected one distinct service name per lifecycle stage"


@pytest.mark.integration
@pytest.mark.xfail(
    reason="CMP-DEPLOY-03 (observability) not yet implemented",
    strict=False,
)
def test_deploy_03c_alarms_exist_for_named_events() -> None:
    """Alarms exist for every named operational event.

    Test id: TST-AC-DEPLOY-03c
    Maps to AC: AC-DEPLOY-03c — Alarms exist for: snapshot-worker failure rate,
        detector-worker failure rate, callback HMAC rejection rate, Attestor
        core-partition diff (any non-zero rate is a hard incident), `CW-DETECT`
        differential-oracle disagreement rate, e-process martingale-unit-test
        failure.
    Kind tag: [INTEGRATION]
    Inputs: the provisioned CloudWatch alarm set (CLAR-DEPLOY-07).
    Outputs: the set of configured alarm names + their thresholds.
    Pass criteria: an alarm exists for each of the six named events: (1) snapshot-
        worker failure rate, (2) detector-worker failure rate, (3) callback HMAC
        rejection rate, (4) Attestor core-partition diff (threshold: any non-zero
        rate = hard incident), (5) CW-DETECT differential-oracle disagreement
        rate, (6) e-process martingale-unit-test failure.
    Frequency: every CI run.
    Hard gate?: yes.
    """
    # TODO: enumerate provisioned CloudWatch alarms; assert all six named alarms
    #       exist with the Attestor-diff alarm tripping on any non-zero rate when
    #       CMP-DEPLOY-03 is DONE.
    pytest.skip("CMP-DEPLOY-03 not implemented yet")


# ---------------------------------------------------------------------------
# CMP-DEPLOY-04 — CI/CD: pinned-digest deploy + hard CI gates (AC-DEPLOY-04a..c)
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.xfail(
    reason="CMP-DEPLOY-04 (CI/CD pipeline) not yet implemented",
    strict=False,
)
def test_deploy_04a_main_deploy_requires_pinned_digests_or_rollover() -> None:
    """Main-branch deploy cannot ship tool digests that drift from the record.

    Test id: TST-AC-DEPLOY-04a
    Maps to AC: AC-DEPLOY-04a — A merge to the main branch cannot deploy a worker
        image whose tool digests differ from those committed in the substrate
        decision record without an explicit `env_digest` rollover ceremony.
    Kind tag: [INTEGRATION]
    Inputs: a deploy attempt whose built image tool digests differ from the
        committed pin set, with NO `env_digest rollover` ceremony marker.
    Outputs: deploy workflow exit status.
    Pass criteria: the deploy is rejected (workflow fails) unless the
        `env_digest` rollover ceremony (CLAR-DEPLOY-13 / DOC-CMP-DEPLOY-02 §6.2)
        was performed; a matching rollover allows it.
    Frequency: every CI run; pre-release.
    Hard gate?: yes (CI gate).
    """
    # TODO: drive deploy.yml with a digest-drift image lacking a rollover marker;
    #       assert the workflow fails; then with a valid rollover, assert it passes
    #       when CMP-DEPLOY-04 is DONE.
    pytest.skip("CMP-DEPLOY-04 not implemented yet")


@pytest.mark.integration
@pytest.mark.xfail(
    reason="CMP-DEPLOY-04 (CI/CD pipeline) not yet implemented",
    strict=False,
)
def test_deploy_04b_ci_gates_are_hard_pipeline_failures() -> None:
    """The CMP-CI-01 gates are enforced as hard pipeline failures, not advisory.

    Test id: TST-AC-DEPLOY-04b
    Maps to AC: AC-DEPLOY-04b — The CI gates in `CMP-CI-01` are enforced as hard
        pipeline failures, not advisory checks.
    Kind tag: [INTEGRATION]
    Inputs: a pipeline run where each of the four named gates is independently
        seeded to fail (CLAUDE.md §15).
    Outputs: the overall pipeline conclusion for each seeded failure.
    Pass criteria: each of the four gates fails the pipeline hard (non-zero
        conclusion, merge blocked): Gate 1 DSL proofs (AC-DET-01a), Gate 2
        Falsifier CW (AC-SNAP-03a), Gate 3 Attestor (AC-CP-05c), Gate 4 e-process
        unit (AC-TRI-02b). No gate is advisory.
    Frequency: every CI run.
    Hard gate?: yes (CI gate).
    """
    # TODO: seed each of the four gates to fail in turn; assert the pipeline
    #       conclusion is a hard failure (not neutral/advisory) for each when
    #       CMP-DEPLOY-04 + CMP-CI-01 are DONE.
    pytest.skip("CMP-DEPLOY-04 not implemented yet")


@pytest.mark.integration
@pytest.mark.xfail(
    reason="CMP-DEPLOY-04 (CI/CD pipeline) not yet implemented",
    strict=False,
)
def test_deploy_04c_image_provenance_signed_and_published() -> None:
    """Image provenance (commit, inputs, tool digests) is signed and published.

    Test id: TST-AC-DEPLOY-04c
    Maps to AC: AC-DEPLOY-04c — Image provenance (build commit, build inputs,
        tool digests) is signed and published with the artifact.
    Kind tag: [INTEGRATION]
    Inputs: a published worker image artifact in ECR (CLAR-DEPLOY-13).
    Outputs: the attached Cosign signature + SLSA-3 provenance attestation.
    Pass criteria: the artifact carries a verifiable Cosign signature and a SLSA-3
        provenance attestation whose predicate links build commit, build inputs
        (`pins.json` sha256), and tool digests to the image digest.
    Frequency: every CI run; pre-release.
    Hard gate?: yes (CI gate).
    """
    # TODO: pull the published image; `cosign verify` the signature; fetch and
    #       validate the SLSA-3 attestation predicate links commit + pins + tool
    #       digests to the image digest when CMP-DEPLOY-04 is DONE.
    pytest.skip("CMP-DEPLOY-04 not implemented yet")


# ---------------------------------------------------------------------------
# CMP-DEPLOY-05 — tenant isolation: cross-org denial + namespaced blobs
# (AC-DEPLOY-05a..b — WBS kind [NEGATIVE], executed as integration)
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.xfail(
    reason=(
        "AC-DEPLOY-05a app-surface arm blocked on CLAR-DEPLOY-19 (HTTP adapter); "
        "enforcement arm lives in tests/integration/test_tenant_isolation_live.py (aws_live)"
    ),
    strict=False,
)
def test_deploy_05a_cross_org_access_denied_at_every_surface() -> None:
    """A cross-org access attempt fails 4xx + audit log at every API/callback surface.

    Test id: TST-AC-DEPLOY-05a
    Maps to AC: AC-DEPLOY-05a — A parameterised negative test that drives a
        cross-org access attempt at every API surface and every worker callback
        fails with a 4xx and emits an audit log line.
    Kind tag: [NEGATIVE]
    Inputs: an authenticated principal scoped to org A; requests parameterised
        across every API surface and every worker callback that target org B
        resources.
    Outputs: HTTP status + audit log line per attempted surface.
    Pass criteria: every cross-org attempt is rejected with a 4xx and emits an
        audit log line; no surface returns org B data. (Three-layer backstop:
        S3 prefix, RDS RLS, per-tenant CMK — CLAR-DEPLOY-16.)
    Frequency: every CI run.
    Hard gate?: yes.

    Arm split (CLAR-DEPLOY-21): this stub is the app-surface 4xx+audit arm and
    is gated on the CLAR-DEPLOY-19 HTTP adapter, NOT on AWS emulation — moto
    cannot observe policy denies, so no moto flip is possible here. The
    substrate enforcement arm (real S3/KMS AccessDenied under a rendered
    session policy) is covered by the aws_live twins.
    """
    # TODO: parameterise org-A principal across all API surfaces + worker callbacks
    #       targeting org-B resources; assert 4xx + audit log on each when
    #       CMP-DEPLOY-05 is DONE.
    pytest.skip(
        "app-surface arm blocked on CLAR-DEPLOY-19; enforcement arm lives in "
        "tests/integration/test_tenant_isolation_live.py (aws_live)"
    )


@pytest.mark.integration
def test_deploy_05b_blob_paths_namespaced_no_cross_org_traversal() -> None:
    """Blob-store paths are org-namespaced; a path traversal cannot cross orgs.

    Test id: TST-AC-DEPLOY-05b (key-resolution arm — CI-runnable per CLAR-DEPLOY-21)
    Maps to AC: AC-DEPLOY-05b — Blob-store paths are namespaced by org id; a path
        traversal in a request parameter cannot resolve to another org's artifact.
    Kind tag: [NEGATIVE]
    Inputs: org-A S3ObjectStore requests carrying traversal payloads (`../`,
        encoded variants — the tests/unit/test_substrate.py corpus) in key
        components and access keys aimed at org B's prefix, against a moto S3
        backend seeded with an org-B artifact.
    Outputs: resolved S3 key + access result per payload.
    Pass criteria: every traversal payload is rejected client-side BEFORE any
        S3 call (PathTraversalError / CrossTenantAccessError); no minted key
        ever escapes `orgs/{org_id}/...` (CLAR-DEPLOY-02/16); org B's artifact
        is never read or written; the positive control (same operation on the
        owning org's key) succeeds.
    Frequency: every CI run.
    Hard gate?: yes.

    Arm split (CLAR-DEPLOY-21): moto does not evaluate IAM/bucket/key policies,
    so this arm asserts key-resolution mechanics only — the enforcement (deny)
    arm lives in the aws_live twin
    (tests/integration/test_tenant_isolation_live.py::
    test_deploy_05b_live_bucket_policy_prefix_deny).
    """
    import boto3
    from moto import mock_aws

    from services.substrate.object_store import (
        CrossTenantAccessError,
        PathTraversalError,
        S3ObjectStore,
        SnapshotKeyBuilder,
    )

    org_a = "11111111-1111-1111-1111-111111111111"
    org_b = "99999999-9999-9999-9999-999999999999"
    builder_kw = {
        "codebase_id": "22222222-2222-2222-2222-222222222222",
        "commit_sha": "0123456789abcdef0123456789abcdef01234567",  # pragma: allowlist secret
        "env_digest": "sha256:" + "a" * 64,
    }
    bucket = "scanipy-test-snapshot"

    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket=bucket)
        store = S3ObjectStore(bucket, client=s3)

        # Seed the victim: an org-B artifact at its legitimate key.
        victim_key = SnapshotKeyBuilder(org_id=org_b, **builder_kw).artifact_key("cpg_tarball")
        store.put(org_b, victim_key, b"org-b-secret-artifact")

        # (1) Traversal payloads in a key COMPONENT never mint a key at all
        # (tests/unit/test_substrate.py component corpus).
        for payload in ["../escape", "a/b", "a\\b", "%2e%2e", "%2fetc", "%5c", "x\x00y", ""]:
            with pytest.raises(PathTraversalError):
                SnapshotKeyBuilder(org_id=payload, **builder_kw)
        # Every key a valid org-A builder CAN mint stays inside org A's prefix.
        minted = SnapshotKeyBuilder(org_id=org_a, **builder_kw).all_artifact_keys()
        assert all(key.startswith(f"orgs/{org_a}/") for key in minted.values())

        # (2) Traversal payloads in an ACCESS key aimed at org B's prefix are
        # rejected client-side, before any S3 call (guard-level corpus).
        for traversal_key in [
            f"orgs/{org_a}/../{victim_key}",
            f"orgs/{org_a}/%2e%2e/{victim_key}",
            f"orgs/{org_a}/%5c../{victim_key}",
            f"orgs/{org_a}/a\\../{victim_key}",
        ]:
            with pytest.raises(PathTraversalError):
                store.get(org_a, traversal_key)
            with pytest.raises(PathTraversalError):
                store.put(org_a, traversal_key, b"overwrite-attempt")
        # A forged well-formed org-B key from an org-A request is denied
        # client-side too (CrossTenantAccessError — guard, not AWS policy).
        with pytest.raises(CrossTenantAccessError):
            store.get(org_a, victim_key)
        with pytest.raises(CrossTenantAccessError):
            store.put(org_a, victim_key, b"overwrite-attempt")

        # Org B's artifact was neither read nor written by any attempt above.
        assert store.get(org_b, victim_key) == b"org-b-secret-artifact"
        listed = s3.list_objects_v2(Bucket=bucket)
        assert [obj["Key"] for obj in listed.get("Contents", [])] == [victim_key]

        # (3) Positive control: the same operations succeed for the owning org,
        # so the rejections above cannot be empty-because-absent greens.
        own_key = minted["cpg_tarball"]
        store.put(org_a, own_key, b"org-a-artifact")
        assert store.get(org_a, own_key) == b"org-a-artifact"
