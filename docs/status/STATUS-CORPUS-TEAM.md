# STATUS — Corpus team

**Owner:** Corpus curators + the second reviewer (CLAR-CORP-03 — pending assignment, see
`STATUS-MANAGEMENT.md` §3-E) · **Updated by:** corpus team, via PR.

All six corpora exist as **v0.1.0 scaffolds, self-declared NOT gate-strength**. Each sheet below
states the gate-strength bar (from the DOCs/CLARs), what currently exists, the campaign work, and
what the corpus unblocks. Decisions marked **[MGMT]** must be signed in `STATUS-MANAGEMENT.md`
before the campaign row can complete. Update the fill-in fields only.

**Shared rules for every corpus:**
- Every delivered increment lands as a PR updating `tests/corpora/<name>/` + its `corpus.lock`
  (content digest must be self-consistent — two corpora currently have digest drift, flagged below).
- Dual review: curator + second reviewer sign-off recorded per increment (CLAR-CORP-03).
- Provenance: every sourced item carries license + origin URL; no GPL-incompatible inclusion.
- When an increment crosses gate-strength, say so in the PR body — it flips named `TST-AC-*` gates.

---

## 1. REFL-01 — reflection corpus *(Gate 2 / CW-DETECT falsifier)*

**Gate-strength bar:** ≥ 50 hand-curated snippets **per category** (Java dynamic proxies/Class.forName,
Python getattr/importlib, JS dynamic require/eval-family; CLAR-CORP-01) **+** ≥ 20 mutation-injected
adversarial cases per language, dual-reviewed.
**Today:** v0.1.0 seed set; generator emits structurally-similar trees (CLAR-CORP-06 fix is an
engineering item, queued); scoring rule for mutation-vs-hand-curated ambiguous (CORP-04 **[MGMT]**);
bulk OSS sourcing DEFERRED (CORP-05 **[MGMT — the Fork]**).
**Unblocks:** Gate 2 real on AC-SNAP-03a (zero-FN) · the SNAP-04 seeded-FN falsifier corpus (with CLAR-FE-03 scanner) · §21-L7.

| Field | Value |
|---|---|
| Campaign owner | _____ |
| Second reviewer | _____ |
| Java: hand-curated N / 50 per category | _____ |
| Python: hand-curated N / 50 per category | _____ |
| JS: hand-curated N / 50 per category | _____ |
| Mutation-injected per language / 20 | _____ |
| Dual-review sign-offs (PR links) | _____ |
| corpus.lock digest @ latest increment | _____ |
| Status / Date | _____ |

## 2. CPG-java — Java CPG-fidelity ground truth *(CP-06 Stage-A keystone)*

**Gate-strength bar:** ground truth re-extracted under a **pinned** Soot/WALA toolchain in a
provisioned build env (CORP-07 — coordinate env with the AWS team), JDK pin confirmed (CORP-08
**[MGMT]**: DOC says 17, current sandbox 21), per-language N + real-OSS SOURCED quota pinned
(CORP-09 **[MGMT]**), generated-code balance ≥ 10% (CORP-10 **[MGMT]**).
**Unblocks:** CP-06 gate verdict for Java → Stage-A staging line, INV-6 honesty, §21-L3/L9.

| Field | Value |
|---|---|
| Campaign owner | _____ |
| Ground-truth toolchain pinned (versions + env link) | _____ |
| JDK pin decision applied | _____ |
| Sourced-repo quota progress (N / target) | _____ |
| Generated-code share (% / ≥10%) | _____ |
| Dual-review sign-offs | _____ |
| corpus.lock digest | _____ |
| Status / Date | _____ |

## 3. CPG-python — Python CPG-fidelity ground truth *(CP-06 Stage-A keystone)*

**Gate-strength bar:** toolchain decision CORP-11 **[MGMT]** (pin scalpel/Pyan3/Pyre on CPython 3.10
**or** ratify the in-repo extractor + amend the DOC), then ground-truth extraction at the pinned
toolchain; SOURCED real-repo quota; per-category N.
**Known defect (engineering, queued):** `corpus.lock` digest drift — corpus_digest does not match its
own contents; will be fixed code-side, do not hand-edit.
**Unblocks:** CP-06 for Python → Stage-A, §21-L3/L9.

| Field | Value |
|---|---|
| Campaign owner | _____ |
| CORP-11 decision applied | _____ |
| Sourced-repo quota progress | _____ |
| Dual-review sign-offs | _____ |
| corpus.lock digest (post drift-fix) | _____ |
| Status / Date | _____ |

## 4. CANARY-01 — 100-repo determinism canary *(Gate 3 / CP-05 corpus)* — **UNBUILT, now dep-unblocked**

**Bar:** 100-repo manifest mirrored to **all four** SCM providers with an automated, reproducible
re-mirror procedure driven by the (now conformance-verified) SCM connectors.
**Needs from outside the corpus team:** real `scanipy-canary` orgs on GitHub/GitLab/Bitbucket/ADO +
push credentials in Secrets Manager — request via `STATUS-AWS-TEAM.md` item 9.
**Unblocks:** CP-05/Gate-3 attestation runs · AC-CORE-01a corpus determinism · AC-CORE-03b
budget-exhaustion rate · TST-AC-SCM-03c cross-provider resolution · §21-L4.

| Field | Value |
|---|---|
| Campaign owner | _____ |
| Manifest authored (N/100, PR link) | _____ |
| 4-provider orgs + creds ready (AWS item 9) | _____ |
| Re-mirror procedure run green (AC-CANARY-01b evidence) | _____ |
| Status / Date | _____ |

## 5. REFAC-01 — refactor corpus *(CORE-02 fingerprint stability)*

**Bar:** ≥ N structurally-distinct sourced (class, language, sink-topology) refactor pairs —
diversity bar CORP-17 **[MGMT]**; v0.1.0 is topology-thin.
**Unblocks:** AC-CORE-02a/02b empirical halves (fingerprint invariance under named refactors).

| Field | Value |
|---|---|
| Campaign owner | _____ |
| Topology count (distinct / target) | _____ |
| Dual-review sign-offs | _____ |
| Status / Date | _____ |

## 6. VULN-01 — held-out vulnerability corpus *(AC-CORE-01b recall)*

**Bar (CORP-19 — currently DEFERRED, the Fork):** real NIST/SARD Juliet 1.3 + upstream BigVul CSV +
OWASP fetch-on-demand (CORP-18 resolved), held-out split re-derived over real rows, populated per
Stage-A (class, language). The deterministic-split + never-train-on-held-out machinery is **already
built** — only scale is deferred.
**Known defect (engineering, queued):** `corpus.lock` digest drift, same as CPG-python.
**Unblocks:** AC-CORE-01b recall measurement → §21-L3.

| Field | Value |
|---|---|
| Campaign owner | _____ |
| Fork decision applied (A: stays deferred / B: funded) | _____ |
| Juliet/BigVul/OWASP integration progress | _____ |
| Held-out split re-derived (evidence) | _____ |
| Status / Date | _____ |
