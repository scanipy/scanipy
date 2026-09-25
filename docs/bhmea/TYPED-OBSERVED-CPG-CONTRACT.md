# R19-B1 — immutable typed observations and versioned transport

Status: LOCAL IMPLEMENTATION AND INDEPENDENT SCOPED REVIEW COMPLETE.
Dependency merge, combined-head verification, remote CI and canonical approval
remain pending. This is not a claim of direct owner design selection or full
R19/submission acceptance.
Date: 2026-09-25. Corrective issue: #393. Parent objective: #362.
Dependency: #376 / PR #382, locally based on frozen
`9035359e548ac210c3d101f24df76b7df2ebc32d`; local availability is not merge approval.

## 1. Authority, scope and non-claims

The root engineering coordinator approved the layered model, version names,
syntax-only supplement direction and explicit legacy-refusal fences under
[DECISION-BHMEA-01](../DECISION-BHMEA-01-current-execution-authority-2026-09-25.md).
These are engineering decisions under the owner's full Black Hat objective,
not a claim that the owner directly selected each design. Historical PLAN,
SDD, WBS, CLAR records and signed artifacts remain unchanged.

This first slice, called **R19-B1** in this document, implements immutable
observations, typed structural views and strict transport. It does not complete
the whole R19-B semantic model, R19-C binding, R19-D flow, R02/R06 purity,
R07/R08 persistence or G1. The [full review](../REVIEW-BHMEA-EXECUTION-ACTION-ITEMS-2026-09-23.md)
and [graph proposal](../PROPOSAL-BHMEA-GRAPH-PROVENANCE-2026-09-25.md) remain the
full acceptance target. Unsupported cases are outstanding work, not a reduced
submission or a substitute for the required extraction examples.

Exactly five new files are assigned to this issue:

| File | Responsibility |
| --- | --- |
| `docs/bhmea/TYPED-OBSERVED-CPG-CONTRACT.md` | This reviewed implementation contract and subsequent-work boundary |
| `analysis/cpg_ingest/typed_observed.py` | Immutable observations, bounded capture, structural views and validation |
| `analysis/cpg_ingest/typed_observed_wire.py` | Exact versioned artifact writer/reader; no production-default dispatch |
| `tests/unit/test_typed_observed_cpg.py` | Model, role, immutability and retained-evidence falsifiers |
| `tests/unit/test_typed_observed_cpg_wire.py` | Wire, bounds, tampering, replay and actual legacy-refusal controls |

Do not modify the raw-v2 dependency, legacy mapper/archive, canonical v2,
solver, worker/API, source invocation, image or Java safety profile here.
`JAVA_STATIC_V1` stays unchanged. No native probe, target execution/build/test,
image publication or external organizer message is authorized. Read-only
retained evidence tests are not fresh frontend runs.

## 2. Layering and exact version identities

| Layer | Identifier | What completion means |
| --- | --- | --- |
| Existing native raw export | `scanipy-joern-export`, integer `format_version = 2` | Pinned raw nodes/edges/properties enumerated, not resolved language semantics |
| New immutable observation model | `scanipy-cpg/2` | Exact supported raw values captured without mutable references |
| New structural role profile | `scanipy-java-python-roles/1` | Mechanical role/ownership views over those observations |
| New transport | `scanipy-cpg-artifact/2` | Strict lossless archive of the captured observations and original raw bytes |
| Later syntax supplement | `scanipy-source-syntax/1` | Reserved design direction; no parser implemented in #393 |
| Later semantic graph identity | `scanipy-canonical-graph/3` | Separate encoding/projection implementation and verification required |
| Later normalized slice identity | `scanipy-slice-normal-form/3` | Separate semantic normalization and verification required |

The new artifact has an explicit `stage = observed-only`. No graph/slice hash,
strong/weak class, solver result or derived completeness is emitted here.
Integrity hashes of actual bytes are not canonical structural identities.

Layers must remain separate:

1. Native observations: exact values, explicit absences and multiedges.
2. Structural views: observed declarations, AST ownership, arguments, receivers,
   return expressions, references, types and lookup hints.
3. Future proof-bearing relations: complete call targets, actual/formal binding,
   return/result binding, effects and purity.

The five existing derived raw capabilities remain `unsupported`, even when
a view has one candidate, a zero-length edge list or a familiar-looking name.
The current exact observed-only wire shape is closed. Future derived payloads
need a separately reviewed version/profile and explicit reader dispatch; do
not add fields or change meanings silently under this profile.

## 3. Inputs, public interfaces and deep immutability

Approved public interfaces:

```python
def parse_observed_graph(
    raw_export_bytes: bytes, *, limits: ObservedGraphLimits | None = None
) -> TypedObservedGraph: ...

def validate_observed_graph(graph: TypedObservedGraph) -> None: ...

def to_raw_document(graph: TypedObservedGraph) -> dict[str, object]: ...

def serialize_observed_graph(graph: TypedObservedGraph) -> bytes: ...

def deserialize_observed_graph(
    artifact_bytes: bytes,
    *,
    limits: ObservedGraphLimits | None = None,
    expected_artifact_sha256: str | None = None,
    expected_raw_export_sha256: str | None = None,
) -> TypedObservedGraph: ...
```

Digest arguments, when provided, are `sha256:` plus 64 lowercase hexadecimal
characters and are compared to actual bytes. Optional expected digests are
trusted-controller assertions, not values copied from the received artifact.
Without them the reader establishes internal consistency, not authentication.

`parse_observed_graph` accepts exact immutable `bytes`, not a caller-owned dict,
CPG, arbitrary Mapping or mutable buffer. It enforces bounds, uses the strict
pinned raw-v2 reader with completed status required, and freezes primitive
values recursively. The schema catalog remains single-sourced in
`analysis/cpg_ingest/joern_schema_v2.py`; do not duplicate a permissive catalog.

Every model/view record is frozen with slots. Collections are exact tuples;
objects and arrays have distinct frozen wrapper types. Primitive types retain
their identity: bool is not int; an empty object is not an empty array. No
mutable raw dict/list, CPG or custom scalar subclass survives capture. Validate
direct construction as well as factory construction before returning a valid
graph. Arbitrary in-process Python execution that bypasses frozen objects is
outside this value-object boundary; this is not an authentication mechanism.

The pinned native property catalog permits only `str`, `int` and `bool`;
do not broaden it to floats. Generic JSON null is retained only where the raw
schema permits it, not substituted for an absent native property.

`to_raw_document` returns a detached mutable reconstruction. Its mutation must
not change the captured graph, views, digests or original raw bytes. Rebuilding
views must be deterministic for one captured input. Views are not independent
caller-supplied evidence and must not accept conflicting cached role records.

The implemented `TypedObservedGraph` constructor accepts only original bytes
and limits. Node, edge, producer and view fields are derived (`init=False`),
not independent constructor arguments. `validate_observed_graph` rebuilds those
fields from bounded original bytes before accepting the object for transport.

### 3.1 Required records

| Record | Required content |
| --- | --- |
| `TypedObservedGraph` | Exact model/profile/stage, original raw bytes and computed SHA, frozen producer/capabilities, node tuple, edge tuple, derived structural views, validated limits |
| `ObservedNode` | Native ID string, pinned kind, complete catalog-aware property observations, exact `missing_properties` tuple |
| `PropertyObservation` | Property name, native schema type/cardinality, explicit presence state, immutable value only when present |
| `ObservedEdge` | Snapshot edge ordinal, native src/dst references, pinned kind and exact sparse property observations |
| `StructuralViews` | Immutable role records referring only to captured node/edge references; explicit unverified/unsupported semantic status |

Property states are `present`, `missing_required`, `absent_optional` and
`absent_many`. The latter is not a fabricated empty list. For present values,
preserve scalar/list shape and list order. The original raw missing-required
list must agree exactly with the pinned schema and stored properties.

Native IDs are the raw export's canonical decimal strings in the nonnegative
signed-64-bit range, `0..2**63-1`. They are native snapshot references here, unlike the
mapper-assigned IDs of the old minimal CPG. The exporter has no exported native
edge ID: the edge ordinal is this capture's array position, not a native edge
identity or semantic tie-breaker. Preserve each duplicate edge separately.

## 4. Exact observation-to-role mapping

The raw exporter obtains node values with `n.propertiesMap`, determines absent
required fields with GraphSchema, and reads edge payloads through
`propertyMaybe` / `propertyName`. Do not substitute generated-accessor defaults.
See [the producer](../../workers/snapshot/joern-scripts/export_cpg_v2.sc).

All 43 pinned node kinds and 34 edge kinds remain representable as immutable
observations, not only those appearing in the two retained fixtures. Every
catalog property is retained with its state. Unknown kinds/fields fail; no
generic drop-unknown-fields path exists. A structural view need not interpret
every kind, but observation-only kinds remain available in the model/replay.

| Native surface | Structural view | Explicit non-claim |
| --- | --- | --- |
| METHOD and its observed properties | Method identity, observed name/full-name/signatures/modifiers | No resolved symbol or complete dispatch from text alone |
| METHOD to formal/return AST edges | Direct formal/return owner | No caller actual/formal or return/result proof |
| AST ancestry | Unique nearest METHOD ownership where present | No FQN fallback or invented owner for disconnected metadata |
| IDENTIFIER to REF | Declaration-reference candidates | Not a reaching-definition, alias or exact-value proof |
| LOCAL / MEMBER / formal | Separate declaration/storage categories | Fields/members are not alpha-renamable locals |
| CALL properties | Observed call/operator spellings and signatures | No suffix matching, API identity or executable operator semantics |
| CALL edge to METHOD | Candidate target edge, including its ordinal | One candidate is not uniquely resolved or complete |
| RECEIVER edge | Callee-expression observation | Not automatically the bound receiver object |
| CALL to ARGUMENT | Actual expression with native index/name/order states | No invented semantic index or evaluation schedule |
| Formal INDEX/NAME/IS_VARIADIC/EVALUATION_STRATEGY | Exact formal-role observations | Missing IS_VARIADIC is not false; native index is not a DSL position |
| PARAMETER_LINK | Formal-input/output edge | Not actual/formal binding; duplicates remain represented |
| RETURN to ARGUMENT | All observed return-expression edges | BLOCK is not flattened; zero/multiple values are not silently repaired |
| RETURN to CFG to METHOD_RETURN | Observed exit candidate | Not a matched return to every caller |
| AST / ARGUMENT operand structure | Child/operand observations and raw ORDER/index | No raw-array or location-based operand ordering |
| CFG / CDG | Distinct observed control relations | No normal/exception/branch completeness from an unlabeled edge |
| REACHING_DEF with VARIABLE | Distinct dependency edges and exact payload | VARIABLE text is not a binding ID; no PDG collapse |
| EVAL_TYPE and type properties | Declared/hint/possible-type observations | ANY, unresolved names and hints are not exact runtime types |
| MODIFIER / BINDS / INHERITS_FROM | Dispatch-relevant observations | Not exhaustive targets or a complete class hierarchy |
| CAPTURE / CLOSURE_BINDING | Capture observations | Not no-alias/no-mutation evidence |
| File, line, column, offset, raw CODE | Source lookup/replay hints | Not canonical identity or a unique source association |

### 4.1 Ownership rules

Reapply the raw-v2 structural invariants: AST parents are unique and acyclic;
parallel edges to the same parent remain distinct; formal input/output and
METHOD_RETURN nodes have a direct METHOD owner; PARAMETER_LINK endpoints share
that owner. Invalid structure fails capture, not just an optional view.

For body membership, a METHOD owns itself; an ordinary node belongs to its
nearest METHOD ancestor. Stop at a nested METHOD. A method declaration's outer
lexical owner, where observed, is a separate relation from ownership of its
body. No METHOD ancestor means `no_method_ancestor`, not a fabricated global
procedure. Role evidence references the actual AST edges used.

Store a shared parent/edge forest and one nearest-owner result per node.
Ownership construction and cycle validation are iterative, with linear storage
in nodes plus edge occurrences. Do not materialize every ancestor path or expand
all pairs. Deep valid chains and parallel same-parent edges require explicit
bounded-storage regression tests.

Maintain full-name lookup only as a multimap. Duplicate/unresolved names are
legal observations and cannot merge declarations. Never choose a method by
lowest ID, first occurrence, matching name/arity or raw-array position.

### 4.2 Cardinality and lookup ambiguity

Candidate targets, receiver expressions, actuals, REF targets and return
expressions are tuples of observed edges, not implicit singletons. Preserve
multiple values and missing properties. A view may report an ambiguity or
missing-evidence diagnostic, but cannot convert it to a guessed binding.

Formal/argument index observations may be absent or otherwise unusable for a
future semantic profile. This slice preserves schema-valid native integers;
it does not certify semantic index validity, uniqueness or contiguity. A future
binder must reject or explain invalid positions before completing bindings.

Method source hints retain exact available filename/line/column/offset states.
An exact filename/line lookup returns every matching native METHOD, including
synthetic candidates; it performs no basename normalization, nearest-line
selection or first-match tie-break. Zero/one/many candidates remain explicit.
Even one candidate has source-association status `unverified`: no source-syntax
parser or association proof is implemented here.

## 5. Provenance, source identity and losslessness

Preserve the entire validated raw producer object and all capability records,
including image observation kind, actual tool/script/input-CPG digests, frontend,
import/overlay observations, JVM strings, source inventory and their absences.
Do not add invented S_version, tenant, runtime observations or source acceptance.
This module emits no Finding or provenance-store mutation.

Keep three different byte identities distinct:

1. Original raw export SHA: computed over the exact bytes supplied to capture.
2. Native binary CPG SHA: retained from the raw producer as its assertion.
3. New typed archive SHA: computed over actual serialized archive bytes.

The artifact retains original raw bytes as well as normalized observation JSON.
Losslessness means reconstruction preserves every raw value, list/array order,
missing-state distinction, producer field and directed multiedge occurrence.
Original whitespace/object-key order is preserved only by the original byte
payload, never falsely attributed to normalized JSON. Changing raw array order
may change replay bytes and raw SHA; no canonical identity is claimed.

### 5.1 Source algorithms are not interchangeable

Raw-v2 `scanipy-source-tree/1` hashes the prefix `scanipy-source-tree/1\0`, then
UTF-8-byte-sorted file paths as u64 big-endian path length, path bytes, u64 file
size and 32 file-digest bytes. It is a manifest hash; this reader validates the
manifest framing but does not read unseen source files.

R04/#391 `sha256-length-prefixed-path-and-content-v1` instead hashes sorted
relative POSIX paths with u64 path/content byte lengths and actual content,
with no algorithm prefix. A manifest of file hashes cannot reconstruct this
digest without source bytes. Preserve algorithm names and each supplied digest;
do not convert, compare or substitute these different identities.

A later trusted capture adapter must verify source bytes, inventory, parser
attempts and CPG correspondence. File inclusion does not prove parsing coverage.
Unknown ignored/failed files or missing semantic relations cannot establish a
completed clean scan, vulnerability removal or closed-world status.

## 6. Exact artifact format and actual legacy refusal

The artifact is one gzip stream containing a tar with exactly one regular file
named `cpg.json`. Its JSON object has exactly these fields:

```text
format: "scanipy-cpg-artifact"
format_version: 2                         # exact integer, not bool/string
model_version: "scanipy-cpg/2"
role_profile: "scanipy-java-python-roles/1"
stage: "observed-only"
nodes: null                              # compatibility fence, NOT observations
edges: null                              # compatibility fence, NOT observations
original_raw_export:
  encoding: "base64"
  byte_length: <exact nonnegative integer>
  sha256: <64 lowercase hexadecimal characters>
  data: <strict standard base64 of original raw bytes>
graph: <normalized complete raw-v2 document reconstructed from the typed model>
```

`graph` retains the raw document's exact schema, producer, capabilities, nodes,
edges and completed status. Structural views are reconstructed and validated
from it, not accepted as independently supplied proof. Keeping both original
bytes and normalized observations is deliberate: the reader verifies they
describe exactly the same typed JSON value, not merely the same node counts.

The null `nodes`/`edges` fields are mandatory wire compatibility fences. The
current legacy mapper uses `.get("nodes", [])` / `.get("edges", [])`; simply
omitting these keys could yield a falsely successful empty graph. Required
nulls make the tested legacy mapper and archive reader reject before returning
a CPG. They are not empty observed arrays or a failed raw-export envelope.
The new reader rejects missing/non-null fences. Do not claim protection against
every arbitrary legacy consumer; test the actual current readers explicitly.

### 6.1 Writer

Validate the graph and limits before serialization. Encode JSON with strict
UTF-8, `ensure_ascii=False`, sorted object keys, compact separators, no NaN or
Infinity, and no trailing newline. Base64 is standard padded ASCII without
whitespace. Preserve all arrays in their captured order.

Use a regular USTAR member: name `cpg.json`, uid/gid 0, uname/gname empty,
mode `0600`, mtime 0, no links/PAX/global headers. Gzip uses mtime 0, no filename
or comment and fixed compression level 9. Repeated serialization of the same
captured input under the pinned runtime is byte-identical; this is a transport
property, not cross-refactor or cross-runtime canonicality.

### 6.2 Reader

Validate exact bytes and optional expected archive SHA first. Enforce compressed
and decompressed limits while reading, not after unbounded decompression.
Feed bounded compressed-input chunks and retain only each chunk's pending
tail; repeatedly passing the entire remaining input would cause quadratic
copying on incompressible artifacts. Bound both input and output chunks.
Reject truncated/corrupt gzip, concatenated gzip streams and trailing nonstream
data. Validate tar structure without extracting files. Reject extra/duplicate
members, directories, links, sparse/PAX/extension records, wrong names, invalid
size/header, nonzero trailing data or excess padding. Enforce `max_tar_bytes`
independently of the member's `max_json_bytes` bound.
The header must exactly match the writer's USTAR header (including its metadata
and field encodings); alternative UID/mode/name/PAX conventions are not accepted
as this profile. Gzip may use another valid deflate presentation but must remain
one complete stream with no trailing data.
For payload size N, require the single-header/member/two-zero-block layout,
with total length rounded up to a 10,240-byte record boundary; every byte after
the member payload is zero padding. No second hidden archive is permitted.

Decode bounded UTF-8 JSON with duplicate-key rejection at every depth. Validate
the exact shape/version/profile/stage/fences and strict scalar types. Strictly
decode base64, require standard re-encoding to equal its supplied spelling,
check declared length and raw SHA, and apply the optional trusted
expected raw SHA. Parse the original raw bytes as a completed strict raw-v2
document. Independently validate `graph` under that same schema and require
exact type-sensitive JSON-value equality, preserving all array order and
multiplicity. Reject any mismatch before returning a graph. Finally construct
and validate the immutable model and its structural views.

No lenient fallback to raw-v2, v1 or a minimal CPG is permitted. Existing v1
archives remain readable by the unchanged v1 reader; the new reader explicitly
refuses v1. Writer output must round-trip byte-identically. The model does not
claim that every alternative valid gzip encoding received from another writer
will be reproduced byte-for-byte; an expected archive digest binds those actual
received bytes separately. Routing between old and new readers is future producer/consumer
integration, not added to a default path here.

## 7. Resource limits and errors

Approved first-slice hard ceilings, also the defaults:

| `ObservedGraphLimits` field | Ceiling |
| --- | ---: |
| `max_raw_bytes` | 16 MiB |
| `max_artifact_bytes` | 32 MiB |
| `max_json_bytes` | 64 MiB |
| `max_tar_bytes` | 64 MiB + 10,240 bytes |
| `max_nodes` | 10,000 |
| `max_edges` | 100,000 |
| `max_source_files` | 10,000 |
| `max_string_bytes` | 1 MiB |
| `max_total_string_bytes` | 8 MiB |
| `max_json_depth` | 32 |
| `max_json_values` | 500,000 |

These are conservative reviewed resource ceilings, not measured
presentation budgets or proof of adequate full-repository throughput. Settings
are exact positive integers. Only a trusted coordinator may lower them; clients
cannot raise ceilings. A higher resource profile needs review and validation,
not silent truncation or a claim that the full source scope was processed.

Enforce byte/depth bounds before general JSON parsing, then node/edge/inventory/
value/string bounds before deep copying and view construction. A bounded lexical
depth pass must respect JSON strings and escapes; it does not replace the JSON
parser. Enforce base64 encoded/decoded lengths before allocation. Check output
limits before building/returning an oversized archive. No partial completed
graph, successful prefix or time-dependent weak identity is returned.

String/value counts apply to the complete observation document, including its
producer and capabilities. `max_json_values` counts the root plus every nested
scalar/container value, but not object keys. String bounds count every UTF-8
object key and string-valued occurrence, including repeated array elements.
Container nesting starts at depth one; string contents do not increase depth.
Apply the observation counts independently to original and normalized documents.
The transport's base64 string has separate encoded/decoded byte bounds; it is
not subject to the one-observation-string ceiling. Structural-view storage must
be bounded linearly by validated observations, not an all-pairs expansion.

Use typed errors with stable reason codes:

| Error family | Examples | Outcome |
| --- | --- | --- |
| `ObservedGraphInputError` | Bad input type/UTF-8/JSON, duplicate keys, invalid schema/reference/ownership, inconsistent original/normalized payload | No graph |
| `ObservedGraphUnsupportedError` | Unknown format/model/profile/kind/property/version; v1 sent to new reader | No fallback or graph |
| `ObservedGraphLimitError` | Any configured byte/depth/count/string/output ceiling exceeded | No completed prefix |
| `ObservedGraphArtifactError` | Invalid archive/gzip/member/header/base64/digest | No graph; never retry an old artifact as this attempt |

A valid raw failure envelope still fails completed capture. Preserve the causal
raw-reader failure category without dumping unbounded source text or credentials.
Potentially source-bearing raw-schema exception chains are suppressed in rendered
tracebacks; stable typed reason codes distinguish unsupported, incomplete and
invalid captures. The caller can report those codes without logging raw bytes.
No retry, queue policy, process watchdog or artifact persistence is implemented
by this pure library. Unknown derived semantics are represented as unsupported
observations, not confused with a malformed raw transport or successful solver.

## 8. Retained evidence and required first-slice tests

Use the exact [retained R19-A evidence](../../tests/fixtures/joern_raw_v2/README.md)
and its hash inventory. Java has 199 nodes / 1,022 edges; Python has 442 nodes /
2,435 edges. Those are native static-parser observations, not solver findings.
Tests must never import or execute the fixture source.

| Test ID | Required controlled falsifier / invariant |
| --- | --- |
| OBS-01 | Both retained exports capture and round-trip with every typed raw value, missing property, producer field and edge occurrence preserved |
| OBS-02 | Deep mutation of detached output cannot alter the model, views, digests or original bytes; mutable/subclass/invalid direct construction is rejected |
| OBS-03 | All pinned property types/cardinalities work; false/zero/empty/present/missing-required/absent-optional/absent-many stay distinct |
| OBS-04 | Duplicate/dangling IDs, unknown schema fields, malformed AST ownership and invalid formal links fail before completion |
| OBS-05 | Duplicate Java helper FQNs remain separate; wrong overload candidate remains only an observation; no inferred resolved target |
| OBS-06 | Static-call synthetic receiver, Java missing vararg boolean, Python named/default/star forms and callee-expression/bound-object distinction remain intact |
| OBS-07 | Python default literal absent from raw graph is not invented; source methods and synthetic adapters sharing locations all remain lookup candidates |
| OBS-08 | BLOCK returns and both parallel VARIABLE-bearing dependencies survive; dropping/changing one observation changes reconstructed content |
| OBS-09 | No canonical/fingerprint/legacy solver/worker/native subprocess invocation occurs in capture, views, serialization or error handling |
| OBS-10 | Bounds fail before the corresponding parsing/copy/decompression/output expansion; bool/nonpositive/over-ceiling settings fail |
| WIRE-01 | Repeat serialization is byte-identical under one runtime; deserialize/serialize preserves deterministic bytes |
| WIRE-02 | Original raw whitespace/key-order bytes and their SHA remain exact; normalized bytes are not mislabeled as original |
| WIRE-03 | Wrong versions, stages, fences, duplicate keys, malformed base64, forged lengths/digests and original/normalized disagreement fail |
| WIRE-04 | Tar traversal/link/extra/duplicate/sparse/extension members, corruption, gzip concatenation/trailing data and decompression limits fail |
| WIRE-05 | Actual current legacy mapper and legacy archive reader reject the new null-fenced envelope before returning a graph; missing fences expose the controlled legacy trap |
| WIRE-06 | Existing real v1 archive round trip stays unchanged; new reader refuses it rather than upgrading its capabilities |
| WIRE-07 | Raw source-tree namespace and content-framed tree algorithm are not substituted; supplied producer bindings remain assertions, not authentication |
| OBS-11 | Raw array permutations preserve the observation multiset and role candidates without promising identical original/replay bytes |
| OBS-12 | Every new test has the unit marker and is collected by actual CI and pre-push selectors |

Finite tests are regressions/falsifiers, not a proof of full language semantics.
Run dedicated tests, Ruff, strict mypy and relevant existing unit/integration
checks on the final combined dependency head. Required canonical APPROVE and
CI remain merge gates. Local review or test success cannot substitute for them.

## 9. Required later semantic contracts — not implemented by #393

### 9.1 Source syntax, Java and Python binding

A future syntax supplement must bind actual source bytes, parser/version/code
digest/options, language version and per-file outcomes. It observes defaults,
parameter kinds, modifiers and AST roles without executing expressions or
source. Source/native association must combine validated lexical/structural
evidence and preserve ambiguity, not choose by location/name/lowest ID.

Java binding must separate overload selection, runtime target coverage,
receiver evaluation, ordinary arguments, fixed-array invocation and vararg
packing. Preserve conversions, operand order and exception behavior. One native
candidate, source-static modifier or raw DYNAMIC_DISPATCH string is not enough.
The JLS distinguishes strict/loose/variable-arity applicability and later target
invocation. [JLS 21 method invocation](https://docs.oracle.com/javase/specs/jls/se21/html/jls-15.html#jls-15.12).

Python formals need positional-only, positional-or-keyword, var-positional,
keyword-only and var-keyword kinds. Bind names to eligible formals, reject
collisions/arity errors, and distinguish descriptor-bound receivers from an
ordinary parameter named self. Defaults refer to definition-time values;
syntax alone does not establish their alias/effect properties.
[Python 3.11 function definitions](https://docs.python.org/3.11/reference/compound_stmts.html#function-definitions).

Star/dict unpacking requires bounded supported iterable/mapping semantics and
explicit evaluation/binding order; unknown expansion remains unsupported.
Positional iterable unpacking is processed before keyword binding even when
written after a keyword. Do not derive this from raw node order.
[Python 3.11 calls](https://docs.python.org/3.11/reference/expressions.html#calls).

Unknown calls retain candidates and uncertainty. Only a verified supported
resolution, a reviewed version-pinned conservative summary, or explicit
incomplete/unsupported analysis is permitted. Never turn an empty target list
into complete absence or use node-name suffixes to guess a modeled API.

### 9.2 Values, effects, flow and purity

R19-C/D must represent storage declarations separately from expression values;
REF is not reaching-definition analysis. Required derived relations include
actual/formal and return/result links tied to a specific call site and target,
value/operand dependencies, control dependencies and effect ordering. Preserve
BLOCK-yield structure and synthetic evaluation steps until a supported lowering
proves how to interpret them. Never connect one callee return to every caller.

Effects need explicit read/write/alias/exception/I/O/dynamic-execution evidence
and completeness. Missing effects mean unknown, not the empty effect set.
R19-D must apply actual positional/access-path Source/Sink/Sanitize/Propagate
semantics and update matched call/return summaries during the fixpoint. The
existing #391 exact-token CFG/CALL bootstrap is not a real-flow shortcut.
The existing DSL's Propagate application-site/model contract still needs
reconciliation; comments naming StringBuilder do not implement that selector.

Purity/extraction requires uniquely bound called helpers, multiple meaningful
operands, transformed returned values, type/alias/effect/control evidence and
an explicit operation/observation model. A syntax-only default, a native type
hint or a canonical graph label is not a purity certificate. Do not replace
required positive corpus cases with identity helpers, unused code or unsupported
labels and call extraction complete.

### 9.3 Canonical v3, history and downstream integration

The approved migration direction is new graph/slice namespaces v3, not changing
minimal v2 meanings. A later encoder must include every semantic role/index,
call-site/target association, relevant type/effect distinction and directed
multiedge multiplicity. Reference-valued data must be canonical-indexed or
represented with relation nodes/edges, never hashed as raw native IDs.

Source coordinates, artifact/attempt IDs and proof-record IDs stay outside
structural bytes. Literal/operator meanings need a supported typed adapter;
arbitrary CODE strings are not a substitute. Do not erase field/member names
as locals, normalize all FQNs indiscriminately or omit new attributes merely
to obtain a strong label. Required unknown semantics prevent strong semantic
identity; malformed/unsupported input is not the deterministic weak fallback.

Reuse complete bounded canonical search only with the expanded exact label
contract and certified pruning. Reified relation nodes count toward its work
budget. Preserve explicit T failure and shared normalization-budget accounting.
Graph canonicality and normalized-slice/refactor equivalence remain separate.

R09 outputs, continuity policy, R04 gate policy, cache compatibility and signed
history need explicit version-aware migration. Do not overwrite namespace
constants or reinterpret old protected passes. No such consumer edits occur
in #393, and no production default becomes a typed-v2 producer here.

### 9.4 Real G1 and full scope

First real G1 models/cases require separate concrete review. The later required
helper milestone is actual source to multiple operands/local assignments to a
called helper to transformed return to caller result to modeled sink, on the
production parser/mapping/solver path. It is not an implemented fixture here.

Corrected refactor seeds with vulnerable input parameters do not automatically
match shipped source patterns. Python sqlite examples do not automatically
match the shipped injection detector's subprocess sink. Preserve the corpus;
implement/review actual entrypoint/API models or explicitly scoped real-flow
cases rather than injecting labels or assuming a match.

Early G1 may have a declared narrow case scope as the active review allows;
full R19 still needs Java and Python, returned-value and helper-contained-sink
witnesses, clean/tainted-actual controls, matched callers, changed semantics,
alias/effect/ambiguity controls and sufficient source coverage. Final extraction
and full-submission acceptance remain required afterward.

## 10. Primary Java configuration evidence; no runtime authorization

Retrieved read-only on 2026-09-25 at approximately 11:31 UTC. Annotated upstream
tag v4.0.554 resolved to commit
`cf59a329bf83063c096e1e803d608e5057d8bb95`. SHA-256 values of retrieved bytes:

| Pinned primary source | SHA-256 |
| --- | --- |
| [Main.scala](https://raw.githubusercontent.com/joernio/joern/cf59a329bf83063c096e1e803d608e5057d8bb95/joern-cli/frontends/javasrc2cpg/src/main/scala/io/joern/javasrc2cpg/Main.scala) | `c20468ae08f53519796671305023b8bbea9d96731bd6b73f0e5f91b64d4456ff` |
| [JavaSrc2Cpg.scala](https://raw.githubusercontent.com/joernio/joern/cf59a329bf83063c096e1e803d608e5057d8bb95/joern-cli/frontends/javasrc2cpg/src/main/scala/io/joern/javasrc2cpg/JavaSrc2Cpg.scala) | `013ca9c021ba33fa9213acb255a009a4e2495267ed4e9ff3ee86b94b80dd63c6` |
| [AstCreationPass.scala](https://raw.githubusercontent.com/joernio/joern/cf59a329bf83063c096e1e803d608e5057d8bb95/joern-cli/frontends/javasrc2cpg/src/main/scala/io/joern/javasrc2cpg/passes/AstCreationPass.scala) | `953f6bcaca986cc24dd53f7e5742d1fd77ac5d8cb1adc62ba26d515e8296d82b` |

Main declares `--jdk-path`, `--inference-jar-paths` and `--delombok-mode`.
JavaSrc2Cpg declares JAVASRC_JDK_PATH. AstCreationPass selects configured JDK
path before that environment value, then java.home; it adds source and
inference-jar solvers, and can warn/skip individual inference solver failures.
These are source-level observations, not accepted launcher flags, complete
loaded-class attestation, successful native type resolution or proof that the
retained unresolved String types have one particular cause.

Future JDK/classpath work needs a separately reviewed closed-profile extension,
immutable artifact inventories, duplicate-type/ordering policy, actual routing
tests and fresh bounded producer controls. On-disk jar hashes alone do not
prove the executed class loader used those bytes. Keep JAVA_STATIC_V1 unchanged
and obtain separate engineering/resource approval before any new native run.

## 11. Action checklist and merge handoff

### #393 first-slice actions

- [x] Root reviewed this exact contract, limits, API and redundant raw/normalized
  transport check before any implementation code is written.
- [x] Implement only the four assigned model/wire/test files after approval.
- [x] Verify all OBS/WIRE tests on retained and controlled inputs, with actual
  unit marker selection; report skips and evidence scope honestly.
- [x] Obtain independent scoped code review after the bounded compressed-input
  correction; root reran 145 dedicated tests with no skips and approved this
  observation-only slice. That review is not canonical merge approval.
- [x] Run normal lint/type/secret/hygiene hooks without bypass. If exact retained
  evidence hashes require reviewed secret-baseline entries, request that narrow
  additional file authority rather than broad-excluding this document.
- [ ] Wait for #382's actual approved merge; integrate reviewed main and rerun
  relevant checks before a dependent PR/review. Do not edit #382 or #391 trees.
- [ ] Obtain final-head CI and canonical APPROVE before root's merge/board step.
  #393 can close its narrow scope; #362 and full R19 remain open.

### Required separately assigned follow-ups

- [ ] R19-B semantic projection/encoding extension and namespace consumers.
- [ ] Source-syntax supplement and unambiguous native/source association.
- [ ] Reviewed Java JDK/classpath/profile/runtime evidence, preserving safety.
- [ ] R19-C Java/Python resolution, parameter kinds, defaults, unpacking and
  actual/formal/return-result proofs.
- [ ] R19-D finite access-path transfers, matched summaries and true witnesses.
- [ ] R02/R06 operation/type/alias/effect/purity certificates and full genuine
  extraction/inline positive and negative corpus evidence.
- [ ] Trusted source/spec/runtime binding, parsing coverage, durable raw
  retention before identity, output/provenance and real G1/G2 integration.

No checklist item is completed merely by writing this contract. No historical
CLAR is declared resolved and no whole R-task or submission claim is accepted.

### Local verification checkpoint — 2026-09-25

This implementation was tested on Python 3.11.16 with the declared compatible
development closure, based on the frozen dependency commit recorded above.
These results describe local retained/synthetic tests, not a fresh native
frontend campaign, production integration, or final merged artifact:

- Dedicated model/wire suite with `-m unit`: **145 passed, 0 skipped**.
  Both modules carry the unit marker; the pre-push expression
  `(unit or invariant) and not integration and not falsifier and not empirical`
  includes them, as does CI's `unit or invariant` selector.
- Full `tests/unit tests/integration` suite after the resource correction:
  **1,466 passed, 48 skipped**. Existing environment/stage-dependent skips are
  not new acceptance evidence. Scratch JUnit: `/tmp/scanipy-r19b-typed-full-final.xml`.
- Independent root scoped review: **145 passed, 0 skipped**; scratch JUnit
  `/tmp/scanipy-r19b-393-root-review.xml`. No canonical approval is inferred.
- Ruff, strict mypy and every applicable scoped pre-commit hook passed.
  One exact inline secret-scanner exception marks a reviewed synthetic
  diagnostic-redaction sentinel, not a credential or broad path exclusion.
- A deterministic 4 MiB incompressible transport regression instruments each
  zlib call: compressed input per call is at most 64 KiB. It prevents recurrence
  of the independently diagnosed whole-remaining-input tail-copy pattern.
  Truncation, concatenation and trailing data in unread chunks remain rejected.

Scratch files are local diagnostics, not an archived release evidence bundle.
Re-run integration after #382's approved merge and on the final PR head before
requesting canonical review. Keep every separately assigned follow-up above open.
