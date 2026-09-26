# Local runtime evidence store and journal — proposed concrete contract

Status: **Root/peer-reviewed wire and replay design; pure API addendum pending.**
Owner: root coordinator, #400 under #362. Authoring allocation: schema/ingestion
agent, documentation only, 2026-09-25. The original proposal was authored
outside the repository against the unchanged frozen
`d51c5f33a0c929bd95be9107a1b46f73b5690652` combined tree.
It creates no store, event, profile, key, process, container or database state.
No TODO below is accepted merely because a shape or method is specified.

Read with [PROCESS-EVIDENCE.md](PROCESS-EVIDENCE.md),
[LOCAL-RUNTIME-PROFILE.md](LOCAL-RUNTIME-PROFILE.md),
[LOCAL-RUNTIME-CONTROLLER.md](LOCAL-RUNTIME-CONTROLLER.md), and the actual
occurrence-persistence and accepted-input resolver contracts in their owned
branches. PE's locally reviewed codec remains unchanged. Its `Prepared*` values
are not durable receipts; this proposal supplies the missing boundary, not a
second transport or authority hierarchy. R07/R08/R15/R16 and full Black Hat
functionality remain open.

## 1. Guarantees and deliberately separate authorities

The proposed store owns one bounded, private, append-only attempt history:
actual immutable request/input/metadata bytes; intended and observed calls;
actual bounded output and lossy error diagnostics; state transitions; and
cleanup/admission observations. It acknowledges a write only after exclusive
publication, file/directory fsync and independent readback.

This establishes local byte custody and checked history relative to an actual
protected filesystem root. It does **not** establish:

- Authentication, current registry acceptance, execution authorization or a
  still-live DB work/capture lease. Those remain actual installed adapters.
- That a caller-constructed outcome came from Docker, that a CLI's zero exit
  means domain success, or that killing the client terminated its container.
- A signature, external rollback-resistant journal head, SCM authenticity,
  native static-only behavior, or correctness of an accepted semantic model.
- Atomicity across filesystem, Docker and PostgreSQL. Each ambiguous boundary
  is retained and reconciled; it is never called an exactly-once launch.

Trust is the reviewed installed parent/controller, kernel, local filesystem,
Docker daemon and nonconcurrent host administrator. Scanner input and API/ranker
principals cannot supply a store instance, root, clock, callback, append method,
mode switch or recovery target. Same-UID hostile Python execution, compromised
host root or simultaneous privileged tampering is outside this boundary, not
prevented by frozen dataclasses or file hashes.

The low-level store is callback-free. It verifies supplied installation data
and actual held filesystem objects; it cannot authenticate the provenance or
currentness of an arbitrary constructor argument. Only the installed factory
selects it. Factory composition and its startup/current-anchor rereads remain
mandatory before create, release and admission.

## 2. Exact versions, primitives and stored classes

Use PE's canonical JSON rules and **actual** `CliOperation`,
`RuntimeCallBinding`, `EvidenceBlob`, `PreparedCallIntent`, `PreparedCallResult`,
`Stored*` views, `FrozenInvocation`, `ProcessOutcome` and `ProcessTransportError`.
Do not copy them. Source/error/path objects are snapshotted without instance
callbacks, including on re-consumption of a receipt.

`H`, `UUID`, `UtcInstant`, `AbsolutePath`, `Mode`, `Phase`, `FailureCode`,
`BlobRef`, `MetadataRef` and kernel/file/socket observations keep the profile's
exact meanings. Event digests are `D(schema, raw canonical event bytes)`;
blob digests are raw SHA256. No artifact contains its own hash or a future
event digest. Blob keys are exactly `blobs/` plus H, never external paths.

New coordination IDs are actual random UUIDs allocated by this installed
service; they denote local storage operations, not authenticated principals.
IDs observed from Docker/kernel/DB are never generated to fill missing facts.

Initial platform: Linux, CPython 3.11/3.12, a local filesystem supporting
nofollow directory-relative access, hard links, advisory `flock`, file and
directory fsync, and allocation reservation. NFS/FUSE/network filesystems,
unsupported primitives and filesystems with uncertain durability fail closed.
An installed filesystem type/mount is an operator choice requiring tests; a
successful call to `fsync` is not a power-loss guarantee on every device.

## 3. Installed root and bounded constructor

Proposed module `tools.worker.runtime_evidence`; no domain/DB/Docker imports.
Its internal constructor is only used by the installed factory, never exposed
as an HTTP/queue/CLI selector. Exact constructor data:

```text
RuntimeEvidenceInstallation(
 deployment_id:UUID, store_id:UUID,
 artifact_domain:"operational"|"diagnostic",
 evidence_root:PosixPath, host_work_root:PosixPath,
 owner_uid:int, owner_gid:int,
 root_record_sha256:bytes32)

open_runtime_evidence(installation:RuntimeEvidenceInstallation)
    -> RuntimeEvidenceRoot
```

All fields are privately primitive-snapshotted before filesystem access.
Actual nonroot effective UID/GID must equal the declared owner, range
1..2147483647. Paths satisfy the outer profile's normalized 4096-byte domain,
are disjoint, and are selected from actual independently installed runtime
configuration. No environment/root discovery, `resolve`, glob, user-home lookup
or automatic creation/adoption of an unknown store.

`root.json` is an already installed, immutable canonical file (4096 bytes,
depth2, 32 key-inclusive values):

```text
{schema:"scanipy-runtime-evidence-root/1",deployment_id:UUID,store_id:UUID,
 artifact_domain:"operational"|"diagnostic",owner_uid:int,owner_gid:int,
 evidence_root:AbsolutePath,host_work_root:AbsolutePath,
 format:"scanipy-runtime-journal/1"}
```

It must match the independently supplied raw hash and all constructor fields.
It does not authenticate those supplied pins. The explicit installation utility
which creates/pins this root is separate, operator-authorized work; ordinary
open cannot bootstrap a missing root or choose the highest record it finds.
Diagnostic roots have distinct IDs/paths and use diagnostic event schemas;
an operational open refuses them. There is no request-selected test flag.

Open starts an internal monotonic deadline before filesystem work, with no
caller clock. Walk parents using `O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC`; permit
root/owner ancestors without group/other write, except literal root-owned
sticky `/tmp`. Both direct roots are owner UID/GID, exactly0700. Regular
installed metadata is one link, exact0400/0600, opened O_NONBLOCK|O_NOFOLLOW.
Require the expected device/inode/type/owner/mode at each recheck. Never chmod,
chown or repair a foreign object to pass validation.

Hold the evidence-root and host-work-root descriptors for store lifetime.
Open fixed `writer.lock` through the held root (regular, one link, owner,
0600); take a nonblocking exclusive flock with a bounded retry deadline.
One writer process owns this lock for its whole lifetime. An internal bounded
thread lock serializes this process's appends while an attached transport can
run concurrently. No external lock/clock/append callback is accepted. A second
writer fails/queues without launching work, including in the same process.

Read-only auditing uses a separate fixed `open_runtime_evidence_reader` entry
point with the same root checks, bounded immutable reads and no writes/launches.
Its snapshot may end at a verified complete **visible** prefix; it never supplies
a durability receipt, admission or concurrency-slot release. A final name and
stable nlink1 can be visible before the writer's last directory fsync/ack, so
readback alone cannot prove that publication checkpoint. It retries a bounded
concurrently advancing suffix or returns unstable-read, not mixed history.

Initial bounds: constructor/recovery pass35000ms cooperative, at most128 held
FDs including descendants, at most512 root/ancestor/file observations per
steady append,4096 per whole-attempt read/replay and131072 per root recovery
pass. These are cumulative counts, not per-file resets. Read one bounded object
at a time rather than holding all256 blob descriptors. Use64KiB read/write chunks,
relative name at most128 ASCII
bytes. Every operation uses the remaining controller deadline; no sequence of
store methods resets the outer30-second launch allowance. The installed parent
supplies its actual same-process monotonic start/deadline scalars at reservation,
not a callable clock; the store checks their fixed30-second relation and uses
its own monotonic reads. It does not attest those scalars' provenance. No source
or API request can select them. An individual steady
state append/readback is bounded at2000ms; recovery has its separate35-second
budget because it cannot authorize a new launch. Blocking kernel fsync/read
still needs the outer host supervisor and durable recovery procedure.

## 4. Exact private layout and immutable membership

```text
evidence_root/
  root.json
  writer.lock
  attempts/<attempt UUID>/
    manifest.json
    events/<six-digit sequence>.json
    blobs/<64 lowercase hex>
    spool-registrations/<call UUID>.json
    staging/<publication UUID>.json
    staging/<publication UUID>.data
  refusals/<refusal UUID>/refusal.json
  refusals/<refusal UUID>/blobs/<64 lowercase hex>
  refusals/<refusal UUID>/staging/<publication UUID>.json|.data
host_work_root/<attempt UUID>/
  cli-home/ cli-tmp/ cli-bin/ docker-config/ control/
  call-spools/<call UUID>/stdout.bin|stderr.bin
```

All created directories0700; active staging files0600; published immutable
files0400, regular, one link after completed publication. Close mode transitions
are performed only on newly created owned descriptors, never inherited objects.
No symlinks, devices, sockets, FIFOs, xattr-based authority, user filenames or
unregistered siblings. A lock file and in-progress hard-link publication are
the only explicitly nonimmutable objects below the evidence root.

Attempt directory name is a fresh actual installed-service-generated UUID; it is not reused
after failure, cleanup, restore or identical input. Initial APIs have no delete,
truncate, overwrite, recursive cleanup or history GC. Retention administration
needs a separate reviewed policy; successful runtime cleanup does not delete
evidence. Unknown directory/file names are quarantined as corruption, not
silently removed/adopted. A bounded root inventory is required before serving
new work; cap256 retained attempts/refusals and16384 directory entries in this
first installation. At the cap, explicit storage administration is required;
do not silently drop history or scan an unbounded directory.

Attempt `manifest.json` (16384 bytes, depth6, 256 values) is immutable:

```text
{schema:"scanipy-runtime-attempt-manifest/1",store_id:UUID,
 deployment_id:UUID,attempt_id:UUID,operation_id:UUID,mode:Mode,
 artifact_domain:"operational"|"diagnostic",created_at:UtcInstant,
 origin_host_boot_id:UUID,origin_writer_id:UUID,request:BlobRef,input:BlobRef,
 launch:BlobRef,initial_prerequisite:BlobRef,
 authority_inventory:BlobRef,parent_barrier:BlobRef|null,
 installation_id:UUID,installation_generation:positive int64,
 installation_sha256:H,controller_profile_sha256:H,domain_profile_sha256:H,
 inventory_sha256:H,inventory_digest:H,program_digest:H,
 expected_image_config_id:ImageId,expected_oci_manifest_digest:ImageId|null,
 container_name:Text,metadata:[MetadataRef x4],
 quota_plan:QuotaPlan}
```

`container_name` is exactly profile-derived; all repeated identities match
actual loaded metadata/request/launch bytes. `metadata` order is installation,
controller-profile, domain-profile, inventory, with original origins and actual
observations. Raw metadata files remain separate exact blobs. No caller-made
loaded record suffices: factory rereads its actual anchor, invokes real loader
and owning domain codecs, then invokes the store through installed composition.

`authority_inventory` is a bounded canonical inventory, not an authority grant:

```text
{schema:"scanipy-runtime-prerequisite-evidence/1",prerequisite:BlobRef,
 objects:[{role:Role,bytes:BlobRef},...]}
Role = authentication | scope | admission | execution-authorization |
       capture-lease | content-verification
```

Order is exactly that list with only mode-required rows present, no duplicates.
Every BlobRef's size and **raw SHA256** bind its exact retained bytes. That
raw integrity check is separate from the following six role-specific links:

| Inventory role | Link to the prerequisite | First pure journal slice |
|---|---|---|
| authentication | `authentication_evidence_sha256` equals the raw BlobRef SHA256 | Enforce equality, required presence and byte/role limits |
| scope | `scope_evidence_sha256` equals the raw BlobRef SHA256 | Enforce equality, required presence and byte/role limits |
| admission | Link through the actual `AdmissionExpectation` and its owning checkpoint/policy evidence codecs; there is no `admission_evidence_sha256` field | Enforce mode-required presence, role/size/raw integrity only; retain the expectation and packet as explicit opaque-owner obligations |
| execution-authorization | The owner's actual `EXECUTION` schema-domain digest of the raw packet equals `execution_authorization_digest` and the real execution/ledger binding | Enforce mode-required presence, role/size/raw integrity only; preserve the declared domain digest and opaque packet without comparing it to raw SHA256 |
| capture-lease | `capture_lease_evidence_sha256` equals the raw BlobRef SHA256 | Enforce equality, required presence and byte/role limits |
| content-verification | `content_verification_evidence_sha256` equals the raw BlobRef SHA256 | Enforce equality, required presence and byte/role limits |

The two owner-dependent links are not interchangeable with an arbitrary
hash of their bytes. The real accepted-input verifier already decodes its
`EXECUTION` document and computes that owning domain digest before comparing
the ledger and execution binding. The journal must not copy that codec or
guess its schema-domain literal. Admission's exact packet-to-expectation
checkpoint/policy linkage is still an unresolved adapter contract, not a new
synthetic hash field. The full store/controller must integrate the actual
owning codecs and complete both links before launch; missing integration is
unavailable, with no caller-supplied callback or accepted flag.

The owning adapters also verify original schemas, provenance and currentness;
local raw equality alone proves none of those. Missing
auth/capture records cannot be replaced by hashes of arbitrary fixture strings.
This initial inventory has at most6 rows,16384 bytes/depth6/256 values, and all
raw objects together at most1MiB. If real authentication evidence cannot fit,
the profile is unavailable pending review, not silently truncated.

Every subsequent fresh prerequisite has its own exact inventory closure, not
the initial inventory reused as an implicit explanation of changed hashes.
Use the closed `PrerequisiteRef={prerequisite:BlobRef,authority_inventory:BlobRef}`
in every later create/observation/release/admission payload. The inventory's
prerequisite ref must equal the first member. Apply the exact six-role linkage
table above to every fresh inventory; never compare a domain digest with a raw
BlobRef SHA256 or invent a missing admission hash field. A new lease,
authorization, authentication or admission observation requires its actual new
bytes and corresponding inventory; no undocumented hash-to-path traversal.
An unchanged inventory may be physically deduplicated but remains role-checked
and logically charged for the new observation. Release packet fields containing
a prerequisite hash bind `PrerequisiteRef.prerequisite.sha256`, not the inventory.

The manifest has no event-head digest. Event1 references its raw BlobRef via
the revised `reserved` payload, so references point backwards, never cyclically.
The store reads the fixed manifest path and its matching retained bytes; it does
not accept a manifest selected by an API request. No mutable `latest.json` is
authoritative. Optional indexes are disposable derived caches and cannot bypass
complete bounded event replay/cross-blob validation.

## 5. Quotas and actual reservation

Keep the existing ceilings:32MiB retained attempt bytes,512KiB logical summary
metadata,4MiB cumulative non-attached output work,1MiB kernel raw bytes,
16 CLI slots,16 kernel samples, plus exact smaller mode input/output caps.
No identical-content discount applies to observed/retained stream work, metadata
work, call slots or role-specific caps. Only physically deduplicated identical
byte blobs save storage under the32MiB retention allowance. A manifest/event
copy stored at a second path still consumes its actual physical bytes; merely
having an equal hash does not discount another allocated file.

**Proposed clarification for root approval:** raw installed metadata/inventory
and raw domain/authority packets belong to the32MiB raw-artifact pool; their
small reference/observation summaries belong to512KiB. Otherwise the already
permitted8MiB inventory contradicts the512KiB summary ceiling. This does not
exclude invocation/error/path/result/event JSON from the512KiB PE workload.
Initial immutable request/manifest/registration/publication-control JSON also
counts as summary metadata. Never classify a large invocation as raw output
merely to evade the summary cap.

Root has tentatively accepted this classification as an engineering direction;
it is not acceptance of a physical installation or an increased limit.

Keep five accounting domains distinct:

1. Retained payload is the sum of actual immutable file lengths by unique
   `(device,inode)`. A known staging/final hard-link pair is one inode; equal-hash
   separate files are two. Block allocation/rounding remains an additional
   physical check, not hidden by this byte sum.
2. Logical metadata and role work count each new call/observation/publication
   occurrence, even if it references previously retained identical bytes.
   Exact replay is not a second logical event. Readback/hash passes are not new
   metadata records. Publication-control bytes count once for the corresponding
   logical publication, with the format's conservative maximum control length
   reserved up front; retry I/O does not create new logical credits. Recovery
   charges bounded unknown stages pessimistically until their exact status is
   established. The fixed reservation is recomputable from retained records,
   their role inventory and bounded unresolved stages, not a lost mutable counter.
3. Stream work sums actual observed and retained counts separately per call,
   without dedup discounts. A returned over-limit count remains honest evidence;
   it prohibits further productive work and is never clamped to fit a cap.
4. Transient peak includes committed evidence, both spool and copied-blob
   inodes, unpublished/abandoned staging, registration/control files, hard-link
   membership and any preallocation/reservation extents. It is not merely the
   currently reachable blob set. Charge before allocation; unknown ownership
   or publication keeps the pessimistic reservation.
5. Operational I/O counts bytes actually read, written and hashed, including
   failed/retried reads, unchanged duplicate content and full-closure checking.
   These are separate bounded-work counters, not retained storage or logical
   metadata. They cannot be used to extend wall deadlines or admit a result.

Closed work ceilings for the first proposal (each independent, bytes):

| Scope | Read | Write | Hash |
|---|---:|---:|---:|
| One steady store method | 134217728 | 67108864 | 268435456 |
| One whole-attempt read/replay | 134217728 | 0 | 268435456 |
| One live attempt handle, cumulative normal/retry work | 8589934592 | 268435456 | 17179869184 |
| One root open/recovery pass, cumulative across all histories | 17179869184 | 67108864 | 34359738368 |

Hash counts every byte fed to any hash, even if an input was already read or
hashed earlier. EOF probes count actual returned bytes; admission of each
bounded read/write/hash chunk happens before the operation. Metadata/FD/name
observation counts and2s/35s deadlines remain independent tighter limits.
These work ceilings do not allocate corresponding RAM or disk and do not
increase32MiB retained/64MiB proposed transient caps. Exhaustion causes a typed
limit and recovery barrier, not silent partial verification. A whole root of
large histories might not fit35s; installation compatibility must be tested,
not assumed from its byte ceiling.

Counters reset only on a new root open or new attempt-handle allocation, never
per blob, recursive edge or retry. Any unfinished attempt reopened by a new
writer first enters durable recovery-only under section7; it cannot obtain a
new productive budget. A reader's bounded read has no launch authority.
Automatic unbounded supervisor reopen loops are not provided by this store.

Closed `QuotaPlan`:

```text
{retained_bytes:33554432,metadata_bytes:524288,
 nonattached_output_bytes:4194304,kernel_bytes:1048576,
 cli_calls:16,kernel_samples:16,
 cleanup_cli_slots:4,cleanup_metadata_bytes:131072,
 cleanup_retained_bytes:2097152,terminal_metadata_bytes:65536}
```

The cleanup/terminal reservations are partitions of, not additions to, the
existing maxima. They cover a bounded exact-ID inspect/kill/wait/remove path,
its call/error records, a cleanup event and a failed/orphaned terminal record.
If a particular installed path/argv/observation maximum cannot fit these
reservations, preflight refuses with `limit` before create. Do not weaken the
record shapes or enlarge a runtime limit to force compatibility.

Before any side effect, the controller supplies its fixed planned operations
and known exact invocations to a store reservation calculation. The store
accounts the exact canonical intent/invocation size plus bounded result/error/
event and role-specific output maxima. Dynamic container IDs have fixed64-hex
width. Actual renderer/operation planners remain required: an arbitrary caller
estimate is not a reservation. The plan must leave cleanup and terminal pools
untouched by ordinary preflight/inspection/execution work. A call cannot launch
if its slot or worst-case retention reservation cannot be made.

Reservation is real local accounting under the writer lock, retained in
manifest/events and recomputed on restart, plus an actual capacity reservation
on the installed bounded evidence/work filesystem. Merely checking free space
or recording `reserved=true` is insufficient. The conditional dedicated-volume
model in section5.1 replaces the earlier speculative dummy-reservation-file
transfer. There is **no allocate/free/write transfer** and no guarantee imported
from `posix_fallocate` on a different inode or range. Filesystems lacking a
qualified reservation/metadata/work-isolation model remain unavailable. No mount,
project quota, volume or disk allocation is authorized by this document.

At most128 events and256 distinct blobs per attempt. At most16 registration
records and16 live staged publications. Initial implementation serializes one
publication at a time, so the larger bound is only for recovery residues, not
permission for concurrent unbounded writes. In-progress temporary/spool copies
must be charged too; proposed transient disk bound64MiB per attempt, including
the32MiB retained ceiling, requires root/installation approval. This is not
additional retained evidence or container scratch allowance.

Before writes, validate exact record/byte/count limits, then reserve credits.
Charge full read/write/hash/EOF work even for duplicate bytes. Release unused
reservation only after a write is proven not published or its committed outcome
is read back. Unknown publication holds the reservation. Successful exact replay
does not consume another event/call slot, but its bounded reread still costs I/O
budget. Any quota violation is a retained failure if the emergency reserve can
be used; inability to retain it is itself a fatal evidence failure and durable
startup quarantine, never fake successful absence.

### 5.1 Conditional capacity installation proposal — not yet qualified

Root and peer prefer a dedicated fixed-capacity, exclusively controlled local
filesystem for this file-per-artifact and O_EXCL-spool design. This is an
engineering direction, **not approval of a particular filesystem, arithmetic
split, installation or current host configuration**. In particular, no plausible
48/16MiB split or metadata/inode constant is frozen without the actual planner
and an independently reviewed worst-case allocation model.

The underlying storage must be either a dedicated fully allocated block device,
or an exclusively held, fully allocated, non-CoW backing file of fixed length
on a qualified backing filesystem/device. Every layer matters: no sparse holes,
thin/unreserved backing, reflink/dedup sharing, snapshot growth allocation,
compression, overlay copy-up or discard/hole-punch reclaim may create a hidden
future-space obligation. This includes hypervisor/virtual-disk backing; a VMware
guest's file or device alone cannot attest thick host-side allocation. The
operator must supply independently verified backing-stack evidence. Unknown
stack properties leave capacity unqualified, not inferred from `st_blocks`.

The installer creates and fully initializes the fixed filesystem, inode tables,
journal and root layout before use, with no lazy allocation task consuming an
unaccounted reserve later. The candidate is pinned ext4 on a specified kernel/
e2fsprogs/feature-mask/block-size/mount-policy combination, barriers honored by
the device stack, no runtime resize/discard and no foreign writer. These exact
versions/options and bounded verification method remain installation choices.
`data=ordered` still needs explicit file/directory fsync; journal metadata
consistency is not equivalent to this application's atomic receipt protocol.
[Kernel ext4 journal documentation](https://docs.kernel.org/filesystems/ext4/journal.html),
[ext4 mount and initialization behavior](https://docs.kernel.org/admin-guide/ext4.html).

Freeze a qualified ledger using actual measured installation constants, not
free-space samples supplied by a request. Let:

```text
B                  = pinned filesystem block size, bytes
S                  = ceil(67108864 / B), proposed full slot blocks
F_total, I_total    = measured fixed filesystem blocks and inode capacity
F_static, I_static  = fully allocated installation/journal/root metadata
F_global, I_global = conservative permanent global recovery/FS headroom
I_slot             = qualified maximum additional inodes for one full slot
E_static, E_global = fixed installation names and permanent recovery name reserve
E_slot             = qualified maximum evidence/work names for one full slot
N                  = min(256,
                         floor((F_total-F_static-F_global)/S),
                         floor((I_total-I_static-I_global)/I_slot),
                         floor((16384-E_static-E_global)/E_slot))
```

All counts are exact bounded nonnegative integers; B, S, I_slot and E_slot are
strictly positive before division. Undefined/negative/zero usable capacity
refuses service. E_slot counts both names of a hard-link publication, all
registered directories and unexplained bounded residues; it cannot be inferred
from inode count alone. `F_static` includes fixed ext4 journal,
bitmaps/inode tables and known installed files; `F_global` is a separate fixed
unspendable installation reserve, not a hidden per-attempt cap increase.
Unprivileged allocator-inaccessible reserved blocks are excluded from usable
capacity rather than promised to the nonroot store. Kernel-reserved allocation
behavior also belongs in the qualified model, not an assumption that every
`statvfs` free block is usable.

For every admissible branch of the actual mode/16-call planner, prove:

```text
peak evidence payload + work/spool payload + rounded tails
  + dynamic directory/extent/xattr/quota metadata
  + all still-owned abandoned/staging/reservation extents
    <= 67108864 bytes

peak distinct evidence/work/stage/directory/auxiliary inodes <= I_slot
retained immutable payload <= 33554432 bytes
logical summary metadata <= 524288 bytes
```

Both copies of spool-to-blob retention count. Hard-linked names share one inode
but their directory entries/metadata still cost blocks. Known hash equality
never merges separately allocated inodes. Account explicit filesystem rounding,
extent-tree/directory growth, journal/global headroom, unsuccessful/ambiguous
publications, and final cleanup/refusal/control records. `I_slot`, metadata
functions and permissible path/operation variants must come from pinned-source
analysis plus worst-bound task-private tests; an unexplained percentage or
one successful sample is not the required proof. If any currently proposed
branch cannot fit, that profile is unavailable pending an explicit new design;
do not raise32/64MiB, silently omit evidence or invent a smaller actual output.

The permanent-allocation protocol is finite:

1. Installer records the actual fixed layout/backing identity and qualified
   block/inode model in protected configuration. Only its bounded installed
   adapter can read/validate this configuration; source/API cannot select it.
2. Writer holds the exclusive root lock and reconstructs at mostN immutable
   slot claims. Before the first attempt/refusal publication, claim one unused
   slot permanently by an exclusive fsynced/readback store-owner allocation
   record binding store ID, next slot index, scope kind+UUID and capacity-model
   digest. Root/control record space comes from accounted installation headroom.
   Here store-owner means the configured nonroot store UID/GID, not UID0;
   "root" describes the held storage-root namespace, not privileged ownership.
   A lost claim acknowledgement holds that slot; exact ID replay reuses only
   that same claim, never another slot or a content-similarity match.
3. The fullS blocks andI_slot inodes remain charged for this scope, including
   after terminal success/failure and despite unused space. There is no GC in
   this version, so no slot is automatically refunded. An incomplete pre-reserve
   failure or early refusal also consumes its claimed slot. OnceN is reached,
   the store is unavailable until separately reviewed retention administration.
4. Before each allocation, enforce the per-slot peak and cleanup reservation
   against the closed plan and actual accounted inodes/extents. The exclusive
   writer cannot spend another slot or the unspendable global reserve. Actual
   allocation/free counters are sanity checks against the fixed ledger;
   `statvfs` is never the sole reservation or ownership proof.
5. Publication transfers a name/reference to the **same** staged inode, not
   reservation blocks released for another writer. A dedup hit skips allocating
   another copy only after exact immutable readback. Unknown/abandoned allocations
   remain charged. No hole punching, truncating backing storage or deleting a
   dummy reserve to make room is allowed.
6. Restore first blocks admission; replays actual slot claims and surviving
   file allocation evidence; then reconciles daemon/DB orphans. A missing claim,
   ledger disagreement or older valid snapshot is not permission to reuse a
   slot. Any unexplained allocator drift blocks service before new launch.

Under independently established exclusivity and a sound upper allocation model,
the fixed volume supplies protected capacity; concurrent ordinary host writes
cannot consume it. This does not prevent device failure, read-only remount,
kernel/firmware bugs or privileged tampering. Those still produce fatal evidence
failure and block admission. `fallocate`'s space guarantee applies to the **same
allocated file range**, not arbitrary future files or all directory/inode
metadata. It is insufficient as a transferable reserve.
[Linux fallocate contract](https://man7.org/linux/man-pages/man2/fallocate.2.html).

Host work requires a separate enforced bound within that same overall slot
calculation. Current Docker rendering fixes HOME/TMPDIR/config/cwd but does not
itself constrain host filesystem writes. Trusted CLI temporary/config/output
files and spool files can otherwise consume evidence cleanup headroom. An
installation must therefore provide either a genuinely separately bounded work
filesystem/domain inaccessible to the evidence reserve, or an independently
reviewed constrained-writer mechanism whose exact path/inode/block limits
cannot be changed by that writer. Its total maximum, metadata and backing
extents are part of the formula above, not an additional allowance. A full
work domain may fail CLI cleanup and leave an orphan; it must not prevent the
evidence domain from retaining the reserved failure/terminal diagnostics.

An ordinary ext4 project quota is **not assumed to be that non-bypassable
boundary**. In Linuxv6.8 the owner check and initial-user-namespace project-ID
change path permit operations that can change the project attribution;
ext4's project transfer is not generally fenced by an additional CAP_SYS_ADMIN
check. The actual installed enforcement must address this or reject that
mechanism. No quota or namespace is configured here.
[VFS file-attribute permission path](https://github.com/torvalds/linux/blob/v6.8/fs/ioctl.c#L585-L700),
[ext4 project transfer](https://github.com/torvalds/linux/blob/v6.8/fs/ext4/ioctl.c#L711-L795).

Alternative: a fixed preallocated append-only arena avoids later allocation
for its own records only if ranges are retained and never punched/reused, with
bounded commit/readback and crash markers. It would replace the current
file-per-blob publication/mode/membership contract, and still would not reserve
the actual transport's separately created spool/control/CLI files or inodes.
It would need its own reviewed format and the same enforced work boundary.
Consequently it is not the selected first direction and is not an excuse to
copy/modify transport or claim whole-attempt reservation from one preallocated
file. No arena, mount, loop device, quota, block device or backing file was
created or changed during this design task.

**Current result:** the finite model and assumptions are explicit, but actual
planner qualification, metadata/inode bounds, host-work enforcement and storage
stack installation remain unresolved. FS store code/capacity acceptance is
unallocated. Pure journal schemas can be reviewed independently; they never
return a physically reserved or operationally admitted capability.

## 6. Publication transaction and held-descriptor ownership

Use one explicit protocol for a blob, registration, manifest, event or refusal. Never
write an append stream whose partial last JSON record could be mistaken for a
complete event. Each complete event is a separately published immutable file.

1. Under the internal append lock, validate a private snapshot, select the exact
   relative destination from a fixed role plus UUID/sequence/hash, and reserve
   limits. Open/create a private staging intent file with O_EXCL/O_NOFOLLOW/
   O_NONBLOCK/O_CLOEXEC, mode0600. No user path is interpolated.
2. Write canonical publication intent, fsync/readback it, then fsync staging.
   Create its paired data file exclusively, write bounded chunks, require EOF
   and exact expected length/raw hash, fsync, fchmod0400, fsync the same data
   descriptor **again after the final mode change**, and recheck identity.
   Any later inode-metadata change needed by this publication is also fsynced
   on that inode before acknowledgement. A directory fsync does not substitute
   for this final file-metadata durability step.
   Publication intent is closed,4096 bytes/depth3/64 values:

   ```text
   {schema:"scanipy-runtime-publication-intent/1",publication_id:UUID,
    store_id:UUID,scope_kind:"attempt"|"refusal",scope_id:UUID,
    role:Role,destination:FixedRelativeName,
    size:int,sha256:H,expected_previous_event_digest:H|null}
   Role = blob | manifest | event | spool-registration | refusal
   ```

   Attempt scope permits the first four roles; refusal scope only blob/refusal.
   Refusal destination is exactly `refusal.json`, with null predecessor; it
   never invents an attempt ID. Other names derive from the fixed layout.

3. Publish with same-filesystem `linkat`/`os.link(...,follow_symlinks=False)`
   from the exact owned staging name to the absent destination. EEXIST is not
   overwrite: independently open/read/check the existing immutable file. Only
   exact bytes and the same operation/state permit idempotent replay; changed
   bytes, a foreign inode, unexpected links or mismatching intent quarantine.
   Known same-attempt deduplicated blobs can have an earlier publication's inode:
   prove their existing immutable membership through that history and full
   readback, then reuse them without linking the new stage over them. Equal
   bytes alone do not authorize adopting an unexplained preexisting file.
4. During a newly successful link there are exactly two known links to the
   held data inode: this staging file and its named destination. Verify both
   through held directories, remove **only** that validated owned staging
   data name, fsync the still-held final inode after its link-count change,
   fsync both affected directories, and require final nlink1.
   Never unlink an unvalidated replacement or retry a close-failed numeric FD.
5. Reopen final through the held destination directory with nofollow/nonblock,
   verify regular type, owner/mode/nlink, exact size, full EOF/raw digest and
   pre/post stat identity. Recheck destination membership and parent identity.
   Only then acknowledge the write. The immutable staging intent may be retained
   as bounded publication history or retired under the exact cleanup rule below;
   it cannot serve as an event-head substitute.

The host/kernel/admin threat boundary still applies to races between checks;
FD checks are not a promise to defeat a malicious privileged concurrent writer.
Nevertheless substitutions, hardlinks, FIFO/device swaps, permission drift and
partial fsync failures are explicit falsifiers, not ignored because a path is
private. Hold each child FD before a fallible parent close; close owned FDs once
on every path. Preserve original primary/interruption plus prior cause/context
and cleanup failures without custom exception truth/formatting callbacks.
The separate file/inode and containing-directory fsync requirements follow the
[Linux fsync contract](https://man7.org/linux/man-pages/man2/fsync.2.html);
the final chmod is therefore before the last file-metadata flush, not after it.

Crash before link: unacknowledged staged data is not committed. Crash after link
but before unlink/fsync/readback: publication is **ambiguous**, not failed-empty.
Recovery may complete only this exact recorded publication after verifying
same inode/bytes/known link pair and current directory identity. A file with two
links is never accepted by ordinary read as an immutable committed object.
Unknown/extra hardlinks or staging records block; do not guess their owner.

Publication intent retirement must not grow the journal unboundedly: after final
readback, remove only its exact held/rechecked owned intent file and fsync staging.
If that last cleanup fails, the result is not a clean acknowledgement; restart
can reconcile it from exact intent/final bytes. No final blob/event/history file
is deleted. A previous publication's reused UUID or changed destination fails.
The absence of an ack never authorizes another CLI invocation or release.

## 7. Journal grammar and event transition rules

Reuse the profile's full `scanipy-local-runtime-event/1` envelope and payloads,
with the following **proposed additive schema closures requiring root approval**.
There is no deployed journal to reinterpret; these must be frozen before its
first codec. Diagnostic events use `scanipy-diagnostic-runtime-event/1` and
the same closed data fields in a separate root, never operational schema IDs.

- `reserved` adds `manifest:BlobRef` to its existing launch/input payload.
- `loaded` adds `image_inspect_call:CallRef` and
  `create_prerequisite:PrerequisiteRef` to its existing fields.
- Add `spool-registered`: `{intent_event_digest:H,call_id:UUID,
  registration:BlobRef}`; at most one per call, before that transport starts.
- Add `spool-collected`: `{registration_event_digest:H,stream:"stdout"|"stderr",
  observation:BlobRef}`; at most one per registered stream, normally before its
  result. Section9's diagnostic recovery exception permits a first late
  collection after an existing result only once recovery-only is recorded and
  before a terminal event. It does not replace that result or its transport
  retention counters, establish EOF/custody success or permit later admission.
- Add `release-intent`: `{release:BlobRef,prerequisite:PrerequisiteRef,
  observed_event_digest:H}` before making the release visible to bootstrap.
- `released` adds `release_intent_event_digest:H`; its existing release and
  prerequisite refs must equal that exact preceding intent.
- `admitted` adds `domain_exited_event_digest:H`; all existing fields remain.
  Its existing `result_digest` is the raw SHA256 of that prior event's exact
  nonnull domain_result blob, and the prior event declares domain_validation
  `valid`. It is not an owning result identity or a schema-domain digest.
  `domain_exited_event_digest` separately keeps D(event schema,event bytes).
- `observed` adds `observation_id:UUID`; `cleanup` adds `cleanup_id:UUID`.
  These are actual controller-assigned record identities for exact append
  replay, not kernel identity or authorization. Changed bytes under one ID fail.
- In `observed`, `released` and `admitted`, replace the prospective plain
  `prerequisite:BlobRef` with the exact `PrerequisiteRef` above. Do not reinterpret
  an already deployed event; this proposal assumes the first journal is unbuilt.
- Add `recovery-entered`: `{recovery_id:UUID,writer_id:UUID,
  reason:"writer-restart"|"boot-change"|"clock-uncertain"|"abandoned-handle"|
  "orphan-resume",prior_head_digest:H}`. It is emitted only by the recovery
  method before any new recovery call or collection in an unfinished attempt.
- Add `reconciled`: `{orphan_event_digest:H,cleanup_event_digest:H,
  disposition:"failed",parent_lease_action:"none",invocation_slot:"released"}`.
  Recovery cannot turn an old orphan into admitted success.

Envelope invariant fields come from manifest and actual store scope, not a
caller-supplied full envelope. Store allocates event ID, sequence, predecessor,
trusted UTC/boot identity and measured elapsed time. Caller supplies only an
exact typed payload through dedicated methods or the exhaustive phase enum.
Numeric PID, image,
container ID and kernel facts are supplied by the installed observers; the
store checks consistency and history but does not pretend to observe Docker.

`origin_host_boot_id` and `origin_writer_id` in manifest never change. A writer
ID is a fresh actual service coordination UUID on each successful root-writer
open; it is not process authentication. Each event's `host_boot_id`
is the actual current boot, including after restart. `elapsed_ms` is cumulative
active-controller measured monotonic work, not elapsed wall downtime: restart
retains the last value and adds new measured recovery work. A changed boot,
controller interruption or uncertain clock permits recovery-only events, not
continuation/release/admission. `recorded_at` is actual current trusted UTC;
backward/uncertain time blocks launch and admission and is retained as failure.
The store never fabricates a previous-boot monotonic duration.

Recovery mode is irreversible, including on a same-boot writer restart. A newly
opened writer may never resume an unfinished attempt merely because boot ID,
PID or a lease still matches. `recover_attempt` first publishes/readbacks
`recovery-entered` with the exact prior head. Replay sets a sticky
`recovery_only=true`; every `orphaned` also sets `ever_orphaned=true` and recovery
only. Later cleanup cannot clear either fact. `admitted` requires both false.
No call that could create/start/release is permitted after this boundary.
Repeated recovery on another writer adds a new recovery entry under the same
overall128-event limit; exhausted reserve/cap stays blocked, not reset. If the
entry cannot be made durable, no new recovery CLI is started through this store.

One event sequence1..128, no gaps, duplicates or changed replay; sequence1 is
reserved with null predecessor. Other previous hashes name the exact immediate
predecessor under D(event schema, bytes). An operation receipt acknowledges
this exact event, not just the highest number on disk.

State is derived by replay, not arbitrary mutable `state` fields:

| State / permitted transition | Required retained prerequisites |
|---|---|
| uninitialized → reserved | Fully readback manifest, launch/input/request, loaded metadata and initial evidence; actual capacity and required parent barrier established |
| reserved → loaded | Daemon version/info + image-inspect call results retained; exact installed pin comparisons and fresh create prerequisite from owning adapters |
| loaded → created | One preceding create intent/result and exact-ID inspect result; current create authority; actual owned ID/config association |
| created → start-intended | Exactly one durable start-attached call intent; no prior start intent in this attempt |
| start-intended → started | Actual running PID/start identity and pending/returned same start call; no simulated PID from request |
| started → observed | Full actual pre-release kernel sample, exact-ID inspect and fresh release prerequisite, all same identities |
| observed → release-intended | Exact release bytes retained, current prerequisite and identity checks; no prior release intent |
| release-intended → released | Exclusive release publication readback acknowledges the same bytes; ambiguity blocks success |
| released → domain-exited | Start call result and exit inspect retained, owning exact domain decoder reports valid/rejected/invalid; never prefix or missing EOF |
| any active state → cleanup | Actual bounded disposal observations; may be incomplete, never synthesized from phase alone |
| domain-exited + cleanup complete → admitted | Valid domain result, all relevant calls complete/custodied, fresh same-scope authority and current installation reread, actual parent barrier still held |
| any active state → failed | Known failure, complete cleanup or positive proof no side effect could have occurred; terminal evidence durable before slot release |
| any active state → orphaned | Ambiguous/incomplete child, release, retention or cleanup; durable barrier and slot remain held |
| orphaned → reconciled | Recovery-only exact owned observations now prove cleanup complete; append failed disposition, never rewrite orphan or admit old output |

An unfinished non-orphan history also enters recovery-only before new recovery
calls. If cleanup later succeeds it terminates as failed, never admitted; an
ever-orphaned history terminates only as reconciled. Cleanup's temporary state
retains these sticky flags and the originating semantic phase. An existing
durable admitted/failed/reconciled history is read-only, with no recovery entry.

`observed` can repeat at most16 times while started/observed and before release
intent, each with a new sample. It cannot refresh or overwrite an old lease/
authorization; changed binding requires explicit failed attempt/new invocation.
At most one cleanup-complete event may finalize an attempt. Earlier incomplete
cleanup observations remain; later recovery appends new cleanup evidence.
`failed`, `admitted`, `reconciled` are final: subsequent mutation or execution
is rejected; exact read-only replay returns the prior receipt.

Uniqueness applies within each coordination-ID namespace: event IDs, call IDs,
publication IDs, observation IDs, cleanup IDs and recovery IDs have their own
defined keys. Repeated scope IDs, referenced event IDs and the same deployment/
attempt fields are required equal, not incorrectly rejected as duplicate UUIDs.
One error_id may be referenced repeatedly only with the same exact graph bytes
within its attempt/refusal scope; it is not a claim of live Python identity.

The following call intents/results are interleaved with semantic events:

- Before loaded: only daemon-version, daemon-info, image-inspect. Results may
  fail and lead directly to failed only if no possible container exists and
  every owned client is disposed or no client launch was attempted.
- After loaded: one container-create; ID inspect after an acknowledged ID.
  Name inspect is recovery-only after an unmatched/ambiguous create intent,
  requiring full retained name/config/labels before adoption.
- After created: one start-attached. Its result can arrive after inspection,
  release or timeout cleanup; global event order is append order, not call order.
- ID inspect is bounded in create/start/release/cleanup/recovery phases. Kill,
  wait and remove are cleanup-only for a corroborated exact owned ID; remove is
  nonforced only after stopped/cgroup-empty/client-disposal evidence.
- Every CallRef references a preceding same-attempt call-result with matching
  operation/ID. Started references the preceding start **intent**. No result
  without its unique intent, second result, changed replay or arbitrary operation.
- New calls after orphaned are recovery calls only. Pending earlier calls can
  contribute their one actual returned result during recovery. A still-running
  thread receives no synthetic exception-no-outcome result.

These structural gates are necessary, not proof that an operation was authorized
or its observation was genuine. The installed controller's exact operation
branches, current adapters and semantic validators remain required.

## 8. Concrete API, snapshots and receipts

There are two lifetimes, not one class impersonating both. The root handle owns
the root descriptors, writer lock, installed scope and one active invocation
slot. `RuntimeEvidenceStore` is its bound attempt handle, matching PE section8.
Neither accepts a caller-provided filesystem, clock, journal writer, callback,
authorization evaluator or process runner. No method executes Docker.

The installed factory allocates a fresh attempt UUID before rendering its
launch. It does not reuse that UUID after an ambiguous reservation. Allocation
itself is not an event or permission; before create, the store must acknowledge
the actual reservation. Source/API bodies cannot choose these IDs or handles.

Closed Python records below are exact frozen classes, with class-owned slot
snapshots and no repr exposing private inputs. UUID fields are exact UUID
objects internally; stored views use canonical UUID strings. Hash fields are
exact bytes32 internally. Exact tuples only; reject subclasses/poisoned aliases
before iteration, bounded aggregate projection or filesystem work.

```text
AttemptReservation(
 attempt_id:UUID, operation_id:UUID, mode:Mode,
 controller_started_ns:int, controller_deadline_ns:int,
 loaded:LoadedRuntimeInstallation,
 request_bytes:bytes, input_bytes:bytes, launch_bytes:bytes,
 initial_prerequisite_bytes:bytes,
 authority_blobs:tuple[EvidenceBlob,...],
 parent_barrier_bytes:bytes|null)

JournalReceipt(
 store_id:UUID, attempt_id:UUID, operation_id:UUID,
 sequence:int, event_id:UUID, event_schema:str,
 event_sha256:bytes32, event_digest:bytes32, event_bytes:bytes)

DurableCallIntent(receipt:JournalReceipt, prepared:PreparedCallIntent)
DurableCallResult(receipt:JournalReceipt, call_ref:StoredCallRef)
DurableSpoolRegistration(receipt:JournalReceipt, registration:StoredObject)
DurableRefusal(
 store_id:UUID, refusal_id:UUID, refusal_schema:str,
 refusal_sha256:bytes32, refusal_digest:bytes32, refusal_bytes:bytes)
StoredRefusalEvidence(
 visibility:"verified-visible",store_id:UUID,refusal_id:UUID,
 refusal_schema:str,refusal_sha256:bytes32,refusal_digest:bytes32,
 refusal_bytes:bytes,blobs:tuple[EvidenceBlob,...])

StoredCallEvidence(
 visibility:"verified-visible",
 intent_event:bytes, result_event:bytes,
 intent:StoredCallIntent, result:StoredCallResult,
 requested_invocation:StoredInvocation,
 actual_invocation:StoredInvocation|null,
 error_graph:StoredErrorGraph|null,
 stdout:bytes|null, stderr:bytes|null)

AttemptReadback(
 visibility:"verified-visible",
 manifest:StoredObject, event_bytes:tuple[bytes,...],
 state:State, recovery_only:bool, ever_orphaned:bool,
 unresolved_calls:tuple[StoredCallIntent,...])
```

`State` is exactly `reserved`, `loaded`, `created`, `start-intended`, `started`,
`observed`, `release-intended`, `released`, `domain-exited`, `cleanup`, `failed`,
`admitted`, `orphaned`, `reconciled`. The pre-reservation uninitialized condition
has no valid AttemptReadback. Cleanup state also retains the preceding semantic
phase in replay's private state, because final admission must still require a
valid earlier domain-exited event. Cleanup is never permission to resume
productive work; orphaned allows only the specified recovery operations.
`StoredObject` and other stored views are PE's actual tagged immutable tuples,
not another JSON object implementation. All readback views carry the exact
literal `visibility="verified-visible"`; they never nest or manufacture a
Durable* receipt. `StoredCallEvidence` returns null for
unavailable/unretained bytes, not fabricated empty bytes; the result's custody
fields distinguish every case. Its existence means this store performed the
specified readback, not that it approved the domain result or rehydrated a live
exception/outcome. Revalidation is mandatory when a receipt is consumed.
Only writer append or exact writer replay, after actual publication/fsync/
readback recovery, creates a Durable* receipt. Later writer consumption verifies
its actual namespace and repeats required sync/recovery; a caller's stored
receipt or a reader's visible prefix is not evidence that this checkpoint ran.

The manifest derives all repeated fields from these actual raw inputs and the
privately snapshotted loaded result. The store verifies raw hashes, exact closed
installation/outer metadata association and existing immutable loader fields;
it does not repeat runtime measurement or treat a `Loaded*` constructor as its
proof. The factory owns actual loader invocation/current-anchor checks. The
domain's request/input/launch/prerequisite decoders remain mandatory owning
adapters; the store rejects a mode whose actual integration is unavailable.
It never substitutes its structural JSON checks for signature/domain checks.

The two monotonic scalars are exact positive signed64 integers from the actual
installed parent's same-process `time.monotonic_ns`, with deadline equal to
start+30000000000. Store time must be at least start and below deadline when
reserving; elapsed work before reservation is therefore included. They are
private live coordination, not serialized cross-boot timestamps or runtime
authority. The store uses the lesser of the stored deadline and its own2-second
operation deadline for normal work. Cleanup/emergency evidence after expiry
uses the separately bounded recovery-only path; it cannot authorize further
productive calls. The parent checks its original deadline too. A caller cannot
reset an existing attempt's start/deadline by re-consuming a receipt.

`request_bytes` is exactly the profile's closed mode-specific outer request
(maximum65536), `input_bytes` is the exact mode-limited inner packet, and
`launch_bytes` is at most65536. Prerequisite is at most16384; authority blobs
are at most6 with combined1MiB. Parent-barrier bytes are at most16384. The
already bounded installed inventory remains at most8MiB. Validate length and
aggregate caps before copying/hashing. No arbitrary blob bundle is allowed:
all supplied blobs must be reachable through these exact role references.

Proposed fixed root/attempt API:

```text
RuntimeEvidenceRoot.reserve_attempt(AttemptReservation) -> RuntimeEvidenceStore
RuntimeEvidenceRoot.recover_attempt(attempt_id:UUID) -> RuntimeEvidenceStore
RuntimeEvidenceRoot.read_attempt(attempt_id:UUID) -> AttemptReadback
RuntimeEvidenceRoot.append_refusal(refusal_id:UUID,
                                  phase:EarlyPhase, code:FailureCode,
                                  observation:bytes,
                                  blobs:tuple[EvidenceBlob,...]) -> DurableRefusal
RuntimeEvidenceRoot.read_refusal(refusal_id:UUID) -> StoredRefusalEvidence
RuntimeEvidenceRoot.close() -> None

RuntimeEvidenceStore.reserved_receipt() -> JournalReceipt
RuntimeEvidenceStore.append_phase(kind:PhaseEventKind, payload:bytes,
                                 blobs:tuple[EvidenceBlob,...]) -> JournalReceipt
RuntimeEvidenceStore.append_call_intent(PreparedCallIntent) -> DurableCallIntent
RuntimeEvidenceStore.register_spool(DurableCallIntent) -> DurableSpoolRegistration
RuntimeEvidenceStore.collect_spool(DurableCallIntent,
                                 *, stream:"stdout"|"stderr") -> bytes
RuntimeEvidenceStore.append_call_result(DurableCallIntent,
                                      PreparedCallResult) -> DurableCallResult
RuntimeEvidenceStore.read_call(StoredCallRef) -> StoredCallEvidence
RuntimeEvidenceStore.unresolved_calls() -> tuple[StoredCallIntent,...]
RuntimeEvidenceStore.close() -> None
```

`PhaseEventKind` is a new exact enum with wire literals `loaded`, `created`,
`started`, `observed`, `release-intent`, `released`, `domain-exited`, `cleanup`,
`admitted`, `failed`, `orphaned`, `reconciled`. The one method is not an arbitrary
append hook: it has an exhaustive closed payload decoder and transition branch
per enum member, accepts no caller envelope/sequence/time, and rejects unknown
or subclassed enum values. `reserved`, `spool-registered`, `spool-collected`,
`call-intent` and `call-result` can only be emitted by their dedicated methods. No public raw
append, generic file write, root traversal, callback or state override exists.
`recovery-entered` can only be emitted by `recover_attempt`, never append_phase.

The reader has only `read_attempt`, `read_call(attempt_id, reference)`,
`read_refusal(refusal_id)` and
`close`, with the same immutable return shapes. `recover_attempt` is writer-only
and always recovery-only after open detects an unfinished history; it does not
restore a suspended launch permit or let ordinary state appends resume.

Every supplied referenced blob has an exact allowed role, cap and schema where
applicable. At most32 newly supplied blobs per phase; call results keep PE's
existing maximum8. All must be referenced by that payload or its bounded
transitive closure. Reject dangling, extra, contradictory and wrong-role blobs.
This API cap does not authorize an unknown kernel/domain schema. Repeated raw
bytes can share a blob, but role accounting and semantic validation remain per
reference. Loaded metadata bytes and initial blobs are published before the
manifest; manifest is published before reserved. A crash in between is an
incomplete reservation with no permission to execute, not a valid eventless run.

Receipts contain no FD, key, secret permit, mutable reference or authority bool.
On consumption, the store reads its actual attempt directory and exact event,
checks all scope fields and raw/domain digests, verifies state/predecessor and
compares canonical payload bytes. A fabricated/replayed receipt from another
store, attempt, mode or call cannot select a path. The actual installed caller
still owns admission. Closing a handle only releases local descriptors; it
does not append success, clear a durable slot/barrier, delete a spool, release
a parent lease or attest container termination.

Same-operation replay is exact. `append_call_intent` uses its unique
attempt/call-ID/call-sequence key; equal bytes return the original event even
after a lost ack, changed bytes fail. `append_call_result` uses that same call
key and requires identical prior result bytes for replay. For phase appends,
the operation identity is the fixed singleton phase, or for repeated observed/
cleanup records the exact referenced observation/event IDs in the payload;
no new event is manufactured to acknowledge a previously committed payload.
The explicit `observation_id` and `cleanup_id` additions in section7 supply
these keys; the implementation may not deduplicate observations by payload
similarity, timestamp or a guessed PID alone.

## 9. Registered spool custody without inferred outcomes

Actual `run_bounded_process` creates both fixed files with O_EXCL and requires
the spool directory initially empty. Consequently registration **must not**
precreate either file. It creates one fresh0700 call directory below the held
attempt's `call-spools`, opens/holds it, verifies empty membership and publishes
a canonical registration before the installed controller passes its derived
path to the actual transport. The controller passes only that fixed path; no
source/API path or stored diagnostic path is used.

Closed registration, maximum4096 bytes/depth4/96 values:

```text
{schema:"scanipy-runtime-spool-registration/1",store_id:UUID,attempt_id:UUID,
 operation_id:UUID,call_id:UUID,intent_event_digest:H,
 relative_directory:"call-spools/"+call_id,
 directory:{device:int,inode:positive int,uid:int,gid:int,mode:448},
 files:[{stream:"stdout",name:"stdout.bin"},
        {stream:"stderr",name:"stderr.bin"}],
 input_mode:"finite-one-shot",
 limits:{stdin_bytes:int,stdout_bytes:int,stderr_bytes:int,
         combined_output_bytes:int,wall_ms:int,cleanup_reserve_ms:int}}
```

The limits are derived by the installed call planner from mode/operation and
the fixed reviewed profile. The store checks those exact values and reservation;
caller-authored estimates are refused. PE's `FrozenInvocation` does not include
limits/spool mode, so the registration records **planned transport arguments**,
not a claim that the returned invocation attests them. The real controller must
forward the same actual `ProcessLimits` and path; integration tests verify it.
Memory-mode calls omit registration. Registration is immutable and unique per
intent; its `spool-registered` event precedes actual transport invocation.
`directory` identifies the newly allocated and held `call-spools/<call_id>`
directory itself, not its `call-spools` ancestor. Its device/inode must remain
the same when the stream files are subsequently opened.

The exact dir identity is known before transport; file identities are initially
unknown and must never be populated with zeros. After the owning synchronous
transport returns or raises, the installed controller has stopped that call's
parent pump and closed its owned spool descriptors. It may then invoke
`collect_spool` using the durable intent, not a path from `SpoolOutput`. The
store rechecks the registered directory and opens only its fixed stream name
O_RDONLY|O_NOFOLLOW|O_NONBLOCK|O_CLOEXEC. Require regular0600, owner UID/GID,
one link, actual bounded size and stable device/inode/size/mtime/ctime before
and after bounded read-to-EOF. Actual file identities are observed now.

Collection while the parent transport is active is prohibited by the installed
controller's exclusive call-lifetime bookkeeping. Frozen records and stable
stat samples cannot prove no writer exists. An interrupted process/restart,
uncertain parent pump or unknown file identity never gets success custody by
merely passing a Path or waiting for a lease expiry. Recovery may collect only
after separately establishing the former parent is gone and exact owned
container recovery permits a diagnostic read; never admit resumed old output.
The store itself cannot infer these facts from a supplied bool or returncode.

Before returning, collection retains the exact bytes and an immutable
observation, then appends/readbacks `spool-collected`. Observation is closed,
at most4096 bytes/depth5/128 values:

```text
{schema:"scanipy-runtime-spool-observation/1",store_id:UUID,attempt_id:UUID,
 call_id:UUID,stream:"stdout"|"stderr",registration_event_digest:H,
 observed_at:UtcInstant,before:FileObservation,after:FileObservation,
 bytes:BlobRef}
```

The two observations must agree on the required stable identity/content fields;
the bytes' exact size/raw digest comes from the actual bounded read. These
are file-custody facts only, not a new process/EOF/termination proof. No unobserved
file IDs appear in the pre-launch registration. Repeating collection after a
lost acknowledgement verifies and returns the already committed immutable blob;
it cannot overwrite the observation with a later version of that stream. A
second changed collection under the same call/stream key is a conflict.

`collect_spool` returns exact bytes, preserving empty bytes as observed empty.
Absence, unsafe file, readback change or an unestablished producer lifetime is
a typed evidence failure, not empty success. It retains no invented transport
EOF, retained count/hash, reason or cleanup status. `prepare_call_result`
compares the returned bytes to the actual outcome's reported retention using
its existing custody rules; a later readback cannot upgrade unknown retention.
One stream may be available while the other is unavailable. A bounded partial
read that fails is not returned as a complete stream; its failure remains
private evidence, and domain success is refused.

The first durable result copies available bytes into immutable evidence blobs;
restart `read_call` opens those blobs, never old spool paths. Registering a dir
is not publishing a result. The result's actual diagnostic path is retained
as bytes but never treated as a reopen instruction. Any later orphan-file
recovery is a separate diagnostic artifact with a new observation and cannot
alter the original PE result. Initial store has no spool deletion API; task
work retention/GC needs the separate controlled cleanup policy.

## 10. Cross-blob verification and bounded restart

Before every receipt and readback, verify full closure with bounded role-aware
decoders, not only a top-level digest. At minimum:

1. Root/manifest scope, fixed namespace, exact filenames, canonical schemas,
   sizes/raw hashes, role caps and installation/input/launch associations.
2. Event sequence/predecessor, invariant manifest fields, UUID uniqueness and
   exact allowed transitions; references target preceding committed events.
3. Intent payload's invocation digest/size and actual finite stdin identity;
   requested operation/target/attempt must match the journal. Verify mode-specific
   stdin bytes from actual retained inputs, never infer them from byte count.
4. Call-result payload, result blob and intent digest agree on every duplicate
   field. Requested invocation is exactly that intent's blob. Actual invocation
   may legitimately differ and remains preserved; controller admission separately
   rejects incompatible behavior. Do not discard mismatch evidence.
5. Actual stream evidence versus byte blobs, custody state and diagnostic path;
   null, empty, missing and unknown remain distinct. Readback never promotes a
   prefix, absent EOF or incomplete cleanup into success.
6. Error graph raw identity, canonical/DFS/depth/edge/omission rules through the
   actual PE decoder. Restart exposes the explicitly lossy graph only; no pickle,
   exception reconstruction, traceback evaluation or arbitrary property callback.
   For failed/orphaned primary_error_id, require equality with the error_id in
   at least one referenced preceding PE call-result and its graph. Each such
   reference resolves to the same exact graph bytes. A refusal's nonnull
   primary_error_id must match exactly one graph in its explicit evidence refs.
   Null means no retained primary graph; it is not a generated live exception ID.
7. All manifest/phase/CallRefs and error/blob references resolve in this attempt's
   owned namespace, with no cross-attempt dedup path, external URL or symlink.
   Shared physical content within the attempt does not share semantic authority.
8. Recompute slot, metadata, retained, per-call, observed/output and kernel
   accounting from immutable history. Unfinished calls retain their worst-case
   reservations. Exceeding a cap is corruption/unavailable, not clamped counters.

Replay uses iterative bounded traversal, depth at most16 for blob-reference
closure, at most256 unique blobs,128 events and the original per-role JSON
caps. Event envelope parser is capped65536 bytes/depth16/4096 key-inclusive
values; both complete call variants remain capped8192. Before generic JSON allocation, the
linear lexical pass enforces containment depth, key-inclusive value counts and
integer-token range; scalar leaves do not add a containment level. Reject
duplicates, noncanonical bytes, unknown fields and cycles. Raw packets are not
parsed as arbitrary JSON by the store merely because their first byte is `{`.

The reader first captures exact bounded directory membership and the highest
complete visible contiguous event prefix, reads all dependencies, then rechecks that
membership/identities. A concurrently appended suffix permits bounded retry or
an explicitly identified earlier complete visible prefix; it cannot splice two
heads or label that prefix fsync-acknowledged. It may observe a publisher between
final unlink/name visibility and directory fsync. No reader adds synchronization
or a durability guarantee; actual writer replay performs publication recovery
before a receipt can be consumed for a side effect.
Writer recovery takes the exclusive root lock and never executes source/tools.

Partial staging intent bytes are not authoritative publication instructions.
If a crash occurs while their own O_EXCL write is incomplete, retain/quarantine
the residue; do not derive a destination or unlink an object from malformed
JSON. Fully validated publication intents can reconcile only their exact owned
staging/final objects, previous head and hashes. Known two-link publication
completion follows section6; unexplained hard links fail closed. Missing final
file after an acknowledged event is corruption, not an invitation to reconstruct
history from a later caller's bytes.

Crash classifications are explicit:

| Durable evidence at restart | Allowed disposition |
|---|---|
| No reserved event; only incomplete manifest/staging | No execution receipt existed; quarantine reservation, no reuse of its UUID |
| Reserved/loaded, no create intent | Cleanup of owned local bookkeeping only; still verify no inconsistent later artifacts |
| Create intent, no result/ID | Possibly created; recover by exact retained name plus corroborated daemon/config/labels, otherwise orphan |
| Create result/ID, no start intent | Inspect only exact owned object; never start it on recovery |
| Start intent, no result | Possibly running; separate bounded exact-ID inspect/kill/wait, never attach a second start |
| Release intent, no release ack | Possibly released; kill/reconcile, do not publish a replacement release or admit old output |
| Domain result, no cleanup-complete | Result stays evidence only; establish actual termination before any reconciliation |
| Cleanup-complete, no terminal ack | Re-read exact terminal publication; current installation/authority governs any new action; recovery disposition is failed, not resumed admission |
| Admitted/failed/reconciled durable | Read-only exact result/replay; downstream idempotent workflow finalization rechecks its own current protocol |
| Orphaned or any inconsistent ownership | No new launch/slot release/retirement until explicit bounded recovery succeeds or operator intervenes |

For every ambiguous append, the caller retries only that storage operation
with identical bytes. Never rerun a CLI command to obtain an acknowledgement.
A late actual return may fill its one previously unmatched intent while recovery
owns the journal; a raced different result is rejected and preserved as failure,
not last-write-wins. If a lost writer cannot be excluded, no second writer is
admitted even when its wall-clock lease appears expired.

No local hash chain detects deletion/restoration of a valid old prefix by a
privileged administrator. Restore requires the independently installed factory
to enter blocked recovery admission, fence/stop launchers and audit retained
attempts against the actual daemon and parent-work ledger before enabling new
work. Its registry/admission checkpoint is outside the restored DB domain under
AIR; evidence-store restore admission is an explicit deployment procedure,
not invented signature/current-head proof. Silent autonomous reopening of a
restored journal while old containers may exist is prohibited.

## 11. Failure channel, live errors and terminal evidence

`RuntimeEvidenceError` is a fixed private error type with a closed reason:
`invalid-input`, `unsafe-path`, `unsupported`, `limit`, `deadline`, `busy`,
`corrupt`, `missing`, `conflict`, `io-failed`, `publication-ambiguous`,
`recovery-required`, `closed`. Messages are fixed; no raw paths, arguments,
packets, traceback text, exception repr/str or arbitrary attributes are logged.
Original live exceptions remain private and unchanged wherever possible.

On cleanup, close every owned FD at most once, tracking ownership before any
fallible operation. Snapshot an existing explicit cause, otherwise implicit
context, without boolean conversion or property callbacks. An earlier primary
interruption is not replaced by a later close/fsync/evidence error. Retain both
through an explicit private chain/group with no new immediate self-reference
or duplicate; never retry a numeric descriptor after a failed close. If cleanup
alone fails, return no successful receipt. PE's lossy graph is a bounded durable
diagnostic, not serialization of the complete live exception object.

If transport failed and persistence also fails, the controller preserves the
original exact transport/interruption as primary and explicitly chains the
evidence failure. It cannot downgrade the call to exception-no-outcome, erase
its partial outcome, publish a fabricated result or continue domain admission.
The store has no generic `error` parameter that formats exception state; the
actual pure PE preparer remains the only process diagnostic codec.

For refusal before a reserved attempt, the root method accepts only:

```text
EarlyPhase = "load" | "authority" | "reserve"
observation = canonical closed {
 operation_id:UUID|null,requested_mode:Mode|null,
 anchor:{deployment_id:UUID,installation_id:UUID,
         generation:positive int64,installation_sha256:H}|null,
 input:{size:int,sha256:H}|null,
 available_evidence:[BlobRef <=16],primary_error_id:UUID|null}
```

Maximum16384 bytes/depth6/256 key-inclusive values, full profile refusal at
most16384. The trusted factory allocates and fixes a genuine refusal UUID
before append, even if operation_id is not known. The store supplies actual
UTC/boot/elapsed fields and fixed schema; only established observations may be
nonnull. Associated
blobs must be exactly referenced. Early refusal raw evidence is opaque,
bounded to at most16 blobs, each at most8388608 bytes and all within the
32MiB retained allowance including its document; a referenced PE error graph
retains its stricter8192-byte limit and actual decoder. Do not invent a role
decoder for an untyped raw failure blob. Initial refusal pool is32MiB retained/512KiB metadata
per refusal, inside the256 total retained-entry count. No pre-load record may
invent an observed image/runtime identity from candidate pins. The root method
only retains data supplied by the trusted factory; it does not certify that
the load/admission checks were really performed.

Publish `refusals/<refusal_id>/refusal.json` only after all its bounded blobs
are durably available in that refusal's own `blobs/` directory. The writer receipt
contains the exact raw bytes, raw SHA256, D(refusal schema, bytes), refusal ID
and store ID; the raw file name is fixed, not an ordinary `blobs/H` selected
without a scope. `read_refusal(refusal_id)` opens exactly this installed-root
namespace through held descriptors and returns a verified-visible complete
closure, not a DurableRefusal; it does
not search directories, infer a refusal by content/time or use operation_id as
the key. The read-only reader exposes the same fixed method.

Lost acknowledgement is idempotent under the factory's fixed refusal ID.
Retry compares exact original phase/code/observation and supplied blob bytes
to the retained document/closure, excluding only the store-generated time/boot/
elapsed fields from the input comparison. If they match, return the original
full receipt with its original times; otherwise conflict. Never generate another
refusal UUID as an automatic retry or overwrite the stored timestamp. Unknown
staging state goes through the same exact-publication reconciliation, not
directory-search adoption.

A nonnull primary_error_id must identify the graph-level UUID in one explicitly
retained bounded PE error graph. All call-result graph references additionally
match that result's error_id. Integer graph-node IDs are a separate namespace.
No extra live-error identity map is created. If no genuine supported standalone
error-graph producer is available for an early load failure, keep this field
null and preserve the real live error privately; never manufacture a Docker call
just to obtain a graph from the existing call-result preparer.

If even the protected root cannot be opened or refusal cannot be persisted,
the controller refuses launch and propagates private failure; it must not
claim a durable refusal exists. After any potentially effectful call, evidence
failure holds the in-memory no-new-work latch and the previously acquired
durable parent/global recovery barrier. If storage is unavailable, the operator
must restore controlled recovery before service resumes. A write failure does
not magically create a durable quarantine marker. This is why the barrier and
reservation must precede create, not be attempted only after cleanup fails.

Terminal ordering is strict: retain actual call outputs/errors, establish
actual cleanup, append/readback cleanup-complete, perform the owning current
admission checks, append/readback admitted or failed/reconciled, then let the
outer workflow finalize its DB result and dispose its own parent leases.
There is no `finally: release_all_leases` behavior. No store destructor runs
network/DB cleanup or implicitly marks an attempt terminal.

## 12. Parent-work, capture retirement and orphan barrier

This is a genuine cross-component dependency, **not implemented by the current
occurrence store or by a filesystem receipt**. Its current finish/expiry paths
release ordinary capture consumers; retirement currently checks consumers and
pending work. Those rules alone cannot protect source when a timed-out runtime
container may remain. The first operational execution/syntax path requires a
coordinated DB barrier extension before any native launch.

Proposed narrow extension, owned by root's occurrence/controller integration:

- Add `runtime_capture_barriers` in the occurrence namespace, with immutable
  tenant/codebase/request/capture/seal/work-item/work-attempt/detector-run/
  capture-lease/authorization binding, deployment/store/runtime-attempt/
  operation IDs, exact original ExecutionBinding bytes/digest, launch/request/
  input/installation digests and acquisition evidence. No bare arbitrary
  consumer string or caller `accepted=true` column.
- Unique `(deployment_id,runtime_attempt_id)` and one barrier for that exact
  invocation; scope FKs must bind the same real execution rows. A file path or
  source commit assertion is not capture evidence. The initial public
  ExecutionBinding is detector-run-specific; identity attempts need their
  separately reviewed mode/binding before they can use this table.
- Guarded coordination is only `held -> released`, plus revision and exact
  release evidence. No automatic expiry or reactivation. Original bindings/
  evidence never change. Expiring/cancelling parent work does not delete or
  release a held runtime barrier.
- Claim locks the same capture/work/attempt rows as retirement and verifies
  current lease/fence/revision/retention state through the real trusted adapter.
  Commit the claim before reserved/create; retirement must see it atomically.
- Every retirement path, including replacement cleaner and cancellation,
  refuses a held barrier regardless of ordinary lease expiry or terminal work
  state. Retry/new native work for the same protected invocation scope also
  refuses unresolved barriers. Previously retained occurrences remain intact.
- Release requires the exact owned runtime identity and independently retained
  complete cleanup/terminal-journal proof through the installed controller's
  restricted recovery interface. It cannot rely on a codec receipt, PID
  absence alone, expired lease, zero client returncode or caller boolean.
  Releasing the barrier does not revive or complete the original work attempt.

Closed claim evidence returned after the actual DB transaction, at most16384
bytes/depth6/256 values:

```text
{schema:"scanipy-runtime-parent-barrier/1",barrier_id:UUID,
 deployment_id:UUID,store_id:UUID,runtime_attempt_id:UUID,operation_id:UUID,
 execution_binding:ExecutionBindingWire,
 execution_binding_sha256:H,request_digest:H,input_digest:H,
 launch_digest:H,installation_sha256:H,
 acquired_at:UtcInstant,barrier_revision:0}
```

`ExecutionBindingWire` is the exact accepted-input contract5.1 field set,
serialized by its owning canonical codec, not a duplicated divergent schema.
The `request_digest` here names the runtime outer request; original work-policy
and run-input digests retain their distinct named fields in ExecutionBinding.
The barrier binds planned bytes and original scope, not observed execution.
Its initial evidence excludes manifest/event hashes: the manifest references
it, preventing a claim↔manifest hash cycle.

Release evidence is a separate append-only DB record, not rewriting claim:

```text
{schema:"scanipy-runtime-parent-barrier-release/1",barrier_id:UUID,
 claim_digest:H,deployment_id:UUID,store_id:UUID,runtime_attempt_id:UUID,
 terminal_event:{schema:EventSchema,digest:H,sha256:H},
 cleanup_event:{schema:EventSchema,digest:H,sha256:H},
 disposition:"admitted"|"failed"|"reconciled",
 released_at:UtcInstant,barrier_revision:1}
```

These byte shapes do not authenticate actual fsync or kernel observations.
The actual restricted adapter must independently read the store's fixed root,
verify history/cleanup and compare real daemon/kernel recovery evidence before
issuing DB release. SQL cannot infer those facts from a hash. Exact transaction
functions, role grants, recovery caller authentication and source-backend
integration require a separately reviewed root allocation; this document does
not add them to the function fence or give the detector role a bypass.

There is no distributed transaction. Safe ordering is:

1. Claim DB barrier while ordinary current work/capture authority is live.
2. Retain its exact evidence in the immutable reserved journal.
3. Execute only through current installed controller gates.
4. Retain/verify final cleanup and terminal journal before barrier release.
5. Outer owner performs idempotent current DB finalization/consumer release.

Crash after step1 but before2 leaves a conservative barrier with no launch;
it **cannot use the release schema above**, because no genuine cleanup/terminal
event may exist. Its required separate restricted pre-reservation recovery
branch is unresolved and excluded from the first pure-journal allocation.
It must establish exclusion of the old parent/launcher and corroborate the
exact daemon/derived-name/immutable ownership plan through an actual trusted
adapter; absence of a journal, lease expiry or a caller boolean is insufficient.
The design must also ensure the original exact ownership/launch recipe is
retained before this crash window, rather than assuming a digest reconstructs
lost bytes. Root's cross-DB design will choose a distinct closed recovery
evidence/disposition schema or a separately journaled trusted recovery path.
Until reviewed, the barrier remains held. Do not make every release reference
nullable, fabricate reserved/cleanup events or reopen the old execution lease.
Crash after4 but before5 replays release/finalization exactly. Expired parent
authority permits only the restricted cleanup/recovery operation, not late
success commit or another execution. A stale attempt's real observations stay
retained through the explicit failure/late-evidence path; no false-empty result.

Publication/historical verifier modes do not use a capture and have null parent
barrier. Their container orphan still holds the deployment's one-active runtime
slot and root startup recovery gate. Execution verifier and per-file syntax
share the outer capture but get distinct invocation barriers; completing one
child cannot retire the scan-wide capture or release another child's barrier.
The outer owner retains its source/work leases across all required children and
its durable finalization; a store handle never owns those leases.

## 13. Interleavings, private lifetime and restoration tests

One active invocation per installation remains the profile limit. Root writer
lock serializes writers; journal appends are atomic critical sections within
the one trusted parent. The long attached start call does not hold the append
lock. The controller may inspect/release/cleanup while it is pending, with each
new operation's unique durable intent preceding that operation. This is trusted
orchestration, not an interactive addition to the one-shot shared transport.

Reservation, result-retention and failure paths all use the same lock and
quota ledger. A race cannot claim the last CLI slot twice, spend the cleanup
reserve as normal work, append two sequenceN events, or release a slot because
one of two competing writers happened to receive an acknowledgement. A failed
thread must not mutate a successful thread's actual outcome to fit its intent.

Required behavior at important interleavings:

- Attached result arrives during cleanup: append its one actual result, then
  re-evaluate all terminal requirements. Cleanup completion alone cannot
  manufacture the missing result or change transport cleanup state.
- Authority expires during observation: no release/admission; retain actual
  evidence and cleanup. A fresh authorization is a new immutable record under
  the real adapter, not an edited journal prerequisite.
- Cancellation during release publication: preserve ambiguity, stop/inspect the
  exact owned container and hold the barrier until termination is established.
- Disk/FD deadline failure during result publication: preserve live primary and
  pending call; no in-place result correction, no call rerun. Exact readback
  resolves only storage ambiguity, not native execution ambiguity.
- Lost worker thread or failed client cleanup: no collector/reaper guesses from
  its Python object; exact retained identity plus actual controller recovery is
  required. Missing acknowledged container ID remains a name/config-correlated
  recovery problem, not an empty result.
- Reader runs while writer commits: return one verified complete visible prefix or
  unstable-read; never an event referring to not-yet-published blobs.
- Competing expiry and retirement: DB barrier is checked under the same capture
  lock, so neither ordinary lease release nor file-journal close unblocks a
  possibly running consumer.

Store restore is not ordinary open. The operator/factory must block admission
outside the restored state before rollback/restore, inventory owned daemon
objects using immutable IDs/name+labels, reconcile every held DB barrier and
unmatched intent, and establish the current installation/trust checkpoint.
If a required old evidence object is unavailable, keep recovery blocked or make
an explicit audited administrative disposition; do not invent a matching event.
This procedure is an operational owner decision, not authorization conferred
by engineering approval or test-only roots.

## 14. Required tests and dependency-ordered implementation slices

All tests must have actual CI selectors. Pure vectors are diagnostic; filesystem
positives use fresh task-owned directories/files only. No existing evidence,
live app DB, Docker container, source, installation or operator key is touched.
Use actual reviewed PE/transport/inventory/profile types, not synthetic parallel
models. Runtime/controller integration remains unavailable until its real
dependencies and operational installation are separately reviewed.

| ID | Required acceptance/falsification |
|---|---|
| RES-01 | Complete root + independent review of this proposal and its existing-doc amendments; resolve section15 choices before affected code |
| RES-02 | Pure root/manifest/event/registration/barrier-reference codecs: exact types, byte/depth/key-inclusive-value limits, no unknown fields/duplicates/coercion, no caller callbacks, all transitions and cross-reference directions |
| RES-03 | Actual nofollow/nonblocking directory-relative file positives; symlink/FIFO/device/socket/hardlink/owner/mode/ancestor/renamed-root negatives; UID/GID mismatch refuses before reads; close once and retain context/primary/cleanup interruptions |
| RES-04 | Every publication boundary interrupted: before/after intent fsync, partial intent, data fsync, final chmod and post-mode fsync, link, unlink, inode-link-count fsync, dir fsync, final readback and acknowledgement. Exact replay/changed replay, owned two-link recovery and foreign replacement preservation |
| RES-05 | Every N-1/N/N+1 quota, aggregate metadata/raw distinction, identical-byte repeated work charging, last-slot races, actual physical-reservation failure, ENOSPC during ordinary work and guaranteed cleanup/terminal reservation under the accepted installation assumptions |
| RES-06 | Call intent before invocation, intended/actual mismatch retention, PTE carrier consistency through actual PE, missing versus empty/unknown streams, one-stream loss, late zero/incomplete, immutable original error graph and full cross-blob custody checks |
| RES-07 | Empty held spool registration, actual exclusive transport filename compatibility, no precreation, replacement/symlink/writer-active refusal, failed readback and original-error preservation, restart reads only blobs not diagnostic paths |
| RES-08 | Interleaved attached call/inspect/release/cleanup, two result attempts, UUID/sequence reuse, wrong attempt/mode/store/target, changed phase replay, bounded reader/writer visible-prefix consistency without false durable receipts |
| RES-09 | Same-boot writer restart, durable recovery entry, sticky recovery-only/ever-orphaned through cleanup, boot/clock change, unmatched create/start/release, stopped client but live container, old-prefix restore, parent expiry and no resumed admission |
| RES-10 | Separate restricted DB barrier slice: claim-vs-retirement race, expiry/cancellation leave barrier held, exact release/replay, wrong tenant/capture/fence/claim rejection, separately resolved claim-before-reservation recovery, DB↔FS crash windows and no scanner-supplied release authority |
| RES-11 | Actual installed factory/renderer/transport forwarding, real durable call intents and release intent before side effect, exact mode/domain/current authority gates; no fallback when any adapter is absent |
| RES-12 | Independent security/code review, focused and full configured tests, normal hooks/remote review, and separately authorized real durability/resource/termination/no-egress tests before operational acceptance |

Proposed first code allocation is deliberately split:

1. `tools/worker/runtime_journal.py` and
   `tests/unit/test_runtime_journal.py`: pure closed journal schemas/state replay
   and immutable stored views, importing existing PE. No FS, clock, DB, Docker,
   keys, runtime admission or event-store side effects. This can proceed only
   after the full event/schema/replay choices are frozen.
2. `tools/worker/runtime_evidence.py` and
   `tests/unit/test_runtime_evidence.py`: concrete held-FD store and fixed-root
   reader using the actual pure codec; fresh task-private filesystem positives
   and fault/race controls. Requires the chosen physical-reservation protocol
   and actual fixture/platform assumptions, not `reserved=true` placeholders.
3. `tests/integration/test_runtime_evidence.py`: controlled process-crash,
   writer-lock and restart tests against a fresh owned local filesystem only.
   An explicit required CI job may be needed for platform-specific durability
   semantics; no silent all-skipped integration acceptance.

The barrier migration/repository, installer/root bootstrap, controller call
planner, phase observers, release publisher and production factory remain
**separate unallocated integration slices**. Their exact filenames/schema/role
contracts must be assigned by root after design, not hidden inside these two
low-level modules. No code is authorized by this proposal. Existing PE source,
transport, runtime loader/renderer, occurrence migrations and signed historical
records remain unchanged.

## 15. Root decisions and current non-acceptance

The following are explicit engineering choices proposed for review, not already
approved operational facts:

1. **Schema closure:** adopt section7's exact payload additions/new kinds plus
   observation/cleanup identities, the manifest/registration/refusal/reference
   schemas and exact phase-replay keys. Preserve profile schemas only because
   there is no deployed journal; if one exists by implementation, version it
   instead of silently changing historical bytes.
2. **Budget classification:** raw installed metadata/inventory and raw authority/
   domain packets use the32MiB raw pool; small summaries and all PE/journal JSON
   work remain under512KiB. Keep all per-call/cumulative limits unchanged.
   Proposed64MiB transient disk and bounded retained-root inventory need review.
3. **Physical reservation:** qualify section5.1's conditional dedicated exclusive
   filesystem, permanent full-slot claim and backing-stack/metadata/inode model.
   Freeze actual work-domain enforcement and planner-derived bounds; no guessed
   split or project-quota assumption. `statvfs`, logical credits or allocating
   then freeing a different file do not guarantee cleanup capacity. This remains
   the principal FS-store prerequisite, independent of pure journal review.
4. **Parent/barrier integration:** approve the distinct irreversible runtime
   barrier dependency and allocate exact DB functions/roles/adapter plus source
   retirement/retry changes. Existing finish/expiry behavior must not be described
   as already implementing this. No operational execution/syntax launch before
   these real gates and recovery interfaces exist.
5. **Installer/restore ownership:** actual owner chooses root installation,
   authenticated factory/recovery operator and external blocked restore admission.
   Engineering review, local test keys and a root-hash field cannot make this
   operational choice on the owner's behalf.
6. **Actual compatibility:** fixed30-second outer and2-second store-operation
   bounds, reservations and filesystem costs need measured task-private testing.
   Failure means unavailable or another explicitly reviewed profile, never a
   silent cap increase or invented receipt.

All RES items remain open in this proposal. The existing pure PE checkpoint
keeps its original cutoff and tests; this document does not retroactively add
storage/DB/controller acceptance to it. The full submitted Black Hat scope,
real end-to-end execution and stage readiness remain separately tracked.

Review revision: this draft incorporates the root/corpus findings after the
original1113-line draft (`3930264758440dadc2173ab863f09d966eba3634c17eca66d99b96d7730569b4`).
Changes are documentation only: durable file-mode fsync, scoped refusal replay,
fresh authority closure, sticky recovery, explicit accounting/work bounds,
spool directory identity and conditional dedicated-volume capacity. No new
source, filesystem fixture, mount, runtime test, journal record or acceptance
was created. At that review cutoff RES-01 remained open pending review of the
corrected version; the subsequent limited approvals are recorded below.

Approval chronology, 2026-09-25:

- The original1113-line proposal remained in a task-private temporary directory;
  root and corpus identified the corrections listed above before any code.
- Root and corpus each read all1477 corrected lines at raw SHA256
  `42d31451bade18ddfe8f488527e4f033cdc618baf25fa3d1ce5af10ca6d98b39`, plus the
  68-line companion amendment proposal at
  `dd1924af83cf09dd52f445c68409342f6cbe3295f7a10c732f24ebb84c609bfc`.
  They approved the closed wire/replay/receipt design, visible-versus-durable
  distinction, and raw32MiB-versus-summary512KiB classification only.
- Root authorized this docs-only repository integration and the nonroot-owner
  clarification. Original PE implementation/test cutoff remains unchanged.
- During the new pure-API review, canonical peer found and root independently
  verified that the earlier generic role/raw-hash equality was wrong for
  execution authorization and unspecified for admission. Section4 now records
  the six-role table: four direct raw-SHA links and two explicit owner-codec
  obligations. The original42d31451 review artifact remains unchanged as
  historical evidence; this newly found correction is documentation only,
  pending review with the API. No historical signature or runtime record changed.
- The physical filesystem/backing-stack/work-domain model, metadata/inode
  qualification, installation, DB barrier and pre-reservation recovery branch,
  controller and operational authority remain unapproved/unimplemented. Their
  RES items stay open. Approval of design is not completion of RES-02–12.
- The following exact pure API addendum is **PROPOSED, review pending**. Root
  has identified two future files but has not authorized their implementation.
  This describes the pre-review cutoff, not the later allocation below.
- Root and canonical peer subsequently approved the exact API/accounting at
  `47731c42ef90efbdbadeadf5f1a7c510838786bd65dee0264feef21c04703ca1`.
  Root allocated only runtime_journal.py and its dedicated unit tests. During
  implementation root explicitly clarified planned-limit bounds, the raw
  admitted-result link, declared-time fresh-use versus historical-repeat
  chronology, cumulative observed pins and first late diagnostic spool
  collection. These are structural rules only. Code review/full gates remain
  pending; no filesystem, DB, controller, admission or operational authority
  has been implemented or accepted by this allocation.

## 16. Proposed first pure journal API — structural validation only

This addendum is the pre-code boundary for exactly
`tools/worker/runtime_journal.py` and `tests/unit/test_runtime_journal.py`.
No helper/source file, store, installer, migration, fixture filesystem, domain
profile bytes or service integration is included. The module performs bounded
canonical decoding/encoding, reference checking and replay of **supplied data**.
It has no filesystem, clock, process, network, database, randomness, storage,
environment discovery or callback parameters/calls.

It must never return `JournalReceipt`, any `Durable*` record, `AttemptReadback`,
`StoredCallEvidence`, a `verified-visible` view or an installation/admission
capability. Those require real later adapters. A caller can construct arbitrary
well-formed bytes: successful pure replay establishes their local structural
consistency, not their provenance, visibility, durability or truth. In
particular, an input `kind="admitted"` is a declaration being checked, not a
successful runtime result established by this module.

### 16.1 Dependencies and exact types

Import the actual PE `EvidenceBlob`, `StoredValue`, `StoredArray`, `StoredObject`,
`StoredBlobRef`, `StoredCallIntent`, `StoredCallRef`, `StoredCallResult`,
`StoredInvocation`, `StoredErrorGraph`, `CliOperation` and public decoders.
Delegate PE invocation/call/ref/error schemas to those public decoders and map
operations with `cli_operation_from_wire`; no second operation enum/codec and
no imports of private PE helpers. The shared tagged tuple representation remains
unchanged. The journal's `Mode`, `Phase`, `FailureCode`, observation shapes and
new event variants are the exact wire domains in the profile/this document;
there are no existing public Python journal classes to replace or clone.

Do not define lookalike `LoadedRuntimeInstallation`, `RuntimeInstallationAnchor`,
`RuntimeArtifact*`, `ExecutionBinding`, `AdmissionExpectation`, `QualifiedRuleKey`,
`VerifierRuntimeProfile` or `PythonSyntaxRuntime` classes. No new record claims
to be one of those actual owning types. The pure module does not accept a
caller-created live loader/profile/outcome as its evidence input.

New exact frozen/slotted classes, all with non-content repr:

```text
ParsedJournalRecord(
 validation:"local-structure-only",
 kind:JournalRecordKind, schema:str,
 data:bytes, sha256:bytes32, schema_digest:bytes32,
 document:StoredObject)

ReplayedCall(
 intent_event_sequence:int, result_event_sequence:int|null,
 intent:StoredCallIntent, result:StoredCallResult|null)

OpaqueOwnerValue(
 role:OwnerRole, containing_sha256:bytes32,
 field_path:tuple[str|int,...])

JournalStructureReport(
 validation:"local-structure-only",
 manifest:ParsedJournalRecord,
 events:tuple[ParsedJournalRecord,...],
 declared_phase:DeclaredPhase,
 recovery_only_recorded:bool, ever_orphaned_recorded:bool,
 calls:tuple[ReplayedCall,...],
 blobs:tuple[EvidenceBlob,...],
 opaque_owner_values:tuple[OpaqueOwnerValue,...],
 accounting:StructuralAccounting)

RefusalStructureReport(
 validation:"local-structure-only",
 refusal:ParsedJournalRecord, blobs:tuple[EvidenceBlob,...],
 opaque_owner_values:tuple[OpaqueOwnerValue,...])

StructuralAccounting(
 supplied_blob_bytes:int, supplied_record_bytes:int,
 logical_metadata_bytes:int, call_count:int, kernel_sample_count:int,
 nonattached_observed_bytes:int,
 nonattached_known_retained_bytes:int,
 nonattached_missing_outcome_count:int,
 nonattached_missing_output_count:int,
 nonattached_unknown_retention_count:int,
 kernel_raw_bytes:int)
```

Exact tuples/bytes/classes only; no subclasses, custom Mapping/iterables,
instance methods, caller boolean conversion, error formatting, cached Path/UUID
strings or mutable aliases. Record constructors are convenience carriers, not
validation authority; every public consumption privately snapshots/revalidates
all fields using fixed class-owned access. The API uses wire strings instead
of accepting Path or UUID objects. `schema_digest=D(schema,data)` and raw
SHA256 remain different named fields, computed from the exact supplied bytes.
All count/index/byte fields are exact nonnegative signed64 integers within
their tighter listed bounds; event-sequence fields are1..128. Nullable result
sequence/result fields are paired, and a present result follows its intent.
Digests are exactly32 bytes. Literal tags/roles/kinds are exact builtin strings;
only the imported `CliOperation` uses its existing Enum representation.

`JournalRecordKind` is an exact string Literal, not a new enum:
`root | manifest | event | refusal | authority-inventory | prerequisite |
spool-registration | spool-observation | publication-intent`.
`DeclaredPhase` is exactly the phase strings listed with `State` in section8;
the prefix "declared" is mandatory in public pure results. Recorded recovery
flags describe history data only, not an installed writer's lifecycle.

The exact kind-to-schema mapping is:

| Kind | Accepted schema literal |
|---|---|
| root | `scanipy-runtime-evidence-root/1` |
| manifest | `scanipy-runtime-attempt-manifest/1` |
| event | `scanipy-local-runtime-event/1` or `scanipy-diagnostic-runtime-event/1` |
| refusal | `scanipy-local-runtime-refusal/1` |
| authority-inventory | `scanipy-runtime-prerequisite-evidence/1` |
| prerequisite | `scanipy-local-launch-prerequisite/1` |
| spool-registration | `scanipy-runtime-spool-registration/1` |
| spool-observation | `scanipy-runtime-spool-observation/1` |
| publication-intent | `scanipy-runtime-publication-intent/1` |

No suffix substitution or unknown version is accepted. Replay requires the
event schema selected by the manifest's declared artifact domain. Root/refusal
single-record decoding establishes no association with an installed root;
refusal has no domain field from which to infer one. A separate diagnostic
refusal schema is not invented here. Controlled tests may exercise these
schemas as data without claiming operational origin.

`OwnerRole` is exactly `installation`, `controller-profile`, `domain-profile`,
`runtime-inventory`, `mode-request`, `mode-input`, `launch-packet`,
`release-packet`, `domain-result`, `authentication`, `scope`, `admission`,
`execution-authorization`, `capture-lease`, `content-verification`,
`parent-barrier`, `kernel-raw`, `refusal-raw`. The last role denotes explicitly
untyped refusal evidence, not a promise that a missing domain decoder exists.
A location is the raw containing blob/record's
digest plus at most8 exact field components; string components are known schema
keys of at most128 UTF-8 bytes, index components exact ints0..4095. Root opaque
packet locations use an empty tuple. These are JSON locations, never paths
to open, callbacks or names of dynamically imported validators.

### 16.2 Exact public functions

```text
decode_journal_record(kind:JournalRecordKind, data:bytes)
    -> ParsedJournalRecord

encode_journal_record(kind:JournalRecordKind, document:StoredObject)
    -> bytes

replay_journal(manifest:bytes, events:tuple[bytes,...],
               *, blobs:tuple[EvidenceBlob,...])
    -> JournalStructureReport

validate_refusal(refusal:bytes, *, blobs:tuple[EvidenceBlob,...])
    -> RefusalStructureReport
```

No optional callback, authority reader, current-time argument, relaxed mode,
filesystem opener, output path or success flag. The diagnostic/operational
artifact domain is checked from the declared root/manifest/schema, not selected
by an enablement flag. A diagnostic byte vector is still only data. The pure
API does not create observed UUIDs/timestamps or fill absent facts.

`decode_journal_record` validates one local record's canonical encoding, exact
owned key sets/scalars and local cross-field rules. It cannot resolve a BlobRef
or prove event ordering alone. `encode_journal_record` accepts only PE's exact
bounded tagged tuples, validates the same schema, emits canonical bytes and
performs the same decoder validation before return. It never accepts a live
object whose `to_dict`, `__iter__`, property or repr is invoked.

`replay_journal` requires exactly one manifest and1..128 event byte records in
declared sequence order. An empty/unreserved/incomplete manifest is rejected
by this function, not represented as an executable phase. At most256 exact
EvidenceBlob objects, sorted by raw digest, no duplicate digests, combined
supplied blob payload at most33554432 bytes. Hash/length validation occurs
before reference use; conflicting/unused/missing blobs fail. Event/manifest
records together are also charged to metadata, not ignored because they were
passed separately. Their actual original bytes are retained in the report;
immutable bytes may be shared in memory, never reserialized as the original.
The sum of separately supplied record bytes and blob bytes must also fit the
33554432-byte retained limit. The manifest is a distinguished supplied record:
the reserved event's manifest BlobRef resolves against those exact bytes,
without a second manifest in `blobs`. Event references resolve only against
preceding supplied events, using the specified raw/domain digest kind. Reject
a blob entry duplicating a distinguished record or an event; these are not
additional loose blob roots. Distinct role references may reuse a real blob,
but they cannot reinterpret a journal record as an arbitrary metadata packet.

`validate_refusal` resolves only the refusal's explicitly referenced local blob
closure, at most16 raw blobs, original8MiB-per-blob/32MiB aggregate bounds and
stricter8192-byte PE graph limit. It returns no store ID or fixed-root path
claim because neither exists in its arguments. The scoped reader/receipt
classes in section8 are deliberately different and absent from this module.
The refusal document plus all supplied blobs fit the32MiB total; available
evidence refs are the exact roots and no extra blob is accepted. A nonnull
primary_error_id requires exactly one referenced blob that passes the actual
PE graph decoder with that ID. Other refusal evidence remains `refusal-raw`,
even when it happens to look like JSON; do not discover transitive references
by guessing an arbitrary raw blob's schema or content prefix.

### 16.3 Per-record and aggregate bounds

Every JSON parser first runs the linear preserved-byte lexical guard. The root
container is depth1, object/array nesting increments depth and scalar leaves
do not; every value and every object-member key consumes one value slot.
Reject oversized integer tokens/range, duplicate keys, noncanonical UTF-8,
NUL/lone surrogates, floats/nonfinite numbers, coercion and unknown local fields
before permissive normalization can lose information. Encoding preflights total
escaped UTF-8 bytes and queued+processed values before serialization/allocation.

| Kind | Maximum bytes | Depth | Key-inclusive values |
|---|---:|---:|---:|
| root | 4096 | 2 | 32 |
| manifest | 16384 | 6 | 256 |
| event | 65536 | 16 | 4096 |
| event with call-intent or call-result | 8192 | 16 | 4096 |
| refusal | 16384 | 6 | 256 |
| authority-inventory | 16384 | 6 | 256 |
| prerequisite local envelope | 16384 | 16 | 1024 |
| spool-registration | 4096 | 4 | 96 |
| spool-observation | 4096 | 5 | 128 |
| publication-intent | 4096 | 3 | 64 |

Opaque raw roles retain these existing byte ceilings; these are not permission
to skip their later owning codecs:

| Role | Maximum raw bytes |
|---|---:|
| installation | 65536 |
| controller-profile | 131072 |
| domain-profile | 65536 |
| runtime-inventory | 8388608 |
| mode-request / launch-packet | 65536 each |
| mode-input | 2621440 for verifier modes; 263244 for python-syntax |
| release-packet / parent-barrier | 16384 each |
| domain-result | 16384 for verifier modes; 8388608 for python-syntax |
| each authentication/scope/admission/execution-authorization/capture-lease/content-verification object | 1048576, with all objects of each inventory together <=1048576 |
| kernel-raw | 65536 per blob; <=1048576 cumulative per-attempt role use |
| refusal-raw | 8388608 each, within the refusal's total pool |

The complete manifest/events, local prerequisite/inventory/registration/
observation summaries, PE invocation/call/result/error JSON, and PE's exact
UTF-8 diagnostic path bytes count
toward the524288-byte logical metadata ceiling. Raw installed metadata and
authority/domain packets use the total raw pool even when their bytes happen
to be JSON. A blob used by both classes is charged in both relevant logical
roles, but retained once. Role classification is determined by these closed
reference positions, never caller-chosen content type or a dedup shortcut.

PE blobs retain their actual decoder caps; no larger journal cap overrides one.
Spool-registration ProcessLimits keep the actual shared relationships. For an
attached call, require positive wall_ms<=30000 and exact integer
1<=cleanup_reserve_ms<=min(5000,wall_ms-1); neither30000 nor500 is invented as
the one exact attached plan. For nonattached calls require250<wall_ms<=2000,
cleanup_reserve_ms=250, stdin_bytes=0, and the documented exact initial-profile
stdout/stderr/combined maxima. Attached I/O maxima equal the declared mode's
fixed caps. These are structural bounds only; exact installed planner equality
and remaining outer deadline still require the actual controller. Test both
boundary values and that a valid record does not imply effective enforcement.
Embedded owner objects described below stay within their containing record's
same lexical/aggregate caps. At most4096 reference edges and256 distinct blobs
in replay, at most16 reference-containment levels, iterative bounded traversal
with cycle rejection; at most4096 opaque-owner locations. At most16 calls and
16 kernel samples. Refusal uses its stricter16 referenced blobs. Bound outer
tuples and aggregate byte totals before copying or parsing any member.

Pure hashing has a separate512MiB cumulative input-byte work ceiling per public
call; cache one validated digest/decoder view per exact immutable blob inside
that call. Structural reference/accounting passes still count each logical
role occurrence even when content was cached. This is a CPU-work bound, not
disk I/O or a claim that the outer runtime's latency ceiling passed. No clock
is read or caller-chosen work limit accepted. Future full-store I/O budgets
remain independent and do not apply to this no-I/O parser.

### 16.4 Replay and closure semantics

Replay checks exact first reserved event/manifest ref, declared scope fields,
contiguous sequences/predecessor digests, same-attempt refs, per-namespace UUID
uniqueness, call IDs/ordinals and at most one exact result per call. A duplicate
event inside the supplied sequence is not an idempotent append request: it is
invalid history. Exact append retry behavior belongs to the real writer and
is not simulated by discarding duplicate input events.

Implement section7's phase transitions and sticky recorded recovery rules.
The fixed declared call plan permits at most12 ordinary intents and16 total.
Classify an intent as cleanup/recovery only under the existing declared
cleanup/orphan/recovery state restrictions, not its operation name alone:
inspect-id may serve either role. Cleanup/recovery may use unused ordinary
slots as well as the four reserved slots; there is no separate four-cleanup
maximum. Counts never replenish after cleanup, recovery or another writer.
This is local declared-plan consistency, not proof of actual physical slot
reservation or binding to the installed planner.
An orphan→cleanup path cannot erase recorded recovery mode and admit output.
Each recovery entry's prior head must equal its envelope predecessor; repeated
writer/recovery IDs cannot change facts. Fresh create/observation/release/admit
PrerequisiteRefs resolve their own inventory and enforce section4's four
direct raw-SHA links. Admission/execution-authorization enforce their local
presence/role/size/raw-integrity rules and remain explicit opaque-owner
obligations; no domain-digest equality is fabricated by this pure slice.
At the manifest and each genuinely fresh authorization boundary (loaded/create,
observed, release-intent, admitted), require the supplied prerequisite's
observed_at <= that declared boundary timestamp < valid_until. This is a local
chronology comparison, not a clock read or assertion of current authority.
The released event repeats the exact release-intent prerequisite/inventory;
its delayed acknowledgment may occur after that prior validity interval and
does not grant fresh authorization or admission. A later admitted boundary
still needs its own locally valid prerequisite observation.
A matching historical `released` acknowledgment remains representable while
still release-intended after a concurrent failed or overrun call-result (or
known spool overrun). It does not clear that sticky failure or permit another
productive intent/admission. Preserve no-recovery/no-orphan/nonterminal guards,
expected/observed image and OCI consistency, exact prior refs and the declared
publication timestamp bounds. This exception applies only to this historical
acknowledgment, not other phase transitions, actual release publication or the
future controller's current-authority checks.
Envelope observed image/OCI pins are cumulative latest-known facts: after a
nonnull value, null cannot erase it. A differing nonnull actual value remains
retainable on failure/cleanup, but prevents productive continuation against
the expected pins. An unknown new measurement stays in failure evidence rather
than replacing a previously known envelope value. These are supplied-record
consistency rules, not independent image or daemon observations.
Requested/actual invocation mismatches remain intact and do not become parser
errors merely because the observed data differs from intended policy.

Call-result closure delegates to actual PE parsers: requested invocation equals
the earlier intent; actual invocation/result/error/stream references agree;
retention/custody states, missing/empty/unknown and graph-level error IDs remain
distinct. Spool registration/collection references match the declared call and
stream. No file is opened and no reported EOF/cleanup is independently observed.
First registration for the attached start call must precede its supplied
`started` event; later recovery cannot retroactively register that same call.
Memory mode without registration remains valid, as does registration for a
new cleanup/recovery call before its result. This checks supplied chronology,
not actual process creation or directory-allocation timing.
Kernel samples use exact local field shapes/caps and retained raw refs, without
claiming the values came from `/proc` or met a real runtime policy.
Observed kernel mount targets may be exactly `/`, so a complete mount inventory
can represent the root mount. Only this observed-target grammar permits that
value; storage/installation/control paths retain their existing nonroot and
traversal/control-character fences. Replay compares supplied timestamps:
started.recorded_at <= sample.observed_at <= its observed-event.recorded_at,
and release-intent.recorded_at <= released.published_at <= released.recorded_at.
Both bounds are inclusive. These causal comparisons neither read a clock nor
prove actual observation/publication or current authority; a delayed release
acknowledgment remains representable under the existing historical-repeat rule.
The journal-owned admitted.result_digest must equal the raw SHA256 of the
exact domain_result ref in its specified prior valid domain-exited event.
Validate this local link, not an invented owner-schema digest. The result
remains opaque and pure replay remains local-structure-only; actual owning
domain validation is still mandatory before real admission. Controls must
reject a different result's raw hash and D(owner schema,result bytes), while
accepting the exact same retained result's raw hash.

StructuralAccounting uses a fixed logical-occurrence census, independent of
blob traversal order and caches:

- Count each call intent once for call_count and its requested invocation
  metadata once under that call's requested role. Reuse of the same invocation
  bytes in another call is another logical role occurrence.
- Count the complete call-result record/closure and its outcome/stream counters
  once when that call's single result event appears. "Completed call-result"
  here means a result record exists, not successful client/domain execution.
  Its present actual invocation is charged once under its actual role, even
  when raw bytes equal the requested invocation. The repeated requested ref
  inside the result is checked against the intent, not charged as a third role.
  Each present stream/path and error-graph role is charged once for that result;
  identical stdout/stderr bytes are two stream roles, not one observed stream.
- A later phase's CallRef contributes its bytes inside that phase envelope,
  but does not charge the already-counted invocation/result/stream/error closure
  again. Revalidation/hash work is separate from logical metadata/stream work.
- Count the manifest, each event and each separately owned local summary once
  at their declared occurrence. Count manifest metadata/request/input/launch/
  parent-barrier roles once; later identity/equality references do not create
  new metadata observations. An independently recorded new observation does.
- Count a prerequisite summary, inventory and each of its six possible evidence
  roles once per distinct prerequisite observation_id. A genuinely fresh
  observation counts these roles anew even if some evidence blobs are unchanged.
  Repeated references to the same exact observation do not invent observations;
  changed bytes or inventory under the same observation identity are a conflict.
  Apply the analogous identity rule to kernel observation_id, spool registration
  per call and collection per call/stream. Their repeated references do not
  duplicate samples, collections or role charges. A release packet belongs to
  its single release-intent; the released event's equality ref does not duplicate
  it. A domain result belongs to its single domain-exited event, not every later
  admitted reference. Each new envelope still contributes its actual bytes.

For nonattached call-results, the exact incomplete-state counters are:

- `nonattached_missing_outcome_count`: add one when the recorded result has
  null outcome. Do not invent two null output objects or reported stream counts.
- `nonattached_missing_output_count`: only when outcome exists, add one for
  each null stdout/stderr. A null outcome does not also increment this field.
- `nonattached_unknown_retention_count`: add one for each **present** output
  whose reported retained count/hash is the actual paired null state. Missing
  outcomes/outputs do not also increment this field.
- Sum observed_bytes only from present reported outputs; sum retained_bytes only
  from present outputs with known counts. These sums are known lower bounds,
  never proof of zero/full observation or retention when any applicable missing
  or unknown state exists. A present output with unknown retention can still
  have a known observed count, which is preserved.

Pending intents remain unmatched calls in `calls`, not completed results with
invented absent/empty streams; none of these result counters is incremented
for them. The report's complete retained result views preserve every original
state in addition to the aggregate census. A real known-empty stream has its
actual zero count and SHA256(empty), not any missing/unknown flag.
Unmatched calls also prevent interpreting the known sums as a complete total;
their absence of a result is not evidence of zero output work.

A record of a real limit overrun is not clamped or
discarded: replay requires no subsequent productive/admitted transition under
that declared failed history, while preserving the bounded actual count.
Impossible numeric relationships and schema overflow still fail decoding.
In particular each retained spool collection is checked against its registered
stream-byte cap and the sum of that call's collected streams against its
registered combined cap. A known violation sets sticky overrun even before a
call result exists or when the separately supplied result reports different
in-memory/zero-byte output. Retain both evidence sources without deriving
transport observed/retained/EOF/custody counters from file readback. Recovery
or failure evidence may still be retained; it cannot reenable productive work
or admission. Equal-content streams are charged as two stream sizes here.
The current closed profiles set combined equal to the sum of stream maxima;
combined-overflow controls consequently also exceed at least one stream and
must not invent an unapproved lower combined limit to claim independence.

This summary is **not** physical accounting: it cannot know distinct inodes,
block rounding, unreferenced staged files, quotas, fsync, actual allocators or
unknown side effects. The filesystem store must enforce those separately. Its
logical publication-control reservation is also separate from supplied event
and blob bytes; pure replay does not pretend absent filesystem control records
were observed or reserved.

### 16.5 Owner-codec and truth boundaries still missing

The current tree has no public completed controller mode-request/domain-result
or live-authority adapters. The first journal module must not invent them or
copy accepted-input/semantic/runtime profile codecs. Consequently:

- Its local prerequisite envelope checks the profile's top-level keys, scalar
  domains, mode/action/nullability relationships and the four direct raw-SHA
  links in section4. Execution authorization's declared domain digest is not
  compared with a raw hash, and admission has no fabricated raw-hash member.
  A nonnull embedded AdmissionExpectation is preserved as a bounded canonical
  owner object, not certified against the owner's full schema or signature.
  Both corresponding raw evidence packets are required when the mode requires
  them, byte/role/raw-hash checked and exhaustively listed as opaque. Their
  exact actual owner-codec/expectation/ledger links remain later mandatory
  adapter work before launch, not optional validation omitted after success.
- Mode-request, inner input, launch/release packet, domain result, installed
  metadata/inventory and authority/source/barrier/kernel raw blobs are retained
  byte-for-byte, raw-hash/role-size checked and listed as opaque-owner values.
  Their nested owning schemas, execution semantics and authenticity are not
  inferred from a role label, matching digest or caller-supplied view.
- The local inventory/reference shapes and all owned event fields remain closed;
  the explicit opaque owner subtrees are the only local-schema boundary. No
  unknown top-level field is accepted under the word "opaque". Every opaque
  object embedded in local JSON remains subject to that containing record's
  strict canonical primitive/resource guards. An opaque raw blob may instead
  be a binary framed packet or arbitrary failure bytes: check its exact raw
  digest and role-specific byte cap, do not JSON-decode it based on its prefix.
- `opaque_owner_values` is a required exhaustive list of these locations, not
  an optional acceptance override. The later concrete store/controller must
  invoke the real owning codecs/adapters and independently establish current
  trust, source and runtime facts. Missing or rejecting adapters block launch/
  admission; no caller can clear this list or provide a validator callback.

The exhaustive location algorithm is fixed, not caller metadata:

| Referenced value | Opaque role and location |
|---|---|
| Manifest metadata in its fixed four-member order | Whole raw blobs: `installation`, `controller-profile`, `domain-profile`, `runtime-inventory` |
| Manifest request/input/launch | Whole raw blobs: `mode-request`, `mode-input`, `launch-packet` |
| Manifest nonnull parent_barrier | Whole raw blob: `parent-barrier` |
| Every initial/fresh prerequisite's nonnull admission member | Its prerequisite record digest and field path `("admission",)` with role `admission` |
| Every authority-inventory objects member | Whole raw blob with the exact corresponding six-role literal |
| Every release-intent/released release ref | Whole raw blob: `release-packet` |
| Every nonnull domain-exited domain_result ref | Whole raw blob: `domain-result` |
| Every kernel sample's raw refs and nonnull failed/orphaned kernel ref | Whole raw blobs: `kernel-raw` |
| Every refusal evidence ref except its selected valid primary graph | Whole raw blob: `refusal-raw` |

No reference traversal occurs inside these opaque raw packets. Local owned
records and PE records use their explicit decoded reference fields only.
Deduplicate identical `(role,containing_sha256,field_path)` triples, while
retaining different roles for the same raw bytes. Return tuples ordered first
by OwnerRole's declaration order, then digest bytes, then field-path component
order (string tag before integer tag; UTF-8 byte ordering for strings and
numeric ordering for indices, shorter equal prefix first). The implementation
cannot omit an opaque location because another role validated the same bytes.

Thus the module does **not** validate complete accepted-input envelopes,
signature/key/admission policy, live tenant/work/capture authority, external
restore checkpoints, actual artifact measurement, mode-input semantics, kernel
isolation, daemon/container ownership, native cleanup or physical capacity.
It does not implement §12's DB barrier or unresolved pre-reservation recovery
release. Declared `admitted` records can be structurally consistent without any
of those truths being established; reports must retain `local-structure-only`.

`JournalValidationError` has a fixed reason only:
`invalid-type | limit | noncanonical | schema | reference | order | conflict`.
Messages contain no raw data/paths; original causes stay private. Expected
malformed input fails through this type. Preserve actual interruptions as
interruptions, not validation success. No silent downgrade, best-effort record
drop or synthetic placeholder fills a missing reference.

### 16.6 API review and implementation gate

Before code, root/peer must review this exact API and especially the explicit
opaque-owner limit. Required pure tests cover every bound, constructor mutation,
poison callback, canonical/duplicate rule, all declared phase branches and
negative transitions, same-boot/sticky recovery, exact refusal closure, fresh
authority inventories, observed-vs-intended differences and missing/unknown
retention. Include forged `kind="admitted"` data proving the result remains
structural-only, never a durable/visible/installed/authorized carrier.

Accounting controls must cover identical requested/actual invocation bytes,
one CallRef reused by several phase records, fresh versus identically reused
prerequisite observations, and identical bytes in two stream roles. Assert
logical counts are unchanged by internal reference/traversal order or
validation-cache hits. Public blob inputs remain digest-sorted; unsorted
public inputs are rejected rather than normalized by this control.
For nonattached results separately assert: null outcome increments only missing
outcome; present outcome with null stdout/stderr increments only missing output
for those streams; present output with null retention increments only unknown
retention while preserving its observed bytes; known-empty present output
increments none of those counters and retains its genuine zero/empty hash.
An unmatched intent increments call_count but none of the completed-result
absence counters. Reusing any result via later CallRefs cannot increment them.
Chronology controls include exact expiration, future observation, a delayed
release acknowledgment followed by honest failure (not admission), and known
pin erasure/mismatch with retained failure/cleanup evidence.
Call-partition controls cover12ordinary+4cleanup, rejection of13ordinary,
more than4cleanup within16total, rejection of17total and same-boot recovery
without count replenishment. Actual result overruns remain retained bounded
failure evidence; they do not authorize an extra ordinary intent.

No FS/runtime test is part of these two files. Normal configured unit markers,
independent code review, full gates and canonical repository review remain
required after a separate explicit code allocation. This addendum itself
does not allocate implementation or complete any RES acceptance item.

## 17. Pure journal implementation and correction checkpoint — September 25

The proposal/pending labels above preserve their original review chronology.
Root subsequently approved the exact pure API and allocated only this contract,
the two companion clarification deltas, `tools/worker/runtime_journal.py` and
`tests/unit/test_runtime_journal.py`. The runtime controller, physical store,
DB barrier, installer and current-authority adapters were not allocated by that
approval. Independent full-source/security review and final correction review
are now complete for the pure slice; repository acceptance remains pending.

The implementation supplies the four pure functions from §16. It uses the
actual public process-evidence codec and exact detached record types, bounded
canonical bytes, a bounded reference graph and explicit opaque-owner
obligations. Every result remains `local-structure-only`. A caller's declared
`admitted` phase does not establish installed, current, durable or executable
authority. No filesystem, clock, process, Docker or database call is made.

Root's five unchanged chronology controls initially failed: the kernel mount
target `/` was rejected; samples could predate the supplied start or postdate
their event; and publication timestamps could fall outside intent/acknowledgment.
The fixed contract admits `/` only as observed kernel mount data, not a control
path, and validates the supplied inclusive time intervals without reading a
clock. The valid configured red is retained in
`/tmp/scanipy-runtime-journal-root-chronology-configured-red.xml`.

Independent review then found three concrete state-machine defects, each
retained in an unchanged external reproducer before correction:

- Actual registered-spool cap overruns did not set sticky failure. Collection
  now checks stream and combined caps, retaining all supplied bounded bytes
  without rewriting process-result counters or inferring EOF/custody.
- An exact historical released acknowledgment was rejected after a retained
  failure. It now records history subject to the other phase/reference/time/
  image guards; failure remains sticky and blocks new productive/admitted work.
- A first attached-spool registration could occur after supplied `started`.
  It now requires the pre-start state; cleanup/recovery calls retain their own
  registration paths. This does not prove actual native process chronology.

Final frozen source SHA256:
`51e56785a7ef0d19ad9fc67f677161a69a93729217cd98570cfecd5b152b705e`;
unit-test SHA256:
`b707390028c83aff0879af3e19d9be17bdf12be601fd5f4c704e13f104bf6ba6`.
Final configured focus is **331 passed, zero failures/errors/skips**: 309
repository cases plus 22 unchanged external controls. Python 3.11: 23.096
seconds, `/tmp/scanipy-runtime-journal-corrections-331-311.xml`; Python 3.12:
18.245 seconds, `/tmp/scanipy-runtime-journal-corrections-331-312.xml`.
Independent rerun: 22.960 seconds,
`/tmp/scanipy-runtime-journal-peer-final-331.xml`. Repeated and earlier runs
are overlapping checkpoints, not additive unique coverage. Scoped Ruff/format,
strict module mypy and whitespace checks passed. Scratch reports are diagnostics,
not a public immutable acceptance archive.

Before acceptance: integrate the reviewed dependencies/current main, run the
configured combined full suite and normal hooks, then obtain exact-head remote
tests and canonical `claude-review` SUCCESS/final APPROVE. All RES implementation
and operational TODOs not actually implemented by this pure slice remain open;
none of full R16, issue #400, C01–C18 or G0–G3 is accepted here.

## 18. Current non-event byte-custody core contract — September 26

Status: **root-approved implementation contract; source allocation recorded in 18.11.**
Root approved the engineering design in the final 220-line non-event allocation
at SHA256 `e06359aa738037ffd3e56cf0903314be6c9586bfc06567ce406753d0b5f0c107`;
independent review confirmed its five corrections. This section consolidates
that design and the compatible API01 wrapper/lifetime rules into the repository.
It is the current contract for this narrow next slice, not evidence that it is
implemented. Sections 1–17 remain preserved historical design/checkpoint text.

The only intended source allocation is new `tools/worker/runtime_evidence.py`,
new `tests/unit/test_runtime_evidence.py`, and this document, under root-owned
#400/#362. Root approved this contract before allocating either source file.
Do not change the actual journal, PE, transport, inventory or owner schemas to
make the new core pass. Only trusted hermetic tests in fresh task-owned temporary
directories are allowed; no real installation, native launch, database change,
image operation or operational constructor is authorized here.

### 18.1 Scope, owner types and explicit supersessions

The useful initial slice publishes complete initial manifests/refusals and
their required immutable members, with all four existing modes and existing
byte ceilings. It is not a metadata-only or reduced-intent substitute. It uses
the actual journal `ParsedJournalRecord`, `decode_journal_record` and
`encode_journal_record`, and PE `EvidenceBlob`, `StoredObject` and public
`decode_error_graph`. No private owner helper, copied wire validator, invented
owner record or caller-selected validator is permitted.

This section supersedes these earlier proposals for this slice only:

- Generic `new_scope`, `publish_blob` and scope-only spool-registration
  publication are replaced by immutable parent plans and closed selectors.
- Completed publication intents are permanently retained, replacing section 6's
  intent-retirement rule. Final bytes alone cannot identify an old publication
  ID; deleting its only mapping contradicted exact-ID replay. No hidden index
  or uncharged extra intent is introduced.
- Initial plan counts are 12/13/16/17 below, not the obsolete generic
  273-intent calculation. The 129-credit example is future-state accounting,
  not a reachable initial same-scope acceptance case.
- A single nonblocking writer-lock attempt replaces a lock retry loop.
- Refusal finalization permits 24 bounded owner calls, not the proposed 16;
  sixteen legitimate graph candidates plus journal checks require that change.

Event/phase/history publication, full-history reading/replay, spool collection
and registration publication remain unallocated. Registration needs its actual
call/event owner and `intent_event_digest`; scope identity cannot replace them.
No `RuntimeEvidenceRoot`, `AttemptReadback`, `JournalReceipt`, `Durable*`,
capacity qualification or actual attempt-recovery authority is implemented by
this slice. No HTTP/queue/CLI/environment/test switch enables its private
diagnostic publisher as an operational fallback.

### 18.2 New immutable wrappers and callable surface

The new module, not an existing owner, owns these exact frozen/slotted,
non-content-repr wrappers. They introduce no new wire format:

```text
RuntimeEvidenceInstallation(
 deployment_id:UUID, store_id:UUID,
 artifact_domain:Literal['operational','diagnostic'],
 evidence_root:PosixPath, host_work_root:PosixPath,
 owner_uid:int, owner_gid:int, root_record_sha256:bytes32)
_ScopeKey(kind:Literal['attempt','refusal'], id:UUID)
_PublicationKey(scope:_ScopeKey, publication_id:UUID)
_FileStamp(device:int,inode:int,full_mode:int,uid:int,gid:int,nlink:int,
 size:int,mtime_ns:int,ctime_ns:int)
MemberSelector(kind:Literal['metadata','request','input','launch',
 'prerequisite','authority-inventory','parent-barrier','authority',
 'refusal-evidence'], ordinal:int)
VisiblePublication(
 visibility:Literal['verified-visible-file'], key:_PublicationKey,
 intent:ParsedJournalRecord, file:EvidenceBlob,
 record:ParsedJournalRecord|None, observation:_FileStamp)
_PublicationAck(
 completion:Literal['local-fsync-readback'], publication:VisiblePublication,
 disposition:Literal['new','exact-recovery'])
```

`EvidenceBlob` remains the actual two-field `data:bytes, sha256:bytes` owner
type. `record=None` denotes a raw blob; manifest/refusal/intent data uses the
actual journal decoder result. `_FileStamp` contains actual `fstat` facts, not
a second serialized FileObservation. A returned ack describes this completed
local protocol only; it is not a cross-restart token, current permission or
proof that the same operation was acknowledged before a crash. A reader never
constructs an ack. Later consumption independently checks actual bytes again.

Every entrypoint snapshots all consumed fields once through class-owned access
before I/O, then uses only detached validated primitives. Exact types exclude
subclasses, bool-as-int, custom Mapping/iterable and instance methods. UUIDs
require their exact integer slot in `[0,2**128)`, then a fresh UUID. Paths use
bounded exact primitive storage snapshots for the supported CPython 3.11/3.12
layouts before formatting or cached strings, then a fresh normalized PosixPath
within 4096 UTF-8 bytes. All integers use signed64 bounds and tighter listed
caps; identities/sizes are nonnegative, inode/nlink positive, installation
UID/GID are 1..2147483647, and bytes32 is exact bytes of length 32. No caller FD,
opener, executor, clock, authority callback or forged receipt selects a name or
substitutes for raw-byte validation.

```text
_open_diagnostic_publisher(installation:RuntimeEvidenceInstallation)
 -> _DiagnosticPublisher
_DiagnosticPublisher.begin_manifest(
 key:_ScopeKey, publication_id:UUID, data:bytes) -> _PlannedScope
_DiagnosticPublisher.begin_refusal(
 key:_ScopeKey, publication_id:UUID, data:bytes) -> _PlannedScope
_PlannedScope.publish_member(
 publication_id:UUID, selector:MemberSelector, blob:EvidenceBlob)
 -> _PublicationAck
_PlannedScope.finalize() -> _PublicationAck
_DiagnosticPublisher.recover_publication(key:_PublicationKey) -> _PublicationAck
_DiagnosticPublisher.close() -> None
_PlannedScope.close() -> None
open_runtime_publication_reader(installation:RuntimeEvidenceInstallation)
 -> RuntimePublicationReader
RuntimePublicationReader.read_publication(key:_PublicationKey)
 -> VisiblePublication
RuntimePublicationReader.close() -> None
```

Both opening entrypoints require the diagnostic domain; an operational
installation is rejected, not redirected. `begin_*` returns only a private
same-root handle, never an ack. It creates a fresh fixed scope/parent plan
exclusively or performs the exact complete-parent rebind in 18.5. No method
accepts a role, destination, arbitrary relative path or arbitrary event.

`RuntimePublicationError.reason` is exactly one of `invalid-input`,
`unsafe-path`, `conflict`, `limit`, `deadline`, `storage`, `cleanup-incomplete`,
`unsupported`. Messages/reprs are fixed and never format paths, bytes or an
arbitrary exception. Preserve private original causes/contexts and cleanup
failures. Original `KeyboardInterrupt`/`SystemExit` objects remain primary,
including during cleanup; do not invoke exception truth/formatting callbacks.
Never retry a close-failed numeric FD: it may already be closed and reused.
An uncertain write/close/sync returns no ack and never claims rollback or
failed-empty effects. Retention failure must not erase the earlier failure.

If an operation fails after mutation or sync effects may have begun, invalidate
that held writer for further operations except once-only owned close. A fresh
diagnostic open must perform bounded read/sync-only reconciliation; it grants
no repair/adoption or earlier acknowledgment. A pre-I/O argument rejection may
leave the handle usable, but never refunds work, deadlines or retained credit.

### 18.3 Installed root, fixed names and held-descriptor lifetime

Open existing `root.json` through held nofollow/nonblocking descriptors and the
actual journal `root` codec (4096 bytes). Its exact fields remain `schema`,
`deployment_id`, `store_id`, `artifact_domain`, `owner_uid`, `owner_gid`,
`evidence_root`, `host_work_root`, `format`; the literals are
`scanipy-runtime-evidence-root/1` and `scanipy-runtime-journal/1`. Independently
verify raw SHA256 and every installation field. Supplied pins establish equality
only, not their provenance/currentness. No bootstrap, highest-record search,
environment/home discovery, `resolve`, glob or adoption of an unknown store.

Actual nonroot effective UID/GID must match installation. Evidence/work roots
are disjoint owner UID/GID 0700. Walk nofollow directories with owned descriptors;
allow root/owner ancestors without group/other write except literal root-owned
sticky `/tmp`. Ancestors retain device/inode/full-mode/UID/GID security identity,
not unrelated sibling timestamps; measured roots/descendants/leaves retain full
stamps. Never chmod/chown an inherited object to make it pass.

Hold evidence/work roots, fixed direct-parent directories and regular one-link
owner 0600 `writer.lock` for publisher lifetime. Attempt exactly one exclusive
nonblocking `flock`; a second writer fails without effects. A bounded internal
thread lock serializes methods. At most one bound planned scope exists per
publisher. Child descriptors are tracked before any fallible parent close,
closed once, and invalidated on root close. Scope close/rebind does not reset
root-owned cumulative scope counters, refund residues or release a DB hold.
Work root is verified/held but no CLI/work/spool files are allocated here.

The reader owns its own verified descriptors, takes no writer lock and writes
nothing. It reads one exact final publication, its retained intent and fixed
parent membership, with pre/post identity and full EOF/hash checks. A changing
or ambiguous name yields no result. This is not full member/history closure or
proof of the writer's earlier directory fsync; no verified-visible history
report or `Durable*` acknowledgment is returned.

The existing publication-intent codec owns exactly `schema`, `publication_id`,
`store_id`, `scope_kind`, `scope_id`, `role`, `destination`, `size`, `sha256`,
`expected_previous_event_digest`. Build its actual PE `StoredObject`, encode
through the public owner, then independently decode retained raw bytes. Schema
is `scanipy-runtime-publication-intent/1`; store/scope come from held bindings,
size/hash from actual bytes, and predecessor is null in this non-event subset.
Only these method-derived roles/destinations are enabled:

| Role | Fixed destination | Actual record or member limit |
|---|---|---|
| manifest | `manifest.json` | journal manifest, 16384 bytes |
| refusal | `refusal.json` | journal refusal, 16384 bytes |
| blob | `blobs/<64-lowercase-hex raw hash>` | resolved selector limit below |

Staging is exactly `staging/<publication UUID>.json` plus `.data`; no caller
filename. Relative names are at most 128 ASCII bytes. Manifest deployment ID,
store ID and artifact domain must equal held root, and attempt ID equals its
attempt scope. Refusal ID equals its refusal scope; refusal has no domain field
to invent. Initial scopes contain no event/registration/work payload. Reject
such future or unexplained histories rather than ignoring them as safe input.

### 18.4 Parent-owned selectors, linkage and logical role accounting

The parent is retained immutable prospective manifest/refusal bytes, not an
independently supplied ParsedJournalRecord, JSON pointer or content type.
Snapshot `MemberSelector` before effects; its exact string/int pair is closed:

| Kind / ordinal | Actual parent location | Logical class / maximum bytes |
|---|---|---|
| metadata / 0..3 | `manifest.metadata[i].blob`, exact named-role order | raw / 65536, 131072, 65536, 8388608 respectively |
| request / 0 | `manifest.request` | metadata / 65536 |
| input / 0 | `manifest.input` | raw / verifier 2621440, syntax 263244 |
| launch / 0 | `manifest.launch` | metadata / 65536 |
| prerequisite / 0 | `manifest.initial_prerequisite` | metadata / 16384 |
| authority-inventory / 0 | `manifest.authority_inventory` | metadata / 16384 |
| parent-barrier / 0 | `manifest.parent_barrier` | metadata / 16384; execution/syntax only |
| authority / 0..5 | retained inventory's role-selected `objects` row | raw / combined 1048576 |
| refusal-evidence / 0..15 | `refusal.available_evidence[i]` | actual owner classification below / each 8388608 |

Metadata role order is exactly `installation`, `controller-profile`,
`domain-profile`, `inventory`; the last one's opaque owner is runtime-inventory.
Mode/action mappings are `verifier-historical`/`audit-historical`,
`verifier-publication`/`publish-builtin-preflight`,
`verifier-execution`/`verify-execution`, `python-syntax`/`parse-python`.
The shorter mode names in the arithmetic table below denote these same modes.

Authority ordinals mean authentication, scope, admission, execution-authorization,
capture-lease, content-verification, not filtered-array positions. An absent
role rejects. Decode retained prerequisite/inventory before authority members;
require actual mode/action, required roles/order, and inventory's prerequisite
reference equal to the manifest reference. After both exist, verify all actual
raw-reference links and the supplied-data relation
`prerequisite.observed_at <= manifest.created_at < prerequisite.valid_until`.
This is not an actual-clock or current-authority check. Never equate a domain
digest with a raw hash or invent an admission raw-digest field.

Required inventory roles begin with authentication/scope, then admission only
when the prerequisite's admission is nonnull, execution-authorization plus
capture-lease only when its execution-authorization digest is nonnull, and
content-verification only when its evidence raw hash is nonnull. Preserve that
fixed order. Match authentication, scope, capture-lease and content-verification
BlobRef hashes to their actual prerequisite `*_evidence_sha256` fields.
Admission and execution-authorization semantic/domain linkage remains an
explicit current-owner obligation, not a raw-hash equality invented here.

Each selector resolves to an actual parent-owned BlobRef, with exact
size/hash/role cap agreement. Logical `(scope,kind,ordinal)` differs from physical
raw-hash destination. Exact selector replay adds no logical occurrence, but
all reread/hash work is charged. Distinct actual roles sharing bytes incur both
role charges while retaining one explained inode. No unreferenced raw member.
Request/launch/barrier are conservatively metadata, not raw exemptions; installed
inventory/input/authority packets remain raw even if their encoding is JSON.
At begin reserve all direct planned lengths plus the 1MiB authority allowance;
replace that allowance with the exact closed inventory total only after its
durable readback. Dedup never erases logical role work.

Before `begin_refusal` has effects, require unique `available_evidence` raw
hashes, even with null primary error. Manifest cross-role dedup is unchanged.
Finalization reads every member. With nonnull primary, feed every candidate
of at most 8192 bytes to actual public `decode_error_graph`; require exactly
one successfully decoded matching `error_id`, without stopping at the first
match. That matching graph is metadata. Malformed/nonmatching/large members
are opaque refusal-raw, following the actual owner. Null primary needs no graph
match or graph decoder call. Reserve 8192 metadata until association is known.
This validates bytes/association, never that an exception actually occurred.

### 18.5 Durable staged parent, rebind and final publication

Exactly one parent publication intent per scope is the plan; no new plan wire.
Exclusively write its existing intent and paired parent data. For EACH inode:
fsync, fchmod 0400, fsync again; fsync staging; independently read complete EOF
and verify expected bytes/hash/identity before any child publication. No final
parent name exists yet. The same parent data inode becomes final; no second copy.

After bounded root reconciliation, `begin_*` may rebind ONLY a complete sealed
parent+intent pair with the same scope, publication ID, raw bytes/hash, owned
identities and fixed membership. Staged or already-final parent is allowed;
independently verify both intent and parent. Return a private handle, no ack;
it may complete remaining planned members. Missing/partial/unknown parent is
unavailable to begin, member publication and recovery: no adoption or repair.
Complete-parent recovery cannot bypass required child closure.

Dependencies are manifest to prerequisite/inventory to authority members,
manifest to its other direct members, and refusal to its evidence. Crosslink
prerequisite/inventory after both are retained. Reject cycles among these
documented references; BlobRef-looking opaque content does not create an edge.
Installed inventory metadata remains opaque raw bytes, not another authority
inventory. Private derived states are `PLAN_STAGED -> PARTIAL -> READY ->
PARENT_PUBLISHED`; they are not a new persisted enum or phase event.

`finalize` requires all referenced members, exact parent readback, all local
links, unique refusal association and quotas before linking the parent. There
is no reserved/runtime phase, domain acceptance or DB receipt. Recovery derives
blob membership from retained parent references, never the generic intent role.
Parent recovery has the same entire closure requirement as finalization.

For every member/final parent use section 6's exclusive no-overwrite link
protocol. Verify the two known staging/final names refer to the held inode;
unlink only its validated owned staging-data name; fsync the still-held inode
after link-count change and both containing directories. Require final 0400,
regular one-link file, independently reopened full EOF/raw hash and stable
pre/post stamps/membership. Preserve uncertain effects and original failures;
never delete accepted bytes, repair foreign objects or infer rollback.

Retain completed intent 0400 at its existing staging UUID.json name and fsync
it/directory. One ID owns one destination; a new ID targeting an existing
destination rejects even for equal bytes. Known hash reuse names the original
mapping, not another dedup intent. Only after the entire owned sync/readback
protocol return `_PublicationAck`; exact recovery repeats required checks/syncs
and does not infer an earlier acknowledgment. Visible readers never ack.

### 18.6 Permanent intent credit, cold reconciliation and mode feasibility

Recomputable metadata accounting is:

```text
M = other logical metadata + actual completed-intent lengths
    + 4096 * unresolved publications + planned unspent credits
```

Reserve 4096 before effects. Replace that credit with actual intent length only
after the whole owned sync/readback protocol. Retained intent bytes, inodes and
names remain charged permanently. Close/rebind gives no refund. At most 16
pending residues; active/completed IDs share the plan's actual publication count,
not that count plus 16 completed IDs. Keep 512KiB metadata, 32MiB retained and
64MiB proposed transient ceilings, with 131072 cleanup-metadata and 65536
terminal-metadata reserves partitioned inside them, not added capacity.
The existing `cleanup_retained_bytes=2097152` partition also remains inside the
32MiB retained ceiling; it is not extra storage or reclaimable ordinary payload.

The `129 * 4096 = 528384` example remains a future/full-state accounting
falsifier, NOT a reachable initial same-scope 17-intent positive. Cold
reconciliation is READ/SYNC-ONLY before new-write admission: no create, link,
unlink, chmod or ack. Fsync and independently verify exact final 0400/nlink1
intent/final pairs before using completed-actual credit. Anything requiring
repair retains 4096; quotas still gate later writes/repairs. Stable visible
bytes never prove an earlier durable acknowledgment.

All four required initial modes fit the following conservative upper bounds:
all four metadata blobs, full 1MiB authority, maximum input, no dedup and
522 actual bytes per completed intent. These are arithmetic plan positives,
not an implemented filesystem test or future native-call planner proof.

| Mode | Publications | Initial retained bytes | Metadata bytes |
|---|---:|---:|---:|
| historical | 12 | 12507256 | 186488 |
| publication | 13 | 12507778 | 187010 |
| execution | 16 | 12525728 | 204960 |
| syntax | 17 | 10168054 | 205482 |

Even `205482 + 196608 + 16*4096 = 467626 < 524288`. Refusal jointly limits all
evidence, parent and permanent controls to 32MiB; sixteen times 8MiB is not
admissible. Stage/final hardlinks share one inode but retain both name costs;
separate or partial copies remain charged. These calculations do not prove the
later 16-call/event/output planner, block/inode headroom or backing capacity.

### 18.7 Work, delegated codecs and allocation budgets

Preserve section 5's independent Read/Write/Hash ceilings exactly:

| Scope | Read bytes | Write bytes | Hash bytes |
|---|---:|---:|---:|
| Steady publication/read/recovery | 134217728 | 67108864 | 268435456 |
| Live scope cumulative normal/retry | 8589934592 | 268435456 | 17179869184 |
| Root open/reconciliation | 17179869184 | 67108864 | 34359738368 |

Use at most 64KiB chunks, 128 held FDs, 128-byte relative names and 4096-byte
absolute paths; at most 256 scopes/16384 entries. Observation ceilings remain
512 steady, 131072 root; 4096 whole-attempt reading remains deferred. Pure
bounded argument checks precede internal monotonic start, which precedes all
filesystem work. Steady deadline is 2s, root 35s, including cleanup/finalization;
no retry/rebind/per-file reset or caller clock. The future controller must also
enforce its remaining outer 30s allowance. Blocking kernel work still requires
the separate outer supervisor; a large root may fail 35s and return no handle.

Reserve the next work before its syscall/hash; charge actual transferred bytes,
failed/retried work and EOF attempts. Fail on zero progress instead of spinning.
Direct hashes count actual update bytes. Each actual non-event journal decode
hashes `2*B + len(schema) + 1`; reserve `2*B + 128` before calling. Encode's
internal decode counts too. No `replay_journal`, `validate_refusal`, full-history
helper or arbitrary metering callback is hidden in this allowance.

- Ordinary operations: at most 16 journal-owner calls: plan/inventory/prerequisite
  at most 3, intent encode/readback/recovery at most 6, final rechecks at most 3,
  spare at most 4. Spare is finite, not a retry loop.
- Refusal finalization: at most 24 calls, every 16 possible PE candidates plus
  at most 8 journal calls: parent before/after 2, intent before/after 2, recovery/
  control encode/readback at most 4. This changes a proposed implementation
  call bound only, not any existing RES byte/FD/observation/deadline cap.
- Actual `decode_error_graph` hashes zero bytes. It admits at most 8192 bytes,
  depth 8, 1024 values, 32 nodes, 96 edges, 32 arguments and cumulative encoded
  arguments 2048 bytes. Its at most 32 mini-canonicalizations/base64 operations
  remain real work, not additional public-owner calls or free copies.

Process one decoder/candidate at a time and release intermediate trees before
the next. Proposed conservative allocation reservations: 32768 delegate slots
(`16*V+4096`, V at most 1024), 8192 active-plan slots and 16384 accounting
slots; census is compact bytes. Sequential release stays below 262144 owned
slots. Instrument source-derived temporary slots/copies before implementation
acceptance; this is not total CPython heap/RSS or a caller memory callback.

Read one raw file at a time into one exact-size assembly plus final immutable
bytes, at most `2*N`, never repeated concatenation. Proposed 4MiB census,
8MiB encoded-only cache and two chunks give 76.125MiB at N=32MiB, below a
proposed 96MiB raw-buffer ceiling; initial members are at most 8MiB. Never
cache all decoded scopes. Cache eviction retires no accounting or I/O work.

Proposed steady cumulative byte-copy ceiling is 192MiB: conservatively reserve
2MiB per owner call including UTF-8, canonical JSON, hash-prefix and PE argument/
base64 copies. At 24 calls that is 48MiB; even `4*N` at N=32MiB plus 12MiB
census/cache totals 188MiB. This is a conservative implementation reservation,
not a measured allocator claim. Instrument actual copies and fail rather than
increase limits. Root cumulative-copy reservation is separately
`R + 2MiB*C + 16MiB`, R at most `8GiB+4096`, C at most 32768. RES had no root
copy counter; this new bound does not raise any I/O/hash/peak allowance.

### 18.8 Finite cold census, steady checks and exact-file reading

Retain compact rows of at most 256 bytes/name (at most 4MiB), scope counters
and bounded sorted indices. Enumerate with admission before each name, not an
unbounded `list(scandir)`. Hold root/work/lock/direct parents plus ONE scope's
directories, never every scope's descriptors. Fixed grammar selects expected
type; nofollow/nonblocking open and fstat verify it, without a redundant
DirEntry.stat-plus-open/stat census. Unknown names or linkages reject.

Per scope there are at most 17 intents, 17 final names and 16 staged-data
residues: 50 files. Known stage/final hardlinks share one content read; different
inodes do not. No new-ID copies means partial planned data plus controls still
fit reserved 32MiB unique bytes per scope, at most 8GiB across 256 scopes plus
4096 root bytes. This is the initial non-event namespace, not future copied
spools or a claim that all 64MiB transient states have that read bound.

Proposed root application-OS-attempt schedule: file names F at most 12802,
directories D at most 1284; body reads at most `ceil(8GiB/65536)+F`; at most
7F for open/pre-post-fstat/EOF/fsync/membership/close, 7D for open/pre-post-stat/
scandir/fsync/membership/close, 12288 ancestor-walk calls and 512 fixed calls.
Total is at most 255276, below proposed 262144 attempts. Iterator yields count
as name observations, not separate os.* calls; kernel batching/EINTR is not
bounded by this application-call metric. Instrument actual API attempts.

Use fixed-name priority: intents, parent, prerequisite/inventory, other members.
Perform one content pass after required read/sync identity checks, not a second
8GiB read. Root owner calls are at most 32768; discard each decoded tree/file.
The cold pass is read/sync-only and grants no operation ack or launch permission.

Steady methods validate affected names/held parent stamps against the held
census, update only known own namespace effects, and invalidate on unexpected
drift; do not perform a whole-root rescan under 512 observations. This is not
global leaf-content proof or hostile same-UID/admin concurrency defense.
Consumption/recovery independently rereads the actual leaf bytes. Proposed
8192 steady OS-API attempts include finalization/cleanup, never a reset budget.

Fixed final-file reader uses at most 16 owner calls and the steady budgets;
it returns only `VisiblePublication`. Full history reading/replay remains
unallocated: its permitted 512MiB delegated hash work is not automatically
within RES's 256MiB whole-read allowance. An exact complete helper schedule or
separately reviewed owner accounting seam must close that mismatch. Do not
widen caps or infer actual helper work from a structural report.

### 18.9 Required falsifiers and implementation/operational TODOs

Before local implementation acceptance, require hermetic tests and actual
instrumentation for all of the following; none is claimed passed by this draft:

- Callback-free wrapper/UUID/Path/selector/blob snapshots; wrong exact types,
  poisoned internals, missing roles, wrong order/size/hash and cross-scope IDs.
- All four maximum initial modes, full-capacity member retention, distinct
  roles sharing bytes without logical discounts, cycles and unreferenced bytes.
- Refusal's 16 candidates, malformed/nonmatching graphs, exactly-one match,
  duplicate raw hashes with null/non-null primary and no early candidate exit.
- Exact complete sealed parent rebind after reconciliation; missing, partial,
  changed, foreign or unknown parent/intent rejection; no parent-recovery
  missing-child bypass; held-root deployment/store/domain and time mismatches.
- Permanent-ID replay, new-ID/equal-destination conflict, retained actual
  intent charges, pessimistic unresolved credits and no close/rebind refund.
  Test future 129-credit accounting separately from initial-mode acceptance.
- Every write/link/unlink/chmod/fsync/read/close boundary, original interruption
  plus cleanup failure, uncertain descriptor reuse and no false acknowledgment.
  Reader-visible versus writer-acknowledged files must remain distinct.
- Maximum compact census/name/FD/observation/OS-attempt limits, actual owner
  call/hash/copy/temporary-slot schedules, deadline/finalization exhaustion,
  affected-name drift and no unsupported full-history acceptance.

Keep full configured tests, normal hooks, independent review, exact-head remote
tests and canonical SUCCESS/final APPROVE as later gates. A local arithmetic
positive or stubbed fault test is not filesystem/power-loss qualification.

Operational prerequisites remain hard, separate TODOs: qualified capacity and
enforced evidence/work isolation; actual installed root/operator provenance;
six-role current owner closure and fresh policy/lease decisions; AL/DB owner
bridges, DB-BAR work exclusion/capture retirement/old-parent exclusion and
claim-before-filesystem-reservation cleanup; full reader; event/call/registration/
spool owners; actual controller/supervisor; native static-only/source/coverage
evidence. AL command parsing or this primitive cannot manufacture any of them.
The later real factory may reuse private owned-inode mechanisms only after
those prerequisites. It must never promote a diagnostic handle/ack or install
a diagnostic fallback. No full R-task, #400, C01–C18 or G0–G3 is accepted here.

### 18.10 Integration checkpoint for this draft

Isolated branch `bhmea/runtime-evidence-core` began at controller
`0dbee6ef97409b9dda7fcc38545595edefc82348`. Normal conflict-free merges included
accepted main `95fa5d1991cbb65b89569c399c51186ba44cae9e` as
`53211d5d2a82b94da68274c81762a13289a4a465`, then reviewed inventory
`40ba98afa353428e96add873cdecc52b84b6a0e1` as
`573b0a5ea0551e98f9decac4f275a1071ff5dcf7`. The first merge's 12 incoming paths
were byte-equal to accepted main; the second changed ancestry only. Both normal
commit hooks completed, with merge-only file gates reporting no applicable
changed/conflict files; these are not fresh broad-suite results. No baseline
union or conflict resolution was necessary.

Before this appendix, tree `9b61238f31d7eb102326ec196cb5f12a0a784c4d` exactly
matched root's separately integrated tree. Existing first 2137 document lines
retain SHA256 `284ef321dfda7f3d42cbade462e04fb0c9046917db4dfd63a328580c98f07e38`.
Actual unchanged source pins are journal
`51e56785a7ef0d19ad9fc67f677161a69a93729217cd98570cfecd5b152b705e`, PE
`601fef04b641b28c6f7e3abe948490bd7507287c103194a42b2cc7f943ac0fe8`, inventory
`8accd2e2e32cd12ef90f0bb29946ad8197cc1a56c895f848525a44f40e87d05a`.
No source or tests changed. Root's separate equivalent-tree 638
focused passes (309 journal, 99 inventory, 26 ledger, 204 Git; 31.83s,
`/tmp/scanipy-runtime-journal-git-main-focused.xml`) are root's prior-tree
observation, not a new test of this appendix or a complete acceptance suite.
This is the preimplementation checkpoint; the subsequent scoped approval below
does not relabel it as a test of implemented filesystem behavior.

### 18.11 Root review and exact source allocation

2026-09-26 PKT / September 25 UTC. Root read all 511 appended contract lines
and independently verified the original 2137 lines unchanged. An independent
reviewer read the entire addition against the complete approved 220-line
allocation, API01 and actual journal/PE owner codecs, approving draft SHA256
`08a15b0273f29622f15e3833563105f17dabae2cb3e7600d561a378bdcec9051`.
Its nonblocking suggestion is incorporated above: explicitly repeat the existing
2MiB cleanup-retention partition. No owner schema or budget is changed.

Root allocates only the two named new source/test files and this append-only
contract to the corpus implementation agent in this independent worktree.
Implement the usable complete non-event custody core, not placeholder or
metadata-only methods. Prove the real call/copy/slot/OS schedules in trusted
unit tests and report any infeasible bound or unspecified behavior before
changing scope, counters or owner APIs. Preserve all failure/recovery evidence.

Tests may use isolated temporary roots and inert bytes, never the user's
application/database/volumes or target program execution. Full suites, normal
pre-push and remote actions remain root-coordinated; independent implementation
review and all exact-head repository gates are still required. No diagnostic
result enables the actual controller or supplies operational authority.

### 18.12 First implementation review checkpoint — not operational acceptance

The isolated implementation adds only `tools/worker/runtime_evidence.py` and
`tests/unit/test_runtime_evidence.py`, plus this append-only contract. Source
SHA256 is `2fd1297a3b664689f2219693ac0ee8524cf419119977b83bf42037e0d18340f0`;
test SHA256 is `3a5093955dc8bab301cc652def4f10ff32f4a44399d810cf40b6a9869dbee16c`.
Both are frozen for independent review, not committed or published. The first
2137 document lines remain byte-exact at the hash recorded in 18.10.

Actual configured focused results on that frozen pair:

- CPython 3.11.16: 110 passed, zero failures/errors/skips, 12.934s;
  `/tmp/scanipy-res-core-frozen-110-311.xml`.
- CPython 3.12.14: the same 110 passed, zero failures/errors/skips, 12.391s;
  `/tmp/scanipy-res-core-frozen-110-312.xml`.
- Ruff check/format, strict source mypy and `git diff --check` pass. Every new
  test is under the module's actual `pytest.mark.unit`; the configured
  `-m 'unit or invariant'` collection selects exactly 110. No skip/gate changed.

These are overlapping controls, not 220 different requirements. They exercise
all four modes through publication/readback/rebind/recovery; maximum opaque
metadata/input/authority sizes; all sixteen refusal graph candidates; exact
identity/selector snapshots; logical-versus-physical duplicate accounting;
permanent-ID and future-only 129-credit negatives; a real 256-scope cold pass;
257-scope refusal; actual read/write/hash counters; finite owner/FD/name/work
reservations; nofollow/mode/namespace refusal; deadlines, interruptions and
selected publication/recovery fault points. They use private temporary roots,
inert bytes and actual owner codecs, not installed profiles or native tools.

The implementation's private counters distinguish actual transferred/read/hash
bytes from conservative delegated reservations and source-derived live-slot/
buffer reservations. Cold census stores fixed 256-byte entries; scope/intent
plans remain bounded and only one scope's descriptors are opened at a time.
Ordinary operations reserve at most sixteen owner calls; refusal finalization
uses the approved twenty-four-call ceiling. Counters are not CPython RSS,
kernel I/O, power-loss proof, capacity qualification or authority attestations.

Preserved failures and corrections:

- `/tmp/scanipy-res-core-security-first.xml`: 60 passed, three failed before
  early stop. These were test expectation errors: `BaseExceptionGroup` legally
  returns an `ExceptionGroup` for all-Exception members. The controls now use
  `isinstance`, still requiring the exact original interrupt and prior cause.
- `/tmp/scanipy-res-core-recovery-first.xml`: 77 passed, one genuine failure at
  source `0c595a370d7953012467f3da751a75f8a8318a318febc9df334e7fd10a791ff4`.
  A cold-verified stage/final prerequisite pair had two links after interrupted
  publication, but plan reload required one and blocked its exact recovery.
  Reload now permits that already-pinned pair for parsing. Actual completed
  parent closure still requires one-link member files. Both unchanged recovery
  vectors passed in `/tmp/scanipy-res-core-pair-recovery-green.xml`.
- `/tmp/scanipy-res-core-path-312-first.xml`: one genuine failure at source
  `b531111dd061be0de16cf49204d6c6b57784d84309ed994364d816919bc58b86`.
  Legitimate 3.12 `_raw_paths` constructor fragments were initially rejected.
  Bounded exact-fragment reconstruction corrected that layout without calling
  poisoned cached formatting; the unchanged four-mode 3.12 controls then passed
  in `/tmp/scanipy-res-core-path-312-green.xml`.
- One targeted retry used a mistyped temporary interpreter path and exited 127
  before pytest. It is a tooling error, not a product failure or passing test.

Independent complete implementation review and any resulting falsifiers remain
pending. Selected fault controls do not claim every possible syscall-position
interleaving or storage power-loss state has been exhaustively exercised.
Full configured suites, normal hooks, exact-head remote checks and canonical
approval have not run for this source. All physical-installation, current-owner,
DB barrier, full-reader/event/spool/controller and native prerequisites in 18.9
remain unimplemented or separately unaccepted. No full task or gate changes.

### 18.13 Root lifetime correction — independent race retained

Root read the entire initial 1818-line implementation, 1168-line test module
and section 18 against the actual owner boundaries. Independent accounting and
recovery review continues separately. The initial source/test hashes and 110-case
results in 18.12 remain attributed to that frozen checkpoint.

A deterministic real-thread scheduling falsifier demonstrated a genuine race:
`begin_*` assigned `core.active` after its operation released the internal lock.
A second caller could finish another begin in that gap. Both callers received a
private scope handle and two scope directories were created before the first
call overwrote the second handle's active status. This violated the single-bound-
scope lifetime contract; it did not grant operational authority.

The unchanged external falsifier is retained at
`/tmp/scanipy-res-root-review-sB5ezz4S/test_root_concurrency.py`. Its first run
failed once (with outside-root pytest marker warnings); the explicit configured
repeat also failed once, zero errors/skips, 0.280s:
`/tmp/scanipy-res-root-concurrency-configured-before.xml`. Source was the frozen
`2fd1297a` checkpoint. These are repeated observations of one defect, not two
independent defects. Original completed filesystem effects were not erased.

The correction keeps the existing single nonblocking lock and all numeric,
wire, ownership and syscall boundaries. Closed/invalidated state is now checked
after acquiring that lock; begin rechecks and commits its active handle before
unlocking. Scope methods recheck their lifetime after acquisition, and scope
close changes lifetime under the same lock. A failed operation restores only
its prior private active-handle state before unlocking: no bytes, work credits,
deadlines or uncertain effects are rolled back or refunded. Once-only descriptor
cleanup and post-effect writer invalidation remain unchanged.

Five new repository controls cover double begin, publisher close between
precheck/acquisition, scope close during an owned operation, and both member and
finalize calls whose scope closes before acquisition. The original independent
double-begin falsifier remains unchanged and also passes. Corrected source SHA256:
`2efe26dd6b78fa6eeb0610b3c5f38992ac1031bc8dec5a8c7b48fa44ce1bd4e1`;
test SHA256:
`94eb0c478723936a96c8bb2cd43a30cdc4ae589690f84822e3d08d347effb9db`.

Actual configured focused results on these bytes:

- CPython 3.11.16: 116 passed, zero errors/failures/skips, 13.843s;
  `/tmp/scanipy-res-root-lifetime-combined-311.xml`.
- CPython 3.12.14: the same 116 passed, zero errors/failures/skips, 11.777s;
  `/tmp/scanipy-res-root-lifetime-combined-312.xml`.
- Each selection is 115 repository cases plus the one external race control;
  the duplicate mechanism is not additional independent coverage. The five
  lifetime cases alone passed in 0.642s before the final static-only cleanup.
- Ruff and formatting pass. Initial strict mypy rejected a redundant pre-lock
  closed-state check as making the later check unreachable; removing that
  unsynchronized early check, without a suppression, made strict mypy pass.

This is a corrected local checkpoint, not final RES acceptance. Complete the
independent accounting/recovery review; cover every actual publication/recovery
write/link/unlink/chmod/fsync/read/close fault position required by 18.9; test the
combined accepted tree; then run normal hooks, remote checks and canonical review.
All installation, capacity, authority, full-reader/event/spool/controller, DB-BAR
and native-static-analysis prerequisites remain separate open action items.

### 18.14 Independent stored-state and cleanup corrections

The subsequent independent review retained five genuine failures against the
`2efe26dd` source from 18.13, not against the corrected source below:

- `/tmp/scanipy-res-peer-drift-red.xml`: two failed controls, 0.219s. Changed
  retained leaf bytes and unexpected directory membership were detected during
  finalization, but the old writer remained usable for a different scope.
- `/tmp/scanipy-res-peer-close-red.xml`: two failed controls, 0.189s. A read-only
  owned-file close raised before or after the actual close, but the writer
  remained usable. These are two descriptor-close timings, not an observed
  iterator-close failure.
- `/tmp/scanipy-res-peer-priority-red.xml`: one failed control, 0.595s. Reversed
  publication UUIDs drove cold member reads before the required prerequisite
  then authority-inventory priority.

Root corrected only the already-allocated source. A private stored-drift marker
distinguishes held stamp/name/hash/EOF contradictions from ordinary invalid
caller conflicts. Detected stored drift, runtime storage/unsafe failures and
uncertain descriptor or iterator cleanup invalidate the writer, even before a
new mutation; ordinary pre-I/O invalid input is not silently relabeled as drift.
No spent accounting is refunded. Cold members follow the fixed prerequisite,
inventory, then remaining-member order and are decoded/discarded immediately.
No numeric limits, owner schemas, roles or operational permissions changed.

Corrected source SHA256 is
`c01df000b92e88b035db5e0184d88a4ff2bfee7af921ca84df32c91cd34247bd`.
The independent reviewer read the correction and reran the same five outside
controls unchanged: five passed, zero failures/errors/skips, 0.397s,
`/tmp/scanipy-res-peer-correction-five.xml`. Their source remains
`/tmp/scanipy-res-budget-review-4fvK39MD/test_res_drift.py`. Root and peer gave
scoped source-review approval; this is not an installation or feature gate.
Equivalent five controls are now in the repository test module. The original
five lifetime controls and outside real-thread race from 18.13 remain intact.

### 18.15 Systematic observed-position fault campaign

This test-only allocation changed the existing test module and appended this
evidence; it did not edit root's frozen `c01df000` source. Position-campaign test
SHA256 (before the separately recorded iterator batch in 18.16):
`bfc73d8712e536c37720d2aeeb92a2fbc9787134cbeb3c8c9f8379ce34189c84`.
Removing only the new dataclass import, fault constants and appended tests
reconstructs the entire previous 115-case file at the exact `94eb0c47` hash in
18.13. No existing assertion, limit, marker, skip or test body was weakened.

Each vector creates its own private temporary installation with inert bytes
and actual owner codecs. The manifest path uses the existing controlled history;
the refusal member is 69,600 bytes, exercising multiple 65,536-byte I/O chunks.
Pair recovery first performs a real link and deliberately interrupts before
unlink; fresh reconciliation only observes/syncs that retained state. Baseline
traces record each actual operation, per-operation ordinal and normalized target
path, then repeat every observed position with an `OSError` before and after
the real operation. The table is the observed baseline per phase, not a claimed
upper bound for every permitted input:

| Phase | Positions | Observed operation counts |
|---|---:|---|
| Begin manifest | 48 | close 23; mkdir 5; fsync 12; write 2; fchmod 2; read 4 |
| Begin refusal | 42 | close 21; mkdir 3; fsync 10; write 2; fchmod 2; read 4 |
| Publish manifest member | 56 | close 27; read 12; write 2; fsync 11; fchmod 2; link 1; unlink 1 |
| Publish refusal member | 60 | close 27; read 15; write 3; fsync 11; fchmod 2; link 1; unlink 1 |
| Finalize manifest | 113 | close 48; read 58; link 1; unlink 1; fsync 5 |
| Finalize refusal | 48 | close 26; read 15; link 1; unlink 1; fsync 5 |
| Recover complete parent | 42 | close 25; read 13; fsync 4 |
| Recover member pair | 42 | close 24; read 12; unlink 1; fsync 5 |
| Reconcile complete root | 38 | close 20; read 11; fsync 7 |
| Reconcile root with pair | 38 | close 20; read 11; fsync 7 |
| Close owned writer | 5 | close 5 |

There are 532 baseline positions and 1,064 before/after `OSError` injections in
22 parametrized rows. Another 22 rows inject the original `KeyboardInterrupt`
or `SystemExit` after the last occurrence of each observed operation kind:
100 interruption vectors, not every position under both interruption classes.
An additional 44 rows exercise 216 paired failures: the original interruption
after the last read (first close for writer close), followed by an `OSError`
before/after every subsequently observed cleanup-close position. They preserve
the original interruption object, its existing explicit cause, and the cleanup
failure. Baselines and single-interruption setup repeats are not additional
independent fault vectors.

Every injected vector requires no returned handle/publication acknowledgment,
fixed public error text with the original private cause retained, prior bytes
unchanged or preserved under their valid linked final name, and no further I/O
through a poisoned writer. Descriptor generations require once-only production
close attempts and no acknowledged descriptor leak. Only the test harness closes
its known-still-open descriptor when its stub deliberately failed before close;
production never retries an uncertain numeric descriptor. Successful cleanup
is not inferred from an exception. Both before/after effects and cleanup-only
failures are represented without removing retained publication bytes.

Configured reports on frozen source `c01df000`; preliminary test snapshots are
identified separately from the final test hash above:

- `/tmp/scanipy-res-systematic-first.xml`: 49 passed, 92.663s JUnit duration;
  the first 44 fault rows plus five peer regressions, before adding the 44
  dual-failure rows and the final stronger poison assertion.
- `/tmp/scanipy-res-dual-fault-first.xml`: 44 passed, 18.547s JUnit duration;
  the added dual-failure rows only.
- `/tmp/scanipy-res-systematic-module-311.xml`: CPython 3.11.16, 209 passed,
  zero failures/errors/skips, 128.457s JUnit duration (pytest summary 128.50s).
- `/tmp/scanipy-res-systematic-module-312.xml`: CPython 3.12.14, the same 209
  passed, zero failures/errors/skips, 131.273s JUnit duration (pytest summary
  134.50s). The runtime repetitions are overlapping evidence, not 418 distinct
  requirements. Each full selection is 208 repository cases plus the unchanged
  external real-thread race. The repository addition is 88 fault rows and five
  equivalent peer controls beyond the preserved 115 cases.

The final XML properties retain `observed_positions`, `injected_positions`,
`interruption_operation_kinds`, `cleanup_close_positions` and
`dual_failure_positions`, including exact normalized names/ordinals. Both final
reports contain the same 1,064 / 100 / 216 vector counts. No genuine source
failure occurred in this campaign. One mistyped interpreter-path version query
exited 127 before any pytest collection; the corrected version query confirmed
the two interpreters above. This was tooling error, not a product red or pass.
Ruff check and format check pass for the final test file; `git diff --check`
passes. The configured `-m 'unit or invariant'` collection selects all 208
repository cases. No full suite, hook, commit or remote action was run here.

Coverage is deliberately finite: these eleven real traces, representative
manifest/refusal inputs and the stated interruption/cleanup schedule. `open` is
tracked for descriptor ownership but not position-faulted by this matrix;
scandir iterator cleanup, all mode/size combinations, all possible multiple
faults, hostile OS interleavings and real power loss are not exhaustively tested.
The earlier all-mode, maximum-size, census/accounting and path controls remain
separate tests, not an implied Cartesian fault campaign. No syscall, heap/RSS,
filesystem capacity or crash-durability qualification follows from these counts.

Required next actions remain: independent final test/evidence review, combined
accepted-tree configured full tests, normal hooks, exact-head remote checks and
canonical SUCCESS/final APPROVE. The operational and full-scope prerequisites
in 18.9 and 18.13 are unchanged; no task, claim, G0–G3, or installation acceptance
is promoted by this focused campaign.

### 18.16 Narrow iterator-close owner-boundary supplement

Root requested a separate small iterator-close batch after the 209-case reports,
not a new exhaustive eleven-trace sweep. The test module now has SHA256
`691a057e056f2f7dbf11d912dbbd43b1c791116aa58e0c84fa9fe7156beb009c`.
Removing only this final appended test reconstructs the exact `bfc73d87` file;
all previous controls and their report attribution remain unchanged. Source is
still `c01df000`; there was no source correction or new genuine failure.

Twelve cases combine two owner boundaries, before/after the actual iterator
close, and ordinary cleanup versus original `KeyboardInterrupt`/`SystemExit`:

- Real `scandir` plus the real `_names` helper under the existing
  `core.operation` context: uncertain iterator cleanup must invalidate the
  writer, preserve original/prior/cleanup exception objects, and prevent later
  I/O. Current public steady publication methods do not enumerate names, so
  these are helper-under-owner-context tests, not an invented public route.
- Public cold constructor: the same real iterator wrappers must return no
  handle and release all acknowledged owned file descriptors exactly once.
  No unavailable writer object is inferred to establish invalidation.

The wrappers retain the actual iterator's bound close method. Production gets
one close attempt; the harness uses the saved real method only to release its
known before-close fixture resource, never as a production retry. Both paths
retain fixed public failure text and private causes; interruption cases retain
the exact original exception and its preexisting explicit cause. The test tracks
actual owned descriptor generations and checks no file-descriptor leak. An
iterator may already close its internal resource at exhaustion; these tests do
not infer internal kernel lifetime from the wrapper's close exception.

Configured focused results on this new test hash, without rerunning the earlier
entire module during another owner's broad slot:

- `/tmp/scanipy-res-iterator-owner-311.xml`: CPython 3.11.16, 12 passed,
  zero failures/errors/skips, 0.617s JUnit duration (pytest summary 9.86s).
- `/tmp/scanipy-res-iterator-owner-312.xml`: CPython 3.12.14, the same 12
  passed, zero failures/errors/skips, 0.711s JUnit duration (pytest summary 0.84s).

Ruff check/format pass. The whole final test module now contains 220 repository
cases; a fresh combined run with the unchanged outside race would contain 221
and remains root-scheduled, not an already observed 221-pass result. This narrow
batch supplements but does not remove the finite-coverage and operational limits
in 18.15. No full suite, hook, commit, remote action or acceptance promotion was
performed by this test-only assignment.

### 18.17 Root final source/test/evidence checkpoint

Root read the complete original core and test implementation, the lifetime and
stored-drift/cleanup corrections, all systematic and iterator test additions,
and sections 18.14–18.16. The source remains the independently approved
`c01df000` hash; final tests remain `691a057e`. The reviewed document before
this appended observation was
`33d5784ad9aa7abbcf794774d733a68294b48c6220ee43549ef8b7ce836ca955`.
The readback found no further blocker within this diagnostic-only allocation.

The fresh configured combined selection on CPython 3.11.16 passed **221 cases**,
zero failures/errors/skips, 141.059s JUnit duration:
`/tmp/scanipy-res-final-221-311.xml`. This is 220 repository cases plus the
unchanged external real-thread race, not 221 additional requirements. Root
independently parsed the result and the retained 1,064 single-fault and 216
paired-cleanup counts. The earlier 209-case and 12-case Python 3.12 reports
remain separate selections; no combined Python 3.12 result is invented.

This checkpoint is still based on `573b0a5e` plus the three allocated files.
It is not a fresh full-repository, current-main or production integration
result. Required next steps are normal commit hooks, minimal accepted-main
and corrected-ancestor composition with the actual PE/journal prerequisites,
fresh configured full regression, normal push, exact remote tests and canonical
SUCCESS/final APPROVE. No event writer, installation, runtime controller,
database orphan barrier, current authority or native execution is enabled.


## 19. Diagnostic one-attempt visible-history reader — September 26

Root engineering implementation approval now covers the exact four paths in
ROOT-HISTORY-SOURCE-ALLOCATION.md, based on clean eba0a2c5288fa75010645f1092583539d9d5aa7f.
This is not separate human approval, installed authority, durability, capacity,
controller enablement or completion of #400. The existing 3010-line prefix and
all previous source/test bodies remain preserved. Current owner-role documents
will be composed separately before publication; they do not change these owners.

The complete reviewed inputs follow verbatim for a self-contained contract.
Their original proposal/status and past composition statements are retained as
history: source implementation is now allocated, but none of their runtime or
maximum-input outcomes is promoted. Accounting02 closes draft01 section6;
mandatory accounting03 overrides ONLY02's candidate prefix, including comma and
colon.02 alone is rejected. Root and independent peer approved the combined
design at review af315ca42793716d66831faca6d8e68c79676ee1930cec18e8b077b31412cc63.

The only new callable is read_diagnostic_attempt_history(installation, attempt_id).
It returns the exact actual replay report inside frozen VisibleAttemptHistory
only after its owned physical finalization succeeds. Its private whole-history
meter permits4096 observations/403 owners without changing any old16/24/512
recipe, and pays full86MiB before the one actual replay. No callbacks, writer,
spool traversal, process launch, current grant, recovery or root census is added.
Focused trusted controls and fresh ordinary-UID small-filesystem tests are
allocated; native/crash/PG/process/full tests, hooks and publication are not.

### 19.1 Retained draft01, completed by19.2–19.3

# RES diagnostic history reader — concrete draft 01

Status: outside-source engineering proposal, not source allocation or runtime
acceptance. Owner: root #400/#362. The tenant-local submitted path remains the
target. No global-adoption or inferred-publication prerequisite is introduced.
This draft does not amend a repository contract until root explicitly approves
its completed accounting and source allocation. Later corrections append a new
section/version; retain this original proposal and contrary evidence.

## 1. Dependency composition, not new implementation

New private outer: `/tmp/scanipy-runtime-history-compose-i8DzOVBc` (0700).
Worktree: its `source` child; branch `bhmea/runtime-history-composition`.
HEAD remains `3194baa1e4a3002854f754c212006bc132adac20`; MERGE_HEAD is
`9ef9fe88bf4c942dc9a1b9aa07b528c1c9b068e4`. Normal `merge --no-commit --no-ff`
stopped on three add/add conflicts. After root reviewed both sides and approved
the exact selection, apply_patch retained the full core RES document and the
exact accepted-main profile/Docker-policy sources. The accepted 2137-line RES
document is byte-exact at the start of the retained 3010-line document.

Staged tree: `7b74563ecc26d330c781224fd76d5285c826b66f`.
Against accepted main the complete difference is exactly three core paths,
4703 added lines and no deletions: source1866, unit1964, contract873. No unmerged
or unstaged tracked differences remain. There is no merge commit, hook/test run,
push, installation, database or process qualification from this preparation.

Preserved SHA256 pins:

| Path | SHA256 |
|---|---|
| tools/worker/runtime_evidence.py | c01df000b92e88b035db5e0184d88a4ff2bfee7af921ca84df32c91cd34247bd |
| tests/unit/test_runtime_evidence.py | 691a057e056f2f7dbf11d912dbbd43b1c791116aa58e0c84fa9fe7156beb009c |
| docs/bhmea/RUNTIME-EVIDENCE-STORE.md | 784ac4ac69e7affc99e4f90355a0911ef85d489370a7fb104160b479394bb572 |
| tools/worker/bounded_process.py | 6a4ec17d2f4a3b04f94ff24a7e213a2be45ac1781fdd885c115756f7fc1f1d34 |
| tools/worker/process_evidence.py | 601fef04b641b28c6f7e3abe948490bd7507287c103194a42b2cc7f943ac0fe8 |
| tools/worker/runtime_journal.py | 51e56785a7ef0d19ad9fc67f677161a69a93729217cd98570cfecd5b152b705e |
| tools/worker/runtime_artifacts.py | 8accd2e2e32cd12ef90f0bb29946ad8197cc1a56c895f848525a44f40e87d05a |
| tools/worker/runtime_profiles.py | 03491134eb0cac62800aa8968f599e909855ec1f7838e746903e525b521e9c01 |
| tools/worker/runtime_docker_policy.py | aa5ad9783a04298408531825841185a47103c78c5c65a0597111708a0c5f0862 |
| tools/worker/runtime_packets.py | b23dfe8398b8b70406bf0e81986519e48d575c5913f3633bcc7124e824589be3 |

The accepted owner files in the last seven rows are byte-exact in the staged
tree. The full-tree comparison establishes preservation of all other accepted
paths too, not just this selected list. The three original core paths are exact.
An initial unsupported `mktemp -m` invocation created nothing; ordinary mktemp
then created the checked0700 outer. A truncated source retrieval was rejected
before any patch; complete retrieval and final hashes established exactness.
Neither preparation issue was a product test or runtime failure.

## 2. Smallest coherent API proposal

Add one synchronous, one-shot, diagnostic-only read function to the existing
module, plus one exact frozen/slotted/non-content-repr result wrapper:

```text
read_diagnostic_attempt_history(
    installation: RuntimeEvidenceInstallation, attempt_id: UUID
) -> VisibleAttemptHistory

VisibleAttemptHistory(
    visibility: Literal['verified-visible-prefix'],
    key: _ScopeKey,  # exact attempt kind and requested UUID
    report: JournalStructureReport
)
```

The wrapper retains the actual complete owning report, including raw manifest,
events, blobs, unresolved calls and `opaque_owner_values`; it never drops those
obligations or substitutes a locally reconstructed report. The inner validation
literal stays `local-structure-only`. A recorded declared phase of `admitted`
is historical structure, not fresh authority. The wrapper is not JournalReceipt,
_PublicationAck, Durable*, a SQL result, an installed reader, or a callable.

Exact installation and UUID primitive snapshots precede filesystem access.
No caller path beyond the existing installation record, root discovery, FD,
clock, budget, mode switch, decoder/runner callback or prevalidated report is
accepted. Operational-domain installation is refused. The function closes its
entire owned lifetime before returning; cleanup failure returns no result.

This separate one-shot entrypoint avoids changing the old publication reader's
meaning or teaching the non-event writer to accept events through publish_member.
Existing publisher, final-file reader, formats, body guards and tests stay exact.
No event append, registration creation, collection, recovery mutation, capacity
claim, CLI invocation or slot release is implemented by this proposal.

## 3. Exact scope and read recipe

The proposed read scope is one explicitly named attempt, not a root audit or
capacity census. Open and recheck the existing root.json, held evidence/work
roots, their normalized ancestors and fixed attempts parent using the existing
ownership/nofollow/nonblocking rules. Preserve actual nonroot UID/GID checks.
No writer flock, fsync, chmod, chown, link, unlink, repair, adoption or creation.
No other attempt's raw content is opened; no whole-root/capacity assertion follows.
Root-wide writer census and its35-second budget remain unchanged and unavailable
as a shortcut to this read. Root must approve this explicit scoped-reader
distinction; it does not weaken the existing publisher's root audit.

Only fixed names below `attempts/<canonical UUID>/` are eligible: manifest.json,
events, blobs, spool-registrations and staging. Event names are six digits plus
`.json`; selected events are a nonempty contiguous prefix1..N, N<=128. Blobs use
lowercase64-hex names, at most256; registrations use canonical call UUIDs,
at most16. Do not traverse host-work spools or any URL named by retained bytes.

Use one bounded enumeration, a private immutable membership/index snapshot,
one content pass through nofollow descriptors, actual owner replay, and final
membership/leaf/root identity rechecks. Require the selected membership to stay
identical; a concurrently changing suffix returns conflict rather than retrying
or splicing heads. No automatic second replay/read or reopen loop exists.
Published leaves must be regular owner0400/nlink1 with full pre/post stamps,
expected sizes, complete EOF and actual raw hashes. Known two-link or partial
publication states remain ambiguous, not acknowledged or repaired by a reader.

Permanent publication intents cannot be discarded or silently ignored. The
history-specific census must validate every accepted retained intent's fixed
scope/destination/raw identity/predecessor mapping, reject duplicate/new-ID
adoption and account its bytes/names. Full-history intent maxima and checks are
not the obsolete initial17-intent bound. Malformed/unknown/unfinished residue
returns conflict/unsupported with no successful clean-history claim. The exact
intent/control census recipe and its owner-call costs are a pre-code gate in§6.

Read all required bytes from this owned namespace; supply the actual immutable
bytes and sorted unique EvidenceBlob tuple to replay_journal exactly once.
Its existing structural/closure/metadata/call/spool/recovery checks remain the
owner: no cloned transition engine, decoded arbitrary raw packet, live outcome
reconstruction, hidden prepare_call_result or signature/domain validation.
Every return must match root store/deployment/domain and selected attempt IDs.
Unexpected/unreferenced or cross-scope evidence fails, not partial success.

## 4. Reviewed hash-only admission

Root and the independent peer reviewed the ONE-invocation source schedule at
the pinned journal/PE versions. This is a static SHA-input bound, not a measurement
or approval of allocation/physical I/O/time. Let MiB=1048576. Reserve and consume
the entire90177536 bytes (86MiB) before entering replay_journal, no refund on any
failure. If another invocation is ever separately allocated, it pays again.

```text
supplied-blob hashing                          <= 32MiB
manifest+events: 2*524288 +129*128              <= 1MiB+16512
four cached local record kinds:
  2*256*(16384+16384+4096+4096) +1024*128       <= 20MiB+131072
16 PE intent preparations, 2*1MiB each         <= 32MiB
request schema-domain hashing                 <= 65536+128
TOTAL                                         <= 89342208
86MiB margin                                  = 835328
```

Pool cache keys are(kind,digest), not digest alone. Only the four listed local
kinds are reachable. Failed decoding/preparation aborts replay, without a retry.
The PE1MiB canonical bound precedes its first SHA; the512KiB combined check is
AFTER that first SHA. Retain1MiB per hash, including malformed/failing work.
Stored PE decoders and FrozenInvocation validation have no SHA. Live output/
result packing is unreachable here and is not hidden in this reservation.

Do not reserve512MiB merely because _Pool.hash has that internal ceiling: it is
not the full nested-work meter. Do not reinterpret the86MiB charge as the entire
physical method. Direct hashes, root/intent codec hashes and any other owners
are additional precharged work against the same256MiB method ceiling.
Reducing input bytes alone does not establish nested-work accounting. A returned
post-hoc cost record cannot replace admission or failure charging; no new public
meter/callback/accounted-owner API is proposed for this hash closure.

## 5. Unchanged hard limits and direct-read accounting

One function invocation uses one monotonic lifetime before the first filesystem
operation and through close, at most2000ms cooperative, without renewal. Root
open35s is not added to this one-shot deadline. This may legitimately refuse a
large history; no guaranteed maximum-input latency, RSS or blocking-syscall
duration follows. A separately reviewed outer supervisor remains required for
real deployment. This proposal creates no process/concurrency admission system.

| Counter | Hard ceiling for this one-shot read |
|---|---:|
| Bytes actually read, including EOF failures | 134217728 |
| Bytes written / sync / mutation | 0 / none / none |
| All direct and delegated SHA input bytes | 268435456 |
| Cumulative owned/generated byte copies | 201326592 |
| Live raw buffers | 100663296 |
| Live implementation slots | 262144 |
| Held FDs, including acquisition/cleanup | 128 |
| Observations: entries/stat/membership, cumulatively | 4096 |
| Application OS attempts, cleanup included | 8192 |
| Chunk bytes / relative ASCII name / absolute UTF-8 path | 65536 /128 /4096 |

These use existing RES ceilings; no implicit per-file, per-codec, per-role or
failure reset/refund. Independent read lifetimes are not an aggregate memory
or concurrency guarantee. Logical summary metadata remains512KiB, retained
raw32MiB,128 events/256 blobs/16 calls; publication-control metadata still counts.
Scope/path/raw-length checks precede large conversion. New history admission
may refuse a legal wire combination whose complete cost exceeds these limits;
such refusal is explicit `limit`, not silent truncation or full-support evidence.

Reuse the actual direct-read charging: reserve next read/hash before each read;
charge actual bytes and EOF probes; reserve3*N cumulative copies and2*N+2*65536
live buffers before a file's assembly; release temporary buffers only after
their last owning reference. Retained report/input buffers remain live, not
recharged as new physical files and not released while still owned. Known equal
bytes do not discount separate reads or hashes. Stat, membership, enumeration,
iterator acquisition/close, descriptor handoff and uncertain-close paths count.
Keep the existing cleanup-attempt reserve and one-close primary/cause/context
discipline; no numeric-FD retry, background I/O or uncertain cleanup adoption.

## 6. Required closure before source allocation

Hash review does NOT close the following. Do not implement the entrypoint merely
with an86MiB ticket and an unmetered owner call. The next review must freeze:

1. Full-history intent/registration/staging membership recipe, direct-file and
   observation/OS-attempt schedule, including final rechecks and failing reads.
   The old initial17-intent/50-file census cannot be reused. Derive the maximum
   geometry admitted by4096 observations/8192 attempts BEFORE expensive work.
2. Complete replay primitive/UTF-8/canonical-copy and simultaneous-slot bound,
   including cached local/PE records, parsed-event tuples, report construction,
   temporary owners, largest offending decoded item and output lifetime.
   A public call count is not a bound on its nested allocations. No generic
   JSON decoder, duplicated semantic codec or hidden relaxed value cap may be
   invented for discovery. Exact safe admission must precede the work it covers.
3. Whole invocation R/H/copy/live-slot schedule: direct bytes + root/intent
   codecs + the full replay ticket + final readback/cleanup. Demonstrate useful
   genuine histories within the existing limits and disclose any unsupported
   maximum combination; no array/input truncation or public-cap increase.

These are concrete outstanding arithmetic/recipe gates, not asserted solved
ceilings or permission to weaken the owning formats. If they cannot close using
the existing public owners, bring the exact conflict to root before proposing
a narrowly owned additional admission interface. No such interface is allocated.

## 7. Proposed tests and boundaries

After contract/source allocation, author tests only in the existing core unit
module and new `tests/integration/test_runtime_evidence.py`, plus the core source
and append-only RES contract. Keep all old tests/owners unchanged. Reuse actual
journal diagnostic History vectors and PE codecs, not fake transition success.

Trusted small-filesystem controls use fresh task-owned temporary directories,
the current ordinary nonroot UID/GID, real fixed modes/nofollow/EOF/flock where
applicable, and real file/dir descriptors; no host/etc, mount/quota setup, keys,
Docker, PG, external source/build execution, installed-authority claim or VM
power-loss claim. Fault-injection tests are labelled controlled; later separately
granted native crash/platform qualification remains necessary. No tests run here.

Cover all four unchanged modes;128/129 events,256/257 blobs, metadata/raw bounds,
16/17 calls; no-event/incomplete/terminal/recovery/orphan histories; missing,
extra, duplicated, malformed, cross-scope and inconsistent refs; full original
outcomes/unknown retention; exact intent/destination mapping; visible-not-durable
and unresolved owner obligations; appended/deleted/substituted names and equal-
byte inode swaps; nlink2/unknown staging refusal; no write/repair; every read,
hash, buffer, slot, observation, FD, deadline and cleanup boundary. Instrument
actual nested helpers separately for maximal valid and late-malformed inputs;
unused precharge slack must not mask an uncharged operation. Test all old
publication/writer guards and operational unsupported behavior remain exact.

Current-authority custody0e9354c/factory6059ed3/composerf7185b7 are separately
local/unpublished foundations, not dependencies of this diagnostic reader.
Qualified capacity/backing/isolation, installed provenance/current owners,
DB-BAR, writer events/spools, controller/kernel/transport and genuine domain
execution remain required later. This slice accepts no C/R/G gate or full#400.

### 19.2 Complete accounting02 (prefix corrected by19.3)

# RES diagnostic history: closed admission schedule 02

Prepared 2026-09-26, after the retained 257-line draft01. This is a concrete
source-allocation proposal for root/peer review, not reader implementation or
native acceptance. It closes draft01 §6; all its diagnostic-only/unsupported,
same-attempt, no-write, no-root-capacity and two-second qualifications remain.
Retain draft01 SHA5f92ec14b0a6be6d93c4ed84cba2e48c38954e83aee636a733f8ccc70662548a.

## 1. Frozen owners and composition

The dependency merge is now normally committed at
eba0a2c5288fa75010645f1092583539d9d5aa7f, tree
7b74563ecc26d330c781224fd76d5285c826b66f, parents3194baa1 and9ef9fe88.
Root's LOCAL-COMMIT.md records applicable merge-conflict hook scope, not a full
regression. The worktree is `/tmp/scanipy-runtime-history-compose-i8DzOVBc/source`.
All ten draft01 pins remain exact. Main's later9a999b8c owner-role documentation
does not alter these code owners; compose it separately before publication.

Actual owners here are RES c01df000, RJ51e56785 and PE601fef04, not copies of
their decoders. Source anchors: RES _read561/_names899/_walk974; RJ _decode487,
decode_journal_record731/_Pool1122/_Replay1267/replay_journal2037; PE _decode354,
_snapshot_json236/_canonical286/prepare_call_intent525/_graph_fields855.
The already reviewed ONE replay SHA ticket remains exactly86MiB; no re-review
or extension of that hash-only decision is claimed by this appendix.

## 2. Closed completed-visible geometry

Let E=events(1..128), B=unique blob files(0..256), R=registration sidecars(0..16),
G=1+E+B+R, I=G completed intent files and L=2G+1 regular content files including
root.json. Writer.lock is separate, zero-length. A is the sum of normalized
non-root components of both configured absolute paths, computed before walking.
All counts are exact private integers, not caller budget inputs.

Accepted names are exactly root's four fixed names; selected attempt's five
fixed names; contiguous six-digit event names1..E; lowercase64hex blob names;
canonical call-UUID.json registrations; and canonical publication-UUID.json
intents. There is one intent per final destination, never an additional ID for
the same destination. Staging contains exactly those I .json files and NO .data,
unknown suffix, extra directory, symlink or unfinished pair. No other attempt,
refusal contents or host-work spool is traversed. The work root is checked as a
held configured root, not represented as empty or independently capacity-safe.

Every intent and final content inode is regular, correct owner/group,0400,
nlink1, same admitted filesystem and stable complete stamp/EOF. Each intent is
decoded once by actual decode_journal_record('publication-intent'). Its filename,
publication ID, store, attempt scope, role, fixed destination, size and raw SHA
must match the observed final member. Root uses its actual owning decoder and
installed digest. No data-only file or intent-only declaration yields a report.

Manifest intent predecessor is null. Event intent predecessor equals the actual
owning parsed event's previous_event_digest (null exactly for event1). Blob and
registration intent predecessors are null OR an actual schema_digest in this
verified same-attempt event prefix. This is a validated retained declaration,
NOT physical first-use/publication chronology, durable acknowledgement or writer
recovery evidence. Root explicitly accepted that distinction during this draft.
Old core-generated non-event intents remain null; no old writer guard changes.

After the ONE actual replay, each registration sidecar is byte-equal to the
actual blob named by exactly one owning spool-registered event with the same
call ID. Every such event has its sidecar. Do not decode sidecar semantics again
or follow relative_directory to the work filesystem. Actual replay owns the
registration/input/result/collection binding. Use fixed destination/digest maps,
not a cloned replay graph or opaque BlobRef discovery. All B blobs still go to
the actual owner's unreferenced/cycle closure; no opaque obligation is removed.

Snapshot initial membership/full leaf stamps, read content once, replay once,
then enumerate the same six directories once more and compare exact names,
held directory identities, all L final leaf stamps and configured ancestors.
Equal-byte inode substitution, changed suffix or altered stamps conflicts.
No second replay/reread retry is hidden in finalization. Complete visible content
is not fsync evidence and grants no reusable publication/quota credit.

## 3. Filesystem admission, including errors and short reads

Before walking, admit A and minimum geometry. Before retaining each enumerated
name, reserve its slot/name bytes plus next-advance observation/application-FS
attempt; include EOF and the one over-limit sentinel. Stop immediately on an
unknown entry. When geometry is known, before content/owner work require:

```text
O_plan = 4*A + 6*L + 96             <= 4096 observations
FS_full_chunks = 8*A + 10*L + 768   <= 8192 application FS attempts
```

The second expression is a conservative full-requested-chunk admission plan,
NOT an assertion that regular-file read always returns the requested amount.
All actual attempts, including positive short reads, consume the same8192
counter. Before each additional read keep the remaining mandatory final checks
and existing128 cleanup attempts reserved; if it cannot fit, return limit before
that syscall. No counter refund, partial-record success or retry/reopen. Zero
progress fails. This bounds every failure path by8192 even when the nominal
full-chunk plan is exceeded. Short reads do not increase byte/hash/copy limits.

The source schedule behind those expressions is:

| Fixed phase | Application attempts | Observations |
|---|---:|---:|
| Initial and final walks of both roots, closes, four held-root fstats | 8A+12 | 4A+4 |
| Six direct directories: open, initial/final fstat+membership, close | 36 | 24 |
| Zero-length writer.lock: open/check/EOF/final check/close, NO flock | 7 | 4 |
| Actual effective UID/GID | 2 | 0 |
| Each content file: open, fstat, Q reads, EOF, poststat/member, close, final member | Q+7L | 4L |
| Two enumerations of root/attempt/events/blobs/registrations/staging | 2L+50 | 2L+26 |

There are2L+14 successful entry yields and12 EOF advances in those enumerations.
Each scandir acquisition and close is an attempt too. Successful full chunks
have Q<=513+L at P<=32MiB+4096. The sum is8A+10L+620;128 reserved cleanup plus20
spare fixed attempts gives768. Observation sum4A+6L+58 leaves38 fixed sentinels/
guard observations inside96. No fallback repeatedly consumes that spare.

An iterator's possible internal duplicate descriptor is included in FD admission;
application attempts are not a universal libc/getdents/kernel syscall count.
Hold root/work/lock plus six direct directories and at most one content FD,
one iterator duplicate, two walking ancestors and one acknowledged handoff.
Even a conservative32 simultaneous owned descriptors is below128. Acquisition,
registration, iteration and cleanup share guarded ownership; acknowledged FDs
cannot fall between an unguarded return and registration. Close each once, retain
the original primary and prior cause/context plus cleanup failures, never retry
an uncertain close. Do not silently rewrite old core descriptor methods.

## 4. Static byte/shape admission, not a decoder

Let S be raw manifest+event bytes (<=524288). Let J be root.json plus all actual
intent bytes. Let P be all L regular content bytes, counting sidecars/intent
duplicates physically, even if equal to a blob. Require P-root_size<=32MiB.
After owning replay also require its logical_metadata_bytes + intent bytes
<=524288. This is observed structure, not writer credit or a root-capacity audit.

For raw d define v(d)=1+count(',')+count(':')+count('[')+count('{'). Counting
punctuation inside strings deliberately overestimates. JSON grammar gives one
root plus separators/container starts as an upper bound for parsed key/value/
container nodes, including a partial tree before malformed/duplicate rejection.
This is four bounded bytes.count scans with integer accumulation, not JSON/schema
parsing. A small no-copy prefix scan classifies a blob as a possible metadata
candidate only when len<=1MiB and its first non-ASCII-whitespace byte is one of
`{["-0123456789tfn`, OR it is empty/all whitespace. Both actual lexical owners
reject other prefixes or oversized inputs before generic JSON/UTF-8 decoding.
Never treat a candidate as valid because it passes this admission scan.

Use64KiB scan ranges (no sliced raw copies), check the same deadline between
ranges. At most five raw byte visits per byte, <=5P, aside from existing owner
work. A JSON-looking opaque blob may conservatively consume admission/refuse;
do not relax its role or feed it into a new decoder. Invalid UTF-8 is charged.

Let Cb=sum candidate lengths, M=max candidate length or0 and Vb=sum v(candidate).
Let Vr=sum v(manifest/events), V=Vr+7Vb, and define:

```text
C = 3*S + 7*Cb + 16*M + J
Copies = 4*P + 64*C + 16MiB <= 192MiB
```

The seven candidate occurrences pay all four possible journal cache kinds and
three PE cache kinds, including an eventual wrong-kind failure. Cache key is
(kind,digest); do not assume digest-only or successful-schema uniqueness. The16M
term pays sequential actual prepare_call_intent invocations independently,
including failure. The actual decoded canonical invocation is re-encoded by that
owner; it cannot generate an invocation larger than its admitted source bytes.
Fixed new payload fields remain capped2048 per call and paid in the fixed term.

Three S occurrences separately cover (1) journal parse/canonical/tag and local
field validation, (2) embedded PE payload/ref canonicalization and replay's
plain/intent-view work, (3) the reader's bounded owning-report projection for
scope/event/registration/intent comparisons. The third pass must not invoke
replay again. Reuse/discard one plain event view at a time.

64 bytes of copy allowance per byte-occurrence is conservative over these actual
representations: lexical token slices<=N; UTF-8 input/decoded scalar storage
<=8N; tag/plain preflight string encodes<=4N; one JSON fragment+joined-Unicode+
UTF-8 pass<=9N; closed field/path/FrozenInvocation revalidation<=16N; a nested
PE canonical/input pass<=20N; remaining scalar/escaping/base64 slices<=6N.
These sum64N. Embedded disjoint ref subtrees sum to at most their source event;
repeated encoded fields count as repeated source bytes. PE error graph's<=32
mini-canonicalizations operate on disjoint argument subtrees; its offending
argument is included even though the2048 cumulative test follows construction.
No live _Graph/_Pack/prepare_call_result/MemoryOutput hashing is reachable here.

The fixed16MiB pays bounded names/hex/schema-prefix/compact-row copies and small
generated controls: all<=4096 graph/reference attempts, <=16 generated2048-byte
intent payloads and <=32 decoded4096-byte raw output paths, plus path/census
snapshots. It is consumed once at entry, not another per-file allowance. Direct
read's three explicit N copies are paid3P; the fourth P covers possible pool
prefix concatenations. Internal allocator relocation, interpreter object/RSS
overhead and kernel copies are not represented as measured bytes by this meter.

## 5. Slots, raw-buffer lifetime and owner calls

Let n=B+E+1 and O=min(4096,18B). There are17 reachable empty-path owner roles
(refusal-raw is unreachable) plus admission's one field path, hence18B, not an
assumption that every role has only one path. Reserve:

```text
Slots = 6*V + 16*4096 + 4096 + 4*4096 + 8192
        + 12*O + 12*n + 96*E + 96*B + 24*L + 24*I + 12*A
Slots <= 262144
```

Slot units are logical owned container fields/references, not CPython allocated
capacity. A complete tagged tree requires<=2v slots; a plain tree<=v. Tags plus
plain cached data and retained call-intent views fit6V. One active decoder and
generated PE preparation use the existing conservative16v+4096 scratch shape,
with v<=4096 (actual invocation<=2048); they are sequential, not16 simultaneous.
This scratch is held through failure/cleanup. No whole-history decoder cache is
freed on paper while still owned.

Graph sets need<=4096 entries; DFS pending pairs need<=3*(4096+2n) references;
graph/colors/heights dictionaries bring that to4*4096+12n. Opaque set/path,
sort-key tuples/path keys, sorted references and output records peak within12O.
96B covers fixed blob copies/maps and all seven cache-key/pair/record headers;
96E covers event/call/identity/prerequisite/charge/registration/collection maps
and headers (their nested metadata is already V). The8192 fixed remainder pays
small loop/record/cleanup structures.24L pays original/final membership indices,
stamps and active row views;24I pays compact ten-field intent/destination maps;
12A pays both five-field ancestor snapshots with indexing. Keep census raw
storage within its separately retained4MiB, not unbounded Python DirEntry lists.

Let Nmax be the largest content file, and T=max(4096, largest manifest/event,
M), so T<=1MiB. At all stages preadmit:

```text
Live = 4MiB + P + 4*C + max(Nmax+131072, 16*T+131072) <= 96MiB
```

P is retained raw content.4C covers retained decoded Unicode/derived scalars.
Reading one new N-byte file has previously retained P-N plus assembly/final2N
and two64KiB chunks. The replay's largest pool hash-prefix copy is at most Nmax;
later metadata/canonical/PE transient representations fit16T plus two chunks.
These phases are sequential; don't add their mutually exclusive peaks or release
P prematurely. Since Copies implies C<=2.75MiB, P<=32MiB+4096, Nmax<=32MiB,
this live expression is conservatively below80MiB even without correlating the
stronger P/C tradeoff. The report's actual raw buffers stay owned through final
rechecks/cleanup and transfer to its caller; returning is not a claim of freeing
them. Retained traceback objects likewise are not a process-global memory quota.

Direct root/intent calls are exactly I+1, then one replay: I+2<=403. This is a
new private whole-history recipe bound, NOT a raise of the old non-event16/24
call limits or their512-observation meter. The proposed history branch uses
only the already deferred4096 observation and existing8192/byte/slot/FD ceilings.
No metadata owner, encoded-value property or public callback is unmetered.

## 6. Payment order, final result and useful feasibility

Start the one2s monotonic lifetime before filesystem work; bounded exact public
primitive snapshots have fixed prepaid slots. Pay fixed16MiB copy/4MiB census
and scratch reservations once. Enumerate/admit geometry incrementally. At each
opened leaf's fstat, admit N into P, direct3N copies and assembly/live bounds
BEFORE allocation/read. Charge read/hash chunks before use, actual transferred
bytes after, EOF work even on failure. Positive short reads never reset counters.

Before each root/intent decoder consume64N copies and2N+128 hash input, its owner
call and scratch slots. Keep only compact intent rows plus bounded raw snapshots.
Before ONE replay consume the whole86MiB SHA ticket, remaining P copy allowance,
64*(3S+7Cb+16M) delegated copies and all V/graph/live reservations; no failure or
unused branch refund. Remaining counters obey:

```text
Read <= P+L <=128MiB
Hash <= P + 2J +128*(I+1) +86MiB <=256MiB
Write = sync = mutation =0
```

Every actual owner/scan/filesystem phase checks deadline before and after.
Existing synchronous owner work is not preempted mid-call: a late return fails
before result publication. Preserve original exceptions/cleanup evidence; no
hard blocking-syscall or aggregate process/concurrency guarantee is asserted.

All final matching and full-stamp checks must finish before returning the exact
actual JournalStructureReport inside VisibleAttemptHistory. The wrapper cannot
answer current permission, durability, installation, capacity or recovery.

The final small pure probe uses actual existing diagnostic History and replay/
PE owners, four modes × reserved/loaded/created/admitted plus one registered
spool prefix. Each completed-intent shape is also accepted by the actual codec.
At A=12, all17 fit. The largest demonstrated case is python-syntax admitted:
28events/35blobs/9calls,64intents/129leaves, P116041B, C406314B, V12862,
918 observations,2154 full-chunk FS plan,116170 read bound,90361087 hash bound,
43245476 copy bound,6136817 live bound,190532 slots. These are proposed admission
calculations over small supplied bytes, not observed filesystem/syscall/memory.
Actual replay there used116 SHA calls/167720 input bytes,31 journal decodes,
52 PE decodes,9 real prepares,147 observed canonical calls/120416 output bytes.
The full86MiB ticket is still consumed, not reduced to that observed usage.

All four admitted cases retain actual9-call histories and opaque obligations;
the spool prefix retains1registration/2collections and an unresolved call, not
an invented healthy result. Max wire E128/B256/R16 gives803leaves and4962
observations at A12: explicit limit refusal, not support for every valid wire
combination. A32MiB physical input plus C1MiB also exceeds192MiB copies. No cap
increase or truncation is needed for the useful demonstrated histories.

## 7. Requested next source allocation and required controls

After root/independent accounting review only: additive history API/private
recipe in tools/worker/runtime_evidence.py; append tests/unit/test_runtime_evidence.py;
append this owning contract to docs/bhmea/RUNTIME-EVIDENCE-STORE.md; new trusted
small-filesystem tests/integration/test_runtime_evidence.py. Preserve all old
public bodies/tests/owner pins and unsupported operational paths. No writer,
event append, controller, provider, root reconciliation or environment API.

Implementation must instrument each named phase before its allocations/owner/
OS effects, with separate malformed/wrong-kind/late-failure and accounting-limit
tests; fixed prepaid work must not mask uncharged operations. Include actual
positive short reads, growth/EOF, N/N+1 names, all caps, equal-byte inode swaps,
KI/SystemExit at acknowledged acquisition/cleanup, and finalization exhaustion.
Use actual small temp files only after an explicit test grant, ordinary current
UID/GID and diagnostic roots; no scanned source, mounts, keys, Docker, PG or
runtime authority. Current probes exercised no physical reader or real history.

### 19.3 Mandatory leading-delimiter correction03

# RES history accounting: leading-delimiter correction 03

This short amendment supersedes only the candidate-prefix claim in §4 of
HISTORY-ACCOUNTING-02.md SHA18a352927a060aae0ad83881cc8efd82db098651c375b12b6dd0ef6110d120a8.
The306-line original, its prior draft, probes,32-pass reports and freeze index
remain unchanged. The full proposal still requires root/independent review;
there is no implemented history reader or new runtime permission.

## 1. Actual contrary evidence and normative replacement

Root identified that both RJ._lexical and PE._lexical permit leading comma and
colon before generic JSON/UTF-8 work, although JSON later rejects the document.
The original filter wrongly classified those prefixes as noncandidates.
Four actual-owner controlled regressions (two delimiters × both owners) first
confirmed generic JSON received the complete decoded string, then failed the
original candidate-admission assertion:4 failures,0 errors/skips. This is a
real accounting-proposal omission, not an accepted owner decoder defect.

Replace the §4 candidate byte set with exactly:

```text
len(d) <=1048576 AND
(d is empty/all ASCII whitespace OR
 first byte after ASCII whitespace is in b',:{["-0123456789tfn')
```

Whitespace is exactly space/tab/CR/LF. The added comma and colon are candidate
starters, not skipped by this classifier. Do not infer validity from the set.
Both owners fail first on every other initial byte: unmatched `]`/`}` fails
negative depth; unsupported token starters fail their literal/number/string/
container branch. Initial ASCII whitespace is skipped only conservatively for
PE (RJ may reject sooner). Both owners reject bytes beyond their actual cap
before generic decoding. Consequently noncandidate blobs cannot reach generic
JSON/UTF-8 allocation, while all candidate bytes count in Cb/M/Vb BEFORE replay.
All-whitespace/empty input remains charged despite containing no valid document.

No counter/ceiling,86MiB ticket, slot/copy formula, useful-history semantic result,
filesystem recipe, owner API or source pin changes. Candidate admission is only
a conservative prerequisite; actual owning schema/canonical validation remains.

## 2. Preserved and corrected controls

Original regression source:
`/tmp/scanipy-history-accounting-bc9w8hQb/test_leading_delimiters.py`
SHA4f3992a1d816d7d2a76c3f2291a4a0271f8ccf0dd5bc58abad1e4851aad9902c.
Original red XML `leading-delimiters-original.xml` in that directory:
SHA9dc5a35fee41747187cddddcf85fbd691a32dd98953b44e97bfefc1ee94c233d.
LEADING-DELIMITERS-ORIGINAL.txt retains the complete actual failure output.

The corrected probe is a separate file in
`/tmp/scanipy-history-accounting03-UNFOB2ZG/probe_accounting.py`, SHA
220ab4788540171af5ee17bc4ae3ea865513b414b7d64b8d4acd949d013b9ec1.
It differs from preserved5805e2bb solely by the two added literal prefix bytes.
The original32 controls and four regression bodies were copied byte-exact.
Twelve further pure controls check all256 initial byte values, with and without
leading whitespace, against each actual lexical owner for six tiny suffixes.
They are finite supporting vectors, not a universal semantic-decoder proof.

Configured final run:48 unique passed,0 failures/errors/skips. It is32 existing
controls + the SAME four formerly red controls +12 first-byte controls, not
48 native tests. Report `accounting-prefix-final-48.xml` SHA
7a848afacebdca57e5ce3cdc3a7f0f0441e7d81caa633e3cda07c86460f1b89d.
The corrected17-history probe output is byte-exact to the original final output,
SHAfac0ab959429094a9b4a973b1fe88871414963e640f64b0e1ebdf52dc4995eae;
the useful small examples and conservative numerical admissions are unchanged.

The run uses the exact clean Python3.11 environment/owner tree in the original
ACCOUNTING-FREEZE.md, but PYTHONPATH's outside directory and all three selected
test paths point to scanipy-history-accounting03-UNFOB2ZG and the fresh48 XML.
No source/index, native filesystem history, PostgreSQL, process runner or key
was touched. All original files/reports remain available; no implementation or
maximum-memory probe was executed.

### 19.4 Implemented diagnostic reader and bounded author qualification

September 26, 2026. The four-path source allocation above is now implemented
locally, pending independent implementation review. This is not a current
authority, writer/controller, full #400, or operational acceptance statement.
The API returns the actual complete `JournalStructureReport`, wrapped only in
the frozen `VisibleAttemptHistory`. A recorded `admitted` phase remains recorded
structure. It retains unresolved calls, original outcomes, opaque values, every
supplied blob and all actual owner accounting; it cannot grant execution.

The new `_HistoryWork` recipe is independent of the old `_Work` initializer,
root35-second route and16/24-call/512-observation limits. Its single two-second
cooperative lifetime begins before primitive snapshots and extends through
cleanup. Fixed shared descriptor slots own acknowledged opens immediately;
scandir is guarded from acquisition through bookkeeping, iteration and close.
Finalization allowance remains reserved during short reads, alongside128 cleanup
attempts. No uncertain close is retried. Full held inode stamps, exact six
memberships, configured ancestor security identities and root bindings are
checked before success. The extra fixed refusals-directory metadata check does
not enumerate its contents; its two observations/calls fit the accounting02
fixed spare. Other attempts and work-spool contents are never traversed.

The final content pass pays direct byte/assembly costs before allocation. Static
candidate discovery includes mandatory comma/colon correction03 and uses no
semantic decoder. The complete copy/live/slot plan precedes every semantic
owner. Each root/intent decoder pays its exact private recipe, and the one
actual replay consumes86MiB SHA plus all separate physical/control costs before
entry, including malformed/failing histories. There is no reset or refund.
Tests instrument each actual application OS attempt/observation and owner
boundary independently; an unused large replay reservation is not their oracle.

Author evidence is retained outside the worktree in
`/tmp/scanipy-history-reader-evidence-Yd79GqH3`. Exact results are distinct runs,
not additive coverage claims:

| Checkpoint | Actual result | JUnit SHA256 |
|---|---|---|
| Missing new API baseline |4 failures; AttributeError construction baseline, not an old-owner defect|f23c877b3a780893fbb79ef7cc706d735e6880aced29c7f8eb181340ffa74328|
| First implemented four-mode reserved histories |4 passed|d1b6619a8774cbb2897df202f55123841a4027b9fac9d69fd5d2888bfd8862d5|
| First expanded controls |80 passed,6 failed; five invalid fixture operation literals and one wrong private-helper call signature|603d3fd02feb68f8ae614e18432fe182c07a074463b4d78775fe3f1b89bb93b9|
| Corrected expanded controls |100 passed|e0b5029d22e3d3422f2912467e8b05597523994c80b4794e124d4bed799677c5|
| Acquisition/accounting expansion |129 passed|44d2acfce029b0a33837f17a3404b8bcbf8331b3154d076473ba731ea3b2f93e|
| Full new controls before final cleanup correction |143 passed|4d8d99eecb5311851b7e3324884e329fa2086c5e1b1636177ccffd64ada8b20b|
| New controls plus23 unchanged old guards |166 passed|d11ff6ed370a7440112f2456bb5691611389d19254f3650a026b034f847d2dc9|
| New cleanup-primary causal control |1 failure,1 pass|778f313d7e61dd7bc2c139d0e8a0acdf62fbac882c2f21d8d7c5d9c141461037|
| Final controlled selection |168 unique passed,0 failures/errors/skips;12.730s JUnit|5fd69504947c4e70733afb127f7a423d1c06924137592a7e08a2f0535a35184a|
| Separate small measured history |1 passed,0 failures/errors/skips;1.246s JUnit|7679ebcb1bae691909532c2088fd458f5a7b5d46be3b1269d44adc603fca7169|

The cleanup-primary failure was a genuine new-source finding at
`d83b136e3ddea5e04e5e17ee4cfe142e3cbfdf069407f4f02d08205e6a35d2a7`:
when a cleanup KeyboardInterrupt became primary and a later close failed, its
explicit prior cause could be overwritten. That complete original source and
the contrary XML are retained. The new finish helper now carries the chosen
primary's original cause-or-context into aggregation. Both original controls
pass unchanged in the final selection. This correction touches no old owner.

The final168 are131 additive unit cases,14 new small ordinary-UID filesystem
cases and23 unchanged old guards, with197 other old unit cases deselected.
The separate measurement overlaps these semantics; it is not another feature
or native gate. Coverage includes actual16-call/recovery histories and17-call
refusal, all four modes through actual admitted reports, unresolved/missing/
orphan/spool evidence, duplicate/malformed/cross-scope intent refusal, exact
name and numeric limits, positive short reads and zero/EOF failure, same-byte
different-inode replacement, no writes/flock, late owner/cleanup deadlines,
and controlled KeyboardInterrupt/SystemExit acquisition/close failures. Native
crash, mount/quota, hostile-host, power-loss and maximum-memory guarantees are
not inferred from these finite Python/source and small filesystem tests.

The separate real small python-syntax admitted fixture observed28 events,
35 blobs,9 calls,64 intents and129 leaves at A=10. Its retained physical bytes
were116137 and C=406410, with V=12862. Path-length-dependent root bytes explain
the difference from the earlier pure prototype; this is not a bound increase.

| Meter | Actual reserved/observed value |
|---|---:|
| Read bytes / write bytes |116137 /0|
| Direct plus delegated SHA reservation |90361375|
| Cumulative copy reservation |43252004|
| Retained logical slots / raw-buffer peak reservation |190508 /6137297|
| Application OS attempts / observations |1478 /874|
| Root+intent+replay owner entries |66|
| Peak held FDs / final owned FDs |11 /0|

The OS/observation counts are actual application attempts, not universal libc
or kernel syscall counts. Slots/copies/buffers are the reviewed source-derived
logical reservation units, not RSS measurements. The synchronous decoder can
return late and then be refused; no hard preemption/blocking-syscall guarantee
is claimed. All same-invocation raw content remains retained through cleanup
and transfers to the actual returned report. Independent invocations are not
an aggregate process/concurrency memory limit. Simultaneous wire maxima may
explicitly limit-refuse; this checkpoint does not claim maximum support.

The original57 source definitions,65 test definitions,1964-line unit prefix
and3010-line contract prefix remain exact; only necessary imports and additive
history declarations/tests were added. All seven dependent PE/journal/process/
profile/Docker/packet/artifact sources remain pinned unchanged. There has been
no full regression, hook, commit, push, Docker, PostgreSQL, process launch,
installation, key generation, UID change or operational activation here.

### 19.5 Finite cleanup ownership correction contract

September 26, 2026. Root allocated this narrow correction after independent
review of source743025fe. The original four-file checkpoint, 168 passing
controls and prior findings remain historical. Canonical's unchanged twelve
fake-only controls reproduce six failures and six healthy comparisons: two
successful-result-to-finish handoffs and four shared-slot-to-local-close
handoffs lose acknowledged ownership. Their report is
`/tmp/scanipy-history-implementation-peer-SEuu6ENe/cleanup-handoffs-original.xml`,
SHA77d66a4c961c80b153c08a1afc1674fd6c6ee042bd0dc10be179c43748475ac8.

The successful finish call must run inside the active read/verify/finalize
exception guard. A failure there snapshots the exact primary and its explicit
cause, otherwise context, before the remaining-owned cleanup fallback. That
fallback scans the same slots and scanner; it cannot retry a consumed close.
No result is returned on any primary/cleanup failure or late deadline.

Each descriptor/scanner close starts its guard before clearing shared ownership.
A preinitialized local owner plus an attempt flag records the transfer. A
failure before the actual attempt restores the acknowledged local resource to
the same shared slot; an entered close remains consumed and uncertain, never
restored or retried. Attempt claiming and the native call occupy one guarded
Python line for these finite line-boundary controls. This is not arbitrary
opcode/signal atomicity or immunity to another interruption during fallback.
The diagnostic FD count is recomputed from surviving shared ownership, including
an existing scanner. All original cleanup causal links remain retained.

These are only new-suffix cleanup changes. All old publisher/reader/root bodies,
seven owner pins, integration bytes, original unit oracles, existing 2-second
lifetime and every byte/hash/copy/slot/FD/observation/attempt limit remain.
Preattempt failed work remains charged; restoration does not refund an attempt
reservation. Fallback remains inside the existing 128 cleanup reserve and the
8192 aggregate limit. No new syscall, owner replay, authority, retry policy,
publication acknowledgement or runtime qualification is introduced. Preserve
original 1964/3010 prefixes and the complete pre-correction 2994/3780 prefixes.
Separately named semantic successors must select the actual successful finish
and first normal line after ownership transfer, demonstrate red on preserved
743025fe, then green corrected without changing the exact ownership oracle.

### 19.6 Cleanup correction author evidence, pending independent review

The two allocated defects are corrected only in `_HistoryFiles.close`,
`_HistoryFiles.close_scanner` and `_history_read_owned`. The original four
files are retained byte-exact in
`/tmp/scanipy-history-cleanup-correction-90Nsx5H0/ORIGINAL-*`. The integration
file is unchanged. All 97 pre-correction unit definitions and the complete
2994-line unit prefix remain exact, including all original 65 definitions.
The 3780-line document prefix (and original 3010 lines) remains exact. Replacing
only those three new function spans reconstructs source743025fe byte-exact;
all 57 old source definitions, seven owner files and three embedded proposals
remain exact. No changed assertion or selector is called an unchanged peer run.

The appended 58 fake-only cases select the first successful finish call and
the first normal statement after the actual shared ownership transfer. They
retain exact primary/cause-or-context, subsequent cleanup evidence, remaining
ownership, FD counts and once-only attempted closes. They use only substituted
OS/iterator close operations and small in-memory reader doubles, not real
descriptor acquisition or semantic owner verification. Original peer twelve
controls/report remain unchanged; the semantic successor is a separately
named expanded suite, not an unmodified rerun of the old layout locators.

| Distinct report in the correction evidence directory | Actual result | SHA256 |
|---|---|---|
| semantic-original.xml, source743025fe |58 unique:24 failed/34 passed/0 errors/skips,3.979s|f76905c270d8c5c6c0b9fafb1d0bf29544609ea134ee9086a29039255c5848c6|
| semantic-corrected.xml, pre-static correction |58 unique passed/0 errors/skips,1.746s|c1b0d1ca2bf5647ed9003126cd61decdd055dacfa794ebfc1226e752815c75ee|
| history-corrected-focused.xml, final sourcebed822cd/unit6ab152f1 |226 unique passed/0 failures/errors/skips,14.330s JUnit,14.84s console|cf154ff7c5ecbe622332213b7026392814dc999dba7509aea500a34e704cb4e2|

The 24 new original-source failures are eight successful-finish and sixteen
post-transfer variants. Every failure reaches the exact missing-close
assertion after confirming the original primary/prior; no import, API or
locator failure is represented as a product defect. All 58 successor case
identities and bodies persist in the final run. Final226 equals the prior168
ordered identities plus58 successors:189 new unit,14 unchanged small-filesystem
integration and23 unchanged old guards;197 other cases remain deselected.
Overlapping runs are not cumulative independent feature coverage.

Initial scoped static checks found one new test line needing wrapping and one
redundant iterator cast; those were corrected without changing the oracle or
close schedule. Final Ruff/format checks pass for the two changed Python files,
and strict Mypy with silent imported-module following passes the source file.
Existing removed ANN101/ANN102 warnings remain; no typing/config/baseline rule
was relaxed. The final focused run followed these static corrections. The raw
inverse/AST/prefix/report checker also passes, as does `git diff --check`.

This is author evidence for two finite cleanup fixes, pending root/independent
review. It is not full regression, native interruption, power-loss, maximum
memory, current authority or durable acknowledgement qualification. No hook,
stage, commit, push, process campaign, Docker, PostgreSQL, key or UID operation
was performed. All original failures and source checkpoints remain preserved.
