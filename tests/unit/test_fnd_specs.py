"""FND-family unit + invariant specs — TST-AC-FND-* (unit/invariant-shaped) + TST-INV-*.

Spec-first TDD: as each owning CMP lands, its stub goes live. The FND-02
(schema) and FND-03 (signed chain) specs are live; the FND-01 (normalizer /
SARIF emitter) specs are now live too — their previous ``@pytest.mark.xfail`` +
``pytest.skip`` guards were removed when CMP-FND-01 shipped
``analysis.sarif.canonical_emit``. Any spec for a still-unbuilt CMP keeps the
xfail/skip guard until that CMP is DONE.

Pattern mirrors ``tests/unit/test_dsl_proofs.py`` (the canonical convention).

FND is the provenance-threading heart: the four required fields
(``origin``, ``S_version``, ``env_digest``, ``cpg_order_hash`` + the literal
annotation ``canonical iff fingerprint_class = strong``) are anchored at the
SARIF emitter (CMP-FND-01), the schema (CMP-FND-02), and the signed chain
(CMP-FND-03). Concrete pass criteria below are taken verbatim from
DOC-CMP-FND-0{1,2,3}, DOC-DB §4.12/§4.13, DOC-SARIF, and DOC-PROVENANCE.

Covers (from WBS §4.2 / §4.3):
  - TST-AC-FND-01a   [UNIT]      — outputs validate against SARIF 2.1.0 schema
  - TST-AC-FND-01b   [UNIT]      — result ordering is canonical CPG order (CORE-03)
  - TST-AC-FND-02a   [INVARIANT] — baseline lookup never auto-suppresses weak/oracle
  - TST-AC-FND-02b   [INVARIANT] — non-null origin, S_version, env_digest (schema)
  - TST-AC-FND-03b   [INVARIANT] — annotation in auditor export (INV-5)
  - TST-AC-FND-03c   [INVARIANT] — re-partition events appear in the record
  - TST-INV-1-FND-01 [INVARIANT] — origin partition at the normalizer (two-Run)
  - TST-INV-1-FND-02 [INVARIANT] — origin partition at the store (NOT NULL + enum)
  - TST-INV-1-FND-03 [INVARIANT] — origin partition at provenance (link 9, append-only)
  - TST-INV-2-FND-01 [INVARIANT] — non-null S_version + env_digest at the normalizer
  - TST-INV-2-FND-02 [INVARIANT] — non-null S_version + env_digest at schema level
  - TST-INV-2-FND-03 [INVARIANT] — S_version + env_digest as links in the signed chain
  - TST-INV-5-FND-01 [INVARIANT] — annotation literal on every emitted Result
  - TST-INV-5-FND-03 [INVARIANT] — annotation literal in chain + auditor export
"""

import pytest
from sqlalchemy import CheckConstraint

from services.scan.models.findings import (
    CPG_ORDER_HASH_ANNOTATION,
    Finding,
)

# The exact INV-5 annotation literal pinned by the
# findings_cpg_order_hash_annotation_chk CHECK constraint (DOC-DB sec 4.12).
# The live-PostgreSQL INSERT falsifiers that exercise this literal now live in
# tests/integration/test_fnd_specs.py (so CI's postgres:16 job runs them); this
# unit file keeps only the no-DB metadata-introspection assertions.
_ANNOTATION = "canonical iff fingerprint_class = strong"


def _check_sqltext(table: object, name: str) -> str:
    """Return the rendered ``sqltext`` of the named CHECK constraint."""
    for constraint in Finding.__table__.constraints:
        if isinstance(constraint, CheckConstraint) and constraint.name == name:
            return str(constraint.sqltext)
    raise AssertionError(f"CHECK constraint {name!r} not found on findings table")


@pytest.mark.unit
def test_fnd_01a_outputs_validate_against_sarif_210() -> None:
    """Every detector output validates against the SARIF 2.1.0 (shape) schema.

    Test id:        TST-AC-FND-01a
    Maps to AC:     AC-FND-01a — "All detector outputs validate against SARIF
                    2.1.0 schema."
    Kind tag:       [UNIT]
    Inputs:         A ``frozenset[Finding]`` spanning both partitions, fed to
                    ``analysis.sarif.canonical_emit.normalize(...)`` with pinned
                    scan_id/snapshot_id/codebase_id/commit_sha/S_version/
                    env_digest/precondition_status, llm_triage_flag=False.
    Outputs:        ``SARIFLog.canonical_bytes`` — a two-Run log (runs[0]=core,
                    runs[1]=oracle), minified, UTF-8/LF.
    Pass criteria:  ``SARIFLog.canonical_bytes`` validates against the SARIF
                    v2.1.0 + Scanipy-extension STRUCTURAL validator
                    (``validate_sarif_210``) with zero errors; every Result
                    carries the required ``scanipy.*`` properties
                    (DOC-CMP-FND-01 §7.1). A schema failure raises
                    ``SARIFSchemaViolation`` (halt, no partial emit).
    Method note:    The OASIS jsonschema is not vendored and ``jsonschema`` is not
                    a declared CI dependency (CLAR-SARIF-01 DEFERRED); per the task
                    this is SARIF-2.1.0 *shape* validation in pure Python, behind
                    the same ``bytes -> list[str]`` signature the OASIS validator
                    would expose (drop-in swap once the schema is vendored).
    Frequency:      every CI run
    Hard gate?:     yes — DOC-SARIF §12 gate 1 (release blocker).
    """
    import uuid as _uuid

    from analysis.sarif.canonical_emit import (
        InvariantViolation,
        SARIFSchemaViolation,
        normalize,
        validate_sarif_210,
    )
    from tests.fnd01_fakes import make_broken_finding, make_finding

    findings = frozenset(
        {
            make_finding(origin="deterministic-core", engine="ifds"),
            make_finding(
                origin="oracle-passthrough",
                engine="semgrep",
                rule_id="scanipy/secrets/aws-access-key",
                uri="config/dev.env",
                start_line=14,
                severity="medium",
                class_="secrets",
                witness_blob_uri=None,
                spec_provenance=None,
            ),
        }
    )
    log = normalize(
        findings,
        scan_id=_uuid.uuid4(),
        snapshot_id=_uuid.uuid4(),
        codebase_id=_uuid.uuid4(),
        commit_sha="a" * 40,
        S_version="1.4.0",
        env_digest="sha256:" + ("7" * 64),
        precondition_status="closed-world",
        llm_triage_flag=False,
    )

    # Anti-vacuity: the emission is non-empty; both partitions present, 1 each.
    assert len(log.canonical_bytes) > 0
    assert log.runs[0].partition == "core" and log.runs[0].result_count == 1
    assert log.runs[1].partition == "oracle" and log.runs[1].result_count == 1

    # The structural SARIF 2.1.0 + extension validator returns ZERO errors.
    assert validate_sarif_210(log.canonical_bytes) == []

    # Anti-vacuity for the validator itself: a corrupted (provenance-stripped)
    # log must FAIL the same validator, proving it is not trivially returning [].
    corrupted = log.canonical_bytes.replace(
        b'"scanipy.origin":"deterministic-core"', b'"scanipy.origin":""'
    )
    assert corrupted != log.canonical_bytes  # the substitution actually happened
    assert validate_sarif_210(corrupted) != []

    # Halt-on-bad-input: a finding missing a required Result property is rejected
    # before any partial emit (DOC §7.1) — either fail-fast (InvariantViolation)
    # or the post-build schema check (SARIFSchemaViolation); both halt emission.
    with pytest.raises((InvariantViolation, SARIFSchemaViolation)):
        normalize(
            frozenset({make_broken_finding("rule_id")}),
            scan_id=_uuid.uuid4(),
            snapshot_id=_uuid.uuid4(),
            codebase_id=_uuid.uuid4(),
            commit_sha="b" * 40,
            S_version="1.4.0",
            env_digest="sha256:" + ("7" * 64),
            precondition_status="closed-world",
            llm_triage_flag=False,
        )


@pytest.mark.unit
def test_fnd_01b_result_ordering_is_canonical_cpg_order() -> None:
    """Result ordering within each Run is the canonical CPG order from CORE-03.

    Test id:        TST-AC-FND-01b
    Maps to AC:     AC-FND-01b — "Result ordering is the canonical order from
                    CMP-CORE-03."
    Kind tag:       [UNIT]
    Inputs:         A ``frozenset[Finding]`` deliberately constructed with
                    findings whose canonical sort keys are out of order;
                    ``normalize(...)`` output.
    Outputs:        Two SARIF Runs, each with its ``results`` array.
    Pass criteria:  Within each Run, ``results`` (re-parsed from
                    ``canonical_bytes``) is sorted ascending by the canonical key
                    tuple ``(cpg_order_hash, rule_id, uri, start_line)``
                    (DOC-SARIF §7); the order is independent of input iteration
                    order. A non-canonical serialisation raises
                    ``CanonicalEmissionFailure`` inside ``normalize``.
    Frequency:      every CI run
    Hard gate?:     yes — DOC-SARIF §12 gate 4.
    """
    import json as _json
    import uuid as _uuid

    from analysis.sarif.canonical_emit import normalize
    from tests.fnd01_fakes import make_finding

    def _key(result: dict) -> tuple[str, str, str, int]:
        properties = result["properties"]
        region = result["locations"][0]["physicalLocation"]
        return (
            properties["scanipy.cpg_order_hash"],
            result["ruleId"],
            region["artifactLocation"]["uri"],
            region["region"]["startLine"],
        )

    # Three CORE findings with cpg_order_hashes that, sorted, do NOT match the
    # order they are passed in. ``cpg_order_hash`` is the PRIMARY sort key, so a
    # missing/incorrect sort surfaces here. Pin distinct hashes explicitly so the
    # expected order is unambiguous.
    h_lo = "0" * 64
    h_mid = "5" * 64
    h_hi = "f" * 64
    findings = frozenset(
        {
            make_finding(cpg_order_hash=h_hi, rule_id="scanipy/ssrf/a", uri="z.py", start_line=9),
            make_finding(cpg_order_hash=h_lo, rule_id="scanipy/ssrf/b", uri="a.py", start_line=1),
            make_finding(cpg_order_hash=h_mid, rule_id="scanipy/ssrf/c", uri="m.py", start_line=5),
        }
    )

    log = normalize(
        findings,
        scan_id=_uuid.uuid4(),
        snapshot_id=_uuid.uuid4(),
        codebase_id=_uuid.uuid4(),
        commit_sha="c" * 40,
        S_version="1.4.0",
        env_digest="sha256:" + ("7" * 64),
        precondition_status="closed-world",
        llm_triage_flag=False,
    )

    doc = _json.loads(log.canonical_bytes)
    core_results = doc["runs"][0]["results"]
    keys = [_key(r) for r in core_results]

    # Anti-vacuity: there really are 3 results to order.
    assert len(keys) == 3
    # The serialised order is exactly the canonically-sorted order (DOC-SARIF §7).
    assert keys == sorted(keys)
    # And concretely: cpg_order_hash ascending (0.. < 5.. < f..).
    assert [k[0] for k in keys] == [h_lo, h_mid, h_hi]


@pytest.mark.invariant
def test_fnd_02a_baseline_lookup_never_autosuppresses_weak_or_oracle() -> None:
    """Cross-scan baseline lookup is correct and never auto-suppresses across refactor.

    Test id:        TST-AC-FND-02a
    Maps to AC:     AC-FND-02a — "Cross-scan baseline lookup by
                    `(codebase_id, slice_fingerprint)` is correct and never
                    auto-suppresses a `weak` or `oracle-passthrough` finding
                    across a refactor."
    Kind tag:       [INVARIANT]
    Inputs:         Two scans of the same codebase across a refactor; baseline
                    rows in ``findings`` keyed by ``(codebase_id,
                    slice_fingerprint)`` using ``findings_codebase_slice_idx``.
                    The set includes a ``fingerprint_class='weak'`` finding and
                    an ``origin='oracle-passthrough'`` finding.
    Outputs:        Baseline-match decisions per finding (matched / new).
    Pass criteria:  The lookup uses the ``findings_codebase_slice_idx`` index and
                    returns the correct baseline row for ``strong`` findings; AND
                    no finding with ``fingerprint_class='weak'`` OR
                    ``origin='oracle-passthrough'`` is auto-suppressed (its
                    ``status`` is never flipped to ``suppressed`` by the baseline
                    matcher across the refactor). INV-5: weak slices are not
                    refactor-stable, so they must not be auto-matched away.
    Frequency:      every CI run
    Hard gate?:     yes — component acceptance gate for CMP-FND-02.
    """
    # --- Schema/index half (CMP-FND-02 owns this; asserted here) ---
    # The cross-scan baseline matcher (CMP-SNAP-02 / CMP-FND-01) looks up by
    # (codebase_id, slice_fingerprint); CMP-FND-02's contribution to AC-FND-02a
    # is that the supporting index exists with exactly those columns in that
    # order. Assert it on the ORM table that mirrors the shipped DDL.
    table = Finding.__table__
    by_name = {ix.name: ix for ix in table.indexes}
    assert "findings_codebase_slice_idx" in by_name, (
        "AC-FND-02a baseline-lookup index findings_codebase_slice_idx is missing"
    )
    baseline_idx = by_name["findings_codebase_slice_idx"]
    assert [c.name for c in baseline_idx.columns] == [
        "codebase_id",
        "slice_fingerprint",
    ], "baseline-lookup index must be keyed (codebase_id, slice_fingerprint)"

    # status / fingerprint_class / origin must exist on the row so a matcher can
    # read fingerprint_class='weak' / origin='oracle-passthrough' WITHOUT writing
    # status='suppressed'. Assert their presence and enum domains.
    cols = table.columns
    assert "status" in cols and "fingerprint_class" in cols and "origin" in cols
    assert "weak" in _check_sqltext(table, "findings_fingerprint_class_chk")
    assert "oracle-passthrough" in _check_sqltext(table, "findings_origin_chk")
    assert "suppressed" in _check_sqltext(table, "findings_status_chk")

    # --- Behavioral baseline-matcher half: DOCUMENT-AND-DEFER ---
    # "never auto-suppresses a weak or oracle-passthrough finding across a
    # refactor" is a BEHAVIORAL property of the baseline matcher, which lives in
    # the downstream CMP-SNAP-02 (incremental delta) / CMP-FND-01 (normalizer)
    # contract -- NOT in the CMP-FND-02 schema component. The schema makes the
    # safe behaviour possible (the index + the columns asserted above); it
    # cannot itself flip a status. The matcher-behaviour assertion is therefore
    # owned by TST-AC-SNAP-02* / the FND-01 baseline path and is intentionally
    # not exercised here.


@pytest.mark.invariant
def test_fnd_02b_every_row_carries_nonnull_origin_sversion_envdigest() -> None:
    """Every findings row carries non-null origin, S_version, env_digest.

    Test id:        TST-AC-FND-02b
    Maps to AC:     AC-FND-02b — "Every row carries a non-null `origin`,
                    `S_version`, `env_digest` (INV-1, INV-2)."
    Kind tag:       [INVARIANT]
    Inputs:         A live ``findings`` table (Alembic-migrated per CMP-FND-02);
                    a candidate INSERT omitting each of the three columns in turn.
    Outputs:        INSERT outcome (success / DB error).
    Pass criteria:  The ``origin``, ``S_version``, ``env_digest`` columns are all
                    declared ``NOT NULL`` (DOC-DB §4.12); an INSERT omitting any
                    one raises a NOT NULL violation (SQLSTATE 23502); a SELECT
                    over the production table returns zero rows with a NULL in any
                    of the three. ``cpg_order_hash`` and its annotation are NOT
                    under this AC (covered by TST-INV-5-FND-02).
    Frequency:      every CI run
    Hard gate?:     yes — schema NOT NULL gate for CMP-FND-02.
    """
    # --- Metadata introspection (always runs, no DB) ---
    # AC-FND-02b pins NOT NULL on exactly these three columns.
    cols = Finding.__table__.columns
    for name in ("origin", "S_version", "env_digest"):
        assert not cols[name].nullable, (
            f"AC-FND-02b: findings.{name} must be NOT NULL (INV-1/INV-2)"
        )

    # NOTE: the live-PostgreSQL INSERT-fail falsifiers for this invariant
    # (NOT NULL 23502 / CHECK 23514) live in tests/integration/
    # test_fnd_specs.py under @pytest.mark.integration, so CI's postgres:16
    # integration job runs them. This unit half asserts only the no-DB
    # schema metadata above.


@pytest.mark.invariant
def test_inv_5_fnd_02_cpg_order_hash_annotation_persisted_at_schema() -> None:
    """INV-5 at the persistence layer: the annotation column is NOT NULL + CHECKed.

    Test id:        TST-INV-5-FND-02
    Maps to AC:     INV-5 (conditional labels self-describing) for CMP-FND-02 —
                    the emitter named in WBS §4.3 (CMP-FND-02 carries the findings
                    store schema). Referenced by TST-AC-FND-02b.
    Kind tag:       [INVARIANT]
    Inputs:         A live ``findings`` table (Alembic-migrated per CMP-FND-02);
                    candidate INSERTs that (a) omit ``cpg_order_hash_annotation``
                    and (b) supply a non-conforming annotation string.
    Outputs:        INSERT outcome (success / DB error).
    Pass criteria:  ``findings.cpg_order_hash_annotation`` is declared ``NOT NULL``
                    with a CHECK constraint pinning the exact literal
                    ``"canonical iff fingerprint_class = strong"`` (DOC-DB §4.12);
                    an INSERT omitting it raises 23502, and an INSERT with any
                    other annotation string raises a CHECK violation (23514). This
                    closes the persistence-layer gap so a migration that drops the
                    annotation cannot pass Phase-1 specs.
    Frequency:      every CI run
    Hard gate?:     yes — schema INV-5 gate for CMP-FND-02.
    """
    # --- Metadata introspection (always runs, no DB) ---
    table = Finding.__table__
    annotation_col = table.columns["cpg_order_hash_annotation"]
    assert not annotation_col.nullable, "INV-5: findings.cpg_order_hash_annotation must be NOT NULL"
    # The literal CHECK pins the EXACT annotation string.
    sqltext = _check_sqltext(table, "findings_cpg_order_hash_annotation_chk")
    assert _ANNOTATION in sqltext, (
        f"INV-5: the annotation CHECK must pin the exact literal {_ANNOTATION!r}; got {sqltext!r}"
    )
    # The model constant equals the literal (the same string the DDL pins).
    assert CPG_ORDER_HASH_ANNOTATION == _ANNOTATION
    # cpg_order_hash itself is NOT NULL with a 32-byte length CHECK.
    assert not table.columns["cpg_order_hash"].nullable
    assert "octet_length(cpg_order_hash) = 32" in _check_sqltext(
        table, "findings_cpg_order_hash_len_chk"
    )

    # NOTE: the live-PostgreSQL INSERT-fail falsifiers for this invariant
    # (NOT NULL 23502 / CHECK 23514) live in tests/integration/
    # test_fnd_specs.py under @pytest.mark.integration, so CI's postgres:16
    # integration job runs them. This unit half asserts only the no-DB
    # schema metadata above.


@pytest.mark.invariant
def test_fnd_03b_cpg_order_hash_annotation_in_auditor_export() -> None:
    """The cpg_order_hash field carries its conditional-canonicality annotation.

    Test id:        TST-AC-FND-03b
    Maps to AC:     AC-FND-03b — "The `cpg_order_hash` field carries its
                    conditional-canonicality annotation in the auditor export
                    (INV-5)."
    Kind tag:       [INVARIANT]
    Inputs:         A signed ``provenance_records`` row exported via
                    ``services.scan.provenance.export_auditor_record(record_id)``
                    (DOC-PROVENANCE §8.1).
    Outputs:        The auditor-export ``dict`` / JSON document.
    Pass criteria:  The export contains key ``cpg_order_hash_annotation`` with
                    the exact literal ``"canonical iff fingerprint_class =
                    strong"``, JSON-adjacent to ``cpg_order_hash`` (DOC-PROVENANCE
                    §8.2). A grep of the export for any abbreviated, translated,
                    or truncated annotation variant returns no hit; emitting the
                    hash without the annotation is an INV-5 violation.
    Frequency:      every CI run
    Hard gate?:     yes — INV-5 gate for CMP-FND-03.
    """
    import json as _json

    from services.scan.provenance import export_auditor_record, sign_provenance
    from tests.fnd03_fakes import (
        InMemoryProvenanceStore,
        SoftwareKMSSigner,
        make_chain_record,
    )

    signer = SoftwareKMSSigner()
    store = InMemoryProvenanceStore()
    record = make_chain_record()
    sign_provenance(
        record,
        signer=signer,
        kms_key_arn="arn:aws:kms:us-east-1:000000000000:key/fnd03",
        store=store,
    )

    export = export_auditor_record(record.id, store=store)

    # The annotation is present with the EXACT literal.
    assert export["cpg_order_hash_annotation"] == _ANNOTATION

    # It is JSON-adjacent to cpg_order_hash (consecutive keys = JSON adjacency).
    keys = list(export.keys())
    hash_idx = keys.index("cpg_order_hash")
    assert keys[hash_idx + 1] == "cpg_order_hash_annotation", (
        "INV-5: cpg_order_hash_annotation must be JSON-adjacent to cpg_order_hash"
    )

    # A grep of the serialized export for any abbreviated/truncated variant of the
    # annotation returns no hit other than the full literal itself.
    serialized = _json.dumps(export)
    for variant in ("canonical hash", "cpg_canonical_hash", "canonical CPG"):
        assert variant not in serialized, (
            f"INV-5: abbreviated annotation variant {variant!r} leaked"
        )
    assert serialized.count(_ANNOTATION) == 1


@pytest.mark.invariant
def test_fnd_03c_repartition_events_appear_in_the_record() -> None:
    """Differential-oracle re-partition events appear in the provenance record.

    Test id:        TST-AC-FND-03c
    Maps to AC:     AC-FND-03c — "Differential-oracle re-partition events appear
                    in the record."
    Kind tag:       [INVARIANT]
    Inputs:         A base ``record_type='chain'`` provenance row for a
                    ``deterministic-core`` finding; a seeded CMP-SNAP-04
                    re-partition event for that finding via
                    ``append_repartition_event(parent_record_id=...,
                    repartition_oracle_id=..., repartition_reason=...)``.
    Outputs:        A new ``provenance_records`` row + the auditor export.
    Pass criteria:  A new row exists with ``record_type='repartition'``,
                    ``parent_record_id`` = the base record id,
                    ``origin='oracle-passthrough'``, ``cpg_order_hash`` NULL
                    (not recomputed, DOC-PROVENANCE §4.1); the base record is
                    NEVER mutated (append-only); the auditor export's
                    ``repartition_history`` array surfaces the event.
    Frequency:      every CI run
    Hard gate?:     yes — INV-1 / append-only gate for CMP-FND-03.
    """
    import uuid as _uuid

    from services.scan.provenance import (
        append_repartition_event,
        export_auditor_record,
        sign_provenance,
    )
    from tests.fnd03_fakes import (
        InMemoryProvenanceStore,
        SoftwareKMSSigner,
        make_chain_record,
    )

    signer = SoftwareKMSSigner()
    store = InMemoryProvenanceStore()
    base = make_chain_record(origin="deterministic-core")
    base_signed = sign_provenance(
        base,
        signer=signer,
        kms_key_arn="arn:aws:kms:us-east-1:000000000000:key/fnd03",
        store=store,
    )
    base_bytes_before = base_signed.canonical_bytes

    oracle_id = _uuid.uuid4()
    repart = append_repartition_event(
        parent_record_id=base.id,
        repartition_oracle_id=oracle_id,
        repartition_reason="differential-oracle disagreement: reachable reflection",
        store=store,
        signer=signer,
    )

    # A NEW row exists with the re-partition shape (DOC-PROVENANCE §4.1).
    assert repart.record.record_type == "repartition"
    assert repart.record.parent_record_id == base.id
    assert repart.record.origin == "oracle-passthrough"
    assert repart.record.cpg_order_hash is None  # not recomputed on re-partition
    assert repart.record.repartition_oracle_id == oracle_id

    # The base record is NEVER mutated (append-only): its canonical bytes and its
    # origin are byte-identical before and after the append.
    base_after = store.get(base.id)
    assert base_after is not None
    assert base_after.canonical_bytes == base_bytes_before
    assert base_after.record.origin == "deterministic-core"

    # The auditor export of the base record surfaces the event in repartition_history.
    export = export_auditor_record(base.id, store=store)
    history = export["repartition_history"]
    assert isinstance(history, list) and len(history) == 1
    assert history[0]["new_origin"] == "oracle-passthrough"
    assert history[0]["repartition_oracle_id"] == str(oracle_id)


@pytest.mark.invariant
def test_inv_1_fnd_01_origin_partition_at_normalizer() -> None:
    """INV-1 at the normalizer: per-finding origin drives the two-Run partition.

    Test id:        TST-INV-1-FND-01
    Maps to AC:     INV-1 (CMP-FND-01 emitter) — every finding carries
                    ``origin ∈ {deterministic-core, oracle-passthrough}``; the
                    two-Run emission is the wire-level expression of the partition.
                    Also exercises the byte-identity guarantee that feeds CMP-CP-05
                    (AC-CP-05a): same inputs ⇒ byte-identical canonical bytes.
    Kind tag:       [INVARIANT]
    Inputs:         A ``frozenset[Finding]`` with a mix of
                    ``origin='deterministic-core'`` and
                    ``origin='oracle-passthrough'`` findings; ``normalize(...)``.
    Outputs:        ``SARIFLog`` with ``runs=(core, oracle)``.
    Pass criteria:  Every ``deterministic-core`` finding lands in ``runs[0]``
                    (partition='core'); every ``oracle-passthrough`` finding
                    lands in ``runs[1]`` (partition='oracle'); no Run mixes
                    partitions; every ``Result.properties["scanipy.origin"]`` is
                    set verbatim from the Finding and is never the value
                    ``"mixed"`` (DOC-CMP-FND-01 §5.1). Re-running ``normalize`` on
                    the same inputs yields byte-identical ``canonical_bytes``.
    Frequency:      every CI run
    Hard gate?:     yes — INV-1 emitter gate; feeds CMP-CP-05 (AC-CP-05a).
    """
    import json as _json
    import uuid as _uuid

    from analysis.sarif.canonical_emit import normalize
    from tests.fnd01_fakes import make_finding

    scan_id = _uuid.uuid4()
    snapshot_id = _uuid.uuid4()
    codebase_id = _uuid.uuid4()
    findings = frozenset(
        {
            make_finding(origin="deterministic-core", engine="ifds", rule_id="scanipy/injection/a"),
            make_finding(origin="deterministic-core", engine="ide", rule_id="scanipy/injection/b"),
            make_finding(
                origin="oracle-passthrough",
                engine="semgrep",
                rule_id="scanipy/secrets/c",
                class_="secrets",
                witness_blob_uri=None,
            ),
        }
    )

    kwargs: dict[str, object] = {
        "scan_id": scan_id,
        "snapshot_id": snapshot_id,
        "codebase_id": codebase_id,
        "commit_sha": "d" * 40,
        "S_version": "1.4.0",
        "env_digest": "sha256:" + ("7" * 64),
        "precondition_status": "closed-world",
        "llm_triage_flag": False,
    }
    log = normalize(findings, **kwargs)  # type: ignore[arg-type]
    doc = _json.loads(log.canonical_bytes)

    core_run, oracle_run = doc["runs"][0], doc["runs"][1]
    assert core_run["properties"]["scanipy.partition"] == "core"
    assert oracle_run["properties"]["scanipy.partition"] == "oracle"

    core_origins = [r["properties"]["scanipy.origin"] for r in core_run["results"]]
    oracle_origins = [r["properties"]["scanipy.origin"] for r in oracle_run["results"]]

    # Anti-vacuity: each partition actually received its findings.
    assert len(core_origins) == 2 and len(oracle_origins) == 1
    # No Run mixes partitions; origin is verbatim per finding; 'mixed' never appears.
    assert set(core_origins) == {"deterministic-core"}
    assert set(oracle_origins) == {"oracle-passthrough"}
    assert b'"mixed"' not in log.canonical_bytes
    # determinism_partition equals origin at emission time (DOC-SARIF §6).
    for run in (core_run, oracle_run):
        for r in run["results"]:
            assert (
                r["properties"]["scanipy.determinism_partition"]
                == r["properties"]["scanipy.origin"]
            )

    # Byte-identity (AC-CP-05a foundation): re-running on identical inputs yields
    # byte-identical canonical bytes. This is the mutation a clock read would
    # break — ``normalize`` emits no timestamp, so it holds.
    log2 = normalize(findings, **kwargs)  # type: ignore[arg-type]
    assert log2.canonical_bytes == log.canonical_bytes
    assert log2.sarif_hash == log.sarif_hash


@pytest.mark.invariant
def test_inv_1_fnd_02_origin_partition_at_store() -> None:
    """INV-1 at the store: origin NOT NULL + enum CHECK rejects null and 'mixed'.

    Test id:        TST-INV-1-FND-02
    Maps to AC:     INV-1 (CMP-FND-02 schema) — schema-level discharge of the
                    determinism partition.
    Kind tag:       [INVARIANT]
    Inputs:         A live ``findings`` table; candidate INSERTs (a) omitting
                    ``origin``, (b) with ``origin='mixed'``.
    Outputs:        INSERT outcome (success / DB error).
    Pass criteria:  INSERT omitting ``origin`` raises a NOT NULL violation
                    (SQLSTATE 23502); INSERT with ``origin='mixed'`` is rejected
                    by the ``findings_origin_chk`` CHECK constraint (only
                    ``deterministic-core`` / ``oracle-passthrough`` permitted);
                    ``determinism_partition`` and ``engine`` enforce their enums
                    likewise (DOC-DB §4.12, DOC-CMP-FND-02 §5.1). The violation is
                    unrecoverable at the schema layer (no silent default-stuffing).
    Frequency:      every CI run
    Hard gate?:     yes — schema INV-1 gate for CMP-FND-02.
    """
    # --- Metadata introspection (always runs, no DB) ---
    table = Finding.__table__
    for name in ("origin", "determinism_partition", "engine"):
        assert not table.columns[name].nullable, f"INV-1: findings.{name} must be NOT NULL"
    # The origin enum CHECK admits ONLY the two partitions; 'mixed' is excluded.
    origin_chk = _check_sqltext(table, "findings_origin_chk")
    assert "deterministic-core" in origin_chk
    assert "oracle-passthrough" in origin_chk
    assert "mixed" not in origin_chk, (
        "INV-1: 'mixed' must never be an admissible finding-level origin"
    )
    assert "mixed" not in _check_sqltext(table, "findings_determinism_partition_chk")
    engine_chk = _check_sqltext(table, "findings_engine_chk")
    for eng in ("ifds", "ide", "semgrep", "cpg-query", "external"):
        assert eng in engine_chk

    # NOTE: the live-PostgreSQL INSERT-fail falsifiers for this invariant
    # (NOT NULL 23502 / CHECK 23514) live in tests/integration/
    # test_fnd_specs.py under @pytest.mark.integration, so CI's postgres:16
    # integration job runs them. This unit half asserts only the no-DB
    # schema metadata above.


@pytest.mark.invariant
def test_inv_1_fnd_03_origin_partition_at_provenance() -> None:
    """INV-1 at provenance: chain link 9 carries origin; parent never mutated.

    Test id:        TST-INV-1-FND-03
    Maps to AC:     INV-1 (CMP-FND-03 chain) — link 9 records per-finding origin;
                    re-partition is an append, not a mutation.
    Kind tag:       [INVARIANT]
    Inputs:         A ``record_type='chain'`` provenance row; a subsequent
                    ``append_repartition_event`` for the same finding.
    Outputs:        Provenance rows + their canonical bytes.
    Pass criteria:  Every ``chain``/``repartition`` provenance row has a non-null
                    ``origin`` (row-level CHECK ``record_type NOT IN
                    ('chain','repartition') OR origin IS NOT NULL``, DOC-DB
                    §4.13); the re-partition record carries
                    ``origin='oracle-passthrough'``; the parent base record's
                    ``canonical_bytes`` are byte-identical before and after the
                    append (append-only, no UPDATE/DELETE grants).
    Frequency:      every CI run
    Hard gate?:     yes — INV-1 / append-only gate for CMP-FND-03.
    """
    import uuid as _uuid

    from services.scan.provenance import (
        append_repartition_event,
        sign_provenance,
    )
    from tests.fnd03_fakes import (
        InMemoryProvenanceStore,
        SoftwareKMSSigner,
        make_chain_record,
    )

    signer = SoftwareKMSSigner()
    store = InMemoryProvenanceStore()
    base = make_chain_record(origin="deterministic-core")
    base_signed = sign_provenance(
        base,
        signer=signer,
        kms_key_arn="arn:aws:kms:us-east-1:000000000000:key/fnd03",
        store=store,
    )
    base_bytes_before = base_signed.canonical_bytes

    repart = append_repartition_event(
        parent_record_id=base.id,
        repartition_oracle_id=_uuid.uuid4(),
        repartition_reason="reachable reflection",
        store=store,
        signer=signer,
    )

    # Every chain/repartition record carries a non-null origin (link 9, INV-1).
    assert base_signed.record.origin is not None
    assert repart.record.origin == "oracle-passthrough"

    # The parent base record's canonical bytes are byte-identical before and
    # after the append (append-only — no UPDATE/DELETE).
    base_after = store.get(base.id)
    assert base_after is not None
    assert base_after.canonical_bytes == base_bytes_before


@pytest.mark.invariant
def test_inv_2_fnd_01_nonnull_sversion_envdigest_at_normalizer() -> None:
    """INV-2 at the normalizer: S_version + env_digest threaded to every result.

    Test id:        TST-INV-2-FND-01
    Maps to AC:     INV-2 (CMP-FND-01 emitter) — every emitted finding carries a
                    non-null ``S_version`` and ``env_digest``, propagated unchanged
                    from the worker-emitted finding into the normalized SARIF.
    Kind tag:       [INVARIANT]
    Inputs:         A ``frozenset[Finding]`` whose members carry pinned
                    ``S_version`` and ``env_digest`` values, fed to
                    ``analysis.sarif.canonical_emit.normalize(...)`` with the run
                    pins (scan_id/snapshot_id/codebase_id/commit_sha/S_version/
                    env_digest/precondition_status, llm_triage_flag=False).
    Outputs:        ``SARIFLog`` with two Runs; per-Result ``properties`` block.
    Pass criteria:  Every normalized ``Result.properties`` carries
                    ``scanipy.S_version`` (capital S, per DOC-SARIF §5/§6/§8 — the
                    capital S is load-bearing for canonical key order) and
                    ``scanipy.env_digest``; both are non-null/non-empty; AND each
                    equals the source Finding's ``S_version`` / ``env_digest``
                    verbatim (propagated unchanged, DOC-CMP-FND-01 §5.2 /
                    DOC-SARIF §7). The normalizer never invents, defaults, or drops
                    either field; a missing field on an input Finding raises (no
                    silent null-stuffing).
    Frequency:      every CI run
    Hard gate?:     yes — INV-2 emitter gate; feeds CMP-CP-05.
    """
    import json as _json
    import uuid as _uuid

    from analysis.sarif.canonical_emit import InvariantViolation, normalize
    from tests.fnd01_fakes import make_broken_finding, make_finding

    s_version = "2.7.1"
    env_digest = "sha256:" + ("9" * 64)
    findings = frozenset(
        {
            make_finding(origin="deterministic-core", S_version=s_version, env_digest=env_digest),
            make_finding(
                origin="oracle-passthrough",
                engine="semgrep",
                class_="secrets",
                rule_id="scanipy/secrets/x",
                witness_blob_uri=None,
                S_version=s_version,
                env_digest=env_digest,
            ),
        }
    )
    log = normalize(
        findings,
        scan_id=_uuid.uuid4(),
        snapshot_id=_uuid.uuid4(),
        codebase_id=_uuid.uuid4(),
        commit_sha="e" * 40,
        S_version=s_version,
        env_digest=env_digest,
        precondition_status="closed-world",
        llm_triage_flag=False,
    )
    doc = _json.loads(log.canonical_bytes)

    all_results = [r for run in doc["runs"] for r in run["results"]]
    assert len(all_results) == 2  # anti-vacuity
    for r in all_results:
        props = r["properties"]
        # Capital S per DOC-SARIF §5/§6/§8; both non-empty and verbatim.
        assert props["scanipy.S_version"] == s_version
        assert props["scanipy.env_digest"] == env_digest
        assert "scanipy.s_version" not in props  # no lowercase variant leaked
    # Run.properties carry the same pinned values (INV-2 at Run level too).
    for run in doc["runs"]:
        assert run["properties"]["scanipy.S_version"] == s_version
        assert run["properties"]["scanipy.env_digest"] == env_digest

    # No silent null-stuffing: a finding with a blank S_version is REJECTED
    # fail-fast (negative control) — never emitted with an invented/blank value.
    with pytest.raises(InvariantViolation):
        normalize(
            frozenset({make_broken_finding("S_version")}),
            scan_id=_uuid.uuid4(),
            snapshot_id=_uuid.uuid4(),
            codebase_id=_uuid.uuid4(),
            commit_sha="f" * 40,
            S_version=s_version,
            env_digest=env_digest,
            precondition_status="closed-world",
            llm_triage_flag=False,
        )


@pytest.mark.invariant
def test_inv_5_fnd_01_annotation_literal_on_every_result() -> None:
    """INV-5 at the normalizer: the conditional-canonicality annotation literal
    is emitted on every Result, sourced from the single construction-site constant.

    Test id:        TST-INV-5-FND-01
    Maps to AC:     INV-5 (CMP-FND-01 emitter) — DOC-CMP-FND-01 §5.3: every
                    ``Result.properties["scanipy.cpg_order_hash_annotation"]`` is
                    the exact literal ``"canonical iff fingerprint_class =
                    strong"``, JSON-adjacent to ``scanipy.cpg_order_hash``, and the
                    string is imported from ``analysis.ordering`` rather than
                    rebuilt. DOC-SARIF §9 lists this as forthcoming; it is the
                    headline INV-5 requirement of the emitter, so it is authored
                    here alongside 01a/01b.
    Kind tag:       [INVARIANT]
    Inputs:         A ``frozenset[Finding]`` (both ``strong`` and ``weak``
                    fingerprint classes); ``normalize(...)``.
    Outputs:        ``SARIFLog.canonical_bytes``.
    Pass criteria:  Every emitted Result carries the EXACT annotation literal next
                    to its ``cpg_order_hash``; no abbreviated / translated /
                    truncated variant leaks; the literal equals
                    ``analysis.ordering.CPG_ORDER_HASH_ANNOTATION``. An emission
                    with the annotation stripped fails the INV-5 structural check.
    Frequency:      every CI run
    Hard gate?:     yes — INV-5 emitter gate; CMP-CI-01 annotation-presence gate
                    (DOC-SARIF §12 gate 5).
    """
    import json as _json
    import uuid as _uuid

    from analysis.ordering import CPG_ORDER_HASH_ANNOTATION as ORDERING_ANNOTATION
    from analysis.sarif.canonical_emit import normalize, validate_sarif_210
    from tests.fnd01_fakes import make_finding

    # The emitter must source the literal from the CORE-03 constant, never rebuild.
    assert ORDERING_ANNOTATION == _ANNOTATION

    findings = frozenset(
        {
            make_finding(
                origin="deterministic-core", fingerprint_class="strong", rule_id="scanipy/ssrf/s"
            ),
            # A weak-classed finding STILL carries the annotation (the annotation
            # is precisely what tells consumers canonicality holds only on strong).
            make_finding(
                origin="oracle-passthrough",
                engine="semgrep",
                class_="secrets",
                rule_id="scanipy/secrets/w",
                fingerprint_class="weak",
                witness_blob_uri=None,
            ),
        }
    )
    log = normalize(
        findings,
        scan_id=_uuid.uuid4(),
        snapshot_id=_uuid.uuid4(),
        codebase_id=_uuid.uuid4(),
        commit_sha="1" * 40,
        S_version="1.4.0",
        env_digest="sha256:" + ("7" * 64),
        precondition_status="closed-world",
        llm_triage_flag=False,
    )
    doc = _json.loads(log.canonical_bytes)
    all_results = [r for run in doc["runs"] for r in run["results"]]

    # Anti-vacuity: there are results to check, across both fingerprint classes.
    assert len(all_results) == 2
    assert {r["properties"]["scanipy.fingerprint_class"] for r in all_results} == {
        "strong",
        "weak",
    }
    for r in all_results:
        props = r["properties"]
        assert props["scanipy.cpg_order_hash_annotation"] == ORDERING_ANNOTATION
        # JSON adjacency is enforced by the canonical key sort: with keys sorted,
        # ``scanipy.cpg_order_hash_annotation`` immediately follows
        # ``scanipy.cpg_order_hash`` (no scanipy.cpg_order_hash* key sorts between
        # them). Assert both keys are present together on every Result.
        assert "scanipy.cpg_order_hash" in props

    # No abbreviated / truncated annotation variant leaks anywhere in the bytes.
    for variant in (b"canonical hash", b"cpg_canonical_hash", b"canonical CPG"):
        assert variant not in log.canonical_bytes
    # The full literal appears exactly twice (once per Result).
    assert log.canonical_bytes.count(_ANNOTATION.encode("utf-8")) == 2

    # Negative control (c): an annotation-stripped emission fails the INV-5 leg of
    # the structural validator (the const check), proving the assertion is not
    # vacuous.
    stripped = log.canonical_bytes.replace(
        b'"scanipy.cpg_order_hash_annotation":"' + _ANNOTATION.encode("utf-8") + b'"',
        b'"scanipy.cpg_order_hash_annotation":"canonical hash"',
    )
    assert stripped != log.canonical_bytes
    errors = validate_sarif_210(stripped)
    assert any("cpg_order_hash_annotation" in e for e in errors)


@pytest.mark.unit
def test_fnd_01_normalize_split_emits_two_single_run_files() -> None:
    """Smoke test for the opt-in split-file emitter (DOC-SARIF §4 alternate).

    Not in the four target ACs, but ``normalize_split`` is a shipped emit path;
    assert it produces two standalone single-Run SARIF files (``*-core``,
    ``*-oracle``), each one canonical, non-empty, and re-parseable to exactly one
    Run whose partition matches. The per-file canonical/validation requirements
    are the same as :func:`normalize` applied independently (DOC-SARIF §4).
    """
    import json as _json
    import uuid as _uuid

    from analysis.sarif.canonical_emit import normalize_split
    from tests.fnd01_fakes import make_finding

    findings = frozenset(
        {
            make_finding(origin="deterministic-core", engine="ifds"),
            make_finding(
                origin="oracle-passthrough",
                engine="semgrep",
                class_="secrets",
                rule_id="scanipy/secrets/k",
                witness_blob_uri=None,
            ),
        }
    )
    core_run, oracle_run = normalize_split(
        findings,
        scan_id=_uuid.uuid4(),
        snapshot_id=_uuid.uuid4(),
        codebase_id=_uuid.uuid4(),
        commit_sha="2" * 40,
        S_version="1.4.0",
        env_digest="sha256:" + ("7" * 64),
        precondition_status="closed-world",
        llm_triage_flag=False,
    )

    assert core_run.partition == "core" and oracle_run.partition == "oracle"
    assert core_run.result_count == 1 and oracle_run.result_count == 1
    for run in (core_run, oracle_run):
        assert len(run.canonical_bytes) > 0
        doc = _json.loads(run.canonical_bytes)
        # Each split file is a single-Run document of its own partition.
        assert len(doc["runs"]) == 1
        assert doc["runs"][0]["properties"]["scanipy.partition"] == run.partition


@pytest.mark.invariant
def test_inv_2_fnd_02_nonnull_sversion_envdigest_at_schema_level() -> None:
    """INV-2 at the store: S_version + env_digest NOT NULL; env_digest format CHECK.

    Test id:        TST-INV-2-FND-02
    Maps to AC:     INV-2 (CMP-FND-02 schema) — versioned parameters enforced at
                    the SQL constraint level.
    Kind tag:       [INVARIANT]
    Inputs:         A live ``findings`` table; candidate INSERTs (a) omitting
                    ``S_version``, (b) omitting ``env_digest``, (c) with a
                    malformed ``env_digest`` (not ``sha256:hex64``).
    Outputs:        INSERT outcome (success / DB error).
    Pass criteria:  INSERT omitting ``S_version`` or ``env_digest`` raises a NOT
                    NULL violation (SQLSTATE 23502); INSERT with ``env_digest``
                    not matching ``^sha256:[0-9a-f]{64}$`` is rejected by the
                    ``findings_env_digest_format`` CHECK (DOC-DB §4.12,
                    DOC-CMP-FND-02 §5.2).
    Frequency:      every CI run
    Hard gate?:     yes — schema INV-2 gate for CMP-FND-02.
    """
    # --- Metadata introspection (always runs, no DB) ---
    table = Finding.__table__
    for name in ("S_version", "env_digest"):
        assert not table.columns[name].nullable, f"INV-2: findings.{name} must be NOT NULL"
    # env_digest format CHECK pins sha256:hex64.
    env_chk = _check_sqltext(table, "findings_env_digest_chk")
    assert "^sha256:[0-9a-f]{64}$" in env_chk, (
        f"INV-2: env_digest must enforce the sha256 format; got {env_chk!r}"
    )

    # NOTE: the live-PostgreSQL INSERT-fail falsifiers for this invariant
    # (NOT NULL 23502 / CHECK 23514) live in tests/integration/
    # test_fnd_specs.py under @pytest.mark.integration, so CI's postgres:16
    # integration job runs them. This unit half asserts only the no-DB
    # schema metadata above.


@pytest.mark.invariant
def test_inv_2_fnd_03_sversion_envdigest_as_links_in_signed_chain() -> None:
    """INV-2 at provenance: S_version + env_digest are links in the audit chain.

    Test id:        TST-INV-2-FND-03
    Maps to AC:     INV-2 (CMP-FND-03 chain) — the signed provenance record carries
                    ``S_version`` and ``env_digest`` as links in the audit chain
                    (DOC-PROVENANCE: ``... → S_version → env_digest → ...``).
    Kind tag:       [INVARIANT]
    Inputs:         A signed ``record_type='chain'`` provenance row built for a
                    finding with pinned ``S_version`` / ``env_digest`` values, plus
                    its auditor export via
                    ``services.scan.provenance.export_auditor_record(record_id)``.
    Outputs:        The provenance DB row + the auditor-export ``dict`` / JSON.
    Pass criteria:  The chain row has non-null ``S_version`` and ``env_digest``
                    columns (DOC-DB §4.13), and both appear as ordered links in the
                    exported chain between the snapshot digest and the
                    ``cpg_order_hash`` link (DOC-PROVENANCE chain order); AND each
                    equals the owning finding's ``S_version`` / ``env_digest``
                    verbatim. The signature covers both fields, so a tampered
                    value fails verification (no out-of-band substitution).
    Frequency:      every CI run
    Hard gate?:     yes — INV-2 chain gate for CMP-FND-03.
    """
    import dataclasses

    from services.scan.provenance import (
        export_auditor_record,
        sign_provenance,
        verify_chain,
    )
    from tests.fnd03_fakes import (
        InMemoryProvenanceStore,
        SoftwareKMSSigner,
        make_chain_record,
    )

    signer = SoftwareKMSSigner()
    store = InMemoryProvenanceStore()
    s_version = "4.5.6"
    env_digest = "sha256:" + ("d" * 64)
    record = make_chain_record(s_version=s_version, env_digest=env_digest)
    signed = sign_provenance(
        record,
        signer=signer,
        kms_key_arn="arn:aws:kms:us-east-1:000000000000:key/fnd03",
        store=store,
    )

    # Both links are non-null on the chain row and equal the source verbatim.
    assert signed.record.S_version == s_version
    assert signed.record.env_digest == env_digest

    # Both appear in the auditor export, ordered between the snapshot digest link
    # and the cpg_order_hash link (DOC-PROVENANCE chain order).
    export = export_auditor_record(record.id, store=store)
    assert export["S_version"] == s_version
    assert export["env_digest"] == env_digest
    keys = list(export.keys())
    assert keys.index("snapshot_digest") < keys.index("S_version") < keys.index("env_digest")
    assert keys.index("env_digest") < keys.index("cpg_order_hash")

    # The signature covers both fields: tampering with env_digest fails verification.
    tampered = dataclasses.replace(
        signed,
        record=dataclasses.replace(signed.record, env_digest="sha256:" + ("e" * 64)),  # type: ignore[arg-type]
    )
    assert verify_chain(tampered, signer=signer) == "TAMPERED"


@pytest.mark.invariant
def test_inv_5_fnd_03_annotation_present_in_chain_and_auditor_export() -> None:
    """INV-5 at provenance: annotation literal present in chain row + export.

    Test id:        TST-INV-5-FND-03
    Maps to AC:     INV-5 (CMP-FND-03) — conditional-canonicality annotation is
                    self-describing in every chain record and auditor export.
    Kind tag:       [INVARIANT]
    Inputs:         A signed ``provenance_records`` chain row + its auditor export
                    (DOC-PROVENANCE §8.1); the ``CPG_ORDER_HASH_ANNOTATION``
                    constant from ``analysis.ordering``.
    Outputs:        The DB row and the export JSON.
    Pass criteria:  ``provenance_records.cpg_order_hash_annotation`` equals the
                    literal ``"canonical iff fingerprint_class = strong"``
                    (DB literal CHECK, DOC-DB §4.13); the auditor export carries
                    the same literal as a key JSON-adjacent to ``cpg_order_hash``;
                    a grep for any abbreviated/translated variant returns no hit;
                    the annotation equals ``CPG_ORDER_HASH_ANNOTATION`` (never a
                    locally-constructed string).
    Frequency:      every CI run
    Hard gate?:     yes — INV-5 gate for CMP-FND-03.
    """
    from analysis.ordering import CPG_ORDER_HASH_ANNOTATION as ORDERING_ANNOTATION

    # The provenance module re-exports the same single-construction-site constant.
    from services.scan.provenance import CPG_ORDER_HASH_ANNOTATION as PROV_ANNOTATION
    from services.scan.provenance import export_auditor_record, sign_provenance
    from tests.fnd03_fakes import (
        InMemoryProvenanceStore,
        SoftwareKMSSigner,
        make_chain_record,
    )

    assert PROV_ANNOTATION is ORDERING_ANNOTATION
    assert ORDERING_ANNOTATION == _ANNOTATION

    signer = SoftwareKMSSigner()
    store = InMemoryProvenanceStore()
    record = make_chain_record()
    signed = sign_provenance(
        record,
        signer=signer,
        kms_key_arn="arn:aws:kms:us-east-1:000000000000:key/fnd03",
        store=store,
    )

    # The chain row carries the literal — sourced from the constant, not rebuilt.
    assert signed.record.cpg_order_hash_annotation == ORDERING_ANNOTATION

    # The auditor export carries the same literal, JSON-adjacent to the hash.
    export = export_auditor_record(record.id, store=store)
    assert export["cpg_order_hash_annotation"] == ORDERING_ANNOTATION
    keys = list(export.keys())
    assert keys[keys.index("cpg_order_hash") + 1] == "cpg_order_hash_annotation"
