# Scanipy v3.2 — Work Breakdown Structure (WBS)

**Document status:** Mechanically-derived WBS for Scanipy v3.2.
**Sources of truth:** `PLAN.md` (architecture; wins on disagreement) and `SDD.md` (component specs, IDs, acceptance criteria).
**Intended consumer:** A planning agent that will schedule work, plus a code-writing agent that will execute work packages against the documentation produced in Phase 0 and the test specs produced in Phase 1.
**This document is standalone.** It carries no dependency on, and makes no reference to, any other system or codebase. Every claim below is sourced from `PLAN.md` or `SDD.md`. Where those documents do not pin a detail, the gap is registered in §17 (`CLARIFICATION-NEEDED`) instead of being designed inline.

---

## 0. How to use this document

1. **Phase 0 (Docs) comes first.** Every implementation work package downstream of Phase 0 reads the per-component reference documentation it produced. Code-writing agents are expected to load the matching `DOC-CMP-*` artifact as their primary specification for the work.
2. **Phase 1 (QA / test cases) comes second.** Every `AC-*` in `SDD.md` is converted to one or more concrete test specs (`TST-AC-*`). Code-writing agents are expected to make those tests pass. A work package is not "done" until every test under its `TST-AC-*` set is green.
3. **Phases 2–9 are the implementation phases**, ordered by `PLAN.md` §"Concrete refactor map" (Phase 1–9 in PLAN). Each implementation work package follows the inner cycle **Docs → Tests → Code → Verification** within itself.
4. **Phase 10 (Per-language staging, §13)** is an overlay constraint over Phases 2–9, not a separate workstream. A `(class, language)` pair may not enter the implementation track until its CPG-fidelity gate (`CMP-CP-06`) is green for that language. Where the dependency DAG (from `Depends-On`) suggests an order that violates per-language staging, **staging wins**.
5. **Phase 11 (Multi-tenant control plane) and Phase 12 (Research mode)** map to `PLAN.md` Phase 6 and Phase 8 respectively; their numbering here reflects `PLAN.md`'s grouping order, not their execution order — `CMP-CP-02` / `CMP-CP-03` are wave-1 eligible per §20.2 and must land early.
6. **Phase 13 carries cross-cutting deliverables** — test corpora as work packages (`SDD.md` §12), CI gates (`CMP-CI-01`), and provenance threading verification.
7. **§17 (CLARIFICATION-NEEDED) and §18 (OUT-OF-SCOPE) are open registers**, not phases. Anything that would extend scope beyond `SDD.md` §12 "Out of scope" is filed in §18; anything that requires a decision not pinned by `PLAN.md` or `SDD.md` is filed in §17. **§19 holds the risk-mitigation matrix**; **§20 governs scheduling** via the dependency DAG; **§21 is the Definition of Done**.
8. **Phase numbers reflect `PLAN.md` / `SDD.md` groupings, not strict execution order.** §20 (the dependency DAG, gated by §10 per-language staging) is the authoritative scheduler.
9. **A work package may not start until every package in its `Depends-On` set has every `AC-*` green.** Eligibility-to-start is computed from the dependency DAG (§20), gated by the Phase 10 per-language staging overlay (§13).

---

## 1. Conventions

### 1.1 Identifier scheme

| Prefix | Meaning | Source |
|---|---|---|
| `CMP-*` | Component work package | Carried verbatim from `SDD.md`. **Stable; never renumbered.** |
| `CMP-CORP-*` | Test-corpus work package | Derived from `SDD.md` §12 (corpora named as work packages). |
| `CMP-CI-*` | CI-pipeline work package | Derived from `SDD.md` §12 (CI gates). |
| `CMP-DOC-*` | Documentation work package | Phase 0 outputs. |
| `CMP-DEPLOY-*` | Deployment / runtime substrate work package | Derived from inferred substrate (§2). |
| `T-CMP-*-NN` | Implementation task under a `CMP-*` | Two-digit running number per component. |
| `TST-AC-*` | Test spec corresponding to an `AC-*` from `SDD.md` | One-to-one with `SDD.md` acceptance criteria. |
| `DOC-CMP-*` | Reference doc deliverable under Phase 0 | One per `CMP-*`. |
| `INV-N` | Invariant from `SDD.md` §2 | Verbatim. |
| `R-N` | Risk from `SDD.md` §13 | Verbatim. |
| `CLAR-*` | A `CLARIFICATION-NEEDED` register item | §17. |
| `OOS-*` | An `OUT-OF-SCOPE` register item | §18. |
| `WORKING-ASSUMPTION-*` | A working assumption labelled as such | Used in §2 only, where the substrate is inferred rather than pinned. |

### 1.2 Status codes (for downstream scheduling)

- `BLOCKED` — has unmet `Depends-On`.
- `READY` — all deps green, eligible to start.
- `IN-PROGRESS` — implementation has begun, ACs not all green.
- `DONE` — every `TST-AC-*` under the package is green and every `INV-*` verification task has fired.
- `STAGE-GATED` — implementation could otherwise start but is blocked by a per-language staging gate (§11 / `CMP-CP-06`).

### 1.3 What this WBS is not allowed to do

- **Invent scope.** Where `PLAN.md` / `SDD.md` are silent, a `CLAR-*` item is emitted in §17. The document never paper-cracks a missing decision with a design choice.
- **Renumber `CMP-*` IDs.** `SDD.md` §0 forbids this.
- **Drift into `OUT-OF-SCOPE`.** `SDD.md` §12 enumerates the forbidden derivations (CI-agent / on-prem runner, container-image scanning, binary-only analysis, IDE plugin). Any task that implies one of these is emitted as `OOS-*` in §18 instead.
- **Collapse invariants into a single global task.** Per `SDD.md` §12 ("Provenance threading"), every emitting component carries its own invariant-verification task.

### 1.4 Inner cycle of an implementation work package

For every `CMP-*` work package in Phases 2–10:

```
1. DOCS        — produce / refresh DOC-CMP-<id>  (interfaces, types, error contracts,
                                                  data schemas, persistence keys)
2. TESTS       — produce TST-AC-<id>-<n> for every AC-<id>-<n> in SDD.md
                 (fixtures, inputs, expected outputs, framework, kind tag)
3. CODE        — implement the component to make the tests pass; honour every
                 INV-* the component touches
4. VERIFICATION— run the AC tests + the cross-cutting INV-* verification tasks
                 attached to this component; record provenance threading
```

A package is not `DONE` until step 4 is green for **every** AC.

---

## 2. Deployment architecture map

### 2.1 What the source documents commit to

The following deployment-shape elements are stated or directly implied by `PLAN.md` / `SDD.md`:

| Element | Source |
|---|---|
| Multi-tenant SaaS, customer-facing | `PLAN.md` §"Context and the objective"; `SDD.md` §1 |
| Multi-SCM connectors (GitHub/GHE, GitLab, Bitbucket, Azure DevOps) | `SDD.md` §3 (CMP-SCM-01..03) |
| Container-orchestrated workers, "fanout"-style | `PLAN.md` §"Context and the objective" (legacy ECS Fargate fanout cited) |
| Worker contract: env-var contract, `report_status` callback, argument allowlist, secure `subprocess.run` | `SDD.md` CMP-SNAP-05 |
| Container image as the **authoritative `env_digest`** with `joern`, `codeql`, `git` pinned by digest | `SDD.md` CMP-SNAP-05 (AC-SNAP-05b) |
| Snapshot artifacts persisted at deterministic blob-store keys (CPG tarball, reverse-symbol index, dynamic call graph, ΔG, precondition-status record) | `SDD.md` CMP-SNAP-01 |
| HMAC-bearer pattern on worker callbacks | `SDD.md` CMP-ORCH-01 (AC-ORCH-01b) |
| Credential encryption service for at-rest SCM credentials, with rotation | `SDD.md` CMP-CP-02 |
| OIDC / SAML federation for the customer dashboard | `SDD.md` CMP-CP-04 |
| Relational store with migrations (`orgs`, `projects`, `codebases`, `scm_credentials`, `org_policies`, `memberships`, `snapshots`, `proposed_specs`, `spec_versions`, `attestations`, `findings`) | `SDD.md` CMP-CP-03; CMP-FND-02 |
| Differential reflection oracle running asynchronously, off the critical path | `SDD.md` CMP-SNAP-04 |
| Determinism Attestor as a partitioned CI pipeline (core: byte-identical hard-fail; oracle: digest-stability + measured rate) | `SDD.md` CMP-CP-05 |
| LLM use confined to **triage and gated spec inference**, default-off feature flag, never on the deterministic-core detection path | `SDD.md` §1, INV-3; CMP-TRI-01..03 |

### 2.2 The working assumption

The source documents do not pin a cloud vendor, region strategy, queue technology, RDBMS engine, blob store implementation, OIDC IdP, secrets vendor, or observability stack. The legacy reference to "ECS Fargate" plus the explicit "S3 keys" and "container image digest" framing imply an AWS-flavoured target, but the source documents stop short of mandating it.

> **WORKING-ASSUMPTION-DEPLOY-01.** The runtime substrate is a public cloud whose primitives include: container orchestration with pinned-image workers, an object store with content-addressable keys, a managed relational database, a managed KMS or equivalent envelope-encryption service, a managed work-queue service, and an OIDC/SAML-compatible IdP integration point. The selection of specific managed services is filed in §17 (`CLAR-DEPLOY-*`) and resolved by `CMP-DEPLOY-01` before Phase 4 (Snapshotter) starts; Phase 4 is the first phase that materially exercises every substrate primitive.

### 2.3 ASCII deployment map (inferred)

```
                           ┌───────────────────────────────┐
                           │ SCM providers                 │
                           │ GH / GHE / GL / BB / ADO      │
                           └───┬───────────────────────┬───┘
                       webhooks│                       │clone + REST
                               ▼                       ▼
   ┌─────────────────┐    ┌────────────────────────────────┐
   │ Customer users  │    │ Control Plane API              │
   │ + dashboard     │◀──▶│   /api/v1/scans  (CMP-ORCH-01) │
   │ (CMP-CP-04)     │OIDC│   tenancy + RBAC (CMP-CP-01)   │
   │  - findings UI  │SAML│   worker callback (HMAC)       │
   │  - origin /     │    │   webhook ingest (per-SCM)     │
   │    S_version /  │    └─────┬────────────┬─────────────┘
   │    env_digest   │          │            │
   │    visible      │          │ enqueue    │ enqueue
   └─────────────────┘          ▼            ▼
                            ┌─────────────────────────┐
                            │ Job queues              │
                            │ (per-stage, retries,    │
                            │  per-queue DLQ)         │
                            └────────┬────────────────┘
                                     │
                  ┌──────────────────┼──────────────────────┐
                  ▼                  ▼                      ▼
       ┌─────────────────┐   ┌─────────────────┐   ┌────────────────────┐
       │ Snapshot worker │   │ Detector worker │   │ Triage / spec      │
       │ (CMP-SNAP-05)   │   │ (CMP-ORCH-03)   │   │ inference worker   │
       │  - clone        │   │  - load CPG     │   │ (CMP-TRI-01..03)   │
       │  - CPG build    │   │  - IFDS (core)  │   │  - LLM ranking     │
       │  - CW-DETECT    │   │    OR           │   │  - e-process gate  │
       │  - env_digest   │   │  - oracle adptr │   │  - default OFF     │
       │  - argv allowl. │   │  - stamp origin │   │                    │
       │  - report_status│   │  - emit SARIF   │   │                    │
       └────────┬────────┘   └────────┬────────┘   └─────────┬──────────┘
                │                     │                       │
                └─────────────┬───────┴───────────────────────┘
                              ▼
                ┌─────────────────────────────────────┐
                │ Object store (CMP-DEPLOY-01)        │
                │  - CPG tarballs                     │
                │  - reverse-symbol index             │
                │  - dynamic call graph               │
                │  - ΔG                               │
                │  - precondition-status record       │
                │  - witness_blob_uri (per finding)   │
                │  - SARIF artifacts                  │
                │  - signed provenance record        │
                └─────────────────┬───────────────────┘
                                  │
                                  ▼
                ┌─────────────────────────────────────┐
                │ Relational store (CMP-CP-03)        │
                │  - orgs, projects, codebases        │
                │  - scm_credentials (encrypted)      │
                │  - org_policies, memberships        │
                │  - snapshots (+ precondition-status)│
                │  - findings                          │
                │  - proposed_specs, spec_versions    │
                │  - attestations                     │
                └─────────────────────────────────────┘

       Asynchronous / off-critical-path:
       ┌─────────────────────────────────┐    ┌─────────────────────────────┐
       │ Differential reflection oracle  │    │ Determinism Attestor        │
       │ (CMP-SNAP-04)                   │    │ (CMP-CP-05)                 │
       │  - whole-program scan           │    │  - core: byte-identical SARIF│
       │  - re-partition on disagreement │    │    hard-fail on diff        │
       │  - log to provenance            │    │  - oracle: digest-stability │
       └─────────────────────────────────┘    │    + measured rate          │
                                              └─────────────────────────────┘

       Cross-cutting:
       ┌─────────────────────────────────────────────────────────────────┐
       │ Credential encryption / KMS (CMP-CP-02)                          │
       │   - encrypts scm_credentials at rest; supports rotation          │
       │ Identity (CMP-CP-04)                                             │
       │   - OIDC/SAML; first-admin provisioning on SSO sign-up           │
       │ CI gates (CMP-CI-01)                                             │
       │   - AC-DET-01a, AC-SNAP-03a, AC-CP-05c, AC-TRI-02b               │
       └─────────────────────────────────────────────────────────────────┘
```

### 2.4 Deployment work packages

#### CMP-DEPLOY-01 — Runtime substrate selection `DONE`
**Depends-On:** none · **Staging:** cross-cutting (must complete before Phase 4)
**Purpose:** Resolve every `CLAR-DEPLOY-*` item in §17 and commit one substrate per primitive (compute, queue, blob store, RDBMS, KMS, secrets, IdP, observability stack, region strategy, network model). Output is a written substrate decision record plus the IaC scaffolding needed by every later phase. The decision record is the input to `CMP-DEPLOY-02..04`.
**Acceptance criteria:**
- AC-DEPLOY-01a: Every `CLAR-DEPLOY-*` in §17 has a recorded decision with a one-paragraph rationale referenced back to `PLAN.md` / `SDD.md` constraints.
- AC-DEPLOY-01b: The chosen object-store primitive supports content-addressable, deterministic keys for the artifacts named in `SDD.md` CMP-SNAP-01 (`AC-SNAP-01a`).
- AC-DEPLOY-01c: The chosen queue primitive supports per-queue dead-letter routing and at-least-once delivery, with idempotent worker contracts.
- AC-DEPLOY-01d: The chosen relational primitive supports forward + rollback migrations on a fresh database (cf. `AC-CP-03a`).
- AC-DEPLOY-01e: The chosen KMS-equivalent supports envelope encryption and key rotation (cf. `AC-CP-02a`).

#### CMP-DEPLOY-02 — Worker container baseline `IN-PROGRESS`
**Depends-On:** CMP-DEPLOY-01 · **Staging:** Stage A
**Purpose:** Produce the base container image that bundles `joern`, `codeql`, `git` and pins each by digest; bake the environment-variable contract, the argument allowlist machinery, and the `report_status` callback affordances into the image. The image digest **is** `env_digest` (per `AC-SNAP-05b`); changing any bundled tool changes the digest.
**Acceptance criteria:**
- AC-DEPLOY-02a: `joern`, `codeql`, `git` are present at pinned digests inside the image.
- AC-DEPLOY-02b: Mutating any bundled tool changes the image digest, and that digest is the authoritative `env_digest` exposed to the snapshot worker.
- AC-DEPLOY-02c: The image-build process refuses to publish if any pinned digest is unspecified.

#### CMP-DEPLOY-03 — Observability surfaces `IN-PROGRESS`
**Depends-On:** CMP-DEPLOY-01 · **Staging:** cross-cutting
**Purpose:** Structured logs, metrics, and traces for every worker and API surface. Carries the per-scan correlation fields needed for cross-component triage (scan id, snapshot id, org id, codebase id, detector id, `S_version`, `env_digest`, `fingerprint_class`, `origin`).
**Acceptance criteria:**
- AC-DEPLOY-03a: A single scan id resolves to a chronological cross-component trace covering at least: webhook ingest, snapshot worker, every detector worker, normalizer, attestor verdict, callback delivery.
- AC-DEPLOY-03b: Every emitted log line carries a service name, build commit, and `env_digest`.
- AC-DEPLOY-03c: Alarms exist for: snapshot-worker failure rate, detector-worker failure rate, callback HMAC rejection rate, Attestor core-partition diff (any non-zero rate is a hard incident), `CW-DETECT` differential-oracle disagreement rate, e-process martingale-unit-test failure.

#### CMP-DEPLOY-04 — CI/CD pipeline (build, test, deploy)
**Depends-On:** CMP-DEPLOY-01, CMP-DEPLOY-02 · **Staging:** cross-cutting
**Purpose:** Pipelines for building worker images, running every CI gate enumerated under `CMP-CI-01`, deploying behind controlled gates, and registering signed image digests as the active `env_digest` for the next snapshot run. Pinned-image discipline is enforced here so it cannot be bypassed at deploy time.
**Acceptance criteria:**
- AC-DEPLOY-04a: A merge to the main branch cannot deploy a worker image whose tool digests differ from those committed in the substrate decision record without an explicit `env_digest` rollover ceremony.
- AC-DEPLOY-04b: The CI gates in `CMP-CI-01` are enforced as hard pipeline failures, not advisory checks.
- AC-DEPLOY-04c: Image provenance (build commit, build inputs, tool digests) is signed and published with the artifact.

#### CMP-DEPLOY-05 — Tenant data isolation
**Depends-On:** CMP-DEPLOY-01, CMP-CP-01, CMP-CP-03 · **Staging:** cross-cutting
**Purpose:** Enforce that no worker, query path, or object-store access can cross an org boundary. Backstop for `AC-CP-01a` at the runtime layer rather than only in application code.
**Acceptance criteria:**
- AC-DEPLOY-05a: A parameterised negative test that drives a cross-org access attempt at every API surface and every worker callback fails with a 4xx and emits an audit log line.
- AC-DEPLOY-05b: Blob-store paths are namespaced by org id; a path traversal in a request parameter cannot resolve to another org's artifact.

---

## 3. Phase 0 — Documentation

**Purpose.** Phase 0 produces the per-component reference documentation that a code-writing agent will consume as the primary specification of the work. This phase comes **before** any production code is written so that downstream agents are not reading the `SDD.md` directly and re-deriving the same interpretation each time. The Phase 0 outputs are normative; the SDD remains the source of truth that they faithfully transcribe.

**Output format for every `DOC-CMP-*` artifact.** Each one mirrors the same sections so that an agent can index into them mechanically:

1. **Component identity** — `CMP-ID`, subsystem, staging, owning subsystem maintainer (named in `CLAR-OWNER-*` until assigned).
2. **Mandate** — verbatim copy of the SDD `Purpose:` field, plus an expanded paragraph describing the operational role.
3. **Interface contract** — fully typed signatures for every public method / handler / message, including error types. For data interfaces, the schema (column types, nullability, indices, constraints, foreign keys) is written out explicitly.
4. **Inputs and outputs** — for every interface method, name every required input, every produced output, every side effect, and every persisted artifact (with the storage key shape where applicable).
5. **Invariants touched** — enumerate which of `INV-1..INV-6` this component touches and exactly how it discharges each one (e.g., "stamps `origin` on every emitted finding", "rejects a non-DSL spec at registration"). Each entry cross-references a `TST-INV-*` test.
6. **Dependency contract** — what this component assumes about each of its `Depends-On` entries (e.g., "assumes CMP-SNAP-01 has persisted the precondition-status record at the documented S3 key shape").
7. **Failure modes and error contracts** — every error type, every retry policy, every fallback path (closed-world → degraded → full-reparse, etc.). For undecidable-property approximators (`CW-DETECT`, the combinator DSL closure check), the safe direction is written here per `INV-4`.
8. **Provenance threading** — every field this component writes to a provenance record or finding row, named explicitly (`S_version`, `env_digest`, `origin`, `cpg_order_hash` with its conditional-canonicality annotation where applicable).
9. **Acceptance criteria cross-reference** — table of every `AC-*` from `SDD.md` for this component, paired with its `TST-AC-*` test spec in Phase 1.
10. **Open questions** — every `CLAR-*` item that bears on this component.

The Phase 0 outputs are the work-package inputs for Phases 2–10. A code-writing agent that has not loaded the relevant `DOC-CMP-*` is operating outside contract.

### 3.1 Per-component documentation work packages

A `DOC-CMP-<id>` exists for every `CMP-*` work package in §4 through §13, including the deployment packages and the test-corpus packages. Tabular index:

| Doc package | Documents component |
|---|---|
| DOC-CMP-DEPLOY-01..05 | §2.4 deployment work packages |
| DOC-CMP-SCM-01 | SCMConnector abstract base |
| DOC-CMP-SCM-02 | GitHub connector |
| DOC-CMP-SCM-03 | GitLab / Bitbucket / Azure DevOps connectors |
| DOC-CMP-SCM-05 | Shared HTTP retry/backoff |
| DOC-CMP-DET-01 | Combinator DSL for taint specs |
| DOC-CMP-DET-02 | Detector registry + closure check |
| DOC-CMP-DET-03 | Class plugin scaffolding + content migration |
| DOC-CMP-SNAP-01 | Snapshot service API |
| DOC-CMP-SNAP-02 | Incremental CPG maintenance (Algorithm 1) |
| DOC-CMP-SNAP-03 | CW-DETECT closed-world precondition detector |
| DOC-CMP-SNAP-04 | Differential reflection oracle |
| DOC-CMP-SNAP-05 | Snapshot worker + environment pinning |
| DOC-CMP-CORE-01 | IFDS/IDE tabulation solver (Algorithm 2) |
| DOC-CMP-CORE-02 | Slice fingerprint (Algorithm 3) |
| DOC-CMP-CORE-03 | Canonical CPG ordering (Algorithm 5) |
| DOC-CMP-FND-01 | Findings normalizer |
| DOC-CMP-FND-02 | Findings store schema |
| DOC-CMP-FND-03 | Signed provenance record |
| DOC-CMP-ORCH-01 | Scan API |
| DOC-CMP-ORCH-02 | Heuristic scheduler SNAP-SCHED-H |
| DOC-CMP-ORCH-03 | Detector-agnostic worker |
| DOC-CMP-TRI-01 | LLM triage ranking |
| DOC-CMP-TRI-02 | Anytime-valid e-process spec gate |
| DOC-CMP-TRI-03 | Per-customer revalidation + drift monitor |
| DOC-CMP-CP-01 | Multi-tenant scan API guard |
| DOC-CMP-CP-02 | Credential encryption service |
| DOC-CMP-CP-03 | Tenancy schema + migrations |
| DOC-CMP-CP-04 | Authentication (OIDC/SAML) + dashboard |
| DOC-CMP-CP-05 | Determinism Attestor (partitioned) |
| DOC-CMP-CP-06 | CPG-fidelity gate harness |
| DOC-CMP-CORP-* | Each test-corpus work package (§16) |
| DOC-CMP-CI-01 | CI pipeline enforcing the four named gates |

### 3.2 Cross-cutting reference documents

In addition to the per-component artifacts, Phase 0 produces these cross-cutting reference documents. They are read by every code-writing agent regardless of which `CMP-*` is being implemented:

- **DOC-INV — Invariants catalog.** Restatement of `INV-1..INV-6` with examples and counter-examples, plus the master cross-reference of which components carry which invariant verification tasks.
- **DOC-GLOSSARY — Vocabulary.** `S_version`, `env_digest`, `origin`, `determinism_partition`, `cpg_order_hash`, `fingerprint_class` (`strong` / `weak`), `slice_fingerprint`, `precondition-status` (`closed-world | degraded | full-reparse`), `spec_provenance` (`global-unrevalidated | …`), `engine` (`ifds | ide | semgrep | cpg-query | external`).
- **DOC-API — External API contract.** OpenAPI-equivalent reference of every public API surface enumerated in `SDD.md` (`POST /api/v1/scans`, `GET /api/v1/scans/{id}`, `GET …/findings`, `POST /api/v1/jobs/{job_id}/status`, `POST /snapshots`), including the HMAC-bearer worker callback contract.
- **DOC-DB — Persistence schema reference.** Every table from `SDD.md` CMP-CP-03 and CMP-FND-02, with column types, nullability, indices, constraints, foreign keys, and the migration order in which they must apply.
- **DOC-SARIF — SARIF emission contract.** Every required field on emitted SARIF results, including the conditional-canonicality annotation on `cpg_order_hash`, the per-finding `origin`, `S_version`, `env_digest`, `slice_fingerprint`, `fingerprint_class`, `witness_blob_uri`.
- **DOC-DSL — Combinator-DSL grammar reference.** Grammar for `source`, `sink`, `sanitize`, `propagate`, and sanctioned compositions; explicit non-grammar (escape hatches that must be rejected at registration per `AC-DET-01b`); the proof-obligation template for adding a combinator (`f(X ∪ Y) = f(X) ∪ f(Y)` exhaustively over the bounded domain).
- **DOC-PROVENANCE — Provenance record reference.** Full schema of the signed chain `source commit → snapshot digest → S_version → env_digest → cpg_order_hash (canonical iff strong) → taint witness → rule/spec id → SARIF hash → per-finding origin`, including the differential-oracle re-partition log records.
- **DOC-ALGS — Algorithm reference suite.** One reference per algorithm: Algorithm 1 (incremental CPG maintenance), Algorithm 2 (IFDS/IDE tabulation), Algorithm 3 (slice fingerprint), Algorithm 4 (heuristic scheduler `SNAP-SCHED-H`), Algorithm 5 (canonical CPG ordering, with explicit canonicality annotation), Algorithm 6 (anytime-valid e-process spec gate).
- **DOC-PARTITION — Determinism partition reference.** How `origin` is determined per detector engine (`ifds`, `ide` → `deterministic-core`; `semgrep`, `cpg-query`, `external` → `oracle-passthrough`), and the rules for `mixed` detectors that emit per-finding `origin`.
- **DOC-STAGING — Per-language staging reference.** Verbatim restatement of `SDD.md` §11, with the gate criteria for `CMP-CP-06` enumerated explicitly per language (`parse success ≥ 99.5%`, call-edge precision/recall thresholds, PDG dependence-edge recall threshold), and the list of `(class, language)` pairs in each stage.
- **DOC-RUNBOOK — Operations runbook.** Worker lifecycle, scan lifecycle (queued → snapshotting → analysing → normalising → attested → callback-delivered), failure recovery, manual re-attestation, key rotation, the differential-oracle disagreement-incident procedure (raise determinism incident → retroactively re-partition → notify affected customer → log to provenance).

### 3.3 Phase 0 acceptance criteria

- AC-DOC-01: Every `CMP-*` in this WBS has a corresponding `DOC-CMP-*` artifact that follows the §3 §3.1 format.
- AC-DOC-02: Every cross-cutting reference in §3.2 exists and is internally consistent with the per-component artifacts.
- AC-DOC-03: Every `INV-1..INV-6` is named in `DOC-INV` with at least one component owner per invariant.
- AC-DOC-04: A code-writing agent given only `DOC-CMP-<id>` for any single `CMP-*` (plus the cross-cutting refs in §3.2) can produce a passing implementation for that component without re-reading the SDD.

---

## 4. Phase 1 — QA / test cases

**Purpose.** Phase 1 converts every `AC-*` in `SDD.md` into one or more concrete, executable test specifications. The test specs are the "done" contract for every implementation work package downstream. A code-writing agent in Phases 2–10 makes these tests pass.

### 4.1 Test-spec format

Every `TST-AC-*` artifact carries:

- **Test id** — `TST-AC-<CMP-tail>-<ac-letter>[-N]` (where `N` disambiguates if the SDD AC expands to multiple tests).
- **Maps to AC** — verbatim cross-reference of the `SDD.md` AC.
- **Kind tag** — one of:
  - `[CONDITIONAL THEOREM]` — covers a precondition-conditional theorem claim.
  - `[EMPIRICAL]` — measures and asserts against a published threshold.
  - `[FALSIFIER]` — adversarial corpus or mutation-injected test that closes an undecidable-precondition risk.
  - `[INVARIANT]` — verifies one of `INV-1..INV-6` is held by the component under test.
  - `[NEGATIVE]` — drives a rejected input and asserts the rejection diagnostic.
  - `[REGRESSION]` — locks behaviour against a named legacy finding.
  - `[UNIT]` — pure-function unit test.
  - `[INTEGRATION]` — multi-component end-to-end exercise.
  - `[CONFORMANCE]` — a connector-level conformance suite (CMP-SCM-01).
- **Inputs** — required fixtures (corpus path, repo commit, seed values, env-digest pin).
- **Outputs** — expected results expressed in normalised form (SARIF blob hash, e-process realised rate, parse success percentage, etc.).
- **Pass criteria** — concrete and unambiguous; no judgement calls.
- **Frequency** — `every CI run`, `nightly`, `pre-release`, `pre-customer-enablement`.
- **Hard gate?** — yes/no; if yes, identifies which CI gate (CMP-CI-01) it backs.

### 4.2 Comprehensive `TST-AC-*` index (one row per SDD AC)

| Test id | Maps to | Kind | Hard gate? |
|---|---|---|---|
| TST-AC-SCM-01a | AC-SCM-01a — ABC defines all six methods with typed signatures and documented contracts | [UNIT] | yes |
| TST-AC-SCM-01b | AC-SCM-01b — SCMCredentials round-trips all four auth modes through encryption at rest | [UNIT] | yes |
| TST-AC-SCM-01c | AC-SCM-01c — Conformance test suite for concrete connectors | [CONFORMANCE] | yes |
| TST-AC-SCM-02a | AC-SCM-02a — GitHub connector passes the conformance suite | [CONFORMANCE] | yes |
| TST-AC-SCM-02b | AC-SCM-02b — Existing retry, rate-limit, and tiered-star behaviour byte-for-byte preserved | [REGRESSION] | yes |
| TST-AC-SCM-02c | AC-SCM-02c — `integrations/github/__init__.py` exports `search_repositories` as a caller-transparent shim | [REGRESSION] | yes |
| TST-AC-SCM-03a | AC-SCM-03a — GL/BB/ADO each pass the conformance suite | [CONFORMANCE] | yes |
| TST-AC-SCM-03b | AC-SCM-03b — Webhook signature verification rejects forged payloads per provider | [NEGATIVE] | yes |
| TST-AC-SCM-03c | AC-SCM-03c — Canary repo mirrored across four SCMs produces identical commit resolution | [INTEGRATION] | yes |
| TST-AC-SCM-05a | AC-SCM-05a — Exponential backoff with jitter; provider-specific rate-limit honouring | [UNIT] | yes |
| TST-AC-SNAP-01a | AC-SNAP-01a — Snapshot request produces all five persisted artifacts at deterministic keys | [INTEGRATION] | yes |
| TST-AC-SNAP-01b | AC-SNAP-01b — Precondition-status record records exactly one of three values | [UNIT] | yes |
| TST-AC-SNAP-01c | AC-SNAP-01c — env_digest computed from pinned container image digest and recorded on snapshot | [UNIT] | yes |
| TST-AC-SNAP-02a | AC-SNAP-02a — Closed-world κ-bound regression on ≥1,000 commits | [CONDITIONAL THEOREM] | yes |
| TST-AC-SNAP-02b | AC-SNAP-02b — Open-world median ≥ 5×, p95 ≥ 2×, fallback ≤ 15% | [EMPIRICAL] | yes |
| TST-AC-SNAP-02c | AC-SNAP-02c — Function-granularity reparse preserves node IDs for unchanged declarations | [UNIT] | yes |
| TST-AC-SNAP-03a | AC-SNAP-03a — Falsifier CW: zero false negatives on the curated reflection corpus | [FALSIFIER] | yes (release blocker) |
| TST-AC-SNAP-03b | AC-SNAP-03b — Combined TP+FP routing rate measured and reported | [EMPIRICAL] | no |
| TST-AC-SNAP-04a | AC-SNAP-04a — Seeded CW-DETECT FN is detected by the oracle; triggers exact re-partitioning | [FALSIFIER] | yes |
| TST-AC-SNAP-04b | AC-SNAP-04b — Labeling-correction window measured; contractual SLA published | [EMPIRICAL] | yes |
| TST-AC-SNAP-04c | AC-SNAP-04c — Every re-partition event written to provenance | [INVARIANT] | yes |
| TST-AC-SNAP-05a | AC-SNAP-05a — Argument allowlist rejects any non-sanctioned flag | [NEGATIVE] | yes |
| TST-AC-SNAP-05b | AC-SNAP-05b — Container image digest is authoritative env_digest; tool change changes digest | [UNIT] | yes |
| TST-AC-DET-01a | AC-DET-01a — Each combinator carries a machine-checked distributivity proof obligation | [UNIT] | yes (CI gate) |
| TST-AC-DET-01b | AC-DET-01b — DSL grammar rejects specs embedding arbitrary code | [NEGATIVE] | yes |
| TST-AC-DET-02a | AC-DET-02a — Registration rejects out-of-DSL specs with precise diagnostic | [NEGATIVE] | yes |
| TST-AC-DET-02b | AC-DET-02b — Manifest records all required fields plus derived determinism_partition | [UNIT] | yes |
| TST-AC-DET-02c | AC-DET-02c — engine→determinism_partition mapping is correct for every engine value | [UNIT] | yes |
| TST-AC-DET-03a | AC-DET-03a — All ten class directories register without error (stubs permitted) | [UNIT] | yes |
| TST-AC-DET-03b | AC-DET-03b — Migrated path-traversal spec produces historical CVE-2025-61765 finding | [REGRESSION] | yes |
| TST-AC-CORE-01a | AC-CORE-01a — 100 canary repos × 5 re-runs produce identical pre-serialisation hashes | [CONDITIONAL THEOREM] | yes (release blocker) |
| TST-AC-CORE-01b | AC-CORE-01b — On CPG-fidelity-gate-passing pairs: recall ≥ Semgrep-default + 10pp at equal precision | [EMPIRICAL] | yes (per stage) |
| TST-AC-CORE-01c | AC-CORE-01c — Incremental retabulation visits only AFFECTED entry points and their callers | [UNIT] | yes |
| TST-AC-CORE-02a | AC-CORE-02a — Fingerprint invariant under each named refactor on 50 seeded findings | [FALSIFIER] | yes |
| TST-AC-CORE-02b | AC-CORE-02b — Fingerprint changes on genuine fix and on aliasing-changing extract | [FALSIFIER] | yes |
| TST-AC-CORE-02c | AC-CORE-02c — weak-fallback rate measured and <5%; weak never auto-suppressed | [EMPIRICAL] + [INVARIANT] | yes |
| TST-AC-CORE-03a | AC-CORE-03a — CFI-style symmetric inputs terminate within (B,T) with deterministic order | [UNIT] | yes |
| TST-AC-CORE-03b | AC-CORE-03b — Budget-exhaustion rate on real code <1% | [EMPIRICAL] | yes |
| TST-AC-CORE-03c | AC-CORE-03c — Persisted hash field named cpg_order_hash; conditional annotation everywhere | [INVARIANT] | yes |
| TST-AC-ORCH-01a | AC-ORCH-01a — A scan creates a snapshot if absent, then fans one job per detector | [INTEGRATION] | yes |
| TST-AC-ORCH-01b | AC-ORCH-01b — Worker callback rejects invalid-HMAC payload | [NEGATIVE] | yes |
| TST-AC-ORCH-01c | AC-ORCH-01c — Backwards-compat: scanipy --query extractall --run-semgrep yields CVE-2025-61765 with origin=deterministic-core on Stage-A language | [REGRESSION] | yes |
| TST-AC-ORCH-02a | AC-ORCH-02a — Production-shaped replay p95 end-to-end scan latency <30 min | [EMPIRICAL] | yes |
| TST-AC-ORCH-02b | AC-ORCH-02b — Different schedules produce identical deterministic-core findings | [INVARIANT] | yes |
| TST-AC-ORCH-02c | AC-ORCH-02c — ρ≈2 appears in documentation only as relaxation bound, never as guarantee | [UNIT] (doc-link grep test) | yes |
| TST-AC-ORCH-03a | AC-ORCH-03a — Every emitted finding has a correct origin | [INVARIANT] | yes |
| TST-AC-ORCH-03b | AC-ORCH-03b — Mixed-class detector emits per-finding origin without blurring | [INVARIANT] | yes |
| TST-AC-FND-01a | AC-FND-01a — All detector outputs validate against SARIF 2.1.0 | [UNIT] | yes |
| TST-AC-FND-01b | AC-FND-01b — Result ordering is canonical CPG order from CORE-03 | [UNIT] | yes |
| TST-AC-FND-02a | AC-FND-02a — Cross-scan baseline lookup correct; never auto-suppresses weak or oracle-passthrough across refactor | [INVARIANT] | yes |
| TST-AC-FND-02b | AC-FND-02b — Every row carries non-null origin, S_version, env_digest | [INVARIANT] | yes |
| TST-AC-FND-03a | AC-FND-03a — Record independently verifiable from stored artifacts without re-running analysis | [INTEGRATION] | yes |
| TST-AC-FND-03b | AC-FND-03b — cpg_order_hash carries conditional-canonicality annotation in auditor export | [INVARIANT] | yes |
| TST-AC-FND-03c | AC-FND-03c — Differential-oracle re-partition events appear in the record | [INVARIANT] | yes |
| TST-AC-TRI-01a | AC-TRI-01a — Triage flag off: no row's origin or detection content affected | [INVARIANT] | yes |
| TST-AC-TRI-01b | AC-TRI-01b — Ranking writes only triage_* columns | [INVARIANT] | yes |
| TST-AC-TRI-02a | AC-TRI-02a — Adversarial unbounded continuation: realised ever-false-acceptance rate ≤ α | [FALSIFIER] | yes (pre-customer-enablement) |
| TST-AC-TRI-02b | AC-TRI-02b — e-process martingale-property unit test passes | [UNIT] | yes (pre-customer-enablement) |
| TST-AC-TRI-02c | AC-TRI-02c — Accepted spec written version-pinned; core only ever consumes pinned specs | [INVARIANT] | yes |
| TST-AC-TRI-03a | AC-TRI-03a — Global-accepted spec on adversarial customer distribution is quarantined | [FALSIFIER] | yes |
| TST-AC-TRI-03b | AC-TRI-03b — Findings dependent on an unrevalidated global spec carry global-unrevalidated | [INVARIANT] | yes |
| TST-AC-CP-01a | AC-CP-01a — Cross-org access attempt is denied | [NEGATIVE] | yes |
| TST-AC-CP-02a | AC-CP-02a — Credentials unreadable at rest without managed key; rotation supported | [INTEGRATION] | yes |
| TST-AC-CP-03a | AC-CP-03a — Migrations apply forward and roll back cleanly on a fresh DB | [INTEGRATION] | yes |
| TST-AC-CP-04a | AC-CP-04a — SSO sign-up provisions org row plus first-admin membership | [INTEGRATION] | yes |
| TST-AC-CP-04b | AC-CP-04b — Findings view never visually blurs deterministic-core and oracle-passthrough | [UNIT] (snapshot test) | yes |
| TST-AC-CP-05a | AC-CP-05a — Deliberately introduced core-path nondeterminism fails the core pipeline | [FALSIFIER] | yes (release blocker) |
| TST-AC-CP-05b | AC-CP-05b — Oracle pipeline reports numeric reproduction rate; never asserts theorem | [INVARIANT] | yes |
| TST-AC-CP-05c | AC-CP-05c — CI runs both pipelines on canary corpus on every detector/engine/Env change | [INTEGRATION] | yes (CI gate) |
| TST-AC-CP-06a | AC-CP-06a — Failing language reported front-end-blocked, not recall failure | [INVARIANT] | yes |
| TST-AC-CP-06b | AC-CP-06b — Gate results recorded per language and consulted by staging logic | [UNIT] | yes |
| TST-AC-DEPLOY-01a..e | AC-DEPLOY-01a..e — substrate decision record discharges every CLAR-DEPLOY-* | [INTEGRATION] | yes |
| TST-AC-DEPLOY-02a..c | AC-DEPLOY-02a..c — Worker base image bundles pinned tools as authoritative env_digest | [UNIT] | yes |
| TST-AC-DEPLOY-03a..c | AC-DEPLOY-03a..c — End-to-end correlation trace; alarms exist for the named events | [INTEGRATION] | yes |
| TST-AC-DEPLOY-04a..c | AC-DEPLOY-04a..c — Main-branch deploy enforces pinned digests; CI gates are hard fails | [INTEGRATION] | yes (CI gate) |
| TST-AC-DEPLOY-05a..b | AC-DEPLOY-05a..b — Cross-org access denied at every surface; namespaced blob paths | [NEGATIVE] | yes |

### 4.3 Invariant-verification test specs (one per emitting component)

`SDD.md` §12 mandates a per-component invariant-verification task rather than a single global task. These supplement (do not replace) the AC tests above.

| Invariant | Component(s) carrying explicit verification |
|---|---|
| INV-1 (origin partition) | CMP-ORCH-03 (TST-INV-1-ORCH-03), CMP-FND-01 (TST-INV-1-FND-01), CMP-FND-02 (TST-INV-1-FND-02), CMP-FND-03 (TST-INV-1-FND-03), CMP-SNAP-04 (TST-INV-1-SNAP-04 for re-partitioning correctness), CMP-TRI-01 (TST-INV-1-TRI-01 — no triage-induced origin flips) |
| INV-2 (versioned parameters) | CMP-SNAP-01 (TST-INV-2-SNAP-01), CMP-ORCH-03 (TST-INV-2-ORCH-03), CMP-FND-01..03, CMP-TRI-02 (TST-INV-2-TRI-02 — accepted specs are version-pinned) |
| INV-3 (LLM off detection path) | CMP-TRI-01 (TST-INV-3-TRI-01), CMP-TRI-02 (TST-INV-3-TRI-02), CMP-CP-05 (TST-INV-3-CP-05 — Attestor runs with LLM_TRIAGE=off) |
| INV-4 (one-sided approximations) | CMP-SNAP-03 (TST-INV-4-SNAP-03 — falsifier CW), CMP-DET-01 (TST-INV-4-DET-01 — DSL closure check) |
| INV-5 (conditional labels self-describing) | CMP-CORE-03 (TST-INV-5-CORE-03 — cpg_order_hash annotation), CMP-FND-03 (TST-INV-5-FND-03 — annotation present in auditor export), CMP-CORE-02 (TST-INV-5-CORE-02 — weak-classed findings never auto-suppressed) |
| INV-6 (per-language honesty) | CMP-CP-06 (TST-INV-6-CP-06), CMP-CORE-01 (TST-INV-6-CORE-01 — recall claim only on gate-passing pairs) |

### 4.4 Phase 1 acceptance criteria

- AC-QA-01: Every `AC-*` in `SDD.md` has at least one `TST-AC-*` artifact in the WBS-managed test inventory.
- AC-QA-02: Every `INV-1..INV-6` has at least one explicit `TST-INV-*` per emitting component.
- AC-QA-03: Every test spec carries a kind tag from §4.1.
- AC-QA-04: Hard-gate test specs are wired to the CI pipeline (`CMP-CI-01`) such that failure of any one fails the pipeline.
- AC-QA-05: A code-writing agent given only the `TST-AC-*` set for a `CMP-*` plus `DOC-CMP-<id>` can decide unambiguously whether its implementation is `DONE` for that component.

---

## 5. Phase 2 — Generalise SCM (PLAN Phase 1)

**Goal.** Replace the GitHub-only ingest path with a provider-neutral abstraction whose four concrete connectors all satisfy the same conformance suite. Preserve the existing GitHub retry/backoff and tiered-star behaviour verbatim. Research-mode `search_code()` is GitHub-only.

### CMP-SCM-01 — SCMConnector abstract base
**Depends-On:** none (CMP-CP-02 mockable until available) · **Staging:** cross-cutting
**Tasks:**
- T-CMP-SCM-01-01: Author the ABC for `list_repos`, `clone`, `register_webhook`, `verify_webhook`, `get_default_branch`, `resolve_commit`.
- T-CMP-SCM-01-02: Define `SCMCredentials` covering PAT, app installation, OAuth, SSH key with a single round-trip-encryptable representation.
- T-CMP-SCM-01-03: Build the conformance suite that any concrete connector must satisfy.
- T-CMP-SCM-01-04: Wire `SCMCredentials` through a mock encryption-at-rest layer until `CMP-CP-02` is available.
**Tests:** TST-AC-SCM-01a, TST-AC-SCM-01b, TST-AC-SCM-01c.
**Invariants threaded:** none direct.

### CMP-SCM-05 — Shared HTTP retry/backoff
**Depends-On:** none · **Staging:** cross-cutting
**Tasks:**
- T-CMP-SCM-05-01: Lift the existing GitHub retry/backoff/rate-limit pattern into a provider-agnostic module.
- T-CMP-SCM-05-02: Wire each per-provider rate-limit response shape (429, secondary limits) into the shared module with provider-specific honoring policies.
**Tests:** TST-AC-SCM-05a.

### CMP-SCM-02 — GitHub connector
**Depends-On:** CMP-SCM-01 · **Staging:** cross-cutting
**Tasks:**
- T-CMP-SCM-02-01: Subsume the existing `integrations/github/github.py` behind the ABC; preserve retry/backoff and tiered-star helpers byte-for-byte.
- T-CMP-SCM-02-02: Expose `search_code()` for Research mode only; reject Research-mode helpers on non-GitHub connectors at the type system.
- T-CMP-SCM-02-03: Keep `integrations/github/__init__.py` exporting `search_repositories` as a caller-transparent shim.
**Tests:** TST-AC-SCM-02a, TST-AC-SCM-02b, TST-AC-SCM-02c.

### CMP-SCM-03 — GitLab / Bitbucket / Azure DevOps connectors
**Depends-On:** CMP-SCM-01, CMP-SCM-05 · **Staging:** cross-cutting
**Tasks:**
- T-CMP-SCM-03-01: Implement the GitLab connector against the REST API and webhook signature scheme.
- T-CMP-SCM-03-02: Implement the Bitbucket connector against the REST API and webhook signature scheme.
- T-CMP-SCM-03-03: Implement the Azure DevOps connector against the REST API and webhook signature scheme.
- T-CMP-SCM-03-04: Mirror the canary repo to all four providers; assert identical commit resolution.
**Tests:** TST-AC-SCM-03a, TST-AC-SCM-03b, TST-AC-SCM-03c.
**Invariants threaded:** none direct.

---

## 6. Phase 3 — Detector catalog + combinator DSL + closure check (PLAN Phase 2)

**Goal.** Replace bespoke detector code with a declarative combinator DSL whose closure check discharges the IFDS distributivity hypothesis. Stand up the registry, the manifest, and the ten class directories. Migrate the legacy path-traversal spec and the CodeQL queries to their detector homes.

### CMP-DET-01 — Combinator DSL for taint specs
**Depends-On:** none · **Staging:** cross-cutting
**Tasks:**
- T-CMP-DET-01-01: Implement the primitive set `source(access-path-pattern)`, `sink(...)`, `sanitize(...)`, `propagate(arg→ret | field)` and the sanctioned composition operators.
- T-CMP-DET-01-02: For every primitive and every sanctioned composition, encode the machine-checked distributivity proof obligation (`f(X ∪ Y) = f(X) ∪ f(Y)`, exhaustively over the bounded finite domain).
- T-CMP-DET-01-03: Reject any spec embedding non-DSL code at parse time with a precise diagnostic.
**Tests:** TST-AC-DET-01a, TST-AC-DET-01b, TST-INV-4-DET-01.
**Invariants threaded:** INV-4 (owner of Algorithm 2's distributivity precondition).

### CMP-DET-02 — Detector registry + closure check
**Depends-On:** CMP-DET-01 · **Staging:** cross-cutting
**Tasks:**
- T-CMP-DET-02-01: Discover `detectors/<class>/` directories and load `manifest.yaml`.
- T-CMP-DET-02-02: Run the grammar/closure check on every loaded spec; reject out-of-DSL with a precise diagnostic.
- T-CMP-DET-02-03: Derive `determinism_partition` from `engine` (`ifds | ide` → `deterministic-core`; `semgrep | cpg-query | external` → `oracle-passthrough`).
- T-CMP-DET-02-04: Persist manifest records (`id`, `cwes`, `languages`, `frameworks`, `engine`, `severity_default`, `determinism_partition`, per-language readiness).
**Tests:** TST-AC-DET-02a, TST-AC-DET-02b, TST-AC-DET-02c.

### CMP-DET-03 — Class plugin scaffolding + content migration
**Depends-On:** CMP-DET-02 · **Staging:** per class (see §13)
**Tasks:**
- T-CMP-DET-03-01: Scaffold the ten class directories `detectors/{injection,path-traversal,ssrf,deserialization,xss,crypto-misuse,authn-authz,memory-safety,secrets,dep-cve}/` with `specs/` skeletons.
- T-CMP-DET-03-02: Migrate `tarslip.yaml` → `detectors/path-traversal/specs/`.
- T-CMP-DET-03-03: Migrate the existing CodeQL queries → `detectors/memory-safety/codeql/` tagged `oracle`.
- T-CMP-DET-03-04: Verify that the migrated path-traversal spec reproduces the CVE-2025-61765 finding on the appropriate Stage-A language.
**Tests:** TST-AC-DET-03a, TST-AC-DET-03b.

---

## 7. Phase 4 — Snapshotter + CW-DETECT + differential oracle (PLAN Phase 3)

**Goal.** Stand up the snapshot service, the incremental CPG maintenance pipeline, and the two precondition-soundness mechanisms that make Theorems (a) and 1 reliable: `CW-DETECT` (zero-FN release gate) and the async differential reflection oracle (bounded-latency re-partitioning of mislabelled findings).

### CMP-SNAP-03 — CW-DETECT closed-world precondition detector
**Depends-On:** none · **Staging:** Stage A
**Tasks:**
- T-CMP-SNAP-03-01: Implement the conservative over-approximating detector for reachable reflection / dynamic dispatch / open-hierarchy dispatch.
- T-CMP-SNAP-03-02: Document the safe direction explicitly: any reachable reflection construct must drive a `not-closed-world` verdict (false negatives forbidden; false positives merely cost performance).
**Tests:** TST-AC-SNAP-03a (release blocker), TST-AC-SNAP-03b, TST-INV-4-SNAP-03.
**Invariants threaded:** INV-4 (owner of Algorithm 1's precondition).
**Risk owned:** R-1.

### CMP-SNAP-01 — Snapshot service API
**Depends-On:** CMP-SCM-01, CMP-FND-03 · **Staging:** Stage A
**Tasks:**
- T-CMP-SNAP-01-01: Implement `POST /snapshots {codebase_id, commit_sha}` to enqueue a snapshot job.
- T-CMP-SNAP-01-02: Persist the five artifacts (CPG tarball, reverse-symbol index, dynamic call graph, ΔG, precondition-status record) at deterministic object-store keys.
- T-CMP-SNAP-01-03: Stamp `env_digest` from the worker's container image digest and record it on the snapshot row.
**Tests:** TST-AC-SNAP-01a, TST-AC-SNAP-01b, TST-AC-SNAP-01c, TST-INV-2-SNAP-01.

### CMP-SNAP-05 — Snapshot worker + environment pinning
**Depends-On:** CMP-SNAP-01, CMP-DEPLOY-02 · **Staging:** Stage A
**Tasks:**
- T-CMP-SNAP-05-01: Implement the worker against the existing env-var / `report_status` / argv-allowlist / secure-`subprocess.run` contract.
- T-CMP-SNAP-05-02: Mount the worker base image (CMP-DEPLOY-02) such that the container image digest is the authoritative `env_digest`.
- T-CMP-SNAP-05-03: Reject any invocation flag not on the sanctioned argument allowlist.
**Tests:** TST-AC-SNAP-05a, TST-AC-SNAP-05b.

### CMP-SNAP-02 — Incremental CPG maintenance (Algorithm 1)
**Depends-On:** CMP-SNAP-01, CMP-SNAP-03 · **Staging:** Stage A
**Tasks:**
- T-CMP-SNAP-02-01: Implement the closed-world incremental path: compute `AFFECTED = changed-decls ∪ reverse-symbol-closure(changed-decls) ∪ direct-callers(changed-signatures) ∪ CHA-cone(changed-types)`; visit only `AFFECTED + frontier` summary edges.
- T-CMP-SNAP-02-02: Implement the points-to-bounded cone fallback under `CW-DETECT`'s not-closed-world verdict.
- T-CMP-SNAP-02-03: Implement the `θ_cone` (default 0.25) and `θ_files` (default 0.4) full-reparse fallback.
- T-CMP-SNAP-02-04: Function-granularity reparse must preserve node IDs for unchanged declarations (key on enclosing-declaration content hash).
**Tests:** TST-AC-SNAP-02a (conditional theorem), TST-AC-SNAP-02b (empirical), TST-AC-SNAP-02c.

### CMP-SNAP-04 — Differential reflection oracle
**Depends-On:** CMP-SNAP-03, CMP-FND-02 · **Staging:** Stage A (must ship alongside CMP-SNAP-02, not later — see R-1)
**Tasks:**
- T-CMP-SNAP-04-01: Implement the asynchronous whole-program reflection scanner that runs off the critical path.
- T-CMP-SNAP-04-02: On disagreement with `CW-DETECT`, raise a determinism incident, retroactively re-partition the affected findings from `deterministic-core` to `oracle-passthrough`, and notify the affected customer.
- T-CMP-SNAP-04-03: Log every re-partition event to provenance.
- T-CMP-SNAP-04-04: Measure and publish the labeling-correction window as a contractual SLA.
**Tests:** TST-AC-SNAP-04a, TST-AC-SNAP-04b, TST-AC-SNAP-04c, TST-INV-1-SNAP-04.
**Risk owned:** R-1 (mitigates Closed-world FN leak).

---

## 8. Phase 5 — Analysis Core (PLAN draws from §6 + Algorithm 2/3/5)

**Goal.** The IFDS/IDE tabulation solver, the slice fingerprint, and the canonical CPG ordering. This is the principal engineering deliverable; per-language staging (§13) governs its rollout per language.

### CMP-CORE-03 — Canonical CPG ordering (Algorithm 5)
**Depends-On:** none · **Staging:** Stage A
**Tasks:**
- T-CMP-CORE-03-01: Implement 2-WL refinement.
- T-CMP-CORE-03-02: Implement bounded individualisation-refinement under hard `(B, T)` budget (defaults: `B = 2^16` search-tree nodes, `T = 200 ms`).
- T-CMP-CORE-03-03: Implement the stable-order fallback keyed on `(declaration-hash, structural-path-from-declaration-root, edge-kind)` on budget exhaustion.
- T-CMP-CORE-03-04: Name the persisted hash field `cpg_order_hash` and stamp the `canonical iff fingerprint_class = strong` annotation everywhere it appears (provenance record, SARIF properties, auditor export).
**Tests:** TST-AC-CORE-03a, TST-AC-CORE-03b, TST-AC-CORE-03c, TST-INV-5-CORE-03.
**Invariants threaded:** INV-5.

### CMP-CORE-01 — IFDS/IDE tabulation solver (Algorithm 2)
**Depends-On:** CMP-DET-01, CMP-SNAP-02, CMP-CORE-03 · **Staging:** Stage A (then per-language per §13)
**Tasks:**
- T-CMP-CORE-01-01: Build the exploded supergraph from the CPG and the loaded detector spec.
- T-CMP-CORE-01-02: Implement the RHS Tabulation algorithm with reusable procedure summaries.
- T-CMP-CORE-01-03: Implement the IDE extension for lattice-valued classes (crypto key-size, race windows, etc.).
- T-CMP-CORE-01-04: Implement incremental mode invalidating only `AFFECTED` summaries.
**Tests:** TST-AC-CORE-01a (release blocker), TST-AC-CORE-01b (per stage), TST-AC-CORE-01c, TST-INV-6-CORE-01.
**Invariants threaded:** INV-6.

### CMP-CORE-02 — Slice fingerprint (Algorithm 3)
**Depends-On:** CMP-CORE-01, CMP-CORE-03 · **Staging:** Stage A
**Tasks:**
- T-CMP-CORE-02-01: Compute the backward interprocedural slice along the witness.
- T-CMP-CORE-02-02: Implement the named normalisation passes: α-renaming for locals; PDG-only formatting; canonical topological sort for independent reordering; summary-inlining for extract/inline-method (pure-extract proven only); FQN normalisation for file-move / package-rename.
- T-CMP-CORE-02-03: Implement the bounded canonicalisation under the shared `(B, T)` budget with the `weak` fallback (witness-edge-sequence hash, `O(|witness|)` capped).
- T-CMP-CORE-02-04: Stamp `fingerprint_class` (`strong` | `weak`) on every emitted finding; ensure the baseline never auto-suppresses a `weak` finding across a refactor.
**Tests:** TST-AC-CORE-02a, TST-AC-CORE-02b, TST-AC-CORE-02c, TST-INV-5-CORE-02.

---

## 9. Phase 6 — Orchestration + scheduler (PLAN Phase 4)

**Goal.** Stand up the scan API, the heuristic scheduler `SNAP-SCHED-H`, and the detector-agnostic worker that loads a CPG once and runs IFDS or an oracle adapter per detector.

### CMP-ORCH-01 — Scan API
**Depends-On:** CMP-SNAP-01, CMP-FND-01, CMP-CP-01 · **Staging:** Stage A
**Tasks:**
- T-CMP-ORCH-01-01: Implement `POST /api/v1/scans {codebase_id, commit_sha, detector_ids[]}` to enqueue a scan job.
- T-CMP-ORCH-01-02: Implement `GET /api/v1/scans/{id}` and `GET /api/v1/scans/{id}/findings`.
- T-CMP-ORCH-01-03: Implement the worker callback `POST /api/v1/jobs/{job_id}/status` with HMAC-bearer verification.
- T-CMP-ORCH-01-04: On a scan submission, create the snapshot if absent, then fan one job per detector.
- T-CMP-ORCH-01-05: Backwards-compat: `scanipy --query extractall --run-semgrep` (Research mode) yields the historical CVE-2025-61765 finding with `origin=deterministic-core` on a Stage-A language.
**Tests:** TST-AC-ORCH-01a, TST-AC-ORCH-01b, TST-AC-ORCH-01c.

### CMP-ORCH-02 — Heuristic scheduler SNAP-SCHED-H (Algorithm 4)
**Depends-On:** CMP-ORCH-01 · **Staging:** cross-cutting
**Tasks:**
- T-CMP-ORCH-02-01: Implement snapshot-affinity grouping to amortise CPG load `L`.
- T-CMP-ORCH-02-02: Implement the independent-moldable 2-approx allotment as a heuristic seed (no constant-factor guarantee claimed).
- T-CMP-ORCH-02-03: Implement LPT list-scheduling with dependence-aware deferral.
- T-CMP-ORCH-02-04: Policy-gate the classes that customer policy elevates first.
- T-CMP-ORCH-02-05: Ensure documentation reads ρ≈2 strictly as a relaxation bound, never a guarantee.
**Tests:** TST-AC-ORCH-02a (empirical p95), TST-AC-ORCH-02b (schedule-invariance), TST-AC-ORCH-02c.
**Invariants threaded:** INV-1 (via schedule-invariance check).

### CMP-ORCH-03 — Detector-agnostic worker
**Depends-On:** CMP-CORE-01, CMP-DET-02, CMP-FND-01 · **Staging:** Stage A
**Tasks:**
- T-CMP-ORCH-03-01: Load the snapshot CPG once and resolve the detector via the registry.
- T-CMP-ORCH-03-02: Run IFDS for `engine ∈ {ifds, ide}`; run the oracle adapter for `engine ∈ {semgrep, cpg-query, external}`.
- T-CMP-ORCH-03-03: Stamp `origin` and `determinism_partition` on every emitted finding.
- T-CMP-ORCH-03-04: For `mixed`-class detectors, emit per-finding `origin` without blurring.
- T-CMP-ORCH-03-05: Emit SARIF in canonical CPG order (delegates to CMP-FND-01).
**Tests:** TST-AC-ORCH-03a, TST-AC-ORCH-03b, TST-INV-1-ORCH-03, TST-INV-2-ORCH-03.

---

## 10. Phase 7 — Findings & Provenance (PLAN Phase 5)

**Goal.** Normalise every detector output to SARIF, persist with the full provenance surface, and produce the signed audit chain.

### CMP-FND-02 — Findings store schema
**Depends-On:** CMP-CP-03 · **Staging:** cross-cutting
**Tasks:**
- T-CMP-FND-02-01: Create the `findings` table with columns `slice_fingerprint`, `fingerprint_class`, `origin`, `determinism_partition`, `witness_blob_uri`, `S_version`, `env_digest`, `cpg_order_hash`, `triage_score`, `triage_reason`, `status`.
- T-CMP-FND-02-02: Index `(codebase_id, slice_fingerprint)` for cross-scan baseline lookup.
- T-CMP-FND-02-03: Enforce non-null `origin`, `S_version`, `env_digest` at the schema level (INV-1, INV-2).
**Tests:** TST-AC-FND-02a, TST-AC-FND-02b, TST-INV-1-FND-02, TST-INV-2-FND-02.

### CMP-FND-01 — Findings normalizer
**Depends-On:** CMP-CORE-02, CMP-CORE-03 · **Staging:** Stage A
**Tasks:**
- T-CMP-FND-01-01: Normalise every detector output to SARIF 2.1.0.
- T-CMP-FND-01-02: Attach the slice fingerprint and `fingerprint_class` to every result.
- T-CMP-FND-01-03: Emit results in canonical CPG order from `CMP-CORE-03`.
**Tests:** TST-AC-FND-01a, TST-AC-FND-01b, TST-INV-1-FND-01.

### CMP-FND-03 — Signed provenance record
**Depends-On:** CMP-FND-02 · **Staging:** Stage A
**Tasks:**
- T-CMP-FND-03-01: Construct the audit chain `source commit → snapshot digest → S_version → env_digest → cpg_order_hash (canonical iff strong) → taint witness → rule/spec id → SARIF hash → per-finding origin`.
- T-CMP-FND-03-02: Sign the record.
- T-CMP-FND-03-03: Stamp the conditional-canonicality annotation on `cpg_order_hash` in the auditor export.
- T-CMP-FND-03-04: Append every differential-oracle re-partition event to the record.
**Tests:** TST-AC-FND-03a, TST-AC-FND-03b, TST-AC-FND-03c, TST-INV-1-FND-03, TST-INV-5-FND-03.

---

## 11. Phase 8 — Triage + spec inference with the e-process gate (PLAN Phase 7)

**Goal.** Stand up the LLM triage ranker (default off; never deletes findings), the anytime-valid e-process spec gate, and the per-customer revalidation and drift monitor. The acceptance gate and the drift monitor share one mathematical instrument.

### CMP-TRI-01 — LLM triage ranking
**Depends-On:** CMP-FND-02 · **Staging:** post-core (after Stage A)
**Tasks:**
- T-CMP-TRI-01-01: Score `(likely_exploitable, likely_test_code, likely_fp)` from the SARIF blob plus a bounded code window.
- T-CMP-TRI-01-02: Write `triage_score` and `triage_reason` only; never touch `origin` or detection content.
- T-CMP-TRI-01-03: Default the feature flag to off.
- T-CMP-TRI-01-04: Make ranking strictly additive — never delete a finding.
**Tests:** TST-AC-TRI-01a, TST-AC-TRI-01b, TST-INV-1-TRI-01, TST-INV-3-TRI-01.
**Invariants threaded:** INV-3.

### CMP-TRI-02 — Anytime-valid e-process spec gate (Algorithm 6)
**Depends-On:** CMP-DET-02, CMP-FND-02 · **Staging:** post-core (after Stage A)
**Tasks:**
- T-CMP-TRI-02-01: For each candidate spec `σ`, maintain an e-process `E_t(σ)` for the precision-floor null `H0(σ) : true precision of σ < π₀`.
- T-CMP-TRI-02-02: Use a betting confidence sequence for the bounded mean (per `PLAN.md` Algorithm 6).
- T-CMP-TRI-02-03: Accept `σ` when `E_t(σ) ≥ 1/α`; write the accepted spec version-pinned as a new `S_version`.
- T-CMP-TRI-02-04: Combine multiplicity over selected specs by e-process averaging (closed under averaging).
- T-CMP-TRI-02-05: Implement the martingale-property unit test as a pre-customer-enablement gate.
**Tests:** TST-AC-TRI-02a (falsifier — adversarial unbounded continuation), TST-AC-TRI-02b (release-blocking unit test), TST-AC-TRI-02c, TST-INV-2-TRI-02, TST-INV-3-TRI-02.
**Risk owned:** R-3.

### CMP-TRI-03 — Per-customer revalidation + drift monitor
**Depends-On:** CMP-TRI-02 · **Staging:** post-core
**Tasks:**
- T-CMP-TRI-03-01: Maintain `S = S_global ∪ S_customer` per scan; pin both per scan.
- T-CMP-TRI-03-02: Run the same e-process instrument on the customer's adjudicated stream.
- T-CMP-TRI-03-03: Auto-quarantine `σ` for a customer on a floor breach.
- T-CMP-TRI-03-04: Label findings dependent on an unrevalidated global spec as `spec_provenance = global-unrevalidated` until revalidation.
**Tests:** TST-AC-TRI-03a, TST-AC-TRI-03b.

---

## 12. Phase 9 — Determinism Attestor + CPG-fidelity gate (PLAN Phase 9)

**Goal.** The partitioned Attestor (core: byte-identical SARIF hard-fail; oracle: digest-stability + measured rate) and the per-language CPG-fidelity gate that decides which `(class, language)` pairs are eligible for Algorithm 2 benchmarking.

### CMP-CP-05 — Determinism Attestor (partitioned)
**Depends-On:** CMP-ORCH-01, CMP-FND-03 · **Staging:** Stage A
**Tasks:**
- T-CMP-CP-05-01: Core pipeline — re-run `F` under fixed `(S_version, env_digest, LLM_TRIAGE=off)` and assert byte-identical SARIF over the `deterministic-core` partition. Any diff hard-fails CI.
- T-CMP-CP-05-02: Oracle pipeline — record oracle digests and report a measured reproduction rate; never assert the reproducibility theorem.
- T-CMP-CP-05-03: Run both pipelines on the canary corpus on every detector / engine / `Env` change.
- T-CMP-CP-05-04: Deliberately introduce a core-path nondeterminism in a scoped harness; verify the core pipeline fails (release gate self-test).
**Tests:** TST-AC-CP-05a, TST-AC-CP-05b, TST-AC-CP-05c, TST-INV-3-CP-05.
**Risk owned:** R-4 (alongside CMP-SNAP-04).

### CMP-CP-06 — CPG-fidelity gate harness
**Depends-On:** CMP-SNAP-05 · **Staging:** per language
**Tasks:**
- T-CMP-CP-06-01: For each target language, curate the fidelity corpus with ground-truth ASTs/CFGs/call-edges (corpus is itself a work package; see CMP-CORP-CPG-*).
- T-CMP-CP-06-02: Implement the gate thresholds: parse success ≥ 99.5% of files; call-edge precision/recall ≥ stated thresholds; PDG dependence-edge recall ≥ threshold.
- T-CMP-CP-06-03: A `(class, language)` pair enters Algorithm 2 benchmarking only after passing.
- T-CMP-CP-06-04: Record gate results per language; the staging logic consumes this record.
- T-CMP-CP-06-05: Report failing languages as `front-end-blocked`, never as recall failures.
**Tests:** TST-AC-CP-06a, TST-AC-CP-06b, TST-INV-6-CP-06.
**Invariants threaded:** INV-6.
**Risk owned:** R-2.

---

## 13. Phase 10 — Per-language staging (overlay, §11 of SDD)

**Goal.** Sequence Phase 2–9 work per language. A stage may not begin until the prior stage's core components have passed every AC **and** the relevant CPG-fidelity gate is green for that language. Stages leave the system runnable and independently shippable.

### Stage A — Java + Python
- Languages with the strongest Joern front-ends.
- Detector classes promoted to core: `injection`, `path-traversal`, `ssrf`, `deserialization`.
- Algorithm 2 falsifier (TST-AC-CORE-01b) is first meaningful here.
- Other detector classes ship `oracle-passthrough` until later stages.

### Stage B — JS/TS
- Begins only after Stage A is determinism-attested (`CMP-CP-05` green for Stage A).
- JS/TS front-end fidelity validated via `CMP-CP-06` before any class falsifier counts.

### Stage C — Go
- Front-end fidelity gate first.
- Carries an explicit points-to / interface-dispatch investment work package as a prerequisite (`T-STAGE-C-FE-01`).
- Algorithm 2 benchmarking only after the gate passes.

### Stage D — Ruby, PHP
- Lowest front-end maturity.
- Until the fidelity gate passes, these languages ship `oracle-passthrough` only.
- Likely requires a proprietary front-end work package (`T-STAGE-D-FE-01` — filed as `CLAR-FE-01`).

### C/C++ (memory-safety)
- Remains `oracle-passthrough` (CodeQL) throughout v3.2.
- Port to core is tracked but explicitly **out of v3 scope** (see `OOS-CC-01`).

### Always `oracle-passthrough` throughout v3.2
- `secrets`, `dep-cve` — deterministic in practice, attested, not theorem-covered.
- `crypto-misuse`, `authn-authz` — `mixed`. The IDE/IFDS portion follows its language's staging; the pattern portion ships `oracle-passthrough`.

### Staging tasks (one per stage)
- T-STAGE-A-01: Promote Java + Python to core for `{injection, path-traversal, ssrf, deserialization}`. Gate on `CMP-CP-05` green and `CMP-CP-06` green for both languages.
- T-STAGE-B-01: Promote JS/TS to core. Gate on Stage A determinism-attested and `CMP-CP-06` green for JS/TS.
- T-STAGE-C-01: Promote Go to core. Gate on `CMP-CP-06` green for Go (which gates on `T-STAGE-C-FE-01` — points-to / interface-dispatch investment).
- T-STAGE-D-01: Promote Ruby and PHP to core. Gate on `CMP-CP-06` green for both (likely requires `T-STAGE-D-FE-01` — proprietary front-end work).

---

## 14. Phase 11 — Multi-tenant control plane (PLAN Phase 6)

**Goal.** Tenancy schema, RBAC, credential encryption, authentication, dashboard.

### CMP-CP-03 — Tenancy schema + migrations
**Depends-On:** none · **Staging:** cross-cutting
**Tasks:**
- T-CMP-CP-03-01: Tables `orgs`, `projects`, `codebases`, `scm_credentials`, `org_policies`, `memberships`, `snapshots` (+ precondition-status), `proposed_specs`, `spec_versions`, `attestations`. Reuse the existing `BaseDatabase`.
- T-CMP-CP-03-02: Author forward + rollback migrations that apply cleanly on a fresh database.
**Tests:** TST-AC-CP-03a.

### CMP-CP-02 — Credential encryption service
**Depends-On:** none · **Staging:** cross-cutting
**Tasks:**
- T-CMP-CP-02-01: Encrypt `scm_credentials` at rest with a managed key.
- T-CMP-CP-02-02: Support key rotation.
- T-CMP-CP-02-03: Expose the key service consumed by CMP-SCM-01.
**Tests:** TST-AC-CP-02a.

### CMP-CP-01 — Multi-tenant scan API guard
**Depends-On:** CMP-CP-03 · **Staging:** cross-cutting
**Tasks:**
- T-CMP-CP-01-01: Require `X-Scanipy-Org-Id` and `X-Scanipy-User-Id` on every API call.
- T-CMP-CP-01-02: Scope every query by org id; enforce RBAC in the API layer.
- T-CMP-CP-01-03: Parameterise the cross-org-access negative test (TST-AC-CP-01a).
**Tests:** TST-AC-CP-01a.

### CMP-CP-04 — Authentication (OIDC/SAML) + dashboard
**Depends-On:** CMP-CP-01, CMP-FND-03 · **Staging:** cross-cutting
**Tasks:**
- T-CMP-CP-04-01: Implement OIDC/SAML federation in `web/auth.ts` / `web/middleware.ts`.
- T-CMP-CP-04-02: First-admin provisioning on SSO sign-up — creates org row and admin membership.
- T-CMP-CP-04-03: Build the dashboard tree orgs → projects → codebases → scans → findings grouped by class.
- T-CMP-CP-04-04: Per-finding render: witness, `origin`, `S_version`, `env_digest`, and the conditional-canonicality annotation.
- T-CMP-CP-04-05: Visual partition — `deterministic-core` and `oracle-passthrough` are never blurred in the UI.
**Tests:** TST-AC-CP-04a, TST-AC-CP-04b.

---

## 15. Phase 12 — Research mode reattached (PLAN Phase 8)

**Goal.** Preserve the GitHub-search-driven Research mode that feeds synthetic codebases and labelled CVE findings into the same pool; route labelled CVE findings to the e-process evaluation stream.

### CMP-RES-01 — Research mode service
**Depends-On:** CMP-SCM-02 (GitHub-only `search_code()`), CMP-TRI-02 (e-process evaluation stream) · **Staging:** post-core
**Tasks:**
- T-CMP-RES-01-01: Implement `services/research/api.py` to feed synthetic codebases into the shared scan pool.
- T-CMP-RES-01-02: Route labelled CVE findings into the e-process evaluation stream with explicit covariate-shift handling.
- T-CMP-RES-01-03: Preserve the v2-era `scanipy --query` CLI entry points as caller-transparent shims (covered by TST-AC-ORCH-01c).
**Tests:** Recall-claim-per-language tests of Algorithm 2 use Research-mode-curated corpora; coverage rolled into TST-AC-CORE-01b per stage. No new top-level AC; the feature is exercised through CMP-ORCH-01 and CMP-TRI-02 ACs.

---

## 16. Phase 13 — Cross-cutting concerns (SDD §12)

Each item below is a discrete work package; not a metadata field on another package.

### CMP-CORP-REFL-01 — Reflection corpus
**Depends-On:** none · **Staging:** Stage A (must precede `TST-AC-SNAP-03a`).
**Purpose.** Curated labelled reflection corpus driving Falsifier CW: Spring dynamic proxies, Python `__import__` / `getattr` dispatch, Ruby `send` / `method_missing`, PHP variable functions, Java `Class.forName`, plus mutation-injected reflection in otherwise-closed-world repos with ground-truth labels.
**Acceptance criteria:**
- AC-CORP-REFL-01a: Corpus covers every category listed above with ≥ N labelled examples per category (`N` filed as `CLAR-CORP-01`).
- AC-CORP-REFL-01b: Mutation-injection pipeline reproducibly generates labelled reflection scenarios from clean closed-world repos.
- AC-CORP-REFL-01c: Corpus is versioned; a corpus change is part of the release ledger.

### CMP-CORP-CPG-{java,python,js,go,ruby,php} — CPG-fidelity corpora
**Depends-On:** none · **Staging:** per language (must precede that language's entry into `CMP-CP-06` / Algorithm 2 benchmarking).
**Purpose.** Per-language fidelity corpus with ground-truth ASTs, CFGs, and call-edges. One corpus per language; six total.
**Acceptance criteria:**
- AC-CORP-CPG-*a: Corpus carries ground-truth AST/CFG/call-edge annotations and a documented annotation methodology.
- AC-CORP-CPG-*b: Corpus is versioned; gate thresholds are evaluated against the pinned corpus version.

### CMP-CORP-CANARY-01 — Canary repo set across four SCMs
**Depends-On:** CMP-SCM-02, CMP-SCM-03 · **Staging:** Stage A.
**Purpose.** 100 canary repos mirrored to GitHub, GitLab, Bitbucket, Azure DevOps; used by `TST-AC-CORE-01a` (determinism) and `TST-AC-SCM-03c` (identical commit resolution).
**Acceptance criteria:**
- AC-CORP-CANARY-01a: 100 repos, each mirrored to all four providers with identical commit history.
- AC-CORP-CANARY-01b: Re-mirroring is automated and reproducible.

### CMP-CORP-REFAC-01 — Seeded-refactor set
**Depends-On:** none · **Staging:** Stage A (must precede `TST-AC-CORE-02a/b`).
**Purpose.** 50 seeded findings paired with each named refactor (α-renaming, formatting, independent reordering, pure extract, file-move / package-rename) and with a genuine fix and an aliasing-changing extract.
**Acceptance criteria:**
- AC-CORP-REFAC-01a: 50 seeded findings × each refactor; ground-truth labels (`should-flip` vs `should-stay`).
- AC-CORP-REFAC-01b: Adding a new refactor is a documented procedure with a regression-impact assessment.

### CMP-CORP-VULN-01 — OWASP / Juliet / BigVul slices
**Depends-On:** none · **Staging:** Stage A.
**Purpose.** Evaluation slices used by Algorithm 2's per-(class, language) recall claim. Held-out portion of BigVul is preserved across releases.
**Acceptance criteria:**
- AC-CORP-VULN-01a: OWASP Benchmark + Juliet integrated; BigVul held-out split is versioned and never used for training.
- AC-CORP-VULN-01b: Per-(class, language) slicing supports the per-stage benchmark in `TST-AC-CORE-01b`.

### CMP-CI-01 — Continuous-integration gate pipeline
**Depends-On:** CMP-DEPLOY-04 · **Staging:** cross-cutting (lit up in Stage A; extended per stage).
**Purpose.** Enforce the four named gates as continuous, hard-failing CI gates rather than periodic checks. Wire them so a failure of any one fails the pipeline.
**Tasks:**
- T-CMP-CI-01-01: Wire `AC-DET-01a` (combinator distributivity-proof obligations) as a hard CI gate on the `analysis/ifds/dsl/` directory.
- T-CMP-CI-01-02: Wire `AC-SNAP-03a` (Falsifier CW zero-FN gate) as a release-blocking job.
- T-CMP-CI-01-03: Wire `AC-CP-05c` (Attestor runs core + oracle pipelines on canary corpus on every detector/engine/Env change) as a hard CI gate.
- T-CMP-CI-01-04: Wire `AC-TRI-02b` (e-process martingale-property unit test) as a pre-customer-enablement gate that blocks the customer-enablement deploy stage.
- T-CMP-CI-01-05: Document the gate failure-response procedure (who is paged, how to roll back, how to re-attest).

### Provenance threading (SDD §12)
Per-component verification tasks rather than a single global task. Already enumerated:
- TST-INV-2-SNAP-01 (snapshot writes `env_digest`).
- TST-INV-2-ORCH-03 (every emitted finding carries `S_version` and `env_digest`).
- TST-INV-2-FND-02 (schema-level non-null check).
- TST-INV-2-TRI-02 (accepted spec is version-pinned).
- TST-INV-1-{ORCH-03, FND-01, FND-02, FND-03, SNAP-04, TRI-01}.
- TST-INV-5-{CORE-03, FND-03, CORE-02}.
- TST-INV-6-{CP-06, CORE-01}.
- TST-INV-3-{TRI-01, TRI-02, CP-05}.
- TST-INV-4-{SNAP-03, DET-01}.

---

## 17. CLARIFICATION-NEEDED register

These items must be resolved before the work that depends on them can begin. Each carries a target resolution phase; per-component ownership is tracked separately under `CLAR-OWNER-01` (DEFERRED — to be populated in `docs/cross-cutting/DOC-OWNERS.md` once teams are seated). **Resolved** items carry a one-line decision summary and link to the full decision record. **Deferred** items remain blocking until a human decision is recorded.

| Id | Question | Blocks | Target resolution | Status | Resolved date | Decision summary |
|---|---|---|---|---|---|---|
| CLAR-DEPLOY-01 | Cloud / compute service selection (container-orchestration primitive) | CMP-DEPLOY-01..05; everything dependent | Before Phase 4 | RESOLVED | 2026-05-23 | AWS ECS Fargate, pinned-image workers. See `docs/cross-cutting/DOC-DEPLOY-DECISIONS.md`. |
| CLAR-DEPLOY-02 | Object-store choice (must support content-addressable, deterministic keys) | CMP-SNAP-01 | Before Phase 4 | RESOLVED | 2026-05-23 | Amazon S3, key `orgs/{org_id}/codebases/{codebase_id}/snapshots/{commit_sha}/{env_digest}/{artifact}`; content-addressable via `commit_sha` (Git content hash) + `env_digest`. See `docs/cross-cutting/DOC-DEPLOY-DECISIONS.md`. |
| CLAR-DEPLOY-03 | Relational-DB engine + version | CMP-CP-03; CMP-FND-02 | Before Phase 7 (Findings) | RESOLVED | 2026-05-23 | PostgreSQL 16 on Amazon RDS, Alembic migrations. See `docs/cross-cutting/DOC-DEPLOY-DECISIONS.md`. |
| CLAR-DEPLOY-04 | KMS / envelope-encryption vendor + rotation primitive | CMP-CP-02 | Before Phase 11 (Control plane) | RESOLVED | 2026-05-23 | AWS KMS envelope encryption, per-tenant CMKs, annual rotation. See `docs/cross-cutting/DOC-DEPLOY-DECISIONS.md`. |
| CLAR-DEPLOY-05 | Secrets vendor + injection path into workers | CMP-DEPLOY-02..04 | Before Phase 4 | RESOLVED | 2026-05-23 | AWS Secrets Manager, ECS task `secrets` env-var injection. See `docs/cross-cutting/DOC-DEPLOY-DECISIONS.md`. |
| CLAR-DEPLOY-06 | Queue technology + DLQ + visibility-timeout / retry semantics | CMP-ORCH-01..03 | Before Phase 6 (Orchestration) | RESOLVED | 2026-05-23 | Amazon SQS standard + per-queue DLQ, max-receive 3. See `docs/cross-cutting/DOC-DEPLOY-DECISIONS.md`. |
| CLAR-DEPLOY-07 | Observability stack — logs, metrics, traces, alarms | CMP-DEPLOY-03 | Before Phase 4 | RESOLVED | 2026-05-23 | OpenTelemetry → CloudWatch Logs + X-Ray. See `docs/cross-cutting/DOC-DEPLOY-DECISIONS.md`. |
| CLAR-DEPLOY-08 | Region strategy — per-env, per-tenant, single-region | CMP-DEPLOY-01 | Before Phase 4 | RESOLVED | 2026-05-23 | Single region `us-east-1` (prod), `us-east-2` (staging). See `docs/cross-cutting/DOC-DEPLOY-DECISIONS.md`. |
| CLAR-DEPLOY-09 | Network model — VPC, private subnets, ingress / egress controls | CMP-DEPLOY-01 | Before Phase 4 | RESOLVED | 2026-05-23 | Single VPC per env, three subnet tiers, VPC endpoints. See `docs/cross-cutting/DOC-DEPLOY-DECISIONS.md`. |
| CLAR-DEPLOY-10 | OIDC / SAML IdP integration target — preferred IdP, federation pattern | CMP-CP-04 | Before Phase 11 | RESOLVED | 2026-05-23 | Auth0 (primary); federated to customer IdPs via Auth0 connections. See `docs/cross-cutting/DOC-DEPLOY-DECISIONS.md`. |
| CLAR-DEPLOY-11 | CI/CD provider + OIDC-to-cloud trust pattern | CMP-DEPLOY-04 | Before Phase 4 | RESOLVED | 2026-05-23 | GitHub Actions, OIDC-to-AWS keyless. See `docs/cross-cutting/DOC-DEPLOY-DECISIONS.md`. |
| CLAR-DEPLOY-12 | RBAC model surface — which roles exist (admin, viewer, scanner, …), default role on first-admin provisioning | CMP-CP-01, CMP-CP-04 | Before Phase 11 | RESOLVED | 2026-05-23 | Roles `org-admin`, `org-viewer`, `scanner`; first user → `org-admin`. See `docs/cross-cutting/DOC-DEPLOY-DECISIONS.md`. |
| CLAR-DEPLOY-13 | Image registry + signing/attestation surface | CMP-DEPLOY-02, CMP-DEPLOY-04 | Before Phase 4 | RESOLVED | 2026-05-23 | Amazon ECR + Sigstore Cosign keyless, SLSA-3 attestation. See `docs/cross-cutting/DOC-DEPLOY-DECISIONS.md`. |
| CLAR-DEPLOY-14 | LLM provider for triage and spec inference, plus pricing/quota controls | CMP-TRI-01, CMP-TRI-02 | Before Phase 8 enable | RESOLVED | 2026-05-23 | Anthropic API `claude-sonnet-4-6`; per-tenant quota via `CMP-CP-01`. See `docs/cross-cutting/DOC-DEPLOY-DECISIONS.md`. |
| CLAR-DEPLOY-15 | Data retention policy per artifact class (CPG tarball, witness blob, SARIF, provenance record); legal hold and export | CMP-DEPLOY-01, CMP-FND-03 | Before Phase 7 | RESOLVED | 2026-05-23 | CPG 90d / witness 1y / SARIF+provenance 7y (S3 Object Lock). See `docs/cross-cutting/DOC-DEPLOY-DECISIONS.md`. |
| CLAR-DEPLOY-16 | Per-tenant data-isolation backstop at the substrate layer (e.g. per-tenant blob namespace; per-tenant DB row-level security) | CMP-DEPLOY-05 | Before Phase 11 | RESOLVED | 2026-05-23 | S3 prefix + RDS row-level security + KMS per-tenant CMKs. See `docs/cross-cutting/DOC-DEPLOY-DECISIONS.md`. |
| CLAR-DEPLOY-17 | Server-side branch protection / required-status-checks are unavailable on this repo (GitHub Free/private — `gh api .../branches/main/protection` returns 403). `DOC-CMP-CI-01 §3.3` and `DOC-CMP-DEPLOY-04 §3` both assume gate enforcement via required status checks on `main`. Decision: upgrade plan (Pro/Team) or make repo public to enable native protection, vs keep the process-level shim doctrine (`enforce-pr-only-merges.yml` + RULE-10). Surfaced by the Phase-0b workflow-docs review. | CMP-CI-01 §3.3 enforcement; CMP-DEPLOY-04 §3 deploy-time gate verification | Before Stage-A go-live | RESOLVED | 2026-06-03 | **CTO ratified 2026-06-03 (DECISION-PART2 Q3):** keep the process-level shims (`enforce-pr-only-merges.yml` + RULE-10 fail-closed loud-red check) through v3.2 — fail-closed enforcement at no cost; native branch protection (GitHub Team/Pro or public repo) is a one-step wire-up if/when the org upgrades, not funded now. Full record: `DOC-DEPLOY-DECISIONS.md` § CLAR-DEPLOY-17. CI-01/DEPLOY-04 docs remain annotated as subject to this CLAR. |
| CLAR-DEPLOY-18 | IaC scaffolding (`infra/` Terraform/CDK) deferred from CMP-DEPLOY-01. The PR #238 substrate port-surface (`services/substrate/`) proves the substrate contract (AC-DEPLOY-01a..e) but does not include the production IaC under `infra/`. CMP-DEPLOY-02..05 depend on the substrate *decisions* (all 16 CLAR-DEPLOY-* RESOLVED) but will need the IaC layer to provision real AWS resources. Decision: should the IaC scaffolding be delivered as a sub-task of CMP-DEPLOY-01 (blocking close of issue #3), or as the first task of CMP-DEPLOY-02 which has `Depends-On: CMP-DEPLOY-01`? | CMP-DEPLOY-02..05; CMP-SNAP-05 (first phase that exercises every substrate primitive in production) | Before Phase 4 start | RESOLVED | 2026-06-03 | **CTO ratified 2026-06-03 (DECISION-PART2 §3):** production IaC (`infra/` Terraform) is the **first task of CMP-DEPLOY-02** (Depends-On CMP-DEPLOY-01); CMP-DEPLOY-01 ACs (01a..e) stay contract-only (port-surface + decision record), which cleanly closes issue #3. Pure work-sequencing, no new money/scope. Full record: `DOC-DEPLOY-DECISIONS.md` § CLAR-DEPLOY-18. |
| CLAR-CORP-01 | Reflection corpus minimum sample size per category (Spring proxies, Python `__import__`/`getattr`, Ruby `send`/`method_missing`, PHP variable functions, Java `Class.forName`, mutation-injected) | CMP-CORP-REFL-01 | Before Phase 4 | RESOLVED | 2026-05-23 | N ≥ 50 per category, ≥ 20 mutation-injected per language; revisit during `CMP-CORP-REFL-01` build. |
| CLAR-CORP-02 | CPG-fidelity gate exact thresholds per language (parse success ≥ 99.5% is given; call-edge precision/recall and PDG dependence-edge recall floors are not pinned) | CMP-CP-06 | Per stage | RESOLVED | 2026-05-23 | Parse ≥99.5%, call-edge precision ≥90%, recall ≥85%, PDG dependence-edge recall ≥80% per language. |
| CLAR-PARAM-01 | Default values for `κ` (closed-world κ-bound regression threshold), `θ_cone` (default 0.25 stated; confirm), `θ_files` (default 0.4 stated; confirm), `(B, T)` budget (defaults `2^16` nodes / 200 ms stated; confirm) | CMP-SNAP-02, CMP-CORE-02, CMP-CORE-03 | Before relevant stage | RESOLVED | 2026-05-23 | Confirm θ_cone=0.25, θ_files=0.4, B=2^16, T=200ms; κ TBD by detector at registration. **κ refinement 2026-06-03 (DECISION-PARAM-01):** κ is the property-(b) **economics** ceiling on the per-commit ratio ρ = time(Δ)/[(\|AFFECTED\|/\|graph\|)·time(full)]; it has **no runtime consumer** (gates only the post-hoc TST-AC-SNAP-02a timing test), so a labelled interim is RULE-4-safe. Calibrated in Phase 5, certified per-language at Stage-A go-live as ⌈MAX(ρ, floored corpus)⌉ × margin (MAX, not p99 — per-commit zero-tolerance gate). Per-detector registry read unchanged. **Blocked on the well-posedness fix (CLAR-PARAM-04).** Interim dev κ=50 is mechanically separated and never feeds the still-xfail hard gate. **D-7 (CTO):** AC-SNAP-02a is a Stage-A-go-live economics gate, **decoupled** from the CMP-CORE-01 dev dependency — CORE-01 development may start now against a correct SNAP-02 (AC-SNAP-02c green). |
| CLAR-PARAM-02 | Default values for the e-process gate: `π₀` per detector class, `α`, and the per-class evaluation-stream definition | CMP-TRI-02 | Before Phase 8 enable | DEFERRED | — | π₀ requires per-class empirical baseline (collect during Phase 5); α=0.05 confirmed. **Refinement 2026-06-03 (DECISION-PARAM-01 §8):** the two real blockers are (i) the per-class **certified** π₀ values and (ii) the per-class **evaluation-stream definition** — pin the stream first (which adjudicated findings feed which σ). Interim uniform π₀=0.80 (config-driven, never hardcoded; the martingale holds for any π₀, so Gate-4 stays green). Stays DEFERRED to Phase 5; Security + Architect own it (RULE-9, INV-3). |
| CLAR-PARAM-04 | Should AC-SNAP-02a's bound be affine — `time(Δ) ≤ κ·(\|AFFECTED\|/\|graph\|)·time(full) + C₀` — to absorb the constant frontier + O(\|graph\|) serialization floor (restoring `PLAN.md`'s `O(\|AFFECTED\| + frontier)`), or should the floor be removed by delta-only / copy-on-write persistence, or by an architect-ratified corpus / `\|AFFECTED\|` floor? How is `C₀`/`f_min` pinned per (language, Env)? Without this the per-commit ratio ρ diverges on small commits and no single frozen scalar κ is well-posed. Filed by DECISION-PARAM-01 (D-3). | CMP-SNAP-02 (gates the certified-κ pin for TST-AC-SNAP-02a; does **not** block CMP-CORE-01 dev per PARAM-01 D-7) | Stage-A go-live | OPEN | — | Architect decision (PLAN↔SDD arbitration via /cto if they conflict); recommended primary fix = normalize the O(\|graph\|) term out of measured time(Δ) (delta-only / copy-on-write persistence) + route sub-T commits to full-reparse, with the affine +C₀ variant as the architect's option at ratification. |
| CLAR-CORE-01 | DOC-CMP-CORE-01 §3.1/§8's solver/Finding interface diverges from the shipped CMP-DET-01 `Spec` (id/class_/languages/engine/clauses): the doc's S_version/mode/fact_domain/lattice/flow_factory/source_preds/sink_preds/dsl_closure_proof_digest fields are absent, so `solve()`/`incremental_solve()` take S_version/env_digest as kwargs and build the clause→FlowFunction adapter + AccessPathPattern matcher in CMP-CORE-01; the doc's defensive `dsl_closure_proof_digest` INV-4 re-check is dropped (DET-01 `parse_spec` owns INV-4 at registration per CLAR-DET-02 RESOLVED); `Finding.determinism_partition` is dropped (shipped Spec lacks it; stamped downstream by CMP-DET-02/ORCH-03 — not one of the four RULE-6 fields); PR1's `SolverResult` does not yet expose the `SummaryCache` (per-procedure summaries consumed by CMP-CORE-02 are computed internally, surfaced in the CORE-02-handoff PR). Filed by the CMP-CORE-01 PR1 implementation. | CMP-CORE-01 (solver interface); CMP-CORE-02 (consumes summaries) | Before Stage A go-live | OPEN | — | Provisional (PR1 in effect): build the clause→flow adapter + AccessPathPattern matcher in CMP-CORE-01; drop the unimplementable doc fields against the shipped `Spec`/`Finding`; expose `SummaryCache` on `SolverResult` in the CORE-02-handoff PR. Architect to reconcile DOC-CMP-CORE-01 §3.1/§8 with the shipped shapes. |
| CLAR-PARAM-03 | Default value for the `weak`-fallback-rate publish threshold (5% target stated; confirm operational threshold) | CMP-CORE-02 | Before Phase 5 | RESOLVED | 2026-05-23 | 5% confirmed as operational publish threshold (gates `CMP-CORE-02` benchmark report). |
| CLAR-SLA-01 | Differential-oracle labeling-correction window SLA target | CMP-SNAP-04 | Before Stage A go-live | RESOLVED | 2026-05-23 | 24h for high-impact incidents, 7d for routine; finalize numeric SLA at Stage A go-live. |
| CLAR-FE-01 | Stage-D proprietary front-end work — build vs buy vs delay | T-STAGE-D-FE-01 | Before Stage D | DEFERRED | — | Business decision required (build/buy/delay); Ruby/PHP remain oracle-passthrough until resolved. **Team decision 2026-06-03 (DECISION-PART2 Q1): DELAY for v3.2** — no Stage-D customer committed; stays DEFERRED (honest `front-end-blocked`, INV-6); no spend. Revisit if/when Stage D is funded. |
| CLAR-FE-02 | Stage-C points-to / interface-dispatch investment scope (Andersen-style baseline vs richer) | T-STAGE-C-FE-01 | Before Stage C | DEFERRED | — | Scoping decision required; default to Andersen-style baseline if approved. **Team decision 2026-06-03 (DECISION-PART2 Q1): DELAY for v3.2** — Go stays oracle-passthrough (`front-end-blocked`); if later funded, an Andersen-style baseline is the cheapest gate-clearing path. Stays DEFERRED; no spend. |
| CLAR-OWNER-01 | Module / corpus / risk owners — every `CMP-*` and every `R-*` mitigation needs a named owner | All phases | Continuous | RESOLVED | 2026-06-03 | **CTO decision 2026-06-03 (DECISION-PART3 Q1 → option 1):** ratify the **role/agent-doctrine ownership map** (subsystem→role + R-*→role) as the v3.2 working assignment — recorded in `docs/cross-cutting/DOC-OWNERS.md`; revisit when human teams are seated. Named-individual assignment stays out of agent scope (RULE-4 — no human-name source); supply names later by editing that one file. `Risk owned:` tags are component→risk attributions, not person assignments. RULE-9 Security co-sign is a standing owner on the seven INV-3/INV-4 components. (CLAR-CORP-03 second-reviewer stays DEFERRED with the corpus campaign.) |
| CLAR-MIGRATION-01 | Legacy data migration plan from v2 to v3.2 (findings, codebase membership, credentials) — in scope vs new-env-only | CMP-CP-03 | Before Phase 11 | RESOLVED | 2026-06-03 | **Decision 2026-06-03 (DECISION-PART2 Q6):** launch is **new-environment-only** — no v2 customer data (findings, codebase membership, credentials) is carried into v3.2; no migration is scoped. If a customer migration is later contractually committed, scope it (incl. credential re-encryption under the new KMS envelope) as a fresh work item before Phase 11. |
| CLAR-API-01 | URL alignment for `POST /snapshots` (SDD line 97) and `POST /api/v1/jobs/{job_id}/status` (SDD line 193) under the unified `/api/v1/` prefix proposed by `DOC-API.md` | None (SDD path is normative until resolved) | Pre-GA housekeeping | RESOLVED | 2026-06-03 | **Architect ratified 2026-06-03 (DECISION-PART2 §2A):** SDD paths stand — the inconsistency is internal to the normative SDD and the Architect cannot rewrite SDD paths (SoT fence); it blocks nothing. An alignment proposal may move both under `/api/v1/` post-acceptance. Lowest priority. |
| CLAR-SLA-02 | Numeric per-tenant rate-limit budgets (general API RPM/burst) and LLM RPM/TPD budgets enforced by `CMP-CP-01` (CLAR-DEPLOY-14 names the vendor only) | CMP-CP-01 enforcement defaults | Before Stage A go-live | RESOLVED | 2026-06-03 | **SRE ratified 2026-06-03 (DECISION-PART2 §4, RR-CONFIRM) — interim:** adopt the `DOC-API §7` general-API enforcement numbers as interim (60 req/s sustained per org, burst 200/5s; `POST /scans` 600/hr; `POST /snapshots` 1200/hr; `429 rate_limited`); the **LLM RPM/TPD budget** = fail-closed interim (deny when unset). **Residual (human/cost input still needed before Stage-A go-live):** the real LLM RPM/TPD numbers (Anthropic per-account quota under CLAR-DEPLOY-14 + expected per-tenant triage volume). |
| CLAR-DB-01 | `scans` table is not explicitly enumerated by `SDD.md CMP-CP-03` but is required by `CMP-ORCH-01`'s API surface; documentation-hygiene update needed | CMP-CP-03 migration enumeration | Pre-implementation review of `CMP-CP-03` | RESOLVED | 2026-06-02 | **Ratified (Architect):** `DOC-DB.md §4.11`'s `scans` table (CMP-ORCH-01-derived) is canonical. SDD's CMP-CP-03 enumeration is documentation-incomplete, not contradictory — the derived-table listing stands as-is; no new schema designed (RULE-4: this ratifies the documented provisional). |
| CLAR-DB-02 | PostgreSQL RLS session-variable scheme (`app.org_id`, `app.user_id`, `app.role`) not pinned by SDD / DOC-DEPLOY-DECISIONS; proposed defaults need ratification | CMP-CP-01, CMP-CP-03 | Before Phase 11 | RESOLVED | 2026-06-03 | **SRE ratified + Security APPROVE-WITH-CONDITIONS 2026-06-03 (DECISION-PART2 §4/§5):** adopt the `DOC-DB §3.2` RLS scheme (`app.org_id`/`app.user_id`/`app.role`, `current_setting('…', true)`); missing GUC → NULL → zero rows (fail-closed). **Binding conditions (tracked):** (1) `SET LOCAL` only, never `SET`, + an integration test that a recycled pooled connection with no fresh `SET LOCAL` reads zero rows; (2) `BYPASSRLS` only on `scanipy_system`, request-path role distinct + cannot self-elevate to `app.role='system'`; (3) `scanipy_triage` non-BYPASSRLS + cannot widen its own grants. **Follow-up landed 2026-06-03 (PR #265, RULE-9 /security-analyst APPROVE) — conditions IMPLEMENTED:** `scanipy_system` (BYPASSRLS) + distinct NOBYPASSRLS `scanipy_app` request-path role, FORCE ROW LEVEL SECURITY on every RLS table, least-privilege grants (no `orgs` SELECT; append-only `provenance_records`), and the recycled-pooled-connection zero-rows + grant-surface integration tests (`test_cp03b`/`test_cp03c`). |
| CLAR-SARIF-01 | Public hosting URL for the Scanipy SARIF extension JSON Schema (`https://schemas.scanipy.io/sarif-extension/v1.0.0.json` proposed) | CMP-CI-01 SARIF schema-validation gate | Before first customer SARIF export GA | RESOLVED | 2026-06-03 | **SRE ratified 2026-06-03 (DECISION-PART2 §4):** vendor the SARIF-extension schema file locally now (check it into the CI gate's schema dir); keep `https://schemas.scanipy.io/sarif-extension/v1.0.0.json` as the schema `$id` (an identifier, not a fetch dependency). CI validates against the vendored copy → the gate is unblocked today; standing up the public URL is a pre-GA task (pin it to the byte-identical vendored content at GA). |
| CLAR-DET-01 | Persistence surface for the detector registry — `AC-DET-02b` mandates that manifest records (`id`, `cwes`, `languages`, `frameworks`, `engine`, `severity_default`, derived `determinism_partition`, per-language readiness) be persisted, but `DOC-DB.md` has no `detectors` table; manifests currently live as on-disk YAML loaded at process start and accepted DSL ASTs are persisted only via `spec_versions.spec_set` (jsonb). Should a first-class `detectors` table be added, or is the on-disk manifest + in-memory registry the source of truth? | CMP-DET-02, CMP-CP-03 | Before Phase 2 acceptance | RESOLVED | 2026-06-03 | **Architect ratified 2026-06-03 (DECISION-PART2 §2A):** on-disk version-controlled YAML manifests (source of truth) + in-memory `DetectorRegistry`; accepted DSL ASTs persist via `spec_versions.spec_set` (satisfies AC-DET-02b "persisted"). A first-class SQL `detectors` table is a purely additive future CLAR if dashboards need queryable rows. |
| CLAR-SCM-01 | Source location of the legacy GitHub connector against which `AC-SCM-02b` regression ("retry, rate-limit, tiered-star behavior byte-for-byte preserved") is measured. `SDD.md` line 71 and `WBS.md §5` presume `integrations/github/github.py` exists as legacy v2 code, but no such file is present in this v3.2 scaffold. Where is the byte-for-byte baseline captured (vendored copy / v2 git history / golden-fixture archive)? | CMP-SCM-02 | Before Phase 2 acceptance | RESOLVED | 2026-06-03 | **Decision 2026-06-03 (DECISION-PART2 Q5):** no v2 artifacts available — the legacy v2 GitHub connector cannot be supplied, so `AC-SCM-02b` (byte-for-byte regression) is **rescoped to its DOC-CMP-SCM-02 §3.5 shape contract** (`AC-SCM-02c`, independently dischargeable). Nothing faked (RULE-4). |
| CLAR-SCM-02 | Azure DevOps webhook (service-hook) signature scheme is under-specified: `DOC-CMP-SCM-03 §3.3` and `DOC-API §2.4` state the connector "pins HMAC-SHA-256" but name no signature *header* (`X-Vss-Activityid` is an activity id, not a signature; "body HMAC where applicable" is conditional). GitLab/Bitbucket headers are pinned (`X-Gitlab-Token`, `X-Hub-Signature`); ADO is not. Which header carries the ADO HMAC, and is the consumer secret the subscription `basicAuthPassword`? | CMP-SCM-03 (ADO `verify_webhook` only; GitLab/Bitbucket unaffected) | Before Phase 2 acceptance | RESOLVED | 2026-06-03 | **Architect + Security ratified 2026-06-03 (DECISION-PART2 §7 ARB — real bug found):** native Azure DevOps service-hooks emit **no per-delivery HMAC body signature and no signature header** — only HTTP Basic auth. The interim `verify_webhook` (requires `X-Hub-Signature-256`) would **reject every genuine ADO delivery** (`AC-SCM-03b` passes only vacuously). **Ruling:** verify ADO by **constant-time equality of the shared secret echoed in `basicAuthPassword`** (the GitLab `X-Gitlab-Token` pattern; `register_webhook` already sets it). **Tracked follow-up:** fix `verify_webhook` to read the Basic-auth credential + add a **positive-control** test. DOC wording corrected (Part-4 D-6, now unblocked). GitLab/Bitbucket unaffected. **Follow-up landed 2026-06-03 (PR #262, Security co-sign APPROVE):** `verify_webhook` rewritten to constant-time `basicAuthPassword` secret-equality (the interim `X-Hub-Signature-256` rejected every genuine ADO delivery); positive-control + body-independence tests added (mutation-verified). |
| CLAR-FND-01 | `DOC-DB.md §4.13` and `DOC-PROVENANCE.md §3` define `provenance_records` with two structurally different shapes (column-per-link vs `chain_payload jsonb`; `record_kind` 2-enum vs `record_type` 5-enum; `RSASSA_PSS_SHA_256` baseline vs `ecdsa-p256-sha256` baseline; `kms_key_arn`+`kms_key_version` vs `signature_key_id`+`signature_algorithm`+`signature_value`). `DOC-CMP-FND-03.md` Appendix C treats `DOC-PROVENANCE.md §3` as the primary contract for `CMP-FND-03` (aligns with SDD chain shape + `CLAR-DEPLOY-04` algorithm); `DOC-DB.md §4.13` must be reconciled before migration delivery. | CMP-FND-03 migration; CMP-CP-05 read path; `attestations.signed_chain_id` FK | Before CMP-FND-02 migration ships | RESOLVED | 2026-05-23 | Canonical shape = **column-per-link** (PROVENANCE §3) with DOC-DB's forced parts: PK `id` + `<table>(id)` FKs (schema-wide; `attestations.signed_chain_id` FK), `record_type` 5-enum (`chain`/`repartition`/`attestation`/`spec-acceptance`/`witness-update`; `chain`=per-finding), `scan_id` NOT NULL + `finding_id` NULL. Signature kept `RSASSA_PSS_SHA_256` (PROVENANCE/FND-03; ECDSA flip out of scope — would need CLAR-DEPLOY-04 amend). Canonical DDL now lives in **DOC-DB §4.13**; PROVENANCE §3 points to it. INV-1 via row-level CHECK (`origin` NOT NULL for chain/repartition); INV-2 `S_version`/`env_digest` NOT NULL on every row. |
| CLAR-DB-03 | The `snap_oracle_runs` table (one row per async differential-oracle run; both verdicts + `agreed` flag) is defined inline in `DOC-CMP-SNAP-04 §4.2` and referenced by `provenance_records.repartition_oracle_id`, but is **not mirrored into the canonical `DOC-DB §4`** schema reference. Surfaced by the CLAR-FND-01 reconciliation. | CMP-SNAP-04; CMP-FND-03 FK | Before CMP-SNAP-04 migration ships | RESOLVED | 2026-06-02 | **Ratified (Architect):** mirror `snap_oracle_runs` into `DOC-DB §4` as the canonical schema reference (the DDL is already `id`-PK aligned with `provenance_records.repartition_oracle_id` FK targets fixed in PR #207). No new shape introduced — this ratifies the documented provisional; the `DOC-DB §4` mirror is doc-hygiene to be carried with the CMP-SNAP-04 migration. |
| CLAR-DB-04 | Ownership of the `scanipy_triage` Postgres role lifecycle (CREATE/DROP): `DOC-CMP-CP-03 §8` quotes the GRANT/REVOKE fence but does not say who creates the role. CMP-CP-03 creates+drops it idempotently in the initial Alembic migration; the alternative is provisioning at the substrate layer (Terraform / CMP-DEPLOY). Surfaced by the PR #217 review (flagged as a RULE-4 inline scope decision). | CMP-CP-03; CMP-DEPLOY-05 | Before Phase 11 | RESOLVED | 2026-06-02 | **Ratified (Architect):** the `scanipy_triage` role is created/dropped idempotently **in the initial Alembic migration** (the documented provisional) — self-contained and CI-testable against a fresh PG, no substrate dependency for Phase-1. **Escape hatch retained:** this is SRE-adjacent; if SRE/CTO elect substrate-level (Terraform) role management at CMP-DEPLOY-05, relocating the CREATE/DROP there is a sanctioned follow-up (the GRANT/REVOKE fence in `DOC-CMP-CP-03 §8` is unaffected either way). |
| CLAR-CP-04-01 | Auth0 outage handling for the customer dashboard — should `CMP-CP-04` allow a degraded read-only mode (cached JWT validation past JWKS TTL, no writes) or remain fail-closed (503 Service Unavailable)? `DOC-CMP-CP-04.md §7` defaults to fail-closed. A read-only degraded mode would require careful JWT-revocation semantics and SRE + Security Analyst sign-off. | CMP-CP-04 | Before Stage A GA | RESOLVED | 2026-06-03 | **SRE ratified + Security co-sign 2026-06-03 (DECISION-PART2 §4/§5):** stay **fail-closed** — 503 + `Retry-After: 60`, no degraded read-only mode in v3.2. A cached-JWT read-only mode risks JWT-revocation bypass (unsatisfiable without an outage-resilient revocation channel). Blast radius is the dashboard auth surface only: scan/worker execution uses the `system` role (BYPASSRLS), so the deterministic core keeps running during an Auth0 outage. Kept open as a **post-GA enhancement** gated on a revocation-channel design. |
| CLAR-CP-05-01 | Oracle-pipeline reproduction-rate alarm thresholds — what numeric rate triggers a release-notes flag vs an OTel alarm? The two-pipeline contract requires "measured rate, no hard fail," but the alarm floor is not pinned. `DOC-CMP-CP-05.md §10` proposes alarm at < 99% rolling 7-day, investigate at < 95%, as a working assumption. | CMP-CP-05 oracle-pipeline tuning | Before Stage A GA | RESOLVED | 2026-06-03 | **SRE ratified 2026-06-03 (DECISION-PART2 §4, RR-CONFIRM) — interim:** OTel alarm when the rolling-7-day oracle reproduction rate < 99%; investigation ticket at < 95%; **never a hard CI fail** (two-pipeline contract). Config-driven; retune freely once an empirical oracle-reproduction baseline exists — rate-only, so a mis-set threshold cannot block a release or corrupt the core partition. |
| CLAR-CP-05-02 | Attestor CI cadence — does the core pipeline run on every push to `main` or only on commits that touch the existing `.github/workflows/attestor.yml` `paths:` filter? `AC-CP-05c` says "on every detector / engine / `Env` change"; the path filter encodes this but may miss `Env` changes that only touch base-image pins outside `workers/**` (e.g., in `infra/`). | CMP-CP-05 CI configuration; CMP-CI-01 Gate 3 | Before Stage A GA | RESOLVED | 2026-06-03 | **SRE ratified 2026-06-03 (DECISION-PART2 §4) — broaden (fail-closed):** run the core attestor pipeline on **every push to `main`** (drop the `paths:` restriction for `main`; keep `paths:` on `pull_request` for cost; add `workflow_dispatch`). A determinism gate whose trigger can't be proven to capture every `Env` input (tool-digest pins editable in `infra/` etc.) is effectively fail-open; a provably-complete `paths:` filter is a valid later optimization once that file-set is enumerated. |
| CLAR-CP-06-01 | Persistence surface for `CMP-CP-06` fidelity verdicts — should verdicts be persisted to a PostgreSQL `fidelity_results` table in addition to the `tests/results/cpg_fidelity/{language}/latest.json` artifact? JSON-only satisfies `AC-CP-06b` literally; a DB table enables historical trend analytics, per-customer readiness views in the dashboard, and per-(language, metric) audit. `DOC-DB.md §4` has no such table; `DOC-CMP-CP-06.md §10` proposes the schema if filed. | CMP-CP-06 persistence; downstream dashboard (`CMP-CP-04`) per-language readiness view | Before Stage B GA | RESOLVED | 2026-06-03 | **Architect ratified 2026-06-03 (DECISION-PART2 §2A, RR-CONFIRM):** keep **JSON-only** (`tests/results/cpg_fidelity/{language}/latest.json`) as the canonical persistence surface for v3.2 — AC-CP-06b is satisfied literally; `/stage-gate` + `/sync-wbs` read the JSON; CP-04 has no fidelity-trend view. A `fidelity_results` table is a pure additive, JSON-backfillable future CLAR if the product roadmap commits to historical/per-customer fidelity-trend dashboards. |
| CLAR-CP-06-02 | Should `CMP-CP-06` hard-enforce that the gate-evaluation `env_digest` matches the production worker image, or only record it? A gate run on a non-production `Env` is not authoritative for production claims. `DOC-CMP-CP-06.md §7` defaults to hard-enforce (fail closed). | CMP-CP-06 CI configuration | Before Stage A GA | RESOLVED | 2026-06-03 | **SRE ratified 2026-06-03 (DECISION-PART2 §4) — hard-enforce (fail-closed), bootstrap caveat:** the gate fails if its `env_digest` ≠ the pinned production worker image (a non-production `Env` verdict can't back a production INV-6 claim). **Bootstrap:** the production `env_digest` doesn't exist until CMP-SNAP-05 publishes the worker image, so until then the check is **record-and-warn**; flip to hard-fail the moment the production digest is pinned. |
| CLAR-CP-02-01 | `DOC-CMP-CP-02 §7` specifies a three-way decrypt-failure taxonomy: `TenantIsolationError` → 403 for `EncryptionContext`/CMK mismatch (KMS `InvalidCiphertextException`), `KMSKeyMissingError` → 500 for a deleted CMK (KMS `NotFoundException`), and a `ThrottlingException` retry path (exponential backoff, 3 attempts, jitter) that resolves to `503 KMS_UNAVAILABLE` on exhaustion. The current implementation has no boto3 `ClientError` introspection and no retry/backoff: it maps every opaque KMS exception to `TenantIsolationError` (fail-closed, Security-Analyst-confirmed not a security risk, but a contract deviation). Decision needed: add boto3 `ClientError` code introspection + `ThrottlingException` retry to honour the §7 taxonomy, or formally narrow the DOC §7 contract to the catch-all mapping. | CMP-CP-02 | Before Stage A go-live | RESOLVED | 2026-06-03 | **Security ratified 2026-06-03 (DECISION-PART2 §5, RR-COND — real bug found):** narrow DOC §7 toward **fail-closed**. **Mandatory code split (tracked follow-up):** the documented 500/503 paths do not execute against real boto3 today (a real `ClientError` is mislabeled 403 — masked by typed test fakes); classify `NotFoundException`→`KMSKeyMissingError` (operational, page SRE) **separately** from the tenant-isolation 403 alarm (else a deleted CMK pollutes the cross-tenant-attack forensic channel), and add a **botocore-`ClientError`-shaped** pos/neg test. SRE owns the throttle-retry/503 disposition. No fork leaks plaintext. **Follow-up landed 2026-06-03 (PR #263, RULE-9 /security-analyst APPROVE):** `decrypt_credential` now splits botocore `NotFoundException` → `KMSKeyMissingError` (500 `kms_key_missing`) out of the 403 cross-tenant catch-all; botocore-`ClientError`-shaped pos/neg tests added (mutation-verified non-vacuous); throttle/503 stays deferred to SRE. |
| CLAR-OWNER-02 | `TST-INV-4-SNAP-03` (the INV-4 falsifier for `CW-DETECT`, WBS §4.3 mandate) is deliberately excluded from the Phase-1 QA test-spec PR (#211): per RULE-9 the INV-4 safe-direction falsifier for `CMP-SNAP-03` is the **Security Analyst's** deliverable, not QA's. Recorded so `/sync-wbs` and `/stage-gate` do not read the omission as an AC-QA-02 gap. | CMP-SNAP-03 DONE (issue #15) | Before Stage A go-live | RESOLVED | 2026-05-24 | `TST-INV-4-SNAP-03` owned by the Security Analyst (RULE-9), tracked on issue #15; CMP-SNAP-03 is not DONE until that falsifier is green in addition to the QA-authored `TST-AC-SNAP-03*`. Phase-1 QA coverage (AC-QA-02) is complete modulo this delegated spec. |
| CLAR-CI-01 | CI's unit job runs `pytest tests/unit/ -m unit`, but the `TST-INV-*` / several `TST-AC-*` specs are marked `@pytest.mark.invariant` (not `unit`) and no gating job selects `-m invariant`, so invariant tests authored as "hard gate: every CI run" are **not actually collected by any required check**. Project-wide: affects already-merged CMP-FND-02 and CMP-FND-03 (#247), and likely CORE/CP/ORCH/DET/TRI/SNAP invariant specs. Surfaced by the CMP-FND-03 `claude-review` (PR #247, LOW). What is the canonical fix — add `invariant` to the unit selector (`-m "unit or invariant"`), add a dedicated invariant gate job, or dual-mark specs `@pytest.mark.unit @pytest.mark.invariant`? | RULE-3 CI enforcement for every component carrying `TST-INV-*` (FND-02/03, CORE-*, CP-*, ORCH-*, DET-*, TRI-*, SNAP-*) | Before Stage A go-live (RULE-3 must be CI-enforced, not local-only) | RESOLVED | 2026-06-01 | **Option (a):** the required `unit-tests` job selector becomes `-m "unit or invariant"` in `.github/workflows/ci.yml` (both source + scaffold branches); `.husky/pre-push` mirrors it as `(unit or invariant) and not integration and not falsifier and not empirical`. Rejected (b) a dedicated invariant job (extra required-check wiring, no benefit) and (c) dual-marking specs (40-file churn) — specs are single-primary-marked (invariant XOR unit), so the union selector is minimal and canonical. Validated: the no-DB unit invariant set runs 15 passed / 22 skipped (spec-first stubs) / 0 failed / 0 xpass; coverage only rises. **Residual (not over-claimed):** gates only the no-DB *unit* invariant tests on every PR; the 2 `integration`-marked invariant falsifiers (SNAP-04, need postgres) stay on the `integration-tests` job and the 1 `falsifier`+`invariant` test stays on Gate 2/3 — revisit the integration-job-as-gate question when SNAP-04 lands. Surfaced by PR #247 review; QA + SRE ratified. |
| CLAR-SNAP-01 | CW-DETECT file-type scope for config-driven reflection. `CW-DETECT` classifies files by source language and silently skips those it cannot classify (`file_lang is None` — `.xml`, `.properties`, …). But config files can wire runtime reflection / dynamic dispatch (Spring AOP via `applicationContext.xml` `<aop:config>`/`ProxyFactoryBean`; `META-INF/services`), so skipping them can yield a false `closed-world` verdict on a reflection-bearing project — an INV-4 false negative. `DOC-CMP-SNAP-03 §6.4` does **not** scope `.xml` out, and §7's safe-direction contract says any file whose reflection-freedom cannot be proven ⇒ `degraded`, never `closed-world`. Question: which non-source/config file types are in CW-DETECT's safe-direction scope, and the conservative default? Surfaced by PR #214 review (HIGH). | CMP-SNAP-03 (INV-4 safe direction); CMP-SNAP-04 | Before Stage A go-live | RESOLVED | 2026-05-24 | Security Analyst (RULE-9) ratified an **inert-allowlist** (stronger than the provisional language_mix default): a file that is NEITHER a scanned source language NOR in an explicit provably-inert extension allowlist (docs/images/data/lockfiles/VCS-meta) emits `structural-uncertainty` ⇒ `degraded`. Config formats (.xml/.yaml/.properties/.toml/.ini/.cfg/.json) + extensionless files are NOT inert (can wire Spring AOP / service-loaders / entry-points). Implemented in `cw_detect.py` (`_INERT_EXTENSIONS`) + zero-FN XML-AOP-in-Java regression test. Richer follow-up (Spring-XML sub-detector to *reclaim* closed-world) is v-next; the allowlist is the sound stop-gap. |
| CLAR-CORP-03 | Reflection corpus second-reviewer assignment for the `review_status: second-pass` dual-review protocol (DOC-CMP-CORP-REFL-01 §3.4, §7). The v0.1.0 corpus build delivers the deterministic mutation-injection pipeline + a single-pass sourced seed; scaling hand-curated categories to the `N ≥ 50` second-pass bar (AC-CORP-REFL-01a) requires a named second reviewer. Owner currently DEFERRED via CLAR-OWNER-01. | CMP-CORP-REFL-01 (v1.0.0 hand-curated bar) | Before Stage A go-live | OPEN | — | **Explicitly deferred 2026-06-03 (DECISION-PART2 Q4 / DECISION-PART3 D-6):** travels with the deferred corpus sourcing campaign; folds into the role-based ownership map (CLAR-OWNER-01) as a QA ⊕ Corpus-Curator pairing — the second reviewer must be **distinct from the corpus builder**. Stays OPEN pending a named reviewer. |
| CLAR-CORP-04 | Does the per-language `mutation-injected` count (≥ 20, CLAR-CORP-01) substitute for the per-category hand-curated `N ≥ 50` toward AC-CORP-REFL-01a, or are the two tracks scored separately? The v0.1.0 `corpus.lock` reports them separately (`sample_size` vs `hand_curated_second_pass`); the AC text is ambiguous on whether mutation items satisfy the per-category quota. | CMP-CORP-REFL-01 (AC-CORP-REFL-01a interpretation); CMP-SNAP-03 Gate 2 readiness claim | Before Stage A go-live | OPEN | — | — |
| CLAR-CORP-05 | Sandbox network/sourcing budget for bulk-sourcing real OSS reflection samples at `N ≥ 50` per category. The corpus-agent sandbox CAN reach github.com (verified), so real sourcing is feasible, but bulk hand-curation + dual review of ~800 hand-curated items exceeds a single agent-run. Needs a scoped sourcing campaign (which repos per category, license screening, dual-review staffing) — likely a multi-PR corpus effort. | CMP-CORP-REFL-01 (v1.0.0) | Before Stage A go-live | OPEN | — | **Explicitly deferred 2026-06-03 (DECISION-PART2 Q4):** the bulk OSS reflection-sourcing campaign is DEFERRED for v3.2 — the v0.1.0 scaffold stays honest (not gate-strength), CMP-SNAP-03 Gate-2 stays xfail. Revisit only to fund language coverage beyond Java+Python. |
| CLAR-CORP-06 | The v0.1.0 mutation pipeline's per-item `seed` does not diversify the generated source — the 20 mutation-injected items per language reduce to ~1–3 distinct source trees (seed differentiation is effectively a no-op in the generator). For genuine per-item coverage toward AC-CORP-REFL-01a the generator must vary structure / identifiers / call-context per seed. Surfaced by PR #219 (HIGH). | CMP-CORP-REFL-01 (v1.0.0 generator); CMP-SNAP-03 Gate-2 coverage claim | Before Stage A go-live | OPEN | — | Provisional: v0.1.0 ships as-is (explicitly NOT meeting AC-CORP-REFL-01a; Gate 2 is NOT declared passing on it — CMP-SNAP-03's `TST-AC-SNAP-03a` stays xfail). v1.0.0 must make `seed` produce structurally-distinct trees. |
| CLAR-CORP-17 | The refactor corpus (`CMP-CORP-REFAC-01`) v0.1.0 meets the AC-CORP-REFAC-01a *count* (50 seeds × 7 refactors = 350 pairs with `should-stay`/`should-flip` ground truth) but round-robins only **8 base templates** (4 Stage-A classes × 2 Stage-A languages), so `corpus.lock.distinct_topologies == 8`. Seeds differ only by identifier suffix, so the falsifier power for Algorithm 3 (`CMP-CORE-02`) is ~8, not 50: a fingerprint impl correct on one `injection/java` seed is correct on all of them. `DOC-CMP-CORP-REFAC-01 §4.1` names "Algorithm 2 / Semgrep + manual curation" as the seed source — real, structurally-distinct seeds are not yet sourced. Question: what is the v1.0.0 distinct-topology target (N structurally-distinct `(class, language, sink-topology)` cells), and is real-repo sourcing in budget (cf. CLAR-CORP-05 for the REFL analogue)? Filed by the `CMP-CORP-REFAC-01` v0.1.0 build. | CMP-CORP-REFAC-01 (v1.0.0 diversity bar); CMP-CORE-02 Algorithm-3 falsifier strength (TST-AC-CORE-02a/b) | Before Stage A go-live | OPEN | — | Provisional: v0.1.0 ships count-complete + topology-thin; `corpus.lock` records `distinct_topologies` honestly and README marks it NOT the v1.0.0 bar. TST-AC-CORE-02a/b may run against it but must not be read as a 50-independent-topology falsifier. v1.0.0 must expand to ≥ N distinct sourced topologies. |
| CLAR-CORP-14 | `CMP-CORP-CPG-go` minimum sample size `N` and per-category minimum counts for a statistically meaningful CPG-fidelity gate evaluation are not pinned by `SDD.md` (`DOC-CMP-CORP-CPG-go.md §10` leaves per-category minimums to a CLAR). The v0.1.0 corpus delivers 7 tool-derived, idiom-coverage items (one SOURCED, six SYNTHESIZED) — enough to exercise CP-06 mechanics and anchor the Stage-C `front-end-blocked` verdict (INV-6), but NOT a powered recall/precision estimate. Also: should the gate corpus require ≥ K real-world SOURCED items (vs synthesized idiom isolators), and what is the sourcing/license budget? | CMP-CORP-CPG-go (v1.0.0 gate-pass bar); CMP-CP-06 Go gate readiness | Before Stage C go-live | OPEN | — | Provisional: v0.1.0 ships as idiom-coverage (explicitly NOT the gate-pass bar); CP-06 verdict against today's Go front-end is `front-end-blocked` per CLAR-FE-02. v1.0.0 must pin `N`, per-category minimums, and a real-world SOURCED quota. |
| CLAR-CORP-18 | OWASP BenchmarkJava is licensed **GPL-2.0** across all released versions (verified on tag `1.2beta` and `master`), which is off the corpus vendor allow-list (MIT/Apache-2.0/BSD/MPL/Public-Domain; GPL/AGPL require explicit CTO approval). The v0.1.0 vuln corpus therefore ships OWASP items **fetch-on-demand** (pinned commit + path + `upstream_sha256` + CSV-verbatim ground truth, NOT vendored). Decision needed: grant CTO approval to vendor GPL-2.0 OWASP content into `tests/corpora/vuln/`, or keep the fetch-on-demand reference model. | CMP-CORP-VULN-01 (OWASP vendoring); downstream `TST-AC-CORE-01b` corpus availability | Before Stage A go-live | RESOLVED | 2026-06-03 | **CTO/legal decision 2026-06-03 (DECISION-PART2 Q2):** keep OWASP BenchmarkJava **fetch-on-demand** (pinned commit + `upstream_sha256`, NOT vendored) — deterministic ground truth with zero GPL-2.0 copyleft exposure; no vendoring approved. Gates only the OWASP portion of CLAR-CORP-19 (Juliet/BigVul unaffected). |
| CLAR-CORP-19 | Sandbox / sourcing budget to integrate the full held-out vuln corpus at scale: vendor the full OWASP Stage-A class coverage (pending CLAR-CORP-18), the real **NIST/SARD Juliet 1.3** suite (Public Domain, on allow-list), and the upstream **BigVul** CSV (MIT), then re-derive the deterministic held-out split over the real BigVul rows. The v0.1.0 build delivers the deterministic split + training-exclusion proof machinery + a small SOURCED OWASP seed + synthetic Juliet/BigVul seeds; bulk sourcing + per-(class,language) population at the `AC-CORP-VULN-01a/b` scale exceeds a single agent-run. | CMP-CORP-VULN-01 (v1.0.0 scale); CMP-CORE-01 `TST-AC-CORE-01b` empirical recall | Before Stage A go-live | OPEN | — | **Explicitly deferred 2026-06-03 (DECISION-PART2 Q4):** the full vuln-corpus sourcing campaign (real Juliet/BigVul scale-up; OWASP portion gated on CLAR-CORP-18 = fetch-on-demand) is DEFERRED for v3.2. The deterministic held-out split + never-train-on-held-out machinery is already built; only scale is deferred. |
| CLAR-CORP-16 | Per-category minimum item counts (`N`) for the PHP CPG-fidelity corpus are not pinned by `SDD.md` (`DOC-CMP-CORP-CPG-php §10` explicitly defers them here). The v0.1.0 build ships 1 synthesized item per dynamism axis (`variable_functions`, `call_user_func`, `magic_methods`, `eval`, `include_dynamic`, `callable_array`) + 1 `pure_php` control, with a documented rationale, and 0 SOURCED real-world / framework items. v1.0.0 needs: (a) the per-category `N`, and (b) the framework-coverage distribution (Laravel facades / Symfony DI / WordPress hooks / pure-PHP) proportional to real-world prevalence. Also pending: the PHP toolchain **image digest** pin (TBD until `CMP-SNAP-05` publishes the PHP worker image — `methodology.md §1`). | CMP-CORP-CPG-php (v1.0.0 bar; `AC-CORP-CPG-phpa/b` full); CMP-CP-06 PHP gate evaluation | Before Stage D readiness | OPEN | — | Provisional: v0.1.0 ships as a versioned, methodology-backed seed (1 item/axis) — explicitly NOT meeting the v1.0.0 `AC-CORP-CPG-php*` bar. `CLAR-FE-01` (DEFERRED) gates the PHP front-end verdict (`front-end-blocked` expected, INV-6), not this corpus build. |
| CLAR-CORP-15 | Ruby CPG-fidelity corpus per-category minimum sample size `N` is unspecified in SDD (`DOC §10`) — blocks the v1.0.0 AC bar for `CMP-CORP-CPG-ruby`. The v0.1.0 scaffold ships one+ item per DOC-enumerated idiom and documents its distribution rationale rather than asserting an unpinned `N`. Referenced by `tests/corpora/cpg_fidelity/ruby/{README,methodology}.md`. Surfaced by PR #230. | CMP-CORP-CPG-ruby (v1.0.0 sample-size bar) | Before Stage D go-live | OPEN | — | Provisional: v0.1.0 ships as a front-end-blocked Stage-D scaffold (oracle-passthrough only; NOT claiming the v1.0.0 AC). `N` to be pinned before any Ruby CMP-CP-06 gate-pass claim. |
| CLAR-CORP-12 | `DOC-CMP-CORP-CPG-js §3.4` mandates **Jelly 1.4** (+ `tsc --noEmit --declaration` for TS type-informed edges) as the call-graph / PDG ground-truth tool. The v0.1.0 corpus build ships AST via the production tool (`@typescript-eslint/typescript-estree` 6.18.0) but derives **call-graph + PDG** from a documented *intraprocedural* resolver (`pipeline/extract_ground_truth.mjs`), which conservatively tags higher-order indirection + TS type-informed dispatch as `dynamic` (excluded from metrics). Adopting Jelly/tsc requires a pinned toolchain (Jelly is a separate analyzer with its own runtime) — out of one-agent-run scope. Until resolved, JS/TS call-edge + PDG gate numbers on this corpus are NOT authoritative and `CMP-CP-06` must NOT declare the JS/TS gate passing on v0.1.0 ground truth. | CMP-CORP-CPG-js (v1.0.0 ground truth); CMP-CP-06 JS/TS gate verdict | Before Stage B GA | OPEN | — | Provisional: v0.1.0 ships with the intraprocedural resolver (AST is the production tool); call-edge/PDG ground truth is explicitly NON-authoritative until Jelly 1.4 + tsc are adopted. |
| CLAR-CORP-13 | Minimum program count N (and per-surface / per-module-system / per-construct-tag quotas) for a statistically-meaningful JS/TS CPG-fidelity gate set. `DOC-CMP-CORP-CPG-js` mandates tag + module-system + dual-surface coverage but pins no minimum program count. The v0.1.0 build ships a **9-program coverage skeleton** (7 js + 2 ts) that covers all §4.3 tags + module systems but is not a gate-strength sample; reaching gate strength needs a scoped real-OSS sourcing campaign (parallels CLAR-CORP-05 for reflection). | CMP-CORP-CPG-js (v1.0.0); CMP-CP-06 JS/TS gate authority | Before Stage B GA | OPEN | — | — |
| CLAR-CORP-11 | Python CPG-fidelity ground-truth toolchain. `DOC-CMP-CORP-CPG-python §3.4` pins scalpel 1.0.4 (CFG/SDG) + Pyan3 1.2.0 + Pyre 0.0.301 on cpython 3.10 for the v1.0.0 ground-truth. None are vendored in the corpus-agent sandbox and the host interpreter is 3.12; installing Pyre offline reliably is non-trivial. The v0.1.0 `CMP-CORP-CPG-python` build runs the AST step on the host interpreter and replaces the scalpel/Pyan3/Pyre CFG/callgraph/PDG steps with an in-repo, zero-dependency extractor (`pipeline/extract_ground_truth.py`); call-graph ground truth is the statically name-resolvable subset, with unresolved sites tagged `dynamic` and excluded from precision/recall per §3.4 step 3. v1.0.0 must either (a) provision the pinned toolchain via the DOC-DEPLOY image registry and re-extract under cpython 3.10, bumping `corpus_version`, or (b) ratify the in-repo extractor as the canonical ground-truth method and amend `DOC-CMP-CORP-CPG-python §3.4`. The `CMP-CP-06` Python gate verdict (parse/precision/recall/PDG) MUST NOT be declared authoritative on the v0.1.0 extractor-derived ground truth until this is resolved. | CMP-CORP-CPG-python (v1.0.0); CMP-CP-06 Python gate authority | Before Stage A go-live | OPEN | — | Provisional: v0.1.0 ships honestly as a scaffold + reproducible `corpus.lock`; does NOT assert the CMP-CP-06 Python verdict is authoritative. |
| CLAR-CORP-07-java-tooling | The DOC-pinned Java CPG ground-truth toolchain (`DOC-CMP-CORP-CPG-java §3.4`: Soot 4.4.1 + WALA 1.6.5) is unavailable in the corpus-agent sandbox (`soot`/`wala` not installed). The v0.1.0 corpus therefore derives AST-detail/CFG/call-graph/PDG ground truth **by inspection** of 11 tiny hand-authored programs (parse-success IS javac-verified). This is sound for the tiny programs but is NOT the pinned-tool extraction; `CMP-CP-06` MUST NOT report `GATE-PASS` for Java on v0.1.0. Needs a build environment with Soot/WALA (or sha256-pinned object-store artifacts) to re-extract for v1.0.0. | CMP-CORP-CPG-java (v1.0.0 ground truth); CMP-CP-06 Java gate sufficiency | Before Stage A go-live | OPEN | — | Provisional: v0.1.0 ships SYNTHESIZED, by-inspection ground truth; v1.0.0 must re-extract under pinned Soot/WALA. |
| CLAR-CORP-08-java-jdk | JDK baseline drift for the Java CPG corpus: `DOC §3.2`/`§3.4` pin JDK 17; the sandbox has only JDK 21. v0.1.0 compiles every program at `-source 17 -target 17` (parse-success holds) and records `extraction_tools.jdk: openjdk-21.0.10`. Pattern-matching `switch` (a 17 preview, finalized 21) was avoided in `0010-recent-language` so the program stays 17-compilable. Confirm the pinned JDK for v1.0.0 extraction and whether 21 is acceptable. | CMP-CORP-CPG-java; CMP-CP-06 Java gate | Before Stage A go-live | OPEN | — | Provisional: programs verified at `-source 17`; jdk pinned at 21 in extraction.yaml. |
| CLAR-CORP-09-java-sourcing | The per-language minimum program count `N` for CPG-fidelity corpora is unpinned (CLAR-CORP-01 covered only the reflection corpus), and no real-OSS SOURCED-program campaign is scoped. v0.1.0 ships 11 SYNTHESIZED programs (one per `DOC §4.3` construct tag, all 11 covered) and **zero** SOURCED real-repo programs. A scoped sourcing campaign (which Apache/MIT/BSD repos, license screening, sha256-pinned slices, second-pass review) is needed for the v1.0.0 gate-ready bar — likely shared across all six `CMP-CORP-CPG-{lang}` corpora and with CLAR-CORP-05. | CMP-CORP-CPG-java (v1.0.0 coverage bar); CMP-CP-06 Java gate sufficiency | Before Stage A go-live | OPEN | — | Provisional: v0.1.0 = 11 synthesized programs; not a per-`N` or SOURCED claim. |
| CLAR-CORP-10-java-generated-balance | DOC §3.3 requires ≥ 10% of programs to carry a generated-code / hard-to-parse tag. v0.1.0 has 1 `generated-code` program of 11 = 9% (a documented WARN from `build_lock.py`, not a hard refuse). Confirm the threshold denominator and whether the v1.0.0 bar flips this WARN to a hard refuse (and the target count). | CMP-CORP-CPG-java (v1.0.0 balance bar) | Before Stage A go-live | OPEN | — | Provisional: v0.1.0 ships at 9% with a documented WARN; v1.0.0 adds generated-code programs to clear ≥ 10%. |
| CLAR-DET-02 | `detectors.registry.closure_check` performs a narrower engine/spec *shape* re-validation than `DOC-CMP-DET-02 §3.3` items 3-4 imply: it confirms the frozen `Detector` is internally consistent (core engine carries a non-empty core-engine spec; oracle engine carries an existing query file, no spec) but does NOT re-run the full distributivity-closure decision procedure, relying on CMP-DET-01's registration-time `parse_spec` check for DSL membership (INV-4). Is the narrower defense-in-depth shape check sufficient, or must `closure_check` re-run the full §3.3 closure decision itself? Surfaced by PR #235 claude-review. | CMP-DET-02 (`closure_check` scope); CMP-CORE-01 (consumer assumption) | Before Stage A go-live | RESOLVED | 2026-06-03 | **Architect ratified 2026-06-03 (DECISION-PART2 §2A) — APPROVE-WITH-CONDITIONS (Security, RULE-9):** the narrower shape check is accepted as defense-in-depth; CMP-DET-01 `parse_spec` owns the authoritative INV-4 distributivity/closure decision. **Binding condition (tracked follow-up):** Security found `parse_spec` is on every *production* path but NOT the public `register()` API path (shape-check-only), so a caller-built `Spec` can carry unparsed escape-hatch pattern content past `register()` — a one-sided INV-4 FN. Fix: pin `parse_spec` on the `register()` path (or make `Spec` parser-only) + add the `TST-INV-4-DET-01` `register()`-path negative test. The `Clause` grammar has no non-distributive node, so the residual surface is unparsed pattern content only. **Follow-up landed 2026-06-03 (PR #264, RULE-9 /security-analyst APPROVE) — binding condition DISCHARGED:** `revalidate_spec` (E-DSL-001..004 + 008) now runs on the public `register()` path and `load_manifests`; `TST-INV-4-DET-01` register()-path negative test added (pre-fix bypass reproduced red→green). |
| CLAR-DET-03 | Single-spec-per-detector design: a `detectors.registry.Detector` carries exactly one parsed `Spec` (`_load_core_spec` parses the first `specs/*.dsl.yaml`), but `DOC-CMP-DET-02 §3.3` is ambiguous on whether a detector may bind multiple specs. Confirm one-spec-per-detector for v3.2, or must a `Detector` support a spec list? Surfaced by PR #235 claude-review. | CMP-DET-02 (`Detector` shape); CMP-DET-03 (scaffolding); CMP-ORCH-03 (consumer) | Before Stage A go-live | RESOLVED | 2026-06-02 | **Ratified (Architect):** one spec per `Detector` for v3.2 (the shipped `_load_core_spec` shape). A class needing multiple specs is modelled as **multiple detector rows**, not a spec list on one detector — this keeps the `determinism_partition` / engine binding 1:1 and the DSL closure check (CMP-DET-01 `parse_spec`) per-spec. No `Detector` shape change (RULE-4: ratifies the documented provisional). Revisit only if a future class genuinely requires a single detector bound to a spec list. |
| CLAR-CP-01-01-inv2-emitter | `TST-INV-2-CP-01` is marked `[FORTHCOMING]` and absent from Phase-1 specs; WBS §14's INV-2 emitter table does not list CMP-CP-01. CP-01 is a routing/authz guard that does not itself emit a `Finding` (so it stamps no `S_version`/`env_digest`), but the scan-submission entry point it fronts carries `S_version` forward (DOC-CMP-CP-01 §3.1 `validate_s_version`, currently out of scope). Question: is CMP-CP-01 an INV-2 emitter requiring `TST-INV-2-CP-01`, or is the INV-2 obligation discharged downstream (CMP-ORCH-03 / CMP-FND-01..03)? Filed during CMP-CP-01 implementation (PR #236); also tracked operationally as issue #242. | CMP-CP-01 (TST-INV-2 obligation); QA spec authoring | Before Stage A go-live | RESOLVED | 2026-06-03 | **Architect ratified 2026-06-03 (DECISION-PART2 §2A):** CP-01 is a non-emitting routing/authz guard — it constructs no `Finding`, stamps no `S_version`/`env_digest`, and is **not** an INV-2 emitter; the obligation is discharged downstream (CMP-ORCH-03 / CMP-FND-01..03). The phantom `TST-INV-2-CP-01 [FORTHCOMING]` is retired (done in PR #259 D-3); `validate_s_version` keeps its `AC-CP-01a` unknown-`S_version`→422 negative test (an input check, not an emitter test). |
| CLAR-SNAP-02 | `DOC-CMP-SNAP-01 §3.3/§4.4` specify a `queued→snapshotting→ready` state machine with **nullable** `precondition_status` plus `snapshot_digest` and `completed_at` columns on the `snapshots` table; none of these exist in the shipped CP-03 schema (`db/migrations/versions/20260524_0001_initial_tenancy_tables.py` lines 174-208): there `precondition_status` is **NOT NULL** with a CHECK over `('closed-world','degraded','full-reparse')`, and there is no `state` / `snapshot_digest` / `completed_at` column. CMP-SNAP-01 was built to its 4 ACs against the **real shipped schema** — a single-insert `SnapshotRow` made once the precondition verdict + the five artifact URIs are known (the simulated CMP-SNAP-05 worker-completion seam `record_completion`), with no async state surface. Which contract is canonical, `DOC-CMP-SNAP-01` or `DOC-DB §4.7`? Surfaced during CMP-SNAP-01 implementation (issue #16). | CMP-SNAP-01 status/read surface (`GET /snapshots/{id}` state); CMP-SNAP-05 `report_status` callback (state machine + `snapshot_digest` persistence) | Before CMP-SNAP-05 | RESOLVED | 2026-06-03 | **Architect/CTO arbitrated 2026-06-03 (DECISION-PART2 §2 ARB):** the **shipped schema (`DOC-DB §4.7`) is canonical**; the `DOC-CMP-SNAP-01 §3.3/§4.4` state machine is the document to correct (lowest SoT authority, and the NOT-NULL `precondition_status` CHECK mechanically forbids a `queued`-state insert). No AC requires a `state` column; `GET /snapshots/{id}/status` is served by row-existence. **Unblocks CMP-SNAP-05 design.** The SNAP-05 `report_status` callback (state machine + `snapshot_digest` persistence) is a **separate downstream decision** (off-row tracking vs a deliberate CP-03 amendment), not this conflict. |
| CLAR-MIGRATION-02 | Where are the legacy `tarslip.yaml` taint definitions and the C/C++ memory-safety CodeQL queries (`*.ql`/`*.qll`) that `CMP-DET-03` must migrate, and what Stage-A repo state + canonical witness define the historical CVE-2025-61765 finding for the `AC-DET-03b` regression? Both legacy artifacts are **absent from the repo**, and the regression requires running a real Stage-A scan via `CMP-CORE-01`/`CMP-ORCH-01` (not yet built). Surfaced during the CMP-DET-03 scaffold (issue #14). | CMP-DET-03 (`AC-DET-03b` migration + CVE reproduction); ties to CMP-ORCH-01 (`AC-ORCH-01c`) | After CMP-CORE-01 + CMP-ORCH-01 land | RESOLVED | 2026-06-03 | **Decision 2026-06-03 (DECISION-PART2 Q5):** the legacy artifacts (`tarslip.yaml`, C/C++ CodeQL queries, CVE-2025-61765 baseline) are confirmed **unavailable** — `AC-DET-03b` (migration + CVE reproduction) is **rescoped/deferred** (full reproduction deferred, not faked — RULE-4). Provisional (unchanged): CMP-DET-03 ships the **scaffold** (`AC-DET-03a` — ten class dirs register via `tools/scaffold_class.py`) only; the `tarslip.yaml`/CodeQL migration and the CVE-2025-61765 reproduction (`AC-DET-03b`) are DEFERRED pending (a) the legacy artifacts being located/supplied and (b) CMP-CORE-01/ORCH existing to run the Stage-A scan. No migration was fabricated (RULE-4). *(Renumbered from a duplicate `CLAR-MIGRATION-01` id — the v2→v3.2 data-migration sense keeps `CLAR-MIGRATION-01` in the row above; see DECISION-PART4-register-defects-2026-06-03 D-1.)* |
| CLAR-DB-05 | Exact persistence pattern for per-customer revalidation/quarantine state (CMP-TRI-03): (a) a customer-scope shadow `spec_versions` row (`scope='customer'`, referencing the global parent) vs (b) a dedicated `spec_revalidations` table keyed by `(org_id, spec_version_id)` carrying the two log-space e-process wealths. Both preserve INV-2 (append-only) + INV-3 (pinned). Surfaced during CMP-TRI-03 implementation (issue #31). **Note:** `DOC-CMP-TRI-03 §10` mis-numbers this as "CLAR-DB-02" — that id is already taken by the RLS `app.org_id` scheme; this row (CLAR-DB-05) is the canonical entry. | CMP-TRI-03 revalidation/quarantine persistence; CMP-ORCH-01 scan-time `S` composition (excludes quarantined specs) | Before Phase 8 customer-enablement | RESOLVED | 2026-06-02 | **Ratified (Architect):** option **(b)** — a dedicated `spec_revalidations` table keyed by `(org_id, spec_version_id)` carrying the two log-space e-process wealths — is the canonical production persistence pattern (the shipped CMP-TRI-03 `CustomerEProcessState` store is already (b)-shaped; ratifying it avoids a re-model). Rationale: (b) keeps per-customer revalidation/quarantine state out of the global `spec_versions` lineage (cleaner INV-2 append-only semantics; no shadow-row ambiguity in scan-time `S` composition). The production **migration remains to be written** under the normal CMP-CP-03/schema track — this resolves the *design* (a-vs-b), not the migration delivery; ships against the in-memory store until then (RULE-4: no migration fabricated). Supersedes `DOC-CMP-TRI-03 §10`'s mis-numbered "CLAR-DB-02" reference. |
| CLAR-TRI-01 | update_e_process operates on the bounded [0,1] outcome (DOC §3 AdjudicatedFinding.label projected tp=1.0/fp=0.0); finding_id traceability lives on `proposed_specs.e_process_state` at the evaluate/caller layer, not threaded into the O(1) statistical primitive. Deviation from DOC §3 `observation: AdjudicatedFinding` param type. | CMP-TRI-02 | resolved-with-PR-255 | RESOLVED | 2026-06-02 | **Resolved (PR #255, merged 2026-06-02):** keep the float primitive; the adjudication→outcome projection (`AdjudicatedFinding.label` → tp=1.0/fp=0.0) is the caller's responsibility — in effect at `services/triage/spec_inference.py:185-211`. (Status flipped per DECISION-PART4-register-defects-2026-06-03 D-2.) |

---
## 18. OUT-OF-SCOPE register

`SDD.md` §12 enumerates the v3 out-of-scope items. The WBS records them here so derived tasks that drift toward them are deflected.

| Id | Item | Source |
|---|---|---|
| OOS-CI-AGENT-01 | CI-agent / on-prem runner | SDD §12 |
| OOS-CONTAINER-SCAN-01 | Container-image scanning | SDD §12 |
| OOS-BINARY-01 | Binary-only analysis | SDD §12 |
| OOS-IDE-01 | IDE plugin | SDD §12 |
| OOS-CC-01 | C/C++ memory-safety port to core (remains oracle-passthrough through v3.2) | SDD §11 |
| OOS-LLM-DET-01 | Any LLM influence on `deterministic-core` findings other than via accepted version-pinned `S` | SDD INV-3 |
| OOS-ENV-INDEP-01 | Environment-independent determinism (reproducibility is **scoped to fixed `Env`**) | PLAN §"Central correction" |

If a derived task implies any of the above, emit an `OOS-*` reference and **do not** schedule it under v3.2.

---

## 19. Risk mitigation matrix

`SDD.md` §13 risks are matched to mitigation work packages here. Every risk must have a mitigation task that is in-flight or done by Stage A go-live.

| Risk | Statement | Mitigation owner(s) | Notes |
|---|---|---|---|
| R-1 | Undecidable preconditions leak — `CW-DETECT` FN ships wrong `deterministic-core` label | CMP-SNAP-04 (differential oracle) | Must be scheduled in the **same stage** as CMP-SNAP-02, not later. |
| R-2 | Front-end fidelity dominates schedule — weak front-ends silently depress AC-CORE-01b | CMP-CP-06 (gate) + T-STAGE-{C,D}-FE-01 | Gate precedes every Algorithm 2 benchmark. |
| R-3 | Spec gate misuse — e-process without martingale unit test invalidates the guarantee | TST-AC-TRI-02b as hard production-enablement gate | Gate is wired by CMP-CI-01. |
| R-4 | Determinism regression invisible to same-path re-run | CMP-SNAP-04 + CMP-CP-05 partition split | Both required, neither sufficient alone. |
| R-5 | Detector-catalog chicken-and-egg — stubbed classes block adoption | Stage A front-loads `{injection, path-traversal, ssrf, deserialization}`; other six are post-Stage-A increments | Stage A is the minimum shippable set. |

---

## 20. Dependency DAG summary

Adjacency list of `CMP-*` `Depends-On` edges, derived from `SDD.md`. Reading: `A → [B, C]` means A depends on B and C; B and C must reach `DONE` before A becomes `READY` (subject to per-language staging in §13).

```
CMP-DEPLOY-01      → []
CMP-DEPLOY-02      → [CMP-DEPLOY-01]
CMP-DEPLOY-03      → [CMP-DEPLOY-01]
CMP-DEPLOY-04      → [CMP-DEPLOY-01, CMP-DEPLOY-02]
CMP-DEPLOY-05      → [CMP-DEPLOY-01, CMP-CP-01, CMP-CP-03]

CMP-SCM-01         → []                      (CMP-CP-02 mockable until available)
CMP-SCM-05         → []
CMP-SCM-02         → [CMP-SCM-01]
CMP-SCM-03         → [CMP-SCM-01, CMP-SCM-05]

CMP-DET-01         → []
CMP-DET-02         → [CMP-DET-01]
CMP-DET-03         → [CMP-DET-02]            (per class)

CMP-SNAP-03        → []
CMP-SNAP-01        → [CMP-SCM-01, CMP-FND-03]
CMP-SNAP-05        → [CMP-SNAP-01, CMP-DEPLOY-02]
CMP-SNAP-02        → [CMP-SNAP-01, CMP-SNAP-03]
CMP-SNAP-04        → [CMP-SNAP-03, CMP-FND-02]

CMP-CORE-03        → []
CMP-CORE-01        → [CMP-DET-01, CMP-SNAP-02, CMP-CORE-03]
CMP-CORE-02        → [CMP-CORE-01, CMP-CORE-03]

CMP-FND-02         → [CMP-CP-03]
CMP-FND-01         → [CMP-CORE-02, CMP-CORE-03]
CMP-FND-03         → [CMP-FND-02]

CMP-ORCH-01        → [CMP-SNAP-01, CMP-FND-01, CMP-CP-01]
CMP-ORCH-02        → [CMP-ORCH-01]
CMP-ORCH-03        → [CMP-CORE-01, CMP-DET-02, CMP-FND-01]

CMP-TRI-01         → [CMP-FND-02]
CMP-TRI-02         → [CMP-DET-02, CMP-FND-02]
CMP-TRI-03         → [CMP-TRI-02]

CMP-CP-02          → []
CMP-CP-03          → []
CMP-CP-01          → [CMP-CP-03]
CMP-CP-04          → [CMP-CP-01, CMP-FND-03]
CMP-CP-05          → [CMP-ORCH-01, CMP-FND-03]
CMP-CP-06          → [CMP-SNAP-05]

CMP-CORP-REFL-01   → []
CMP-CORP-CPG-*     → []
CMP-CORP-CANARY-01 → [CMP-SCM-02, CMP-SCM-03]
CMP-CORP-REFAC-01  → []
CMP-CORP-VULN-01   → []

CMP-CI-01          → [CMP-DEPLOY-04]

CMP-RES-01         → [CMP-SCM-02, CMP-TRI-02]
```

### 20.1 Cycle note

There is one apparent cycle to be aware of when reading the DAG:

```
CMP-SNAP-01 → CMP-FND-03 → CMP-FND-02 → CMP-CP-03
```

`CMP-SNAP-01` depends on `CMP-FND-03` only insofar as Snapshot persistence emits a provenance row. Implementation order: stand up `CMP-CP-03`, `CMP-FND-02`, `CMP-FND-03` first; then `CMP-SNAP-01`. The dependency edge is forward in the DAG; there is no actual cycle.

### 20.2 Eligible-to-start at project kickoff (no unmet deps)

```
CMP-DEPLOY-01, CMP-SCM-01, CMP-SCM-05, CMP-DET-01,
CMP-SNAP-03, CMP-CORE-03, CMP-CP-02, CMP-CP-03,
CMP-CORP-REFL-01, CMP-CORP-CPG-*, CMP-CORP-REFAC-01, CMP-CORP-VULN-01
```

These 12 work packages plus Phase 0 (Docs) and Phase 1 (QA / test specs) are the parallelisable wave-1 work.

---

## 21. Definition of Done — v3.2 baseline (SDD §14)

The v3.2 baseline is complete iff **every** item below is checked.

- [ ] Phase 0 — Every `CMP-*` has a `DOC-CMP-*`; every §3.2 cross-cutting reference exists.
- [ ] Phase 1 — Every `AC-*` in `SDD.md` has a `TST-AC-*` artifact; every `INV-*` has at least one explicit `TST-INV-*` per emitting component.
- [ ] Stage A — Every `CMP-*` with `Staging: Stage A` has every AC green for Java + Python.
- [ ] CMP-CP-05 — Reports byte-identical core-partition SARIF over the canary corpus on every detector / engine / `Env` change.
- [ ] CMP-SNAP-04 — Demonstrably re-partitions on a seeded `CW-DETECT` false negative; labeling-correction window has a contractual SLA value.
- [ ] CMP-TRI-02 — Passes the adversarial unbounded-continuation test with `α`-bound respected; the martingale-property unit test is green; pre-customer-enablement gate enforced.
- [ ] CMP-CI-01 — The four named gates (`AC-DET-01a`, `AC-SNAP-03a`, `AC-CP-05c`, `AC-TRI-02b`) are continuously enforced as hard pipeline failures.
- [ ] CMP-DEPLOY-01..05 — Every substrate decision is recorded, the worker baseline image is signed and registered as `env_digest`, observability surfaces are populated, tenant-isolation backstop is verified.
- [ ] Per-language staging — Stage A through Stage D status table is published, driven by AC pass/fail rather than by prose ("honest-labeling ledger as a living status table" per `SDD.md` §14).
- [ ] `CLARIFICATION-NEEDED` register — Every item is either `RESOLVED` with a recorded decision or has been re-deferred to a post-v3.2 milestone with explicit reasoning.
- [ ] `OUT-OF-SCOPE` register — No work has drifted in from this list.
- [ ] All five risks `R-1..R-5` — Each has a mitigation that is `DONE` (R-1, R-2, R-3, R-4) or `LIVE AS POLICY` (R-5: Stage A front-loaded, six classes incremental).

---

## 22. Reading guide — for a code-writing agent that has never seen this WBS

A code-writing agent assigned a work package `CMP-X` should:

1. Read `DOC-CMP-X` (Phase 0 output) as its primary specification.
2. Read the relevant §3.2 cross-cutting references (`DOC-INV`, `DOC-GLOSSARY`, `DOC-API`, `DOC-DB`, `DOC-SARIF`, `DOC-DSL`, `DOC-PROVENANCE`, `DOC-ALGS`, `DOC-PARTITION`, `DOC-STAGING`, `DOC-RUNBOOK`).
3. Read the `TST-AC-X-*` set (Phase 1 output) as the "done" contract.
4. Read every `INV-*` that `DOC-CMP-X` lists in its "Invariants touched" section, plus the corresponding `TST-INV-*` per emitting component.
5. Confirm that every `Depends-On` for `CMP-X` is `DONE`, with `BLOCKED` / `STAGE-GATED` as failure modes.
6. Implement the work package.
7. Run every `TST-AC-*` and `TST-INV-*` attached to the work package. The package is `DONE` only when every one is green.
8. If anything required for completion is unspecified, file a `CLAR-*` entry against §17 of this WBS rather than designing it inline. Do not invent scope (`SDD.md` §0 rule 6).
