# PLAN-BHMEA-EXECUTION — final implementation plan (agent-orchestrated)

> Historical input, superseded for execution on 2026-09-25 by
> [the current handoff](PLAN-BHMEA-EXECUTION-2026-09-25.md) and
> [review revision 3](REVIEW-BHMEA-EXECUTION-ACTION-ITEMS-2026-09-23.md).
> The owner confirmed acceptance, removed the October 23 lock, specified a
> December 2 or 3 local-Docker presentation, and retained the full submitted
> scope. Old dates and automatic feature-drop instructions below are preserved
> for traceability, not active instructions.

**Written:** 2026-09-22 · **Owner:** project owner · **Talk:** 1–3 December 2026, Riyadh
**Demo lock:** **Friday 23 October** (non-negotiable)
**Supersedes:** `docs/PLAN-BHMEA-REFACTOR-INVARIANCE.md` for execution. That document remains
the gap-analysis record; this document is the executable plan. Where they disagree, this one wins.
**Consumer:** an orchestrating LLM that spawns implementation agents. Each task card in §5 is
self-contained: an agent needs only its card, §2 (rules), §3 (commands), and the cited files.

---

## 0. How the orchestrator runs this plan

1. **Waves, not weeks.** §4 defines dependency waves. Tasks inside a wave are parallel-safe;
   the file-ownership matrix (Appendix B) is what makes them safe — enforce it strictly.
2. **One task card = one agent = one branch = one PR.** The repo's own protocol applies
   (`CLAUDE.md` §11): `scripts/board.sh check <issue>` before pickup, claim with
   `set <issue> "In Progress"`, and the `claude-review` CI check must reach **APPROVE**
   before merge (RULE-10 — fail-closed). Merge a card before spawning its dependents.
3. **The `analysis/fingerprint.py` lane is strictly serial.** T1 → T2 → T3b, in that order,
   each fully merged before the next starts. Everything demo-side (TD-*) and docs-side
   (W5-*) runs parallel to it.
4. **Every agent returns a structured report** (Appendix A). The orchestrator verifies a
   "done" claim by re-running the card's done-when commands, not by trusting the report.
5. **Human decision points are explicit** (§6, D1–D6). Agents must not resolve them
   autonomously; a blocked-on-decision task is reported `BLOCKED` with the decision memo
   drafted, per RULE-4.
6. **Escalation cap.** An agent that fails the same gate 3 times stops, preserves its
   artifacts (slice diffs, harness JSON) under `docs/evidence/`, and returns `ESCALATED`.
   The orchestrator re-scopes; it does not let agents grind.

---

## 1. Verified current state (2026-09-22)

### 1.1 The measured refactor-invariance gap (unchanged from the gap analysis)

Evidence run over real Joern-parsed CPGs, 8 seeds = all 8 corpus topologies, 56 pairs,
every pair `strong`/`strong`:

| Demo beat | Java | Python | State |
|---|---|---|---|
| rename locals | 4/4 | 4/4 | holds |
| reformat | 4/4 | 4/4 | holds |
| reorder independent statements | 4/4 ⚠ vacuous (issue #361) | **0/4** | fails |
| extract a helper | 4/4 ⚠ vacuous (issue #361) | **1/4** | fails |
| move file / rename package | **0/4** | 4/4 | fails |
| genuine fix flips it | 3/4 | 4/4 | **7/8 — one false negative (Java seed-007)** |

### 1.2 New finding (2026-09-22 review): the shipped demo cannot perform beat 3 at all

The gap analysis measured the **library** (`analysis/fingerprint.py`, strong path). The
**shipped self-host demo** is a different, disjoint path:

- `deploy/scanipy_oracle/app.py:199` computes the finding id as
  `sha256(commit_sha | check_id | rel_path | line)` — location-keyed and commit-keyed.
  It is honestly *labelled* `fingerprint_class=weak` (`app.py:117-118,197-198`), but it is
  **not refactor-invariant**: a re-scan after *any* refactor gets a new `commit_sha`, so
  every id flips even when no line moves. Formatting shifts `line`. A file move shifts
  `rel_path`. Demo beat 3 ("refactor and re-scan — the identity holds") **fails on the
  shipped demo no matter how well T1–T4 fix the library.**
- The demo image (`deploy/Dockerfile`) contains Python + git + Semgrep only — **no Joern**.
  The strong slice fingerprint needs the Joern toolchain, which lives in
  `workers/snapshot/Dockerfile` (not referenced by `docker-compose.yml`).
- `docker-compose.yml` ships exactly two services (`db`, `scanipy`); no worker lane exists.
  `deploy/README.md:16-26` already discloses this ("the deterministic-core (IFDS/CPG)
  engine is staged and not on this path") — honest in the README, but the *submitted
  abstract and video* promise the refactor beat on `docker compose up`.

**Consequence:** this plan adds a demo-lane workstream (TD-*) with a human architecture
decision (D2) at the end of Wave 0. Without it, the library work is invisible on stage.

### 1.3 Documentation/repo hygiene gaps (verified)

- `docs/EVIDENCE-refactor-invariance-2026-08-31.md` — cited by the gap analysis — **does
  not exist in the repo**. Neither does `docs/evidence/`. The submission promises
  "evidence artifacts are in `docs/`". T0.5 fixes this.
- CLAR status (all verified in `WBS.md` §17): `CLAR-CORE-02` **OPEN** (WBS.md:934 — the
  "pure extract" definition; *already filed, do not re-file*), `CLAR-CORP-17` **OPEN**
  (WBS.md:976 — topology-thin corpus, 8 templates), `CLAR-ORCH-12` **OPEN** (WBS.md:1014 —
  oracle findings vs `canonical_emit` NOT-NULLs; explains why the oracle demo uses a
  separate `oracle` schema).
- The harness `scripts/validate_refactor_fingerprints.py` exists with the exact CLI the
  submission promises (`--corpus-dir`, `--out`). It runs **only inside the Joern worker
  image** (its own docstring, "WHERE IT RUNS") — the "runnable by anyone" claim needs the
  documented container command (T0.1 deliverable).
- Real collaborators for the harness exist and import: `analysis/cpg_ingest/mapper.py`
  (`map_export_with_locations`), `services/scan/oracle_fingerprint.py`
  (`fingerprint_oracle_finding`).
- The fingerprint passes named in the gap analysis all exist: `analysis/fingerprint.py`
  `_canonical_topo_sort` (:355), `_summary_inline_pure_extract` (:371), `_fqn_normalise`
  (:393) with inner `_norm_fqn` (:407), `_content_hash` (:449).
- Corpus defect site: `tests/corpora/refactor/pipeline/refactor_transforms.py:304`
  (`_inject_after_first_body`), call sites :261, :270.
- Tracker: GitHub issues on `github.com:scanipy/scanipy` — #359 (CLAR-ORCH-12),
  #360 (normalisation; body wrong, correction in T0.3), #361 (corpus defects).
  Recent merges: #356 (provenance demo), #353 (location side-table), #357 (this harness).

---

## 2. Non-negotiable rules (every agent, every task)

- **R1 — The acceptance gate is four-sided.** A change to fingerprinting is accepted only
  if it (a) fixes its target column, (b) leaves α-rename and formatting at 8/8, (c) does
  **not** reduce the genuine-fix flip count, **and (d) leaves the determinism surface
  green**: `pytest tests/unit -q` plus `pytest tests/falsifier/attestor -q` plus
  `tests/unit/test_fingerprint.py`. R1(d) is new relative to the gap analysis; fingerprint
  changes can silently break byte-identical reproducibility, and the submission promises a
  reproducibility *theorem*. Read `.claude/rules/05-determinism.md` first.
- **R2 — A genuine-fix regression is blocking, always.** A missed fix means a fixed bug
  keeps the vulnerable identity and stays suppressed. It is the only failure mode here
  that harms a user, and it is what Q&A will probe. Re-check this column after **every**
  change, not just at gates.
- **R3 — Never tune the harness or the corpus to improve a number.** Fix the mechanism or
  narrow the claim. A red cell published is survivable; a green cell manufactured is not.
  No agent edits corpus ground-truth labels or harness comparison logic. Ever.
- **R4 — Source-of-truth writes.** Never edit `PLAN.md` or `SDD.md`. Allowed `WBS.md`
  writes: §17 `CLAR-*` appends, §18 `OOS-*` appends, status-code flips (§1.2). Unspecified
  behaviour → file a `CLAR-*`; never invent scope (repo RULE-4). Repo hooks
  (`.claude/hooks/pre-edit-sot-guard.sh`) enforce this.
- **R5 — Evidence beats intuition.** Every claim that reaches a slide comes from a harness
  run committed under `docs/evidence/<date>-<name>/` (report JSON + summary + notes on how
  it was produced). Evidence files are tool outputs — never hand-edited.
- **R6 — Never blur the partitions.** `origin ∈ {deterministic-core, oracle-passthrough}`
  and `fingerprint_class ∈ {strong, weak}` are labelled honestly in code, schema, UI, and
  on stage. A `weak` fingerprint is a same-source identity only (INV-5).
- **R7 — Nothing fabricated, nothing secret.** The repo is public-bound (OSS-01/OSS-02).
  No fabricated provenance fields, no synthetic fingerprints, no credentials in any
  artifact. The demo signer is a local software key and is stated as such.
- **R8 — The harness runs in-image, and a missing fingerprint is never a flip.** These
  two honesty rules are baked into the harness; do not route around them.

---

## 3. Environment & command reference

```bash
# Unit + type + lint (host; fast)
pytest tests/unit -q
pytest tests/falsifier/attestor -q            # determinism/attestor leg (R1d)
pre-commit run --all-files                    # ruff, mypy, yamllint, detect-secrets, ...

# Integration tests need Postgres: docker compose -f docker-compose.dev.yml up -d  (DB only)

# Corpus pipeline self-tests are EXCLUDED from the global pytest run
# (pyproject.toml --ignore=tests/corpora; duplicate basenames, cwd-relative paths).
# Run them from inside the corpus dir, e.g.:
cd tests/corpora/refactor && python -m pytest pipeline/ -q

# The demo stack (beat 1-4 end-to-end)
docker compose up --build                     # → http://localhost:8000

# Provenance smoke (sign → export → verify → tamper → verify)
python tools/provenance_demo.py --help        # discover current flags; run it

# The refactor-invariance harness — IN-IMAGE ONLY (joern-parse on PATH).
# Build the worker image with pins from workers/pins.json (JOERN_*, CODEQL_*,
# TEMURIN_*, GIT_VERSION build args), then run with the repo mounted so the
# WORKTREE's analysis/ + scripts/ + tests/ are what execute, e.g.:
#   docker build -f workers/snapshot/Dockerfile -t scanipy-snapshot \
#     $(jq -r 'to_entries|map("--build-arg "+.key+"="+.value)|join(" ")' workers/pins.json) .
#   docker run --rm -v "$PWD":/work -w /work -e PYTHONPATH=/work \
#     --entrypoint python scanipy-snapshot \
#     scripts/validate_refactor_fingerprints.py \
#       --corpus-dir tests/corpora/refactor --out docs/evidence/<run>/report.json
# T0.1 owns verifying and documenting the exact final form of this command.

# Board (RULE-11) — before picking up any task:
scripts/board.sh check <issue-number>
```

Python 3.11, pytest config in `pyproject.toml` (`filterwarnings=error` is on — keep it
green). The snapshot worker image's runtime stage `COPY`s `analysis/`, `services/scan/`,
`services/substrate/`, `services/snapshot/`, `tools/worker/`, `tools/observability/` —
so `fingerprint_oracle_finding` is importable in-image by construction.

---

## 4. Wave / dependency graph

```
Wave 0 (parallel):  T0.1  T0.2  T0.3  T0.4  T0.5
                       │     │                 │
Gate G0 (serial):  ◄───┴─────┘   true baseline re-run on fixed corpus, committed
                       │
Decision D2 (human, end of Wave 0): demo-lane architecture, informed by T0.4 numbers
                       │
Wave 1 (parallel):  T1 [fingerprint lane]   TD-1 [demo lane]   T3a [read-only diagnosis]
Wave 2 (parallel):  T2 [fingerprint lane]   TD-2 [demo lane lands e2e on fixtures]
Wave 3:             T3b [fingerprint lane] + hardening          (buffer week)
Wave 4:             T4 [conditional on D3]  →  L0 LOCK RUN Fri 23 Oct  →  D5 freeze
Wave 5 (parallel):  DOC-1 DOC-2 DOC-3 DOC-4  (rewrite public material to the locked set; D4 video)
Wave 6:             DEMO-1 stage build; offline end-to-end ×2 from a clean clone
Wave 7–9:           REH / REL / FALL (rehearsal, signed release, fallback recording)
```

The fingerprint lane (T1→T2→T3b) owns `analysis/fingerprint.py` exclusively and serially.
TD-* never touches it — it consumes the stable seam
`services.scan.oracle_fingerprint.fingerprint_oracle_finding`.

---

## 5. Task cards

Each card: **Goal · Context (what to read) · Do · Done-when · Escalates-to.**
Agents read §2 and §3 plus their card; nothing else is assumed.

### Wave 0 — prerequisites (all parallel; week of Sep 21–27)

---

**T0.1 — Harness fast loop: persistent export cache + slice-diff tool**
*Role: implement · Owns: `scripts/validate_refactor_fingerprints.py`, `tests/unit/test_validate_refactor_fingerprints.py`, and a NEW read-only debug module (e.g. `analysis/fingerprint_debug.py`) — do not edit `analysis/fingerprint.py`.*

- Goal: cut the iteration loop from ~70–80 min (8 seeds × 60–75 s/parse) to minutes, and
  make any failing pair inspectable without Joern in the loop.
- Context: the harness already has an in-memory parse cache
  (`RealFingerprinter._cache`, keyed by resolved dir + language) and re-reads the export
  JSON the parse wrote. `analysis/fingerprint.py:449` (`_content_hash`) shows exactly
  what the hash consumes.
- Do:
  1. Add `--export-cache <dir>`: persist each tree's raw Joern export JSON (and the
     mapped `(cpg, locations)` inputs) to disk; rebuild from cache on hit. Cache key =
     content digest of the source tree + language — never the path.
  2. Add `--dump-slice <seed_id>/<refactor>`: print the *normalised* slice for before and
     after as JSON — node `(kind, operator_or_literal, resolved_fqn, enclosing_decl_fqn)`
     in canonical order, plus ranked edge triples — i.e. precisely `_content_hash`'s
     inputs, plus a side-by-side diff. Implement the extraction in the new debug module
     so the fingerprint module is untouched.
  3. Unit tests for both (cache round-trip; dump determinism). Keep the harness's two
     honesty rules intact (R3/R8).
  4. Verify and then **document the exact in-image run command** (§3 sketch) in the
     harness docstring and `tests/corpora/refactor/README.md` — this is what makes the
     submission's "runnable by anyone" literally true.
- Done-when: a cached 8-seed run completes in < ~3 min; one command prints a before/after
  normalised-slice diff for any failing pair; unit tests + `pre-commit` green.
- Escalates-to: orchestrator if cache keys can't be made content-stable across runs.

---

**T0.2 — Valid Java corpus pairs (issue #361)**
*Role: corpus-agent · Owns: `tests/corpora/refactor/**` (pipeline, regenerated seeds,
`corpus.lock`, README status). Exception: if the corpus version string changes, the
one-line `CORPUS_CAVEAT` version reference in the harness is updated in this PR —
coordinate with T0.1 (same file); land T0.2 first or rebase.*

- Goal: Java reorder/extract variants must be real refactors, not class-body injections.
- Context: `tests/corpora/refactor/pipeline/refactor_transforms.py:304`
  (`_inject_after_first_body`) injects statements after the first *body* — for Java that
  is the class body, which is not valid Java (issue #361). Call sites :261, :270.
  `tests/corpora/refactor/README.md` documents the corpus build; `corpus.lock` is the
  pinned inventory the harness cross-checks (fail-closed on disagreement).
- Do:
  1. Fix `_inject_after_first_body` so Java statements land inside a **method body**.
  2. Regenerate the affected variants; re-pin `corpus.lock`; bump the corpus version
     (patch) and record the change in the corpus README. Ground-truth labels do not
     change (R3 — the fix changes trees, never labels).
  3. Run the corpus pipeline self-tests explicitly (§3 — they are excluded from the
     global pytest run).
- Done-when: all 8 Java `aliasing-changing-extract` pairs *evaluate* (no more
  `no-fingerprint-after` from unparseable trees); Java reorder/extract cells reflect a
  refactor that genuinely applied. **Expect some vacuous 4/4s to turn red — that is the
  point; record it, do not "fix" it.**
- Escalates-to: G0 cannot start until this merges.

---

**T0.3 — Tracker correction (issue #360 body)**
*Role: any · Owns: no code. Uses `gh issue edit` (or drafts the body for the human to paste).*

- Goal: issue #360's body currently misdirects anyone who picks it up. Correct it to:
  `_fqn_normalise` is **implemented** (`analysis/fingerprint.py:393`) — Java FQN is a
  **bug**, not a missing pass. `_canonical_topo_sort` (:355) is identity **by design**
  (its docstring asserts `canonical_order` already delivers reorder-invariance — the
  Python 0/4 disproves the assertion, so the defect lives in ordering/hash, not in a
  missing pass). Only `_summary_inline_pure_extract` (:371) is a genuine no-op, and its
  docstring gives a *soundness* reason, not a TODO. Cross-link #359 and #361.
- Done-when: issue #360 body states the above; #359/#361 bodies confirmed accurate.
- Escalates-to: none. Pure hygiene; do not let it block Wave 0 merges.

---

**T0.4 — Demo-smoke evidence pack + demo-lane measurements**
*Role: sre-agent · Owns: `docs/evidence/2026-09-2x-demo-smoke/` (new, append-only).*

- Goal: convert "reproducibility and provenance already work" from assumption to
  evidence, and produce the numbers D2 needs. This is the plan's verification of every
  submission claim *outside* the refactor-invariance pillar.
- Do:
  1. `docker compose up --build` from a clean checkout; record: stack comes up,
      `GET /healthz` shows a real `env_digest`, a pasted fixture repo yields findings
      **each labelled with CWE and `origin`** (submission demo beat 2). Capture output.
  2. Run `python tools/provenance_demo.py` (sign → export → VERIFIED → tamper →
      TAMPERED); capture the transcript. Confirm the local-software-key honesty note is
      what the demo says on stage.
  3. Run `pytest tests/falsifier/attestor -q` (byte-identical core SARIF surface) and
      record the result as the R1(d) baseline.
  4. Confirm the **demo-path gap** of §1.2 by re-scanning a fixture after a no-op
      recommit and showing the ids flip (one paragraph + command output).
  5. Measure for D2: wall-clock Joern parse time for 2–3 candidate demo fixture repos
      inside the snapshot-worker image; the worker image size; the demo image size.
- Done-when: `docs/evidence/2026-09-2x-demo-smoke/` contains the compose transcript,
  provenance transcript, attestor result, the id-flip demonstration, and a
  `measurements.md` (parse latency, image sizes). **If beat 2 (CWE/origin labels),
  provenance, or the attestor is red, stop the line: report immediately — the fallback
  messaging in §8 assumes all three are green.**
- Escalates-to: human (same day). A red result here re-scopes the talk, not just the plan.

---

**T0.5 — Evidence hygiene**
*Role: doc-agent · Owns: `docs/evidence/`, `docs/EVIDENCE-*.md`, one pointer line in
`docs/PLAN-BHMEA-REFACTOR-INVARIANCE.md`.*

- Goal: make the submission's "evidence artifacts are in `docs/`" true.
- Do:
  1. Create `docs/evidence/` with a README stating the convention (one dated dir per run;
     report JSON + summary + reproduction command; files are tool outputs, never edited).
  2. Recover the 2026-08-31 run's report if it exists outside the repo (check the
     `~/scanipy-demo` runner area) and commit it **verbatim**. If it is not recoverable,
     write `docs/EVIDENCE-refactor-invariance-2026-08-31.md` containing the table from
     §1.1, explicitly labelled "as reported in PLAN-BHMEA-REFACTOR-INVARIANCE §0;
     original run artifact not recoverable; superseded by the G0 baseline".
  3. Add a one-line pointer at the top of `docs/PLAN-BHMEA-REFACTOR-INVARIANCE.md`:
     superseded for execution by this plan.
- Done-when: the citation in the gap-analysis doc resolves to a real file.
- Escalates-to: none.

---

**Gate G0 — true baseline (serial; one agent; after T0.1 + T0.2)**

Re-run the 8-seed all-topology harness on the fixed corpus using the cache, record
`docs/evidence/<date>-baseline-g0/` (report JSON + summary + command). This is the
**baseline of record**: every later gate compares against it. Expect Java reorder/extract
numbers to drop from vacuous 4/4 to honest values — record, don't fix.

---

### Wave 1 — file move / package rename + demo lane starts

**T1 — File move / package rename: Java 0/4 → 4/4**
*Role: implement · Owns: `analysis/fingerprint.py`, `tests/unit/test_fingerprint.py`.*

- Context: ruled out already (do not re-litigate): `structural_path` (excluded from
  `_content_hash` by design; weak-order fallback never taken — all pairs strong/strong)
  and signature-debris asymmetry (the corpus refactor is a *pure* package move, so both
  sides normalise identically even though `_norm_fqn` mangles Joern Java full names —
  fix that anyway, below, but it is not this failure).
- Do:
  1. Run the T0.1 dump tool on seed-001 `fqn-move-package-rename` before/after. The diff
     splits the cause:
     - `operator_or_literal` differs on some node → a `NAMESPACE_BLOCK` / `TYPE_REF` /
       qualified call target is leaking package text into the hash → normalise qualified
       names in `operator_or_literal` for the node kinds that render them (same `%pkg.`
       collapse as `_norm_fqn`).
     - identical content, different node count/shape → the package move changed what
       Joern emits (extra namespace node / different slice frontier) → exclude
       namespace/package scaffolding from the backward slice, or normalise it to one
       canonical token.
  2. Regardless of which branch: make `_norm_fqn` Java-aware — split on `:` first,
     normalise the qualifier **and** each signature type, rejoin — guarded by unit tests
     using real Joern-shaped Java full names.
  3. Run the four-sided gate (R1) against the G0 baseline.
- Done-when: harness Java FQN cell 4/4 on the 8-seed run; α-rename + formatting 8/8;
  genuine-fix ≥ baseline; `pytest tests/unit -q`, `pytest tests/falsifier/attestor -q`,
  `pre-commit` green; evidence committed.
- Escalates-to: orchestrator after 3 failed gate attempts (§0.6).

---

**TD-1 — Demo lane: bring the strong fingerprint to the compose stack**
*Role: sre-agent + implement · Owns: `deploy/**`, `docker-compose.yml`, new worker-loop
module placed inside a package the worker image already COPYs (see below). Never touches
`analysis/`. Starts only after D2; this card specifies the options D2 chooses between.*

- Context: §1.2 is the problem statement. Constraints: `workers/snapshot/Dockerfile`
  already COPYs `analysis/`, `services/scan/` (so `fingerprint_oracle_finding` is
  importable in that image); its build args come from `workers/pins.json`. The app
  container is `read_only` with tmpfs `/tmp` — a second container cannot see the app's
  clones. The stage demo must run **offline** (W6), so fixtures must be local
  (`file://` URLs or pre-seeded volumes), not GitHub. The app currently derives the id
  at `deploy/scanipy_oracle/app.py:199`; findings rows already carry
  `slice_fingerprint` + `fingerprint_class` columns (`app.py:117-118`).
- Options for D2 (recommendation: **A**):
  - **A — fingerprint worker service.** Add a `fingerprint-worker` compose service built
    from `workers/snapshot/Dockerfile` (entrypoint overridden to a new thin poll loop,
    e.g. `services/scan/oracle_fingerprint_worker.py`, so it ships inside an already
    COPYed package). The app stores the cloned source on a shared named volume and marks
    findings `fingerprint_class=weak` (pending); the worker polls Postgres, parses with
    Joern, computes the strong slice fingerprint via `fingerprint_oracle_finding`, and
    upgrades the row. Mirrors the real platform split; keeps the app image light.
  - **B — fat single image.** Rebase `deploy/Dockerfile` to include the Joern toolchain;
    the app computes strong fingerprints inline but asynchronously after responding.
    Simplest compose file; ~GB image growth (measure in T0.4); parse latency sits inside
    the scan flow.
  - **C — identity-lab floor.** No new infra: a separate page that runs the harness-style
    before/after fingerprint comparison on bundled fixtures. Cheapest, but concedes
    "paste a repository → refactor → identity holds" as a live beat. This is the floor,
    not the plan.
- Do (assuming A; B/C analogous):
  1. Board-check DOCKER-02 (shared-queue substrate) — this lane is its minimal demo
     slice; note the scoping in the PR description.
  2. Wire the worker service into `docker-compose.yml` (build args from
     `workers/pins.json`; env `SCANIPY_DATABASE_URL`; shared read-only source volume).
  3. App change: keep the weak id as the *provisional* id, add the source-volume handoff,
     and surface `fingerprint_class` in the API/UI from the stored column — the UI string
     at `deploy/scanipy_oracle/static/index.html:147` must render the stored class, never
     a hardcoded one (R6).
  4. The provenance beat must keep working end-to-end through the new lane.
- Done-when: on the demo fixtures, `docker compose up --build` → paste repo → findings
  appear (weak, pending) → within the measured parse budget they flip to
  `fingerprint_class=strong`; refactor + re-scan → strong ids **hold**; a genuine-fix
  fixture → id flips; whole flow runs with the network cable pulled.
- Escalates-to: if TD-1 cannot hit the latency/offline budget by **Oct 11**, D2 falls to
  option C and W6 builds the identity-lab beat instead.

---

**T3a — Genuine-fix false-negative diagnosis (read-only; parallel with Wave 1)**
*Role: implement · Owns: nothing (read-only + `docs/evidence/` notes).*

- Do: use the T0.1 dump tool on Java seed-007 genuine-fix before/after. Determine which
  of the two it is: (a) the fix lies outside the backward slice (frontier too narrow), or
  (b) its effect is normalised away by a pass. Write the diagnosis + evidence to
  `docs/evidence/<date>-t3a-seed007/`. T3b (Wave 3) implements the fix.
- Done-when: a one-page diagnosis naming (a) or (b), with the slice diff attached.

---

### Wave 2 — independent statement reordering

**T2 — Reorder: Python 0/4 → 4/4**
*Role: implement · Owns: `analysis/fingerprint.py`, `tests/unit/test_fingerprint.py`
(serial after T1 merges).*

- Context: mechanism — swapping two data-independent statements flips the CFG edge
  between them; 2-WL relabels; ranks change; hashed `(kind, src_rank, dst_rank)` triples
  change. `_canonical_topo_sort` (:355) is identity because its docstring claims
  `canonical_order` already provides reorder-invariance; the Python 0/4 disproves it.
  **Tension:** the same CFG-edge family is part of what makes a genuine fix flip —
  removing edges wholesale will cost R1(c). This is a design decision executed as an
  option ladder, cheapest first:
  1. Exclude CFG edges between statements with no data dependence from the hashed edge
     set (keep PDG/data-dependence and call edges). Smallest change — **verify the
     genuine-fix column immediately** (a sanitizer insertion must still flip).
  2. Materialise a real canonical topological re-sort: order data-independent statements
     by WL colour rather than CFG position, then rank.
  3. Hash the edge relation modulo independent-statement order (most faithful, most
     work).
- Do: implement option 1; run the four-sided gate. Escalate to option 2 only on evidence
  (option 1 insufficient or genuine-fix regression), then 3.
- Done-when: Python reorder 4/4 on the 8-seed run **or** the cell is documented as
  dropped with the ladder evidence attached. All R1 gates green; evidence committed.
- Escalates-to: orchestrator with ladder evidence after option 3 if still red — the talk
  then ships 3-of-5 and §8 messaging applies.

---

### Wave 3 — genuine-fix FN fix + hardening (buffer week)

**T3b — Genuine-fix: 7/8 → 8/8**
*Role: implement · Owns: `analysis/fingerprint.py`, `tests/unit/test_fingerprint.py`
(serial after T2).*

- Do: implement the T3a diagnosis — either widen the slice frontier to cover the fix
  site or stop the responsible pass from normalising the fix away. Then hardening: full
  `pytest tests/unit -q`, attestor leg, 8-seed harness, all cells re-verified against
  baseline.
- Done-when: genuine-fix 8/8 on the 8-seed run; no other cell regressed; evidence
  committed. **If 8/8 is unreachable without breaking a should-stay cell, stop and
  escalate — do not trade R2 away.**

---

### Wave 4 — extract method (conditional) + demo lock

**T4 — Extract method: Python 1/4 (spec-blocked, not code-blocked)**
*Gate: starts only if D3 (CLAR-CORE-02 resolution) has happened. Otherwise skipped and
the claim set freezes at four.*

- Context: `_summary_inline_pure_extract` (:371) returns the slice unchanged on purpose —
  normalising a *pure* extract safely needs a purity/alias oracle the minimal CPG model
  lacks, and a heuristic risks normalising an **impure** extract (silently
  auto-suppressing a genuinely-changed finding — the AC-CORE-02b failure). `CLAR-CORE-02`
  is **already filed** (WBS.md:934) — do not re-file.
- Do:
  1. Draft the CLAR-CORE-02 resolution memo (`/clar-resolve` shape): what "pure extract"
     means operationally and what evidence the model must carry before normalising one.
     Human decides (D3).
  2. Only if resolved: implement the narrowest safe subset (likely: single callsite, no
     aliasing of mutable arguments, no writes to enclosing scope), with falsifier cases
     proving an impure extract still flips.
- Done-when: either Python extract 4/4 with the full R1 gate green, or a committed
  `docs/evidence/` note recording the deferral and the exact reason — which W5 turns into
  the "here is exactly why it is hard" slide.

**L0 — Demo-lock run (Fri 23 Oct, serial, one agent).**
Run the 8-seed all-topology harness on the merged state → commit
`docs/evidence/lock-2026-10-23/`. **The claim set freezes to exactly what is green.**
Optionally queue the full 350-pair corpus as an overnight confirmation (it covers the
same 8 topologies; quote only the 8-seed numbers on stage, with the topology-thin caveat
verbatim — CLAR-CORP-17).

---

### Wave 5 — rewrite public material to the locked set (parallel, one file each)

- **DOC-1** — `docs/blackhat-mea-supporting-material.md`: §4 invariance list, §5 demo
  beats, and the §2 diagram must state exactly the frozen set; re-render
  `docs/blackhat-mea-supporting-material.pdf`.
- **DOC-2** — `README.md` + `deploy/README.md`: the "what this path does/doesn't" section
  must match the shipped demo lane after TD-1 (the "staged, not on this path" language at
  `deploy/README.md:16-26` changes if TD-1 lands; the harness section must carry the
  in-image run command from T0.1).
- **DOC-3** — stage slides/abstract-facing language: locked set + topology-thin caveat +
  the extract-method story (shipped or honestly-open).
- **DOC-4** — video audit memo: the submitted video (`youtu.be/IjYhB08JdxI`) shows the
  refactor beat. Audit it against the locked set and write the decision memo for D4:
  re-record, annotate, or leave (only if every beat shown survived the lock).

### Wave 6 — stage demo build (Nov 2–8)

**DEMO-1**: build the demo on the locked set with verified-parsing local fixtures only;
offline end-to-end, twice in a row, from a clean clone (`git clone` →
`docker compose up --build` → all beats scripted and checked). Includes the failure-drill
script (what to say if a beat misbehaves) and the fallback recording shot-list.

### Waves 7–9 — rehearse, release, fallback

- **REL (W8)**: freeze code; tag; publish Cosign-signed images to GHCR (DOCKER-03);
  verify the attendee path on a clean machine: clone → `docker compose up --build` →
  findings; harness in-image command from T0.1 → report.
- **FALL (W9)**: record the offline fallback demo; human rehearses against the
  failure-drill script.

---

## 6. Human decision points (agents draft, humans decide)

| ID | Decision | Needed by | Input |
|---|---|---|---|
| **D1** | RSVP confirmation — deadline was 19 Sep; **today is the 22nd.** If unsent, email Abdulrahman Khaledi now. Nothing else in this plan matters otherwise. | today | — |
| **D2** | Demo-lane architecture: A (worker service, recommended) / B (fat image) / C (identity-lab floor) | end of Wave 0 | T0.4 measurements (parse latency, image sizes) |
| **D3** | Resolve CLAR-CORE-02 ("pure extract") | before Wave 4 | T4 resolution memo |
| **D4** | Submitted-video disposition | Wave 5 | DOC-4 audit memo |
| **D5** | Sign off the frozen claim set | 23 Oct | `docs/evidence/lock-2026-10-23/` |
| **D6** | Confirm repo public flip (OSS-02) — the only irreversible step | before release | OSS-01 scrub green |

---

## 7. Schedule

| Wave | Dates | Work | Exit condition |
|---|---|---|---|
| 0 | Sep 22–27 | T0.1–T0.5 in parallel → G0 baseline → D2 | cached run < 3 min; slice-diff works; honest baseline + demo-smoke committed; D2 decided |
| 1 | Sep 28–Oct 4 | T1 ∥ TD-1 start ∥ T3a | Java FQN 4/4; R1 gates green; demo-lane skeleton up |
| 2 | Oct 5–11 | T2 ∥ TD-1 lands end-to-end | Python reorder 4/4 or documented drop; TD-1 done-when met (else D2→C) |
| 3 | Oct 12–18 | T3b + hardening (buffer for T1/T2 overrun) | genuine-fix 8/8; full suites green |
| 4 | Oct 19–25 | T4 iff D3 resolved · **L0 lock Fri 23 Oct** · D5 | claim set frozen |
| 5 | Oct 26–Nov 1 | DOC-1..4 · D4 | public material states exactly what is proven |
| 6 | Nov 2–8 | DEMO-1 | offline end-to-end ×2 from clean clone |
| 7 | Nov 9–15 | rehearsal + failure drills | timed run-through in slot |
| 8 | Nov 16–22 | REL: freeze, tag, signed GHCR images | reproducible release attendees can run |
| 9 | Nov 23–29 | travel; FALL fallback recording | recording on the laptop |
| — | Dec 1–3 | **Talk** | |

Buffer sits in Wave 3 and Wave 9. T1 and T2 carry the real technical uncertainty;
Wave 0 exists to make them fast. TD-1 carries the second-largest risk and starts in
Wave 1 precisely so a slip surfaces before the lock, not after.

---

## 8. Demo lock (23 Oct) and fallbacks

On 23 Oct, L0 freezes the claim set to exactly what is green; Wave 5 rewrites all
abstract-facing language to match. This converts "we didn't finish" into a deliberate
October scoping decision instead of a discovery in Riyadh.

- **Four of five (extract-method dropped — most likely):** say so plainly. *"Identity
  survives renaming, formatting, reordering and file moves. Extract-method is the open
  one — here is exactly why it is hard, and here is the measurement."*
- **Three of five (reordering slips too):** the talk stands on rename + formatting +
  file-move, plus reproducibility and provenance — both verified in T0.4, not assumed.
  Lead harder on the provenance beat (sign → VERIFIED, tamper → TAMPERED).
- **Demo lane slips:** D2 falls to option C (identity-lab) by 11 Oct at the latest. The
  refactor beat then runs on bundled fixtures through the lab page; the pasted-repo beat
  still shows findings with CWE + origin. Never demo a strong-fingerprint claim through
  the weak-id path.
- **What never happens:** demoing a beat the harness has not proven, on a file you have
  not verified parses, through a fingerprint path the claim does not describe.

---

## 9. Risk register

| Risk | Impact | Mitigation |
|---|---|---|
| Demo path ships the weak location-keyed id (§1.2) while the talk claims refactor-invariance | Talk-ending — contradicts the paper live | TD-1 in Wave 1; D2 with measurements; option-C floor; T0.4 demonstrates the gap explicitly |
| A new pass manufactures genuine-fix false negatives | Highest technical — a fixed bug stays suppressed; what Q&A finds | R1(c)/R2: re-check the column after every change; blocking always |
| Fingerprint change breaks byte-identical reproducibility | Theorem claim dies silently | R1(d): attestor + fingerprint suites in every gate |
| T2 CFG-edge change breaks flip semantics | Reorder and genuine-fix are in direct tension | Option ladder, cheapest first; escalate only on evidence |
| Corpus regeneration (#361) invalidates the baseline | Numbers move mid-plan | G0 re-baseline before any fingerprint.py change |
| Joern parse latency / image size kills the stage demo | Beat 3 unusable live | T0.4 measurements; offline local fixtures; option-C floor |
| Topology-thin corpus (8 topologies, CLAR-CORP-17) | Green cells may not generalise | Caveat verbatim on the slide; never claim beyond the corpus |
| Live demo fails on stage | Talk-ending | W6 offline twice; W9 recorded fallback |
| Extract-method blocked on CLAR-CORE-02 | Plan slips if treated as code work | Scoped as droppable; D3 gate; never build the talk on it |
| Multi-agent merge collisions | Lost work, broken serial lane | Appendix B ownership matrix; §0.2–0.3 |

---

## 10. First three actions

1. **D1: confirm the RSVP was sent** — three days past deadline as of today.
2. Launch Wave 0 in parallel: T0.1, T0.2, T0.4, T0.5 (T0.3 anytime).
3. First use of the T0.1 dump tool: seed-001 `fqn-move-package-rename` before/after —
   settle which of the two T1 candidates it is.

---

## Appendix A — agent report contract

Every agent returns (and the orchestrator re-verifies the done-when commands):

```
task_id, branch, PR #
files changed (must be inside the card's ownership set)
commands run + exit codes
gate results vs baseline (R1 four legs, where applicable)
evidence paths under docs/evidence/
done-when checklist: item → met/not-met + proof
CLAR-*/OOS-* filed (IDs)
deviations from the card, and why
residual risks / follow-ups
status: DONE | BLOCKED(decision ID) | ESCALATED(artifact paths)
```

## Appendix B — file-ownership matrix (collision rules)

| Path | Owner | Mode |
|---|---|---|
| `analysis/fingerprint.py`, `tests/unit/test_fingerprint.py` | T1 → T2 → T3b | **strictly serial, never parallel** |
| `scripts/validate_refactor_fingerprints.py`, `tests/unit/test_validate_refactor_fingerprints.py` | T0.1 (one-line caveat exception: T0.2) | serial in Wave 0, then read-only |
| `analysis/fingerprint_debug.py` (new) | T0.1 | additive only |
| `tests/corpora/refactor/**` | T0.2 | frozen after G0; changes only via a corpus task |
| `deploy/**`, `docker-compose.yml` | TD-* lane | parallel to fingerprint lane |
| `docs/evidence/**` | any | append-only, one dated subdir per run |
| `WBS.md` | any | §17/§18 appends + status flips only (R4) |
| `PLAN.md`, `SDD.md` | none | never (R4; hook-enforced) |
| `docs/blackhat-mea-*.md/.pdf`, `README.md`, `deploy/README.md` | DOC-* lane (Wave 5) | one file per agent |

*Grounding: harness `scripts/validate_refactor_fingerprints.py`; fingerprint passes
`analysis/fingerprint.py:355-449`; corpus defect `tests/corpora/refactor/pipeline/refactor_transforms.py:304`;
demo-path gap `deploy/scanipy_oracle/app.py:199`, `deploy/Dockerfile`, `docker-compose.yml`;
CLARs `WBS.md:934,976,1014`; agent protocol `CLAUDE.md` §11, §14, §15.*
