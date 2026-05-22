# DOC-CMP-DET-02 — Detector registry + closure check

**Status:** ACTIVE (Phase 0 output)
**Source-of-truth lineage:** `SDD.md §5 CMP-DET-02`, `PLAN.md §"Engine adapters and the determinism partition"`, `PLAN.md §"Phase 2 — Detector catalog + combinator DSL + closure check"`, `SDD.md §2 INV-1, INV-2`, `WBS.md §6 CMP-DET-02`, `docs/cross-cutting/DOC-DSL.md`, `docs/cross-cutting/DOC-PARTITION.md`, `docs/cross-cutting/DOC-DB.md`.

When this document conflicts with `PLAN.md` / `SDD.md`, those upstream documents win and this one is corrected.

---

## 1. Component identity

| Field | Value |
|---|---|
| **CMP ID** | `CMP-DET-02` |
| **Subsystem** | Detector Catalog |
| **Staging** | cross-cutting |
| **Depends-On** | `CMP-DET-01` (`WBS.md §20`) |
| **Owner** | unassigned — see `CLAR-OWNER-01` (`WBS.md §17`) |
| **Tests** | `TST-AC-DET-02a`, `TST-AC-DET-02b`, `TST-AC-DET-02c` |
| **Persistence question** | `CLAR-DET-01` — registry table vs in-memory + on-disk YAML |

---

## 2. Mandate

**SDD `Purpose:` (verbatim):**

> Discover `detectors/<class>/`, load `manifest.yaml`, run the grammar/closure check (membership in the distributive DSL — not a distributivity decision procedure), derive `determinism_partition` from the `engine` field.

**Operational role.** `CMP-DET-02` is the gatekeeper between authored detector content (DSL specs and oracle queries) and the analysis pipeline. It is the **only** place specs are admitted to the system; if registration rejects a spec, no downstream component (`CMP-CORE-01`, `CMP-ORCH-03`) will ever see it. Two roles fold together:

1. **Closure check** (`AC-DET-02a`). Membership in the distributive-by-construction DSL is decidable (`DOC-DSL §7`); out-of-DSL specs are rejected with a precise diagnostic (`E-DSL-001..009`). This is a grammar/closure check, **not** a decision procedure for distributivity of arbitrary functions.
2. **Partition derivation** (`AC-DET-02c`). The `engine` field of each manifest record maps deterministically to one of the two partitions. The mapping is the source of truth for `INV-1` and is consumed by `CMP-ORCH-03` when stamping `origin` on findings.

---

## 3. Interface contract

### 3.1 `Detector` dataclass — the registry record

```python
# detectors/registry.py

from dataclasses import dataclass
from typing import Literal

EngineTag = Literal["ifds", "ide", "semgrep", "cpg-query", "external"]
DeterminismPartition = Literal["deterministic-core", "oracle-passthrough"]
LanguageReadiness = Literal["ready", "front-end-blocked", "stage-gated"]


@dataclass(frozen=True)
class Detector:
    """One registry row, derived from a manifest.yaml + (for engine ∈ {ifds, ide})
    a parsed DSL Spec. Required fields per AC-DET-02b."""
    id:                      str                           # globally unique
    cwes:                    tuple[str, ...]               # e.g. ("CWE-89",)
    languages:               tuple[str, ...]               # per Language enum
    frameworks:              tuple[str, ...]               # e.g. ("flask", "django")
    engine:                  EngineTag
    severity_default:        Literal["low","medium","high","critical"]
    determinism_partition:   DeterminismPartition          # derived, not authored
    per_language_readiness:  dict[str, LanguageReadiness]  # one row per language
    # For core engines, the parsed DSL spec is carried inline; for oracle
    # engines, the path to the native query is carried instead.
    spec:                    "Spec | None"                 # CMP-DET-01 Spec
    oracle_query_path:       str | None                    # used iff engine is oracle
```

### 3.2 Registry interface

```python
class DetectorRegistry:
    """Process-singleton registry. Loaded at process start; never mutated
    after load. All Depends-On of CMP-DET-02 are read-only consumers."""

    def load_manifests(self, root: str = "detectors/") -> None:
        """Discover detectors/<class>/manifest.yaml under `root`; parse each;
        for engine ∈ {ifds, ide}, also load every detectors/<class>/specs/*.dsl.yaml
        via CMP-DET-01 parse_spec(); for oracle engines, validate the
        native query file exists. Calls register(...) for each.
        Raises RegistryLoadError on any failure (no partial-load mode)."""

    def register(self, detector: Detector) -> None:
        """Run the closure check on a single Detector and admit it.
        Raises DSLError(E-DSL-*) if a DSL spec falls outside the grammar.
        Raises RegistryError(E-REG-*) for manifest-level violations.
        Idempotent on detector.id only at process boot; re-registration
        with the same id after boot is rejected (E-REG-005)."""

    def all_for(self, *, language: str, class_: str) -> tuple[Detector, ...]:
        """Read-only query consumed by CMP-ORCH-03 when dispatching detectors."""

    def by_id(self, detector_id: str) -> Detector:
        """Lookup; raises KeyError on miss."""

    def all(self) -> tuple[Detector, ...]:
        """Full iteration; consumed by CMP-CP-05 (Attestor) to enumerate
        partitions before each run."""
```

### 3.3 The closure-check function

```python
def closure_check(detector: Detector) -> None:
    """Verify the grammar/closure check on a detector record.

    For engine ∈ {ifds, ide}:
      - detector.spec is not None
      - detector.spec parses through CMP-DET-01 parse_spec() (already enforced
        upstream; this is a defense-in-depth re-validation)
      - every primitive instance has a discharged distributivity obligation
      - composition shape is one of the sanctioned compositions in DOC-DSL §4
      - detector.engine ∈ {ifds, ide} (E-DSL-009 if not)

    For engine ∈ {semgrep, cpg-query, external}:
      - detector.spec is None
      - detector.oracle_query_path is not None and the file exists
      - no grammar check applies; the partition is `oracle-passthrough`

    Manifest-level checks (all engines):
      - id is globally unique within the registry
      - cwes, languages, frameworks, severity_default, per_language_readiness
        are present and well-formed (AC-DET-02b)

    Raises DSLError(E-DSL-001..009) or RegistryError(E-REG-001..006).
    Returns None on success."""
```

### 3.4 The engine → partition derivation (verbatim from `DOC-PARTITION §3`)

```python
CORE_ENGINES   = ("ifds", "ide")
ORACLE_ENGINES = ("semgrep", "cpg-query", "external")

def derive_partition(engine: EngineTag) -> DeterminismPartition:
    """AC-DET-02c. The engine → determinism_partition mapping is normative;
    new engines may not be added without amending SDD AC-DET-02c,
    .claude/rules/05-determinism.md, and DOC-PARTITION §3 in lockstep."""
    if engine in CORE_ENGINES:
        return "deterministic-core"
    if engine in ORACLE_ENGINES:
        return "oracle-passthrough"
    raise RegistryError(
        f"E-REG-006: engine={engine!r} not in the enumerated set; "
        f"register a new engine via AC-DET-02c first."
    )
```

---

## 4. Inputs and outputs

### 4.1 Input: `manifest.yaml` files

One per detector under `detectors/<class>/manifest.yaml`. Required keys per `AC-DET-02b`:

```yaml
# detectors/<class>/manifest.yaml
id:                 "java-jdbc-sqli"
cwes:               ["CWE-89"]
languages:          ["java"]
frameworks:         ["jdbc", "spring-jdbc"]
engine:             "ifds"                  # ifds | ide | semgrep | cpg-query | external
severity_default:   "high"
per_language_readiness:
  java:    "ready"
  python:  "front-end-blocked"
```

For core engines, the manifest is accompanied by `detectors/<class>/specs/*.dsl.yaml` files (parsed by `CMP-DET-01`). For oracle engines, the manifest names the native query file (e.g., `oracle_query_path: oracle/sqli.semgrep.yaml`).

### 4.2 Output: in-memory `DetectorRegistry`

After `load_manifests()` succeeds, `DetectorRegistry` is a frozen, process-wide singleton. It is read by `CMP-CORE-01`, `CMP-ORCH-03`, `CMP-TRI-02` (e-process gate), and `CMP-CP-05` (Attestor). The registry never mutates after boot — re-registration after boot is rejected (`E-REG-005`).

### 4.3 Persistence — see `CLAR-DET-01`

`AC-DET-02b` mandates that manifest records be **persisted**. `DOC-DB.md` does not currently define a `detectors` table; the proposed-default in `CLAR-DET-01` is:

- On-disk YAML manifests (`detectors/<class>/manifest.yaml`) are the source of truth.
- The in-memory `DetectorRegistry` is rebuilt at every process start from those files.
- Accepted DSL ASTs reach the database only via `spec_versions.spec_set` (jsonb), per `DOC-DB §4.9`, when a spec is admitted to an `S_version`.

If `CLAR-DET-01` resolves to a SQL `detectors` table, `DOC-DB.md §4` must be amended and this section updated in lockstep. Until then, do not add a SQL table inline (`RULE-4`).

### 4.4 Side effects

- **Process-singleton mutation at boot only.** `load_manifests()` populates the registry; after boot the registry is read-only.
- **No file-system writes.** `CMP-DET-02` does not write to disk.
- **No DB writes.** Accepted spec-set persistence is `CMP-TRI-02`'s responsibility via `spec_versions`.

### 4.5 Provenance fields written

`CMP-DET-02` stamps `determinism_partition` on every `Detector` record at registration time (`AC-DET-02c`). This field is **derived**, not authored, and is read by `CMP-ORCH-03` when stamping `origin` per finding (`DOC-PARTITION §4`).

| Field | Where stamped | Source | INV |
|---|---|---|---|
| `Detector.determinism_partition` | at `register()` | `derive_partition(detector.engine)` | INV-1 (consumed by ORCH-03) |
| `S_version` | not stamped here | comes from scan submission (`CMP-ORCH-01`) | INV-2 (pass-through) |
| `env_digest` | not stamped here | comes from snapshot worker (`CMP-SNAP-01`) | INV-2 (pass-through) |

---

## 5. Invariants touched

| Inv | How this component discharges it | Test |
|---|---|---|
| **INV-1** (determinism partition) | Derives `determinism_partition` from `engine` at registration (`AC-DET-02c`); the value is consumed by `CMP-ORCH-03` to stamp `origin` per finding. The registry refuses to load a manifest whose `engine` falls outside the enumerated set, guaranteeing every downstream finding has a well-defined partition. | `TST-AC-DET-02c`, `TST-INV-1-FND-02` (downstream NOT NULL) |
| **INV-2** (versioned parameters) | Pass-through. Each `Detector` carries the `id` and `cwes` referenced by spec-set acceptance (`CMP-TRI-02`); the `S_version` itself is stamped downstream (`CMP-ORCH-01`). | n/a (consumed by `TST-INV-2-ORCH-03`) |
| **INV-4** (DSL closure check) | **Defense in depth.** `closure_check()` re-validates that DSL specs lie within the distributive-by-construction grammar. The owner is `CMP-DET-01`; `CMP-DET-02` is the consumer that refuses to admit out-of-DSL content. A spec embedding arbitrary code is rejected, never analyzed (`AC-DET-02a`). | `TST-AC-DET-02a` |
| **INV-3, INV-5, INV-6** | Pass-through. | n/a |

---

## 6. Dependency contract

### 6.1 `CMP-DET-01` (Combinator DSL)

`CMP-DET-02` assumes:

- `parse_spec(source_text)` returns a frozen `Spec` for well-formed DSL files and raises `DSLError(E-DSL-001..009)` for any other input.
- `all_obligations_discharged()` returns `True` at boot — i.e., every primitive and every sanctioned composition has a discharged distributivity proof. If `False`, the registry refuses to start (the upstream boot-guard handles this; `CMP-DET-02` does not retry).
- The set of admissible primitive heads is exactly `{source, sink, sanitize, propagate}`. Adding a head is a `CLAR-DET-*` event, never an inline extension.

### 6.2 No other upstream dependencies

`CMP-DET-02` is otherwise standalone (`WBS.md §20`).

---

## 7. Failure modes and error contracts

### 7.1 DSL-level rejections (passed through from `CMP-DET-01`)

The nine `E-DSL-001..009` codes from `DOC-DSL §6` and `DOC-CMP-DET-01 §7.1` are surfaced verbatim. The registry never silently accepts a DSL parse failure; rejection is total.

### 7.2 Manifest-level rejections (registry-specific)

| Code | Condition | Diagnostic |
|---|---|---|
| **`E-REG-001`** | Missing required field in `manifest.yaml` (`id`, `cwes`, `languages`, `frameworks`, `engine`, `severity_default`, `per_language_readiness`) | `missing required manifest field '<name>' (AC-DET-02b)` |
| **`E-REG-002`** | `engine` value not in the enumerated set | `engine='<value>' not in {ifds, ide, semgrep, cpg-query, external} (AC-DET-02c)` |
| **`E-REG-003`** | Duplicate `id` across detectors | `detector id '<id>' is already registered` |
| **`E-REG-004`** | Oracle engine declared but `oracle_query_path` missing or file not found | `engine='<engine>' requires oracle_query_path; file '<path>' not found` |
| **`E-REG-005`** | Re-registration attempt after process boot | `registry is read-only after load_manifests(); re-registration of '<id>' rejected` |
| **`E-REG-006`** | Engine reached `derive_partition` with an unknown value (defense in depth — should have been caught by `E-REG-002`) | `engine='<value>' not in the enumerated set; register a new engine via AC-DET-02c first` |

### 7.3 No partial-load mode

`load_manifests()` is **atomic**. On the first failure it raises `RegistryLoadError(code, errors=[...])` with the full list of detected errors and **leaves the registry empty**. There is no "load what you can" mode — a half-loaded registry would silently mis-partition findings and is therefore forbidden.

### 7.4 No fallback path

`CMP-DET-02` has no degraded mode. Either every detector loads cleanly or the process refuses to serve scans.

---

## 8. Provenance threading

### 8.1 Engine → origin mapping table (verbatim from `DOC-PARTITION §3` and `AC-DET-02c`)

| `engine` value | `determinism_partition` derived | Downstream `origin` (set by `CMP-ORCH-03`) |
|---|---|---|
| `ifds` | `deterministic-core` | `deterministic-core` |
| `ide` | `deterministic-core` | `deterministic-core` |
| `semgrep` | `oracle-passthrough` | `oracle-passthrough` |
| `cpg-query` | `oracle-passthrough` | `oracle-passthrough` |
| `external` | `oracle-passthrough` | `oracle-passthrough` |

A new engine cannot be added without amending this table, `SDD.md AC-DET-02c`, `.claude/rules/05-determinism.md`, and `DOC-PARTITION §3` simultaneously (`RULE-4`).

### 8.2 What `CMP-DET-02` does **not** write

`CMP-DET-02` does not write `origin`, `S_version`, `env_digest`, `cpg_order_hash`, `slice_fingerprint`, or any field on the `findings` table. The four-field threading rule (`.claude/rules/02-provenance.md`) applies to detection-emitting components; the registry only stamps `determinism_partition` on its own record, which the worker (`CMP-ORCH-03`) reads to choose the per-finding `origin`.

### 8.3 Mixed detectors

A mixed detector (e.g., `crypto-misuse` with both IFDS taint flow and pattern matches) is registered as two or more `Detector` records (one per emission engine), each with its own `determinism_partition`. There is **no** `Detector.engine = "mixed"` value; the enum has exactly five entries. Per-finding `origin` selection happens at `CMP-ORCH-03` (`DOC-PARTITION §3.1`).

---

## 9. Acceptance criteria cross-reference

### 9.1 SDD acceptance criteria (verbatim)

> **AC-DET-02a:** Registration rejects a spec outside the DSL with a precise diagnostic.
>
> **AC-DET-02b:** Manifest records `id`, `cwes`, `languages`, `frameworks`, `engine`, `severity_default`, derived `determinism_partition`, per-language readiness.
>
> **AC-DET-02c:** `engine ∈ {ifds, ide}` ⇒ partition `deterministic-core`; `engine ∈ {semgrep, cpg-query, external}` ⇒ `oracle-passthrough`.

### 9.2 AC → TST mapping

| AC | TST id | Kind | Hard gate | Notes |
|---|---|---|---|---|
| `AC-DET-02a` | `TST-AC-DET-02a` | `[NEGATIVE]` | yes | One test per `E-DSL-001..009` plus one per `E-REG-001..006`. |
| `AC-DET-02b` | `TST-AC-DET-02b` | `[UNIT]` | yes | Asserts every required field is present after `register()` and `determinism_partition` is derived (not authored). |
| `AC-DET-02c` | `TST-AC-DET-02c` | `[UNIT]` | yes | Parametrised over every `EngineTag` value; verifies the exact mapping table in §8.1. |

---

## 10. Open questions

| CLAR | Status | Bearing on this component |
|---|---|---|
| `CLAR-DET-01` | DEFERRED (filed by this document) | Persistence surface for the registry. Default = on-disk YAML + in-memory `DetectorRegistry`; SQL `detectors` table not added. Architect Agent to ratify. |
| `CLAR-OWNER-01` | DEFERRED | Module owner unassigned. |

---

## 11. References

- `PLAN.md §"Engine adapters and the determinism partition"` — partition mapping.
- `PLAN.md §"Phase 2 — Detector catalog + combinator DSL + closure check"` — `detectors/registry.py`, `analysis/ifds/dsl/`, manifest fields.
- `SDD.md §5 CMP-DET-02` — verbatim AC source.
- `SDD.md §2 INV-1` — determinism partition.
- `WBS.md §6` — task list `T-CMP-DET-02-01..04`.
- `WBS.md §20` — dependency DAG (DET-02 → [DET-01]).
- `docs/cross-cutting/DOC-DSL.md` — grammar reference.
- `docs/cross-cutting/DOC-PARTITION.md` — engine → origin mapping.
- `docs/cross-cutting/DOC-DB.md` — persistence schema (`spec_versions.spec_set` for accepted DSL ASTs).
- `docs/cross-cutting/DOC-PROVENANCE.md` — provenance threading rules.
- `.claude/rules/05-determinism.md` — operational partition rules.

---

*Document end. Status: ACTIVE. Next review: at `CLAR-DET-01` resolution or first acceptance of `CMP-DET-02` `DONE`.*
