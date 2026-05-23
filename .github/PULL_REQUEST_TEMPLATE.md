## CMP reference

<!-- One CMP-* per PR. e.g. CMP-SCM-01 -->
**Component:** CMP-

## Summary

<!-- What does this PR implement? One paragraph. -->

## Acceptance criteria covered

<!-- List the TST-AC-* tests that are now green. -->
- [ ] TST-AC-

## Pre-flight checklist

### Scope
- [ ] PR title follows `<type>(CMP-<id>): <subject>` format
- [ ] All changed files are within the allowed edit paths for this CMP
- [ ] `PLAN.md` and `SDD.md` are untouched
- [ ] `WBS.md` changes are limited to: status flip, new CLAR-*, new OOS-*
- [ ] No other components' `tests/` files changed

### Invariants
- [ ] INV-1: Every `Finding` sets `origin` to `"deterministic-core"` or `"oracle-passthrough"`
- [ ] INV-2: `S_version` and `env_digest` sourced from runtime context, not hardcoded
- [ ] INV-3: No LLM output can mutate `origin` or detection-content fields (N/A if not touching triage/Attestor)
- [ ] INV-4: CW-DETECT safe direction verified (N/A if not touching CMP-SNAP-03)
- [ ] INV-5: `cpg_order_hash` carries `# canonical iff fingerprint_class = strong` annotation
- [ ] INV-6: No (class, language) pair in Alg-2 bench before CPG-fidelity gate passes

### Provenance threading
- [ ] All four fields present on every `Finding` emission: `origin`, `S_version`, `env_digest`, `cpg_order_hash`
- [ ] No field set to `None`, `""`, or `"unknown"`

### Tests
- [ ] All `TST-AC-<id>-*` pass in CI (link to green run below)
- [ ] All `TST-INV-*` for this component pass
- [ ] No falsifier test thresholds weakened

### Security sign-off (required for CMP-CP-02, SNAP-03, SNAP-04, DET-01, TRI-01..03)
- [ ] Security Analyst reviewed and approved (or N/A)

### Code quality
- [ ] `ruff check` passes (no unreviewed suppressions)
- [ ] `mypy --strict` passes
- [ ] No new credentials or secrets committed
- [ ] No `TODO` comments except `TODO: CLAR-<NN>`

## CI run link

<!-- Paste the link to the green CI run -->

## WBS + board status (RULE-11)

<!-- After merge, WBS.md status AND the Project board (#5) Status are flipped to DONE by the WBS Sync Agent via scripts/board.sh. -->
- [ ] Issue linked above with `Closes #<n>`
- [ ] Board Status set to `In Progress` while this PR was open (`scripts/board.sh set <n> "In Progress"`)
- [ ] Post-merge: WBS.md → `DONE` and `scripts/board.sh set <n> Done` (only when all TST-* green + Code Review approved)

Current status: IN-PROGRESS → **DONE** (post-merge)

## Open CLAR-* items discovered

<!-- Any new CLAR-* items discovered during implementation -->
None

## Reviewer

@<!-- tag Code Review Agent or team member -->
