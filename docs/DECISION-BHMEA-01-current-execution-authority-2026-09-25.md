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
- The live demonstration will run locally using Docker. Actual presentation
  hardware and the exact presentation date are not yet specified.
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

- Describe historical hierarchy text as historical baseline context, and link
  this current decision from `CLAUDE.md` and affected component contracts.
  Do not make a derived file appear to grant itself new authority.
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
