# Runtime artifact measurement — proposed shared contract

Owner: root, #400. Proposed new files: this document,
`tools/worker/runtime_artifacts.py`, `tests/unit/test_runtime_artifacts.py`.
The root engineering decision and independent design reviews authorize only
these three files for implementation. No runtime activation is approved.
This is the shared
measurement dependency for #397/#399; it must not create a second copy of their
key, transport, authority or worker codecs.

## Boundary and public API

The helper verifies actual installed file bytes against an independently
configured inventory and expected profile bindings. Matching two configured
digest strings is not measurement. The inventory can contain paths only after
its complete membership has matched the trusted expected root/runtime bindings;
it never expands its own filesystem authority.

Proposed API:

```text
require_installed_runtime_artifacts(
    installed: InstalledRuntimeArtifactInventory,
    *, profile_sha256: bytes, expected: RuntimeArtifactBindings,
    limits: RuntimeArtifactLimits | None = None,
) -> VerifiedRuntimeArtifacts
```

`installed` contains exact bounded inventory bytes, their independently
configured raw SHA256, and the three actual metadata origins supplied by the
trusted installation loader. It comes from the deployment/controller factory,
not an analysis packet, rule, source file or test callback. The helper is a real
file verifier, not an unforgeable authorization capability. Constructing any of
these records does not bypass verification or permit an operational launch.

`expected` holds the exact purpose (`python-syntax` or `accepted-verifier`),
implementation/version, executable and worker absolute paths/raw SHA256, ordered
root bindings, expected application/dependency/program digests, and fixed inner
protocol/resource-profile versions. Consumers map the generic program digest to
their actual syntax/verifier artifact field; do not invent an alias for an image
digest. All models are exact frozen records with boundary revalidation and private
primitive snapshots; no subclass/custom Mapping/PathLike/callback dispatch.

Missing installed inventory, mismatched expected/profile binding, malformed
metadata, unsafe paths, changed storage, limits or failed read yields a bounded
typed failure. Retain original private exception causes; no partial success or
configured-equality fallback. A diagnostic fixture may install its own actual
measured files/inventory, but cannot become operational trust.

Exact proposed public record fields (wire strings become the shown types):

```text
RuntimeMetadataPaths(inventory:PosixPath, profile:PosixPath, installation:PosixPath)
InstalledRuntimeArtifactInventory(
 inventory_bytes:bytes, inventory_sha256:bytes, metadata_paths:RuntimeMetadataPaths)
RuntimeRootBinding(role:str, ordinal:int, path:PosixPath)
RuntimeFileBinding(path:PosixPath, sha256:bytes)
RuntimeArtifactBindings(
 purpose:str, implementation:str, python_version:str,
 protocol_version:str, resource_profile:str,
 executable:RuntimeFileBinding, worker:RuntimeFileBinding,
 roots:tuple[RuntimeRootBinding,...],
 application_digest:bytes, dependency_digest:bytes, program_digest:bytes)
RuntimeArtifactLimits(
 max_roots:int=9, max_files:int=10000, max_entries:int=20000,
 max_depth:int=64, max_path_bytes:int=4096, max_file_bytes:int=134217728,
 max_total_bytes:int=536870912, max_inventory_bytes:int=8388608,
 max_json_depth:int=12, max_json_values:int=250000, wall_ms:int=30000)
VerifiedRuntimeArtifacts(
 inventory_bytes:bytes, inventory_sha256:bytes, inventory_digest:bytes,
 expected:RuntimeArtifactBindings, stdlib_digest:bytes,
 application_digest:bytes, dependency_digest:bytes, program_digest:bytes,
 elapsed_ms:int)
```

Only the closed role/purpose/implementation values below are accepted; version
and protocol/resource identifiers are nonempty strict text, at most 128 UTF-8
bytes. This helper matches those declared metadata values to trusted expectations;
it does not execute the interpreter to verify its version. The actual worker
runtime check remains mandatory. All digests are exactly 32-byte bytes internally.

## Exact version-1 inventory and digests

Canonical JSON is sorted-key compact UTF-8, strict Unicode scalar text and exact
primitive types, duplicate-key/nonfinite/unknown-field rejection at every depth,
and exact re-encoding equality. All fields below are required. SHA256 is lowercase
64-hex text on wire and exact 32-byte bytes internally; counts are nonnegative
int64 (never bool), further bounded by the hard limits below.

```text
{
 schema:"scanipy-runtime-artifact-inventory/1",
 profile_sha256:H, purpose:"python-syntax"|"accepted-verifier",
 implementation:"cpython", python_version:str,
 protocol_version:str, resource_profile:str,
 roots:[{
   role:"stdlib"|"application"|"dependency", ordinal:int, path:AbsolutePath,
   directories:[RelativePath,...],
   files:[{path:RelativePath,size:int,sha256:H},...]
 },...],
 runtime_bindings:[
   {role:"executable",path:AbsolutePath,size:int,sha256:H},
   {role:"worker",path:AbsolutePath,size:int,sha256:H}
 ],
 application_digest:H, dependency_digest:H, program_digest:H
}
```

Exactly one application root, 1–4 stdlib roots and 1–4 dependency roots. Roots
are ordered by role (`stdlib`, `application`, `dependency`) then dense zero-based
ordinal within role. Root path identities are unique; nested roots are permitted
for real layouts such as stdlib/lib-dynload, but each view is independently
enumerated/accounted/verified. Directories exclude the root, include empty
directories and are lexically sorted; files are path-sorted. No duplicate,
file/directory collision, skipped child or manifest-directed exclusion.

Paths are normalized absolute/relative POSIX Unicode-scalar text as appropriate;
no empty component, dot/dot-dot, backslash, NUL or control characters. Expected
root/runtime paths must match exactly before file access. Runtime bindings have
exactly the two rows in the shown order; their hashes/sizes are raw file facts,
not image/ELF-loader attestations.

Let `J` be that canonical JSON encoding and `D(s,b)=SHA256(ASCII(s)+LF+b)`.
For each role r, form exactly `{role:r,roots:[that role's full ordered root rows]}`
and calculate `R(r)=D("scanipy-runtime-root-group/1",J(that object))`.
Application/dependency fields equal R(application)/R(dependency). R(stdlib) is
also computed and used below; roots' actual bytes, not just supplied row hashes,
must first verify. Absolute installed paths are deliberately part of these
bindings; no environment-independent artifact identity is claimed.

Program digest is D("scanipy-runtime-program/1",J(exact object below)):

```text
{purpose, implementation, python_version, protocol_version, resource_profile,
 runtime_bindings, stdlib_digest:R(stdlib),
 application_digest:R(application), dependency_digest:R(dependency)}
```

This object excludes profile/inventory hashes and its own program digest, avoiding
hash cycles. A deployment first measures these groups/program, writes the profile
that binds them, then produces this inventory with the resulting profile SHA.
The trusted installation record pins both profile and inventory raw hashes;
neither document embeds the other's final digest recursively.

All three metadata files (inventory, profile and installation record) MUST live
outside every inventoried root and must differ from both runtime binding paths.
They also have distinct paths. Do not embed their resulting digests in an
inventoried code file. There are no exclusions to hide self-referential files.
The helper checks these exact supplied origin paths against every root/binding
before filesystem access. It does not load or authenticate the metadata files:
the trusted installation loader must supply the actual origins of the bytes it
loaded and independently pinned. A caller-constructed origins record is not
evidence of that loading. Tests must cover overlapping origins and a missing
loader; the operational consumer cannot accept packet-supplied origins.

Return actual canonical inventory bytes, raw SHA256 and
D("scanipy-runtime-artifact-inventory/1",inventory bytes), verified expected
bindings, computed three role digests/program digest and actual elapsed time.
Do not rewrite old inventories or reinterpret another schema version.

## Bounded filesystem measurement

Initial ceilings: 9 roots, 10,000 file observations, 20,000 directory/entry
observations, depth 64, path 4,096 UTF-8 bytes, 128 MiB per regular file, 512 MiB
aggregate read payload, 8 MiB inventory, JSON depth 12/250,000 values and 64 KiB
read chunks. Each root visit counts one entry; every enumerated child counts one
entry before classification. A directory child is not counted again on descent.
Each executable/worker payload observation adds one file and one entry, even when
that same file was already observed in a root. Each root's complete final
membership enumeration is charged again as entries, not as file reads. Nested
root views are charged independently. Final executable/worker stat checks add
entries but do not add payload/file-read counts. Ancestor path components used to reach
each root/runtime path also count as entries on every traversal. Payload bytes
are charged for every actual read, including the extra EOF probe, repeated
runtime/root reads and any retry; no retry resets counters. This version has no
read retry. Limits can only lower these maxima. No hidden-file skip or ignored
extra is permitted. These accounting choices can reject an otherwise valid
10,000-file tree under the independent 20,000-entry ceiling; maxima are not a
promise that all maximum dimensions fit simultaneously.

Start a 30,000 ms maximum cooperative total deadline after bounded pure argument
checks but before any filesystem validation/allocation. Charge decode, walk,
reads, hashing, revalidation and final result construction; check expiry before
returning success. Blocking kernel I/O and host failure still require #400's
outer supervision. A method returning after this deadline cannot claim success.

Walk every absolute component through held no-follow directory descriptors,
reject symlinks/special files, and require regular single-link files. Roots and
descendants allow owners only root or the current controller UID and disallow
group/other write. Ancestors follow the same policy except the literal `/tmp`
directory, owned by root with its sticky bit set, is allowed; the selected child must still
satisfy the strict root/descendant policy. This does not allow a user-owned
sticky directory or a group-writable development checkout. No `resolve()` or
symlink-following stat is an admission step. Reject observed
device/inode/type/mode/link/size/mtime/ctime/owner
changes. Read through EOF, match the complete expected inventory and recheck
directory observations/membership before success. Stream file content; never
buffer a 128 MiB object. Close every held descriptor on all paths.

The initial helper targets CPython 3.11 on Linux, matching the current two
worker profiles. Its exact `PosixPath` component snapshot is deliberately
version-specific; unsupported path implementations fail closed. Other Python
versions/platforms need a reviewed adapter and tests, not a permissive fallback.

Final deployment must use readonly immutable code/runtime mounts. Permission and
stat checks do not protect against hostile concurrent host root/same-UID writers.
The helper does not execute/import any measured file, follow loader-selected
libraries, run `ldd`, install packages, spawn a process or contact a network.
Shared libraries outside these roots, Python prior imports/mutable globals and
the Docker image/daemon/security-policy closure remain distinct evidence.

Read-only September 25 diagnostics found about 34.2 MB of stdlib, 212.0 MB of
the current development site-packages and a 14.4 MB cryptography extension.
Those du/stat observations inform conservative ceiling proposals only: they do
not verify membership, links, production packaging, latency or worker limits.

## Required falsifiers and integration

- [ ] Two independent inventory builders agree on small actual file fixtures;
  required empty directories, nested roots and repeated accounting are tested.
- [ ] Every field/order/type/digest mismatch, extra/missing file/directory,
  malformed encoding and unsupported schema fails without partial success.
- [ ] Symlink/hardlink/special paths, wrong owner/mode, create/remove/replace
  races, short/corrupt reads and read/stat/close failures preserve honest errors.
- [ ] N-1/N/N+1 caps, oversized/deep metadata and poisoned record/iterable/path
  objects fail before unbounded projection, callback or filesystem access.
- [ ] Missing/replaced/mutated inventory cannot authorize scanning additional
  paths; roots/bindings match the trusted expected profile before traversal.
- [ ] Timeout includes first filesystem validation and final digest/result work;
  interruption preserves its original object/cause and closes descriptors.
- [ ] Real #397/#399 consumer integration imports the shared implementation;
  no success from configured equality, fake verified records or a production
  fallback to diagnostic execution. Final readonly runtime/image checks remain
  part of the actual controller deployment, not this file helper alone.

Consumer adapters must add the actual installed inventory and expected bindings
from the trusted installation loader to their runtime configuration. Existing
executable/worker/version/private-root fields alone are insufficient. No copied
inventory model, packet-provided origin, configured-digest equality or
caller-constructed `VerifiedRuntimeArtifacts` may substitute for calling the
verifier. The diagnostic fixtures may supply their own explicit installation
origins, but their output stays diagnostic-only.

Independent contract/code review, normal hooks and required exact-head CI plus
canonical APPROVE remain mandatory. No full #400/R16 or submitted claim passes
merely because the inventory verifier's tests pass.

Design review: canonical-budget and schema/ingest peers reviewed the complete
initial contract and its metadata/ancestor/accounting correction on September
25. Both approved this narrow design, not code or production execution. Root
now owns implementation of exactly the three named files. The outer controller,
installation loader, consumer adapters and image preparation remain distinct
required work; their absence is not bypassed by this helper.

## Implementation checkpoint — September 25

The shared helper and 73 marked unit controls are implemented locally. Both
independent reviewers approved their scoped code checks after a reproduced
mutable-PosixPath check/use gap was repaired with a bounded private component
snapshot. Root ordinal fields are likewise read once into the private copy.
The tests include actual byte/membership verification, independent tiny fixture
builders, repeated byte/entry accounting, metadata separation, strict hostile
record checks, late mutation, short reads and read/stat/open/close failures,
first-access/final-result timeout checks, and original interruption retention.

Focused reviewed run: 73 passed, zero failures/errors/skips in 0.685 s;
`/tmp/scanipy-400-inventory-reviewed.xml`. Configured repository run:
1,322 passed / 51 existing skips, 1,373 total, zero failures/errors in 146.474 s;
`/tmp/scanipy-400-inventory-repository-full.xml`. These use the declared trusted
dev toolchain, explicit worktree PYTHONPATH and no external DB/AWS opt-ins.
Ruff/format, strict module typing and staged pre-commit checks passed. Initial
draft formatting and three redundant-cast typing failures were repaired before
the test run; they are not relabeled as successful attempts.

Normal commit/push gates, exact-head remote CI/canonical review and combined
dependency integration still follow. No installed production loader/profile,
Docker launcher, trusted operator keys, native scan, image build or stage
rehearsal was created by these tests. All runtime/controller/consumer TODOs
above remain required; these file fixtures are diagnostic evidence only.
