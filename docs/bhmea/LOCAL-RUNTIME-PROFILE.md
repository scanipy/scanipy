# Local runtime profile, trusted loading and gated launch — engineering contract

Status: **Root-reviewed engineering contract; runtime acceptance outstanding.**
Root reviewed the complete proposal and the corrected loader/factory boundary
on 2026-09-25 under #400. Canonical and corpus peers reviewed their syntax and
transport/lifecycle seams respectively. This is not an owner-approved
installation, operational identity, key, image, launch permission or completed
R16 claim. The initial slice was documentation-only; root now assigns the two
loader files in LRP-02 to the schema agent. Other implementation remains pending.

Read alongside [the controller architecture](LOCAL-RUNTIME-CONTROLLER.md) and
[the actual shared inventory contract](RUNTIME-ARTIFACT-INVENTORY.md). The
current Black Hat decision preserves the submitted scope and historical signed
records; this two-profile dependency does not replace native frontends, real
source acquisition, the solver/controller, API/queue or stage rehearsals.

The initial executable modes proposed here are `verifier-publication`,
`verifier-historical`, `verifier-execution` and `python-syntax`. They are all
pipe-only, no-egress modes. Unknown modes, absent installed adapters, unsupported
platforms and incomplete observations fail closed. The existing constant
operational refusals stay in place until actual integration is reviewed.

## 1. Identity domains and unchanged shared types

`H` means lowercase 64-hex SHA256 on wire and exact 32-byte `bytes` internally.
`J` is sorted-key, compact UTF-8 canonical JSON with exact scalar types,
Unicode scalars excluding NUL, signed-64-bit integers, no floats, duplicate
keys, nonfinite values, coercion or unknown fields. `D(s,b)` means
`SHA256(ASCII(s) + LF + b)`. UUIDs use canonical lowercase hyphenated text.
UTC instants have six fractional digits and a final `Z`. Counts are exact
nonnegative integers, never booleans. All keys below are required; nullable
fields must be explicitly null only in their specified states.

Paths are normalized absolute POSIX Unicode-scalar text, at most 4096 UTF-8
bytes, with no dot/dot-dot, empty interior component, backslash or C0/C1 control.
Relative source paths retain #397's stricter 1024-byte/32-component domain.
IDs are ASCII `[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}` unless otherwise specified.
`Text` means scalar text bounded to4096 UTF-8 bytes unless a stricter field
bound is given. `Mode` means exactly the four modes listed above.
New-schema `mode` permission fields mean `st_mode & 0o7777`; regular-file/socket
type is separately checked and retained in raw observations, not hidden in
those permission values.
No record's shape or digest grants its caller authority.

| Identity | Meaning; must not be substituted |
|---|---|
| `image_config_id` | Actual local Docker image ID, exact `sha256:` plus H; not an OCI index/manifest digest, tag, file inventory or complete execution environment |
| `oci_manifest_digest` | Exact observed/pinned OCI manifest digest, nullable when genuinely unavailable; never inferred from the local ID |
| `domain_profile_sha256` | Raw bytes of the domain's installed runtime profile |
| `inventory_sha256` | Raw bytes of the actual shared inventory document |
| `inventory_digest` | Shared inventory schema-domain digest returned by measurement |
| `program_digest` | Shared noncircular file/program digest; mapped to the verifier artifact identity or syntax runtime evidence |
| `controller_profile_sha256` | Raw bytes of the closed outer isolation/loader profile below |
| `installation_sha256` | Raw installation record, pinned outside that record and outside scan/DB data |
| `input_sha256` | Exact finite inner request bytes, including original domain framing |

Use the real `tools.worker.runtime_artifacts` classes and
`require_installed_runtime_artifacts`; do not clone `RuntimeMetadataPaths`,
`InstalledRuntimeArtifactInventory`, `RuntimeArtifactBindings`, root/file
bindings, limits or `VerifiedRuntimeArtifacts`. Likewise import the actual
bounded transport/outcomes, `VerifierRuntimeProfile`, `ExecutionBinding`,
`QualifiedRuleKey`/codec and `PythonSyntaxRuntime` from their owners.

The hash construction order is:

1. Measure runtime files and calculate shared root-group/program identities.
2. Write the domain profile containing the resulting identities.
3. Write its inventory with `profile_sha256 = domain_profile_sha256`.
4. Write the outer controller profile, binding domain/inventory raw hashes.
5. Write the installation record binding the outer profile and metadata origins.
6. Independently install/pin the installation record's raw hash and generation.

No file embeds its own hash or a downstream hash. None of these metadata files
may occur in an inventoried root or executable/worker binding. The inventory's
existing `profile_sha256` is **not** reinterpreted as the outer controller
profile hash. An image-native relocated runtime needs a separately reviewed
namespace design; renaming paths while keeping any of these digests is invalid.

## 2. Installed records and independent anchor

### 2.1 Anchor supplied only by the trusted deployment factory

Proposed low-level record `RuntimeInstallationAnchor` has exactly:

```text
deployment_id:UUID, installation_id:UUID, generation:positive int64,
purpose:"accepted-verifier"|"python-syntax",
installation_path:PosixPath, installation_sha256:bytes,
metadata_owner_uid:int, metadata_owner_gid:int,
controller_uid:int, controller_gid:int
```

UID/GID values are exact integers in 1..2147483647 for the controller and
0..2147483647 for metadata owners. Initial container UID/GID equals the
non-root controller UID/GID, with no supplementary groups, UID remapping,
rootless-daemon fallback or user-namespace translation. Other arrangements
require a reviewed ownership translation, not relaxed file checks.

The running deployment factory obtains this anchor from protected startup
configuration installed by the actual operator. No HTTP/queue body, bundle,
source, JSON path, ambient environment or database row selects an anchor.
An exact dataclass supplied by a caller is still merely data. There is no
automatic discovery of the highest installation generation or trust-on-first-use.
Missing pins are installation-unavailable, never inferred from readable files.

The independently installed current generation/hash pair prevents rollback of
the installation record. Updates replace that pair through explicit operator
admission, invalidate cached loads and block new launches until reconciled.
Registry trust/admission/restore epochs remain the separate accepted-input
protocol; a new runtime generation cannot reactivate revoked content. Recovery
of an older DB or journal cannot select an older runtime anchor autonomously.

### 2.2 Installation record

Closed `scanipy-local-runtime-installation/1`, maximum 65536 bytes:

```text
schema, deployment_id:UUID, installation_id:UUID, generation:positive int64,
purpose:"accepted-verifier"|"python-syntax",
controller_uid:int, controller_gid:int,
controller_profile:{path:AbsolutePath,sha256:H},
domain_profile:{path:AbsolutePath,sha256:H},
inventory:{path:AbsolutePath,sha256:H},
docker_cli:{path:AbsolutePath,sha256:H,version:ID},
docker_endpoint:{path:"/run/docker.sock",owner_uid:0,owner_gid:int,mode:432},
daemon:{id:ID,version:ID,api_version:"1.52",minimum_api_version:"1.44"},
host_work_root:AbsolutePath, evidence_root:AbsolutePath,
installed_at:UtcInstant
```

432 decimal is mode 0660. The socket's actual owner/group/mode/type must match;
the permitted group is an installed fact, not guessed as the caller's group.
The CLI path/hash and daemon ID/version are actual externally installed pins.
Version text is evidence to compare, not a command to execute. This draft does
not fill unknown pins with this workstation's illustrative observations.

All metadata origins and the installation path are pairwise distinct and
outside every runtime root/binding. The loader checks their disjointness from
the declared host work and evidence roots, and those roots' disjointness from
each other and runtime roots/bindings. Actual source/capture storage and the
derived control directory must also be disjoint; only the factory/controller
knows those paths and must check them before launch. They are not secretly
discovered or asserted by the low-level loader's smaller API.
The installation and outer profile are host-only. The original domain-profile
file is readable by the container's same numeric UID under its existing exact
mode/owner rules, mounted read-only at the **same** absolute path. Do not
world-share, copy/relabel its origin, or chmod user files to satisfy this.

### 2.3 Outer controller profile

Closed `scanipy-local-runtime-profile/1`, maximum 131072 bytes:

```text
schema, purpose:"accepted-verifier"|"python-syntax",
domain_profile_sha256:H, inventory_sha256:H, program_digest:H,
runtime:RuntimeArtifactBindingsWire,
platform:{os:"linux",architecture:"amd64",implementation:"cpython",
          python_version:NumericVersion,cgroup_version:2,cgroup_driver:"systemd"},
image:{config_id:ImageId,oci_manifest_digest:ImageId|null,
       os:"linux",architecture:"amd64",variant:null},
bootstrap:{path:AbsolutePath,sha256:H,protocol:"scanipy-runtime-bootstrap/1"},
container:{uid:int,gid:int,network:"none",pid:"private",ipc:"private",
           cgroupns:"private",userns:"host",readonly_root:true,
           privileged:false,capabilities:[],no_new_privileges:true,
           seccomp:"docker-builtin-default/29.1.3",
           apparmor:"docker-default",restart:"no",auto_remove:false,
           init:false,tty:false,log_driver:"none",ports:[],devices:[]},
scratch:{work_root:"/run/scanipy-work",bytes:8388608,inodes:1024,
         mode:448,nosuid:true,nodev:true,noexec:true},
limits:{memory_bytes:int,memory_swap_bytes:int,pids:16,
        cpu_quota_us:100000,cpu_period_us:100000,
        shm_bytes:65536,max_mounts:64,max_bind_mounts:16,
        max_additional_tmpfs_bytes:67174400,max_additional_tmpfs_inodes:32768,
        inner_wall_ms:int,inner_cleanup_ms:500,
        launch_wall_ms:30000,pre_release_ms:10000,cleanup_ms:5000,
        max_cli_calls:16,max_kernel_observations:16},
io:{stdin_bytes:int,stdout_bytes:int,stderr_bytes:int,combined_bytes:int},
config_policy:"scanipy-docker29-pipe-config/1"
```

`NumericVersion` is exactly `3.11.P`, with decimal P in 0..2147483647, no
leading zero except zero itself. Container UID/GID matches the anchor. Values
shown literally are exact, not defaults silently omitted by a renderer.
`RuntimeArtifactBindingsWire` has exactly the actual shared record's fields:
`purpose, implementation, python_version, protocol_version, resource_profile,
executable, worker, roots, application_digest, dependency_digest, program_digest`.
File bindings are `{path:AbsolutePath,sha256:H}`; root bindings are
`{role,ordinal,path}` with the shared contract's exact roles/order/counts.
Construct the actual shared types from these checked primitives and let the
real measurement helper revalidate them. Do not define a lookalike Python
record or duplicate its filesystem verifier. All repeated purpose/program/
version fields must agree. The owning domain adapter separately decodes the
original domain bytes with its actual codec and checks every mapping in §3
before launch; the low-level loader does not copy the verifier's schema.
For verifier, memory and memory-swap are both 134217728, inner wall is 3000,
stdin 2621440, stdout/stderr 16384 each and combined 32768. For syntax, memory
and memory-swap are both 268435456, inner wall is 5000, stdin 263244, stdout
8388608, stderr 65536 and combined 8454144. These cgroup ceilings are proposed
outer bounds in addition to, not replacements for, existing worker rlimits.
Any measured incompatibility is a failed profile requiring review; do not
silently increase 128 MiB/3 seconds or 256 MiB/5 seconds to make tests pass.

The 8 MiB work tmpfs and additional kernel/runtime tmpfs bytes consume that
same memory allowance. `max_additional_tmpfs_*` covers all writable engine
mounts such as `/dev` and `/dev/shm`, not an allowance for arbitrary new mounts.
Every such mount must have an observed finite byte/inode ceiling within the
aggregate; an unmeasurable/unbounded default blocks release. Exact pinned-engine
mount acceptance needs real controlled tests before implementation acceptance;
this draft does not assert that current Docker defaults meet these bounds.
No quota-less writable host bind is allowed. Root/proc/sys/device pseudo-files
are subject to the closed engine mount/security policy, not treated as ordinary
scratch files. No privileged/mount-capability workaround is permitted.

Bootstrap is a trusted regular script already included in the measured
application root; require its exact inventory member/raw SHA and <=1 MiB size.
Its bytes thus participate in the program digest. The host CLI/daemon and
image-native ELF libraries remain distinct trust/evidence, not falsely measured
by the Python inventory. Kernel seccomp mode and AppArmor label observations do
not prove the full loaded policy bytes; this initial profile explicitly trusts
the pinned daemon's reviewed builtin policy behavior.

## 3. Domain profile mapping without changing its meaning

### 3.1 Verifier

Read and decode the actual `scanipy-accepted-verifier-runtime/1` file with its
own codec into the real `VerifierRuntimeDocument`/`VerifierRuntimeProfile`.
All original fields, flags, environment, 65536-byte cap, complete import-root
order and rlimits remain unchanged. Map its executable/worker and ordered
stdlib/application/dependency roots into actual `RuntimeArtifactBindings`:
purpose `accepted-verifier`, protocol `scanipy-accepted-verifier-request/1`,
resource profile `scanipy-verifier-limits/1`; application/dependency/verifier
artifact fields map to the shared application/dependency/program digests.

The original `work_root` equals `/run/scanipy-work` in the **container**
namespace. The loader must not create, inspect for existence, or reuse that
absolute path on the host. Runtime file bindings remain host/container-identical;
the work path is not a file-inventory binding. The real worker sees a fresh cwd
under it and checks its existing no-follow private-mode rules there.

The operational adapter must not call `_run_diagnostic_verifier`, which is a
host-local diagnostic harness. It uses the actual controller result and the
existing exact request/result codecs, then rechecks live authority. No public
diagnostic switch or implicit in-process fallback is added.

### 3.2 Syntax

New installed file `scanipy-python-syntax-runtime/1`, maximum 65536 bytes,
has exactly:

```text
schema,implementation:"cpython",python_version:NumericVersion,
python_executable:AbsolutePath,python_executable_sha256:H,
worker_script:AbsolutePath,worker_script_sha256:H,
application_root:AbsolutePath,application_artifact_digest:H,
stdlib_roots:AbsolutePath[],dependency_roots:AbsolutePath[],
dependency_artifact_digest:H,syntax_artifact_digest:H,
work_root:"/run/scanipy-work",resource_profile:"scanipy-python-syntax-limits/1"
```

Roots obey the actual inventory's exact role/order/count rules. The shared
protocol version is `scanipy-python-syntax-request/1`, purpose `python-syntax`;
`syntax_artifact_digest` is the program digest. #397's six-field
`PythonSyntaxRuntime` is unchanged: after allocating an invocation, the owning
factory constructs it from the actual installed executable/hash/worker/hash,
exact version tuple and that invocation's **container** private root. It is
a pure expectation passed to the existing response decoder, not a launch token.
Keep raw domain/inventory bytes and measurement/controller evidence separately;
do not add a fake `verified=true` field to this class.

The syntax request remains its actual byte-framed one-file request, with a
262144-byte source ceiling and total 263244-byte ceiling. No source filesystem
mount is needed. Source bytes come from the actual immutable capture/lease
adapter, not a filepath chosen by the worker or an asserted source commit.
The producer still enforces cumulative 8 MiB syntax stdout and the other #397
whole-run budgets across children; one complete child cannot reset them.
The current pure `SourceSyntaxDocument` retains `process=None`. Preserve actual
controller/measurement evidence separately; never inject the Docker-client
`ProcessOutcome` as if it were an observed inner Python process.

## 4. Bounded trusted-loader API and file protocol

Proposed module: `tools.worker.runtime_profiles`. No services/analysis imports
or subprocesses in this loader; owning adapters decode their actual domain
models. Exact proposed API:

```text
load_installed_runtime(anchor:RuntimeInstallationAnchor)
    -> LoadedRuntimeInstallation

LoadedRuntimeInstallation(
 anchor:RuntimeInstallationAnchor,
 installation_bytes:bytes, controller_profile_bytes:bytes,
 domain_profile_bytes:bytes,
 metadata_observations:tuple[RuntimeMetadataObservation,...],
 installed_inventory:InstalledRuntimeArtifactInventory,
 bindings:RuntimeArtifactBindings, measurement:VerifiedRuntimeArtifacts,
 loaded_elapsed_ms:int)

RuntimeMetadataObservation(
 role:str,path:PosixPath,sha256:bytes,size:int,
 device:int,inode:int,uid:int,gid:int,mode:int,nlink:int,
 mtime_ns:int,ctime_ns:int)

RuntimeProfileError(ValueError): reason:str
```

Loader failures use this typed error with a fixed reason from
`installation-unavailable`, `metadata-invalid`, `artifact-mismatch`,
`unsafe-path`, `limit`, `deadline`, `cleanup-incomplete`, `unsupported`.
Retain original filesystem/shared-measurement exceptions as private causes;
never include supplied paths/content or arbitrary exception messages in the
public reason. Interruption remains the original BaseException, with cleanup
failures attached without replacing its original cause or retrying an uncertain
numeric descriptor. Successful data validation is not an authority result.

Metadata roles are exactly `installation`, `controller-profile`,
`domain-profile`, `inventory`, in that order. `RuntimeMetadataPaths.profile`
is the truthful domain-profile origin, not the outer profile path. The loader
also applies the same disjointness checks to the outer profile and all anchor
origins; the existing three-field shared model is not copied or silently
extended. Returned records are evidence/data; a caller-made instance bypasses
neither loading nor the controller's checks. This callback-free loader validates
filesystem bytes and observations relative to the supplied, privately
snapshotted anchor pins only. It has no independent startup-configuration reader
and cannot authenticate the anchor's provenance, factory ownership, publication
or currentness. A successfully loaded result does not establish domain-profile
semantic validity, mode authority or permission to launch.

The loader snapshots exact primitive UUID/path/digest/int fields before
formatting, hashing or filesystem access, using inspected CPython 3.11 storage
and bounded built-in copies; rejects subclasses, custom containers, missing
slots, poisoned caches, arbitrary iterables and unknown layouts without calling
their methods. No `resolve()`, environment lookup, glob, directory discovery or
automatic fallback. Use a shared depth/value/escaped-byte budget before JSON
serialization as well as decoding; fail before large intermediate allocations.

Load protocol:

1. Validate and privately snapshot the supplied anchor's exact primitive fields;
   start a 35000 ms cooperative deadline before first filesystem access. This
   validates supplied data, not its installed-factory provenance or currentness.
   Require actual non-root `os.geteuid()`/`os.getegid()` to equal the snapshot's
   controller UID/GID before metadata/runtime reads; otherwise `unsupported`.
   This aligns the shared measurement's actual owner checks, not anchor authority.
   No cache reuse solely because path/mtime/hash strings match.
2. Walk absolute components with held `O_NOFOLLOW|O_DIRECTORY|O_CLOEXEC`
   descriptors. Ancestors are root or controller owned and not group/other
   writable, except literal root-owned sticky `/tmp`; each direct metadata parent
   is exactly mode 0700 with the pinned metadata-owner UID/GID. Metadata files
   are regular, one link, mode 0600 or 0400,
   exact pinned owner UID/GID, never symlinks or device/FIFO/socket files.
   Open candidate files with O_NOFOLLOW, O_CLOEXEC and O_NONBLOCK, then inspect
   the held descriptor before reading; an unexpected FIFO must not block open.
3. Read the installation through EOF, at most 65536 bytes, matching the
   supplied pinned raw digest and exact anchor identities before trusting its
   other paths. Read the other three files only at those exact declared origins,
   enforce all loader-visible disjointness constraints in §2.2, and compare raw hashes and the closed
   installation/outer schemas. Domain bytes remain exact bounded opaque bytes
   at this low-level boundary; their owning adapter performs semantic decoding.
4. Construct `RuntimeArtifactBindings` from the checked outer profile's exact
   shared-field projection; require all duplicated outer pins agree before reads.
   Call the **actual** shared verifier with `profile_sha256` equal to the raw
   domain-profile digest, truthful origins, and its existing hard ceilings.
   Its wall budget is at most 30000 ms and also at most the remaining loader
   deadline. There is no configured-digest-only success path.
5. Recheck all held metadata observations before return. Require unchanged
   dev/inode/type/size/mode/owner/nlink/mtime/ctime; a concurrent metadata
   replacement fails. This step does not reread an external anchor or establish
   admission currentness.
   Close each acquired descriptor once on every path. Track a child before
   releasing its parent; never retry an uncertain close-failed numeric FD.
   Preserve primary exceptions/interruption and later cleanup causes.

Loader ceilings compose: four metadata files, 8 MiB inventory, 128 KiB outer
profile, 64 KiB installation and 64 KiB domain profile; aggregate metadata
8650752 bytes. Non-inventory JSON depth16/20000 values/4096-byte strings; the
actual inventory retains depth12/250000 values and its own larger byte cap.
Charge reads, EOF probes, parsing, hashing, measurement and final rechecks to
the total deadline. At most 512 metadata/ancestor observations and 64 held
descriptors, plus the shared measurement's own accounted limits. Read chunks
are at most64 KiB. Missing/changed/incomplete evidence never returns a partial
loaded result. Blocking kernel I/O still requires outer host supervision.

Readonly immutable deployment mounts and the nonconcurrent trusted admin
boundary remain mandatory. These checks cannot prevent a privileged writer
from replacing code after measurement. The installed factory, outside this
low-level API, obtains the actual independent protected startup anchor before
calling the loader. It independently rereads that startup anchor immediately
after loading and again before create, release and result admission, comparing
the complete validated anchor with the snapshot used for the load. Any change,
including generation or installation hash, aborts that attempt; no in-place
restamping or caller-supplied replacement is permitted. Missing real factory
composition or a failed reread blocks operational launch/admission, not a
low-level data-only load. The factory also requires the owning domain adapter
to decode and validate the exact retained domain-profile bytes and their
runtime-binding mapping before launch; a loader outcome cannot satisfy that
gate. A retired installation may support explicit historical audit through
the separately authorized mode, but never silently reauthorizes execution.

## 5. Host CLI context and container namespace

One exclusive host attempt directory under `host_work_root` contains exactly
`cli-home/`, `cli-tmp/`, `cli-bin/`, `docker-config/`, `control/` and bounded
retained call data. Directories are 0700; `cli-bin` stays empty. `docker-config`
contains only `config.json` with the exact two bytes `{}` (0600), and is
rechecked before each CLI invocation. No user `~/.docker`, auth config, context,
certificate, credential helper, alias, plugin or completion state is consulted.

Before the first CLI call, the controller measures the actual CLI file through
held no-follow descriptors: regular, single link, trusted root/controller owner,
no group/other write, at most128 MiB, 64 KiB chunks through EOF, exact pinned raw
SHA and unchanged stat identity. This separate file observation is not the
domain runtime inventory or the CLI's native-loader closure. Its walk has at
most64 ancestor observations and32 held descriptors, charged to the outer
deadline. Recheck its identity before each call. Verify the exact local socket
type/owner/mode/dev/inode before/after calls; any daemon/socket replacement
invalidates the attempt. Neither check invokes the CLI or a discovery command.

Every CLI call uses the independently pinned absolute executable, prefix
`(docker_path,"--host","unix:///run/docker.sock","--config",private_config)`
and one of the closed builtin command variants below. Exact environment:

```text
LANG=C.UTF-8; LC_ALL=C.UTF-8; TZ=UTC;
HOME=<host attempt>/cli-home; TMPDIR=<host attempt>/cli-tmp;
PATH=<host attempt>/cli-bin;
DOCKER_API_VERSION=1.52; DOCKER_CLI_HOOKS=false;
DOCKER_CLI_HINTS=false; OTEL_SDK_DISABLED=true
```

These ten entries are constructed by the controller, not merged with ambient
values. Unknown requested environment/configuration is rejected, not passed
through. No `DOCKER_CONTEXT`, `DOCKER_HOST`, TLS/SSH/proxy/credential/debug or
other OTEL values survive. Commands, paths and whole finite stdin are frozen
before the actual shared transport; no shell, help/completion, plugin, build,
pull, run, exec, attach-to-existing, logs or arbitrary `--format` templates.

The private empty PATH matters: pinned CLI config loading still attempts
credential-helper discovery even with `{}`. Fixed builtins avoid the plugin
fallback/help/completion paths; explicit hooks=false and non-TTY operation
remove the hook path. These are source-backed design expectations requiring
real controlled installed-binary tests, not attestation of a matching version
string. [Pinned config loader](https://github.com/docker/cli/blob/v29.1.3/cli/config/config.go),
[credential discovery](https://github.com/docker/cli/blob/v29.1.3/cli/config/credentials/default_store.go),
[builtin/plugin dispatch](https://github.com/docker/cli/blob/v29.1.3/cmd/docker/docker.go),
[endpoint/context selection](https://github.com/docker/cli/blob/v29.1.3/cli/command/cli.go).

`host_work_root` and `evidence_root` are never mounted writable into a worker.
Only the per-attempt control **directory** and the exact domain-profile file
are mounted readonly. The domain-profile file remains identity-mapped. The
control directory is not part of the measured runtime inventory and maps to
the fixed container destination `/run/scanipy-control`, as explicitly specified
in the [Docker policy contract](LOCAL-RUNTIME-DOCKER-POLICY.md); launch/release
paths and their overlap checks use that destination. Runtime roots/files
are also identity-mapped readonly; derive the minimal exact binding cover from
the trusted roots/executable/worker, preserving nested-view measurement without
inventing duplicate writable submounts. Reject overlap with control/metadata,
scratch or source roots. At most16 binds, all private propagation, no recursive
writable submount, no image-declared anonymous volume.

Scratch exists only inside the container. Bootstrap creates
`/run/scanipy-work/<attempt UUID>/` and its `pycache`, `home`, `tmp` children as
empty 0700 directories, owned by the configured non-root UID. These paths never
designate host working directories. The bootstrap's own fresh cache is a
different empty child; the inner worker gets its own initially empty `pycache`.
Neither cache may shadow or overlap an import/profile/source path. Do not use
`-B` alone as protection against stale bytecode loading.

Image creation is out of scope. Admission rejects a missing local image,
wrong full config ID/platform, inherited env outside the exact renderer,
healthcheck, on-build hook, volume, device, port, unexpected labels/entrypoint,
or other unaccounted execution behavior. Use explicit command/user/workdir/
env overrides and compare **effective** inspect results; merely recording what
was requested is insufficient. No launch-time pull or tag resolution.

## 6. Mode-specific controller request and prerequisite snapshot

Closed `scanipy-local-runtime-request/1`, maximum65536 bytes, is internal
controller metadata, not a second accepted-input or source wire protocol:

```text
schema,operation_id:UUID,
mode:"verifier-publication"|"verifier-historical"|"verifier-execution"|"python-syntax",
deployment_id:UUID,installation_id:UUID,installation_generation:positive int64,
controller_profile_sha256:H,domain_profile_sha256:H,
input:{size:int,sha256:H,protocol:ID},
binding:{bundle:BundleExpectation,execution:ExecutionBinding|null,
         qualified_rule:QualifiedRuleKey|null,source:SourceBinding|null},
prerequisite:LaunchPrerequisite
```

Existing nested bundle/execution/key types use their **actual owning codecs**;
no lookalike fields or copied validators. `SourceBinding` is exactly
`{capture_id:UUID,source_tree_algorithm:ID,source_tree_digest:H,
inventory_sha256:H,path:RelativePath,size:int,sha256:H}`. It is produced from
actual immutable capture bytes/lease evidence. Its digest algorithm must match
the source backend; algorithms with different framing are never equated.
This association does not assert that a supplied Git commit proves SCM custody.

`LaunchPrerequisite` is a closed observed adapter result, not a grant:

```text
schema:"scanipy-local-launch-prerequisite/1",
reader_id:ID,observation_id:UUID,observed_at:UtcInstant,valid_until:UtcInstant,
principal_id:ID,org_id:UUID,
action:"publish-builtin-preflight"|"audit-historical"|"verify-execution"|"parse-python",
authentication_evidence_sha256:H,scope_evidence_sha256:H,
admission:AdmissionExpectation|null,
execution_authorization_digest:H|null,
capture_lease_evidence_sha256:H|null,
content_verification_evidence_sha256:H|null
```

The factory selects a fixed real authentication/repository/admission/capture
adapter, never one named in a request or arbitrary callback. It persists the
bounded original evidence to which the hashes refer. Missing adapter/evidence
is unavailable, not a generated UUID/hash or `accepted=true`. `reader_id`
identifies the installed producer but cannot authenticate itself. Fresh reads
occur before create, immediately before release, and before result admission;
if any binding changes, abort that attempt without overwriting earlier reads.
Validity is at most60 seconds and never extends the authenticated session,
current policy/checkpoint, work or capture lease. Use actual trusted wall time
for those expiries and independent monotonic deadlines for process timeouts.
Clock rollback/uncertainty blocks new release rather than prolonging authority.

Mode invariants:

| Mode | Required bindings/prerequisites | Explicitly forbidden inference |
|---|---|---|
| verifier-publication | Customer bundle; authenticated scoped accepting operator; current admission; exact publication-preflight input | No existing receipt, execution binding, selected rule, capture lease or prior verifier-success requirement |
| verifier-historical | Customer bundle; authenticated scoped auditor; exact retained historical receipt/input | Admission/execution/source/selected-rule and all three execution/content evidence digests null; old approval revocation does not prohibit historical inspection |
| verifier-execution | Bundle + execution + selected rule; fresh admission, execution authorization and capture-lease evidence | No prior result from this same verification call; source null and content-verification evidence null |
| python-syntax | Execution + selected rule + actual source; fresh admission/authorization/capture lease and real current content-verification evidence | No caller-made verified record, planted source label, source path opening or unattempted-rule completion |

Actions map one-to-one in table order to `publish-builtin-preflight`,
`audit-historical`, `verify-execution`, `parse-python`. All org IDs must match.
Publication has null execution/selected-rule/source bindings and all three
execution/capture/content evidence digests null. Historical has the same null
bindings plus null admission. Execution has non-null execution/capture digests,
null source and null content-verification digest. Syntax has all three digests
and source non-null. There are no unspecified optional authority fields.

Syntax's bundle must exactly equal the qualified rule's namespace; the small
namespace record is not substituted for complete accepted-content membership.
Initial operational scope is customer-only with non-null matching orgs, as
#399 specifies. Global/customer composition remains a separate extension.
Verifier input header mode, operation, namespace, profile artifact identity and
all expected live bindings must agree with this request using its actual codec.
Syntax bytes must agree with the exact source path/content/hash. Reject a
request assembled by an untrusted caller even if these equalities happen to hold.

Typed operational handoff is proposed in `services.scan.runtime_factory`, not
in the low-level shared loader:

```text
InstalledRuntimeFactory.verify(request:VerifierRequest)
    -> existing VerificationChecks
InstalledRuntimeFactory.parse(source:FrozenSourceFile, *, binding:ExecutionBinding,
                              rule:QualifiedRuleKey, limits:ScalarLimits)
    -> existing SourceSyntaxDocument
```

The factory independently obtains and compares the actual installed trust,
bundle, admission and ledger expectation objects for the requested mode; the
same objects embedded in `VerifierRequest` cannot authenticate themselves.
The factory is installed application composition,
not a public constructor/service locator and not a packet field. It loads,
measures, obtains genuine fresh prerequisites, allocates the controller attempt,
validates the exact owning result codec and rechecks authority. Exact factory
file allocation and the missing real auth/ledger adapters require root review
before implementation. Do not alter the pure carrier into an authority token.

## 7. Launch specification and single-use release

The controller journals an attempt UUID and unique name
`scanipy-runtime-<32 lowercase UUID hex>` before create. No reuse, automatic
relaunch or caller-provided container ID. It creates `control/launch.json`
with `O_EXCL`, exact0600 bytes, fsync/readback, before container creation.
Container hostname is that same fixed attempt name, not a supplied repository
name. No linked containers are permitted.
Closed `scanipy-runtime-bootstrap-launch/1` (maximum65536 bytes):

```text
schema,attempt_id:UUID,operation_id:UUID,request_digest:H,
deployment_id:UUID,installation_id:UUID,installation_generation:positive int64,
mode:Mode,image_config_id:ImageId,
controller_profile_sha256:H,domain_profile_sha256:H,
inventory_sha256:H,inventory_digest:H,program_digest:H,
input:{size:int,sha256:H,protocol:ID},
inner:{argv:Text[],environment:[{name:Text,value:Text},...],cwd:AbsolutePath},
container_uid:int,container_gid:int,
release_filename:"release.json",bootstrap_wait_ms:10000,
inner_wall_ms:int,inner_cleanup_ms:500
```

`request_digest=D(request schema,canonical request bytes)`. Bootstrap receives
only a fixed argv containing the actual launch file path and expected raw
launch SHA from the trusted controller; this expectation is not read from stdin.
Its script path/hash and interpreter are installed/measured. Maximum64 argv
members, each8192 UTF-8 bytes, whole argv65536; environment has at most16 exact
rows, names<=128 bytes, values<=8192, combined<=16384, sorted unique names.
These generic caps do not permit arbitrary values: exact mode grammar below
must match the domain profile and derived invocation paths.

Exact bootstrap argv is `(executable,"-I","-S","-B","-X","utf8","-X",
"pycache_prefix="+bootstrap_cache,bootstrap_script,"--launch",launch_path,
"--launch-sha256",launch_raw_sha256)`. Its environment is exactly
LANG/LC_ALL=`C.UTF-8`, TZ=`UTC`, PATH=`""` and HOSTNAME equal to the fixed
attempt hostname. `bootstrap_cache` is the fresh work tmpfs's
`bootstrap-<attempt UUID>/pycache`, disjoint from the inner private root. The
empty tmpfs is created by the runtime, not a host directory. Bootstrap validates
its actual isolated/no-site/bytecode/cache flags and trusted runtime layout,
creates/checks its private directories, then uses only installed stdlib code
before reading launch/release metadata. It does not add cwd, user site, PTH,
source, arbitrary ZIP/plugin roots or ambient import paths. Any initial
image-provided CPython/native-loader dependencies remain trusted image closure,
not retroactively claimed as measured files outside the declared inventory.
Runtime-layout/poisoned-bytecode controls must prove this exact path before
operational admission. The inner worker's own limits/import checks still run.

The two extra bootstrap variables are deliberate engine overrides, not ambient
inheritance. Pinned Moby adds PATH/HOSTNAME on Linux before applying Config.Env
(and TERM for TTY). The renderer therefore passes exact empty PATH and exact
HOSTNAME explicitly, verifies Config.Env and the observed bootstrap environment,
rejects extra image defaults/links/TTY, then the bootstrap's `execve` strips both
for the unchanged inner domain mapping. Adding three variables to Docker's
environment is not evidence that the child has only those three.
[Pinned daemon environment construction](https://github.com/moby/moby/blob/docker-v29.1.3/daemon/container/container.go#L804-L835).

Verifier inner argv/env is the actual #399 tuple, including `-I -S -B -X utf8`,
the fresh prefix, fixed worker, original domain `--profile` path/hash, and only
LANG/LC_ALL/TZ. Syntax inner argv is exactly executable, `-I`, `-S`, `-B`,
`-X`, `pycache_prefix=<private>/pycache`, worker; environment exactly LANG,
LC_ALL, HOME=`<private>/home`, TMPDIR=`<private>/tmp`. No source-directed flags,
import roots, loader variables or mutable environment merging. Bootstrap
uses a separate safe fixed environment/import/cache setup and then `execve`
with the exact inner mapping, not its inherited environment.

Bootstrap validates launch metadata and waits without reading untrusted stdin,
producing no stdout. The entire finite domain packet is supplied once through
the actual synchronous shared transport's stdin. It may block in pipes before
release; this is intentional. No second stdin frame, interactive transport API,
callback or stdout-prefix handshake is introduced. Parent inspection runs in
one bounded trusted orchestration thread while that transport owns attach I/O.

After actual created/running configuration and kernel checks plus fresh
prerequisites, parent writes a private temp release, fsyncs it, publishes
`control/release.json` atomically with exclusive no-replace semantics, fsyncs
the directory and verifies bytes. The mounted directory, not an individually
bound replaceable file, makes this publication visible. Any existing final file
is replay/collision failure. Closed release (maximum16384 bytes):

```text
schema:"scanipy-runtime-bootstrap-release/1",
attempt_id:UUID,operation_id:UUID,launch_sha256:H,request_digest:H,
container_id:H,daemon_id:ID,mode:Mode,
controller_profile_sha256:H,domain_profile_sha256:H,
inventory_sha256:H,inventory_digest:H,program_digest:H,
input_sha256:H,inner_invocation_digest:H,
prerequisite_digest:H,admission_epoch:UUID|null,fencing_token:positive int64|null,
work_revision:positive int64|null,capture_lease_id:UUID|null,
released_at:UtcInstant,expires_at:UtcInstant,
inner_wall_ms:int,inner_cleanup_ms:500
```

`inner_invocation_digest=D("scanipy-runtime-inner-invocation/1",J(inner))`;
prerequisite digest uses that schema domain. Execution fields are present only
for execution/syntax and equal the actual fresh execution binding. Publication
has current admission epoch but null execution fields; historical has them all
null. Expiry is the minimum remaining applicable prerequisite/session/policy/
checkpoint/work/capture expiry and the outer attempt wall bound. Bootstrap
checks all launch-comparable fields, exact owner/mode/EOF and expiry using its
trusted clock; it does not claim to independently authenticate Docker's own
container ID. Parent establishes that ID and corroborates the actual object.

After a valid single release bootstrap starts only the exact inner program.
It cannot accept a replacement/second release or retry after exec failure.
The parent durably records release intent, actual publication and any ambiguous
acknowledgement. Ambiguous start/release is **possibly executed**, requiring
stop/reconciliation, never a second release or successful unstarted status.
No raw approval/source/credentials are stored in launch/release JSON.

## 8. Finite execution budgets and Docker observations

Load/measurement has its separate35-second bound. A launched attempt has a
30000 ms cooperative outer bound: at most10000 ms before release, the unchanged
inner3000/5000 ms including its500 ms cleanup reservation, at most5000 ms for
container/client cleanup, and the remaining allowance for retained evidence
and checks. Budgets are absolute cumulative monotonic deadlines, not16 fresh
30-second command budgets. Reserve cleanup before starting work. At inner
deadline minus500 ms, incomplete work begins termination; failure to finish
domain I/O by the inner deadline is failure even if outer cleanup succeeds
later. Docker startup does not consume or silently enlarge the inner budget.

The attach transport's fixed wall bound covers pre-release plus inner execution
and bounded client cleanup within the outer deadline. The parent separately
enforces the inner release-relative deadline against the owned container;
`ProcessOutcome.elapsed_ms` for the Docker client is not invented as inner
worker elapsed time. A blocked transport thread, unresolved spawn or stuck
kernel/daemon call is incomplete, never a successful return. Outer host service
supervision and durable restart reconciliation remain necessary.

At most16 CLI invocations, of which one is create and one start. Other closed
variants are exact image inspect, daemon version/info, exact-ID container
inspect, exact-ID kill, wait and remove; exact-name inspect is allowed only for
recovering an ambiguous create against its pre-journaled name and complete
intent. No wildcard/list/prune/group cleanup. Runtime remove is non-forced and
only after confirmed stopped/empty state; failures preserve owned-object
evidence rather than expanding deletion targets.

Each non-attached call has at most2000 ms including250 ms client cleanup,
stdout262144 bytes/stderr16384/combined278528, stdin absent. Cumulative
non-attached raw output is at most4 MiB; kernel raw observations at most1 MiB,
each65536 bytes, at most16 samples. Metadata/journal summaries at most512 KiB
per attempt. Domain input/output keeps its smaller mode cap. Reserve at most
32 MiB total retained attempt evidence before starting; this includes the
original installed metadata/inventory bytes, not just domain output. Never fetch unbounded
`docker logs` or silently discard a successful raw result to fit. At most one
active controller attempt initially; reject/queue additional work without
spawning. Stage-resource admission must observe at least4 GiB available host
RAM without terminating unrelated workloads; this is not a latency promise.

`scanipy-docker29-pipe-config/1` checks the entire effective config against the
installed renderer, including image, user/groups, entrypoint/command/workdir,
complete environment, stdin/non-TTY, image defaults, mounts/propagation,
network/PID/IPC/cgroup/user namespaces, capabilities, devices/ports, readonly
root, NNP, restart/autoremove/init, logging, healthcheck, CPU/memory/swap/PIDs,
tmpfs/shm limits and security options. Unexpected extra controls/behaviors or
unknown security-relevant fields fail, not ignored best-effort projection.
Full raw inspect bytes are retained. Exact pinned API field-to-policy mapping
and flag rendering require a separately reviewed controller implementation
contract/fixtures before launch code is enabled; this proposal does not certify
behavior from flag names alone.

Pre-release kernel observations bind the actual host PID **and start ticks**,
host boot ID, held PID/proc identity and cgroup device/inode/path before/after
observation. Require memory.max equals profile, memory.swap.max=0, pids.max=16,
cpu.max=`100000 100000`, actual private network/PID/cgroup namespaces, NNP=1,
capability sets zero, seccomp mode2 and docker-default AppArmor enforcement.
Verify actual mounts/readonly flags and finite writable tmpfs byte/inode limits,
not just HostConfig promises. Parent and worker namespaces must differ where
private was required. Reused numeric PID, mismatched start, changed daemon/socket
identity, mixed samples or unreadable evidence denies release. No shell, `nsenter`
or source command is used to obtain these checks; bounded trusted kernel readers
own them. Kernel policy label/mode is not the full policy's byte attestation.

## 9. Exact append-only launch evidence

Durable evidence is a controller journal, separate from finding/signature
history. Do not mutate old occurrence/identity rows or stamp a partial attempt
as a completed detector. Every event is canonical closed JSON (<=65536 bytes):

```text
schema:"scanipy-local-runtime-event/1",attempt_id:UUID,sequence:positive int64,
previous_event_digest:H|null,event_id:UUID,
kind:"reserved"|"loaded"|"created"|"started"|"observed"|"released"|
     "domain-exited"|"cleanup"|"admitted"|"failed"|"orphaned"|
     "call-intent"|"call-result",
recorded_at:UtcInstant,host_boot_id:UUID,elapsed_ms:int,
operation_id:UUID,mode:Mode,request_digest:H,
installation_id:UUID,installation_generation:positive int64,
installation_sha256:H,controller_profile_sha256:H,
domain_profile_sha256:H,inventory_sha256:H,inventory_digest:H,program_digest:H,
expected_image_config_id:ImageId,expected_oci_manifest_digest:ImageId|null,
observed_image_config_id:ImageId|null,observed_oci_manifest_digest:ImageId|null,
container_name:Text,container_id:H|null,
payload:EventPayload
```

Sequence starts1 with null previous digest; each later event increments exactly
once and links `D(event schema,previous bytes)`. Changed replay is rejected.
The chain detects inconsistent retained bytes but is **not** an external
signature or self-authenticating durable store. Actual append/fsync/readback
and ownership are required; evidence-write failure is fatal. Journal storage
must outlive CLI temp/control cleanup and restart, and its own quota/bounds
must be installed before launch. A returned hash without its retained bytes
is not evidence.

The full event form starts only after successful bounded loading/measurement
and request/prerequisite validation. Its profile/inventory/program facts then
refer to those actual loaded/measured bytes. Image `expected_*` fields are the
installation pins, not claimed observations; `observed_*` remain null until
corroborated by the actual image/container response. A mismatch is preserved
as the observed differing value and causes failure, never overwritten with
the expected value. Missing OCI evidence remains null. `container_id` is null
until acknowledged or safely recovered; a requested name is not an ID.

Earlier errors use a separate closed bounded refusal, not a zero-filled event:

```text
{schema:"scanipy-local-runtime-refusal/1",refusal_id:UUID,
 recorded_at:UtcInstant,host_boot_id:UUID,elapsed_ms:int,
 operation_id:UUID|null,requested_mode:Mode|null,
 phase:"load"|"authority"|"reserve",code:FailureCode,
 anchor:{deployment_id:UUID,installation_id:UUID,generation:positive int64,
         installation_sha256:H}|null,
 input:{size:int,sha256:H}|null,available_evidence:[BlobRef,...],
 primary_error_id:UUID|null}
```

Maximum16384 bytes, at most16 evidence refs. `refusal_id`/time/boot ID are real
controller facts; operation/mode/input become present only after their own
bounded primitive validation, and anchor only after the trusted factory's
independent anchor is obtained. Never format/hash a poisoned or oversized
candidate just to populate failure evidence. No image/program identity is
required before it exists. Raw bounded failure evidence, if any, remains in
the protected refusal namespace. Failure to retain the refusal still prevents
launch and propagates the real evidence-store error; it cannot imply success.

Closed payload variants, with no free-form caller-defined metadata:

- `reserved`: `{launch_sha256:H,launch_bytes_ref:BlobRef,input:BlobRef}`.
- `loaded`: `{metadata:[MetadataRef x4],measurement_elapsed_ms:int,
  cli_file:FileObservation,socket:SocketObservation,daemon_calls:[CallRef x2]}`;
  daemon version then info, retaining their actual invocations and outputs.
- `created`: `{create_call:CallRef,inspect_call:CallRef,config_digest:H}`.
- `started`: `{start_call_id:UUID,pid:int,start_ticks:int,control_path:AbsolutePath}`.
- `observed`: `{sample:KernelObservation,inspect_call:CallRef,prerequisite:BlobRef}`.
- `released`: `{release:BlobRef,prerequisite:BlobRef,published_at:UtcInstant}`.
- `domain-exited`: `{start_call:CallRef,container_inspect_call:CallRef,
  domain_result:BlobRef|null,domain_validation:"valid"|"rejected"|"invalid"}`.
- `cleanup`: `{state:"complete"|"incomplete",calls:[CallRef,...],
  final_inspect_call:CallRef|null,cgroup_empty:bool|null,client_reaped:bool,
  parent_lease_action:"none",invocation_slot:"held"}`.
- `admitted`: `{result_digest:H,prerequisite:BlobRef,cleanup_event_digest:H,
  parent_lease_action:"none",invocation_slot:"released"}`.
- `failed`/`orphaned`: `{phase:Phase,code:FailureCode,calls:[CallRef,...],
  kernel:BlobRef|null,primary_error_id:UUID|null,cleanup_event_digest:H|null}`.
- `call-intent`: `{call_id:UUID,call_sequence:int,operation:CliOperation,
  target:string|null,invocation:BlobRef}`.
- `call-result`: `{intent_event_digest:H,call:CallRef}`.

The last two complete event variants are capped at8192 bytes and share the
existing512 KiB metadata/32 MiB total attempt budgets. Call sequence is1..16;
the one operation enum and operation-specific target syntax are defined in
[PROCESS-EVIDENCE.md](PROCESS-EVIDENCE.md). Persist/read back the requested
invocation and intent before a CLI call; persist/read back actual result blobs
before appending call-result. Exact replay is idempotent; changed replay fails.
Only one execution/result is allowed per call ID. Results can complete out of
ordinal order while attached start runs concurrently with bounded inspection.

`started.start_call_id` references its preceding start intent; other CallRefs
reference preceding same-attempt call-result events with matching operations.
The inspect CallRefs above retain the raw response through actual stdout rather
than dropping the invocation/failure association. An unresolved call has an
unmatched durable intent, not fabricated empty output or a completed result.

`BlobRef={sha256:H,size:int,key:Text}` has `key` exactly `blobs/` plus that H
and refers only to the attempt's
trusted retained evidence store, not URI/network/user paths. Exact bytes must
be read back and hash/size verified. `MetadataRef={role:MetadataRole,path:AbsolutePath,
blob:BlobRef,observation:FileObservation}`. `FileObservation` is exactly
`{device,inode,uid,gid,mode,nlink,size,mtime_ns,ctime_ns}` with bounded int64
values; mode is the observed permission mask defined in §1. `SocketObservation`
is `{path,device,inode,uid,gid,mode}`, actual socket type independently checked.

`CallRef={call_id:UUID,operation:CliOperation,outcome:BlobRef}` retains an exact
versioned serialization of the **actual shared** `ProcessOutcome`/invocation
and bounded stream bytes, not a fabricated inner-process outcome. The serializer
must preserve optional unknowns, original reason/cleanup, counts/hash/EOF and
truncation from those actual models; exact raw failures remain private causes.
No arbitrary environment or exception text appears in user-facing summaries.
The exact proposed codec, ten-operation enum, acyclic intent/result references,
stored/live separation, spool custody, loss-graph overflow and bounded future
store API are in [PROCESS-EVIDENCE.md](PROCESS-EVIDENCE.md). Codec/store/controller
implementation remains pending. Intended and actual invocation bytes remain
distinct, including mismatches; diagnostic error graphs are explicitly lossy
and cannot replace live original exception chains or reconstruct authority.
The codec additionally binds a directly selected exact transport-error carrier
(or the root error's immediate explicit carrier cause) to its complete supplied
outcome; it never searches an arbitrary exception graph for current-call proof.
Key-inclusive pre-parse bounds and retained-graph semantic validation are
mandatory even when stored JSON is canonical. Original child handles, notes and
live primary/cleanup chains remain private and unchanged.

`KernelObservation` is closed:

```text
{observed_at:UtcInstant,pid:int,start_ticks:int,host_boot_id:UUID,
 cgroup:{path:AbsolutePath,device:int,inode:int,memory_max:int|"max",swap_max:int|"max",
         pids_max:int|"max",cpu_quota_us:int|"max",cpu_period_us:int,populated:bool},
 namespaces:{pid_inode:int,net_inode:int,cgroup_inode:int,ipc_inode:int,
             mount_inode:int,user_inode:int},
 network:{interface_names:[Text,...],nonloopback_routes:int},
 security:{uid:int,gid:int,groups:[int,...],nnp:int,cap_inheritable:int,cap_permitted:int,
           cap_effective:int,cap_bounding:int,cap_ambient:int,seccomp_mode:int,
           apparmor_label:Text},
 mounts:[{target:AbsolutePath,source:Text,fstype:ID,readonly:bool,
          nosuid:bool,nodev:bool,noexec:bool,propagation:ID,
          total_bytes:int|null,total_inodes:int|null},...],
 raw:[BlobRef,...]}
```

At most64 mount rows and16 raw refs. Filesystem type/source fields are observed
bounded text (4096 bytes); only policy-approved exact values pass. Ordinary
bind/source filesystem sizes are null; writable tmpfs sizes/inodes must be
known. Kernel-observation completeness is mandatory before release; missing
fields are represented only by absent observation events plus explicit failure,
not zero-filled facts. Later post-exit evidence may genuinely lack a PID;
do not manufacture a kernel sample from the pre-release state.
The observation schema can retain mismatching facts: `max` records a genuinely
unbounded cgroup value; groups has at most32 entries, NNP is0/1, seccomp0/1/2,
and capability masks are bounded nonnegative int64. Release separately requires
the exact configured limits, empty groups and zero capability masks. Network
observations have at most32 interface names (each<=64 bytes); release requires
exactly loopback `lo` and zero nonloopback routes, with bounded original
namespace `/proc` network records retained. A distinct netns inode alone is
not a no-egress check. Unsupported/unreadable kernel views block release.

`Phase` is `load|authority|reserve|create|inspect|start|release|execute|retain|
cleanup|admit|recover`. `FailureCode` is `installation-unavailable|metadata-invalid|
artifact-mismatch|unsafe-path|limit|deadline|authority-unavailable|authority-stale|
image-unavailable|config-mismatch|kernel-unavailable|kernel-mismatch|spawn-failed|
transport-failed|protocol-invalid|domain-rejected|evidence-failed|cleanup-incomplete|
ambiguous-create|ambiguous-start|ambiguous-release|cancelled|unsupported`.
Unknown exception messages are private evidence, never new public enum values.

Only admitted event with valid domain response, full EOF/limits, current
prerequisite recheck and completed cleanup allows the owning adapter to expose
a completed result. It still is not a completed scan or scalar semantic proof.
Nonzero domain rejection remains failure even when cleanup succeeds.

## 10. Recovery, expiry and diagnostic separation

Before each new launch, the installed controller reconciles its journal's
nonterminal attempts. The name journal supports unknown-ID recovery only by
corroborating exact attempt/operation/profile/image/config labels and retained
create intent; matching name alone cannot adopt a foreign container. If
ownership cannot be proved, record a blocked orphan for operator reconciliation,
do not stop unrelated containers or create another child with the same input.

Terminal cleanup must observe stopped exact container, owned cgroup empty/gone
with its prior identity, attach-client/thread disposal, and retained output.
The controller owns only this invocation and its local concurrency slot. It
does **not** release/renew the parent scan's work or capture leases. Those stay
under the outer workflow owner's control through the final current-authority
recheck, result admission and durable occurrence/result finalization. A single
syntax file must not retire custody needed by subsequent files. If the parent
needs renewal, it obtains new genuine immutable authorization/fence evidence
before the next invocation; it cannot restamp an old release as current.

After complete cleanup, perform final prerequisite recheck, retain the admitted
or failed terminal record, then release the controller's concurrency slot.
Failure records with complete cleanup can release that slot only after durable
terminalization; incomplete cleanup holds an orphan barrier. The outer workflow
alone releases its leases after durable finalization/all children, and may not
delete/reuse source while any referencing invocation is nonterminal/orphaned.
Expiry alone is not proof a child stopped. The actual parent retirement/retry
adapter must consult this durable barrier; its absence blocks operational launch.
There is no new temporary source lease or signing hierarchy in this profile.
Killing the Docker client does not establish container cleanup. Removing the object is a later
exact-ID/nonforced step after final evidence; removal failure cannot destroy
the evidence or turn unknown termination into known cleanup. Crash recovery
does not reuse release files, old fences or old admission epochs.

Production factory and test harness are separate entrypoints/composition.
Controlled tests may build task-owned fixtures and test trust, but label their
records `diagnostic` in a separate diagnostic artifact domain, not this
operational event schema with invented request/authorization IDs. No CLI/env
switch converts those fixtures into an installed production loader. Production
negative tests must prove missing loader/authority/controller never invokes
the private diagnostic runner or a native child.

This document authorizes no test container, image preparation, Docker daemon
change or runtime probe. Future controlled runtime tests require explicit
resource/target authorization and may run trusted failure sentinels only, never
target repository code/build hooks. Operator identity, independent trust/admission
installation, runtime installation pins and restore recovery remain actual
owner decisions; engineering review of this proposal does not supply them.

## 11. Dependency-ordered TODOs and acceptance controls

- [x] **LRP-01 — engineering review/freeze.** Root reviewed the exact records,
  proposed 128/256 MiB outer profiles, mount/inode ceilings and deadline split.
  Scoped peer reviews and the anchor/currentness corrections are recorded above.
  This is design approval, not installed-runtime or operational acceptance.
  Resolve any installed-image incompatibility openly; do not relax inner limits.
- [x] **LRP-02 — allocate loader-only implementation.** Root assigns the schema
  agent these two new files in the controller worktree:
  `tools/worker/runtime_profiles.py`, `tests/unit/test_runtime_profiles.py`.
  The local implementation checkpoint is recorded in section 12; canonical
  LRP-03/04 acceptance remains outstanding. Import actual shared measurement/types;
  no domain callback, Docker call, authority installation or duplicate codec.
- [ ] **LRP-03 — low-level metadata/anchor-data falsifiers.** Mismatching supplied
  pin/generation/purpose or declared origins; no claim to detect a coherent
  caller-selected stale anchor or authenticate its origin. Reject
  symlink/hardlink/FIFO/special/owner/mode errors, descriptor close/reuse,
  replacement races, partial reads, first/final deadline, poisoned exact records,
  deep/shared-branch/escaped-byte amplification, and N-1/N/N+1 bounds.
- [ ] **LRP-04 — domain mapping controls.** Exact verifier profile unchanged;
  syntax six-field carrier stays pure; per-invocation container scratch never
  accesses host work paths; actual inventory/program/domain hash parity and
  metadata exclusions; stale-pyc/no ambient import negative controls.
- [ ] **LRP-05 — close controller implementation contracts.** Specify exact
  pinned Docker create/inspect renderer/field mapping, actual shared-outcome
  serializer, durable append/readback/recovery repository and bounded kernel
  readers. Proposed eventual files are `tools/worker/runtime_controller.py`,
  `tools/worker/runtime_bootstrap.py`, `tools/worker/runtime_evidence.py` and
  `services/scan/runtime_factory.py`, with separately allocated tests. No
  implementation is authorized by listing them here.
- [ ] **LRP-06 — genuine mode authority.** Implement/test installed operator,
  auditor, live ledger/admission and capture adapters. Publication has no
  preexisting receipt/lease; historical survives content revocation without
  gaining execution rights; execution verification avoids circular prerequisites;
  syntax requires real fresh accepted-content checks and exact source custody.
  Separately test the real factory's independent startup-anchor acquisition and
  rereads immediately after load and before create/release/admission: stale
  DB/installation restore, changed generation/hash/other pins, self-selected
  anchors, missing factory composition and failed rereads must block operation.
  Loader success alone must never bypass the owning adapter's domain-profile
  semantic validation or those currentness/authority checks.
- [ ] **LRP-07 — hermetic renderer/bootstrap/recovery falsifiers.** Reject extra
  env/image-defaults/mounts/ports/groups/namespaces, wrong socket/daemon/image,
  plugin/context/helper traps, release-before-inspection/replay/change/race,
  stale fence/time, expired lease, PID reuse/mixed samples, ambiguous create/
  start/release, evidence failure and incomplete client/container cleanup.
- [ ] **LRP-08 — separately authorized installed runtime tests.** Prove actual
  no-egress/static-only behavior, memory/no-swap/CPU/PIDs/tmpfs/inodes, exact
  arbitrary binary stdin/EOF, output bounds, OOM/deadline/cancellation,
  setsid/double-fork disposal, controller restart and original-failure retention.
  Inspect defaults instead of assuming flags worked; no scanned-code execution.
- [ ] **LRP-09 — actual integrations.** Replace operational refusals only after
  reviewed real loader/controller/adapters exist. Reuse actual domain result
  codecs and authority rechecks; preserve raw failures/occurrences separately
  from identity and never treat absent results as no findings.
- [ ] **LRP-10 — acceptance and full-scope continuation.** Independent security
  review, marker-selected tests, exact-head normal hooks/CI and canonical APPROVE,
  then real composed-path checks. Joern/Semgrep/CodeQL, online Git, projection/
  solver isolation, asynchronous status, provenance and offline stage rehearsals
  remain distinct mandatory work. No full R-task is completed by this proposal.

No operational keys, profiles, installed anchors or container evidence are
claimed as produced here. The original proposal produced no test evidence;
the diagnostic loader checkpoint below is subsequent implementation work.
Upstream Docker source was read without launching Docker;
its semantics inform the required falsifiers but do not prove this machine's
installed binary, daemon, image or runtime configuration.

## 12. Local loader review checkpoint — September 25

The allocated loader and private-file tests form a locally reviewed implementation
checkpoint, not accepted by canonical review. Initial selected checks passed:
148 loader cases plus 73 unchanged shared-inventory cases, 221 total with zero
failures/errors/skips (`/tmp/scanipy-runtime-profiles-expanded.xml`). These
exercise actual file measurement, not configured-digest equality, and deliberately
allow opaque domain bytes to demonstrate that this boundary grants no semantic
or operational authority.

Root's independent review reproduced a cleanup-evidence defect: appending close
failures preserved an explicit `__cause__` but omitted an earlier implicit
`__context__`. The configured external regression failed on the initial frozen
code (`/tmp/scanipy-runtime-profiles-root-context-configured-before.xml`). An
earlier external-file invocation lacked the repository configuration and had a
marker warning; it is not substituted for that configured failure.

The correction snapshots cause-or-context before cleanup, and snapshots each
cleanup failure's original chain before later closes can mutate it. A promoted
cleanup interruption remains the original object. Immediate cause-group members
are deduplicated by identity, without rewriting existing private chains or
retrying an uncertain numeric descriptor. Thirteen new repository cases cover
public-loader and direct-cleanup paths, explicit-cause precedence, context-only
failures, promoted interruptions, later context mutation and no-failure controls.
Explicit `is not None` selection avoids invoking a custom exception's truth
method when choosing its original cause; two controls exercise that distinction.

Final focused verification includes those 161 loader cases, 73 unchanged shared
cases and root's one independent external regression: 235 selected cases, zero
failures/errors/skips (`/tmp/scanipy-runtime-profiles-review-final-named.xml`). Root
independently repeated all 235 in 2.59 seconds
(`/tmp/scanipy-runtime-profiles-root-final.xml`). Corpus and root reviewed the
final context-preserving/explicit-None delta and approved this limited boundary.

The configured full `pytest tests/` run passed 1793 cases with 51 existing skips,
zero failures/errors, in 142.900 seconds
(`/tmp/scanipy-runtime-profiles-full.xml`). The actual normal pre-push hook's
four stages passed; its selected unit/invariant run passed 1748 cases with 11
existing skips, zero failures/errors, in 122.643 seconds
(`/tmp/scanipy-runtime-profiles-prepush.xml`). Repository Ruff/format, configured
strict typing, separate module typing and explicit three-file pre-commit checks
passed. No threshold, skip policy, baseline or hook bypass was introduced.

The reviewed source SHA256 is
`b3e721a535243262d83ea3fe40f5433e8619497702c3ed0cbc51e85cf1568daa`;
the test-file SHA256 is
`4ab2b0bbbb1358edaf7cf7ae1fa94f6cdd58b0a1dc9179ca7b27bb70fd89fd82`.
These are task-local verification records, not portable signed acceptance
artifacts. Normal commit hooks, later combined-main verification and exact-head
remote CI/canonical SUCCESS with final APPROVE remain required before merge.
No runtime/container permission is inferred from these checks.
The real factory/current-anchor, domain decoder, image-namespace, controller,
admission/ledger and operational no-egress integrations remain unimplemented here.
