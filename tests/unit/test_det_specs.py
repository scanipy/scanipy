"""DET family acceptance + invariant test specs — Phase 1 (spec-first TDD).

Covers the DET (Detector Catalog) acceptance criteria EXCEPT TST-AC-DET-01a.
TST-AC-DET-01a (the Gate-1 distributivity proof stubs) lives in
``tests/unit/test_dsl_proofs.py`` and is intentionally NOT duplicated here.

Specs in this file (WBS §4.2 / §4.3):
  - TST-AC-DET-01b   [NEGATIVE]    DSL grammar rejects specs embedding arbitrary code
  - TST-AC-DET-02a   [NEGATIVE]    Registration rejects out-of-DSL specs with precise diagnostic
  - TST-AC-DET-02b   [UNIT]        Manifest records all required fields + derived partition
  - TST-AC-DET-02c   [UNIT]        engine -> determinism_partition mapping correct
  - TST-AC-DET-03a   [UNIT]        All ten class dirs register without error (stubs permitted)
  - TST-AC-DET-03b   [REGRESSION]  Migrated path-traversal spec reproduces CVE-2025-61765
  - TST-INV-4-DET-01 [INVARIANT]   DSL closure check rejects any non-DSL spec at registration

DET-01b and DET-02a both exercise the E-DSL-001..009 escape-hatch codes, but at
DIFFERENT entry points — DET-01b at the parser (``parse_spec()``), DET-02a at the
registry (``DetectorRegistry.register()``) where E-REG-001..006 also apply. This is
legitimate non-duplication, not redundancy.

Spec-first: production code does not exist yet. Every test is a registered stub
(xfail + skip) that flips red->green when its CMP-DET-* implementation lands.

Marker set is the CLOSED pyproject.toml set
{unit, integration, falsifier, empirical, invariant, nightly, pre_release};
the WBS kind tag appears in the docstring only.
"""

import pytest

# ─── TST-AC-DET-01b — DSL grammar admits no escape hatch ────────────────────
# AC-DET-01b: one [NEGATIVE] test per E-DSL-001..009 at the PARSER entry point
# (analysis/ifds/dsl/parser.py parse_spec). Each asserts a structured DSLError
# with the expected code; rejection is total (no partial Spec).
# Hard gate? yes. Frequency: every CI run.
# CLAR-PARAM-01 marks the upstream-owned "non-DSL spec" type boundary (see
# test_dsl_proofs.py precedent); the operational boundary is E-DSL-001..009.


@pytest.mark.unit
@pytest.mark.xfail(reason="CMP-DET-01 not yet implemented", strict=False)
def test_dsl_rejects_raw_regex_e_dsl_001() -> None:
    """TST-AC-DET-01b / Maps to AC-DET-01b / Kind [NEGATIVE].

    Inputs: a DSL spec embedding a raw regex, e.g. ``source(re.compile(...))``.
    Outputs: parse_spec raises DSLError(code='E-DSL-001'), structured
        {code, message, line, col, suggested_fix}; no Spec returned.
    Pass criteria: DSLError.code == 'E-DSL-001'; message names raw-regex escape.
    Frequency: every CI run. Hard gate? yes.
    """
    # TODO: from analysis.ifds.dsl.parser import parse_spec, DSLError
    # CLAR-PARAM-01 — non-DSL spec type boundary owned upstream; codes per DOC-DSL §6
    pytest.skip("CMP-DET-01 not implemented yet")


@pytest.mark.unit
@pytest.mark.xfail(reason="CMP-DET-01 not yet implemented", strict=False)
def test_dsl_rejects_embedded_semgrep_e_dsl_002() -> None:
    """TST-AC-DET-01b / Maps to AC-DET-01b / Kind [NEGATIVE].

    Inputs: a DSL spec embedding a Semgrep oracle pattern in a clause.
    Outputs: DSLError(code='E-DSL-002') advising engine=semgrep instead.
    Pass criteria: DSLError.code == 'E-DSL-002'; spec is not analyzed.
    Frequency: every CI run. Hard gate? yes.
    """
    # TODO: parse_spec must reject embedded oracle pattern (CLAR-PARAM-01 boundary)
    pytest.skip("CMP-DET-01 not implemented yet")


@pytest.mark.unit
@pytest.mark.xfail(reason="CMP-DET-01 not yet implemented", strict=False)
def test_dsl_rejects_embedded_cpg_query_e_dsl_003() -> None:
    """TST-AC-DET-01b / Maps to AC-DET-01b / Kind [NEGATIVE].

    Inputs: a DSL spec embedding a cpg-query/CodeQL expression in a clause.
    Outputs: DSLError(code='E-DSL-003') advising engine=cpg-query instead.
    Pass criteria: DSLError.code == 'E-DSL-003'; spec is not analyzed.
    Frequency: every CI run. Hard gate? yes.
    """
    # TODO: parse_spec must reject embedded cpg-query expression
    pytest.skip("CMP-DET-01 not implemented yet")


@pytest.mark.unit
@pytest.mark.xfail(reason="CMP-DET-01 not yet implemented", strict=False)
def test_dsl_rejects_raw_lambda_e_dsl_004() -> None:
    """TST-AC-DET-01b / Maps to AC-DET-01b / Kind [NEGATIVE].

    Inputs: a DSL spec with a non-declarative Python callable, e.g.
        ``sanitize(lambda f: f.is_xss())``.
    Outputs: DSLError(code='E-DSL-004') 'non-declarative callable'.
    Pass criteria: DSLError.code == 'E-DSL-004'; arbitrary code never analyzed.
    Frequency: every CI run. Hard gate? yes.
    """
    # TODO: arbitrary embedded code is the canonical escape-hatch AC-DET-01b forbids
    pytest.skip("CMP-DET-01 not implemented yet")


@pytest.mark.unit
@pytest.mark.xfail(reason="CMP-DET-01 not yet implemented", strict=False)
def test_dsl_rejects_sequencing_operator_e_dsl_005() -> None:
    """TST-AC-DET-01b / Maps to AC-DET-01b / Kind [NEGATIVE].

    Inputs: a DSL spec using a sequencing operator (``then`` / ``;`` / ``seq``).
    Outputs: DSLError(code='E-DSL-005') 'sequencing operator not in §4.3'.
    Pass criteria: DSLError.code == 'E-DSL-005'; sequencing breaks distributivity.
    Frequency: every CI run. Hard gate? yes.
    """
    # TODO: sequencing is excluded by DOC-DSL §4 sanctioned compositions
    pytest.skip("CMP-DET-01 not implemented yet")


@pytest.mark.unit
@pytest.mark.xfail(reason="CMP-DET-01 not yet implemented", strict=False)
def test_dsl_rejects_conditional_operator_e_dsl_006() -> None:
    """TST-AC-DET-01b / Maps to AC-DET-01b / Kind [NEGATIVE].

    Inputs: a DSL spec using a conditional combinator (``if/when/guard``).
    Outputs: DSLError(code='E-DSL-006') 'conditional operator not in §4.3'.
    Pass criteria: DSLError.code == 'E-DSL-006'.
    Frequency: every CI run. Hard gate? yes.
    """
    # TODO: conditional is excluded by DOC-DSL §4 sanctioned compositions
    pytest.skip("CMP-DET-01 not implemented yet")


@pytest.mark.unit
@pytest.mark.xfail(reason="CMP-DET-01 not yet implemented", strict=False)
def test_dsl_rejects_user_fixpoint_e_dsl_007() -> None:
    """TST-AC-DET-01b / Maps to AC-DET-01b / Kind [NEGATIVE].

    Inputs: a DSL spec using a user fixpoint combinator (``fixpoint/closure/rec``).
    Outputs: DSLError(code='E-DSL-007') 'fixpoint operator not in §4.3'.
    Pass criteria: DSLError.code == 'E-DSL-007'.
    Frequency: every CI run. Hard gate? yes.
    """
    # TODO: user fixpoint is excluded by DOC-DSL §4 sanctioned compositions
    pytest.skip("CMP-DET-01 not implemented yet")


@pytest.mark.unit
@pytest.mark.xfail(reason="CMP-DET-01 not yet implemented", strict=False)
def test_dsl_rejects_unknown_primitive_head_e_dsl_008() -> None:
    """TST-AC-DET-01b / Maps to AC-DET-01b / Kind [NEGATIVE].

    Inputs: a DSL spec with an unknown primitive head, e.g. ``taint_flow(p)``.
    Outputs: DSLError(code='E-DSL-008') naming {source, sink, sanitize, propagate}.
    Pass criteria: DSLError.code == 'E-DSL-008'; head set is exactly the four.
    Frequency: every CI run. Hard gate? yes.
    """
    # TODO: admissible primitive heads are exactly {source, sink, sanitize, propagate}
    pytest.skip("CMP-DET-01 not implemented yet")


@pytest.mark.unit
@pytest.mark.xfail(reason="CMP-DET-01 not yet implemented", strict=False)
def test_dsl_rejects_non_core_engine_e_dsl_009() -> None:
    """TST-AC-DET-01b / Maps to AC-DET-01b / Kind [NEGATIVE].

    Inputs: a DSL-parsed spec declaring engine not in {ifds, ide}
        (e.g. ``engine: semgrep`` inside specs/*.dsl.yaml).
    Outputs: DSLError(code='E-DSL-009') 'engine=semgrep specs do not parse'.
    Pass criteria: DSLError.code == 'E-DSL-009'; oracle specs never parse as DSL.
    Frequency: every CI run. Hard gate? yes.
    """
    # TODO: DSL files admit only engine ∈ {ifds, ide}; oracle engines live elsewhere
    pytest.skip("CMP-DET-01 not implemented yet")


# ─── TST-AC-DET-02a — Registration rejects out-of-DSL specs (precise) ───────
# AC-DET-02a / INV-4: at the REGISTRY entry point (DetectorRegistry.register).
# E-DSL-001..009 are surfaced verbatim (passed through from CMP-DET-01) AND the
# registry-specific E-REG-001..006 apply. Reject at registration, never silently
# accept. Hard gate? yes. Frequency: every CI run.


@pytest.mark.unit
@pytest.mark.xfail(reason="CMP-DET-02 not yet implemented", strict=False)
@pytest.mark.parametrize(
    "e_dsl_code",
    [
        "E-DSL-001",
        "E-DSL-002",
        "E-DSL-003",
        "E-DSL-004",
        "E-DSL-005",
        "E-DSL-006",
        "E-DSL-007",
        "E-DSL-008",
        "E-DSL-009",
    ],
)
def test_registration_rejects_out_of_dsl_spec_passthrough_e_dsl(e_dsl_code: str) -> None:
    """TST-AC-DET-02a / Maps to AC-DET-02a / Kind [NEGATIVE].

    One case per E-DSL-001..009 surfaced verbatim at the REGISTRY entry point
    (DOC-CMP-DET-02 §9.2 mandates one test per E-DSL code plus one per E-REG code).

    Inputs: a Detector whose core DSL spec triggers `e_dsl_code` (out-of-grammar).
    Outputs: register() raises DSLError with the verbatim E-DSL code; registry
        left empty (no partial-load); rejection is total.
    Pass criteria: DSLError.code == e_dsl_code surfaced verbatim at register();
        spec never admitted. Distinct entry point from TST-AC-DET-01b (parser).
    Frequency: every CI run. Hard gate? yes.
    """
    # TODO: from detectors.registry import DetectorRegistry, DSLError
    # CLAR-PARAM-01 — non-DSL spec boundary owned upstream; codes per DOC-DSL §6
    # When CMP-DET-02 is DONE, assert on the REGISTRY OUTPUT, never the input var:
    #   with pytest.raises(DSLError) as exc:
    #       DetectorRegistry().register(detector_triggering(e_dsl_code))
    #   assert exc.value.code == e_dsl_code        # verbatim code at register()
    #   assert DetectorRegistry().specs == []      # total rejection, no partial-load
    # (No pre-skip assert on e_dsl_code itself — that is tautological and would leave
    #  the registration guard permanently green once pytest.skip is removed.)
    pytest.skip("CMP-DET-02 not implemented yet")


@pytest.mark.unit
@pytest.mark.xfail(reason="CMP-DET-02 not yet implemented", strict=False)
def test_registration_rejects_missing_manifest_field_e_reg_001() -> None:
    """TST-AC-DET-02a / Maps to AC-DET-02a / Kind [NEGATIVE].

    Inputs: a manifest missing a required field (id/cwes/languages/frameworks/
        engine/severity_default/per_language_readiness).
    Outputs: RegistryError(code='E-REG-001') naming the missing field (AC-DET-02b).
    Pass criteria: error.code == 'E-REG-001'; diagnostic names the field.
    Frequency: every CI run. Hard gate? yes.
    """
    # TODO: from detectors.registry import RegistryError
    pytest.skip("CMP-DET-02 not implemented yet")


@pytest.mark.unit
@pytest.mark.xfail(reason="CMP-DET-02 not yet implemented", strict=False)
def test_registration_rejects_unknown_engine_e_reg_002() -> None:
    """TST-AC-DET-02a / Maps to AC-DET-02a / Kind [NEGATIVE].

    Inputs: a manifest whose engine is outside {ifds, ide, semgrep, cpg-query, external}.
    Outputs: RegistryError(code='E-REG-002') enumerating the valid set (AC-DET-02c).
    Pass criteria: error.code == 'E-REG-002'.
    Frequency: every CI run. Hard gate? yes.
    """
    # TODO: engine enum is closed; new engines need AC-DET-02c amendment (RULE-4)
    pytest.skip("CMP-DET-02 not implemented yet")


@pytest.mark.unit
@pytest.mark.xfail(reason="CMP-DET-02 not yet implemented", strict=False)
def test_registration_rejects_duplicate_id_e_reg_003() -> None:
    """TST-AC-DET-02a / Maps to AC-DET-02a / Kind [NEGATIVE].

    Inputs: two Detectors sharing the same id.
    Outputs: RegistryError(code='E-REG-003') 'detector id already registered'.
    Pass criteria: error.code == 'E-REG-003'; ids are globally unique.
    Frequency: every CI run. Hard gate? yes.
    """
    # TODO: id uniqueness is a registry-level closure constraint
    pytest.skip("CMP-DET-02 not implemented yet")


@pytest.mark.unit
@pytest.mark.xfail(reason="CMP-DET-02 not yet implemented", strict=False)
def test_registration_rejects_oracle_without_query_path_e_reg_004() -> None:
    """TST-AC-DET-02a / Maps to AC-DET-02a / Kind [NEGATIVE].

    Inputs: an oracle-engine manifest with missing/nonexistent oracle_query_path.
    Outputs: RegistryError(code='E-REG-004') naming the missing path.
    Pass criteria: error.code == 'E-REG-004'.
    Frequency: every CI run. Hard gate? yes.
    """
    # TODO: oracle engines require an existing oracle_query_path file
    pytest.skip("CMP-DET-02 not implemented yet")


@pytest.mark.unit
@pytest.mark.xfail(reason="CMP-DET-02 not yet implemented", strict=False)
def test_registration_rejects_reregistration_after_boot_e_reg_005() -> None:
    """TST-AC-DET-02a / Maps to AC-DET-02a / Kind [NEGATIVE].

    Inputs: a register() call for an id after load_manifests() has completed.
    Outputs: RegistryError(code='E-REG-005') 'registry is read-only after load'.
    Pass criteria: error.code == 'E-REG-005'; registry never mutates post-boot.
    Frequency: every CI run. Hard gate? yes.
    """
    # TODO: registry is a frozen process-singleton after load_manifests()
    pytest.skip("CMP-DET-02 not implemented yet")


@pytest.mark.unit
@pytest.mark.xfail(reason="CMP-DET-02 not yet implemented", strict=False)
def test_registration_rejects_unknown_engine_in_derive_partition_e_reg_006() -> None:
    """TST-AC-DET-02a / Maps to AC-DET-02a / Kind [NEGATIVE].

    Inputs: an engine value reaching derive_partition outside the enumerated set
        (defense-in-depth; should have been caught by E-REG-002).
    Outputs: RegistryError(code='E-REG-006').
    Pass criteria: error.code == 'E-REG-006'.
    Frequency: every CI run. Hard gate? yes.
    """
    # TODO: derive_partition is total over the closed engine enum; else E-REG-006
    pytest.skip("CMP-DET-02 not implemented yet")


# ─── TST-AC-DET-02b — Manifest records all required fields + derived partition ─


@pytest.mark.unit
@pytest.mark.xfail(reason="CMP-DET-02 not yet implemented", strict=False)
def test_manifest_records_all_required_fields() -> None:
    """TST-AC-DET-02b / Maps to AC-DET-02b / Kind [UNIT].

    Inputs: a well-formed manifest passed through register().
    Outputs: the resulting Detector record carries id, cwes, languages, frameworks,
        engine, severity_default, per_language_readiness, and a derived
        determinism_partition.
    Pass criteria: every AC-DET-02b field present and well-formed; partition is
        DERIVED (matches derive_partition(engine)), not authored on the manifest.
    Frequency: every CI run. Hard gate? yes.
    """
    # TODO: assert determinism_partition is absent from manifest input yet present on record
    pytest.skip("CMP-DET-02 not implemented yet")


# ─── TST-AC-DET-02c — engine -> determinism_partition mapping ───────────────
# AC-DET-02c: ifds|ide -> deterministic-core; semgrep|cpg-query|external ->
# oracle-passthrough. One [UNIT] test per engine value (the closed enum).
# Hard gate? yes. Frequency: every CI run.


@pytest.mark.unit
@pytest.mark.xfail(reason="CMP-DET-02 not yet implemented", strict=False)
def test_partition_ifds_is_deterministic_core() -> None:
    """TST-AC-DET-02c / Maps to AC-DET-02c / Kind [UNIT].

    Inputs: engine='ifds'.
    Outputs: derive_partition('ifds') == 'deterministic-core'.
    Pass criteria: exact equality 'deterministic-core'.
    Frequency: every CI run. Hard gate? yes.
    """
    # TODO: from detectors.registry import derive_partition
    pytest.skip("CMP-DET-02 not implemented yet")


@pytest.mark.unit
@pytest.mark.xfail(reason="CMP-DET-02 not yet implemented", strict=False)
def test_partition_ide_is_deterministic_core() -> None:
    """TST-AC-DET-02c / Maps to AC-DET-02c / Kind [UNIT].

    Inputs: engine='ide'.
    Outputs: derive_partition('ide') == 'deterministic-core'.
    Pass criteria: exact equality 'deterministic-core'.
    Frequency: every CI run. Hard gate? yes.
    """
    # TODO: derive_partition('ide') -> deterministic-core
    pytest.skip("CMP-DET-02 not implemented yet")


@pytest.mark.unit
@pytest.mark.xfail(reason="CMP-DET-02 not yet implemented", strict=False)
def test_partition_semgrep_is_oracle_passthrough() -> None:
    """TST-AC-DET-02c / Maps to AC-DET-02c / Kind [UNIT].

    Inputs: engine='semgrep'.
    Outputs: derive_partition('semgrep') == 'oracle-passthrough'.
    Pass criteria: exact equality 'oracle-passthrough'.
    Frequency: every CI run. Hard gate? yes.
    """
    # TODO: derive_partition('semgrep') -> oracle-passthrough
    pytest.skip("CMP-DET-02 not implemented yet")


@pytest.mark.unit
@pytest.mark.xfail(reason="CMP-DET-02 not yet implemented", strict=False)
def test_partition_cpg_query_is_oracle_passthrough() -> None:
    """TST-AC-DET-02c / Maps to AC-DET-02c / Kind [UNIT].

    Inputs: engine='cpg-query'.
    Outputs: derive_partition('cpg-query') == 'oracle-passthrough'.
    Pass criteria: exact equality 'oracle-passthrough'.
    Frequency: every CI run. Hard gate? yes.
    """
    # TODO: derive_partition('cpg-query') -> oracle-passthrough
    pytest.skip("CMP-DET-02 not implemented yet")


@pytest.mark.unit
@pytest.mark.xfail(reason="CMP-DET-02 not yet implemented", strict=False)
def test_partition_external_is_oracle_passthrough() -> None:
    """TST-AC-DET-02c / Maps to AC-DET-02c / Kind [UNIT].

    Inputs: engine='external'.
    Outputs: derive_partition('external') == 'oracle-passthrough'.
    Pass criteria: exact equality 'oracle-passthrough'.
    Frequency: every CI run. Hard gate? yes.
    """
    # TODO: derive_partition('external') -> oracle-passthrough
    pytest.skip("CMP-DET-02 not implemented yet")


# ─── TST-AC-DET-03a — All ten class dirs register without error ─────────────


@pytest.mark.unit
@pytest.mark.xfail(reason="CMP-DET-03 not yet implemented", strict=False)
def test_all_ten_class_directories_register_without_error() -> None:
    """TST-AC-DET-03a / Maps to AC-DET-03a / Kind [UNIT].

    Inputs: scaffold_class() run for all ten ClassName values (injection,
        path-traversal, ssrf, deserialization, xss, crypto-misuse, authn-authz,
        memory-safety, secrets, dep-cve); stub manifests permitted.
    Outputs: DetectorRegistry.load_manifests() completes without raising on the
        resulting tree.
    Pass criteria: load_manifests() returns without error; all ten classes present;
        stub specs/oracle dirs are acceptable.
    Frequency: every CI run. Hard gate? yes.
    """
    # TODO: from tools.scaffold_class import scaffold_class; from detectors.registry import ...
    pytest.skip("CMP-DET-03 not implemented yet")


# ─── TST-AC-DET-03b — Migrated path-traversal reproduces CVE-2025-61765 ─────


@pytest.mark.unit
@pytest.mark.xfail(reason="CMP-DET-03 not yet implemented", strict=False)
def test_migrated_path_traversal_reproduces_cve_2025_61765() -> None:
    """TST-AC-DET-03b / Maps to AC-DET-03b / Kind [REGRESSION].

    Inputs: legacy tarslip.yaml migrated via migrate_tarslip(); the resulting
        DSL spec loaded via parse_spec(); a Stage-A-language scan against the
        historical CVE-2025-61765 repo state.
    Outputs: exactly one finding whose rule_id matches the migrated spec id, with
        origin='deterministic-core' and witness blob matching the canonical witness.
    Pass criteria: exactly one CVE-2025-61765 finding; origin=='deterministic-core';
        canonical witness matches. Ties to TST-AC-ORCH-01c backwards-compat surface.
    Frequency: every CI run. Hard gate? yes.
    """
    # TODO: from tools.migrate_tarslip import migrate_tarslip; assert single canonical finding
    pytest.skip("CMP-DET-03 not implemented yet")


# ─── TST-INV-4-DET-01 — DSL closure check rejects any non-DSL spec ──────────
# INV-4 (one-sided undecidable approximation, safe direction): any spec outside
# the distributive-by-construction DSL is rejected at registration, never
# analyzed. Owner module: analysis/ifds/dsl/. Falsifier-backed by TST-AC-DET-01b.


@pytest.mark.invariant
@pytest.mark.xfail(reason="CMP-DET-01 not yet implemented", strict=False)
def test_inv4_closure_rejects_any_non_dsl_spec_at_registration() -> None:
    """TST-INV-4-DET-01 / Maps to INV-4 (CMP-DET-01) / Kind [INVARIANT].

    INV-4 owner module: analysis/ifds/dsl/. Required SAFE direction — any spec
    outside the distributive-by-construction combinator DSL is rejected at
    registration, never analyzed (no partial parse, no silent acceptance).

    Inputs: a corpus of non-DSL specs spanning every escape hatch (E-DSL-001..009).
    Outputs: each is rejected (DSLError) before any registration side effect;
        none reaches CMP-CORE-01 analysis.
    Pass criteria: for every non-DSL spec, register()/parse_spec() rejects; zero
        out-of-grammar specs are admitted (one-sided: false rejections allowed,
        silent acceptance forbidden).
    Frequency: every CI run. Hard gate? yes.
    """
    # TODO: CLAR-PARAM-01 — non-DSL spec type boundary owned upstream (DOC-DSL §6 codes)
    pytest.skip("CMP-DET-01 not implemented yet")
