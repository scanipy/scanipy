# Scanipy v3.2 — Agent Context

> **Read this file first.** It is derivative of PLAN.md, SDD.md, and WBS.md.
> When this file conflicts with any of those three, the upstream document wins.
> Correct this file, never the upstream.

---

## 1. Source-of-truth hierarchy

```
PLAN.md   (architecture)        ── highest authority; wins all conflicts
SDD.md    (component specs)     ── derived from PLAN; defines CMP-* and AC-*
WBS.md    (work breakdown)      ── derived from SDD; defines TST-AC-*, DAG, phases
CLAUDE.md (this file)           ── derived from all three; never overrides them
DOC-CMP-* (per-component docs)  ── implementation contract for code-writing agents
```

Allowed writes to `WBS.md`: §17 CLAR-* appends, §18 OOS-* appends, status-code flips (§1.2). Never edit `PLAN.md` or `SDD.md` — file a `CLAR-*` instead.

---

## 2. Project identity

**Scanipy v3.2** is a multi-tenant SaaS SAST platform defined by:

```
F : (source, S, Policy ; Env) → FindingSet
```

`source` = codebase @ commit · `S` = version-pinned accepted spec set · `Env` = pinned analysis environment (container image digest + tool digests). Three load-bearing properties:

- **(a) Reproducibility** — `deterministic-core` findings are a deterministic function of `(source, S, Env)` for fixed env, `LLM_TRIAGE=off`.
- **(b) Incremental computability** — rebuild cost ∝ semantic delta of commit (Algorithm 1).
- **(c) Machine-checkable provenance** — every finding carries a signed audit chain.

The platform builds a single CPG per commit, runs IFDS/IDE over it for core classes, and routes everything else through oracle adapters (Semgrep, CodeQL). The LLM is **never on the deterministic detection path** (INV-3).

---

## 3. Architectural invariants

| ID | Statement | Owner(s) |
|---|---|---|
| **INV-1** | Every finding carries `origin ∈ {deterministic-core, oracle-passthrough}`. | CMP-ORCH-03, CMP-FND-01..03, CMP-SNAP-04, CMP-TRI-01 |
| **INV-2** | Every finding + provenance record carries `S_version` and `env_digest`. | CMP-SNAP-01, CMP-ORCH-03, CMP-FND-01..03, CMP-TRI-02 |
| **INV-3** | No LLM output influences a `deterministic-core` finding except via an accepted version-pinned spec in `S`. Triage never deletes findings. | CMP-TRI-01..03, CMP-CP-05 |
| **INV-4** | Undecidable-property approximations must be one-sided (safe direction), named, and falsifier-backed. | CMP-SNAP-03 (`CW-DETECT`), CMP-DET-01 (DSL closure) |
| **INV-5** | Conditional artifacts carry their own conditional annotation in the persisted record. | CMP-CORE-02, CMP-CORE-03, CMP-FND-03 |
| **INV-6** | Algorithm 2 recall claims are valid only for CPG-fidelity-gate-passing `(class, language)` pairs. Front-end-blocked pairs are reported as blocked, never as recall failures. | CMP-CP-06, CMP-CORE-01 |

See `.claude/rules/01-invariants.md` for examples and counter-examples.

---

## 4. Glossary (core terms)

| Term | Meaning |
|---|---|
| `S` / `S_version` | Accepted version-pinned spec set and its semver. |
| `Env` / `env_digest` | Pinned analysis environment; its digest = container image digest. |
| `origin` | `deterministic-core` or `oracle-passthrough` (INV-1). |
| `determinism_partition` | Same partition, recorded at detector level. |
| `cpg_order_hash` | Hash of canonical CPG order; canonical **iff** `fingerprint_class = strong`. |
| `slice_fingerprint` | Refactor-stable fingerprint of a backward interprocedural slice. |
| `fingerprint_class` | `strong` (canonical) or `weak` (witness-edge fallback). |
| `precondition-status` | `closed-world`, `degraded`, or `full-reparse`. |
| `spec_provenance` | `global-unrevalidated`, `global-revalidated`, `customer`. |
| `engine` | `ifds`, `ide` → core; `semgrep`, `cpg-query`, `external` → oracle. |
| `CW-DETECT` | Closed-world precondition detector (CMP-SNAP-03). INV-4 owner. |
| `AFFECTED` | Changed decls + reverse-symbol closure + direct callers + CHA-cone (Algorithm 1). |
| `(B, T)` | Canonicalization budget: `B = 2^16` nodes, `T = 200 ms`. |
| `e-process` | Anytime-valid martingale for the precision-floor null (Algorithm 6). |
| `attestor` | Partitioned Determinism Attestor (CMP-CP-05). |

Full glossary: `docs/cross-cutting/DOC-GLOSSARY.md` (Phase 0 output).

---

## 5. Component map

| Subsystem | Components |
|---|---|
| SCM Integration | CMP-SCM-01 (ABC), CMP-SCM-02 (GitHub), CMP-SCM-03 (GL/BB/ADO), CMP-SCM-05 (HTTP retry) |
| Snapshotter | CMP-SNAP-01 (API), CMP-SNAP-02 (Alg 1), CMP-SNAP-03 (CW-DETECT), CMP-SNAP-04 (diff oracle), CMP-SNAP-05 (worker + env) |
| Detector Catalog | CMP-DET-01 (DSL), CMP-DET-02 (registry), CMP-DET-03 (scaffolding + migration) |
| Analysis Core | CMP-CORE-01 (IFDS/IDE, Alg 2), CMP-CORE-02 (fingerprint, Alg 3), CMP-CORE-03 (canonical order, Alg 5) |
| Orchestration | CMP-ORCH-01 (scan API), CMP-ORCH-02 (scheduler, Alg 4), CMP-ORCH-03 (worker) |
| Findings & Provenance | CMP-FND-01 (normalizer), CMP-FND-02 (store schema), CMP-FND-03 (signed provenance) |
| Triage & Spec Inference | CMP-TRI-01 (LLM triage), CMP-TRI-02 (e-process gate, Alg 6), CMP-TRI-03 (drift monitor) |
| Control Plane & Attestation | CMP-CP-01 (API guard), CMP-CP-02 (cred encryption), CMP-CP-03 (tenancy schema), CMP-CP-04 (auth + dashboard), CMP-CP-05 (attestor), CMP-CP-06 (CPG fidelity gate) |
| Deployment | CMP-DEPLOY-01..05 |
| Corpora | CMP-CORP-REFL-01, CMP-CORP-CPG-{java,python,js,go,ruby,php}, CMP-CORP-CANARY-01, CMP-CORP-REFAC-01, CMP-CORP-VULN-01 |
| CI gates | CMP-CI-01 |
| Research mode | CMP-RES-01 |

---

## 6. Dependency DAG (verbatim from `WBS.md §20`)

```
CMP-DEPLOY-01  → []
CMP-DEPLOY-02  → [CMP-DEPLOY-01]
CMP-DEPLOY-03  → [CMP-DEPLOY-01]
CMP-DEPLOY-04  → [CMP-DEPLOY-01, CMP-DEPLOY-02]
CMP-DEPLOY-05  → [CMP-DEPLOY-01, CMP-CP-01, CMP-CP-03]

CMP-SCM-01     → []
CMP-SCM-05     → []
CMP-SCM-02     → [CMP-SCM-01]
CMP-SCM-03     → [CMP-SCM-01, CMP-SCM-05]

CMP-DET-01     → []
CMP-DET-02     → [CMP-DET-01]
CMP-DET-03     → [CMP-DET-02]

CMP-SNAP-03    → []
CMP-SNAP-01    → [CMP-SCM-01, CMP-FND-03]
CMP-SNAP-05    → [CMP-SNAP-01, CMP-DEPLOY-02]
CMP-SNAP-02    → [CMP-SNAP-01, CMP-SNAP-03]
CMP-SNAP-04    → [CMP-SNAP-03, CMP-FND-02]

CMP-CORE-03    → []
CMP-CORE-01    → [CMP-DET-01, CMP-SNAP-02, CMP-CORE-03]
CMP-CORE-02    → [CMP-CORE-01, CMP-CORE-03]

CMP-FND-02     → [CMP-CP-03]
CMP-FND-01     → [CMP-CORE-02, CMP-CORE-03]
CMP-FND-03     → [CMP-FND-02]

CMP-ORCH-01    → [CMP-SNAP-01, CMP-FND-01, CMP-CP-01]
CMP-ORCH-02    → [CMP-ORCH-01]
CMP-ORCH-03    → [CMP-CORE-01, CMP-DET-02, CMP-FND-01]

CMP-TRI-01     → [CMP-FND-02]
CMP-TRI-02     → [CMP-DET-02, CMP-FND-02]
CMP-TRI-03     → [CMP-TRI-02]

CMP-CP-02      → []
CMP-CP-03      → []
CMP-CP-01      → [CMP-CP-03]
CMP-CP-04      → [CMP-CP-01, CMP-FND-03]
CMP-CP-05      → [CMP-ORCH-01, CMP-FND-03]
CMP-CP-06      → [CMP-SNAP-05]

CMP-CORP-REFL-01   → []
CMP-CORP-CPG-*     → []
CMP-CORP-CANARY-01 → [CMP-SCM-02, CMP-SCM-03]
CMP-CORP-REFAC-01  → []
CMP-CORP-VULN-01   → []

CMP-CI-01      → [CMP-DEPLOY-04]
CMP-RES-01     → [CMP-SCM-02, CMP-TRI-02]
```

**Wave-1 (no unmet deps — start in parallel):**
`CMP-DEPLOY-01, CMP-SCM-01, CMP-SCM-05, CMP-DET-01, CMP-SNAP-03, CMP-CORE-03, CMP-CP-02, CMP-CP-03, CMP-CORP-REFL-01, CMP-CORP-CPG-*, CMP-CORP-REFAC-01, CMP-CORP-VULN-01`

---

## 7. Per-language staging gates

```
Stage A  Java + Python    core classes: injection, path-traversal, ssrf, deserialization
Stage B  JS / TS          after Stage A attested + CMP-CP-06 green for JS/TS
Stage C  Go               CMP-CP-06 green first (needs points-to investment T-STAGE-C-FE-01)
Stage D  Ruby + PHP       oracle-passthrough until CMP-CP-06 gate passes (likely needs T-STAGE-D-FE-01)
C/C++    memory-safety    oracle-passthrough (CodeQL) throughout v3.2 — OOS-CC-01
secrets, dep-cve          always oracle-passthrough
crypto-misuse, authn-authz  mixed: IFDS portion follows language staging; patterns always oracle
```

**Rule:** a `(class, language)` pair may not enter Algorithm 2 benchmarking until `CMP-CP-06` is green for that language. Staging constraint overrides the dependency DAG.

---

## 8. Technology stack (resolved CLAR-DEPLOY-*)

| Primitive | Decision |
|---|---|
| Compute | AWS ECS Fargate (pinned-image workers) |
| Object store | Amazon S3 (deterministic key paths `orgs/{org_id}/...`) |
| Relational DB | PostgreSQL 16 on Amazon RDS (Alembic migrations) |
| KMS / encryption | AWS KMS envelope encryption (key rotation via KMS) |
| Secrets injection | AWS Secrets Manager → ECS task |
| Queue | Amazon SQS + per-queue DLQ |
| Observability | OpenTelemetry → CloudWatch Logs + X-Ray |
| Image registry | Amazon ECR + Sigstore Cosign signing |
| OIDC/SAML IdP | Auth0 |
| CI/CD | GitHub Actions (OIDC-to-AWS, keyless) |
| LLM (triage/spec) | Anthropic API `claude-sonnet-4-6` |
| RBAC roles | `org-admin`, `org-viewer`, `scanner` |
| Data retention | CPG: 90d · witness: 1y · SARIF+provenance: 7y (S3 Object Lock) |

Full decision record: `docs/cross-cutting/DOC-DEPLOY-DECISIONS.md` (Phase 0 / CMP-DEPLOY-01 output).

---

## 9. Definition of Done — v3.2 baseline (`WBS.md §21`)

```
[ ] Phase 0    Every CMP-* has a DOC-CMP-*; all cross-cutting refs exist.
[ ] Phase 1    Every AC-* has a TST-AC-*; every INV-* has TST-INV-* per emitter.
[ ] Stage A    Every Stage-A CMP-* has all ACs green for Java + Python.
[ ] CMP-CP-05  Byte-identical core-partition SARIF on every detector/engine/Env change.
[ ] CMP-SNAP-04 Demonstrably re-partitions on a seeded CW-DETECT FN; SLA published.
[ ] CMP-TRI-02 Adversarial unbounded-continuation test passes; martingale unit test green.
[ ] CMP-CI-01  Four named gates enforced as hard pipeline failures.
[ ] DEPLOY-01..05 Substrate decided; worker image signed; observability live; isolation verified.
[ ] Staging    Stage A..D status table is AC-driven, not prose.
[ ] CLAR-*     Every item RESOLVED or explicitly deferred with reasoning.
[ ] OOS-*      No drift in from the out-of-scope register.
[ ] Risks      R-1..5 mitigations DONE or LIVE AS POLICY.
```

---

## 10. Agent team and slash commands

| Role | Command | Scope |
|---|---|---|
| **CTO** | `/cto` | CLAR-* resolution; staging-gate approval; PLAN vs SDD arbitration |
| **Architect** | `/architect` | INV-1..6 design review; DOC-ALGS, DOC-PARTITION, DOC-STAGING |
| **Documentation Manager** | `/doc-agent` | DOC-CMP-* (34 files) + cross-cutting refs; no production code |
| **QA** | `/qa-agent` | AC-* → TST-AC-*; fixtures; falsifier campaigns |
| **Security Analyst** | `/security-analyst` | INV-3/INV-4 review; credential handling; CW-DETECT safe direction |
| **SRE / DevOps** | `/sre-agent` | CMP-DEPLOY-*; CI/CD; Dockerfile pinning; observability |
| **Corpus Curator** | `/corpus-agent` | CMP-CORP-* (reflection, CPG-fidelity, canary, refactor, vuln) |
| **Implementation** | `/implement` | One CMP at a time; reads DOC-CMP-*; makes TST-AC-* green |
| **Code Review** | `/code-review-cmp` | PR review: INV-* compliance, scope, provenance threading |
| **WBS Sync** | `/sync-wbs` | Update status codes; surface next-READY items |
| **Stage Gate** | `/stage-gate` | Approve/reject Stage A→D transitions |
| **CLAR Resolution** | `/clar-resolve` | Research + write a single CLAR-* decision record in WBS.md §17 |

Full briefings: `.claude/commands/<role>.md`.

---

## 11. Agent synchronization protocol

```
RULE-1   No implementation starts CMP-X until DOC-CMP-X is DONE.
RULE-2   No implementation starts CMP-X until every Depends-On is DONE.
RULE-3   CMP-X is DONE only when every TST-AC-X-* is green.
RULE-4   Unspecified behaviour → CLAR-* in WBS.md §17. Never invent scope.
RULE-5   Out-of-scope task → OOS-* in WBS.md §18. Do not schedule.
RULE-6   Every finding emitter threads {S_version, env_digest, origin,
         cpg_order_hash with conditional-canonicality annotation}.
RULE-7   No (class, language) enters Alg-2 benchmarking before CMP-CP-06 green.
RULE-8   CTO approves every CLAR-DEPLOY-* before its dependent phase starts.
RULE-9   Security Analyst reviews every component touching INV-3 or INV-4.
RULE-10  Code Review approval required before merge.
```

Also in `.claude/rules/00-global.md` and the PR template.

---

## 12. File layout

```
CLAUDE.md, PLAN.md, SDD.md, WBS.md, README.md   ← root
.claude/
  settings.json            ← permissions, hooks (PostToolUse/PreToolUse/Stop), MCP
  hooks/                   ← post-edit-invariant-check.sh, pre-edit-sot-guard.sh, stop-wbs-sync.sh
  rules/                   ← 00-global, 01-invariants, 02-provenance, 03-scope, 04-staging, 05-determinism
  commands/                ← /cto, /architect, /doc-agent, /qa-agent, /security-analyst,
                             /sre-agent, /corpus-agent, /implement, /code-review-cmp,
                             /sync-wbs, /stage-gate, /clar-resolve
  agents/                  ← doc-agent, qa-agent, corpus-agent, implement (Agent SDK)
.github/
  workflows/               ← ci.yml, attestor.yml, canary.yml, stage-gate.yml, deploy.yml, falsifier-cw.yml
  PULL_REQUEST_TEMPLATE.md
  ISSUE_TEMPLATE/          ← component.yaml, clar.yaml, corpus.yaml
.husky/pre-commit          ← lint-staged + pre-commit bridge
.pre-commit-config.yaml
pyproject.toml             ← ruff + mypy
package.json               ← lint-staged, husky, commitlint

docs/
  components/DOC-CMP-*.md  ← Phase 0: 34 per-component docs
  cross-cutting/           ← DOC-INV, DOC-GLOSSARY, DOC-API, DOC-DB, DOC-SARIF,
                             DOC-DSL, DOC-PROVENANCE, DOC-ALGS, DOC-PARTITION,
                             DOC-STAGING, DOC-RUNBOOK, DOC-DEPLOY-DECISIONS

integrations/scm/          ← CMP-SCM-01..05
analysis/
  ifds/dsl/                ← CMP-DET-01 (combinator DSL + distributivity proof obligations)
  ifds/solver.py           ← CMP-CORE-01
  cpg_delta.py             ← CMP-SNAP-02
  ordering.py              ← CMP-CORE-03
detectors/<class>/         ← CMP-DET-02, CMP-DET-03
services/snapshot/         ← CMP-SNAP-01
services/scan/             ← CMP-ORCH-01, CMP-FND-01, CMP-ORCH-03
services/triage/           ← CMP-TRI-01..03
services/research/         ← CMP-RES-01
workers/                   ← Dockerfiles (CMP-SNAP-05, CMP-DEPLOY-02)
db/migrations/             ← CMP-CP-03
web/                       ← CMP-CP-04 dashboard (TypeScript)
tests/
  unit/, integration/
  falsifier/cw/            ← Falsifier CW (TST-AC-SNAP-03a)
  falsifier/eprocess/      ← e-process martingale tests (TST-AC-TRI-02a/b)
  corpora/                 ← reflection, cpg_fidelity, canary, refactor, vuln
infra/                     ← Terraform / CDK (CMP-DEPLOY-01..05)
```

---

## 13. Reading guide for code-writing agents (verbatim `WBS.md §22`)

1. Read `DOC-CMP-X` (Phase 0 output) as the primary specification.
2. Read cross-cutting refs: `DOC-INV`, `DOC-GLOSSARY`, `DOC-API`, `DOC-DB`, `DOC-SARIF`, `DOC-DSL`, `DOC-PROVENANCE`, `DOC-ALGS`, `DOC-PARTITION`, `DOC-STAGING`, `DOC-RUNBOOK`.
3. Read `TST-AC-X-*` (Phase 1 output) — the "done" contract.
4. Read each `INV-*` listed in `DOC-CMP-X`'s "Invariants touched" section + corresponding `TST-INV-*`.
5. Confirm every `Depends-On` for `CMP-X` is `DONE`. Fail with `BLOCKED` / `STAGE-GATED` otherwise.
6. Implement.
7. Run every `TST-AC-*` and `TST-INV-*`. `DONE` only when all green.
8. If anything required is unspecified, file a `CLAR-*` in `WBS.md §17`. Never invent scope.

---

## 14. Filing CLAR-* and OOS-* items

**CLAR-***: a required decision is missing from PLAN.md / SDD.md.
Append to `WBS.md §17`:
```
| CLAR-<DOMAIN>-<NN> | <one-line question> | <blocks: CMP-* list> | <target resolution phase> |
```

**OOS-***: a derived task implies a `SDD.md §12` out-of-scope item (CI-agent, on-prem runner, container scanning, binary-only, IDE plugin, C/C++ core port, environment-independent determinism, LLM-influenced core findings).
Append to `WBS.md §18`:
```
| OOS-<DOMAIN>-<NN> | <item being deflected> | <source> |
```

---

## 15. Pre-commit + CI gate reference

| Gate | Enforces | Hard? |
|---|---|---|
| **lint** | ruff, mypy, eslint, prettier, yamllint, detect-secrets, shellcheck | yes (pre-commit + ci.yml) |
| **DSL proofs (Gate 1)** | `AC-DET-01a` — every combinator has a discharged distributivity proof obligation | **yes** — release blocker |
| **Falsifier CW (Gate 2)** | `AC-SNAP-03a` — zero FN on reflection corpus | **yes** — release blocker |
| **Attestor (Gate 3)** | `AC-CP-05c` — byte-identical core SARIF over canary corpus | **yes** — every detector/Env change |
| **e-process unit (Gate 4)** | `AC-TRI-02b` — martingale property holds across simulated stopping times | **yes** — blocks customer-enablement deploy |

Branch protection on `main` enforces Gates 1–4 as required status checks.

---

## 16. How to use this file

- **Session start:** read CLAUDE.md fully.
- **Your role:** also read `.claude/commands/<your-role>.md` + `.claude/rules/00-global.md`.
- **Code work:** also read `docs/components/DOC-CMP-<id>.md` + the cross-cutting refs your component touches.
- **When stuck:** file a `CLAR-*` rather than guessing. See §14.
- **Never:** edit `PLAN.md` or `SDD.md`. Allowed `WBS.md` edits: §17 / §18 appends and status-code flips only.
