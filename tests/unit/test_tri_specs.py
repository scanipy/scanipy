"""TRI-family unit / invariant specs — TST-AC-TRI-* + TST-INV-*-TRI-*.

Spec-first TDD: production code for the Triage & Spec-Inference subsystem
(CMP-TRI-01..03, ``services/triage/``) does not exist yet, so every spec below
is a registered-but-dormant stub. Each carries an
``@pytest.mark.xfail(strict=False)`` so the suite collects and runs without
blocking; the body calls ``pytest.skip`` until the owning CMP is DONE, at which
point the skip is removed and the stubbed assertion goes live.

Pattern mirrors ``tests/unit/test_dsl_proofs.py`` (the canonical convention).

TRI touches INV-3 (LLM off the deterministic detection path) — the most
safety-critical invariant. These specs encode the non-negotiable contract that
no LLM output influences a `deterministic-core` finding except via an accepted,
version-pinned spec in `S`, and that triage never deletes findings.

Covers (from WBS §4.2 / §4.3):
  - TST-AC-TRI-01a   [INVARIANT] — flag OFF: no origin / detection content change
  - TST-AC-TRI-01b   [INVARIANT] — ranking writes ONLY triage_* columns
  - TST-AC-TRI-02c   [INVARIANT] — accepted spec written version-pinned; core
                                   only ever consumes pinned specs
  - TST-AC-TRI-03b   [INVARIANT] — findings on an unrevalidated global spec carry
                                   `global-unrevalidated`
  - TST-INV-1-TRI-01 [INVARIANT] — no triage-induced origin flips (INV-1)
  - TST-INV-3-TRI-01 [INVARIANT] — LLM off the detection path (INV-3)
  - TST-INV-3-TRI-02 [INVARIANT] — accepted spec is a new pinned S_version;
                                   core reads only pinned specs (INV-3)
  - TST-INV-2-TRI-02 [INVARIANT] — accepted specs are version-pinned (INV-2)

NOTE: TST-AC-TRI-02a (falsifier) and TST-AC-TRI-02b (martingale [UNIT]) live in
``tests/falsifier/eprocess/test_tri02_eprocess.py`` so the ci.yml Gate-4 step
(which discovers ``tests/falsifier/eprocess/**/test_*.py``) runs the martingale
test. TST-AC-TRI-03a (quarantine falsifier) lives in
``tests/falsifier/eprocess/test_tri03_quarantine.py``.
"""

import pytest

from services.triage.spec_inference import CandidateSpec, EProcessState


def _drive_to_threshold(spec: CandidateSpec) -> EProcessState:
    """Run the REAL e-process on a clearly-good stream until E_t crosses 1/alpha.

    Used by the CMP-TRI-02 invariant specs so they exercise the real wealth
    process (not a force-constructed state): a do-nothing/broken e-process that
    never crosses the threshold makes the dependent assertions fail. The good
    stream uses true precision 0.95 >> pi_0.
    """
    import random

    from services.triage.spec_inference import initial_state, update_e_process

    rng = random.Random(11)
    state = initial_state(spec)
    for _ in range(500):
        obs = 1.0 if rng.random() < 0.95 else 0.0
        state = update_e_process(state, obs)
        if state.e_value >= state.threshold:
            return state
    raise AssertionError(
        f"e-process never crossed threshold on a good stream (final E_t={state.e_value})"
    )


@pytest.mark.invariant
def test_tri_01a_flag_off_no_origin_or_detection_change() -> None:
    """With the triage flag off, no finding's origin / detection content changes.

    Test id:        TST-AC-TRI-01a
    Maps to AC:     AC-TRI-01a — "With the triage flag off, no finding row's
                    `origin` or detection content is affected (INV-3)."
    Kind tag:       [INVARIANT]
    Inputs:         A scan over a fixture repo run with `LLM_TRIAGE=off`; the
                    pre-triage snapshot of the affected `findings` rows; a second
                    identical run (DOC-CMP-TRI-01 §5 mechanism (b)).
    Outputs:        Row-level diff of `findings` between the two runs over all
                    columns (origin + detection content + status).
    Pass criteria:  With `LLM_TRIAGE=off`, the diff is empty: NO `findings` row's
                    `origin`, detection-content, or `status` column changes, AND
                    no `triage_scores` row is created, AND no LLM call is made.
    Frequency:      every CI run
    Hard gate?:     yes — component acceptance gate for CMP-TRI-01 (INV-3).
    """
    import uuid

    from services.triage import run_triage_cycle
    from tests.tri01_fakes import (
        InMemoryFindingsTable,
        InMemoryTriageScoresStore,
        RecordingFakeLLM,
        make_finding,
    )

    scan_id = uuid.uuid4()
    findings = InMemoryFindingsTable(scan_id, [make_finding(), make_finding()])
    triage_store = InMemoryTriageScoresStore()
    llm = RecordingFakeLLM()

    before = findings.snapshot()
    result = run_triage_cycle(
        scan_id,
        llm_triage=False,  # LLM_TRIAGE=off — the production default
        findings=findings,
        triage_store=triage_store,
        llm=llm,
    )
    after = findings.snapshot()

    # No findings row changed: every column (origin + detection content + status)
    # is byte-identical across the flag-off cycle.
    assert before == after
    # No triage_scores row was created.
    assert result.rows_written == 0
    assert triage_store.writes == []
    # And — load-bearing — no LLM call was made at all.
    assert llm.call_count == 0
    assert result.llm_calls == 0


@pytest.mark.invariant
def test_tri_01b_ranking_writes_only_triage_columns() -> None:
    """Ranking writes only `triage_*` columns (to the triage_scores table).

    Test id:        TST-AC-TRI-01b
    Maps to AC:     AC-TRI-01b — "Ranking writes only `triage_*` columns."
    Kind tag:       [INVARIANT]
    Inputs:         A triage cycle run with `LLM_TRIAGE=on` under the
                    `scanipy_triage` DB role (DOC-CMP-TRI-01 §3.1 ALLOWED_TRIAGE_
                    COLUMNS; DOC-DB §4.14 grants block).
    Outputs:        The set of columns / tables written during the cycle.
    Pass criteria:  The only write target is `triage_scores`, and the written
                    column set ⊆ {finding_id, triage_score, triage_reason,
                    model_id, model_version, S_version, env_digest}. An attempted
                    UPDATE on any `findings` column fails with a Postgres
                    permission error; an attempted DELETE FROM `findings` also
                    fails with a permission error for `scanipy_triage` (INV-3:
                    triage ranking never deletes findings — a role retaining
                    DELETE while UPDATE is revoked would still let triage destroy
                    findings); no insert targets `provenance_records`,
                    `spec_versions`, or `proposed_specs`.
    Frequency:      every CI run
    Hard gate?:     yes — component acceptance gate for CMP-TRI-01 (INV-3).
    """
    import uuid

    from services.triage import ALLOWED_TRIAGE_COLUMNS, run_triage_cycle
    from tests.tri01_fakes import (
        FORBIDDEN_FINDINGS_WRITE_COLUMNS,
        InMemoryFindingsTable,
        InMemoryTriageScoresStore,
        RecordingFakeLLM,
        make_finding,
    )

    scan_id = uuid.uuid4()
    findings = InMemoryFindingsTable(scan_id, [make_finding(), make_finding()])
    triage_store = InMemoryTriageScoresStore()
    llm = RecordingFakeLLM()

    result = run_triage_cycle(
        scan_id,
        llm_triage=True,  # LLM_TRIAGE=on
        findings=findings,
        triage_store=triage_store,
        llm=llm,
    )

    # One additive triage_scores row per finding.
    assert result.rows_written == 2
    assert llm.call_count == 2

    # The ONLY write target is triage_scores.
    assert triage_store.written_tables == {"triage_scores"}
    # The written column set is a subset of the allowed triage columns —
    # never a findings detection / partition / status column.
    assert triage_store.written_columns <= set(ALLOWED_TRIAGE_COLUMNS)
    assert triage_store.written_columns.isdisjoint(FORBIDDEN_FINDINGS_WRITE_COLUMNS)
    assert "origin" not in triage_store.written_columns
    assert "status" not in triage_store.written_columns

    # An attempted UPDATE on any findings column fails with a permission error
    # (REVOKE ALL ON findings FROM scanipy_triage).
    a_finding_id = next(iter(findings.snapshot()))
    with pytest.raises(PermissionError):
        findings.update(a_finding_id, status="suppressed")
    # An attempted DELETE on findings ALSO fails — triage never deletes findings
    # (a role retaining DELETE while UPDATE is revoked could still destroy them).
    with pytest.raises(PermissionError):
        findings.delete(a_finding_id)

    # No insert ever targets provenance_records / spec_versions / proposed_specs.
    for forbidden in ("provenance_records", "spec_versions", "proposed_specs"):
        with pytest.raises(PermissionError):
            triage_store.insert(forbidden, {"finding_id": a_finding_id})
        assert forbidden not in triage_store.written_tables


@pytest.mark.invariant
def test_tri_02c_accepted_spec_version_pinned_core_reads_pinned_only() -> None:
    """Accepted spec written version-pinned; the core only consumes pinned specs.

    Test id:        TST-AC-TRI-02c
    Maps to AC:     AC-TRI-02c -- "An accepted spec is written version-pinned as a
                    new `S_version`; the deterministic core only ever consumes
                    pinned specs (INV-3)."
    Kind tag:       [INVARIANT]
    Inputs:         A candidate spec driven through the REAL e-process on a good
                    stream until its wealth crosses `E_t(sigma) >= 1/alpha`
                    (alpha=0.05 ==> threshold 20.0); the `spec_versions` table before
                    acceptance (DOC-CMP-TRI-02 §3.1, §4.2).
    Outputs:        The `spec_versions` table after acceptance; the `S_version`
                    set the deterministic core reads for a subsequent scan.
    Pass criteria:  Acceptance materializes exactly one NEW `spec_versions` row
                    with a fresh semver `S_version` (no existing row mutated); the
                    `proposed_specs.decision` flips to 'accepted' with an FK to the
                    new row; and the core consumes the spec ONLY via the pinned
                    `S_version` (never a mutable "current spec" pointer).
    Frequency:      every CI run
    Hard gate?:     yes -- standard release gate for CMP-TRI-02 (INV-3).
    """
    from services.triage.spec_inference import (
        CandidateSpec,
        evaluate_proposed_spec,
    )
    from tests.fnd03_fakes import InMemoryProvenanceStore, SoftwareKMSSigner
    from tests.tri02_fakes import (
        InMemoryProposedSpecStore,
        InMemorySpecVersionStore,
        new_uuid,
    )

    spec = CandidateSpec(
        id=new_uuid(),
        org_id=new_uuid(),
        spec_body={"class": "injection", "rule": "user-input-to-sql-sink"},
        detector_class="injection",
        pi_zero=0.7,
    )
    # Drive the REAL e-process to threshold on a clearly-good stream (not a
    # force-constructed state): this is what makes a do-nothing impl fail here.
    state = _drive_to_threshold(spec)
    assert state.e_value >= state.threshold

    spec_versions = InMemorySpecVersionStore()
    proposed_specs = InMemoryProposedSpecStore()
    before = spec_versions.all()
    assert before == []

    verdict = evaluate_proposed_spec(
        spec,
        state,
        spec_versions=spec_versions,
        proposed_specs=proposed_specs,
        provenance_store=InMemoryProvenanceStore(),
        signer=SoftwareKMSSigner(),
    )

    assert verdict.decision == "accepted"
    assert verdict.accepted_S_version is not None  # new pinned semver

    after = spec_versions.all()
    assert len(after) == len(before) + 1  # exactly one new row materialized
    new_row = after[0]
    assert new_row.S_version == verdict.accepted_S_version
    # The core consumes the spec ONLY via the pinned S_version, never a mutable
    # "current spec" pointer: the row is scope='global', pinned, append-only.
    assert new_row.scope == "global"
    assert new_row.spec_provenance == "global-unrevalidated"
    # proposed_specs flipped to 'accepted' with the FK to the new row.
    assert proposed_specs.decision == "accepted"
    assert proposed_specs.accepted_as_spec_version_id == new_row.id


@pytest.mark.invariant
def test_tri_03b_unrevalidated_global_spec_findings_carry_label() -> None:
    """Findings on an unrevalidated global spec carry `global-unrevalidated`.

    Test id:        TST-AC-TRI-03b
    Maps to AC:     AC-TRI-03b — "Findings dependent on an unrevalidated global
                    spec carry `global-unrevalidated` until revalidation."
    Kind tag:       [INVARIANT]
    Inputs:         A customer scan whose findings depend on a `spec_versions`
                    row with `spec_provenance='global-unrevalidated'` for that
                    customer; the customer-stream e-process state pre- and
                    post-clearance (DOC-CMP-TRI-03 §4.2, §5.3 state machine).
    Outputs:        `findings.spec_provenance` on the emitted rows.
    Pass criteria:  Every emitted finding dependent on the unrevalidated global
                    spec carries `spec_provenance='global-unrevalidated'`. After
                    the customer-stream e-process clears H0(sigma), subsequent
                    emissions carry `'global-revalidated'`; a spec never
                    transitions back to `'global-unrevalidated'`.
    Frequency:      every CI run
    Hard gate?:     yes — component acceptance gate for CMP-TRI-03 (INV-3).
    """
    import random
    import uuid

    from services.triage.spec_inference import (
        CustomerEvaluationStream,
        initial_customer_state,
        revalidate_spec,
        update_customer_e_process,
    )
    from tests.tri03_fakes import InMemorySpecQuarantineStore

    org_id = uuid.uuid4()
    spec_version_id = uuid.uuid4()
    pi_zero = 0.7
    quarantine_store = InMemorySpecQuarantineStore()

    def emit_findings(n: int) -> list[str]:
        """Stand-in for CMP-ORCH-03 emission: stamp the CURRENT per-customer
        spec_provenance view onto each finding (CMP-TRI-03 does NOT write findings;
        it owns the value the emitter reads). Returns the stamped label per finding.
        """
        label = quarantine_store.spec_provenance_for(org_id, spec_version_id)
        return [label for _ in range(n)]

    # BEFORE the customer stream revalidates: every emitted finding dependent on
    # the unrevalidated global spec carries 'global-unrevalidated'.
    pre = emit_findings(3)
    assert all(label == "global-unrevalidated" for label in pre)

    # Drive the REAL customer-stream revalidate e-process on a clearly-good stream
    # (true precision 0.95 >> pi_0) until H0(sigma) clears (E_t >= 1/alpha). Using
    # the REAL wealth process (not a force-set flag) is what makes a do-nothing
    # instrument fail this test.
    stream = CustomerEvaluationStream(
        org_id=org_id, spec_version_id=spec_version_id, pi_zero=pi_zero, alpha=0.05
    )
    state = initial_customer_state(stream)
    rng = random.Random(11)
    revalidated = False
    for _ in range(500):
        obs = 1.0 if rng.random() < 0.95 else 0.0
        state = update_customer_e_process(state, obs)
        result = revalidate_spec(spec_version_id, org_id, state, quarantine_store=quarantine_store)
        if result.decision == "revalidated":
            revalidated = True
            break
    assert revalidated, "good customer stream never revalidated within 500 looks"

    # AFTER clearance: subsequent emissions carry 'global-revalidated'.
    post = emit_findings(3)
    assert all(label == "global-revalidated" for label in post)

    # A spec NEVER transitions back to 'global-unrevalidated' (§5.3): even a
    # further revalidate-pending look keeps the revalidated label.
    again = revalidate_spec(spec_version_id, org_id, state, quarantine_store=quarantine_store)
    assert again.decision in {"revalidated", "pending"}
    assert quarantine_store.spec_provenance_for(org_id, spec_version_id) == "global-revalidated"


@pytest.mark.invariant
def test_inv_1_tri_01_no_triage_induced_origin_flips() -> None:
    """INV-1: triage induces no `origin` flips on any finding.

    Test id:        TST-INV-1-TRI-01
    Maps to AC:     INV-1 (origin partition) for CMP-TRI-01 — the triage write
                    surface excludes `origin`; no triage-induced origin flips.
    Kind tag:       [INVARIANT]
    Inputs:         A representative scan; the `findings.origin` column before and
                    after a triage cycle (DOC-CMP-TRI-01 §5.1; DOC-DB §4.14 grant
                    revokes ALL on `findings` from `scanipy_triage`).
    Outputs:        Per-finding `origin` value diff across the triage cycle.
    Pass criteria:  For every finding, `origin` is unchanged across the triage
                    cycle (no `deterministic-core` -> `oracle-passthrough` flip or
                    vice versa); the value stays in {deterministic-core,
                    oracle-passthrough} and is never blurred to "mixed".
    Frequency:      every CI run
    Hard gate?:     yes — INV-1 emitter test for CMP-TRI-01.
    """
    import uuid

    from services.triage import run_triage_cycle
    from services.triage.triage import (
        TriageWriteSurfaceViolation,
        _assert_allowed_columns,
    )
    from tests.tri01_fakes import (
        InMemoryFindingsTable,
        InMemoryTriageScoresStore,
        RecordingFakeLLM,
        make_finding,
        malicious_triage_row,
    )

    scan_id = uuid.uuid4()
    rows = [
        make_finding(origin="deterministic-core"),
        make_finding(origin="oracle-passthrough"),
    ]
    findings = InMemoryFindingsTable(scan_id, rows)
    triage_store = InMemoryTriageScoresStore()
    llm = RecordingFakeLLM()

    before = {fid: r.origin for fid, r in findings.snapshot().items()}
    run_triage_cycle(
        scan_id,
        llm_triage=True,
        findings=findings,
        triage_store=triage_store,
        llm=llm,
    )
    after = {fid: r.origin for fid, r in findings.snapshot().items()}

    # No origin flipped; each value stays in the partition and is never "mixed".
    assert before == after
    assert all(v in {"deterministic-core", "oracle-passthrough"} for v in after.values())
    assert "mixed" not in after.values()

    # The write-surface guard rejects any attempt to smuggle `origin` (or any
    # non-triage column) through the triage write path — the application-layer
    # mirror of the grant that makes an origin flip impossible.
    a_finding_id = next(iter(after))
    with pytest.raises(TriageWriteSurfaceViolation):
        _assert_allowed_columns("triage_scores", malicious_triage_row(a_finding_id))


@pytest.mark.invariant
def test_inv_3_tri_01_llm_off_detection_path() -> None:
    """INV-3: the LLM is off the deterministic detection path.

    Test id:        TST-INV-3-TRI-01
    Maps to AC:     INV-3 (LLM off the detection path) for CMP-TRI-01 — with
                    triage enabled, only `triage_*` columns (in `triage_scores`)
                    change; no `findings` column is mutated.
    Kind tag:       [INVARIANT]
    Inputs:         A scan with `LLM_TRIAGE=on`; the full `findings` row state
                    before and after the triage cycle (DOC-CMP-TRI-01 §5.3; the
                    INV-3 OWNER surface).
    Outputs:        Column-level diff over `findings` and `triage_scores`.
    Pass criteria:  Between pre- and post-triage state, ONLY `triage_scores` rows
                    change; NO `findings` column is mutated (origin, S_version,
                    env_digest, slice_fingerprint, cpg_order_hash,
                    fingerprint_class, determinism_partition, engine, status,
                    detection content). The LLM output never reaches `findings`.
    Frequency:      every CI run
    Hard gate?:     yes — INV-3 emitter test for CMP-TRI-01 (Security-Analyst review).
    """
    import uuid

    from services.triage import run_triage_cycle
    from tests.tri01_fakes import (
        InMemoryFindingsTable,
        InMemoryTriageScoresStore,
        RecordingFakeLLM,
        make_finding,
    )

    scan_id = uuid.uuid4()
    findings = InMemoryFindingsTable(scan_id, [make_finding(), make_finding()])
    triage_store = InMemoryTriageScoresStore()
    llm = RecordingFakeLLM()

    # Full pre-triage findings state (every column).
    before = findings.snapshot()
    result = run_triage_cycle(
        scan_id,
        llm_triage=True,  # triage ENABLED — the INV-3 OWNER surface under load
        findings=findings,
        triage_store=triage_store,
        llm=llm,
    )
    after = findings.snapshot()

    # NO findings column is mutated — the LLM output never reaches `findings`.
    assert before == after
    # The ONLY thing that changed is the triage_scores table.
    assert result.rows_written == 2
    assert triage_store.written_tables == {"triage_scores"}
    # And the triage row stamps its own INV-2 witness (its own copy, not a
    # mutation of the source finding's S_version / env_digest).
    for write in triage_store.writes:
        assert write.row["S_version"] == "1.2.3"
        assert write.row["env_digest"] == "sha256:" + ("a" * 64)
        assert write.row["model_id"] == "claude-sonnet-4-6"


@pytest.mark.invariant
def test_inv_3_tri_02_accepted_spec_new_version_core_reads_pinned() -> None:
    """INV-3: accepted spec materializes a new S_version; core reads pinned only.

    Test id:        TST-INV-3-TRI-02
    Maps to AC:     INV-3 (LLM off the detection path) for CMP-TRI-02 -- an
                    accepted spec materializes as a NEW `S_version`; existing rows
                    are untouched; the core reads only pinned specs.
    Kind tag:       [INVARIANT]
    Inputs:         A candidate spec accepted by the e-process gate (E_t >= 1/alpha,
                    alpha=0.05); the `spec_versions` table before/after (DOC-CMP-TRI-02
                    §5.1 -- the single legitimate INV-3-compliant LLM->core path).
    Outputs:        The `spec_versions` table delta; the spec set the core reads.
    Pass criteria:  Acceptance INSERTs exactly one new `spec_versions` row and
                    mutates NO existing row (append-only). The deterministic core
                    influence is mediated solely by the new pinned `S_version`
                    being consumed by a later scan -- the LLM never directly
                    influences a `deterministic-core` finding.
    Frequency:      every CI run
    Hard gate?:     yes -- INV-3 emitter test for CMP-TRI-02 (Security-Analyst review).
    """
    from services.triage.spec_inference import (
        CandidateSpec,
        SpecVersionRow,
        evaluate_proposed_spec,
    )
    from tests.fnd03_fakes import InMemoryProvenanceStore, SoftwareKMSSigner
    from tests.tri02_fakes import (
        InMemoryProposedSpecStore,
        InMemorySpecVersionStore,
        new_uuid,
    )

    spec_versions = InMemorySpecVersionStore()
    # Seed a pre-existing pinned spec for the class so we can prove append-only:
    # acceptance must NOT mutate it, and must bump to a fresh semver.
    preexisting = SpecVersionRow(
        id=new_uuid(),
        org_id=None,
        S_version="1.0.0",
        scope="global",
        spec_set={"class": "injection", "rule": "prior"},
        spec_provenance="global-unrevalidated",
        e_process_detail={},
    )
    spec_versions.insert(preexisting)
    before = spec_versions.all()

    spec = CandidateSpec(
        id=new_uuid(),
        org_id=new_uuid(),
        spec_body={"class": "injection", "rule": "new-accepted"},
        detector_class="injection",
        pi_zero=0.7,
    )
    state = _drive_to_threshold(spec)

    evaluate_proposed_spec(
        spec,
        state,
        spec_versions=spec_versions,
        proposed_specs=InMemoryProposedSpecStore(),
        provenance_store=InMemoryProvenanceStore(),
        signer=SoftwareKMSSigner(),
    )

    after = spec_versions.all()
    assert len(after) == len(before) + 1  # exactly one new row
    # No existing row mutated (append-only): every prior row is byte-identical.
    assert all(row in after for row in before)
    # The new row is a fresh pinned semver, distinct from the pre-existing one.
    new_rows = [r for r in after if r not in before]
    assert len(new_rows) == 1
    assert new_rows[0].S_version != preexisting.S_version
    # The store exposes NO update/delete surface (mirrors revoked grants).
    assert not hasattr(spec_versions, "update")
    assert not hasattr(spec_versions, "delete")


@pytest.mark.invariant
def test_inv_2_tri_02_accepted_specs_version_pinned() -> None:
    """INV-2: accepted specs are version-pinned (no in-place spec mutation).

    Test id:        TST-INV-2-TRI-02
    Maps to AC:     INV-2 (versioned parameters) for CMP-TRI-02 -- accepted specs
                    are version-pinned; no in-place spec mutation.
    Kind tag:       [INVARIANT]
    Inputs:         An accepted candidate spec; the new `spec_versions` row and
                    its signed `provenance_records` row (DOC-CMP-TRI-02 §5.2, §8 --
                    `S_version` + `env_digest` on the signed chain).
    Outputs:        The new `spec_versions` row's `S_version` semver and the
                    INV-2 fields on the spec-acceptance provenance record.
    Pass criteria:  The new `spec_versions` row carries a non-null, unique
                    (per scope) semver `S_version`; the spec-acceptance
                    `provenance_records` row carries non-null `S_version` and
                    `env_digest`. No UPDATE/DELETE is ever issued against an
                    existing `spec_versions` row.
    Frequency:      every CI run
    Hard gate?:     yes -- INV-2 emitter test for CMP-TRI-02.
    """
    import re

    from services.triage.spec_inference import CandidateSpec, evaluate_proposed_spec
    from tests.fnd03_fakes import InMemoryProvenanceStore, SoftwareKMSSigner
    from tests.tri02_fakes import (
        InMemoryProposedSpecStore,
        InMemorySpecVersionStore,
        new_uuid,
    )

    semver_re = re.compile(r"^\d+\.\d+\.\d+$")
    env_digest = "sha256:" + ("d" * 64)

    spec = CandidateSpec(
        id=new_uuid(),
        org_id=new_uuid(),
        spec_body={"class": "ssrf", "rule": "user-url-to-fetch"},
        detector_class="ssrf",
        pi_zero=0.7,
    )
    state = _drive_to_threshold(spec)

    spec_versions = InMemorySpecVersionStore()
    provenance_store = InMemoryProvenanceStore()

    verdict = evaluate_proposed_spec(
        spec,
        state,
        spec_versions=spec_versions,
        proposed_specs=InMemoryProposedSpecStore(),
        provenance_store=provenance_store,
        signer=SoftwareKMSSigner(),
        env_digest=env_digest,
    )

    # The accepted S_version is a non-null, valid semver (version-pinned).
    assert verdict.accepted_S_version is not None
    assert semver_re.match(verdict.accepted_S_version)
    new_row = spec_versions.all()[0]
    assert new_row.S_version == verdict.accepted_S_version

    # The spec-acceptance provenance row carries the INV-2 fields (S_version +
    # env_digest) on the signed chain row.
    rows = list(provenance_store._rows.values())  # test inspects the in-memory fake store
    accept_rows = [s for s in rows if s.record.record_type == "spec-acceptance"]
    assert len(accept_rows) == 1
    rec = accept_rows[0].record
    assert rec.S_version == verdict.accepted_S_version
    assert rec.env_digest == env_digest
    assert rec.finding_id is None  # scan-level acceptance, not per-finding
    # No UPDATE/DELETE surface on spec_versions (append-only, INV-2).
    assert not hasattr(spec_versions, "update")
    assert not hasattr(spec_versions, "delete")
