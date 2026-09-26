# DECISION-BHMEA-01 — Current Black Hat execution contract

Date: 2026-09-25. Status: current engineering decision for implementation;
repository acceptance remains subject to PR review and tests. Decision owner:
the root engineering coordinator executing the owner's current Black Hat goal.
This is not a claim of a separate human CTO approval or a historical CLAR
resolution. Tracking: #362; documentation/tooling PR #368.

## Context and actual owner directions

The owner identified the submitted supporting material as the promised scope,
asked for a complete LLM-consumable review/action document, and made completing
that review end-to-end the current goal. The owner then clarified:

- Arsenal acceptance/RSVP is already done. There is no demo-lock deadline;
  the presentation will be December 2 or 3, 2026.
- `PLAN.md`, `WBS.md` and `SDD.md` are very old and may contain the old
  architecture; the target is completing the tool for Black Hat.
- The live demonstration will run locally using Docker on the current
  development machine: the owner answered “This machine.” Its observed
  Ubuntu/x86_64 VMware guest and Docker capacity are recorded in the
  [stage-machine observation](evidence/2026-09-25-stage-machine/README.md).
  The exact presentation date and measured acceptance budgets remain open;
  identifying the machine does not establish offline or performance readiness.
- Corrective repository issues/PRs are authorized; merge only after required
  review and tests. Release/image publication and external messages require
  separate authority.

These are directions from the owner, not authority invented by a derived
component document. The current [handoff](PLAN-BHMEA-EXECUTION-2026-09-25.md)
and [full review](REVIEW-BHMEA-EXECUTION-ACTION-ITEMS-2026-09-23.md) implement
them. The [submitted material](blackhat-mea-supporting-material.md) is retained
unchanged; its scope is not reduced by this record.

## Decision and boundaries

1. Execute the full submitted scope: all C01–C18 claims and applicable R01–R20
   acceptance items. A partial repair, reduced demo, or inherited DONE label
   does not establish that scope. Record contrary results and unmet work.
2. Preserve `PLAN.md`, `SDD.md`, `WBS.md` and existing CLAR history unmodified
   by this decision. They remain historical architecture/traceability inputs;
   compatible safety, data, signature and test contracts still apply. Do not
   silently mark old approvals resolved or restore retired cloud dependencies.
3. Record current necessary extensions in explicit engineering contracts with
   tests. The current task does not require the owner to re-approve obsolete
   architectural restrictions before ordinary corrective work can proceed.
   A materially different scope, new external authority or spending still
   requires owner direction.
4. Keep all required repository test/review gates, including canonical
   `claude-review` APPROVE, before merge. A decision record is not a bypass or
   evidence that any technical acceptance criterion has passed.
5. Keep technical acceptance, public release and offline stage readiness
   separate. No October lock or automatic scope downgrade applies. No release,
   image publication, organizer message, visibility change or spending is
   authorized here.

## Explicit implementation extensions covered

| Scope | Current decision | Compatibility / acceptance boundary |
|---|---|---|
| R01/R17 handoff and evidence | Add the full review, ledger and structural checker; preserve original evidence bytes with corrected interpretation | A valid ledger or recovered report is not feature acceptance |
| R04 report acceptance | Add a typed semantic report checker and reviewed policy, distinct from the historical four CI gate jobs | Existing four gates remain; G0 validity cannot substitute for G2 acceptance; protect case coverage/history and expected analysis revision |
| R08 deployment | A separate Joern analysis worker, immutable same-source handoff and explicit asynchronous status | Root's engineering choice within the target, not a literal owner option-selection; preserve detected occurrences through identity failures |
| R09 artifact metadata | Independent graph/slice classes, versioned serialization/signatures, additive migration and explicit missing-evidence semantics | This is one coherent cross-component compatibility change; do not fabricate metadata or weaken historical signed-byte verification |
| R18/R19/R20 analysis foundations | Content-binding canonical identity, deterministic work budgets, explicit timeout failure, typed graph/call/return/effect semantics | New semantic roles require versioned identities; canonical strength is not proof of purity or full source fidelity |
| R07 durable decisions | Separate occurrences, persistent entities and decision history with fail-closed inheritance | Weak, ambiguous, incompatible or failed analysis cannot silently inherit suppression or establish a fix |

The atomic R09 boundary necessarily spans the worker, finding model/migration,
SARIF and provenance consumers. Splitting incompatible writers/readers merely
to satisfy an old one-component title convention would not be safe. Its PR
must identify the affected components, preserve old records and test the
combined contract; it must not claim all missing producers already exist.

Detailed behavior remains in the linked review, active handoff and versioned
component/implementation contracts. This decision does not certify proposed
Joern APIs, an unfinished solver, extraction purity, actual stage budgets or
empirical claims. Those require their own real evidence.

## Operational consequences

- Link this scope-specific current decision from `CLAUDE.md` and affected
  component contracts without globally relabeling the repository hierarchy.
  Preserve active general instructions for unrelated work. The owner's current
  directions, not a derived file granting itself authority, define this task.
- Use narrow corrective issues and independent worktrees. Board status must
  reflect actual ownership; if API synchronization fails, record that failure
  and exclusive local assignment rather than inventing Done or duplicate work.
- Preserve the user's untracked files and existing app/database. Never execute
  scanned source, target build hooks/tests or commands supplied by scanned
  repositories. Trusted Scanipy implementation tests/hooks remain required.
- Re-run affected checks on the combined merged artifact. In-flight library
  tests are not a complete Black Hat acceptance result.

No full R-task, submission claim or shared G0/G1/G2/G3 gate is marked complete
by this decision. The original supporting material and the complete TODOs
remain the acceptance target.

## Tenant-local authority and later publication extensions

Root's engineering clarification during Revision 15 preparation on September
25 preserves the complete submitted scope; it is not separate human approval
or a change to the original submission/backlog. The
[submission's deployment section](blackhat-mea-supporting-material.md#6-the-deployment)
expressly promises self-hosted **single-tenant** Postgres. The
[claim ledger](REVIEW-BHMEA-EXECUTION-ACTION-ITEMS-2026-09-23.md#3-completion-modes-and-claim-ledger)
retains that C12 promise, C11's actual signed provenance, C13's real findings/UI
and C14's Semgrep/CodeQL paths. Full R09/R10/R12 and the other existing TODOs
require actual accepted inputs and producers; they do not require cross-scope
global-publication adoption or statistical/LLM spec inference as prerequisites.

In particular, R10 requires a genuinely accepted spec with `LLM_TRIAGE=off`;
R11 measures empirical **oracle reproduction**, not inferred-rule precision.
R07's durable decisions do not permit LLM detection writes. These existing
requirements remain in the unchanged
[complete task inventory](REVIEW-BHMEA-EXECUTION-ACTION-ITEMS-2026-09-23.md#5-prioritized-task-inventory),
not replaced by an extension's acceptance tests.

The required runnable path remains genuine **tenant-local accepted builtin
content and publication**, exact immutable bytes and versions, current authority,
full provenance and independent verification, and the real scan/lifecycle/UI
workflow. All declared Java/Python semantics, CodeQL/Semgrep, real measurements,
no-execution, release and stage obligations remain. Fixture keys, caller-supplied
hashes, local codecs or synthetic signatures do not satisfy those requirements.

Cross-scope global-publication-to-tenant adoption and statistical/LLM
inferred-spec publication are **later extensions, not Black Hat acceptance
gates or blockers of the tenant-local target**. Derived resolver roadmap rows
that grouped those extensions with required signed/UI work do not expand the
submission. Existing global publication structure and historical records remain
intact. The current customer-only execution, scope, signature and admission
guards must not be removed to make a global fixture pass; a real cross-scope
extension needs its own coordinated owning-schema/authority design and tests.
The known global `SqlLedger.create()` tenant-org fixture defect remains recorded
as extension-path work; changing that fixture alone cannot enable the currently
unsupported owning protocol.

Likewise, a known inferred proposal cannot be relabeled builtin to avoid its
separate statistical acceptance rules. Preserve existing Gate 4, INV-3, CI tests,
signing meanings and all related guards unchanged. This clarification allocates
no source changes or runtime/operator installation and does not resolve those
extensions' designs. Every original R01–R20 checklist, C01–C18 state, milestone
and DAG edge remains unchanged. Current work queues should prioritize the full
tenant-local target without inserting either extension as an invented gate.

## Local-demo human roles — owner clarification, September 26

The project owner answered **“Me, for both local-demo roles”** when asked who
should approve detector/rule bundles and authorize recovery after a database
restore. The same project owner fills both human roles for the **local demo**.
Do not ask again who fills these roles. No two-person separation is assumed;
independent freshness/checkpoint verification still requires its own technical
evidence and is not satisfied merely by assigning two role names to one person.

This is human role assignment, not authentication of an operating-system or
application principal, selection of key fingerprints, persistent trust setup,
approval of a particular bundle or restore execution, or proof of current
authority/recovery. It does not authorize release/image publication, external
messages, spending, modification of the existing user database, or reduced scope.
Older statements that the responsible human is unknown are superseded on this
point only. Their remaining technical and safety prerequisites still apply.

Before persistent local-demo enablement, the executing LLM must:

- [ ] Bind the confirmed owner to the actual authenticated local principal and
  record the separate bundle-approval and restore-recovery scopes. Do not infer
  that identity from the current shell account or invent a name or identifier.
- [ ] Record and verify the chosen persistent public-key fingerprints, publisher
  scope, private-key custody and rotation/revocation procedure. Test-only keys
  remain test-only; this answer is not a key-generation/installation approval.
- [ ] Resolve and implement the independent admission/checkpoint, renewal and
  trusted-clock policy, including restored/old-parent exclusion. Preserve
  fail-closed checks until the real providers and stored state are verified.
- [ ] Require the owner's explicit approval for the actual bundle or recovery
  action when needed; role eligibility alone is not an approval event.
- [ ] Exercise restore/recovery on an isolated local-demo fixture, verify fresh
  authority and exclusion of stale grants, and retain the actual evidence before
  promoting recovery or stage readiness. Keep the existing user app/DB intact.

All original R01–R20 TODOs, C01–C18 statuses, shared gates and historical cutoffs
are preserved. Safe source/test implementation can continue while these
operational prerequisites remain unresolved.
