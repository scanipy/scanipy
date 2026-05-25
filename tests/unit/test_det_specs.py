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

Spec-first → green: the TST-AC-DET-01b (E-DSL-001..009) and TST-INV-4-DET-01
rows are HYDRATED against the landed CMP-DET-01 DSL (analysis/ifds/dsl/). The
DET-02 (registry / E-REG-*) and DET-03 (scaffolding / migration) rows remain
registered stubs (xfail + skip) and flip red->green when their CMP-DET-*
implementations land.

Marker set is the CLOSED pyproject.toml set
{unit, integration, falsifier, empirical, invariant, nightly, pre_release};
the WBS kind tag appears in the docstring only.
"""

from pathlib import Path

import pytest

from analysis.ifds.dsl import DSLError, Spec, parse_spec
from detectors.registry import (
    Detector,
    DetectorRegistry,
    RegistryError,
    RegistryLoadError,
    derive_partition,
)

# Well-formed header shared by the negative fixtures below: an engine=ifds
# (deterministic-core) DSL spec. Each malformed-spec test appends exactly one
# out-of-grammar clause so the asserted E-DSL code is the *only* defect.
_GOOD_HEADER = 'id: "neg-fixture"\nclass: "injection"\nlanguages: ["java"]\nengine: "ifds"\n'


def _spec(*clauses: str, header: str = _GOOD_HEADER) -> str:
    return header + "\n".join(clauses) + "\n"


# ─── TST-AC-DET-01b — DSL grammar admits no escape hatch ────────────────────
# AC-DET-01b: one [NEGATIVE] test per E-DSL-001..009 at the PARSER entry point
# (analysis/ifds/dsl/parser.py parse_spec). Each asserts a structured DSLError
# with the expected code; rejection is total (no partial Spec).
# Hard gate? yes. Frequency: every CI run.
# CLAR-PARAM-01 marks the upstream-owned "non-DSL spec" type boundary (see
# test_dsl_proofs.py precedent); the operational boundary is E-DSL-001..009.


@pytest.mark.unit
def test_dsl_rejects_raw_regex_e_dsl_001() -> None:
    """TST-AC-DET-01b / Maps to AC-DET-01b / Kind [NEGATIVE].

    Inputs: a DSL spec embedding a raw regex, e.g. ``source(re.compile(...))``.
    Outputs: parse_spec raises DSLError(code='E-DSL-001'), structured
        {code, message, line, col, suggested_fix}; no Spec returned.
    Pass criteria: DSLError.code == 'E-DSL-001'; message names raw-regex escape.
    Frequency: every CI run. Hard gate? yes.
    """
    with pytest.raises(DSLError) as exc:
        parse_spec(_spec(r'source(re.compile(r".*\.execute\("))'))
    assert exc.value.code == "E-DSL-001"
    assert "regex" in exc.value.message.lower()
    assert exc.value.suggested_fix  # structured: hint present


@pytest.mark.unit
def test_dsl_rejects_embedded_semgrep_e_dsl_002() -> None:
    """TST-AC-DET-01b / Maps to AC-DET-01b / Kind [NEGATIVE].

    Inputs: a DSL spec embedding a Semgrep oracle pattern in a clause.
    Outputs: DSLError(code='E-DSL-002') advising engine=semgrep instead.
    Pass criteria: DSLError.code == 'E-DSL-002'; spec is not analyzed.
    Frequency: every CI run. Hard gate? yes.
    """
    with pytest.raises(DSLError) as exc:
        parse_spec(_spec('propagate(semgrep: { pattern: "$X = $TAINTED" })'))
    assert exc.value.code == "E-DSL-002"
    assert "semgrep" in exc.value.message.lower()


@pytest.mark.unit
def test_dsl_rejects_embedded_cpg_query_e_dsl_003() -> None:
    """TST-AC-DET-01b / Maps to AC-DET-01b / Kind [NEGATIVE].

    Inputs: a DSL spec embedding a cpg-query/CodeQL expression in a clause.
    Outputs: DSLError(code='E-DSL-003') advising engine=cpg-query instead.
    Pass criteria: DSLError.code == 'E-DSL-003'; spec is not analyzed.
    Frequency: every CI run. Hard gate? yes.
    """
    with pytest.raises(DSLError) as exc:
        parse_spec(_spec('sink(cpg.method("foo").caller)'))
    assert exc.value.code == "E-DSL-003"
    assert "cpg-query" in exc.value.message.lower()


@pytest.mark.unit
def test_dsl_rejects_raw_lambda_e_dsl_004() -> None:
    """TST-AC-DET-01b / Maps to AC-DET-01b / Kind [NEGATIVE].

    Inputs: a DSL spec with a non-declarative Python callable, e.g.
        ``sanitize(lambda f: f.is_xss())``.
    Outputs: DSLError(code='E-DSL-004') 'non-declarative callable'.
    Pass criteria: DSLError.code == 'E-DSL-004'; arbitrary code never analyzed.
    Frequency: every CI run. Hard gate? yes.
    """
    with pytest.raises(DSLError) as exc:
        parse_spec(_spec("sanitize(lambda f: f.is_xss())"))
    assert exc.value.code == "E-DSL-004"
    assert "callable" in exc.value.message.lower()


@pytest.mark.unit
def test_dsl_rejects_sequencing_operator_e_dsl_005() -> None:
    """TST-AC-DET-01b / Maps to AC-DET-01b / Kind [NEGATIVE].

    Inputs: a DSL spec using a sequencing operator (``then`` / ``;`` / ``seq``).
    Outputs: DSLError(code='E-DSL-005') 'sequencing operator not in §4.3'.
    Pass criteria: DSLError.code == 'E-DSL-005'; sequencing breaks distributivity.
    Frequency: every CI run. Hard gate? yes.
    """
    with pytest.raises(DSLError) as exc:
        parse_spec(_spec("then propagate(arg[0] → ret)"))
    assert exc.value.code == "E-DSL-005"
    assert "sequencing" in exc.value.message.lower()


@pytest.mark.unit
def test_dsl_rejects_conditional_operator_e_dsl_006() -> None:
    """TST-AC-DET-01b / Maps to AC-DET-01b / Kind [NEGATIVE].

    Inputs: a DSL spec using a conditional combinator (``if/when/guard``).
    Outputs: DSLError(code='E-DSL-006') 'conditional operator not in §4.3'.
    Pass criteria: DSLError.code == 'E-DSL-006'.
    Frequency: every CI run. Hard gate? yes.
    """
    with pytest.raises(DSLError) as exc:
        parse_spec(_spec("if matches(p) then propagate(arg[0] → ret)"))
    assert exc.value.code == "E-DSL-006"
    assert "conditional" in exc.value.message.lower()


@pytest.mark.unit
def test_dsl_rejects_user_fixpoint_e_dsl_007() -> None:
    """TST-AC-DET-01b / Maps to AC-DET-01b / Kind [NEGATIVE].

    Inputs: a DSL spec using a user fixpoint combinator (``fixpoint/closure/rec``).
    Outputs: DSLError(code='E-DSL-007') 'fixpoint operator not in §4.3'.
    Pass criteria: DSLError.code == 'E-DSL-007'.
    Frequency: every CI run. Hard gate? yes.
    """
    with pytest.raises(DSLError) as exc:
        parse_spec(_spec("fixpoint(propagate(arg[0] → ret))"))
    assert exc.value.code == "E-DSL-007"
    assert "fixpoint" in exc.value.message.lower()


@pytest.mark.unit
def test_dsl_rejects_unknown_primitive_head_e_dsl_008() -> None:
    """TST-AC-DET-01b / Maps to AC-DET-01b / Kind [NEGATIVE].

    Inputs: a DSL spec with an unknown primitive head, e.g. ``taint_flow(p)``.
    Outputs: DSLError(code='E-DSL-008') naming {source, sink, sanitize, propagate}.
    Pass criteria: DSLError.code == 'E-DSL-008'; head set is exactly the four.
    Frequency: every CI run. Hard gate? yes.
    """
    with pytest.raises(DSLError) as exc:
        parse_spec(_spec("taint_flow(?T<:Http.getParameter)"))
    assert exc.value.code == "E-DSL-008"
    assert "taint_flow" in exc.value.message
    for head in ("source", "sink", "sanitize", "propagate"):
        assert head in exc.value.message


@pytest.mark.unit
def test_dsl_rejects_non_core_engine_e_dsl_009() -> None:
    """TST-AC-DET-01b / Maps to AC-DET-01b / Kind [NEGATIVE].

    Inputs: a DSL-parsed spec declaring engine not in {ifds, ide}
        (e.g. ``engine: semgrep`` inside specs/*.dsl.yaml).
    Outputs: DSLError(code='E-DSL-009') 'engine=semgrep specs do not parse'.
    Pass criteria: DSLError.code == 'E-DSL-009'; oracle specs never parse as DSL.
    Frequency: every CI run. Hard gate? yes.
    """
    bad_engine_header = (
        'id: "neg-eng"\nclass: "xss"\nlanguages: ["javascript"]\nengine: "semgrep"\n'
    )
    with pytest.raises(DSLError) as exc:
        parse_spec(_spec("sink(document.innerHTML)", header=bad_engine_header))
    assert exc.value.code == "E-DSL-009"
    assert "do not parse" in exc.value.message


# ─── TST-AC-DET-02a — Registration rejects out-of-DSL specs (precise) ───────
# AC-DET-02a / INV-4: at the REGISTRY entry point (DetectorRegistry.register).
# E-DSL-001..009 are surfaced verbatim (passed through from CMP-DET-01) AND the
# registry-specific E-REG-001..006 apply. Reject at registration, never silently
# accept. Hard gate? yes. Frequency: every CI run.


# Per-code out-of-grammar spec bodies, reused verbatim from TST-INV-4-DET-01.
# Each is the SAME malformed DSL text the parser rejects; here it is surfaced
# through the REGISTRY entry point (load_manifests) where the verbatim E-DSL
# code must pass through unwrapped.
_SEMGREP_HEADER = 'id: "neg-eng"\nclass: "xss"\nlanguages: ["javascript"]\nengine: "semgrep"\n'
_BAD_SPEC_BY_CODE: dict[str, str] = {
    "E-DSL-001": _spec(r'source(re.compile(r".*\.execute\("))'),
    "E-DSL-002": _spec('propagate(semgrep: { pattern: "$X" })'),
    "E-DSL-003": _spec('sink(cpg.method("foo").caller)'),
    "E-DSL-004": _spec("sanitize(lambda f: f.is_xss())"),
    "E-DSL-005": _spec("then propagate(arg[0] → ret)"),
    "E-DSL-006": _spec("if matches(p) then sanitize(arg[0])"),
    "E-DSL-007": _spec("fixpoint(propagate(arg[0] → ret))"),
    "E-DSL-008": _spec("taint_flow(?T<:Http.getParameter)"),
    "E-DSL-009": _spec("sink(document.innerHTML)", header=_SEMGREP_HEADER),
}

_CORE_MANIFEST = (
    "id: neg-fixture\n"
    "cwes: [CWE-89]\n"
    "languages: [java]\n"
    "frameworks: [jdbc]\n"
    "engine: ifds\n"
    "severity_default: high\n"
    "per_language_readiness:\n"
    "  java: ready\n"
)


def _write_core_detector(root: Path, *, spec_text: str, class_name: str = "neg") -> None:
    """Build <root>/<class>/{manifest.yaml,specs/bad.dsl.yaml} for a core engine."""
    class_dir = root / class_name
    (class_dir / "specs").mkdir(parents=True)
    (class_dir / "manifest.yaml").write_text(_CORE_MANIFEST, encoding="utf-8")
    (class_dir / "specs" / "bad.dsl.yaml").write_text(spec_text, encoding="utf-8")


@pytest.mark.unit
@pytest.mark.parametrize("e_dsl_code", sorted(_BAD_SPEC_BY_CODE))
def test_registration_rejects_out_of_dsl_spec_passthrough_e_dsl(
    e_dsl_code: str, tmp_path: Path
) -> None:
    """TST-AC-DET-02a / Maps to AC-DET-02a / Kind [NEGATIVE].

    One case per E-DSL-001..009 surfaced verbatim at the REGISTRY entry point
    (DOC-CMP-DET-02 §9.2 mandates one test per E-DSL code plus one per E-REG code).

    Inputs: a detector tree whose core DSL spec triggers `e_dsl_code`.
    Outputs: load_manifests() raises DSLError with the verbatim E-DSL code;
        registry left empty (no partial-load); rejection is total.
    Pass criteria: DSLError.code == e_dsl_code surfaced verbatim at the registry;
        spec never admitted. Distinct entry point from TST-AC-DET-01b (parser).
    Frequency: every CI run. Hard gate? yes.
    """
    root = tmp_path / "detectors"
    _write_core_detector(root, spec_text=_BAD_SPEC_BY_CODE[e_dsl_code])
    reg = DetectorRegistry()
    with pytest.raises(DSLError) as exc:
        reg.load_manifests(str(root))
    assert exc.value.code == e_dsl_code  # verbatim code surfaced at the registry
    assert reg.all() == ()  # total rejection, no partial-load


@pytest.mark.unit
def test_registration_rejects_missing_manifest_field_e_reg_001(tmp_path: Path) -> None:
    """TST-AC-DET-02a / Maps to AC-DET-02a / Kind [NEGATIVE].

    Inputs: a manifest missing a required field (id/cwes/languages/frameworks/
        engine/severity_default/per_language_readiness).
    Outputs: RegistryError(code='E-REG-001') naming the missing field (AC-DET-02b).
    Pass criteria: error.code == 'E-REG-001'; diagnostic names the field.
    Frequency: every CI run. Hard gate? yes.
    """
    root = tmp_path / "detectors"
    class_dir = root / "neg"
    class_dir.mkdir(parents=True)
    # Drop the required ``cwes`` field.
    manifest = (
        "id: neg-fixture\n"
        "languages: [java]\n"
        "frameworks: [jdbc]\n"
        "engine: ifds\n"
        "severity_default: high\n"
        "per_language_readiness:\n  java: ready\n"
    )
    (class_dir / "manifest.yaml").write_text(manifest, encoding="utf-8")
    reg = DetectorRegistry()
    with pytest.raises(RegistryLoadError) as exc:
        reg.load_manifests(str(root))
    assert exc.value.code == "E-REG-001"
    assert "cwes" in str(exc.value)
    assert reg.all() == ()  # atomic: no partial-load


@pytest.mark.unit
def test_registration_rejects_unknown_engine_e_reg_002(tmp_path: Path) -> None:
    """TST-AC-DET-02a / Maps to AC-DET-02a / Kind [NEGATIVE].

    Inputs: a manifest whose engine is outside {ifds, ide, semgrep, cpg-query, external}.
    Outputs: RegistryError(code='E-REG-002') enumerating the valid set (AC-DET-02c).
    Pass criteria: error.code == 'E-REG-002'.
    Frequency: every CI run. Hard gate? yes.
    """
    root = tmp_path / "detectors"
    class_dir = root / "neg"
    class_dir.mkdir(parents=True)
    manifest = (
        "id: neg-fixture\n"
        "cwes: [CWE-89]\n"
        "languages: [java]\n"
        "frameworks: [jdbc]\n"
        "engine: quantum\n"  # not in the closed engine enum
        "severity_default: high\n"
        "per_language_readiness:\n  java: ready\n"
    )
    (class_dir / "manifest.yaml").write_text(manifest, encoding="utf-8")
    reg = DetectorRegistry()
    with pytest.raises(RegistryLoadError) as exc:
        reg.load_manifests(str(root))
    assert exc.value.code == "E-REG-002"
    assert reg.all() == ()


@pytest.mark.unit
def test_registration_rejects_duplicate_id_e_reg_003(tmp_path: Path) -> None:
    """TST-AC-DET-02a / Maps to AC-DET-02a / Kind [NEGATIVE].

    Inputs: two detectors sharing the same id.
    Outputs: RegistryError(code='E-REG-003') 'detector id already registered'.
    Pass criteria: error.code == 'E-REG-003'; ids are globally unique.
    Frequency: every CI run. Hard gate? yes.
    """
    root = tmp_path / "detectors"
    good_spec = _spec(
        "source(?T<:javax.servlet.http.HttpServletRequest.getParameter(*))",
        "sink(?T<:java.sql.Statement.executeQuery(arg[0]))",
    )
    # Two distinct class dirs whose manifests both declare id: neg-fixture.
    for class_name in ("alpha", "beta"):
        cd = root / class_name
        (cd / "specs").mkdir(parents=True)
        (cd / "manifest.yaml").write_text(_CORE_MANIFEST, encoding="utf-8")
        (cd / "specs" / "ok.dsl.yaml").write_text(good_spec, encoding="utf-8")
    reg = DetectorRegistry()
    with pytest.raises(RegistryLoadError) as exc:
        reg.load_manifests(str(root))
    assert exc.value.code == "E-REG-003"
    assert reg.all() == ()


@pytest.mark.unit
def test_registration_rejects_oracle_without_query_path_e_reg_004(tmp_path: Path) -> None:
    """TST-AC-DET-02a / Maps to AC-DET-02a / Kind [NEGATIVE].

    Inputs: an oracle-engine manifest with missing/nonexistent oracle_query_path.
    Outputs: RegistryError(code='E-REG-004') naming the missing path.
    Pass criteria: error.code == 'E-REG-004'.
    Frequency: every CI run. Hard gate? yes.
    """
    root = tmp_path / "detectors"
    class_dir = root / "neg"
    class_dir.mkdir(parents=True)
    manifest = (
        "id: oracle-fixture\n"
        "cwes: [CWE-79]\n"
        "languages: [javascript]\n"
        "frameworks: [express]\n"
        "engine: semgrep\n"
        "severity_default: medium\n"
        "oracle_query_path: oracle/missing.semgrep.yaml\n"  # file does not exist
        "per_language_readiness:\n  javascript: ready\n"
    )
    (class_dir / "manifest.yaml").write_text(manifest, encoding="utf-8")
    reg = DetectorRegistry()
    with pytest.raises(RegistryLoadError) as exc:
        reg.load_manifests(str(root))
    assert exc.value.code == "E-REG-004"
    assert reg.all() == ()


@pytest.mark.unit
def test_registration_rejects_reregistration_after_boot_e_reg_005(tmp_path: Path) -> None:
    """TST-AC-DET-02a / Maps to AC-DET-02a / Kind [NEGATIVE].

    Inputs: a register() call for an id after load_manifests() has completed.
    Outputs: RegistryError(code='E-REG-005') 'registry is read-only after load'.
    Pass criteria: error.code == 'E-REG-005'; registry never mutates post-boot.
    Frequency: every CI run. Hard gate? yes.
    """
    root = tmp_path / "detectors"
    cd = root / "alpha"
    (cd / "specs").mkdir(parents=True)
    (cd / "manifest.yaml").write_text(_CORE_MANIFEST, encoding="utf-8")
    (cd / "specs" / "ok.dsl.yaml").write_text(
        _spec(
            "source(?T<:javax.servlet.http.HttpServletRequest.getParameter(*))",
            "sink(?T<:java.sql.Statement.executeQuery(arg[0]))",
        ),
        encoding="utf-8",
    )
    reg = DetectorRegistry()
    reg.load_manifests(str(root))  # boot completes; registry frozen

    later = Detector(
        id="post-boot",
        cwes=("CWE-89",),
        languages=("java",),
        frameworks=("jdbc",),
        engine="ifds",
        severity_default="high",
        determinism_partition=derive_partition("ifds"),
        per_language_readiness={"java": "ready"},
        spec=reg.all()[0].spec,
    )
    with pytest.raises(RegistryError) as exc:
        reg.register(later)
    assert exc.value.code == "E-REG-005"


@pytest.mark.unit
def test_registration_rejects_unknown_engine_in_derive_partition_e_reg_006() -> None:
    """TST-AC-DET-02a / Maps to AC-DET-02a / Kind [NEGATIVE].

    Inputs: an engine value reaching derive_partition outside the enumerated set
        (defense-in-depth; should have been caught by E-REG-002).
    Outputs: RegistryError(code='E-REG-006').
    Pass criteria: error.code == 'E-REG-006'.
    Frequency: every CI run. Hard gate? yes.
    """
    with pytest.raises(RegistryError) as exc:
        derive_partition("quantum")
    assert exc.value.code == "E-REG-006"


# ─── TST-AC-DET-02b — Manifest records all required fields + derived partition ─


@pytest.mark.unit
def test_manifest_records_all_required_fields(tmp_path: Path) -> None:
    """TST-AC-DET-02b / Maps to AC-DET-02b / Kind [UNIT].

    Inputs: a well-formed manifest passed through load_manifests().
    Outputs: the resulting Detector record carries id, cwes, languages, frameworks,
        engine, severity_default, per_language_readiness, and a derived
        determinism_partition.
    Pass criteria: every AC-DET-02b field present and well-formed; partition is
        DERIVED (matches derive_partition(engine)), not authored on the manifest.
    Frequency: every CI run. Hard gate? yes.
    """
    root = tmp_path / "detectors"
    cd = root / "injection"
    (cd / "specs").mkdir(parents=True)
    manifest_text = (
        "id: java-jdbc-sqli\n"
        "cwes: [CWE-89]\n"
        "languages: [java]\n"
        "frameworks: [jdbc, spring-jdbc]\n"
        "engine: ifds\n"
        "severity_default: high\n"
        "per_language_readiness:\n  java: ready\n  python: front-end-blocked\n"
    )
    (cd / "manifest.yaml").write_text(manifest_text, encoding="utf-8")
    (cd / "specs" / "sqli.dsl.yaml").write_text(
        'id: "java-jdbc-sqli"\nclass: "injection"\nlanguages: ["java"]\nengine: "ifds"\n'
        "source(?T<:javax.servlet.http.HttpServletRequest.getParameter(*))\n"
        "sink(?T<:java.sql.Statement.executeQuery(arg[0]))\n",
        encoding="utf-8",
    )
    reg = DetectorRegistry()
    reg.load_manifests(str(root))
    det = reg.by_id("java-jdbc-sqli")

    assert det.cwes == ("CWE-89",)
    assert det.languages == ("java",)
    assert det.frameworks == ("jdbc", "spring-jdbc")
    assert det.engine == "ifds"
    assert det.severity_default == "high"
    assert det.per_language_readiness == {"java": "ready", "python": "front-end-blocked"}
    assert det.spec is not None

    # determinism_partition is DERIVED, not authored: absent from the raw manifest
    # on disk, present on the record, and equal to derive_partition(engine).
    import yaml as _yaml

    raw = _yaml.safe_load((cd / "manifest.yaml").read_text(encoding="utf-8"))
    assert "determinism_partition" not in raw
    assert det.determinism_partition == derive_partition(det.engine)
    assert det.determinism_partition == "deterministic-core"


# ─── TST-AC-DET-02c — engine -> determinism_partition mapping ───────────────
# AC-DET-02c: ifds|ide -> deterministic-core; semgrep|cpg-query|external ->
# oracle-passthrough. One [UNIT] test per engine value (the closed enum).
# Hard gate? yes. Frequency: every CI run.


@pytest.mark.unit
def test_partition_ifds_is_deterministic_core() -> None:
    """TST-AC-DET-02c / Maps to AC-DET-02c / Kind [UNIT].

    Inputs: engine='ifds'.
    Outputs: derive_partition('ifds') == 'deterministic-core'.
    Pass criteria: exact equality 'deterministic-core'.
    Frequency: every CI run. Hard gate? yes.
    """
    assert derive_partition("ifds") == "deterministic-core"


@pytest.mark.unit
def test_partition_ide_is_deterministic_core() -> None:
    """TST-AC-DET-02c / Maps to AC-DET-02c / Kind [UNIT].

    Inputs: engine='ide'.
    Outputs: derive_partition('ide') == 'deterministic-core'.
    Pass criteria: exact equality 'deterministic-core'.
    Frequency: every CI run. Hard gate? yes.
    """
    assert derive_partition("ide") == "deterministic-core"


@pytest.mark.unit
def test_partition_semgrep_is_oracle_passthrough() -> None:
    """TST-AC-DET-02c / Maps to AC-DET-02c / Kind [UNIT].

    Inputs: engine='semgrep'.
    Outputs: derive_partition('semgrep') == 'oracle-passthrough'.
    Pass criteria: exact equality 'oracle-passthrough'.
    Frequency: every CI run. Hard gate? yes.
    """
    assert derive_partition("semgrep") == "oracle-passthrough"


@pytest.mark.unit
def test_partition_cpg_query_is_oracle_passthrough() -> None:
    """TST-AC-DET-02c / Maps to AC-DET-02c / Kind [UNIT].

    Inputs: engine='cpg-query'.
    Outputs: derive_partition('cpg-query') == 'oracle-passthrough'.
    Pass criteria: exact equality 'oracle-passthrough'.
    Frequency: every CI run. Hard gate? yes.
    """
    assert derive_partition("cpg-query") == "oracle-passthrough"


@pytest.mark.unit
def test_partition_external_is_oracle_passthrough() -> None:
    """TST-AC-DET-02c / Maps to AC-DET-02c / Kind [UNIT].

    Inputs: engine='external'.
    Outputs: derive_partition('external') == 'oracle-passthrough'.
    Pass criteria: exact equality 'oracle-passthrough'.
    Frequency: every CI run. Hard gate? yes.
    """
    assert derive_partition("external") == "oracle-passthrough"


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
    semgrep_header = 'id: "neg-eng"\nclass: "xss"\nlanguages: ["javascript"]\nengine: "semgrep"\n'
    non_dsl_corpus: list[tuple[str, str]] = [
        ("E-DSL-001", _spec(r'source(re.compile(r".*\.execute\("))')),
        ("E-DSL-002", _spec('propagate(semgrep: { pattern: "$X" })')),
        ("E-DSL-003", _spec('sink(cpg.method("foo").caller)')),
        ("E-DSL-004", _spec("sanitize(lambda f: f.is_xss())")),
        ("E-DSL-005", _spec("then propagate(arg[0] → ret)")),
        ("E-DSL-006", _spec("if matches(p) then sanitize(arg[0])")),
        ("E-DSL-007", _spec("fixpoint(propagate(arg[0] → ret))")),
        ("E-DSL-008", _spec("taint_flow(?T<:Http.getParameter)")),
        ("E-DSL-009", _spec("sink(document.innerHTML)", header=semgrep_header)),
    ]

    # Safe direction: every out-of-grammar spec is rejected — total, no partial Spec.
    for expected_code, text in non_dsl_corpus:
        with pytest.raises(DSLError) as exc:
            parse_spec(text)
        assert exc.value.code == expected_code, f"expected {expected_code}, got {exc.value.code}"

    # One-sided, not vacuous: a well-formed in-grammar spec IS admitted. A check
    # that rejected everything would also "never analyze a non-DSL spec" but
    # would be useless; INV-4 forbids silent acceptance, not all acceptance.
    accepted = parse_spec(
        _spec(
            "source(?T<:javax.servlet.http.HttpServletRequest.getParameter(*))",
            "propagate(arg[0] → ret)",
            "sanitize(?T<:java.sql.PreparedStatement.setString(*))",
            "sink(?T<:java.sql.Statement.executeQuery(arg[0]))",
        )
    )
    assert isinstance(accepted, Spec)
    assert accepted.engine == "ifds"
    assert len(accepted.clauses) == 4
