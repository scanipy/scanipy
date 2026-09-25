# Docker 29 pipe-runtime policy — implementation contract draft

Owner: root coordinator. Tracking: #400, under DECISION-BHMEA-01.
Status: renderer-only sections 3/4 independently reviewed and root-approved;
validator, kernel, storage and launch acceptance remain outstanding. This document neither authorizes a
container launch nor establishes an installed image/runtime or operational
authority. LOCAL-RUNTIME-PROFILE.md remains the outer profile/data contract.

## 1. Purpose and non-negotiable boundary

Turn the installed profile into a finite Docker argv and compare the actual
image/container responses against the entire expected configuration. A pure
renderer or successful inspect comparison is not launch authorization. The
installed factory must independently load current pins, domain semantics and
mode authority; the controller must retain evidence, observe actual kernel
state, gate release, dispose the exact container and recheck before admission.

The initial profiles are only accepted-input verification and Python syntax
parsing. No scanned source is executed. Joern, Semgrep, CodeQL, online Git and
the API/queue workflow remain separate required integrations.

All bounds in the profile stay unchanged: 128/256 MiB outer memory with no
extra swap, 16 PIDs, one CPU quota, 8 MiB work scratch, the original 3/5 second
inner budgets and 30 second total launch budget. An incompatible Docker
default is an explicit design/test failure, not permission to increase limits.

## 2. Primary-source basis and limitations

Pinned source revisions:

- Docker CLI v29.1.3 resolves to
  `f52814d454173982e6692dd7e290a41b828d9cbc`.
- Moby docker-v29.1.3 resolves to
  `fbf3ed25f893e6ce21336f1101590e40a13934f4`.

The source references below define expected behavior; they are not binary,
daemon, image, kernel-policy or resource-enforcement attestations.

| Source | Relevant contract |
|---|---|
| [CLI container options](https://github.com/docker/cli/blob/f52814d454173982e6692dd7e290a41b828d9cbc/cli/command/container/opts.go) | Actual Config/HostConfig construction, explicit init, healthcheck, security options and stdin closure |
| [CLI mount parser](https://github.com/docker/cli/blob/f52814d454173982e6692dd7e290a41b828d9cbc/opts/mount.go) | CSV fields and forced recursive-readonly binds |
| [CLI create](https://github.com/docker/cli/blob/f52814d454173982e6692dd7e290a41b828d9cbc/cli/command/container/create.go) | Pull policy and create behavior |
| [CLI attached start](https://github.com/docker/cli/blob/f52814d454173982e6692dd7e290a41b828d9cbc/cli/command/container/start.go) | Attach-before-start and exit waiting |
| [CLI stream handling](https://github.com/docker/cli/blob/f52814d454173982e6692dd7e290a41b828d9cbc/cli/command/container/hijack.go) | Non-TTY binary input, EOF and demultiplexed output |
| [API Config](https://github.com/moby/moby/blob/fbf3ed25f893e6ce21336f1101590e40a13934f4/api/types/container/config.go) | Complete portable configuration fields |
| [API HostConfig](https://github.com/moby/moby/blob/fbf3ed25f893e6ce21336f1101590e40a13934f4/api/types/container/hostconfig.go) | Complete resources, namespace and mount fields |
| [API inspect records](https://github.com/moby/moby/blob/fbf3ed25f893e6ce21336f1101590e40a13934f4/api/types/container/container.go) | Actual container identity, state and mount observations |
| [Moby OCI defaults](https://github.com/moby/moby/blob/fbf3ed25f893e6ce21336f1101590e40a13934f4/daemon/pkg/oci/defaults.go) | Engine pseudo-filesystems, default masks and host-dependent thermal masks |
| [Moby OCI construction](https://github.com/moby/moby/blob/fbf3ed25f893e6ce21336f1101590e40a13934f4/daemon/oci_linux.go) | Runtime mounts, limits, default-rlimit merging and security behavior |

The first attempted Moby defaults source path was obsolete and returned 404;
the actual source is daemon/pkg/oci/defaults.go, not oci/defaults.go or a
separate defaults_linux.go. No runtime test result is inferred from fetching it.

## 3. Renderer input and path derivation

The renderer is internal, data-only and side-effect free. The exact interface
below is approved for the two-file allocation in DP-02. It must not accept
arbitrary extra flags, shell fragments, callback runners or caller
environment overlays. The factory derives its bounded primitive input from
the actual loaded metadata, measured bindings and newly allocated attempt.
No freely constructed plan object authenticates its own installation.

Use the real shared process invocation/outcome types; do not introduce a
parallel transport. Revalidate/freeze input primitives before iteration,
formatting, filesystem access or callback-capable conversion. A poisoned exact
record is not safe merely because its class matches. The proposed API is:

```python
@dataclass(frozen=True, slots=True, repr=False)
class RuntimeDockerCreateSpec:
    purpose: str
    docker_executable: str
    python_executable: str
    worker_path: str
    bootstrap_path: str
    domain_profile_path: str
    host_work_root: str
    runtime_roots: tuple[str, ...]
    uid: int
    gid: int
    deployment_id: str
    installation_id: str
    attempt_id: str
    operation_id: str
    installation_generation: int
    image_config_id: str
    request_digest: bytes
    controller_profile_sha256: bytes
    domain_profile_sha256: bytes
    inventory_sha256: bytes
    program_digest: bytes
    launch_sha256: bytes

def render_runtime_docker_create(spec: RuntimeDockerCreateSpec) -> FrozenInvocation: ...
```

Import the actual `FrozenInvocation` from tools.worker.bounded_process, not a
new lookalike. The shared transport commits 62a6158 and d3ce731 are separately
reviewed local dependencies, not assumed merged or operational. No filesystem,
clock, process, network, profile discovery or authority call occurs here.
`RuntimeDockerPolicyError` has a fixed non-content-bearing message.

At the public boundary require the exact dataclass, read its class-owned slots
without caller properties, privately snapshot every field and validate exact
builtins before using them. No Path/UUID object, custom Mapping/list/iterator,
string subclass or arbitrary model is accepted. Purpose has the two exact
profile values; UID/GID are integers 1..2147483647; generation is a positive
signed-64-bit integer. Identity strings are canonical lowercase hyphenated UUIDs;
digests are exact32-byte bytes; image ID is sha256: followed by64 lowercase hex.
All paths are exact normalized absolute scalar strings <=4096 UTF-8 bytes,
nonroot, with no empty/dot/dot-dot components, backslash or C0/C1 controls.
Runtime roots are an exact tuple of3..9 unique such strings; nested views are
allowed. Bound lengths/counts before encoding, allocation or iteration.

The factory remains responsible for proving these primitives correspond to
genuine current loaded/measured metadata, correct root roles and domain
semantics. Bootstrap must be inside a declared runtime root in this data-only
check; its stronger application-root/member/raw-hash proof belongs to the
actual loader. A pure returned command does not establish either fact.

Derive host attempt path as host_work_root + slash + canonical attempt_id.
Its children are exactly the existing outer-profile names: control,
docker-config, cli-home, cli-tmp and cli-bin. CLI cwd is the private attempt
directory itself, not a newly invented cli-cwd. Account for the derived suffixes
within the4096-byte path cap. Directories and config are prepared/rechecked by
the later controller, never by this renderer. FrozenInvocation has zero stdin
bytes and SHA256(empty), the sorted ten CLI environment pairs, derived cwd and
complete argv. This declares intended empty create input, not observed child EOF.

Every returned argv has <=256 entries, <=8192 UTF-8 bytes per entry and
sum(encoded_length+1)<=65536. The ten environment entries total<=16384 bytes,
counting name/value/separators. Calculate CSV escaping amplification before
calling the encoder and recheck the final result; two legal4096-byte paths may
not fit one8192-byte mount argument and must be rejected, never truncated.
These are the actual shared transport's argv bounds plus a stricter environment
budget, not permission to emit arbitrary commands within them.

Fixed container destinations:

- Control directory: `/run/scanipy-control`, readonly to the worker.
- Launch file: `/run/scanipy-control/launch.json`.
- Release file: `/run/scanipy-control/release.json`.
- Fresh work tmpfs: `/run/scanipy-work`.
- Bootstrap initial cwd: `/`; isolated CPython flags prevent cwd imports.
- Bootstrap and inner private/cache directories are separately derived from
  the actual attempt UUID under the work tmpfs, as in the profile.

Host control is the attempt's exclusive private directory under the installed
host work root. The later controller, not this pure renderer, establishes its
actual ownership/modes and inability of source/API principals to write it.
The renderer checks overlap only among its supplied runtime roots/files,
domain-profile path/parent, host work root and derived control/work destinations.
Source/capture/evidence and other metadata origins are NOT inputs to this API:
the installed factory must separately check all real origins in both directions.
No discovery, callback or extra authority field fills that gap implicitly.

The domain FILE must be disjoint, component-wise in both directions, from
every supplied runtime root/file and the host work root. Its PARENT must be
disjoint from runtime/import roots and host/container work/control paths.
Distinct standalone executable/worker files may share that private parent;
do not invent a stronger parent-versus-standalone-file exclusion than the
actual verifier imposes. The installed factory and worker still establish
real filesystem ownership, modes, ancestry and distinct file origins.

The closed reserved container targets are `/proc`, `/sys`, `/dev`,
`/etc/hosts`, `/etc/hostname`, `/etc/resolv.conf`, `/run/scanipy-control` and
`/run/scanipy-work`. Reject runtime-root/file/domain-profile bind destinations
equal to, containing, or contained by any reserved target, component-wise.
The host CLI executable is not a container bind. The fixed control mount and
the fixed work/dev/shm tmpfs definitions are intentional exact policy entries,
not an exception permitting input-selected mounts at those targets. The three
possible engine-managed /etc files are conservatively reserved even before
actual mounted-state observations establish whether they exist.
[Pinned engine-managed files](https://github.com/moby/moby/blob/fbf3ed25f893e6ce21336f1101590e40a13934f4/daemon/container/container_unix.go#L61-L122).

Derive the minimal outermost identity-mapped readonly cover of all runtime
roots; preserve the independent measurement of every declared nested view.
An executable/worker file already contained in that cover needs no duplicate
bind; otherwise bind that exact file identity-mapped and readonly. Reject
conflicting destinations/mappings, not legitimate nested inventory roots.
Add the exact domain-profile file and control directory only.
Do not bind source for either initial pipe profile. Sort by destination UTF-8
bytes, reject duplicate destinations and enforce the profile's 16-bind cap.

Every bind is `type=bind`, `readonly`, `bind-propagation=rprivate`,
`bind-recursive=readonly`. Its actual API BindOptions must have forced recursive
readonly true and all create/nonrecursive/read-only-nonrecursive alternatives
false or absent as permitted by that field's schema. This fails on unsupported
kernels instead of leaving writable submounts or hiding measured child mounts.

Mount values use the pinned parser's CSV grammar: encode each full `key=value`
field with a real CSV encoder, including commas/quotes in paths. No ad-hoc
string concatenation and no shell escaping. Round-trip tests must show exactly
one Source and Target, preserving bytes without injecting extra options.

## 4. Fixed create command

Every call starts with the exact measured absolute Docker executable, explicit
`--host unix:///run/docker.sock` and `--config <private-empty-config-dir>`.
The CLI's complete ten-variable environment, empty helper PATH, API 1.52 and
bounded private cwd/config are as specified in LOCAL-RUNTIME-PROFILE.md.
Never use an ambient context, credential helper, plugin, proxy, TLS override,
Docker socket mount or `--use-api-socket`.

The create command has one deterministic order, with values derived only from
the checked installation/attempt. The proposed fixed options are:

```text
container create
--pull never
--name scanipy-runtime-<attempt UUID hex>
--hostname scanipy-runtime-<attempt UUID hex>
--user <controller UID>:<controller GID>
--network none
--ipc private
--cgroupns private
--userns host
--read-only
--cap-drop ALL
--security-opt no-new-privileges
--security-opt seccomp=builtin
--security-opt apparmor=docker-default
--runtime runc
--restart no
--init=false
--log-driver none
--no-healthcheck
--interactive
--attach stdin --attach stdout --attach stderr
--memory <profile bytes>
--memory-swap <same profile bytes>
--cpu-period 100000 --cpu-quota 100000
--pids-limit 16
--shm-size 65536
--workdir /
--entrypoint <measured Python executable>
<exact sorted labels, environment, mounts and scratch options>
<full sha256 image config ID>
<bootstrap argv excluding its already supplied executable>
```

PID and UTS remain private by omission: their API fields are the empty string,
not the literal `private`. No host PID/UTS mode is allowed. Explicit
`--init=false` is necessary because omission can use the daemon's init default.
`seccomp=builtin` is the CLI's reserved builtin value; `seccomp=default` is not
interchangeable and can cause a local filename read. No TTY, detach, port,
device, group, sysctl, annotation, volume, privileged, automatic-remove,
network alias or stop/restart override is allowed.

Container Env is exactly the five bootstrap rows: LANG/LC_ALL=C.UTF-8, TZ=UTC,
PATH empty and HOSTNAME equal to the attempt name. Reject duplicate names or
inherited image extras. Bootstrap verifies its actual environment before input
and replaces it with the unchanged domain worker's exact environment at exec.

Labels are exactly11 sorted keys under the literal `io.scanipy.runtime.` prefix:
schema, deployment-id, installation-id, generation, attempt-id, operation-id,
request-digest, outer-profile-sha256, domain-profile-sha256, inventory-sha256 and
program-digest. Schema value is `scanipy-docker29-pipe-config/1`; other values
are the matching canonical UUID, decimal generation or lowercase digest fields
above. Keys<=64 bytes and values<=64 bytes, with these stronger field-specific
constraints. There is no extra-label input. Neither image-inherited labels nor an arbitrary label
filter establishes container ownership. Retain and compare the complete intent.

Scratch uses the literal tmpfs option set
`rw,nosuid,nodev,noexec,size=8388608,nr_inodes=1024,mode=0700,uid=<UID>,gid=<GID>`.
The pinned CLI's --mount tmpfs form does not expose the needed inode option;
the legacy --tmpfs option map does. The proposed engine-mount correction below
still needs independent contract review and actual compatibility tests; do not
enable this draft command.

### 4.1 Explicit bounded engine temporary filesystems

The inode issue is confirmed: Linux's default inode ceiling derives from host
RAM/low-memory limits, independently of an explicitly chosen tmpfs byte size.
Moby's original /dev and /dev/shm mounts do not set nr_inodes. They cannot be
assumed to meet the profile's 32768-inode aggregate on this host.
[Linux v6.8 tmpfs defaults](https://github.com/torvalds/linux/blob/v6.8/mm/shmem.c#L140-L145),
[independent mount defaults](https://github.com/torvalds/linux/blob/v6.8/mm/shmem.c#L4308-L4315).

Root's proposed correction keeps every existing resource ceiling and IPC
private. In addition to the work tmpfs, render exactly two --tmpfs entries:

```text
/dev:rw,nosuid,noexec,dev,strictatime,mode=755,uid=0,gid=0,size=67108864,nr_inodes=16384
/dev/shm:rw,nosuid,noexec,nodev,mode=1777,uid=0,gid=0,size=65536,nr_inodes=16384
```

The two engine tmpfs limits total exactly 67174400 bytes and 32768 inodes.
The explicit `dev` flag applies only to /dev so its standard device nodes work;
Moby otherwise adds nodev to a user tmpfs. Work/shm remain nodev. No writable
host bind, host /dev, mount capability or root process is introduced.

Pinned Moby removes ALL default /dev/* mounts when /dev is explicitly mounted.
The pipe-only, non-TTY first profile therefore deliberately has no /dev/pts or
/dev/mqueue mounts; /dev/shm is explicitly restored as the bounded tmpfs above.
This is not a claim that all Docker-default facilities survive. A worker that
needs those missing facilities must fail compatibility testing and get a
separate reviewed design, not a hidden host bind or relaxed quota.

Moby's build installer defaults to runc v1.3.4, whose peeled source revision is
`d6d73eb8c60246978da649ffe75ce5c8bca8f856`. Its default node setup is not disabled
by a tmpfs /dev. It creates null/random/full/tty/zero/urandom nodes and symlinks
for fd/stdin/stdout/stderr; an optional core symlink must be retained as an
observed variant with /proc/kcore still masked. Its ptmx setup creates the
relative symlink `pts/ptmx`, which is deliberately dangling without devpts.
No host PTY is exposed by that symlink. The kernel reader must reject extra
device mounts/nodes or an unexpected valid ptmx target; empty HostConfig.Devices
means no caller devices, not no standard devices or no device-cgroup rules.
[Moby build default](https://github.com/moby/moby/blob/fbf3ed25f893e6ce21336f1101590e40a13934f4/hack/dockerfile/install/runc.installer),
[runc device defaults](https://github.com/opencontainers/runc/blob/d6d73eb8c60246978da649ffe75ce5c8bca8f856/libcontainer/specconv/spec_linux.go#L201-L298),
[runc device and ptmx setup](https://github.com/opencontainers/runc/blob/d6d73eb8c60246978da649ffe75ce5c8bca8f856/libcontainer/rootfs_linux.go#L168-L179).

That build default does not prove this Ubuntu installation uses those exact
runtime bytes/configuration. Corroborating installed-runtime identity and
controlled behavior remains required. Runc can fall back to bind-mounting
standard host devices when mknod is denied; this initial strict policy rejects
such unexpected device bind mounts rather than silently calling them new nodes.
Tests must prove usable null/urandom, unavailable PTY and absent mqueue mount, actual finite
statfs byte/inode capacities and the exact mount/device inventory before release.
No runtime test has been performed for this candidate.

The missing /dev/mqueue mount does not disable POSIX message-queue syscalls:
Linux uses an internal mount for those operations. Likewise, a /dev/shm quota
does not bound all anonymous or SysV shared memory. IPC namespace, actual
memory/cgroup and reviewed seccomp controls remain separate; do not advertise
syscall denial without a separately enforced/tested policy.
[Linux message-queue implementation](https://github.com/torvalds/linux/blob/v6.8/ipc/mqueue.c#L897).

## 5. Image and effective-container policy — not yet allocated

The renderer-only interface above does not implement this validator. Parse
bounded full CLI inspect output, not arbitrary --format templates: exactly one
JSON array element, at most262144 raw stdout bytes, duplicate keys/floats/
nonfinite values rejected, depth<=32, total values<=20000, each string<=8192
UTF-8 bytes, and bounded per-field collections. Check amplification/counts
before serialization. Every result remains charged to the existing call and
attempt output/metadata budgets; this is not a separate allowance.

Before create, inspect the exact local image config ID, never a tag, using the
bounded nonattached transport. Reject absent/multiple/mismatching responses,
wrong linux/amd64 platform, nonempty variant, image volumes/ports/on-build/
healthcheck or unsupported defaults. The installed profile's optional manifest
digest is distinct from the config ID: only corroborated actual evidence fills
it; no invented digest is allowed when local manifest evidence is missing.

Image.Config is the pinned DockerOCIImageConfig, NOT container.Config. Its
allowed omitempty key universe is User, ExposedPorts, Env, Entrypoint, Cmd,
Volumes, WorkingDir, Labels, StopSignal, ArgsEscaped, Healthcheck, OnBuild and
Shell. Explicit exact-type/null/omission rules must be validated against that
type. Image Env can contain only the five known bootstrap variable names whose
values the renderer replaces; duplicates or additional keys are rejected.
Moby appends image environment/labels/ports/volumes that are missing from the
container request, so supplying known --env options never proves extras vanished.

The complete image Config must be assessed, not only Env. Existing entrypoint,
command, user and workdir can only be replaced by the exact overrides above;
all effective values must be compared after create. Unsupported image Shell,
stop behavior, network behavior or labels must be explicitly rejected or
covered by a reviewed exact-value policy before launch. No automatic rebuild
or default relaxation is allowed in a job.

The container response must have one full lowercase 64-hex ID; its Name is
exactly slash plus the journaled name; Image equals the pinned config ID.
Config.Image is the original full config-ID argument. Path/Args must agree
with the exact bootstrap argv, not merely Config.Entrypoint/Cmd. Driver is
overlay2 and Platform linux for this profile. AppArmorProfile is docker-default,
RestartCount zero and ExecIDs empty. Preserve actual raw bytes and observations.

Mandatory Config checks include exact User, Hostname, empty Domainname,
Env, Cmd, Entrypoint, WorkingDir and Labels; stdin/stdout/stderr attached,
OpenStdin and StdinOnce true, Tty/ArgsEscaped false, no volumes/exposed ports,
and Healthcheck.Test exactly [NONE] with no enabled health behavior. Complete
field/type/null/omission rules must be frozen from the pinned API before coding
the validator; unknown fields never become silently ignored control settings.
Non-omitempty Config fields must be present. ArgsEscaped/NetworkDisabled may
be omitted or exactly false, never null or integer zero; StopSignal, Shell,
OnBuild and StopTimeout must be absent for the initial strict profile.
Healthcheck is exactly {Test:[NONE]} after rejecting image healthchecks.

Mandatory HostConfig checks include every resource, namespace, mount, security,
logging and lifecycle field, not a projection of the interesting handful.
Required values include NetworkMode=none, IpcMode=private, CgroupnsMode=private,
UsernsMode=host, PidMode/UTSMode empty, ReadonlyRootfs true, CapDrop=[ALL],
CapAdd empty, Privileged/AutoRemove/PublishAllPorts false, Init false,
RestartPolicy={Name:no,MaximumRetryCount:0}, LogConfig={Type:none,Config:{}},
Runtime=runc, the exact three SecurityOpt entries, exact memory/memory-swap/
CPU/PIDs/shm values, exact structured bind mounts and closed tmpfs map.

Reject extra Binds, volumes, devices/device requests/device rules, DNS overrides,
links, groups, host aliases, port bindings, cgroup parent/spec overrides,
CPU realtime/cpuset/shares/nanocpu overrides, block-I/O overrides, storage options,
sysctls, annotations, OOM-disable/score overrides and Windows-only configuration.
The explicit per-field handling of null/empty/default values remains a required
review item. Pinned normalization makes MemorySwappiness null, not the CLI's
input -1; OomKillDisable is false. Dns/DnsOptions/DnsSearch are exactly empty
arrays for this CLI. ContainerIDFile and Isolation are empty strings and
ConsoleSize is [0,0] for the actual piped CLI, not the user's terminal size.
Nonempty effective Ulimits initially fail unsupported: both inspect and runtime
construction merge daemon defaults. Requested empty Ulimits cannot prove no
effective rlimits, and even an empty effective list does not establish absence
of inherited OS limits. Actual bootstrap/inner limits still need observation.

The complete pinned HostConfig key universe is exactly the following69 names:

```text
CpuShares Memory NanoCpus CgroupParent BlkioWeight BlkioWeightDevice
BlkioDeviceReadBps BlkioDeviceWriteBps BlkioDeviceReadIOps BlkioDeviceWriteIOps
CpuPeriod CpuQuota CpuRealtimePeriod CpuRealtimeRuntime CpusetCpus CpusetMems
Devices DeviceCgroupRules DeviceRequests MemoryReservation MemorySwap
MemorySwappiness OomKillDisable PidsLimit Ulimits CpuCount CpuPercent
IOMaximumIOps IOMaximumBandwidth Binds ContainerIDFile LogConfig NetworkMode
PortBindings RestartPolicy AutoRemove VolumeDriver VolumesFrom ConsoleSize
Annotations CapAdd CapDrop CgroupnsMode Dns DnsOptions DnsSearch ExtraHosts
GroupAdd IpcMode Cgroup Links OomScoreAdj PidMode Privileged PublishAllPorts
ReadonlyRootfs SecurityOpt StorageOpt Tmpfs UTSMode UsernsMode ShmSize Sysctls
Runtime Isolation Mounts MaskedPaths ReadonlyPaths Init
```

Only Annotations, StorageOpt, Tmpfs, Sysctls, Runtime, Mounts and Init are
omitempty; this command sets Tmpfs/Runtime/Mounts/Init so they must be present,
whereas the initial strict command leaves Annotations/StorageOpt/Sysctls absent.
The other62 fields must exist even where a reviewed rule permits null/empty.
Reject a70th key. Close every nested field schema as well; a root allowlist
alone is insufficient. BindOptions uses the exact ReadOnlyForceRecursive key,
not a similarly named invented field; nonapplicable option objects are absent.

Compare the complete top-level Mounts inventory to the expected user binds;
also separately observe kernel mounts, including engine-created mounts that
do not appear there. NetworkSettings must contain only the none network and
no endpoint address, published port, alias, link or attached bridge. API1.52's
top-level NetworkSettings has only SandboxID, SandboxKey, Ports and Networks;
do not require removed legacy IP/bridge fields. Exact nested Engine API field
rules and created/running/exited variants remain to be frozen. Retain/refuse
actual daemon create warnings rather than accepting silently discarded limits.

These normalization rules come from the pinned
[daemon settings](https://github.com/moby/moby/blob/fbf3ed25f893e6ce21336f1101590e40a13934f4/daemon/daemon.go#L1768-L1773),
[Unix adaptation](https://github.com/moby/moby/blob/fbf3ed25f893e6ce21336f1101590e40a13934f4/daemon/daemon_unix.go#L403-L462),
[inspect ulimit merge](https://github.com/moby/moby/blob/fbf3ed25f893e6ce21336f1101590e40a13934f4/daemon/inspect.go#L93-L96),
[image configuration merge](https://github.com/moby/moby/blob/fbf3ed25f893e6ce21336f1101590e40a13934f4/daemon/commit.go#L25-L120),
and [versioned inspect projection](https://github.com/moby/moby/blob/fbf3ed25f893e6ce21336f1101590e40a13934f4/daemon/server/router/container/inspect.go#L48-L90).

## 6. Attached execution and evidence

Start is exactly `container start --attach --interactive <owned full ID>`.
Use non-TTY bytes: the CLI only applies its detach escape proxy in TTY mode.
Retain arbitrary binary stdin digest/count, actual EOF evidence, both output
streams and the true Docker-client ProcessOutcome. CLI stderr may contain
client diagnostics in addition to worker stderr; it is not pure inner stderr.
No Docker-client duration/exit/signal is relabeled as an observed Python one.

Bootstrap waits without reading stdin until exclusive durable release; the
parent's separate bounded observation/release loop is mandatory. Actual running
PID/start ticks, boot ID, cgroup identity, namespaces, limits, mount state,
zero capabilities, NNP, seccomp and AppArmor must corroborate inspect values.
Inspect success alone never releases input. A successful CLI write does not
prove inner consumption; validate the actual domain response/request binding
and correlate container exit/OOM state, deadlines and final cleanup evidence.

Create/start/release uncertainty is possibly executed. Only exact journaled
ownership permits reconciliation/kill/wait/remove; no list/prune/wildcard or
force-remove fallback. Parent source/work leases remain held through durable
finalization and all children. Unknown cleanup blocks reuse and admission.

## 7. Explicit remaining decisions and implementation TODOs

- [x] DP-01a: Confirm /dev and /dev/shm default-inode incompatibility from
  official kernel/Moby sources and record an explicit same-ceiling correction
  candidate in section 4.1. Root independently read the cited implementation.
- [ ] DP-01b: Independently approve the complete corrected mount/device policy;
  verify actual installed runtime and controlled non-TTY compatibility. Source
  inspection/candidate arithmetic is not measured enforcement or acceptance.
- [x] DP-02: Root reviewed/froze the exact closed renderer record, existing
  directory names, minimal root cover, fixed11 labels, reserved targets and
  count/byte caps above after independent corpus/schema reviews. Root allocates
  only tools/worker/runtime_docker_policy.py and
  tests/unit/test_runtime_docker_policy.py for the pure create renderer.
  The pure implementation and focused review checkpoint is recorded below;
  composed tests, normal hooks and canonical acceptance remain outstanding.
  Image/inspect validation and launch remain separately gated by DP-03/04/08.
- [ ] DP-03: Freeze every Config/HostConfig/NetworkSettings/Mounts field,
  container-state variant and unknown-field refusal; include daemon-injected
  defaults and ulimit behavior. Do not compare only selected safe-looking keys.
- [ ] DP-04: Freeze actual kernel mount inventory and writable pseudo-filesystem
  policy. Pinned Moby's default masks include host-dependent per-CPU thermal
  paths, so the observed historical 12-path list is not universally exhaustive.
- [ ] DP-05: Keep the domain profile file-only readonly bind, but require the
  installed image's destination parent to be real/nonsymlink, exactly0700 and
  owned by the container UID/GID. ALL container path ancestors must be real,
  nonsymlink and traversable; the file
  itself must satisfy the actual domain worker's stricter owner/mode/nlink/hash
  rules. The entire profile parent must be disjoint in both directions from
  every import root and invocation cwd. Do not bind the whole host metadata
  directory, chmod user files, or relax the existing verifier checks.
- [x] DP-06a: Independent scoped design/code review of the pure renderer, with
  root and corpus reading its complete source/tests and the corpus independently
  running its 288 focused tests. This does not approve runtime enforcement.
- [ ] DP-06b: Independently review and allocate the image/inspect validator
  separately. No Docker launch is enabled by an approved pure renderer.
- [ ] DP-07: Add N-1/N/N+1, duplicate/poisoned/CSV-path, image-extra, init-default,
  seccomp-file, credential-helper, mount-shadow, field-unknown and changed-state
  falsifiers; actual pinned-parser controls must accompany authored fixtures.
- [ ] DP-08: Separately implement bounded journal/outcome codecs, actual kernel
  readers, supervised bootstrap/controller/recovery and installed factory.
- [ ] DP-09: Review scoped trusted-tool runtime tests with exact targets and
  resources; prove binary stdin/EOF, output flooding, cancellation/OOM, limits,
  orphan/restart recovery and unchanged primary failure evidence. No scanned
  code, release/image publication or unrelated system mutation is authorized.
- [ ] DP-10: Required normal hooks, exact-head CI, canonical SUCCESS/APPROVE,
  composed-path integration and the full Black Hat acceptance/rehearsal gates.

This draft deliberately leaves unresolved decisions unchecked. Its source
inspection is useful implementation evidence, not a runtime acceptance report.

## 8. Local pure-renderer checkpoint — not Docker or launch acceptance

The only new implementation files are tools/worker/runtime_docker_policy.py
and tests/unit/test_runtime_docker_policy.py. At the frozen reviewed checkpoint:

- Source raw SHA-256:
  ee1d44eaa032b3078ed5d2f8b13537a0f441895e309578181860497eec5af629.
- Test raw SHA-256:
  efce66b6243afd0a919c73dc9f21ae6f4f466dffd5cdae7da11201455666ca29.
- Author's final configured focused run: 288 passed, zero skips/failures/errors,
  0.893s, /tmp/scanipy-docker-renderer-final.xml.
- Independent corpus run: 288 passed, zero skips/failures/errors, 0.75s,
  /tmp/scanipy-runtime-docker-policy-corpus-review.xml; complete contract,
  source and tests read with no blocking finding.
- Root independently read all 387 source and 735 test lines, then reran the
  configured focused suite: 288 passed, zero skips/failures/errors, 1.21s,
  /tmp/scanipy-docker-renderer-root-review.xml. Root approves this pure slice.
- Ruff/format and source strict mypy passed at the author's frozen checkpoint;
  git diff --check was clean. Root's explicit normal pre-commit run on the
  three authored renderer/source/test/contract files passed all applicable
  checks, including mypy and secret checks; irrelevant hooks skipped normally.
- After normal accepted-main integration a43927d04e052840ded6ad1fffbdfdfcaf29947e
  (main through #403), the configured combined pytest tests/ suite passed
  2,298 tests with 51 existing optional skips and zero failures/errors in
  160.34s, /tmp/scanipy-400-renderer-combined-full.xml. This includes the actual
  shared transport, inventory, loader and renderer sources together; the
  renderer source/test hashes above were independently rechecked unchanged.
  Normal final commit/push and exact-head remote gates remain pending.

The initial test collection failed because pytest attempted to format an
int-subclass poison fixture. Explicit diagnostic parameter IDs corrected the
harness; the subsequent initial 278-test and final 288-test runs passed. The
collection failure is not a product test pass or a suppressed falsifier.

Tests cover exact flags/labels/environments, shared FrozenInvocation, primitive
and missing-slot rejection, mutation-safe snapshots, component-wise overlap,
minimal nested-root cover, destination deduplication, all relevant count/byte
boundaries, escaping amplification and absence of external operations. CSV
round-trips use the authored Python grammar; they do NOT prove the pinned Go
parser, Docker daemon, image defaults, kernel mounts, device inventory, limits,
pipe behavior or current-host compatibility. No filesystem discovery, native
process, controller, installed key/anchor, image build or runtime activation is
introduced. DP-01b/03/04/05/06b/07/08/09/10 remain required.
