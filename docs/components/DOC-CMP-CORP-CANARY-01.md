# DOC-CMP-CORP-CANARY-01 — Canary repo set across four SCMs

## 1. Component identity

- **CMP-ID:** `CMP-CORP-CANARY-01`
- **Subsystem:** Corpora (Phase 13 cross-cutting deliverable, `WBS.md §16`)
- **Staging:** Stage A (cross-cutting — anchors INV-1 Attestor gate from Stage A onward)
- **Owning agent:** Corpus Curator (`/corpus-agent`)
- **Status code:** `READY` once `CMP-SCM-02` and `CMP-SCM-03` are DONE (`WBS.md §20`: `CMP-CORP-CANARY-01 → [CMP-SCM-02, CMP-SCM-03]`).
- **Artifact root:** `tests/corpora/canary/` (metadata + manifest only; actual repository content lives on GH/GitLab/Bitbucket/ADO)

## 2. Mandate

Verbatim from `SDD.md §16` (CMP-CORP-CANARY-01):

> *100 canary repos mirrored to GitHub, GitLab, Bitbucket, Azure DevOps; used by `TST-AC-CORE-01a` (determinism) and `TST-AC-SCM-03c` (identical commit resolution).*

Operational role: this is the corpus that the Determinism Attestor (`CMP-CP-05`) runs over on every detector / engine / `Env` change — the byte-identical-SARIF assertion that anchors INV-1 in CI. It is also the corpus that `T-CMP-SCM-03-04` mirrors across all four providers to assert that the four `CMP-SCM-*` connectors resolve the same commit identifier to byte-identical source content. The corpus is therefore the single physical artifact through which the v3.2 baseline's "byte-identical core-partition SARIF on every detector/engine/Env change" claim (`WBS.md §21`, Definition of Done) becomes testable.

## 3. Interface contract — data artifact

### 3.1 Directory layout

```
tests/corpora/canary/
├── corpus.lock                # signed manifest; 100 entries
├── methodology.md             # selection rationale + per-SCM mirror procedure
├── repos/
│   ├── <repo-id>/
│   │   ├── metadata.yaml      # per-repo provenance + per-SCM coords
│   │   └── README.md          # license, attribution
└── README.md
```

Actual source content is **not** vendored; the corpus is a manifest pointing to mirrored remotes at pinned commits.

### 3.2 `corpus.lock` schema

```yaml
corpus_id: CORP-CANARY-01
corpus_version: vX.Y.Z          # semver
corpus_digest: sha256:<hex>     # over canonical-sorted per-repo manifest digests
created_at: <iso-8601>
repo_count: 100
repos:
  - id: <repo-id>
    upstream_origin: <canonical source URL>
    pinned_commit: <sha>        # single SHA, identical across all four mirrors
    license: <SPDX-id>
    redistribution: { allowed: <bool>, rationale: <string> }
    languages: [java, python, ...]
    mirrors:
      github:    { url: "https://github.com/scanipy-canary/<repo-id>", verified_commit: <sha> }
      gitlab:    { url: "https://gitlab.com/scanipy-canary/<repo-id>", verified_commit: <sha> }
      bitbucket: { url: "https://bitbucket.org/scanipy-canary/<repo-id>", verified_commit: <sha> }
      azure_devops: { url: "https://dev.azure.com/scanipy-canary/<repo-id>/_git/<repo-id>", verified_commit: <sha> }
    repo_digest: sha256:<hex>
```

**SCM-parity contract:** for every repo, the four `verified_commit` SHAs MUST be equal AND MUST equal `pinned_commit`. A mismatch is a hard `T-CMP-SCM-03-04` failure (asserts identical commit resolution under `AC-SCM-03c`).

### 3.3 Per-repo metadata file

```yaml
# tests/corpora/canary/repos/<repo-id>/metadata.yaml
id: <repo-id>
upstream_origin: <URL>
pinned_commit: <sha>
license: <SPDX-id>
license_allows_mirror: <bool>
languages: [...]
size_loc: <int>
selection_rationale: <one-paragraph: why this repo is in the canary set>
mirrors:
  github: { url, verified_commit, last_verified_at }
  gitlab: { url, verified_commit, last_verified_at }
  bitbucket: { url, verified_commit, last_verified_at }
  azure_devops: { url, verified_commit, last_verified_at }
```

### 3.4 Mirroring procedure (T-CMP-SCM-03-04)

Per `WBS.md §6.2` (`T-CMP-SCM-03-04`): *Mirror the canary repo to all four providers; assert identical commit resolution.*

Automated re-mirror procedure (AC-CORP-CANARY-01b):
1. For each repo, fetch the upstream tree at `pinned_commit`.
2. Push (mirror) to all four `mirrors.*.url` destinations via the corresponding `CMP-SCM-02` / `CMP-SCM-03` connector.
3. For each mirror, call `SCMConnector.resolve_commit(<ref>)` and assert the resolved SHA equals `pinned_commit`.
4. Update `last_verified_at`.

Any non-equal resolution is logged as an `AC-SCM-03c` failure and blocks the corpus from being marked `DONE`.

## 4. Inputs and outputs

### 4.1 Inputs (build-time)

- Upstream public repositories with licenses that permit redistribution (selection rationale recorded in `methodology.md`).
- The four `CMP-SCM-*` connectors (GitHub, GitLab, Bitbucket, Azure DevOps), each DONE per `WBS.md §20`.
- Service-account credentials for the four `scanipy-canary` org accounts (provisioned via `CMP-CP-02` credential encryption).

### 4.2 Outputs (consumed downstream)

- `tests/corpora/canary/corpus.lock` — pinned manifest.
- The set of mirrored remotes — consumed by:
  - **`CMP-CP-05`** (Determinism Attestor) — re-runs `F` across the 100 repos and asserts byte-identical SARIF over `origin=deterministic-core` (`AC-CP-05c`). This is **CI Gate 3** (`WBS.md §15.3`, `.github/workflows/attestor.yml`).
  - **`TST-AC-SCM-03c`** — asserts identical commit resolution across the four providers for any chosen canary repo.
  - **`TST-AC-CORE-01a`** — determinism check: 100 canary repos × 5 re-runs of the IFDS solver yield identical findings.

### 4.3 Repo selection criteria (recorded in `methodology.md`)

- **Language coverage:** Stage-A languages (Java, Python) prioritised at corpus initialisation; later expanded to include Stage B (JS/TS) and beyond as those stages open.
- **Size distribution:** mix of small (< 1k LOC), medium (1k–50k LOC), and large (> 50k LOC) repos to exercise scheduler and Algorithm 1 incremental paths.
- **License:** every repo's license must permit redistribution to all four mirrors OR be excluded with rationale; recorded in `metadata.yaml`.
- **Stability:** repos selected from organisations with a low rate of force-pushes; `pinned_commit` is immutable for the lifetime of the `corpus_version`.

## 5. Invariants touched

| Invariant | Discharge |
|---|---|
| **INV-1 (Determinism partition)** | This corpus is the empirical anchor for the byte-identical-SARIF assertion over `origin=deterministic-core`. `CMP-CP-05` runs the core pipeline over the 100 canary repos × 4 mirrors on every detector / engine / `Env` change. A hard CI fail (`.github/workflows/attestor.yml`) blocks merge on any diff. The corpus does not itself emit findings — it provides the substrate over which INV-1 is empirically tested. |

INV-2, INV-5: the *gate* (`CMP-CP-05`) enforces threading; the corpus carries `corpus_version` / `corpus_digest` so the gate run is reproducible.

## 6. Dependency contract

- **`Depends-On`:** `CMP-SCM-02` (GitHub connector) and `CMP-SCM-03` (GitLab / Bitbucket / Azure DevOps connectors) — both must be DONE per `WBS.md §20`.
- **What this CMP assumes about deps:**
  - `CMP-SCM-02` exposes `clone()`, `resolve_commit()`, and `register_webhook()` against GitHub with the conformance suite from `CMP-SCM-01` green (`AC-SCM-02a`).
  - `CMP-SCM-03` provides three concrete connectors (GitLab, Bitbucket, ADO) each passing the conformance suite (`AC-SCM-03a`).
  - Both connectors honour the shared HTTP retry/backoff from `CMP-SCM-05`.
- **Downstream consumers:** `CMP-CP-05` (Attestor, Gate 3); `TST-AC-SCM-03c` (SCM parity); `TST-AC-CORE-01a` (Algorithm 2 determinism). Provider-side Webhooks not in scope here.

## 7. Failure modes and operational risks

| Mode | Mitigation |
|---|---|
| **Upstream repo disappears or is force-pushed.** A canary repo's upstream origin deletes the pinned commit. | The mirrored copy on each of the four providers preserves `pinned_commit` independently; the corpus is sourced from the mirrors, not the upstream origin. If a mirror also loses the commit, a `corpus_version` bump and a re-mirror from the surviving mirror(s) is the recovery procedure. |
| **SCM provider outage during attestation.** GitLab is down when the Attestor runs. | The Attestor degrades to the available providers but records the missing provider; an outage cannot mask a determinism failure. |
| **Commit-resolution divergence across mirrors.** A repo's four `verified_commit` values diverge. | Hard `T-CMP-SCM-03-04` / `AC-SCM-03c` failure; corpus cannot ship until the offending repo is re-mirrored or removed. The post-mirror parity-check step (§3.4) prevents this state from entering `corpus.lock`. |
| **License violation.** A repo's license is changed post-selection to one that forbids redistribution. | `last_verified_at` triggers a periodic license re-check; offending repos are removed in a `corpus_version` bump. License is recorded with an SPDX identifier on a redistribution-friendly allowlist. |
| **Mirror namespace collision.** Two canary repos accidentally collide on `<repo-id>` across providers. | `repo-id` is the canonical key; mirror URLs MUST use `scanipy-canary/<repo-id>` exactly. CI asserts uniqueness. |
| **Selection skew defeats determinism testing.** All 100 repos turn out to be trivially small or single-language. | `methodology.md` enforces the size and language distribution criteria in §4.3; review at every `corpus_version` bump. |

## 8. Provenance threading

Each Attestor (`CMP-CP-05`) run consuming this corpus must carry:

- `corpus_id = "CORP-CANARY-01"`
- `corpus_version` — verbatim from `corpus.lock`
- `corpus_digest` — verbatim from `corpus.lock`
- `repo_id`, `mirror_provider`, `pinned_commit` — per-run, per-finding context
- `env_digest`, `S_version`, `origin`, `cpg_order_hash` — required by INV-1 / INV-2 on every emitted finding (see `docs/cross-cutting/DOC-PROVENANCE.md`); these are the Attestor's responsibility, not this CMP's, but the corpus must not obstruct their threading.

A `corpus_version` bump invalidates all prior Attestor records over this corpus; the gate must re-run before any release.

## 9. Acceptance criteria cross-reference

Verbatim from `SDD.md §16`:

- **AC-CORP-CANARY-01a:** *100 repos, each mirrored to all four providers with identical commit history.*
- **AC-CORP-CANARY-01b:** *Re-mirroring is automated and reproducible.*

### Test mapping

| AC | Test ID | Kind | Status |
|---|---|---|---|
| AC-CORP-CANARY-01a | `TST-AC-CORP-CANARY-01-a` | [INTEGRATION] — for every repo in `corpus.lock`, `verified_commit` is identical across `github`, `gitlab`, `bitbucket`, `azure_devops` and equals `pinned_commit`; `repo_count == 100` | [FORTHCOMING] |
| AC-CORP-CANARY-01b | `TST-AC-CORP-CANARY-01-b` | [INTEGRATION] — re-mirroring script executes from a clean slate against scratch namespaces on all four providers and reproduces `corpus_digest` byte-for-byte | [FORTHCOMING] |

Gate-side tests that *consume* this corpus (not part of this CMP):

- `TST-AC-CP-05c` — CI runs both Attestor pipelines on the canary corpus on every detector/engine/Env change (`AC-CP-05c`, Gate 3). [INTEGRATION]
- `TST-AC-SCM-03c` — Canary repo mirrored across four SCMs produces identical commit resolution (`AC-SCM-03c`). [INTEGRATION]
- `TST-AC-CORE-01a` — Algorithm 2 produces identical `deterministic-core` findings over 100 canary repos × 5 re-runs. [INTEGRATION]

## 10. Edge cases and unspecified behaviour

- **Repo-count exactly 100.** `SDD.md §16 AC-CORP-CANARY-01a` pins this number; any deviation requires a CLAR. Adding the 101st repo or dropping below 100 must update `corpus_version` and trigger a new gate run.
- **Per-language proportion within the 100.** Not pinned by `SDD.md`. `methodology.md` records the chosen distribution; bump strategy follows Stage A → B → C → D so the corpus stays meaningful as stages open. If a Wave-2 build needs an explicit per-language minimum, file `CLAR-CORP-04` rather than designing it inline (RULE-4).
- **GHE (GitHub Enterprise) coverage.** `CMP-SCM-02` covers GHE via the same connector; the canary corpus uses public GitHub for mirroring. GHE-specific parity is not tested by this CMP (out of scope for `AC-CORP-CANARY-01`).

## 11. Open questions

- No open CLAR-* bears directly on this CMP at time of writing.
- `CLAR-FE-01` and `CLAR-FE-02` (DEFERRED, `WBS.md §17`) do not block this CMP — Stage A languages (Java, Python) already have green CPG-fidelity gates and are sufficient for the Attestor's INV-1 assertion on this corpus.

---

*Cross-references: `SDD.md §16 (CMP-CORP-CANARY-01)`, `SDD.md §3 (CMP-SCM-02, CMP-SCM-03, AC-SCM-03c)`, `SDD.md §10 (CMP-CP-05, AC-CP-05c)`, `WBS.md §6.2 (T-CMP-SCM-03-04)`, `WBS.md §15.3 (Gate 3)`, `WBS.md §20`, `docs/cross-cutting/DOC-INV.md (INV-1)`, `docs/cross-cutting/DOC-PARTITION.md`, `.claude/rules/05-determinism.md`.*
