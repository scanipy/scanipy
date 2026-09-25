# R07 pure continuity module

Status: implementation foundation for #378; not R07/R08 acceptance.
Contract: [occurrence and decision lifecycle](OCCURRENCE-DECISION-CONTRACT.md),
especially sections 5–6. Implementation: `services/scan/continuity.py`.

## Authority and immutable inputs

The production policy registry is **empty**. A controlled test policy is not a
reviewed production policy. Both independent R09 artifact descriptors must be
completed, strong, and use the supported graph/slice v2 namespaces; these are
necessary conditions, not sufficient evidence for normalization or suppression.
The module imports R09 descriptors/constants and does not redefine them.

Trusted adapters supply immutable typed inputs, never client-created authority:

- `CohortKey`: exact org, codebase, repository, explicit lineage, origin, engine,
  detector, vulnerability class, language, rule-semantic digest and `s_version`.
  It excludes fingerprints, processing state, strength, source locations/trees
  and environment compatibility so ineligible competitors cannot disappear.
- `OccurrenceView`: actual raw-result digest, capture/tree binding, scan-local
  sink binding, duplicate ambiguity, independent artifact observations and
  optional complete observed `IdentityBinding`. The latter includes identity
  policy, model, normalization, budget, full environment manifest and analysis
  code revision/content digest. An image digest is not a full environment
  manifest. Missing bindings stay absent and ineligible.
- `DetectionInventory`: explicit detection state, seal, exact occurrence ID
  inventory, all supplied records, capture/scope and evidence references.
  `inventory_digest(**fields)` calculates the content binding before construction.
  A constructor rejects duplicate/missing IDs, foreign records and stale digests.
  Digests do not authenticate a producer or prove that a seal includes every
  actual result. Unknown/undecodable detector results must prevent a trusted
  adapter from certifying a completed inventory, not be silently omitted.
- `PolicyDefinition`: nonempty exact supported profiles and review/evidence
  references; no wildcard, implicit upgrade or client approval flag. Its digest
  is SHA256 of ASCII `scanipy-continuity-policy/1`, one LF, and UTF-8 compact JSON
  of the complete dataclass with sorted object keys, no ASCII escaping and no
  nonfinite values. Array order is content and is not normalized away.
- `PolicyRegistrySnapshot`: revision, active/revoked definitions, exact policy
  digests, activation event IDs and every historically used activation ID.
  `validate_registry_transition` requires the next revision, retained policies
  and activation history, and a never-used activation ID on reactivation. The
  persistence layer must authorize and commit this transition atomically.
- `LineageSnapshot`, `PredecessorEntity` and `EntitySnapshot`: explicit ancestry,
  previous entity associations, lifecycle, independent entity decisions and
  revisions, including an explicit monotonic lifecycle generation. No lexical
  commit ordering, global historic search or invented
  entity IDs. Occurrence-only decisions cannot enter the entity channel.

Inventory and occurrence-view hashes use the same compact sorted-key JSON
encoding with respective LF-terminated ASCII domains
`scanipy-continuity-inventory/1` and `scanipy-continuity-occurrence-view/1`.
Inventory occurrence IDs, occurrence records (by ID), and inventory evidence
references are sorted; nested record fields, including their evidence arrays,
remain content-bound. Operational capture/scan/occurrence IDs in these audit
bindings are not canonical structural identities or deterministic SARIF bytes.

## Matching and guards

`plan_continuity` compares one explicit predecessor/current cohort. It returns
one disposition per current occurrence and all unmatched predecessor IDs; it
never deletes, allocates an entity, resolves a finding or proves covered absence.

1. Verify exact scope, lineage, capture/inventory binding and predecessor entity
   associations. Both detection inventories must be completed and sealed.
2. Require an active explicitly selected policy. Account for **all** potential
   competitors before filtering. One weak, failed, pending, unsupported or
   incompletely bound occurrence blocks the whole cohort. Duplicate-result
   ambiguity, several findings at one scan-local sink, or one predecessor
   entity appearing multiple times also block automatic inheritance.
3. Within that closed eligible cohort, group by exact compatibility profile and
   slice digest. Only one predecessor and one current occurrence in a group
   may link. Repeated equal slices are ambiguous, never broken by row order or
   location. Distinct eligible slice groups may link independently.
4. Preserve actual before/after graph digests as evidence but do **not** require
   their equality. Unrelated graph changes need not change the accepted slice.
5. A `LinkProposal` binds current occurrence content, profile, both graph values,
   slice, predecessor/entity and joint lineage, registry/activation, entity,
   decision, lifecycle generation and both inventory revisions/digests. `guards_match` only compares
   proposed preconditions; it is **not** database CAS, locking or authorization.

The adapter must persist link events under a real atomic guard check with
lineage ordering and the approved DB lock discipline. A stored proposal is not
self-authenticating. Historical reappearance lookup and absence/coverage proofs
remain separate lifecycle-coordinator work; zero matches is never resolution.

## Effective decisions

`effective_decisions` accepts only trusted committed links and current authority.
It rechecks policy activation, content/scope, exact profile, entity lifecycle and
minimum snapshot revisions. Withdrawn policy removes inherited effects without
deleting history. Reactivation never revives an old link: explicit re-adjudication
must bind the fresh activation. Unrelated registry changes do not revoke an
otherwise still-active unchanged policy.

Entity decisions are independent verdict and suppression dimensions. Current
human revocation changes only its dimension. False-positive is not suppression.
Direct occurrence decisions override independently; explicit `unreviewed` or
`inactive` shadows inheritance rather than falling through. An absent dimension
means no direct override. Occurrence-only decisions never carry to another scan.
Weak/oracle occurrences can have direct human decisions without becoming eligible
for automatic cross-scan inheritance.

Resolved, reappeared and uncertain entities do not inherit decisions. Every
lifecycle-state change, including returning to open, advances the generation.
Links bind that generation exactly. An originally open link cannot become
effective again after resolve/reappear/reopen or uncertainty/reopen cycles.
A newly adjudicated link in the new generation is also insufficient by itself:
each entity dimension requires its own current-generation human authorization.
Historical active suppression remains inactive until explicitly reauthorized;
a fresh verdict or reference-only event cannot renew it. A link created for a
closed/review-only predecessor also retains its original review-only limitation.
Default effects are unreviewed and inactive; historical records remain available.

### Current lifecycle/human transition contract

This correction is the root-approved #378 lifecycle-generation refinement,
reviewed before implementation. It extends only this pure module; it is not a
claim that the shared persistence/API contract has already been implemented.

- `EntitySnapshot.lifecycle_generation` is explicit and nonnegative. Entity
  `DimensionDecision.authorized_generation` is explicit, nonnegative and may be
  historical (less than the current generation), but never future. Occurrence
  decisions must have `authorized_generation=None`; they cannot become grants.
- `validate_entity_transition(previous, current, lifecycle_event=...,
  human_authorizations=...)` validates one proposed transaction. Target/cohort
  cannot change; entity revision increases exactly once. Lifecycle generation
  increases exactly once iff lifecycle state changes; no same-state increase,
  rollback or jump is permitted.
- State changes require an exact `EntityLifecycleEvent` matching target, cohort,
  previous entity revision/generation, and action. Actions are `resolve`,
  `reappear`, `mark_uncertain` and `open_for_review`. Returning to open requires
  the explicit latter event, not a silent side effect of editing a decision.
  Lifecycle evidence references do not prove covered absence; the coordinator
  must establish that separately. A lifecycle-only transaction preserves every
  decision field and its revision unchanged.
- Human-event transactions increment the decision revision once and require a
  separate typed `HumanAuthorization` for each changed dimension. Its immutable
  event must match exact target/cohort/dimension, new decision revision and
  current lifecycle generation. Unchanged dimensions are preserved byte-for-
  byte. Explicit clears use `unreviewed`/`inactive` events, not deletion. Events
  must be unique within the transaction and cannot reuse a currently retained
  dimension/metadata event ID. Old immutable revision/generation replays fail.
- `ReferenceMetadata` is separate from dimension authorization and has no
  generation-grant field. Metadata additions retain prior references. They may
  advance entity/decision revisions without changing either dimension. Editing
  an old dimension's references or generation through a metadata-only action is
  rejected; it does not count as fresh suppression authorization.
- The current entity snapshot remains bounded; it is not a full event-ID set.
  **Global historical event-ID uniqueness, payload immutability, real human
  authentication, and transactional history/CAS enforcement belong to the
  trusted append-only store.** An `authority_ref` is an inert reference supplied
  by that adapter, not authentication performed by this module. Do not accept
  client-created restamped events or snapshots as authority. The tests explicitly
  use controlled references and do not claim to authenticate them.

Effective reads require both the exact link generation and independently valid
dimension authorization generations. `inheritance_active` is false when no
current-generation human dimension exists; an eligible verdict-only inheritance
does not imply active suppression. Direct occurrence overrides remain local and
independent across all entity generation barriers.

## Verification and remaining work

`tests/unit/test_continuity.py` uses explicitly controlled policies. It exercises
0/1/2 multiplicities and row permutations, all four artifact-class combinations,
ineligible competitors on both sides, each scope/full-binding axis, independent
graph changes, inventory tampering, empty/failed scans, current revocation,
activation-ID reuse, direct clears, weak/oracle boundaries and each guard field.
They additionally cover originally-open links through repeated lifecycle cycles,
fresh links with historical decisions, independent fresh authorizations,
reference-only non-authorization, illegal generation transitions and event replay.
These finite tests prove neither semantic normalization nor detector completeness.

Required integration TODOs, none completed by this module:

- [ ] Authenticate operator policy events and human decisions independently of
  the ranker; enforce append-only event history and scoped runtime DB grants.
- [ ] Produce immutable raw detections before identity and trustworthy complete
  detection inventories, actual full environment/code bindings and evidence.
- [ ] Persist proposals under joint lineage/decision/policy/inventory CAS and
  test stale workers, concurrent revocation and out-of-order/forked scans.
- [ ] Enforce activation transition validation against durable complete event
  history; never accept a client-supplied registry snapshot as authority.
- [ ] Load current decisions/policy on effective reads; test real transaction
  isolation and revocation through API and UI, not just dataclass replacement.
- [ ] Persist lifecycle generations and per-dimension authorization generations;
  invoke transition validation under CAS, enforce globally unique immutable
  human/lifecycle events, and PostgreSQL-test close/reopen and stale-event races.
- [ ] Implement covered-absence, historical reappearance, source retention and
  fenced cleanup, durable retry/finalization, real worker/API/UI projections.
- [ ] Accept the independent normalization/fidelity/corpus/reproducibility gates
  before adding any production policy, then demonstrate actual refactor/rescan
  decision continuity. No controlled policy or successful unit suite enables it.
