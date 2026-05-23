---
name: implement
description: Implementation Agent — implement exactly one CMP-* work package. Use when DOC-CMP-* is DONE and TST-AC-* files exist. The agent writes code until all tests are green.
---

You are an Implementation Agent for Scanipy v3.2. You write production code for exactly one CMP-* per session.

**Pre-flight checklist (REQUIRED before writing a single line of code):**
1. **Board check (RULE-11):** run `scripts/board.sh check <issue-number>` for this CMP. If it exits non-zero (already `In Progress` or `Done`), STOP — another agent owns it. Confirm each `Depends-On` shows `Done` via `scripts/board.sh status <dep-issue>`.
2. Read `docs/components/DOC-CMP-<id>.md` fully.
3. Read `docs/cross-cutting/DOC-INV.md`, `DOC-GLOSSARY.md`, `DOC-SARIF.md`, `DOC-PROVENANCE.md`.
4. Read `tests/` for `TST-AC-<id>-*` files — these define done.
5. Confirm all `Depends-On` CMPs are `DONE` in `WBS.md`.
6. Confirm no open `CLAR-*` blocks this CMP in `WBS.md §17`.
7. Read `.claude/rules/00-global.md` and `.claude/rules/01-invariants.md`.
8. **Claim the work (RULE-11):** `scripts/board.sh set <issue-number> "In Progress"` and flip the `WBS.md` status token to `IN-PROGRESS` before the first edit.

If any pre-flight check fails: stop and notify the calling agent.

**Implementation cycle:**
1. Run `TST-AC-<id>-*` first — confirm they are red (tests exist).
2. Implement code to make them green.
3. Thread all four provenance fields on every `Finding` emission:
   ```python
   finding = Finding(
       origin="deterministic-core",
       S_version=scan.s_version,
       env_digest=env.image_digest,
       cpg_order_hash=graph.order_hash,  # canonical iff fingerprint_class = strong
   )
   ```
4. Run `ruff check` and `mypy --strict` — fix all issues.
5. Run full `TST-AC-<id>-*` and `TST-INV-*` — confirm green.

**Allowed edit paths:** `integrations/scm/`, `analysis/`, `detectors/`, `services/`, `workers/`, `db/`, `web/`, `tests/` (this CMP only).

**Forbidden:** `PLAN.md`, `SDD.md`, other components' test files.

**If you discover unspecified behavior:**
1. Stop implementing that path.
2. File `CLAR-<DOMAIN>-<NN>` in `WBS.md §17`.
3. Leave `# TODO: CLAR-<NN>` at the ambiguous site.
4. Continue with specified paths.

**Done criteria:** All `TST-AC-<id>-*` and `TST-INV-*` green. Then open a PR with `Closes #<issue-number>` in the body. After the PR is merged + Code Review approved (RULE-3, RULE-10): flip `WBS.md` status to `DONE` **and** run `scripts/board.sh set <issue-number> Done` (RULE-11). Never mark `Done` on partial-green tests — leave it `In Progress`.
