# Runtime metadata and request/launch codecs — bounded pure contract

Date: 2026-09-26 PKT. Tracking: #400, root-coordinated runtime foundations.
Status: root-approved implementation contract; the five source/test edits are
allocated in section 14. The consolidated metadata and corrected packet
designs have scoped root and independent peer approval. This is engineering
coordination under [DECISION-BHMEA-01](../DECISION-BHMEA-01-current-execution-authority-2026-09-25.md),
not an operator installation, current authority, runtime admission or completed
Black Hat acceptance result. Section 15 records the local implementation checkpoint;
section 16 records subsequent root review. Repository acceptance remains pending.

## 1. Precedence, scope and exact ownership

This document consolidates the reviewed 136-line metadata proposal and corrected
174-line request/launch proposal. It makes their complete behavior available in
the repository; no temporary file, task-specific path or supplied context is an
implementation dependency. Preserve [LOCAL-RUNTIME-PROFILE](LOCAL-RUNTIME-PROFILE.md),
[LOCAL-RUNTIME-DOCKER-POLICY](LOCAL-RUNTIME-DOCKER-POLICY.md) and
[RUNTIME-ARTIFACT-INVENTORY](RUNTIME-ARTIFACT-INVENTORY.md). This contract adds pure
owner codecs and one intended-inner-invocation helper. It does not replace their
loader, measurement, mount, image, bootstrap, kernel or currentness obligations.

The corrected packet design explicitly adds the supplied lease-expiry comparison
in section 7 and distinguishes tagged-output slots from total heap allocation.
These are preimplementation closures, not silent changes to deployed wire data.
The original metadata proposal's statement that request/launch ownership remained
unallocated is superseded by this cohesive allocation. The earlier proposed
four-member helper in `runtime_profiles` is superseded by
`runtime_packets.decode_runtime_recipe_members`; do not create a weaker alias.

The exact five allocated source/test files are:

- Existing `tools/worker/runtime_profiles.py`: shared pure metadata extraction.
- Existing `tools/worker/runtime_docker_policy.py`: pure intended inner grammar.
- New `tools/worker/runtime_packets.py`: request/launch schemas and four-member join.
- New `tests/unit/test_runtime_profile_documents.py`.
- New `tests/unit/test_runtime_packets.py`.

The two new test modules must carry the actual `unit` selector marker. Existing
loader, inventory and renderer tests remain unchanged and must still pass.
Do not edit accepted-input, analysis, PE, inventory or domain-worker schemas,
source codecs, worker/controller defaults, database code or installation state.
No filesystem, network, process, clock, measurement, dynamic loading or caller
callback occurs in the new pure entrypoints. Existing loader operations retain
their independent filesystem/deadline behavior. No operational refusal is removed.

## 2. Actual owner dependencies and data-only APIs

Use the actual public accepted-input `codec.decode_record`, `canonical_bytes`,
models and schemas; the actual `analysis.ifds.bound_rules` qualified-key codec
and `decode_bounded_json`; actual PE `StoredObject`/`StoredArray`; actual
`RuntimeArtifactBindings`, `RuntimeFileBinding`, `RuntimeRootBinding`; and actual
bounded-process `FrozenInvocation`. Never copy these types or invoke a private
foreign validator, filesystem loader or diagnostic worker to simulate a codec.

```text
runtime_profiles.decode_runtime_metadata_documents(
    installation: bytes, controller_profile: bytes
) -> RuntimeMetadataDocuments

runtime_packets.decode_runtime_request(data: bytes) -> RuntimePacket
runtime_packets.encode_runtime_request(document: StoredObject) -> bytes
runtime_packets.decode_runtime_recipe_members(
    request: bytes, launch: bytes, installation: bytes, controller_profile: bytes
) -> RuntimeRecipeMembers
runtime_packets.encode_runtime_launch(
    document: StoredObject, *, request: bytes, installation: bytes,
    controller_profile: bytes
) -> bytes

runtime_docker_policy.render_runtime_inner_invocation(
    *, purpose: str, python_executable: str, worker_path: str,
    domain_profile_path: str, domain_profile_sha256: bytes, attempt_id: str,
    stdin_bytes: int, stdin_sha256: bytes
) -> FrozenInvocation
```

New carriers have exactly these fields, frozen slots and `repr=False`:

```text
RuntimeMetadataDocuments(
    installation_bytes: bytes, controller_profile_bytes: bytes,
    installation: StoredObject, controller_profile: StoredObject,
    bindings: RuntimeArtifactBindings, input_bytes: int,
    validation: Literal["input-structure-only"]
)
RuntimePacket(
    kind: Literal["request", "launch"], data: bytes, document: StoredObject,
    validation: Literal["input-structure-only"]
)
RuntimeRecipeMembers(
    metadata: RuntimeMetadataDocuments, request: RuntimePacket,
    launch: RuntimePacket, validation: Literal["input-structure-only"]
)
```

Preserve every original raw byte. Runtime bindings contain fresh actual file/root
records and `PosixPath` values constructed from private validated strings, never
caller paths or cached path strings. Constructing or mutating any carrier grants
nothing. Public consumption revalidates original bytes, not validation labels,
cached digests, mutated bindings or constructor history. Inputs are exact bytes
or bounded exact PE tagged primitive tuples, never public dict/model/anchor/
provider/context/budget inputs. Only fresh private JSON reaches owner decoders.

## 3. Primitive and wire domains

All keys listed below are required; unknown keys reject. `J` is compact,
sorted-key, UTF-8 canonical JSON. Reject duplicate keys, nonfinite values,
floats, coercion, trailing bytes, NUL and non-scalar Unicode. Integers are exact
signed64 values unless a narrower range is stated; booleans are not integers.
UUIDs are canonical lowercase hyphenated text. `H` is 64 lowercase hexadecimal
SHA256 text on wire and exact 32-byte bytes where an API specifies bytes.
`D(s,b) = SHA256(ASCII(s) + LF + b)` is distinct from raw `H(b)`.

`T` is a valid calendar UTC instant with six fractional digits and final `Z`.
IDs match `[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}` unless an actual nested owner uses
its own narrower domain. Normal `Text` is at most 4096 UTF-8 bytes. Absolute
paths are nonroot, at most 4096 UTF-8 bytes, and have no empty/dot/dot-dot
component, backslash or C0/DEL/C1 control. Relative source paths are at most
1024 UTF-8 bytes and 32 components, with those same exclusions and no leading
slash. No path is opened by these pure functions.

## 4. Complete installation schema

Closed `scanipy-local-runtime-installation/1`:

```text
schema, deployment_id: UUID, installation_id: UUID, generation: positive64,
purpose: "accepted-verifier" | "python-syntax",
controller_uid: 1..2147483647, controller_gid: 1..2147483647,
controller_profile: {path: AbsolutePath, sha256: H},
domain_profile: {path: AbsolutePath, sha256: H},
inventory: {path: AbsolutePath, sha256: H},
docker_cli: {path: AbsolutePath, sha256: H, version: ID},
docker_endpoint: {path: "/run/docker.sock", owner_uid: 0,
                  owner_gid: 0..2147483647, mode: 432},
daemon: {id: ID, version: ID, api_version: "1.52", minimum_api_version: "1.44"},
host_work_root: AbsolutePath, evidence_root: AbsolutePath, installed_at: T
```

These fields are supplied data, not observed owner, socket, daemon or filesystem
state. `generation` ranges from 1 through `2**63-1`. Pure decoding does not hash
the profile bytes to validate the installation descriptor; section 10 assigns
that raw-byte link explicitly to the consuming owner.

## 5. Complete controller-profile schema

Closed `scanipy-local-runtime-profile/1`, exact top-level fields:

```text
schema, purpose, domain_profile_sha256, inventory_sha256, program_digest,
runtime, platform, image, bootstrap, container, scratch, limits, io, config_policy
```

Purpose equals the installation purpose. Domain and inventory H equal the
corresponding installation descriptor H, without claiming actual file hashing.
`runtime` has the actual `RuntimeArtifactBindings` wire fields:

```text
purpose, implementation: "cpython", python_version, protocol_version,
resource_profile, executable: {path, sha256}, worker: {path, sha256},
roots: [{role, ordinal, path}], application_digest: H, dependency_digest: H,
program_digest: H
```

Runtime root order is stdlib, application, dependency; ordinals start at zero
and are contiguous within each role. There are 3..9 roots: 1..4 stdlib, exactly
one application, 1..4 dependency. All normalized root paths are unique. Python
version is exactly `3.11.P`, P in 0..2147483647 without leading zero. It agrees
with platform version; runtime purpose and outer/runtime program digests agree.
Verifier protocol/resource are `scanipy-accepted-verifier-request/1` and
`scanipy-verifier-limits/1`; syntax uses `scanipy-python-syntax-request/1` and
`scanipy-python-syntax-limits/1`. Do not recompute program/file identities here.

```text
platform = {os: "linux", architecture: "amd64", implementation: "cpython",
            python_version, cgroup_version: 2, cgroup_driver: "systemd"}
image = {config_id: "sha256:" + H, oci_manifest_digest: "sha256:" + H | null,
         os: "linux", architecture: "amd64", variant: null}
bootstrap = {path: AbsolutePath, sha256: H, protocol: "scanipy-runtime-bootstrap/1"}
container = {uid: installation.controller_uid, gid: installation.controller_gid,
             network: "none", pid: "private", ipc: "private", cgroupns: "private",
             userns: "host", readonly_root: true, privileged: false,
             capabilities: [], no_new_privileges: true,
             seccomp: "docker-builtin-default/29.1.3", apparmor: "docker-default",
             restart: "no", auto_remove: false, init: false, tty: false,
             log_driver: "none", ports: [], devices: []}
scratch = {work_root: "/run/scanipy-work", bytes: 8388608, inodes: 1024,
           mode: 448, nosuid: true, nodev: true, noexec: true}
config_policy = "scanipy-docker29-pipe-config/1"
```

`limits` has exactly these keys and values:

```text
memory_bytes = memory_swap_bytes = 134217728 verifier / 268435456 syntax
pids = 16; cpu_quota_us = 100000; cpu_period_us = 100000; shm_bytes = 65536
max_mounts = 64; max_bind_mounts = 16
max_additional_tmpfs_bytes = 67174400; max_additional_tmpfs_inodes = 32768
inner_wall_ms = 3000 verifier / 5000 syntax; inner_cleanup_ms = 500
launch_wall_ms = 30000; pre_release_ms = 10000; cleanup_ms = 5000
max_cli_calls = 16; max_kernel_observations = 16
```

`io` has exactly `stdin_bytes`, `stdout_bytes`, `stderr_bytes`, `combined_bytes`:
verifier 2621440/16384/16384/32768; syntax 263244/8388608/65536/8454144.
Every fixed literal is checked by exact type as well as value.

## 6. Shared extraction without weakening the loader

Split current `_installation` into pure document checks and existing independent
anchor equality. Validate candidate purpose as the closed enum; never synthesize
`RuntimeInstallationAnchor` from candidate documents. Split `_profile` similarly:
pure value linkage uses the validated installation purpose and UID/GID. Keep
compatible private loader wrappers and use the same field validators in both
paths, not parallel copied validation.

`load_installed_runtime` must retain the existing sequence: independently snapshot
the actual anchor; validate installation against it; perform origin separation
before reading the next metadata file; validate profile and full metadata/runtime
separation before domain/inventory reads; measure through the actual inventory
owner; check bootstrap membership; recheck held files; close and perform final
deadline admission. No formerly protected read moves before its anchor check.

Share canonical parser/preflight/value/escaped-byte logic. Private parsing accepts
only an internally created exact `_Budget` or `None`. Fixed module-owned checkpoint
code checks that type and invokes `_Budget.check(value)` only in the loader path;
never dispatch through caller-controlled instance methods. `None` is not a public
timing flag: the pure path offers no authority or loader operation to disable.
Keep all 35-second, filesystem, cleanup and original-interruption constraints.

The pure API has no installation-origin path, so it cannot perform `_separation`
with an invented origin. Metadata may not serve as an installed anchor. Opaque
domain-profile interpretation, complete inventory traversal, bootstrap inclusion,
actual UID/GID/platform/image/kernel/CLI and current trust remain later obligations.

## 7. Complete outer request and nested owner records

Closed `scanipy-local-runtime-request/1`:

```text
schema, operation_id: UUID,
mode: "verifier-publication" | "verifier-historical" |
      "verifier-execution" | "python-syntax",
deployment_id: UUID, installation_id: UUID, installation_generation: positive64,
controller_profile_sha256: H, domain_profile_sha256: H,
input: {size: positive64, sha256: H, protocol: ID},
binding: {bundle: BundleExpectation, execution: ExecutionBinding | null,
          qualified_rule: QualifiedRuleKey | null, source: SourceBinding | null},
prerequisite: LaunchPrerequisite
```

Input size is positive and at most 2621440 for verifier modes or 263244 for
syntax. Protocol is respectively `scanipy-accepted-verifier-request/1` or
`scanipy-python-syntax-request/1`. Use actual accepted owner schemas/model
decoding for `BundleExpectation`, `ExecutionBinding` and `AdmissionExpectation`,
and the actual qualified-key codec. Do not serialize caller-poisoned models.

`SourceBinding` is exactly `{capture_id: UUID, source_tree_algorithm: ID,
source_tree_digest: H, inventory_sha256: H, path: RelativePath,
size: 0..262144, sha256: H}`. Retain the declared algorithm; only the actual
capture owner can establish supported framing and original file membership.
Source H is not the framed input packet H. No source is opened or declaration
planted. If source is present, its capture ID equals execution capture ID.

All modes are customer-only: bundle scope is customer with nonnull org. Every
carried org agrees. A selected key's registry/scope/org/bundle/S_version/content
digest equals the actual bundle. This small namespace does not establish full
accepted content membership or rule/model semantics.

`LaunchPrerequisite` has schema `scanipy-local-launch-prerequisite/1` and exact
additional keys:

```text
reader_id: ID, observation_id: UUID, observed_at: T, valid_until: T,
principal_id: ID, org_id: UUID, action: ID,
authentication_evidence_sha256: H, scope_evidence_sha256: H,
admission: AdmissionExpectation | null, execution_authorization_digest: H | null,
capture_lease_evidence_sha256: H | null, content_verification_evidence_sha256: H | null
```

Require `0 < valid_until - observed_at <= 60 seconds`. Execution/syntax also
require `valid_until <= min(execution.lease_expires_at,
execution.capture_lease_expires_at)`. These are supplied timestamp comparisons,
not host-clock or authority checks. Actual currentness, authenticated session,
current policy/checkpoint expiry and independent live lease reads stay with the
owning adapters. Authentication/scope hashes never become nullable.

| Mode | Exact action | Admission | Execution / key / source | Authorization / capture / content H |
|---|---|---|---|---|
| verifier-publication | publish-builtin-preflight | present | null / null / null | null / null / null |
| verifier-historical | audit-historical | null | null / null / null | null / null / null |
| verifier-execution | verify-execution | present | present / present / null | present / present / null |
| python-syntax | parse-python | present | present / present / present | present / present / present |

Authorization D equals `execution.authorization_digest` where present. Never
compare it with a raw evidence hash. There are no unspecified optional bindings,
signature/principal-authentication checks or inferred accepted-state flags here.

## 8. One renderer-owned intended inner invocation

The helper in section 2 validates exact primitive arguments using the existing
renderer path/UUID/digest/bounds helpers. Never create a fake
`RuntimeDockerCreateSpec` or call the outer renderer with invented pins. Purpose
is exactly accepted-verifier or python-syntax. Let
`P = /run/scanipy-work/<canonical attempt UUID>`; cwd is P and cache P/pycache.

```text
verifier argv = (exe, "-I", "-S", "-B", "-X", "utf8", "-X",
                "pycache_prefix=" + P + "/pycache", worker, "--profile",
                domain_profile_path, "--profile-sha256", raw_profile_H)
verifier environment = sorted LANG=C.UTF-8, LC_ALL=C.UTF-8, TZ=UTC

syntax argv = (exe, "-I", "-S", "-B", "-X",
               "pycache_prefix=" + P + "/pycache", worker)
syntax environment = sorted HOME=P/home, LANG=C.UTF-8, LC_ALL=C.UTF-8, TMPDIR=P/tmp
```

Runtime/profile paths must be normalized nonroot paths disjoint from P. Full
mount, reserved-path and layout checks remain the outer renderer/loader's duties.
Argv has at most 64 members, each at most 8192 UTF-8 bytes and total at most 65536.
Environment has at most 16 sorted unique rows, name at most 128/value at most
8192 bytes and total at most 16384 bytes. Input bounds are section 7's positive
mode limits; input H is exact 32-byte bytes. No ambient environment merge or
bootstrap PATH/HOSTNAME leakage is permitted.

Return the actual `FrozenInvocation` with these intended argv/environment/cwd/
input fields. Existing `render_runtime_docker_create` and shared invocation
behavior remain intact. Both future launch assembly and packet decoder call this
same helper and compare every field. It observes or launches nothing, and does
not call the diagnostic verifier launcher. Fresh/private cache and actual child
environment are later bootstrap/controller observations, not facts from rendering.

## 9. Complete launch and four-member nonhash join

Closed `scanipy-runtime-bootstrap-launch/1`:

```text
schema, attempt_id: UUID, operation_id: UUID, request_digest: H,
deployment_id: UUID, installation_id: UUID, installation_generation: positive64,
mode, image_config_id: "sha256:" + H,
controller_profile_sha256: H, domain_profile_sha256: H, inventory_sha256: H,
inventory_digest: H, program_digest: H, input: section-7 input shape,
inner: {argv: [Text], environment: [{name: Text, value: Text}], cwd: AbsolutePath},
container_uid: 1..2147483647, container_gid: 1..2147483647,
release_filename: "release.json", bootstrap_wait_ms: 10000,
inner_wall_ms: 3000 verifier / 5000 syntax, inner_cleanup_ms: 500
```

All four raw input types/sizes are admitted before any nested decode. Call the
metadata pair decoder once, request validator once and launch validator once.
Share privately validated rows for joins instead of reparsing them in each field
check. Request deployment/installation/generation match installation; its mode
maps to the metadata purpose. Launch repeats request IDs/mode and exact input.
Declared controller/domain pins agree across request/launch/installation/profile;
launch UID/GID, image/program/inventory pins and fixed limits agree with metadata.
Inventory D is not available from metadata equality alone: section 10 applies.

Derive the inner invocation from actual metadata bindings.executable/worker,
installation.domain_profile.path and declared H, launch attempt ID and exact
input fields. Compare all inner fields, not just selected argv entries. Return
the actual metadata-pair result and packet views, not copied binding types.
The launch encoder canonicalizes its bounded candidate then executes this same
join; no separate weaker launch writer, decoder or compatibility alias exists.

## 10. Raw links and zero-hash delegation

Pure metadata extraction, nested model/key decoding and intended rendering do
zero SHA calls per invocation. The four-member facade compares complete local
structures, nonhash links and repeated declared hashes. It does not certify
request D, raw metadata hashes or inventory D against unavailable original bytes.

The concrete consuming claim/recipe codec reserves and computes the four raw
member hashes plus request D once. It compares installation.controller_profile H
with H(profile bytes), request/launch controller H with that value, claim
installation H with H(installation bytes), and launch.request_digest with
D(`scanipy-local-runtime-request/1`, exact request bytes). It also enforces its
recipe/header/claim byte links and own domain digests. Full inventory D and
program/file identities require the actual inventory owner; D is never replaced
by raw inventory H. Do not add a hidden hash/redecode in the pure facade.

Instrument actual helpers, including malformed late inputs. The separate claim
codec's proposed 6/8/10 hash schedule remains conditional on measured zero-hash
delegation; this document does not implement that codec. Existing module-import
constants are not a newly observed per-invocation hash operation.

## 11. Finite parser/writer allocation and error contracts

Metadata checks both exact byte types and lengths before parsing either input:
installation 1..65536, profile 1..131072, combined at most 196608. Each has
lexical depth 16 and at most 20000 values including keys. Put the existing
20-character integer/range admission into shared lexical preflight before generic
JSON allocation, retaining the existing parse-int defense. Valid wire is unchanged.
Bound original and canonical escaped-byte sizes before JSON encoding.

Parse each metadata input once and freeze each private tree once. Combined
admitted JSON values/keys are at most 40000; tagged tuple member slots at most
120000 (at most three per admitted value/key). These are not total parser,
PosixPath or CPython heap/RSS bounds. Actual filesystem/time bounds still belong
to the unchanged loader; the pure entrypoint has no clock or timing switch.

Each request/launch is at most 65536 bytes, depth 16 and 8192 key-inclusive values;
use actual public `decode_bounded_json` with these lower bounds and accepted
`canonical_bytes`, not a copied lexical parser. Normal string caps are section 3,
with section 8's argv/environment exceptions. Four raw members total at most
327680 bytes; their admitted JSON values/keys total at most 56384 and tagged
output slots at most 169152. No total heap, RSS or elapsed-time guarantee follows.

Writers snapshot exact StoredObject tags/tuples/leaves with visited-plus-queued
and escaped-byte admission before private JSON construction or encoding. Share
the same schema checks as readers. No inner input decoding, whole-bundle
membership, file hashing, clock, process or caller callback hides in these bounds.

Metadata reuses `RuntimeProfileError`, with pure reasons metadata-invalid, limit,
unsafe-path, unsupported. Unknown purpose/target Python version is unsupported.
Packet errors are `RuntimePacketError`, with exact reasons invalid-input, limit,
unsupported, link-mismatch. Public messages/reprs contain fixed reasons only;
original JSON/Unicode/calendar/helper errors remain private causes. Do not format
input, paths or exceptions. Preserve KeyboardInterrupt/SystemExit identity rather
than blanket-converting BaseException. No returned carrier represents a load,
measurement, authenticated principal, container observation or launch permit.

## 12. Required controls and acceptance boundary

The scoped implementation must include:

- Both metadata purposes and all four request modes, complete field retention,
  actual shared return types, every missing/extra/nested/enum/literal/scalar/root
  order error, unknown scope/version and exact nullable groups.
- Byte/depth/value/integer/string N/N+1 admission, both metadata input sizes and
  all four member sizes checked before nested parsing, escaped writer expansion,
  exact original bytes, poisoned tuple/primitive/carrier and mutation negatives.
- Metadata pure success when declared hashes agree but actual profile H differs,
  clearly structure-only; the consuming claim owner must reject the raw mismatch.
- Request/launch writer-reader parity, crossed deployment/installation/mode/pins/
  input, actual owner bundle/key/org/capture links, raw-vs-domain distinctions.
- For execution and syntax, validity equal to each lease must pass; validity one
  microsecond beyond each must fail. Hold the other lease later and every other
  constraint valid so either lease independently constrains admission.
- Both intended argv/environment/cache grammars, all inputs primitive-snapshotted,
  no bootstrap PATH/HOSTNAME or ambient-variable inheritance; preserve outer
  renderer mount/reserved-path/security checks.
- Instrument zero SHA/FS/clock/measurement/process calls for the actual pure
  helpers, including a malformed last member. No fake operational fallback.
- Run unchanged loader/inventory/renderer tests, including early anchor mismatch,
  before-next-read separation, deadline/final cleanup, held descriptor ownership,
  interruption/cause retention and actual measurement controls. Test pure decoding
  on Python 3.11/3.12; target wire runtime remains 3.11 and loader host restrictions
  remain unchanged. No live Docker or scanned-source execution is implied.

Pure structure/linkage acceptance cannot enable a constant-refusal operational
API. Actual verifier/source input codecs must bind original inner packets and
source bytes. The installed factory still must acquire independent installed
identity, auth/session, source/capture lease, current admission and complete
accepted content. Domain profiles retain their real owners; never fabricate
VerifierRuntimeProfile, PythonSyntaxRuntime or verified context to bridge a gap.
DB claims need the real AL functions/provider, SQL parity, recipe custody and
distinct release proofs. Controller/bootstrap, capacity/work qualification,
real native frontends, full R-task/claim acceptance and G0–G3 remain separate.

## 13. Local preparation checkpoint, not implementation evidence

This worktree began at reviewed controller `0dbee6e`. Accepted main `95fa5d1`
integrated normally as `e3ee29e`; all 12 incoming changed paths matched its bytes.
Reviewed inventory `40ba98a` integrated as `b11d2ca` with no additional tree diff;
the three inventory files already matched exactly. No content conflict occurred.
At that initial checkpoint, all three supplied parent snapshots contained 166
secret-baseline records, preserved without edits. Its tree matched root's
separately tested controller integration: the reported 638 affected checks apply
to that earlier tree, not the subsequent owner-dependency combination below.

Root then authorized actual owner dependencies, integrated by normal full merges:

- Resolver `58b552c` as `0acbc2f`: real accepted-input codecs/models/schemas and
  their reviewed dependency history, not copied or substituted owner types.
- Occurrence `cadd386` as `c7ba6bf`: the current persistence contract and adjacent
  OPEN `CLAR-BHMEA-02`, retaining `CLAR-BHMEA-01` verbatim. No source reconciliation.
- Rule codec `80f45c3` as `cb28fc2`: its owned files already matched exactly;
  the ancestry merge introduced no final tree-content change.

The resolver baseline reconciliation retained the exact authorized 167-record
union: the existing 166 records plus the reviewed semantic-model fixture hash.
All dispositions/configuration remained unchanged, including the original
generation metadata and current CI line references. Occurrence's anticipated
baseline conflict was resolved to those same bytes. Rule's automatic merge
introduced a duplicate JSON key for that already-present fixture; the explicit
duplicate-key audit caught it and only the duplicate was removed. Final baseline
bytes equal the preceding 167-record checkpoint; no exclusion or regeneration.

Final dependency HEAD is `cb28fc2`. Actual accepted-input, occurrence and rule
owner sources match their specified dependency commits. Runtime profile, Docker
policy, PE and journal sources remain byte-exact to `0dbee6e`; the three inventory
files remain exact `40ba98a`. No AL-02 or unimplemented SQL authority is imported.

Normal merge hooks passed. One inventory commit attempt failed before committing
because the agent mistyped the tool-venv PATH; the corrected normal attempt passed
without bypass. Because merge hooks inspect conflict paths, explicit changed-file
pre-commit checks were also run from `0dbee6e` through final dependency HEAD:
all applicable hygiene, JSON/YAML, secrets, Ruff lint/format, mypy, yamllint and
provenance checks passed. Nonapplicable hooks were skipped, not claimed as tests.
At that preparation checkpoint this new document awaited root review and was
not included in those committed-change checks. That checkpoint claimed no new
source implementation or test run.

Source implementation was on hold at this preparation checkpoint; section 14
records the later allocation. No full/pre-push/remote gate, installation, native
run, database action or feature acceptance is claimed by this checkpoint.

## 14. Root review and exact source allocation

2026-09-26 PKT / September 25 UTC. Root read all 505 consolidated contract
lines and both complete source proposals. Independent review compared the
entire consolidated document with metadata136, corrected packet174 and actual
loader/renderer/accepted-key/model/parser owners. It approved contract SHA256
`b56f15539df6915d0263bb236587321f90b72b56fdb09c6e1620d730aa14d229`,
finding no dropped schema, literal, nullable/lease group, hash responsibility
or protected-loader ordering. This note changes allocation/status only.

Root allocates exactly the five source/test files in section 1 plus this
document to the canonical implementation agent in this independent worktree.
Implement one usable complete metadata/request/launch codec unit, preserving
all loader/outer-renderer checks and unchanged existing tests. Instrument the
real zero-per-invocation hash boundary and bounded parser/writer work; report
any actual mismatch before changing limits, schemas or allocation.

Trusted focused unit/static checks may run with isolated environment. Full
suites, normal pre-push and remote actions remain root-coordinated. Freeze
source and evidence for independent implementation review before committing;
normal hooks, combined verification and exact-head repository gates still
precede merge. No source execution, native launch, installation, database,
key/provider configuration or operational fallback is allocated. Full R/C/G
acceptance and Docker stage readiness remain open.

## 15. Local implementation checkpoint — independent code review pending

The allocated five-file implementation is present on the prepared dependency
HEAD `cb28fc2`, without any additional dependency merge. Metadata extraction
shares the existing field validators and class-owned internal checkpoints with
the loader. The complete request/launch codec uses actual accepted-input and
qualified-key owners, immutable tagged views and the shared intended-inner
renderer. All four modes are implemented; there is no disabled placeholder or
fake installed context. No source, I/O, clock, hash or authority operation is
added to the pure public calls. These are implementation assertions under test,
not proof of operational safety or completed acceptance.

The existing loader, renderer and inventory test files are byte-unchanged.
Loader filesystem acquisition, stat comparisons, read/recheck/cleanup sequence
and operational refusals are unchanged. The separately reported ancestor-stamp
overreach in the existing loader is not repaired or silently bypassed here.
The actual metadata/key/packet helper boundaries are tested with hash, file,
clock, dynamic-import and subprocess operations poisoned after fixture setup.
Returned slot accounting is explicitly a tagged-output count, not total heap.

Observed local checks, all with explicit branch imports and database/AWS opt-ins
unset:

- Initial owned pure controls: 726 passed, zero skips/failures, Python 3.11.16.
- Expanded initial five-module focused run: 1,307 passed and one failed test
  setup. Poisoning `__import__` before subsequent pytest monkeypatch setup
  blocked pytest's own `inspect` import before the code under test ran. The
  original report is retained. Moving only that poison to the last setup step
  made the dedicated control pass; no product correction was made for it.
- Final owned pure controls: 760 passed, zero skips/failures, Python 3.12.14,
  7.827 seconds. The wire target remains Python 3.11; this is host codec coverage.
- Final five-module Python 3.11.16 focused run: 1,308 passed, zero skips/failures,
  13.400 seconds. This includes all 760 new controls plus the 548 unchanged
  loader/renderer/inventory controls. The actual `-m unit` selector was used.
- Scoped Ruff lint, Ruff format check and strict mypy passed on the three source
  files; both new test files passed lint/format. Tracked whitespace diff check
  passed. Local JUnit reports remain diagnostic artifacts, not a published
  immutable evidence archive.

The controls include complete nested required/extra/type checks, independent
lease equality/one-microsecond overflow, all-mode null groups, exact typed owner
reuse, raw-versus-domain delegation, poisoned views, byte/value/depth/escaped
size boundaries, cross-member links and exact independent inner argv/env
expectations. Private primitive-layer maximum-size controls are not valid
runtime requests or evidence of authorization. Constructed profiles, identities,
digests and source descriptors remain explicitly synthetic data.

Source/test bytes are frozen for root and independent peer review before any
commit. No full suite, pre-push, hooks, remote action, database operation, native
run, key installation or runtime activation was performed for this implementation
checkpoint. Remaining operator/provider, raw member hash, inner input, inventory,
image, bootstrap, kernel, DB-barrier/release and complete R/C/G gates are unchanged.

## 16. Root scoped implementation review — September 26 PKT

Root independently read the entire contract, both existing-source changes, the
new606-line packet module and both complete new test modules against actual
owners. Scoped APPROVE for source/test hashes frozen in the review, with contract
SHA256 `0fa3b1ccfa2ce16e9eddeb8041ba2ee84e43b918cdab3a34fe6badd1b895d725`.
This later note changes review state only, not those source or test bytes.

Root's separate tests passed all760 new controls plus16 independent cases on
both hosts: **776 passed**, zero skips/failures/errors,6.723s on Python3.11.16;
**776 passed**, zero skips/failures/errors,9.353s on Python3.12.14. Independent
cases check both intended-input mode boundaries, original-view preservation with
rejected mutated writers, and the explicit structure-only handling of unverified
request-domain hash declarations in all four modes. Local reports are
`/tmp/scanipy-packet-root-review-py311.xml` and
`/tmp/scanipy-packet-root-review-py312.xml`; they are not public immutable evidence.

Root confirmed exact input/queued-work admission, real nested owners, both lease
comparisons, complete renderer/writer parity, no hidden per-call hash/runtime
work and the retained loader anchor/separation/measurement/cleanup sequence.
The separately reviewed ancestor correction may now be integrated after this
checkpoint's normal commit. It is not part of these source hashes or results.
Combined verification, normal push and exact-head canonical SUCCESS/final
APPROVE remain required. No operational refusal or full R/C/G gate is changed.
