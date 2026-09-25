# R19-A — opt-in Joern raw-v2 producer contract

Status: IMPLEMENTED LOCALLY; real bounded probes passed; CI and review pending.
Issue: #376, under full-delivery #362. Owner: schema/ingest agent, explicitly
assigned by the root coordinator. Board synchronization is pending API quota;
local ownership is authoritative for avoiding duplicate work, not a DONE claim.

Authority: the current BHMEA execution handoff and adopted R19 dependency order.
Old PLAN/SDD/WBS documents are preserved; no historical CLAR is resolved here.

## Boundary

This slice adds a NEW `export_cpg_v2.sc` and strict raw-document reader only.
Existing `export_cpg.sc`, default frontend/mapper/archive, solver, canonical
encoding, images and production routing remain unchanged. Selecting v2 requires
an explicit trusted invocation. Never feed v2 to a v1 mapper by dropping fields.
This is not R19-B/C/D, resolved call-flow, purity or full R19 acceptance.

Trusted launcher invocation is `joern --script <trusted export_cpg_v2.sc>` via
the unchanged `secure_run` allowlist. Required explicit environment keys:
`SCANIPY_CPG_BIN_PATH`, `SCANIPY_EXPORT_V2_JSON_PATH`,
`SCANIPY_EXPORT_V2_SCRIPT_PATH` (the actual invoked trusted file),
`SCANIPY_EXPORT_V2_SOURCE_ROOT`, `SCANIPY_EXPORT_V2_FRONTEND`, and
`SCANIPY_EXPORT_V2_IMAGE_ID` (observed outside the container). The launcher
controls these values; target-source contents do not select the script.
`parse_raw_export(bytes_or_text, require_completed=True, max_bytes=67108864)`
returns a validated raw JSON document, not a graph or solver input.

Raw facts are losslessly preserved within pinned Joern CPG-domain 1.7.65:
all node kinds/properties and directed multiedges, including edge properties.
The checked-in schema catalog records each pinned node kind's legal properties,
native type and cardinality, plus every edge label/property. It is extracted
from the actual pinned schema, not inferred from one fixture. Unknown versions,
labels/properties/types or shape changes fail closed. No type coercion is allowed
(in particular, booleans are not integers). Raw defaults/ANY/unknown strings
remain observations; none are interpreted as resolution/type/purity proof.

## Wire envelope

The top-level object has exactly:

- `format`: literal `scanipy-joern-export`.
- `format_version`: integer 2 (not a string or bool).
- `status`: `completed` or `failed`.
- `producer`: provenance object described below.
- `capabilities`: required capability records described below.
- `nodes`: array of node objects on success; null on failure.
- `edges`: array of edge objects on success; null on failure.
- `error`: null on success; `{code,message}` on failure.

Each node has exactly `id`, `kind`, `properties`, `missing_properties`. ID is a nonnegative canonical
decimal string; raw IDs are graph references, not canonical labels. Properties
are a strict map of pinned property names to native JSON string/int/bool/list
values; absent optional values are omitted, never replaced by guessed strings.
Scalar/list shape follows schema cardinality; unsupported property types fail.
`missing_properties` is the exact sorted list of schema QtyOne properties absent
from the actual node. The pinned Python frontend emits BINDING nodes without
METHOD_FULL_NAME/SIGNATURE despite that cardinality. Preserve this unavailable
evidence explicitly; never synthesize defaults to satisfy the schema. Raw
enumeration completeness is not a claim that every node has usable bindings.
The native `propertiesMap` is sparse and can also omit default-valued booleans
or indices. Absence is retained, not turned into false/-1 by this exporter.
Interpreting such defaults is a separate versioned semantic-model decision.

Each edge has exactly `src`, `dst`, `kind`, `properties`. Endpoints must exist;
kind and property keys follow the pinned catalog. The `REACHING_DEF` `VARIABLE`
string is retained, including empty observed values. No edge-property name is
invented. Edge order is not semantic and parallel edges remain distinct; reader
does not deduplicate. Export order is stable sorting of raw reference/record
values for diagnostics only, NOT a canonical graph hash.

Reader rejects duplicate JSON keys/IDs, malformed IDs, dangling endpoints,
unknown fields/schema versions and property type/cardinality violations. It
validates raw role endpoints for CALL, ARGUMENT, RECEIVER, REF and PARAMETER_LINK
where pinned node roles are unambiguous. AST parent ownership must be unique
and acyclic (duplicate edges to the same parent remain distinct observations).
Formal input/output and method-return nodes require a direct METHOD AST owner;
PARAMETER_LINK endpoints must have that same owner. These structural ownership
checks do not establish actual/formal binding or call-target completeness.
It does not invent actual/formal edges,
complete dispatch targets, inferred effects or AST-normalized pure expressions.

## Provenance

Producer has exactly `schema_version`, `image`, `tools`, `script`, `input_cpg`,
`source`, `frontend`, `import_mode`, `java_runtime_version`, `java_tool_options`.

- `schema_version`: integer 1 for this producer metadata contract.
- `image`: `{kind,reference,observation}`; kind=`docker-image-id`, reference is
  actual `sha256:` image ID supplied by the trusted launcher after Docker inspect,
  observation=`caller-observed`. The script cannot independently attest Docker's
  image ID; this limitation is explicit and retained container inspection must
  agree. A registry-manifest digest is not substituted for a different image ID.
- `tools`: exact role/version/path/sha256 records for the actual Joern CLI,
  selected Java/Python frontend, CPG-domain and flatgraph-core jars. Versions
  come from the loaded runtime artifacts and must match the supported pin.
- `script` and `input_cpg`: `{path,sha256}`, computed from actual trusted exporter
  script and supplied binary bytes. Paths locate evidence; digests bind content.
- `source`: `{root,tree_namespace,tree_sha256,files}`. The immutable input source
  root is inventoried as sorted relative UTF-8 POSIX paths and `{path,size,sha256}`
  regular-file records. Symlinks and nonregular entries are rejected. Tree hash
  is SHA256 over `scanipy-source-tree/1\0`, then for each UTF-8-byte-sorted path:
  big-endian u64 path length, path bytes, big-endian u64 size, 32 digest bytes.
  Empty directories are not parser inputs. No file is executed to obtain this.
  Sizes above `2^53-1` fail because the pinned Scala JSON library cannot encode
  them as exact integers. Native graph IntType properties remain signed 32-bit.
- `frontend`: `javasrc` or `pythonsrc`, checked against graph metadata language;
  claimed language cannot silently select a different frontend.
- `import_mode`: literal `importCpg-default-overlays`; runtime graph metadata
  retains its actual overlay list. Import/overlay processing is not hidden.
- Actual JVM version and explicit JAVA_TOOL_OPTIONS are recorded; the launcher
  retains exact parse/export argv and allowlisted nonsecret environment as
  separate evidence. Do not dump unrelated environment variables or secrets.

Source and tool hashes bind artifacts, not a proof that an arbitrary caller's
CPG was derived from the declared source. The bounded evidence driver must run
the actual static parser against that immutable source, retain argv/results,
then invoke this exporter; no provenance may be fabricated to satisfy tests.

## Capabilities and failure

Every capability record is `{status,reason}`; status is `completed`, `failed`,
or `unsupported`. Required records are `raw_nodes`, `raw_edges`,
`typed_properties`, `call_target_completeness`, `actual_formal_binding`,
`return_result_binding`, `effect_analysis`, `purity_certification`.

Completed raw export requires all first three completed. The remaining five are
always unsupported in R19-A, with explicit reasons: raw candidate edges and
properties are not proofs of those derived semantics. Empty raw edge sets do
not mean a derived capability is complete.

Any node/edge/property traversal or serialization error fails the export; do not
catch a per-role exception and emit empty successful arrays. If provenance has
been established, an atomic failed envelope is written with null arrays,
failed raw capabilities and a nonzero process exit. Earlier boot/provenance or
write errors may leave no envelope and must fail the process. The launcher must
require both successful process status and a valid completed document; stale
previous output is never evidence of this attempt. Writer refuses an existing
output path and publishes a fully written same-directory temporary file with
an atomic no-clobber hard link, then removes the temporary link. Unsupported
filesystem operations fail rather than silently falling back to overwrite.

## Required role evidence and non-claims

Real Java and Python static fixtures must expose:

1. Internal helper call candidate target, explicit receiver vs arguments,
   formal index/name/strategy, and normal return value/exit.
2. Java instance/static/overloaded calls and varargs; Python positional/keyword/
   default/star-argument forms and a receiver whose callee expression differs
   from its bound object. Ambiguity stays raw/unresolved.
3. Identifier REF targets; field/index access operands; actual type and method
   signatures; native bool/int/list properties; REACHING_DEF VARIABLE payload.
4. A Python RETURN whose value includes a BLOCK; source synthetic adapters are
   preserved and not confused with user helpers.
5. Unknown external/dynamic calls and effectful writes, with unsupported
   resolution/effect/purity capability; no fabricated proof or blanket purity.

Use strict-parser malformed/version/type/shape/endpoint tests and mutation
controls that would fail if semantic role edges/properties were dropped. Retain
the raw real exports, source bytes, exact commands, tool identities and negative
outcomes. These are raw producer tests, not an IFDS witness, extraction invariant,
Algorithm-2 benchmark, or full submitted demo.

## Safety and completion

All probes use bounded disposable network-none containers, non-root UID,
read-only root/repository/source, no capabilities, no-new-privileges and only
task-owned writable work directories. Run pinned static frontend binaries, never
scanned source, its tests, build hooks or repository-provided commands. Preserve
the running app/DB and old R05 evidence. No remote merges/releases are authorized
in this work package. Completion requires real typed export evidence, strict
reader falsifiers, unchanged v1 regression tests, required CI and review.

## Observed evidence and downstream TODOs

The retained [probe evidence](../tests/fixtures/joern_raw_v2/README.md) contains
actual Java (199 nodes / 1,022 edges) and Python (442 nodes / 2,435 edges) exports,
exact parse/export commands, stdout/stderr, caller-observed container inspection,
and actual source/script/tool hashes. Both static parsers and exporters exited
zero and the strict reader accepted their raw envelopes. Three real negative
attempts reject mismatched frontend metadata, preexisting output and source
symlinks. No target code or build hooks were executed.

The following observations are REQUIRED downstream falsifiers, not acceptance
of those semantics. A nonzero CALL-edge count is insufficient for all of them.

| Observation in this pinned runtime | Required next action / owner boundary |
| --- | --- |
| Java String types are `<unresolvedNamespace>.String`; overloaded String/int helpers share unresolved FULL_NAME/SIGNATURE, despite distinct GENERIC_SIGNATURE and node IDs. The int call's candidate points to the String declaration. | R19-B: specify and attest actual Java toolchain/JDK/classpath; preserve declaration identity and ambiguity. R19-C: verify overload binding or mark unsupported, never choose by name/arity alone. |
| Source-static Java helper calls carry DYNAMIC_DISPATCH and a synthetic `this` receiver. | R19-B/C: reconcile native facts with declaration modifiers and language rules; raw DISPATCH_TYPE is not a correctness certificate. |
| Java varargs call targets an external placeholder; the source `String... rest` formal omits stored IS_VARIADIC. | R19-B/C: preserve the absent property and source role; support explicit vararg binding with falsifiers or report unsupported. No inferred false boolean. |
| Python named actuals carry ARGUMENT_NAME but omit ARGUMENT_INDEX; defaulted call has only one actual; star/dict actuals retain raw adapters. | R19-B/C: implement keyword/default/star binding, collision/arity checks and explicit unsupported dynamic cases. Do not assign positions from raw enumeration order. |
| Python RECEIVER is the callee expression (`tmp0.execute`), while argument zero is the bound object (`tmp0`); normal arguments start at one. | R19-B/C: model receiver, bound object and actual/formal roles independently; map DSL positions explicitly. |
| Python RETURN value is a BLOCK with a synthetic assignment and fetch call; parallel REACHING_DEF edges have distinct VARIABLE strings. | R19-B/D: preserve expression/return nesting and typed edge payloads, then implement matched call/return summaries and finite access paths. |
| Native ANY/unknown types and sparse default properties remain common; field writes and arbitrary external calls exist. | R02/R06/R19-D: add real type/binding/effect/purity certification and meaningful positive/negative pure-extract cases. Raw completion grants no purity or suppression eligibility. |

Next slices remain dependency ordered: R19-B versioned semantic graph and
encoding extension; R19-C language-aware call/actual/formal/return binding;
R19-D access-path facts and fixpoint summaries; then extraction/purity and
end-to-end submitted-language acceptance. Coordinate future producer routing
with R05's frontend observer owner. Do not silently add semantic fields to the
existing canonical v2 minimal-graph encoder, which rejects unknown semantics.

Local raw-v2 acceptance is limited to the strict transport contract and retained
role evidence. Full R19, R02/R06 extraction invariance, Algorithm-2 conformance,
durable occurrence retention and the complete BHMEA demo remain separate open
requirements. Their failure must never be converted to a successful empty graph.
