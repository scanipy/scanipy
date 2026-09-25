# Scanipy

### Findings you can trust: refactor-invariant identity and provable provenance for static analysis

**Black Hat MEA 2026 — supporting material**

| | |
|---|---|
| Open-source repository | `github.com/scanipy/scanipy` — Apache-2.0 |
| Demo video | `https://youtu.be/IjYhB08JdxI` |
| Run it yourself | `docker compose up --build` → `http://localhost:8000` |

---

## 1. The problem

A SAST finding is not a durable object. Incumbents identify a finding by **where it is**
(file and line) plus a fuzzy hash of the surrounding text. Change the text without changing
the bug, and the same finding is re-issued under a **new identity** — detaching every
suppression and triage verdict attached to it.

```
   Monday                            Tuesday  (renamed + reformatted)
   -------------------------------   -------------------------------------
   finding #4e81...                  finding #9c22...   <- new id, same bug
     |- triaged: "false positive"      |- triaged:       (nothing)
     |- suppressed by: alice           |- suppressed by: (nobody)
     `- linked ticket: SEC-231         `- linked ticket: (none)

                 the bug never moved -- only the text did
```

The same fragility means a re-run may not reproduce byte for byte, so SAST output cannot
serve as audit evidence or as a hard CI gate.

---

## 2. What Scanipy adds

Detection stays with proven engines. Scanipy wraps each finding in three guarantees.

```
   +--------------+    +------------------+    +-------------------------+
   |  Repository  |--->|    Detection     |--->|        SCANIPY          |
   |  @ commit    |    | Semgrep / CodeQL |    |      trust layer        |
   +--------------+    +------------------+    +------------+------------+
                                                            |
        +----------------------+----------------------------+
        |                      |                            |
   REFACTOR-INVARIANT     REPRODUCIBILITY            SIGNED PROVENANCE
   IDENTITY               (partitioned)              audit chain

   fingerprint of the     deterministic-core:        commit -> snapshot ->
   finding's code-        byte-identical (theorem)   S_version -> env_digest
   dependence slice,      ------------------------   -> cpg_order_hash ->
   via graph canonical-   oracle-passthrough:        witness -> rule id ->
   isation, not text      measured reproduction      output hash -> origin
                          rate, never a theorem      signed, verifiable
```

> **The honest partition.** Every finding carries `origin`. Only `deterministic-core`
> findings are covered by the reproducibility theorem; `oracle-passthrough` findings carry
> a measured rate. The two are never blurred — in the code, in the schema, or on stage.

---

## 3. The mechanism: identity from structure, not text

The fingerprint is computed from the **canonical form of the code-dependence slice** the
finding implicates — Weisfeiler–Leman refinement, then bounded individualisation–refinement
— and self-labels `strong` or `weak` when the canonicalisation budget is exhausted.
**Source location is used only to locate the node. It never enters the hash.**

```
        BEFORE                               AFTER  (local variable renamed)

   def handler(req):                    def handler(req):
       user = req.args['u']                 name = req.args['u']
       q = "SELECT...%s" % user             q = "SELECT...%s" % name
       cur.execute(q)     <- sink           cur.execute(q)     <- sink

              |                                      |
              v                                      v
     backward dependence slice            backward dependence slice
     canonicalised                        canonicalised
              |                                      |
              +------------->  fingerprint A  <------+

     Scanipy                 same identity -- triage history survives
     location + text-hash    new id issued
     (SpotBugs / CodeQL / Semgrep match_based_id)
```

---

## 4. Refactor-invariance

The identity is derived from structure, so it is invariant under transformations that change
the text without changing the vulnerable data-flow, and it changes when the data-flow is
genuinely fixed.

```
   IDENTITY HOLDS                         IDENTITY CHANGES
   --------------------------------       --------------------------------
   local variable renaming                a genuine fix -- the vulnerable
   formatting-only changes                data-flow is removed or sanitised
   independent statement reordering
   extract method
   file move / package rename
```

Each invariance is enforced by a named normalisation pass applied to the slice before
canonicalisation. Every fingerprint self-labels `strong` or `weak`; a `weak` result is a
same-source identity only and is never treated as a canonical-graph claim.

**Validation.** Invariance is verified by a harness that runs the fingerprint against **real
Joern-parsed code property graphs** over a corpus of before/after refactor pairs carrying
ground-truth `should-stay` and `should-flip` labels, reporting per-refactor results. The
harness ships in the repository and is runnable by anyone:

```
python scripts/validate_refactor_fingerprints.py \
    --corpus-dir tests/corpora/refactor --out report.json
```

---

## 5. What the demo shows

**Video —** `https://youtu.be/IjYhB08JdxI`

```
   1.  docker compose up      one command · no cloud account · Postgres + scan API
   2.  paste a repository     real findings, each labelled with CWE and origin
   3.  refactor and re-scan   Scanipy's identity holds; incumbents re-issue a new id
   4.  provenance             sign -> VERIFIED · tamper one field -> TAMPERED
```

Provenance verification is real RSASSA-PSS over the shipped audit chain, verifiable without
re-running the analysis. The signer in the self-host build is a **local software key**,
stated as such.

---

## 6. The deployment

| | |
|---|---|
| Install | One command: `docker compose up --build` |
| Substrate | Self-hosted, single-tenant · Postgres · no cloud account required |
| Detection | Established engines — Semgrep, CodeQL adapter |
| Isolation | Scanned code is analysed, never executed |
| Licence | Apache-2.0, fully open source |

Detection quality is inherited from the underlying engines and is labelled as such.
Scanipy's contribution is the trust layer above them: identity, reproducibility, provenance.

---

## 7. Reproduce everything

```
git clone https://github.com/scanipy/scanipy && cd scanipy
docker compose up --build          # -> http://localhost:8000
```

Design records, the validation harness, and evidence artifacts are in `docs/` in the
repository.

---

*Scanipy is open source under Apache-2.0. Detection is delegated to established engines and
labelled as such; no unsupported detection-rate claims are made anywhere in this material.*
