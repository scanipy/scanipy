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


@pytest.mark.invariant
@pytest.mark.xfail(
    reason="CMP-TRI-01 (LLM triage ranking) not yet implemented",
    strict=False,
)
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
    # TODO: import from services.triage when CMP-TRI-01 is DONE
    # from services.triage import run_triage_cycle
    # before = snapshot_findings(scan_id)
    # run_triage_cycle(scan_id, llm_triage=False)
    # after = snapshot_findings(scan_id)
    # assert before == after  # no origin / detection / status change
    pytest.skip("CMP-TRI-01 not implemented yet")


@pytest.mark.invariant
@pytest.mark.xfail(
    reason="CMP-TRI-01 (LLM triage ranking) not yet implemented",
    strict=False,
)
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
                    permission error; no insert targets `provenance_records`,
                    `spec_versions`, or `proposed_specs`.
    Frequency:      every CI run
    Hard gate?:     yes — component acceptance gate for CMP-TRI-01 (INV-3).
    """
    # TODO: assert set(written.keys()) <= ALLOWED_TRIAGE_COLUMNS
    # TODO: assert written.table == "triage_scores"
    # TODO: with pytest.raises(PermissionError): triage_role.update("findings", ...)
    pytest.skip("CMP-TRI-01 not implemented yet")


@pytest.mark.invariant
@pytest.mark.xfail(
    reason="CMP-TRI-02 (e-process spec gate) not yet implemented",
    strict=False,
)
def test_tri_02c_accepted_spec_version_pinned_core_reads_pinned_only() -> None:
    """Accepted spec written version-pinned; the core only consumes pinned specs.

    Test id:        TST-AC-TRI-02c
    Maps to AC:     AC-TRI-02c — "An accepted spec is written version-pinned as a
                    new `S_version`; the deterministic core only ever consumes
                    pinned specs (INV-3)."
    Kind tag:       [INVARIANT]
    Inputs:         A candidate spec whose e-process wealth has crossed
                    `E_t(sigma) >= 1/alpha` (alpha=0.05 ⇒ threshold 20.0); the `spec_versions`
                    table before acceptance (DOC-CMP-TRI-02 §3.1, §4.2).
    Outputs:        The `spec_versions` table after acceptance; the `S_version`
                    set the deterministic core reads for a subsequent scan.
    Pass criteria:  Acceptance materializes exactly one NEW `spec_versions` row
                    with a fresh semver `S_version` (no existing row mutated); the
                    `proposed_specs.decision` flips to 'accepted' with an FK to the
                    new row; and the core consumes the spec ONLY via the pinned
                    `S_version` (never a mutable "current spec" pointer).
    Frequency:      every CI run
    Hard gate?:     yes — standard release gate for CMP-TRI-02 (INV-3).
    """
    # TODO: from services.triage.spec_inference import evaluate_proposed_spec
    # verdict = evaluate_proposed_spec(spec, state_at_threshold)
    # assert verdict.decision == "accepted"
    # assert verdict.accepted_S_version is not None  # new pinned semver
    # assert spec_versions_unchanged_except_one_new_row(before, after)
    pytest.skip("CMP-TRI-02 not implemented yet")


@pytest.mark.invariant
@pytest.mark.xfail(
    reason="CMP-TRI-03 (per-customer revalidation + drift) not yet implemented",
    strict=False,
)
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
    # TODO: emit findings on a 'global-unrevalidated' spec_versions row
    # assert all(f.spec_provenance == "global-unrevalidated" for f in findings)
    # TODO: after customer-stream e-process clears -> 'global-revalidated'
    pytest.skip("CMP-TRI-03 not implemented yet")


@pytest.mark.invariant
@pytest.mark.xfail(
    reason="CMP-TRI-01 (LLM triage ranking) not yet implemented",
    strict=False,
)
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
    # TODO: before = {f.id: f.origin for f in findings}
    # run_triage_cycle(scan_id)
    # after = {f.id: f.origin for f in findings}
    # assert before == after
    pytest.skip("CMP-TRI-01 not implemented yet")


@pytest.mark.invariant
@pytest.mark.xfail(
    reason="CMP-TRI-01 (LLM triage ranking) not yet implemented",
    strict=False,
)
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
    # TODO: before = snapshot_findings_all_columns(scan_id)
    # run_triage_cycle(scan_id, llm_triage=True)
    # after = snapshot_findings_all_columns(scan_id)
    # assert before == after  # findings untouched; only triage_scores changed
    pytest.skip("CMP-TRI-01 not implemented yet")


@pytest.mark.invariant
@pytest.mark.xfail(
    reason="CMP-TRI-02 (e-process spec gate) not yet implemented",
    strict=False,
)
def test_inv_3_tri_02_accepted_spec_new_version_core_reads_pinned() -> None:
    """INV-3: accepted spec materializes a new S_version; core reads pinned only.

    Test id:        TST-INV-3-TRI-02
    Maps to AC:     INV-3 (LLM off the detection path) for CMP-TRI-02 — an
                    accepted spec materializes as a NEW `S_version`; existing rows
                    are untouched; the core reads only pinned specs.
    Kind tag:       [INVARIANT]
    Inputs:         A candidate spec accepted by the e-process gate (E_t >= 1/alpha,
                    alpha=0.05); the `spec_versions` table before/after (DOC-CMP-TRI-02
                    §5.1 — the single legitimate INV-3-compliant LLM->core path).
    Outputs:        The `spec_versions` table delta; the spec set the core reads.
    Pass criteria:  Acceptance INSERTs exactly one new `spec_versions` row and
                    mutates NO existing row (append-only). The deterministic core
                    influence is mediated solely by the new pinned `S_version`
                    being consumed by a later scan — the LLM never directly
                    influences a `deterministic-core` finding.
    Frequency:      every CI run
    Hard gate?:     yes — INV-3 emitter test for CMP-TRI-02 (Security-Analyst review).
    """
    # TODO: before = list(spec_versions.all())
    # evaluate_proposed_spec(spec, state_at_threshold)
    # after = list(spec_versions.all())
    # assert len(after) == len(before) + 1  # exactly one new row
    # assert all(row in after for row in before)  # no existing row mutated
    pytest.skip("CMP-TRI-02 not implemented yet")


@pytest.mark.invariant
@pytest.mark.xfail(
    reason="CMP-TRI-02 (e-process spec gate) not yet implemented",
    strict=False,
)
def test_inv_2_tri_02_accepted_specs_version_pinned() -> None:
    """INV-2: accepted specs are version-pinned (no in-place spec mutation).

    Test id:        TST-INV-2-TRI-02
    Maps to AC:     INV-2 (versioned parameters) for CMP-TRI-02 — accepted specs
                    are version-pinned; no in-place spec mutation.
    Kind tag:       [INVARIANT]
    Inputs:         An accepted candidate spec; the new `spec_versions` row and
                    its signed `provenance_records` row (DOC-CMP-TRI-02 §5.2, §8 —
                    `S_version` + `env_digest` on the signed chain).
    Outputs:        The new `spec_versions` row's `S_version` semver and the
                    INV-2 fields on the spec-acceptance provenance record.
    Pass criteria:  The new `spec_versions` row carries a non-null, unique
                    (per scope) semver `S_version`; the spec-acceptance
                    `provenance_records` row carries non-null `S_version` and
                    `env_digest`. No UPDATE/DELETE is ever issued against an
                    existing `spec_versions` row.
    Frequency:      every CI run
    Hard gate?:     yes — INV-2 emitter test for CMP-TRI-02.
    """
    # TODO: verdict = evaluate_proposed_spec(spec, state_at_threshold)
    # assert verdict.accepted_S_version is not None
    # assert is_valid_semver(verdict.accepted_S_version)
    # assert provenance_record.S_version and provenance_record.env_digest
    pytest.skip("CMP-TRI-02 not implemented yet")
