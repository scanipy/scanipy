# Proposed canonical identity and reproducibility contract for BH MEA

| Field | Value |
|---|---|
| Status | Core library direction adopted for implementation; component verification outstanding |
| Date | 2026-09-25 |
| Proposal revision | 1 |
| Backlog scope | R18 canonicalization; R20 budget/reproducibility; interfaces to R02/R06/R07/R09/R10/R12/R19 |
| Objective | Fulfill the complete submitted functionality; no implicit reduced-scope mode |
| Inspected code baseline | `940d440cb99e23131d28ee5bbb1655ea29d46a58` |
| Review state | Root technical review recorded in the 2026-09-25 handoff; not a human approval or completion claim |

Adoption boundary: [the current handoff](PLAN-BHMEA-EXECUTION-2026-09-25.md)
adopts the content-binding canonical encoding, complete bounded search,
deterministic work-budget exhaustion, explicit time failure, and independent
artifact/version boundaries. Source-aware weak fingerprints require a real
source digest; source-less compatibility calls must remain explicitly legacy.
Graph-role expansion, complete SARIF migration, and real-runtime performance
remain implementation/verification work, not facts established by this proposal.

## 1. Decision requested and authority boundaries

The root agent should review, amend, or adopt the concrete version-2 contract
below for implementation. It replaces an unsound canonical-labeling mechanism and separates
deterministic successful analysis from unsuccessful wall-clock termination.
It also defines a genuinely reproducible SARIF artifact independently of scan
attempt bookkeeping. These are proposed semantics, not interpretations that an
implementation agent may silently impose on the existing contracts.

The user clarified on 2026-09-25 that `PLAN.md`, `SDD.md`, and `WBS.md` are old and
may describe an obsolete architecture: completing Black Hat is the target.
The submission, remediation backlog, and latest user direction are therefore the
active contract. Preserve legacy files and historical CLAR records, but do not
block local implementation on their old architecture or approval gates. They are
evidence of past behavior and migration obligations, not vetoes over the active
task. Record the adopted design and its tests; do not falsely mark old CLARs
resolved or claim a human approval that was never given.

Implementation and the corrective issue/PR workflow are authorized by the
owner's current instructions. Merge only after required review and tests pass.
This document adds no authority for releases, external messages, visibility
changes, new spending, or reduced submission scope. Root review coordinates the
interdependent library, schema, worker, and history changes; it is not a new
user-permission barrier for ordinary in-scope implementation.

The full [submission](blackhat-mea-supporting-material.md) and
[remediation backlog](REVIEW-BHMEA-EXECUTION-ACTION-ITEMS-2026-09-23.md) remain the
acceptance scope. This document cannot close either R18 or R20 by being written.
Correct graph canonicalization alone does not prove real-source refactor
invariance, interprocedural fidelity, purity, finding continuity, or attestation.

## 2. Evidence motivating the decision

### 2.1 Source and contract evidence

| Evidence | Current source | Consequence |
|---|---|---|
| Lowest-ID individualization and ID-dependent marker | `analysis/ordering.py::_individualise_refine` | A single arbitrarily numbered branch is labeled strong without canonical branch selection. |
| Only ordered raw IDs enter graph digest | `analysis/ordering.py::_digest_order`; `DOC-CMP-CORE-03` Appendix A | Distinct labeled graphs can receive the same strong digest without a cryptographic collision. The derivative pseudocode also needs correction. |
| Time chooses successful strong versus weak output | `analysis/ordering.py::canonical_order`; `DOC-CMP-CORE-03` sections 3.1 and 7.1 | Same-input purity conflicts with the mandated successful weak result on wall-clock skew. |
| Discrete early returns omit deadline checks | `analysis/ordering.py::canonical_order` | The implementation can return strong after its stated T expires. |
| Auxiliary normalization loses class and starts a fresh default budget | `analysis/fingerprint.py::_alpha_rename_locals`, `compute_slice_fingerprint` | A weak internal result can affect content while the final result is labeled strong. |
| Unconditional same-source order/hash claim | `PLAN.md` Algorithm 5, honest-labeling ledger; `DOC-ALGS` section 6 | Two successful identity outcomes cannot be justified by merely pinning the numeric T value. |
| Per-node refinement formula labeled 2-WL | `DOC-CMP-CORE-03` section 3.2; `analysis/ordering.py::_wl_refine_to_fixpoint` | Name the actual mathematical algorithm honestly. The active submission says WL refinement, not specifically 2-WL. |
| Attempt UUIDs included in canonical Run bytes | `analysis/sarif/canonical_emit.py::_build_run`; `DOC-SARIF` section 5 | Fresh attempt IDs conflict with byte-identical whole-Run output unless the artifact/replay contract changes explicitly. |
| Graph/slice classes have distinct producers | `DOC-CMP-CORE-02` section 3.3; `WBS.md` CLAR-ORCH-03 | An approved R09 schema must preserve both verdicts. |

The node-partition signature currently compares changing hash bytes rather than
partition equivalence. The proposed algorithm below detects partition refinement
directly. It must not reproduce that implementation detail as a definition.

### 2.2 Controlled diagnostics reproduced on 2026-09-25

These are synthetic-graph library diagnostics, not Joern, language-support,
refactor-corpus, latency, or production-timeout measurements. No files were
modified by the diagnostics. The full original permutation and clock reproduction
commands are in section 8 of the remediation backlog.

1. Six insertion permutations of two identical source CALL nodes pointing to a
   sink CALL, with T=10 seconds, produced **two slice hashes, all strong**:
   `f314ca14270fa89efa24c79d301849f7ca8159673c733e8be5f0df0c9ae52e3b` and
   `6099ab99ff39fa353de3a460f6c7ce3ada84321d8ca86e3be997d8943f6d3452`.
2. Mocking `analysis.ordering.time.monotonic` with fast and slow deterministic
   clocks changed successful slice class/hash and graph class/order/hash at the
   same default B/T. This establishes elapsed-time dependence, not its frequency.
3. A single-node graph labeled `SOURCE` and one labeled `UNRELATED` both returned
   strong graph digest
   `af5570f5a1810b7af78caf4bc70a660f0df51e42baf91d4de5b2328de0e83dfc`.
   Their raw ordered-ID encoding is identical; SHA-256 is not the defect.
4. A one-node discrete graph under a clock advancing one second per call returned
   strong with `elapsed_ms=1000.0` despite T=0.2.

Additional diagnostic reproduction, from the repository root:

```bash
python3 -B - <<'PY'
from unittest.mock import patch
import analysis.ordering as ordering

class Clock:
    def __init__(self):
        self.value = 0.0
    def monotonic(self):
        current = self.value
        self.value += 1.0
        return current

for label in ("SOURCE", "UNRELATED"):
    graph = ordering.CPG()
    graph.add_node(label)
    result = ordering.canonical_order(graph)
    print(label, result.fingerprint_class, result.cpg_order_hash.hex())
    with patch.object(ordering, "time", Clock()):
        result = ordering.canonical_order(graph, T=ordering.Duration(0.2))
    print("expired", result.fingerprint_class, result.elapsed_ms)
PY
```

### 2.3 Completion and ownership evidence

Live board checks on 2026-09-25 found CMP-CORE-03 issue #20 **Done**, while
subissues #90 refinement, #91 bounded IR, #92 fallback, and #93 hash/annotation
are **Todo**. Issue #20's legacy check refuses pickup. These statuses are historic
coordination evidence, not completion proof or a blocker under the user's updated
direction. The root agent coordinates local corrective ownership; do not reopen,
claim, or otherwise mutate remote issues without the requisite workflow authority.

`tests/unit/test_core_specs.py::test_core_03a_cfi_symmetric_terminates_in_budget_deterministic`
does not assert an elapsed bound or search-state count. Its bipartite symmetry
fixture is useful but is not evidence covering an entire hard-graph family.
`tests/integration/test_core_specs.py::test_core_03b_budget_exhaustion_rate_under_1pct`
remains an unconditional skip. No empirical gate is discharged.
System `python3 -m pytest --version` reported pytest unavailable during this audit;
implementation must prepare an isolated approved test environment.

## 3. Proposed versioned artifact model

Proposed fixed names:

| Name | Meaning |
|---|---|
| `scanipy-canonical-graph/2` | Canonical labeled directed multigraph encoding defined below |
| `scanipy-slice-normal-form/2` | R02/R06-approved semantic slice projection consumed by that encoding |
| `scanipy-canonical-search/2` | Refinement and complete individualization search below |
| `scanipy-budget-policy/2` | Deterministic B exhaustion versus explicit T failure |
| `scanipy-canonical-sarif/2` | Reproducible artifact boundary in section 7 |
| `scanipy-provenance-chain/2` | Explicitly versioned binding of artifacts, classifications, and attempts |

An implementation identifier is not evidence of correctness. Immutable manifest
digests must accompany these names. Record mapper/export model version, semantic
normalization version, search version, budget configuration, accepted spec-set
digest, and complete analysis-environment identity through R09.

For each hash store a self-contained descriptor:

```json
{
  "namespace": "scanipy-canonical-graph/2",
  "hash": "<64 lowercase hexadecimal characters>",
  "fingerprint_class": "strong",
  "annotation": "canonical iff fingerprint_class = strong"
}
```

This is proposed schema content, not implemented JSON validation. The descriptor
containing the graph hash owns the graph verdict. A distinct descriptor owns the
slice verdict. The literal annotation can retain its existing spelling because
`fingerprint_class` is local to each descriptor. There is no ambiguous shared
top-level class. Coordinate the R09 implementation contract for this representation
with flat database and SARIF fields; CLAR-ORCH-03 is historical problem evidence,
not a new approval gate.

`origin` remains independent: oracle findings never become deterministic-core
merely because their structural identity is strong. An unavailable oracle graph
is not an empty graph and cannot use the empty-graph digest; CLAR-ORCH-12 remains
an independent required decision.

## 4. Exact graph encoding proposal

### 4.1 Input graph and identity equivalence

Input is a finite directed, edge-typed multigraph. Node IDs are unique opaque
lookup keys. Every edge references existing nodes. Self-loops and duplicate
typed edges are retained. Reject malformed references, unsupported semantic
labels, duplicate node IDs, invalid strings, and unsupported model versions;
never downgrade malformed data to weak.

For the current model, a node's semantic label is the ordered tuple:

`(kind, operator_or_literal, resolved_fqn, enclosing_decl_fqn)`.

The R19 model may add semantic properties only through a reviewed projection
version. Raw IDs, file paths, line/column positions, AST traversal positions,
creation order, and `structural_path` are excluded from strong graph encoding.
If any such field is necessary to preserve semantics, encode the required
semantic relation explicitly instead of smuggling source position into identity.

Graph isomorphism here means a bijection preserving these semantic labels and
directed typed-edge multiplicities. It does not mean arbitrary program equivalence.
Whole-CPG FQNs may change across package moves; the advertised refactor-stable
finding identity is computed from the separately approved **normalized slice**.
Do not advertise whole-CPG hashes as unchanged under every refactor merely because
they are canonical for their input labeled graph.

### 4.2 Unambiguous byte format

Use these primitives; do not use `repr`, JSON float formatting, locale collation,
or Python object hashing:

```text
U64(x) = exactly 8 bytes, unsigned big-endian; reject x outside [0, 2^64)
TEXT(s) = U64(len(UTF8(s))) || UTF8(s)
          UTF-8 is strict; no Unicode normalization is silently performed
LABEL(v) = TEXT(kind) || TEXT(operator_or_literal)
           || TEXT(resolved_fqn) || TEXT(enclosing_decl_fqn)
```

For a candidate total order `p = (v0, ..., v(n-1))`, let `rank(vi)=i`:

```text
ENCODE(G,p) = ASCII("SCANIPY-CANONICAL-GRAPH/2\n") || U64(n)
              || LABEL(v0) || ... || LABEL(v(n-1))
              || U64(m)
              || concatenation of [TEXT(kind) || U64(src_rank) || U64(dst_rank)]
                 sorted lexicographically by (UTF8(kind), src_rank, dst_rank)
```

Each duplicate edge contributes an entry. The node count, field length framing,
and edge count make boundaries explicit. The empty graph has the encoding's
header/counts, not the legacy `sha256(b"")` digest.

For a strong graph result:

`cpg_order_hash = SHA256(ASCII("SCANIPY-CPG-STRONG/2\n") || canonical_bytes)`.

For a strong normalized-slice result:

`slice_fingerprint = SHA256(ASCII("SCANIPY-SLICE-STRONG/2\n") || canonical_bytes)`.

The strong digest excludes source commit, B/T, S_version, and Env values so these
do not themselves destroy structural identity. Their provenance and compatibility
checks remain mandatory outside the digest. Changing the graph projection or
encoding changes its namespace; optimization that provably preserves the exact
encoding need not change the structural namespace, but must change the recorded
implementation identity and trigger regression/attestor checks.

## 5. Canonical-search semantics and correctness obligations

### 5.1 Refinement with precisely defined colors

Intern structured signatures by their lexicographically sorted unique values,
assigning contiguous integer colors from zero. Use the framed values, not a
digest as the equality authority; cryptographic collision assumptions belong to
the final digest, not to graph partition correctness.

The version-2 reference implementation uses **direction-aware vertex refinement
(1-WL)** followed by complete bounded individualization search. This matches the
active submission's WL-plus-IR mechanism. It is not called 2-WL and does not adopt
the obsolete pair-refinement requirement merely because an older component
document named it. Strong canonicality comes from invariant refinement plus the
completed canonical search, not from assuming WL distinguishes every graph.

Initial vertex signatures contain the semantic label and individualization marker
(`0` for unmarked, then positive depth markers). Intern them in bytewise label
order and integer marker order. For every subsequent round, simultaneously compute:

```text
C_next(v) = INTERN(
    C(v),
    SORT_MULTISET((UTF8(edge_kind), C(u)) for every incoming edge u -> v),
    SORT_MULTISET((UTF8(edge_kind), C(w)) for every outgoing edge v -> w)
)
```

Self-loops contribute to both incoming and outgoing multisets. Duplicate edges
contribute duplicate entries. Compare colors/signatures structurally; sort each
fixed-shape tuple lexicographically with integers compared numerically.

Stop when the vertex partition no longer splits. Since the old color is part of
the signature, refinement cannot merge cells; unchanged cell count is sufficient
to detect this stopping condition. This avoids comparing unstable hash strings.
There are at most n-1 strict partition splits; a stable partition need not be
discrete. Building adjacency requires O(n+m) storage, and refinement visits typed
adjacency with sorting overhead per round. Search cost may still be exponential;
there is no universal within-budget strong-success guarantee. Performance targets
remain real measured acceptance requirements, not deductions from this algorithm.

### 5.2 Complete individualization search

At the root, no vertex is individualized. At every visited state:

1. Consume one search-state unit from the shared B budget, including the root.
2. Refine using the vertex procedure in section 5.1.
3. If every vertex color is distinct, order vertices by ascending
   color and compute `ENCODE(G,p)` as a leaf certificate. Individualization
   markers and refinement colors themselves never enter `ENCODE`.
4. Otherwise select the non-singleton color cell minimizing
   `(cell_size, color)`. Visit a child for **every** member, marking
   that member with the same next-depth marker in its respective child.
5. At each child preserve earlier markers and restart the prescribed refinement.
   A marker encodes depth, never the selected raw ID or source position.
6. Select the lexicographically smallest leaf encoding after the entire search
   finishes. No unproved symmetry pruning, early best-so-far success, or omitted
   branches are permitted in the reference implementation.

Child visitation may sort raw IDs for same-input repeatability: it cannot affect
the minimum of a completed tree. If the budget cannot visit the entire tree,
discard partial certificates and take the deterministic weak path. Strong must
never mean merely that one branch became discrete. Root/child budget accounting
must be exact, independent of dictionary iteration and wall-clock timing.

When multiple orders produce the identical minimum encoding, use the
lexicographically smallest raw-ID tuple only to select the returned mapping.
The mapping itself is not an isomorphism-invariant byte sequence. On graphs
with automorphisms there need not be a unique distinguished vertex. Consumers
must use canonical encoded structure, not hash that arbitrary mapping as the
canonical identity. Same-source deterministic ordering still requires stable
upstream node identities; R19/mapper validation remains necessary.

### 5.3 Correctness argument to be reviewed

Subject to correct implementation and the declared labeled-graph model:

- Isomorphism preserves initial signatures and every refinement round by
  induction; hence it preserves colors, partitions, and target-cell selection.
- Corresponding individualized children use the same depth markers. Thus
  isomorphism gives a bijection between the complete search trees and their
  leaf encodings. Completed trees have the same minimum encoding.
- Equal full encodings reconstruct equal labeled directed multigraphs in rank
  space, giving an isomorphism. Changed graph structure cannot be erased by the
  encoding. SHA-256 equality additionally relies on its collision resistance.
- Without pruning, corresponding completed trees have equal search-state counts.
  B completion versus exhaustion is therefore independent of node relabeling.
- Selecting one mapping among equal minimum encodings does not affect the bytes.
  It must not be mistaken for a canonical identification of symmetric vertices.

This is an argument about canonicalization, not a proof that R02/R06's semantic
normalization maps exactly the intended refactors to isomorphic graphs. Their
proof obligations, real-source evidence, and negative controls remain separate.

## 6. Deterministic work budget and explicit wall-clock failure

### 6.1 Proposed policy

Keep the existing numeric defaults: **B = 65,536 search states; T = 200 ms**.
Reject non-integer/non-positive B, non-finite/non-positive T, and booleans supplied
as numeric budgets. A state may be entered only if another B unit is available.
Completing exactly B visited states is allowed; needing state B+1 exhausts B.
The versioned configuration represents T as integer `deadline_ns=200000000`,
not a floating-point JSON number. Any compatibility adapter accepting seconds
must document exact conversion and reject unsupported sub-nanosecond precision.

B bounds search-tree work; deterministic refinement inside each state is finite
but is not one constant-time CPU operation. Do not present B as an instruction
budget. T protects the full canonicalization invocation, including validation,
refinement, nested normalization, candidate encoding, and fallback construction.
Shared slice-budget accounting must not restart at each normalization call.

Proposed outcomes:

| Condition | Result | Allowed downstream effect |
|---|---|---|
| Entire canonical search completes within B and before T | Successful strong artifact | Eligible for R09/R07 compatibility checks; not automatic suppression by itself |
| Next required state would exceed B, and deterministic fallback finishes before T | Successful weak artifact | Persist with its own class; no cross-refactor decision inheritance |
| T expires anywhere, including during fallback or before publishing an early return | `CanonicalizationDeadlineExceeded` | Attempt incomplete/failed; no successful analysis artifact published |
| Invalid graph/configuration | Typed validation error | Attempt fails; no invented weak artifact |
| Worker killed/crashes/loses completion acknowledgment | Incomplete attempt | No fixed-finding inference, no successful attestation |

The deadline is measured once with a monotonic clock. Check before and after
potentially substantial phases and immediately before committing a successful
result; a supervised worker watchdog additionally terminates overdue work.
Cooperative checks cannot promise OS scheduling/preemption or zero termination
overhead at exactly 200 ms. Report actual elapsed/termination latency separately.
The enforceable semantic promise is **no successful result whose completion
missed T**, not an impossible real-time scheduling guarantee on arbitrary hosts.

At a race between B exhaustion and T expiry, T failure wins. A later retry with
the same logical inputs/configuration may succeed but must produce the same
successful identity as every other successful attempt. Do not silently increase
T/B, switch algorithms, reuse an earlier partial candidate, or route a failed
core attempt to oracle success under the same logical-run identity.

The API must distinguish deterministic semantic result fields from observational
telemetry. A result object containing `elapsed_ms` is not a pure same-input value;
do not retain that old claim in function or component documentation. The guarantee
applies to the defined successful semantic payload, while telemetry and explicit
attempt failure are represented separately.

### 6.2 Deterministic weak artifacts

Fallback cannot use partially individualized labels: the stopping branch must
not influence weak output. From the original unmodified input, order by the
tuple `(sha256(enclosing_decl_fqn UTF-8), structural_path UTF-8,
sorted incident-edge-kind multiset, semantic label, raw node ID)`.
Compute the same framed graph encoding in that order, but use the domain
`SCANIPY-CPG-WEAK/2\n` and persist class weak. Its scope is same-source only.

For the slice fallback, hash a separately framed source-scoped witness encoding:
domain `SCANIPY-SLICE-WEAK/2\n`, source-tree digest, node-count, original mapped
node IDs in witness order, and for each consecutive pair the sorted typed-edge
multiset connecting it in that direction. Reject disconnected witness steps.
Concretely, concatenate the ASCII domain, 32 raw digest bytes, `U64(node_count)`,
the `U64(node_id)` sequence, and for each consecutive pair `U64(edge_count)`
followed by its UTF-8-sorted `TEXT(kind)` entries including duplicates.
A single sink-node locator is explicitly a length-one witness, not a fabricated
source-to-sink flow proof. O(witness length) construction requires a precomputed
adjacency index with bounded supported edge kinds; include index construction
in measured pipeline cost rather than hiding it in the fallback claim.

The source identity and graph/witness inputs must be provided through typed
interfaces. This extends the current `SliceRequest` surface and requires R19/R09
agreement. Neither B nor T is inserted into the structural strong hash. Policy
values and the successful weak/strong outcome are independently persisted and
included in the reproducible analysis context.

### 6.3 Nested normalization and guarantee boundary

Normalization cannot silently use a weak auxiliary order to assign semantic local
names and later relabel the result strong. Preferred direction: R02/R06 define
binding-aware alpha normalization that does not depend on arbitrary identifier
occurrence ordering. If an auxiliary canonical search is genuinely required, it
shares the invocation's budget/deadline and returns its certificate/class;
exhaustion propagates to the final weak path, and timeout propagates as failure.

This proposal does **not** claim that making T explicit solves the old contract
unchanged. Existing PLAN/SDD text promises a successful weak fallback on time
exhaustion. Under the user's clarified authority, record that this legacy rule is
not adopted: it conflicts with deterministic successful output. Preserve the full byte-equality
claim for every successful core artifact, including deterministic weak results;
publish timeout/failure rates separately. If the owner instead selects a narrower
guarantee, mark that submission claim qualified/unfulfilled until addressed.

## 7. Canonical output, replay, and provenance boundary

### 7.1 Immutable logical context

Define a canonical logical-analysis manifest containing source/repository identity,
commit and source-tree digests, S_version and accepted-spec-set digest, policy
digest, complete R09 analysis-env identity, model/normalization/search versions,
budget-policy digest and B/T, output-schema version, and `LLM_TRIAGE=off`.
Canonicalize that manifest with a specified integer/string-only JSON encoding:
UTF-8, recursively sorted keys, compact separators, no non-finite values, and one
terminal LF. Version its schema and freeze exact golden bytes before implementation.

`analysis_id` is a domain-separated SHA-256 of those bytes. `snapshot_content_id`
is similarly derived from the immutable source, snapshot-toolchain/environment,
and model/export manifest. These are content identities, not existing scan or
snapshot row UUIDs. Repository identity is part of the declared source context;
do not imply equality across distinct tenants/repository identities.

### 7.2 SARIF version-2 artifact

The canonical SARIF artifact remains an actual SARIF log, not a projection created
after comparison. Emit the explicit core/oracle partitions as two primary files,
`core.sarif.json` and `oracle.sarif.json`, each with the fixed valid SARIF envelope
and its single Run. Retain every required detection/provenance property under the
approved version-2 schema. A combined two-Run view may also be delivered; it is
not the core-byte-equality artifact because its oracle bytes may change.

Replace operational `scanipy.scan_id` and `scanipy.snapshot_id` **inside this new
artifact format** with clearly named `scanipy.analysis_id` and
`scanipy.snapshot_content_id`. Do not reuse old field names with new meanings.
Persist operational scan/snapshot/attempt IDs in a signed delivery/provenance
envelope referencing the exact canonical SARIF hash. Preserve existing API/database
identities and their joins. This is an explicit versioned schema change requiring
root/owner coordination and compatibility tests, not an accidental omission of
current fields or a change to the meaning of historical artifacts.

Canonical bytes include detection content, source-relative locations, relevant
rule/spec metadata, immutable logical context, both artifact-specific identity
verdicts, the deterministic B-exhaustion outcome, and required annotations.
Exclude attempt timestamps, elapsed telemetry, attempt UUIDs, storage URLs with
expiring tokens, mutable triage/display state, and signatures from these bytes.
Those belong in separately retained, explicitly linked records. A real fix and
finding removal still change the detection artifact; user triage never deletes
the underlying finding. R07 owns visible lifecycle state and signed decision
history, not mutation of an already signed analysis artifact.

Use versioned SARIF native fingerprint keys `scanipy.cpg_order_hash/v2` and
`scanipy.slice_fingerprint/v2`. Under the proposed conservative interoperability
policy, expose cross-run native fingerprints only when both graph and slice
verdicts are strong and compatible; always retain weak artifacts in their
self-describing properties. This prevents blindly correlating a weak identity
through a third-party consumer that ignores Scanipy class metadata. R09 must
approve the exact adapter behavior and test it; this is not an assertion about
all external SARIF consumers.

### 7.3 Independent replay and attestation

Each attempt receives a fresh operational ID and fresh work directory. A core
replay independently re-parses and analyzes the same immutable logical input;
it does not reuse the first attempt's findings, canonical order, fingerprints,
or output file. Source/tool downloads may be prepared beforehand, but replay
evidence must declare caches and disallow analysis-result reuse for this gate.

Compare the exact version-2 `core.sarif.json` file bytes with no stripping or
re-sorting after comparison. Validate the full schema before comparison. A timeout, parser error,
or incomplete attempt is not an empty successful Run and does not satisfy the
gate. Include at least one known-positive finding to avoid vacuous success.

Oracle outputs remain empirical: R11 records attempted/completed/failed runs and
the exact reproduction metric with declared denominators. Do not discard timed-out
attempts without reporting them, or relabel a 100% sample rate as a theorem.

Persistent provenance binds the logical manifest, canonical SARIF bytes, graph
and witness artifact digests, independent artifact classes, source snapshot,
rule/spec, origin, and actual attempt IDs. Sign the envelope after canonical
artifact creation; randomized RSASSA-PSS signature bytes are not part of the
byte-equality comparison. R12 must prove offline verification from retained
artifacts and trusted historical public keys, not merely signature validation
over unverified caller-provided metadata.

## 8. Compatibility, migration, and operational impacts

- Keep version-1 findings, fingerprints, signed records, keys, and serializers
  readable and verifiable. Never rewrite historical signatures or relabel old
  weak/strong fields as if produced by the new algorithm.
- Introduce additive descriptor/version columns or versioned artifact records and
  explicit logical-manifest/attempt links. Schema migration, indexes, DB grants,
  retention, APIs, UI, and audit exports require R09/R12 design review.
- Register every old record with its actual legacy version/provenance. Do not
  infer trustworthy canonicality for a legacy strong result from its old label.
- A digest without a recognized namespace is not a version-2 identity. New caches
  include exact immutable source input, model/export, normalization/search,
  B/T policy, and environment identities. Never reuse an old raw-ID result as v2.
- Recompute v2 findings only from retained or freshly checked-out verified source.
  Preserve both old/new results during migration; compare them and report changes.
  Recalculation does not retrospectively change which engine produced a finding.
- R07 must not automatically copy decisions across versions on string equality,
  line proximity, or identical rule IDs. Use an explicit reviewed migration mapping
  or retain an unmatched finding pending review. Normal v2-to-v2 refactor continuity
  still must work and be demonstrated end-to-end; migration caution is not a
  substitute for delivering that promised behavior.
- Version-2 rollout changes the analysis Env and attestor obligation. Build and
  pin the actual worker artifacts before collecting final evidence. Keep software
  implementation, normalization, output-schema, and budget identities auditable.
- Keep the v1 execution path available only as explicitly legacy behavior during
  migration; do not use it to fabricate passing v2 evidence or hide deadline errors.
- The reference search may be too slow for T=200 ms on real CPGs.
  That is an engineering and empirical acceptance risk, not authority to silently
  raise T, remove hard cases, or accept a high failure rate. Optimize with a reviewed
  equivalence argument, validate resource use, and publish B-exhaustion and T-failure
  rates separately. Meet the original strong-success/fallback targets on the
  required corpus, with every attempted required case accounted for.

## 9. Required implementation and verification work

All items below are TODO. Test names are proposed artifacts, not files already
present or evidence of passing tests.

| ID | Required evidence |
|---|---|
| CB-01 | Red regression for the six-permutation example; after repair all six return one strong slice hash at ample budget. |
| CB-02 | Arbitrary bijective node relabeling and node/edge enumeration tests over asymmetric, symmetric, self-loop, duplicate-edge, and disconnected graphs. |
| CB-03 | Independent tiny-graph reference checks: compare the production search with its specified full-tree policy; use brute-force isomorphism/encoding enumeration to confirm equality iff isomorphic over the finite test domain. Do not require its byte minimum to equal an unrelated reference ordering convention. |
| CB-04 | Different labels, literal values, edge kinds, direction, multiplicity, and dependency structures remain distinct; include the single-node defect. |
| CB-05 | Framing golden vectors, Unicode cases, malformed graph/configuration errors, empty graph, and new hash-domain separation. |
| CB-06 | Vertex-partition fixpoint and direction-aware refinement tests; reviewed invariance argument and tested exact work counters. |
| CB-07 | Complete-tree/minimum selection, equal-certificate mapping ties, B=1/boundary/exact-B cases, and rejection of partial-best strong success. |
| CB-08 | Fast/slow controlled clocks: either identical successful semantic output or explicit deadline failure; never two different successful identities. Cover early returns and fallback expiry. |
| CB-09 | Shared nested budgets and class propagation; no extra default-B/T alpha-renaming search or hidden weak result beneath strong. |
| CB-10 | Deterministic weak fallback from untouched input; original source-scoped witness edges; disconnected/stale witness rejection. |
| CB-11 | Worker watchdog and crash/timeout integration; no persisted successful output, resolved finding, or passing attestation on incomplete work. |
| CB-12 | Version-2 canonical SARIF schema and golden bytes; independent attempt IDs, triage updates, timings, and signatures do not alter analysis bytes. Detection/source/spec/policy changes are reflected correctly. |
| CB-13 | Four graph/slice class combinations, engine origin independence, native-fingerprint policy, and weak-never-auto-inherit workflow. |
| CB-14 | Historical v1 verification; explicit v1/v2 migration and cache invalidation; unknown namespace rejection; no automatic unsafe decision migration. |
| CB-15 | Real Java/Python parse-to-solver-to-slice-to-SARIF independent known-positive replay with immutable context and raw artifacts; no analysis-result cache reuse. |
| CB-16 | All named genuine refactors plus real fixes/alias-effect controls on the corrected corpus through R02/R03/R06/R19. |
| CB-17 | Real-code B-exhaustion, T-failure, memory and latency measurements on the required corpus; restore the currently skipped empirical gates without weakening them. |
| CB-18 | Independently retained source/graph/witness/SARIF provenance verification, tamper rejection, fresh-process key lookup, and rerun-free offline verification through R12. |

Component verification must run the existing CORE-03/CORE-02 acceptance and
invariant suites in addition to new tests. Integrated checks must cover worker,
normalizer, persistence, provenance, attestor, adapters, and continuity consumers.
Respect CMP-CP-06 language staging before Algorithm 2 benchmarking. Synthetic
graph tests are not substitutes for CB-15 through CB-18.

Maintain three evidence levels: reviewed mathematical argument, executable
mechanism falsifiers, and real-source/integrated measurements. None alone proves
the other two. Report skipped or unavailable acceptance cases as incomplete.

## 10. Historical CLAR mapping and root-review decisions

Candidate identifiers below are **not filed or resolved by this document**.
They preserve traceability for a future authorized workflow update. Under the
latest user direction, they are not prerequisites that stop local implementation.
If later filed, recheck allocation and avoid duplicating an existing question.

| Record | Required treatment |
|---|---|
| CLAR-PARAM-01, RESOLVED | Retain numeric B/T defaults in the proposed initial policy; the legacy record does not settle successful time-exhaustion nondeterminism. |
| Proposed CLAR-CORE-03 | Canonical labeled-graph model, exact encoding/search, digest semantics/versioning, complexity, and canonical mapping versus invariant encoded bytes. |
| Proposed CLAR-CORE-04 | Deterministic work exhaustion, explicit wall-clock failure, shared nested budgets, successful-output guarantee, and protected-source conflict. |
| CLAR-CORE-02, OPEN | Binding/purity/formatting/extract normalization still needs a concrete implementation contract for full slice semantics; do not pretend this graph algorithm implements it. |
| CLAR-ORCH-03, OPEN | Approve independent artifact classes/descriptors and suppression/interoperability behavior. |
| CLAR-ORCH-12, OPEN | Decide honest oracle CPG/precondition metadata producers/applicability; never mint an invented graph digest. |
| Proposed FND/ORCH clarification, ID to allocate | Version-2 canonical SARIF versus attempt envelope, immutable logical context, artifact retention, and additive migration. Reuse an existing relevant replay/schema record if present. |
| CLAR-PROC-01, RESOLVED | Historical build-ahead precedent. The current user directive authorizes local end-to-end implementation; partial tests still do not establish completed functionality. |

Root-review decisions, not requests for renewed implementation permission:

1. **Canonical-library owner/root reviewer:** Adopt the section 4 labeled-graph/encoding definition and
   section 5 complete-search policy as the version-2 identity contract, including
   the graph-versus-normalized-slice distinction and honest 1-WL naming?
2. **Budget/worker owners/root reviewer:** Adopt B=65,536
   deterministic search states and T=200 ms as an explicit failure deadline,
   replacing successful weak-on-timeout behavior? Confirm that all successful
   core outputs, strong or weak, remain byte reproducible and incomplete attempts
   are reported separately rather than counted as successful analyses.
3. **R09/R10 owners/root reviewer:** Adopt independent artifact
   descriptors and version-2 content identities inside canonical SARIF, with real
   operational UUIDs in the signed envelope, without changing the meaning of old
   fields or altering historical artifacts?
4. **R07/R12 owners:** Adopt additive history retention and explicit reviewed
   cross-version decision mappings, while requiring ordinary strong v2 refactor
   continuity and full historical provenance verification?
5. **Root reviewer:** Confirm that performance and coverage gates retain the complete
   submission scope. If the reference algorithm misses the targets, optimization
   and further evidence remain required; no automatic fallback to a reduced demo
   or qualified public guarantee is authorized by this proposal.

Record the adopted choices, reconcile the graph/provenance proposal, and dispatch
owned local implementation milestones. Proposed canonical-library ownership is
`analysis/ordering.py`, `analysis/fingerprint.py`, and dedicated tests
`tests/unit/test_canonical_identity_v2.py` and
`tests/unit/test_canonical_budget_v2.py`. Coordinate before another agent edits
fingerprint slicing or normalization in the same file. Shared schema, mapper,
worker, persistence, and attestor edits remain with their respective owners.
Keep remote issue reconciliation, commits, and publication pending the appropriate
workflow authority. Do not change legacy protected files to manufacture agreement.
