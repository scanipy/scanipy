# DOC-CMP-FND-01 — Findings normalizer (SARIF emission)

> **Status:** DRAFT (Phase 0). Satisfies `AC-DOC-04`: an Implementation Agent given only this document plus the cross-cutting refs (`DOC-SARIF`, `DOC-INV`, `DOC-PROVENANCE`, `DOC-DB`, `DOC-PARTITION`, `DOC-GLOSSARY`, `DOC-ALGS`) can produce a passing implementation without re-reading `SDD.md`.

---

## 1. Component identity

| Field | Value |
|---|---|
| **CMP-ID** | `CMP-FND-01` |
| **Subsystem** | Findings & Provenance (`SDD.md §8`) |
| **Module path** | `analysis/sarif/canonical_emit.py` + `services/scan/findings_normalizer.py` (per `DOC-SARIF.md §3`) |
| **Staging** | Stage A · cross-language · partition-agnostic emitter |
| **Depends-On** | `CMP-CORE-02`, `CMP-CORE-03` (per `WBS.md §20`) |
| **Touches invariants** | INV-1 (preserves per-finding `origin`; emits two partitions); INV-2 (carries `S_version`, `env_digest` in SARIF properties); **INV-5** (writes the `cpg_order_hash` annotation literal on every Result) |
| **Owning maintainer** | Findings & Provenance team (Stage-A maintainer set) |

---

## 2. Mandate

**SDD `Purpose:` (verbatim from `SDD.md §8 → CMP-FND-01`):**

> Normalize every detector output to SARIF 2.1.0; attach the slice fingerprint; emit results in canonical CPG order.

**Operational role.** This component is the wire-format boundary between the analysis core/oracle adapters and every downstream consumer (Attestor, customer SARIF export, dashboard, GitHub code-scanning, third-party SARIF tooling). Given an internal `set[Finding]` produced by `CMP-ORCH-03`, it emits a SARIF v2.1.0 log with **two `Run` objects per scan** — `runs[0]` for `origin=deterministic-core` results, `runs[1]` for `origin=oracle-passthrough` results (`DOC-SARIF.md §4`). Within each Run, results are sorted by the canonical key tuple `(cpg_order_hash, rule_id, uri, start_line)` (`DOC-SARIF.md §7`), then serialised byte-deterministically per the rules of `DOC-SARIF.md §3` (lexicographic key sort, minified, UTF-8/LF, shortest round-trip floats). The component does not set or mutate `origin`; it threads through what `CMP-ORCH-03` already stamped.

It is the **load-bearing emitter for INV-1 byte-identity on the core partition**: any non-determinism here invalidates `CMP-CP-05`'s byte-identical SARIF guarantee (`AC-CP-05a`).

---

## 3. Interface contract

### 3.1 Public Python signatures

```python
from typing import Final, Literal, NewType
from dataclasses import dataclass

Sha256Hex = NewType("Sha256Hex", str)        # 64-char hex
SemVer    = NewType("SemVer", str)           # e.g. "1.4.0"
Partition = Literal["core", "oracle"]

@dataclass(frozen=True)
class SARIFRun:
    """One canonical SARIF Run for a single partition."""
    partition:        Partition                # "core" or "oracle"
    canonical_bytes:  bytes                    # the wire-canonical UTF-8 JSON (no LF)
    sarif_hash:       Sha256Hex                # sha256(canonical_bytes) — fed to CMP-FND-03 link 8
    result_count:     int

@dataclass(frozen=True)
class SARIFLog:
    """The normative two-Run log (DOC-SARIF §4). One per scan."""
    runs:             tuple[SARIFRun, SARIFRun]   # (core, oracle), in this order
    canonical_bytes:  bytes                       # full log: '{"$schema":...,"runs":[<core>,<oracle>]}' + LF
    sarif_hash:       Sha256Hex                   # sha256(canonical_bytes) of the full two-run log

def normalize(
    findings:    frozenset["Finding"],
    *,
    scan_id:     "UUID",
    snapshot_id: "UUID",
    codebase_id: "UUID",
    commit_sha:  str,
    S_version:   SemVer,
    env_digest:  str,
    precondition_status: Literal["closed-world", "degraded", "full-reparse"],
    llm_triage_flag:     bool,
) -> SARIFLog:
    """
    Normative emitter (DOC-SARIF §4): returns ONE SARIFLog containing TWO Runs
    (core first, oracle second). Discharges AC-FND-01a + AC-FND-01b.

    The function is PURE: same inputs ⇒ byte-identical SARIFLog.canonical_bytes.
    No I/O. No clock reads (start/end times must be passed in or come from `findings`).
    No global state.
    """
    ...

# Opt-in alternate (DOC-SARIF §4) — split-file representation for customer SARIF download.
def normalize_split(findings, *, ...) -> tuple[SARIFRun, SARIFRun]:
    """
    Alternate emitter producing two *separate* SARIF files (*-core.sarif, *-oracle.sarif).
    Every requirement of normalize() applies independently to each Run.
    """
    ...
```

The `Finding` type is the internal record produced by `CMP-ORCH-03`; it already carries `origin`, `S_version`, `env_digest`, `cpg_order_hash`, `cpg_order_hash_annotation`, `fingerprint_class`, `slice_fingerprint`, `engine`, `determinism_partition`, `precondition_status`, `class`, `severity`, `status`, and (optionally) `witness_blob_uri`, `spec_provenance`. See `DOC-SARIF.md §6` for the wire mapping.

### 3.2 The canonical annotation constant

This component imports and emits the literal annotation string (never constructs it):

```python
from analysis.ordering import CPG_ORDER_HASH_ANNOTATION
# == "canonical iff fingerprint_class = strong"
```

Every `Result.properties["scanipy.cpg_order_hash_annotation"]` is set from this constant; CI gate (`DOC-SARIF.md §12`) asserts the literal string on every Result.

### 3.3 The five canonical-emission requirements (verbatim from `DOC-SARIF.md §3`)

1. **Key ordering.** Every JSON object's keys emitted in **lexicographic (Unicode code-point) ascending order**.
2. **Whitespace.** No whitespace between tokens; emit minified JSON.
3. **Line endings.** One UTF-8 line followed by a single LF (`\n`). No CR. No BOM.
4. **Numbers.** Integers base-10, no leading zero/`+`; floats use shortest round-trip decimal (Ryū / Grisu equivalent).
5. **Result ordering.** Per §7 of `DOC-SARIF.md`, computed before serialisation; the serialiser never reorders.

If the Python JSON library does not provide guaranteed key ordering, sort explicitly before `json.dumps(..., separators=(',', ':'), ensure_ascii=False)`.

---

## 4. Inputs and outputs

### 4.1 Inputs

| Input | Source | Notes |
|---|---|---|
| `findings: frozenset[Finding]` | `CMP-ORCH-03` (`AC-ORCH-03a/b`) | Each `Finding` already has `origin`, `cpg_order_hash`, `cpg_order_hash_annotation`, `fingerprint_class`, `slice_fingerprint`. |
| `scan_id`, `snapshot_id`, `codebase_id`, `commit_sha` | `CMP-ORCH-01` scan submission | Threaded onto `Run.properties` (`DOC-SARIF.md §5`). |
| `S_version`, `env_digest` | `CMP-ORCH-01` (S_version), `CMP-SNAP-01` (env_digest) | INV-2; threaded onto both `Run.properties` and every `Result.properties`. |
| `precondition_status` | `CMP-SNAP-01` (`AC-SNAP-01b`) | Carried on `Run.properties.scanipy.precondition_status`. |
| `llm_triage_flag` | `CMP-ORCH-01` / feature flag | Boolean. MUST be `false` on every Attestor invocation (`AC-CP-05c`). |

### 4.2 Outputs

| Output | Consumers |
|---|---|
| `SARIFLog.canonical_bytes` (two-Run wire form) | `CMP-CP-05` Attestor; attestation export endpoint (`GET /api/v1/attestations/{scan_id}`, `DOC-API.md §4.7`); S3 long-term storage (`orgs/{org_id}/codebases/{codebase_id}/sarif/{scan_id}.sarif.json`, retention 7y under Object Lock per `CLAR-DEPLOY-15`). |
| `SARIFLog.sarif_hash` | `CMP-FND-03` provenance chain (link 8: SARIF hash); `attestations.attestor_hash` (`DOC-DB.md §4.10`). |
| `SARIFRun.sarif_hash` (per-partition) | `attestations` rows are keyed `(scan_id, partition)` — one row per partition (`DOC-DB.md §4.10`); `attestor_hash` per row is the per-partition SARIFRun hash. |
| Split-file artefacts (opt-in) | Customer SARIF download per integration. |

### 4.3 Persisted artefacts

| Artefact | Location |
|---|---|
| `SARIFLog.canonical_bytes` | S3 `orgs/{org_id}/codebases/{codebase_id}/sarif/{scan_id}.sarif.json` (per `DOC-PROVENANCE.md §6`); also fed inline to `CMP-FND-03`. |
| `SARIFLog.sarif_hash` | `attestations.attestor_hash` (`DOC-DB.md §4.10`) and `provenance_records` link 8 (`DOC-PROVENANCE.md §3`, field `sarif_hash`). |

This component does **not** write to the `findings` table directly — `CMP-ORCH-03` already wrote those rows. FND-01 is a *projection* from the persisted rows + in-memory `Finding`s onto SARIF wire form.

---

## 5. Invariants touched

### 5.1 INV-1 — Determinism partition (pass-through with two-Run discipline)

This component does not assign `origin`; it **respects** what `CMP-ORCH-03` set, and the two-Run emission is the wire-level *expression* of the partition. Discharge:

1. Every `Finding.origin = "deterministic-core"` lands in `runs[0]` (`partition = "core"`); every `Finding.origin = "oracle-passthrough"` lands in `runs[1]` (`partition = "oracle"`). No mixing.
2. Every `Result.properties.scanipy.origin` is set verbatim from the `Finding` field (never recomputed, never blurred to `"mixed"`).
3. The Attestor (`CMP-CP-05`) consumes `Run.properties.scanipy.partition` to pick the right pipeline: byte-identity over `runs[0]`, digest-stability + reproduction rate over `runs[1]` (`.claude/rules/05-determinism.md`).

**Counter-example.** Emitting a single Run containing both partitions, or setting `Result.properties.scanipy.origin = "mixed"` — both are INV-1 violations.

### 5.2 INV-2 — Versioned parameters (threading)

Every `Run.properties.scanipy.S_version` and `Run.properties.scanipy.env_digest`, and every `Result.properties.scanipy.S_version` and `Result.properties.scanipy.env_digest`, MUST be non-null and equal to the values passed in (`DOC-SARIF.md §5, §6`). The emitter MUST NOT default, mask, or strip these fields.

### 5.3 INV-5 — Conditional canonicality annotation (**LITERAL EMITTER**)

Every `Result.properties.scanipy.cpg_order_hash_annotation` MUST be the literal string:

```
canonical iff fingerprint_class = strong
```

Imported from the `CPG_ORDER_HASH_ANNOTATION` constant defined in `analysis/ordering.py` (per `DOC-CMP-CORE-03.md §5.1`). The emitter MUST NOT substring, abbreviate, i18n-translate, or omit the annotation. The CI Scanipy-extension JSON Schema enforces this with a `const` constraint (`DOC-SARIF.md §11`); a violation fails CMP-CI-01 (hard).

The annotation MUST also appear in the SARIF native `fingerprints` block adjacency: `scanipy.cpg_order_hash/v1` is the hex hash; the annotation lives in `properties`. Both keys MUST be present together on every Result.

---

## 6. Dependency contract

`Depends-On:` **`CMP-CORE-02`, `CMP-CORE-03`** (per `WBS.md §20`).

This component **assumes**:

- `CMP-CORE-03` has produced a deterministic `cpg_order_hash` and `fingerprint_class` per snapshot, exposed via `CanonicalOrderResult` (`DOC-CMP-CORE-03.md §3.1`). The hash is hex-encoded for SARIF emission.
- `CMP-CORE-02` has produced `slice_fingerprint` and (re-emitted) `fingerprint_class` per finding (`DOC-CMP-CORE-02.md`).
- `CMP-ORCH-03` has constructed `Finding` records carrying every required wire field (`AC-ORCH-03a/b`). FND-01 does not re-derive `origin`, `S_version`, or `env_digest`.
- The `CPG_ORDER_HASH_ANNOTATION` constant is importable from `analysis.ordering`.

FND-01 does **not** depend on the `findings` table being persisted before emission — the canonical SARIF is computed from the in-memory `Finding` set passed in. Persistence (`CMP-FND-02`) and emission may proceed concurrently from the same upstream stream.

---

## 7. Failure modes and error contracts

### 7.1 Failure modes

| Mode | Detection | Response |
|---|---|---|
| Missing required `Result.properties` field (any of `scanipy.origin`, `scanipy.S_version`, `scanipy.env_digest`, `scanipy.cpg_order_hash`, `scanipy.cpg_order_hash_annotation`, `scanipy.fingerprint_class`, `scanipy.slice_fingerprint`, `scanipy.determinism_partition`, `scanipy.engine`, `scanipy.precondition_status`, `scanipy.class`, `scanipy.severity`, `scanipy.status`) | Pre-emit validation pass | **Halt emission**; raise `InvariantViolation(code="invariant_inv1_violation" \| "invariant_inv2_violation" \| "invariant_inv5_violation")` per `DOC-API.md §6.1`. Surfaces as HTTP 500 to the caller. |
| Annotation literal mismatch | Constant comparison against `CPG_ORDER_HASH_ANNOTATION` | Halt; raise `InvariantViolation(code="invariant_inv5_violation")`. |
| SARIF v2.1.0 schema validation failure | OASIS schema validator run on `SARIFLog.canonical_bytes` | Halt; raise `SARIFSchemaViolation(detail=...)`. Hard CI fail per `DOC-SARIF.md §12` gate 1. |
| Scanipy extension JSON Schema validation failure | Schema in `DOC-SARIF.md §11` | Halt; raise `SARIFExtensionViolation`. |
| Result ordering check failure (post-serialisation sanity check) | Re-parse and verify key order matches §3.3 rule 1 + result order matches §7 of `DOC-SARIF.md` | Halt; raise `CanonicalEmissionFailure`. Indicates an emitter bug, not data. |
| `llm_triage_flag = true` on an Attestor invocation | Caller contract violation | Attestor MUST reject the SARIFLog (it must run with `LLM_TRIAGE=off`, `AC-CP-05c`). FND-01 itself accepts both values — the constraint is enforced upstream. |

### 7.2 No retries

The emitter is pure and synchronous. There is no retry policy; a re-emission on the same inputs produces byte-identical output (this is the whole point — see `TST-INV-1-FND-01`).

### 7.3 Partition-incident routing

If a downstream `CMP-SNAP-04` re-partition flips a finding's `origin` after this scan's SARIF was emitted, the *historical* SARIF in S3 is **NOT** rewritten (`DOC-SARIF.md §10`). A subsequent scan's SARIF reflects the new partition. The `repartition_events` row + `provenance_records` re-partition record document the divergence.

---

## 8. Provenance threading

This component is a wire-form projection; it does not write `findings` or `provenance_records` directly. It **passes through** the four required fields verbatim and **produces the SARIF hash** (link 8 of the provenance chain) that `CMP-FND-03` consumes.

| Field on the wire (Result.properties) | Source `Finding` field | Required adjacency |
|---|---|---|
| `scanipy.origin` | `Finding.origin` | INV-1 — non-null, in `{deterministic-core, oracle-passthrough}` |
| `scanipy.S_version` | `Finding.S_version` | INV-2 — non-null |
| `scanipy.env_digest` | `Finding.env_digest` | INV-2 — non-null |
| `scanipy.cpg_order_hash` | `Finding.cpg_order_hash` (hex) | INV-5 — MUST be adjacent to the annotation in the JSON object |
| `scanipy.cpg_order_hash_annotation` | `CPG_ORDER_HASH_ANNOTATION` constant | INV-5 — literal string check (CI gate) |
| `scanipy.fingerprint_class` | `Finding.fingerprint_class` | `strong` / `weak` |
| `scanipy.slice_fingerprint` | `Finding.slice_fingerprint` (hex) | also in `fingerprints["scanipy.slice_fingerprint/v1"]` |
| `scanipy.determinism_partition` | `Finding.determinism_partition` | equal to `origin` at emission time |
| `scanipy.engine` | `Finding.engine` | one of `ifds`, `ide`, `semgrep`, `cpg-query`, `external` |
| `scanipy.precondition_status` | `Finding.precondition_status` | from the snapshot |

The SARIF hash output (`SARIFLog.sarif_hash`, per-partition `SARIFRun.sarif_hash`) feeds:

- `attestations.attestor_hash` (`DOC-DB.md §4.10`).
- `provenance_records.sarif_hash` (`DOC-PROVENANCE.md §3`, link 8).

A code-review check on FND-01's outputs: confirm every emitted `Result` carries all of the required `scanipy.*` properties, the annotation is literal, and the result list is sorted by `(cpg_order_hash, rule_id, uri, start_line)` ascending.

---

## 9. Acceptance criteria cross-reference

| AC ID | Verbatim from `SDD.md §8 CMP-FND-01` | Test ID | Label | Notes |
|---|---|---|---|---|
| `AC-FND-01a` | "All detector outputs validate against SARIF 2.1.0 schema." | `TST-AC-FND-01a` `[FORTHCOMING]` | `[UNIT]` | Asserts `SARIFLog.canonical_bytes` validates against the OASIS SARIF 2.1.0 schema. Hard CI gate per `DOC-SARIF.md §12 gate 1`. |
| `AC-FND-01b` | "Result ordering is the canonical order from CMP-CORE-03." | `TST-AC-FND-01b` `[FORTHCOMING]` | `[UNIT]` | Asserts within each Run the results are sorted by `(cpg_order_hash, rule_id, uri, start_line)` ascending (`DOC-SARIF.md §7`). Hard CI gate per `DOC-SARIF.md §12 gate 4`. |
| `TST-INV-1-FND-01` | — (invariant test) | `TST-INV-1-FND-01` `[FORTHCOMING]` | `[INVARIANT]` | Two runs with same `(findings, S_version, env_digest, LLM_TRIAGE=off)` produce byte-identical `SARIFLog.canonical_bytes`. Feeds `CMP-CP-05` (`AC-CP-05a`). |
| `TST-INV-2-FND-01` | — (invariant test) | `TST-INV-2-FND-01` `[FORTHCOMING]` | `[INVARIANT]` | Asserts non-null `S_version` and `env_digest` on every `Run.properties` and every `Result.properties`. |
| `TST-INV-5-FND-01` | — (invariant test) | `TST-INV-5-FND-01` `[FORTHCOMING]` | `[INVARIANT]` | Greps every emitted `Result` for the literal `cpg_order_hash_annotation` string; fails on any abbreviated/translated/missing variant. |

Per `WBS.md §10 CMP-FND-01`: tasks are `T-CMP-FND-01-01` (SARIF 2.1.0 normalisation), `T-CMP-FND-01-02` (attach slice fingerprint + `fingerprint_class`), `T-CMP-FND-01-03` (emit in canonical CPG order from `CMP-CORE-03`).

---

## 10. Open questions

- **`CLAR-SARIF-01` (DEFERRED).** Public hosting URL for the Scanipy SARIF extension JSON Schema (proposed `https://schemas.scanipy.io/sarif-extension/v1.0.0.json`). Until pinned, the schema is vendored locally (`schemas/sarif-extension/v1.0.0.json`) and CI runs against the vendored copy. Does not block emission; blocks first customer SARIF export GA.
- No new CLARs filed by this document.

If an Implementation Agent encounters ambiguity not covered here, file `CLAR-FND-NN` in `WBS.md §17` per `.claude/rules/03-scope.md`. **Do not invent missing scope.**

---

## Appendix A. Worked example (informative)

```python
from analysis.ordering import CPG_ORDER_HASH_ANNOTATION

def normalize(findings, *, scan_id, snapshot_id, codebase_id, commit_sha,
              S_version, env_digest, precondition_status, llm_triage_flag):
    core_results   = sorted(
        (_to_result(f) for f in findings if f.origin == "deterministic-core"),
        key=_result_sort_key,
    )
    oracle_results = sorted(
        (_to_result(f) for f in findings if f.origin == "oracle-passthrough"),
        key=_result_sort_key,
    )
    runs = (
        _build_run("core",   core_results,   scan_id, snapshot_id, codebase_id,
                   commit_sha, S_version, env_digest, precondition_status, llm_triage_flag),
        _build_run("oracle", oracle_results, scan_id, snapshot_id, codebase_id,
                   commit_sha, S_version, env_digest, precondition_status, llm_triage_flag),
    )
    log_obj = {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs":    [runs[0]._as_jsonable(), runs[1]._as_jsonable()],
    }
    canonical = _canonical_serialize(log_obj)   # DOC-SARIF §3 rules 1-8
    return SARIFLog(
        runs=runs,
        canonical_bytes=canonical + b"\n",
        sarif_hash=hashlib.sha256(canonical + b"\n").hexdigest(),
    )

def _result_sort_key(r):
    return (
        r["properties"]["scanipy.cpg_order_hash"],
        r["ruleId"],
        r["locations"][0]["physicalLocation"]["artifactLocation"]["uri"],
        r["locations"][0]["physicalLocation"]["region"]["startLine"],
    )

def _to_result(f):
    return {
        "ruleId":   f.rule_id,
        "level":    _level_from_severity(f.severity),
        "message":  {"text": f.message},
        "locations": [{
            "physicalLocation": {
                "artifactLocation": {"uri": f.uri},
                "region": {"startLine": f.start_line, "startColumn": f.start_col,
                           "endLine": f.end_line, "endColumn": f.end_col},
            },
        }],
        "fingerprints": {
            "scanipy.cpg_order_hash/v1":    f.cpg_order_hash,    # hex
            "scanipy.slice_fingerprint/v1": f.slice_fingerprint,
        },
        "properties": {
            "scanipy.origin":                    f.origin,
            "scanipy.S_version":                 f.S_version,
            "scanipy.env_digest":                f.env_digest,
            "scanipy.cpg_order_hash":            f.cpg_order_hash,
            "scanipy.cpg_order_hash_annotation": CPG_ORDER_HASH_ANNOTATION,
            "scanipy.fingerprint_class":         f.fingerprint_class,
            "scanipy.slice_fingerprint":         f.slice_fingerprint,
            "scanipy.determinism_partition":     f.determinism_partition,
            "scanipy.engine":                    f.engine,
            "scanipy.precondition_status":       f.precondition_status,
            "scanipy.class":                     f.class_,
            "scanipy.severity":                  f.severity,
            "scanipy.status":                    f.status,
            **({"scanipy.spec_provenance":   f.spec_provenance}  if f.spec_provenance  else {}),
            **({"scanipy.witness_blob_uri":  f.witness_blob_uri} if f.witness_blob_uri else {}),
        },
    }
```

---

## Appendix B. Cross-references

- `SDD.md §8 CMP-FND-01` — verbatim ACs.
- `WBS.md §10 CMP-FND-01` — task list (`T-CMP-FND-01-01..03`); `§15` invariant map; `§20` DAG.
- `DOC-SARIF` — §3 (canonical serialisation), §4 (two-Run model), §5 (Run schema), §6 (Result schema + required properties), §7 (canonical ordering), §10 (re-partition + historical SARIF), §11 (JSON Schema), §12 (CI gates).
- `DOC-PROVENANCE` §3 (link 8 `sarif_hash`), §10 (per-component threading).
- `DOC-INV` (INV-1 / INV-2 / INV-5 cross-component map).
- `DOC-PARTITION` (engine → origin partition rules).
- `DOC-DB` §4.10 (`attestations.attestor_hash`), §4.12 (`findings` source rows).
- `DOC-CMP-CORE-03` §5.1 (the `CPG_ORDER_HASH_ANNOTATION` constant).
- `.claude/rules/01-invariants.md` (INV-1, INV-2, INV-5).
- `.claude/rules/02-provenance.md` (threading rules).
- `.claude/rules/05-determinism.md` (two-partition discipline).
