# DOC-CMP-DET-03 — Class plugin scaffolding + content migration

**Status:** ACTIVE (Phase 0 output)
**Source-of-truth lineage:** `SDD.md §5 CMP-DET-03`, `PLAN.md §"Phase 2 — Detector catalog + combinator DSL + closure check"`, `SDD.md §11` (per-language staging), `WBS.md §6 CMP-DET-03`, `docs/cross-cutting/DOC-DSL.md`, `docs/cross-cutting/DOC-PARTITION.md`, `docs/cross-cutting/DOC-STAGING.md`.

When this document conflicts with `PLAN.md` / `SDD.md`, those upstream documents win and this one is corrected.

---

## 1. Component identity

| Field | Value |
|---|---|
| **CMP ID** | `CMP-DET-03` |
| **Subsystem** | Detector Catalog |
| **Staging** | per class — see `SDD.md §11` and `DOC-STAGING` |
| **Depends-On** | `CMP-DET-02` (`WBS.md §20`) |
| **Owner** | unassigned — see `CLAR-OWNER-01` (`WBS.md §17`) |
| **Tests** | `TST-AC-DET-03a`, `TST-AC-DET-03b` |
| **Backwards-compat link** | `AC-ORCH-01c` (`TST-AC-ORCH-01c`) — `scanipy --query extractall --run-semgrep` reproduces CVE-2025-61765 on Stage-A language |

---

## 2. Mandate

**SDD `Purpose:` (verbatim):**

> Ten `detectors/<class>/` directories with `specs/` skeletons; migrate `tarslip.yaml` → `detectors/path-traversal/specs/`; migrate CodeQL queries → `detectors/memory-safety/codeql/` tagged `oracle`.

**Operational role.** `CMP-DET-03` is the **content scaffold and migration tool** for the detector catalog. It does two things:

1. **Scaffold** the ten class directories with their `specs/`, `oracle/`, and `README.md` skeletons so that subsequent agents (Corpus Curator, Implementation) have a fixed shape to author into.
2. **Migrate** legacy detection content (the existing `tarslip.yaml` path-traversal taint definitions; the existing CodeQL queries for C/C++ memory-safety) into the v3.2 layout, preserving exactly enough fidelity to reproduce the historical CVE-2025-61765 finding (`AC-DET-03b`, `AC-ORCH-01c`).

The component is content-only — it writes no `Detector` records itself; the registry (`CMP-DET-02`) reads the scaffolded `manifest.yaml` and `specs/*.dsl.yaml` files at process boot. Migrated content carries provenance fields stamped upstream (`S_version` via `CMP-ORCH-01`, `determinism_partition` via `CMP-DET-02`'s engine derivation); `CMP-DET-03` is pass-through with respect to provenance threading.

---

## 3. Interface contract

### 3.1 Scaffolding generator

```python
# tools/scaffold_class.py

from pathlib import Path
from typing import Literal

ClassName = Literal[
    "injection", "path-traversal", "ssrf", "deserialization",
    "xss", "crypto-misuse", "authn-authz", "memory-safety",
    "secrets", "dep-cve",
]


def scaffold_class(
    class_name: ClassName,
    *,
    root: Path = Path("detectors/"),
    languages: tuple[str, ...] = (),
    default_engine: Literal["ifds", "ide", "semgrep", "cpg-query", "external"] = "ifds",
    stub_only: bool = True,
) -> None:
    """Create the directory skeleton for a class.

    Produces (relative to `root / class_name`):
      manifest.yaml          — stub with id / cwes / engine / severity_default / per_language_readiness
      specs/                 — DSL spec directory (engine ∈ {ifds, ide})
      specs/.gitkeep         — empty placeholder when stub_only=True
      oracle/                — native query directory (engine ∈ {semgrep, cpg-query, external})
      oracle/.gitkeep        — empty placeholder when stub_only=True
      README.md              — class-level documentation

    Idempotent: re-running on an existing scaffold updates the README and
    refreshes per_language_readiness in manifest.yaml without overwriting
    authored DSL files.

    Raises ScaffoldError if `root / class_name` exists with unexpected
    structure (e.g., files outside the expected skeleton)."""
```

### 3.2 Migration tool: `tarslip.yaml` → DSL specs

```python
# tools/migrate_tarslip.py

def migrate_tarslip(
    legacy_yaml: Path,
    target_dir: Path = Path("detectors/path-traversal/specs/"),
    *,
    dry_run: bool = False,
) -> MigrationReport:
    """Translate legacy `tarslip.yaml` content into one or more DSL spec
    files under `target_dir` (per DOC-DSL §2 PEG).

    The translation maps:
      tarslip:source           → source(access-path-pattern)
      tarslip:sink             → sink(access-path-pattern)
      tarslip:sanitizer        → sanitize(access-path-pattern)
      tarslip:propagator       → propagate(arg → ret | field)

    Anything in `legacy_yaml` that does not map cleanly to the DSL is a
    migration failure (MigrationAbortError); the tool does NOT emit a
    best-effort partial translation.

    Atomic-write contract:
      1. Stage every output file to a temp dir (`target_dir.parent / .migrate-XXXX`).
      2. fsync each staged file.
      3. Rename temp dir → target_dir (atomic on POSIX).
      4. On ANY error in steps 1–3: rollback temp dir; target_dir untouched.

    Returns a MigrationReport with input checksum, output file list, and
    every translation decision (for audit). Raises MigrationAbortError
    on any failure; the file system is left in its pre-call state."""
```

### 3.3 Migration tool: CodeQL queries → `memory-safety/codeql/` (oracle)

```python
def migrate_codeql_memory_safety(
    legacy_codeql_dir: Path,
    target_dir: Path = Path("detectors/memory-safety/codeql/"),
    *,
    dry_run: bool = False,
) -> MigrationReport:
    """Copy existing CodeQL queries into the oracle subtree, tagging each
    in the manifest as engine='external'.

    Per OOS-CC-01, C/C++ memory-safety remains oracle-passthrough through
    v3.2; this migration preserves that posture. The DSL closure check
    (CMP-DET-01) does NOT apply to these queries — they are native CodeQL
    .ql / .qll files, surfaced to the registry as engine='external' with
    determinism_partition='oracle-passthrough' (per DOC-PARTITION §3).

    Same atomic-write contract as migrate_tarslip().
    Raises MigrationAbortError on any failure."""
```

### 3.4 Error types

```python
class ScaffoldError(Exception):
    """A scaffold operation found unexpected file-system state."""


class MigrationAbortError(Exception):
    """A migration tool halted mid-translation. The file system has been
    rolled back to its pre-call state (no partial writes)."""
    code: str         # E-MIG-001..005
    legacy_path: Path
    reason: str
```

---

## 4. Inputs and outputs

### 4.1 Inputs

| Input | Source | Used by |
|---|---|---|
| `tarslip.yaml` | legacy v2 path-traversal definitions (historical, pre-v3.2) | `migrate_tarslip()` |
| Legacy CodeQL queries (`*.ql`, `*.qll`) | existing C/C++ memory-safety content | `migrate_codeql_memory_safety()` |
| `ClassName` values (10) | `injection`, `path-traversal`, `ssrf`, `deserialization`, `xss`, `crypto-misuse`, `authn-authz`, `memory-safety`, `secrets`, `dep-cve` | `scaffold_class()` |

### 4.2 Outputs — directory tree

```
detectors/
├── injection/
│   ├── manifest.yaml
│   ├── specs/        (engine=ifds|ide → DSL files, parsed by CMP-DET-01)
│   ├── oracle/       (engine=semgrep|cpg-query|external → native queries)
│   └── README.md
├── path-traversal/
│   ├── manifest.yaml
│   ├── specs/        ← tarslip.yaml is migrated into here (T-CMP-DET-03-02)
│   ├── oracle/
│   └── README.md
├── ssrf/                 (same shape)
├── deserialization/      (same shape)
├── xss/                  (same shape)
├── crypto-misuse/        (same shape; mixed engine; both subtrees populated)
├── authn-authz/          (same shape; mixed engine)
├── memory-safety/
│   ├── manifest.yaml
│   ├── specs/        (empty stub; OOS-CC-01 keeps this oracle-passthrough)
│   ├── codeql/       ← CodeQL queries migrate here (T-CMP-DET-03-03)
│   ├── oracle/
│   └── README.md
├── secrets/              (oracle only — secret patterns)
└── dep-cve/              (oracle only — SCA results)
```

Migration mapping:

- `tarslip.yaml` → `detectors/path-traversal/specs/python-os-path-traversal.dsl.yaml` (and any Java sibling required by the canonical CVE-2025-61765 reproduction, see `AC-DET-03b`). Worked example in `DOC-DSL §8.2`.
- CodeQL `*.ql`/`*.qll` → `detectors/memory-safety/codeql/*` with `manifest.yaml` declaring `engine: external` and `determinism_partition` derived to `oracle-passthrough` by `CMP-DET-02`.

### 4.3 Side effects

- **File-system writes** under `detectors/`. Atomic (temp-dir + rename); on any error the file system is rolled back.
- **No DB writes.** `CMP-DET-03` is purely content scaffolding; persistence in the registry is `CMP-DET-02`'s responsibility.
- **No process state mutation.** The component is a one-shot CLI tool; it does not run in the worker.

### 4.4 Provenance fields written

**None.** `CMP-DET-03` is pass-through with respect to provenance threading. The migrated DSL specs and oracle queries carry provenance only when registered by `CMP-DET-02` and consumed by `CMP-ORCH-03`:

| Field | Set by | Source |
|---|---|---|
| `determinism_partition` | `CMP-DET-02` | derived from `manifest.engine` |
| `origin` (per finding) | `CMP-ORCH-03` | derived from `Detector.engine` |
| `S_version` | `CMP-ORCH-01` | scan-submission input |
| `env_digest` | `CMP-SNAP-01` | container image digest |
| `cpg_order_hash` | `CMP-CORE-03` | with conditional-canonicality annotation (INV-5) |

Migrated content carries these only after registration; the migration tool does not synthesise any of them.

---

## 5. Invariants touched

| Inv | How this component discharges it | Test |
|---|---|---|
| **INV-1, INV-2, INV-3, INV-4, INV-5, INV-6** | **Pass-through.** `CMP-DET-03` emits no findings, writes no provenance fields, and does not own any invariant. The migrated content's partition is derived downstream by `CMP-DET-02` from the `engine` field; the migrated path-traversal spec parses through the `CMP-DET-01` DSL closure check at registration (INV-4 is enforced upstream). The CodeQL migration preserves `OOS-CC-01` — C/C++ memory-safety remains `oracle-passthrough` (per `SDD.md §12` and `.claude/rules/03-scope.md`). | n/a |

---

## 6. Dependency contract

### 6.1 `CMP-DET-02` (Detector registry + closure check)

`CMP-DET-03` assumes:

- `DetectorRegistry.load_manifests()` reads `detectors/<class>/manifest.yaml` plus, for core engines, `detectors/<class>/specs/*.dsl.yaml`. The scaffold and migration outputs must conform to that contract.
- Manifests must declare every field listed in `AC-DET-02b` (`id`, `cwes`, `languages`, `frameworks`, `engine`, `severity_default`, `per_language_readiness`); the scaffold generator emits stubs for all of them.
- Engine values are restricted to `{ifds, ide, semgrep, cpg-query, external}` (`AC-DET-02c`). The scaffold and migration emit only these values.

### 6.2 `CMP-DET-01` (transitively)

The migrated `tarslip.yaml` → DSL output must parse through `CMP-DET-01 parse_spec()`. Any legacy construct that does not map to a sanctioned primitive (`source`, `sink`, `sanitize`, `propagate`) or that requires an out-of-DSL operator triggers `MigrationAbortError(E-MIG-002)` and rollback.

---

## 7. Failure modes and error contracts

### 7.1 Migration error codes

| Code | Condition | Diagnostic |
|---|---|---|
| **`E-MIG-001`** | Legacy file not found / unreadable | `legacy source '<path>' not found or unreadable` |
| **`E-MIG-002`** | Legacy construct does not map to the DSL | `legacy construct '<construct>' has no DSL equivalent; file CLAR-DET-* before extending the grammar` |
| **`E-MIG-003`** | Target directory exists with non-skeleton content | `target '<path>' already contains authored content; refusing to overwrite` |
| **`E-MIG-004`** | Atomic-rename failed (file-system error) | `atomic rename of '<temp>' → '<target>' failed: <errno>` |
| **`E-MIG-005`** | Translated output fails downstream `CMP-DET-01 parse_spec()` validation | `translated spec '<path>' failed DSL closure check: <DSLError>` |

### 7.2 Atomicity contract — **"halt, do not partially-write"**

Migration tools enforce atomic semantics by construction:

1. **Stage** all output files to a temp directory (`<target>.migrate-<random>`).
2. **fsync** each staged file (and the temp dir's parent on POSIX).
3. **Atomic rename** of temp dir → target dir (`os.replace()` on POSIX is atomic for same-FS renames).
4. **On any error in steps 1–3:** the temp dir is `rmtree`-ed; the target directory is **untouched**; `MigrationAbortError` is raised with the offending code.

The contract is enforced by the wrapping `_atomic_migrate(...)` helper; individual migration steps may not write to the target directory directly. A migration that has any partial output on the target side is a bug, not a degraded mode.

### 7.3 Scaffold idempotency

`scaffold_class()` is idempotent on re-run:

- Existing `manifest.yaml` is **merged**, not overwritten: `per_language_readiness` keys are refreshed; authored fields (`id`, `cwes`, `frameworks`, `severity_default`, `engine`) are preserved unless they were stubs.
- Authored DSL files under `specs/` are **never** touched by the scaffold tool.
- `README.md` is regenerated from the template.

`ScaffoldError` is raised if the target tree contains structurally unexpected files (e.g., a `manifest.yml` instead of `manifest.yaml`) — the tool refuses to guess; the operator must clean up first.

### 7.4 No fallback / no best-effort

Both migration tools and the scaffold generator are total functions with respect to their inputs: either the inputs translate cleanly to the v3.2 layout or the tool aborts. There is **no** `--lenient` mode; lenient migration would silently lose detection coverage and is forbidden.

---

## 8. Provenance threading

`CMP-DET-03` does not thread provenance. The four-field rule (`.claude/rules/02-provenance.md`) applies to consumers of the migrated content:

- `CMP-DET-02` derives `determinism_partition` from the migrated `manifest.engine`.
- `CMP-ORCH-03` stamps `origin` on each finding emitted via the migrated specs.
- `CMP-ORCH-01` / `CMP-SNAP-01` / `CMP-CORE-03` populate `S_version`, `env_digest`, and `cpg_order_hash` as on any other scan.

**Verification cross-link.** `AC-DET-03b` requires that the migrated path-traversal spec reproduces the historical CVE-2025-61765 finding. That finding's reproduction surface — `origin = deterministic-core`, `S_version` carrying the migration generation, `env_digest` from the worker image, `cpg_order_hash` annotated `canonical iff fingerprint_class = strong` — is asserted in `TST-AC-DET-03b` and tied to the backwards-compat surface in `TST-AC-ORCH-01c`.

---

## 9. Acceptance criteria cross-reference

### 9.1 SDD acceptance criteria (verbatim)

> **AC-DET-03a:** All ten class directories register without error (stubs permitted).
>
> **AC-DET-03b:** The migrated path-traversal spec produces the historical CVE-2025-61765 finding (ties to AC-ORCH backwards-compat).

### 9.2 AC → TST mapping

| AC | TST id | Kind | Hard gate | Notes |
|---|---|---|---|---|
| `AC-DET-03a` | `TST-AC-DET-03a` | `[UNIT]` | yes | Run `scaffold_class()` for every one of the ten `ClassName` values; assert `DetectorRegistry.load_manifests()` completes without error on the resulting tree (stub manifests permitted). |
| `AC-DET-03b` | `TST-AC-DET-03b` | `[REGRESSION]` | yes | Run `migrate_tarslip()` against the legacy file; load the migrated spec via `CMP-DET-01 parse_spec()`; run a Stage-A-language scan against the historical CVE-2025-61765 repo state; assert exactly one finding with `rule_id` matching the migrated spec id, `origin = deterministic-core`, and the witness blob matching the canonical witness. Tied to `TST-AC-ORCH-01c` for the `scanipy --query extractall --run-semgrep` backwards-compat surface. |

### 9.3 Worked migrated example

See `DOC-DSL §8.2` for the migrated Python path-traversal spec; the migration tool produces that file (and any Java sibling required by CVE-2025-61765) as its output. A minimal manifest stub for the migrated path-traversal directory:

```yaml
# detectors/path-traversal/manifest.yaml
id:                "path-traversal"
cwes:              ["CWE-22"]
languages:         ["python", "java"]
frameworks:        ["flask", "werkzeug", "servlet"]
engine:            "ifds"
severity_default:  "high"
per_language_readiness:
  python: "ready"
  java:   "ready"
```

---

## 10. Open questions

| CLAR | Status | Bearing on this component |
|---|---|---|
| `CLAR-DET-01` | DEFERRED | Persistence surface for the registry (filed by `DOC-CMP-DET-02`); affects whether scaffolded manifests are loaded from disk or hydrated from a SQL table. Default assumption: on-disk YAML. |
| `CLAR-OWNER-01` | DEFERRED | Module owner unassigned. |
| `OOS-CC-01` | OUT OF SCOPE | C/C++ memory-safety port to core is OOS through v3.2; the CodeQL migration preserves `oracle-passthrough` posture. |

---

## 11. References

- `PLAN.md §"Phase 2 — Detector catalog + combinator DSL + closure check"` — `tarslip.yaml` → `detectors/path-traversal/specs/`; CodeQL → `detectors/memory-safety/codeql/` tagged `oracle`.
- `SDD.md §5 CMP-DET-03` — verbatim AC source.
- `SDD.md §11` — per-language staging; the ten classes' per-language readiness.
- `SDD.md §12` — out-of-scope register (OOS-CC-01).
- `WBS.md §6` — task list `T-CMP-DET-03-01..04`.
- `WBS.md §20` — dependency DAG (DET-03 → [DET-02]).
- `docs/cross-cutting/DOC-DSL.md §8.2` — migrated path-traversal worked example.
- `docs/cross-cutting/DOC-PARTITION.md §3` — engine → origin mapping (consumed at registration of the migrated content).
- `docs/cross-cutting/DOC-STAGING.md` — per-language staging table.
- `docs/components/DOC-CMP-DET-01.md`, `docs/components/DOC-CMP-DET-02.md` — upstream contracts.
- `.claude/rules/03-scope.md` — `OOS-CC-01` deflection rule.

---

*Document end. Status: ACTIVE. Next review: at first acceptance of `CMP-DET-03` `DONE`.*
