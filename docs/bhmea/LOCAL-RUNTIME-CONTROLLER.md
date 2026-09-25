# Local analysis runtime controller — design under review

Owner: root coordinator. Tracking: [#400](https://github.com/scanipy/scanipy/issues/400),
part of #362/R08/R15/R16. Status: independently reviewed architecture with the
clarifications below; exact implementation contract still pending. This is not
implementation, runtime permission, canonical approval or parent-task acceptance.

This closes a specific missing boundary: the shared process transport can bound
its own pipes and process group, but cannot enforce a Docker resource envelope,
network namespace or disposal of descendants that leave that process group.
Production use by #397/#399 and online acquisition by #398 needs a real outer
controller. Merely adding a caller-supplied `isolated=true` is not that boundary.

The owner's full submission remains the target. The first parser/verifier
profile is an implementation dependency, not a substitute for Joern, Semgrep,
CodeQL, online repository acquisition or the end-to-end API/UI workflow.

## 1. Actual observations and authority

The owner confirmed this development machine for the local Docker presentation.
The current coordinated stage record is in the root-owned handoff branch at
`docs/evidence/2026-09-25-stage-machine/`. Its 13:21 UTC sample had about 7.37 GiB
available RAM and nearly full swap, despite about 62.75 GiB total RAM. Recheck
headroom before heavy work; do not stop the user's workloads to obtain it.

Read-only September 25 checks additionally observed:

- Host UID 1000; Linux kernel `6.8.0-138-generic`.
- Docker client/Engine 29.1.3, Ubuntu build `29.1.3-0ubuntu3~22.04.2`;
  Engine API 1.52, minimum API 1.44.
- Docker uses the systemd cgroup driver, cgroup v2 and overlay2; reported
  security options include AppArmor, builtin seccomp and cgroup namespaces.
- The host exposes cpu, memory and pids cgroup controllers. That observation
  does not prove any particular container's enforced settings.
- The measured `/usr/bin/docker` SHA256 is
  `87bb910f051879cdf2a4a38e01748cbebeb27f3de962122dfdcbd0a4fbeea4ff`.
  An executable-file hash is not an attestation of its loaded dependency closure.

No new container, network, firewall, image, host service or user database was
changed for these observations. Existing Docker access is not permission to
alter daemon settings or unrelated objects. The first version targets this
observed Linux/cgroup-v2 environment; unsupported installations must be explicit
errors, not silently weaker isolation. Attendee-platform support remains R15 work.

## 2. Prefer an enforced parent boundary over a new trust protocol

The trusted controller owns the entire create/inspect/start/observe/stop
transaction through a fixed local Docker endpoint. Neither a scan request nor
a worker receives the Docker socket, host credentials or arbitrary Docker
arguments. A reviewed server/operator adapter calls the controller with one
closed profile and its real input/authority binding; no raw-command public API.

For this local deployment, a separate per-job signing hierarchy or Unix-socket
attestation protocol is not necessary if the same trusted controller creates
the exact container and admits only its own observed result. It must verify
the actual container configuration and kernel state, not trust worker JSON.
The optional channel design in #398 is therefore an alternative only if later
deployment separates the controlling and admitting principals. Do not implement
both architectures without a concrete need and a reviewed privilege boundary.

Worker scripts remain internal trusted analysis code. Direct invocation outside
this controller can at most be a declared controlled diagnostic; it cannot
produce an operational launch receipt or satisfy a caller's production adapter.
Production adapters use the installed controller factory and current admission
reader, never a deserialized controller/result object or a test fallback.

The Docker daemon, kernel, installed controller/runtime code and nonconcurrent
host administrator are trusted. This is not a proof against hostile host root,
daemon compromise, arbitrary kernel exploits or simultaneous tampering by a
privileged deployment writer. Input repositories remain untrusted data.

## 3. Closed profiles, not configurable commands

The initial design has two no-egress profiles: Python source-syntax parsing and
accepted-input verification. Their exact inner argv/env/byte/CPU/address-space
contracts stay owned by #397/#399. Import the actual shared types and transport;
do not copy those implementations or add a callback-based production runner.

An installed, read-only profile must bind at least:

- Profile/schema version and expected platform; actual local image config ID,
  with OCI/repository digest kept distinct and nullable if not established.
- Exact trusted entrypoint, interpreter, worker and import/dependency artifact
  identities; private empty Python bytecode-cache prefix and no ambient imports.
- Fixed container UID/GID, source/input destinations, readonly runtime/input
  mounts, writable scratch inventory and complete child environment.
- Explicit CPU, memory, no-extra-swap, PID, scratch-byte/inode, pipe-output,
  startup, analysis and cleanup bounds. These are ceilings pending measured
  stage acceptance, not assurances of achievable latency.
- Actual required namespace, capability, seccomp, AppArmor and mount policy.
  Missing controls or mismatched effective values are failure, not warnings.

Scan input cannot select an image/tag, endpoint/context, entrypoint, shell,
host path, environment key, bind mount, device, capability or policy override.
The controller must not pull/build an image during a job. Image preparation is
a separate reviewed operation; a mutable tag is not an installed profile identity.

Non-root execution, private PID/network/cgroup namespaces, read-only root,
all capabilities dropped, no-new-privileges, default reviewed seccomp/AppArmor,
no ports/devices/host namespaces, no restart policy and no automatic removal
are the proposed defaults. Exact engine acceptance must be tested, not assumed.

Use `--network none` for the initial profiles: it provides container-local
loopback, not absence of all sockets or proof that the parser cannot execute
source. Trusted-tool static-only arguments and sentinel tests remain mandatory.
[Docker none-network reference](https://github.com/docker/docs/blob/d511fb5636cfc41591a48365fde5126037ea66d6/content/manuals/engine/network/drivers/none.md).

Set memory and memory-swap to the same positive bound when no extra swap is
allowed; verify actual cgroup values. CPU shares are not a hard CPU quota and
`free` inside a container is not evidence of its swap entitlement.
[Docker resource reference](https://github.com/docker/docs/blob/d511fb5636cfc41591a48365fde5126037ea66d6/content/manuals/engine/containers/resource_constraints.md).

Bound scratch explicitly. Tmpfs bytes consume the memory allowance and disappear
on container stop; they cannot be the only retained evidence store. A writable
bind mount is not a hard byte quota merely because free space was checked.
No privileged/mount-capability fallback is permitted if the chosen storage
limit cannot be enforced.
[Docker tmpfs reference](https://github.com/docker/docs/blob/d511fb5636cfc41591a48365fde5126037ea66d6/content/manuals/engine/storage/tmpfs.md).

### 3.1 Initial runtime path namespace and prerequisites

Runtime-inventory v1 includes ABSOLUTE paths in its root-group and program
digests. The initial controller therefore uses exact identity-mapped readonly
runtime binds: each installed host path equals its container destination.
Inspect the actual source, destination, read-only state and complete mount set;
reject overlays, unexpected anonymous volumes and hidden writable submounts.
All metadata/control directories remain outside every inventoried runtime root.
Installation must make the selected non-root container UID able to read the
exact private metadata under the existing domain worker's ownership/mode rules;
do not relax those rules or make metadata world-readable to fix a mismatch.

This is an initial engineering choice, not a claim that runtime files are
already installed or mounted. Image-native relocated runtimes require a separately
reviewed dual-namespace mapping or trusted pre-input measurement in the container
namespace. Never rename an inventory and retain its old identity. Identical
interpreter bytes can still load different image-native libraries: retain the
observed image config ID separately and do not call file measurement a complete
ELF-loader or image attestation. Writable scratch paths have their explicitly
declared container namespace; they are not inventoried host runtime paths.

Launch prerequisites are profile/mode-specific, avoiding verifier circularity:

- Verifier publication-preflight: authenticated operator, installed verifier
  trust/runtime and current publication/admission expectations. It cannot require
  a published bundle, detector-run or capture lease that does not exist yet.
- Verifier historical: authenticated auditor and installed verifier trust/runtime,
  with exact retained historical material. Revocation must not make historical
  audit impossible; successful historical verification grants no current launch.
- Verifier execution: exact live work/fence/capture-lease reads and the verifier
  trust/runtime. Do not require this same verifier's successful cryptographic
  result as a prerequisite for invoking it.
- Parser/native detector execution: the actual accepted-input authorization,
  immutable source/lease and current work/fence checks required by its domain.

These checks belong to installed trusted adapters, never request-supplied
callbacks or booleans. Missing real adapters still block operational launch.

## 4. Proposed gated launch and output retention

The lifecycle must preserve the shared transport's finite-input/no-callback
contract while verifying the container before it consumes untrusted input:

1. Validate/freeze installed profile and exact bounded request. Obtain actual
   mode-specific authority/source-lease checks from their owning adapters; missing production
   integration refuses launch. Allocate an exclusive controller-owned attempt.
   Durably journal its reserved exact unique container name and intended
   configuration BEFORE asking Docker to create anything. Recovery must handle
   a daemon-created container whose client timed out before returning/persisting
   the full ID: exact-name lookup must corroborate the retained attempt, labels,
   image and complete configuration. Never adopt a name match alone.
2. Create one uniquely named container with a fixed trusted bootstrap, closed
   readonly control/input mounts, bounded scratch and no daemon log persistence.
   Retain its full actual ID and configuration. Never resolve ownership by a
   broad name, label filter alone or a caller-supplied container ID.
3. Inspect the created configuration; reject extra mounts, inherited image
   environment, declared anonymous volumes, hooks/healthchecks or other settings
   outside the profile. Profiles must explicitly account for image defaults.
4. Start attached with finite stdin through the actual shared transport. The
   trusted bootstrap waits for a bounded controller-created release record before
   reading untrusted stdin. It emits no domain success while waiting.
5. The parent observes the running container's actual PID/cgroup/netns/mount and
   security state, verifies identity and limits, rechecks current authority, then
   publishes the exact release record on the private readonly-to-worker control
   mount. The source/API cannot write that directory. Define this schema before
   code; a request-provided file or bare boolean is not a release record. Bind
   unique attempt and actual full container IDs, exact inner protocol/argv/env,
   profile/inventory/program and input identities, plus the mode-specific current
   authority, epoch/fence and expiry. The bootstrap compares a fixed schema with
   trusted launch metadata, never expectations supplied by the scanned source.
   Bind the CONTROL DIRECTORY read-only, so exclusive atomic release publication
   is visible; a bind of a replaceable individual file is insufficient. Journal
   release intent and outcome, publish exclusively and reject stale/reused releases.
   Ambiguous start/release acknowledgement means possibly executed: stop and
   reconcile the attempt; do not replay its release or pretend it never ran.
   Revocation or lease expiry between inspection and release blocks the job.
6. Capture exact bounded stdout/stderr and transport failure evidence. Do not
   allow Docker's logging driver to write an unbounded second copy. Correlate
   process outcomes with the actual container's exit/OOM state and profile.
7. On every terminal/error/cancel path, stop only this owned container, verify
   actual termination/descendant disposal, including the exact owned cgroup's
   empty/termination evidence, and retain it before releasing source/authority
   leases. Unknown cleanup remains durable orphan quarantine. Killing
   the Docker client alone does not prove the container stopped.
8. Only after complete output validation, kernel/container checks, authority
   recheck and cleanup may the domain adapter admit the result. A successful
   Docker CLI exit is not an accepted parser/verifier result or scan completion.

Kernel observations must refer to the same container/PID start identity before
and after inspection; a reused numeric PID or changed cgroup/mount identity
cannot satisfy the check. Observed seccomp mode/AppArmor label is not proof of
the full installed rule bytes: retain the distinct trusted daemon/profile
binding, and do not call mode/label equality a complete policy measurement.

Docker CLI v29.1.3's source attaches streams before starting the container and
then waits for the container exit code. This supports step 4's design, but does
not attest the installed Ubuntu binary or replace a controlled runtime test.
[Pinned start implementation](https://github.com/docker/cli/blob/v29.1.3/cli/command/container/start.go).

The parent may coordinate one bounded transport thread with its own bounded
inspection/release loop; no arbitrary user callback enters the transport. Exact
deadlines, failure joins, thread disposal and release-before-start races require
an implementation contract and falsifiers before coding. Reserve explicit time
for inspection, final evidence and container cleanup; do not silently spend an
inner worker's whole analysis deadline on Docker startup. Bound cumulative
controller/Docker-CLI call counts, retained bytes and elapsed time, not each
inspection in isolation. A blocked/surviving transport thread is incomplete;
do not admit a result or reuse its source/authority lease.

Host/daemon failure or an uninterruptible kernel call can prevent prompt cleanup.
Persist an incomplete/orphan state, never fabricate known termination. Before
new work or lease reuse, reconcile exact owned executions and block admission
if cleanup is unknown. A production restart/reaper mechanism is required; an
in-memory timer or a future administrator action alone is not that mechanism.
Normal timeout/cancellation must be proved to dispose setsid/double-fork
descendants inside the actual container without running target source as a test.

## 5. Required extensions remain on the full critical path

- Joern parse/export and Semgrep need their actual approved invocation/tool
  closures, immutable same-source mounts, persisted artifacts, exact coverage,
  real runtime packaging and output retention. Extend the controller profile
  only after these domain contracts are reviewed; do not route through a shell.
- CodeQL setup must preserve R16's no-target-build constraint and have its own
  concrete allowed modes. A generally functioning Docker launcher does not
  establish safe static-only database creation or query coverage.
- Online GitHub acquisition needs independently enforced destination egress,
  TLS hostname/CA identity and no DNS/proxy/metadata/private-address fallback.
  Keep it disabled until real firewall/netns enforcement and negative controls
  pass. Do not reconfigure the host's unrelated firewall/networks for a job.
- Large raw Git/CPG output needs a separately bounded aggregate retention and
  scratch design. Do not discard raw successful evidence or let an ordinary
  bind mount evade storage quotas. The parser/verifier pipe profile is not
  a claim that the larger native profiles already work.
- The API/queue, occurrence store, accepted-input authority, source leases and
  final provenance still need actual integration. Controlled runtime tests must
  be labeled as such and cannot mint production run/capture/authorization IDs.
- Attendee install and two offline stage rehearsals remain separate gates.
  All required images/fixtures/specs/keys must be available before offline runs.

## 6. Next actions and proposed ownership

- [x] Independent schema/security review accepted the trusted-parent architecture
  within its stated threat model, without a second signing/channel hierarchy.
  Root incorporated the required mode-specific verifier prerequisites, exact
  path-namespace, directory-release and ambiguous-launch/cleanup clarifications.
  This is architecture review only, not a claim that any control has been tested.
- [ ] Specify exact profile/request/release/evidence/result/failure schemas and
  count/byte/time limits, actual Docker/kernel observations, lifecycle/recovery
  transitions and the initial exact file allocation before implementation.
- [ ] Verify image-default handling, stdin/attach behavior, no-log output bounds,
  cgroup/mount inspection and private control-directory permissions against
  pinned implementation behavior. No guesses based solely on flag names.
- [ ] Add hermetic lifecycle/configuration/error falsifiers, then normal hooks
  and independent code review. Missing controls must fail before domain work.
- [ ] Build/review a real fixed runtime profile only after dependency and resource
  checks; perform explicitly scoped trusted-tool runtime tests, including OOM,
  output flooding, stdin closure, cancellation, escaped process groups and
  controller restart. Never execute scanned repository code as a positive control.
- [ ] Pass required exact-head CI and successful canonical APPROVE before merge,
  then re-test the merged artifact and the real Compose/worker path.

Root owns this controller design and the adjacent shared runtime-file inventory
slice. The latter is separately implemented at local commit `9b8ec51f` with 73
focused checks and scoped peer review; it is not a controller or installation
loader. No Dockerfile, domain worker, DB schema or running system is changed by
this controller draft. Further controller file allocation and runtime activation
require explicit reviewed engineering contracts; release publication and external
actions retain owner authority.
