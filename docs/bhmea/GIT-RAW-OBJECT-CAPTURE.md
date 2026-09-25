# Git raw objects to verified source custody — proposed producer contract

Status: scoped offline implementation design approved by root under
[#398](https://github.com/scanipy/scanipy/issues/398). The seven offline files
and separately approved [bounded transport](BOUNDED-PROCESS.md) three-file slice
are authorized for local implementation and tests, not runtime acceptance. No native Git,
network acquisition, image build or user app/database/container change has been
performed for this design. Authority:
[DECISION-BHMEA-01](../DECISION-BHMEA-01-current-execution-authority-2026-09-25.md).

Local dependency chain: corrected #395 containment
`9b9091faf1f22b216aca74c87e7711da33d40390`, pending #390
`16252b21db172b967f13a815ca9bd8fe3078dd19`, and #392 source custody
`e3d318b3c24f9509560b07bae04066dd370bf9e0`, joined by normal local merge
`3f27f7e31b9ecd6c9c1fa22cb91aadeac3c89306`. A local dependency merge is not
canonical approval, merged-main acceptance or permission to run a native tool.

## 1. Deliver a real producer without inventing network authority

The smallest executable first subset is:

1. Accept an explicitly supplied private OFFLINE set of raw Git object bytes
   and one trusted expected exact commit OID.
2. Verify the raw commit, complete expanded tree and every referenced blob,
   with strict type/size/hash/path/mode and cumulative bounds.
3. Materialize source-only regular files using bounded no-follow exclusive
   writes, then call the REAL source-custody backend's capture and verify.
4. Independently bind retained capture files back to the verified Git objects.
   Persist/read back an external SCM consistency proof and actual custody
   receipt. Return a machine-readable completed result only after all steps.
5. Re-verify an existing offline sealed capture against a trusted expected
   receipt AND trusted expected SCM proof digest. No source command is run.

This is an actual byte-to-capture path, not an observation-only model. It proves
consistency with an expected Git SHA-1 object, NOT that those bytes were fetched
from GitHub, authenticated by a provider or signed by a commit author. Raw
object input can come from an operator; that trust distinction remains explicit.

Online GitHub acquisition stays UNCONDITIONALLY unavailable in this first code
subset. There is no JSON/env/CLI boolean, optional injected runner or caller-
constructed dataclass that enables it. A separately implemented and reviewed
outer egress/runtime controller is required before the native path can run.
Its precise proposed interface and implementation issue are in sections 8–10.
No generic `secure_run("git", ...)` or legacy connector/snapshot/app route is
re-enabled. Containment is preserved while this separate producer is built.

## 2. Exact proposed file ownership

Root has approved these seven offline files and the shared three files, for ten
total. Online acquisition and the outer controller remain separate:

| File | Owned change |
| --- | --- |
| `docs/bhmea/BOUNDED-PROCESS.md` | Shared contract; already approved separately. |
| `tools/worker/bounded_process.py` | Shared byte transport; no Git authorization. |
| `tests/unit/test_bounded_process.py` | Trusted child transport falsifiers. |
| `docs/bhmea/GIT-RAW-OBJECT-CAPTURE.md` | This proposed producer and controller-dependency contract. |
| `integrations/scm/git_objects.py` | Data-only raw-object validation, exact tree expansion and Git consistency checks. |
| `tests/unit/test_git_objects.py` | Binary framing/hash/tree/path/mode/count falsifiers using authored data, no Git. |
| `integrations/scm/source_acquisition.py` | Actual offline source staging → custody → external proof producer and trusted-receipt verification; online refusal. |
| `tests/unit/test_source_acquisition.py` | Real custody integration, retained-byte tamper/storage/error and trust-label tests. |
| `scripts/capture_git_source.py` | Explicit local operator CLI for offline import/verification; online subcommand unavailable. |
| `tests/unit/test_capture_git_source_cli.py` | Real offline CLI/producer path with native/network entry points poisoned. |

Do not edit #392, Java safety, legacy containment, DB models/seals, accepted-spec
authority, Dockerfiles, dependency/tool/image pins, app routes or remote state.
The controller's later files are NOT silently part of these ten. No new Python
dependency is needed for the offline subset. All source/object input is data;
never import Python from an input, capture or evidence directory.

## 3. Raw object input format and exact verification

`objects_dir` is an existing private owner-controlled real directory. It contains
ONLY regular single-link files named `<40-lowercase-nonzero-hex>.object`; no
subdirectories, manifest-driven exclusion list, symlinks, special files or
unreferenced extras. Enumerate with a hard count bound before building an index.
All components are opened no-follow through held directory descriptors. Inputs
must stay exclusively controlled/read-only throughout verification and capture;
same-UID/mount administrators are outside a process-local proof.

Each file is one uncompressed Git object PREIMAGE, not a loose zlib object,
packfile, archive or pretty-printed representation:

```text
ASCII object type + SP + canonical decimal payload byte length + NUL
exact payload bytes
EOF
```

Allowed types are exactly `commit`, `tree` and `blob`. Header length is at most
64 bytes; decimal is `0` or a nonzero leading digit followed by digits. Reject
negative, signed, padded, leading-zero, missing, duplicate or trailing framing.
Enforce type-specific and aggregate sizes before allocation and while reading.
Verify filename OID equals SHA-1 of the ENTIRE preimage. Also compute independent
SHA256 of that preimage, and payload SHA256 where needed for source inventory.
The native Git SHA-1 format is a compatibility identity, not a new claim of
collision-resistant external authentication. Retaining SHA256 does not convert
an operator-supplied expected SHA-1 into authenticated provider provenance.

Expected commit must be one nonzero 40-lowercase-hex OID. Do not accept branches,
abbreviations, `HEAD`, tags, path expressions, reflogs, refspecs or recursive
peeling. Its verified object must have type commit. Preserve commit bytes
exactly; parse only a bounded header sufficient to establish:

- First line is exactly `tree <40-lowercase-nonzero-hex>` followed by LF.
- Exactly one tree header exists before the first empty LF-delimited line.
- Parent headers, if present, have the same exact OID grammar, at most 64.
- Header continuation is data, not another field; malformed header structure
  or a second tree declaration rejects. Author/committer/signature bytes remain
  observed data; commit signatures are explicitly `not_checked`.

Parent commits need not be present; this is the expected commit's source tree,
not a history-integrity traversal. A tag object is never silently a commit.
Commit message bytes are retained without executing or decoding them as code.

Tree payload is parsed from raw bytes, never `git -p`, line-splitting output or
an OS checkout. Each entry is ASCII octal mode, SP, raw basename, NUL, exactly
20 OID bytes. Accept modes ONLY `40000`, `100644`, `100755`. Reject `120000`
symlinks, `160000` gitlinks/submodules and all other modes for the WHOLE capture;
do not quietly omit unsupported entries. Verify referenced type is tree for a
directory and blob for a regular file. Preserve Git executable mode in the SCM
proof, but never set the materialized file executable or execute it.

Require canonical Git byte ordering (directory names compare with trailing `/`,
regular names with trailing NUL), no duplicate basename or file/directory
collision. Parse names as strict Unicode-scalar UTF-8. Apply the custody path
rules: no empty/dot/dot-dot, slash, backslash, C0/C1 control, `.git` component or
unsafe absolute/path escape. Do not normalize Unicode, line endings or contents.

Expand reused tree objects at EACH path, charging file/entry/content/path/depth
caps to expanded source, not only unique OIDs. Reject ancestor cycles. Verify
the exact referenced object closure and reject extra/missing objects. Root and
non-root empty trees retain their exact Git identity; empty directories remain
outside the separate source-content hash, consistently with custody.

`.gitattributes`, build manifests and other regular files are inert bytes.
Never apply attributes, textconv, filters, hooks, submodule operations or LFS
hydration. The explicit content policy is `git-committed-blobs/1`: LFS pointer
blobs stay literal committed bytes. This is NOT proof that externally referenced
LFS objects, dependencies or the runtime application's complete inputs exist.
No heuristic that fails to find an LFS pointer can imply that stronger claim.

## 4. Bounded producer and actual custody integration

The proposed APIs in `source_acquisition.py` are:

```text
capture_offline_objects(
    objects_dir: Path, *, store_root: Path, evidence_root: Path,
    binding: CaptureBinding, repository_claim: GitHubRepositoryClaim | None,
    limits: GitCaptureLimits,
) -> GitCaptureResult

verify_offline_capture(
    *, store_root: Path, evidence_root: Path,
    expected_receipt: CaptureReceipt, proof_id: UUID,
    expected_proof_digest: bytes,
) -> GitCaptureResult

capture_github_commit(...) -> NoReturn  # constant unavailable failure in v1
```

All public structures use exact frozen records, bytes/tuples/exact primitive
types and constructor plus boundary revalidation. GitHubRepositoryClaim has
only `owner` and `repository`; in offline mode it is explicitly an unverified
operator label, never an authenticated endpoint. GitCaptureLimits embeds exact
CaptureLimits and may only lower the reviewed ceilings. Public results contain
the actual CaptureReceipt, proof UUID/digest, expected commit/root-tree OIDs,
content policy and explicit trust/status labels below. No callback/runner seam
exists in the production API; controlled tests may patch trusted internals.

Use REAL `services.scan.source_capture.LocalSourceCaptureStore`. Current public
API: constructor `(root: Path, *, limits: CaptureLimits | None = None)`,
`capture(source: Path, binding: CaptureBinding) -> CaptureReceipt`, and
`verify(receipt: CaptureReceipt) -> Path`. CaptureBinding contains org/codebase/
request UUIDs plus resolved_commit; it is an assertion until this producer
checks that commit. No fictional VerifiedCapture type or private custody helper
import creates tenant/lease/SCM authority.

Required order:

1. Validate exact bounded arguments and disjoint existing private real roots.
   Freeze scope/expected commit; validate complete commit/tree metadata and
   declared expanded sizes/path/mode inventory before allocating source files.
2. Allocate a fresh random attempt UUID directory exclusively beneath the
   external evidence/work root. Never overwrite/reuse any attempt or source
   storage object, even after failure. Retain failed work for later reviewed
   cleanup; no generic delete/repair function is added.
3. Create source-only staging with owned 0700 directories and 0600 regular
   single-link files, via held no-follow descriptors and O_EXCL creation.
   Stream blobs in at most 64 KiB chunks, accounting partial writes and hashes;
   verify complete preimage/EOF and input observable identity before acceptance.
   Reused blob OIDs may populate multiple paths, each charged to source bounds.
4. Independently read back staging bytes and compare the complete path/size/
   payload-SHA256 inventory AND reconstructed Git blob OIDs. An acknowledged
   write alone is not retained source proof. No custody receipt exists yet.
5. Call actual custody `capture`, then actual `verify` on its returned receipt.
   Independently read the retained capture through bounded no-follow descriptors
   and verify its complete inventory and Git blob OIDs against the expanded
   commit tree. Reject any missing/extra/changed path or byte.
6. Persist the receipt and external proof with exclusive files, fsync, independent
   readback, restrictive published modes and a final completion marker. No
   result is returned on any source/evidence/readback/flush error. A failure
   after custody publication can leave an orphan capture, never an implied
   committed DB seal or resumable success. Retain its exact diagnostic identity.

CaptureBinding.resolved_commit must equal the verified commit OID. Custody's
tree/inventory/manifest digests are copied only from actual verified returned
evidence, never filled with Git tree OIDs, graph hashes, image strings or zeros.
No detector runs, accepted specs, findings or identity jobs are manufactured.

## 5. Distinct identities and external proof layout

Keep all SCM proof OUTSIDE custody's exact `source/`, `manifest.json`, `SEALED`
object layout. Do not add a fourth file to that object or repurpose the accepted
spec `acceptance_evidence_digest`. DB seal/source-authority binding is a separate
reviewed integration; the current store does not authenticate SCM provenance.

External finalized proof UUID contains:

```text
request.json              exact frozen operator request/profile
commit.object             exact verified commit preimage
trees/<oid>.object        exact verified reachable tree preimages
objects.json              exact object type/size/OID/preimage-SHA256 inventory
capture-receipt.json      actual bounded custody receipt and inventory bytes
producer.json             observed source/interpreter identities, not attestation
code/<fixed-name>.py      exact observed producer module source bytes
proof.json                closed scoped consistency record
COMPLETE                  domain proof digest + LF; not a DB/lease marker
```

Staging/diagnostic work is retained under a separate attempt directory, not
silently mixed into the closed finalized proof layout. Blob payloads are retained
in the actual source capture; their preimages can be reconstructed using the
canonical header and measured payload. Preserve raw commit/tree preimages
exactly. Authored summaries never replace immutable raw bytes.

The closed `proof.json` schema is `scanipy-git-source-consistency/1`. It binds:

- Org, codebase, request, generated capture UUID and proof UUID.
- Exact expected commit OID, actual commit preimage SHA256 and root-tree OID.
- Actual custody profile/limits, manifest/inventory/tree identities, counts and
  sorted per-path Git mode/blob OID/payload SHA256/size.
- Exact request/object inventory/receipt/raw metadata file identities.
- `content_policy="git-committed-blobs/1"`,
  `object_consistency="verified"`, `source_capture="verified"`,
  `remote_authentication="not_established"`,
  `commit_signature_verification="not_checked"`,
  `native_execution="not_performed"`, `controller_attestation="not_established"`.
- Optional unverified repository claim, actual producer code/interpreter
  observations and exact invocation. Missing actual image/controller identities
  remain null/unavailable, never invented `env_digest` values.

Use compact sorted-key UTF-8 JSON with duplicate keys, non-finite numbers,
unexpected fields/types and noncanonical encodings rejected. Metadata is bounded
before decode by bytes, depth 24 and 100,000 values. The proof digest is SHA256
of ASCII `scanipy-git-source-consistency/1`, LF and exact proof bytes. Raw object
hashes use their own preimage algorithms. Source tree remains custody's
`sha256-length-prefixed-path-and-content-v1` with NO domain prefix; source
inventory keeps its existing versioned domain. These digests are not aliases.

Replay verification requires a trusted expected receipt AND trusted expected
proof digest/UUID from the local operator or later durable store. Recomputing a
new manifest's own digest is insufficient. Rehash all raw proof metadata and
actual captured blob bytes, re-expand the exact tree, and compare complete
inventories/scope/commit. Retain the offline trust labels; verification does not
upgrade it to authenticated GitHub provenance. RO mounts and active DB leases
remain mandatory before downstream production tools use the returned path.

### 5.1 Exact wire closure (approved for offline adapter/CLI implementation)

Every key below is required; unknown keys reject at EVERY depth. Only explicit
nulls/unions permit alternatives. Require exact bool/int/str/list/dict types,
not coercion. UUID is canonical lowercase hyphenated text; OID is nonzero 40
lowercase hex; H is 64 lowercase SHA256 hex without a prefix (internal hashes
are 32 bytes). P is a safe relative source path; A is a fixed-layout artifact
path. Byte counts are nonnegative exact ints, never bool, and within signed
64-bit plus the smaller profile cap. Arrays are bounded and ordered. Only
explicitly set-like inventories, IDs and paths require uniqueness; positional
argv preserves order and multiplicity, including legitimate repeated values.

Canonical bytes are compact sorted-key UTF-8 JSON with ensure_ascii=False.
Before decoding, cap bytes, depth 24 and 100,000 values; reject duplicate keys,
non-finite numbers, invalid Unicode and trailing data. Re-encoding must equal
the original bytes, including integer/string encoding and whitespace. Raw file
hash is SHA256 of exact bytes. Only a named domain digest uses
`D(schema, bytes) = SHA256(ASCII schema + LF + bytes)`.

Exact shared records:

```text
Binding = {org_id:UUID, codebase_id:UUID, request_id:UUID, resolved_commit:OID}
RepositoryClaim = {owner:str, repository:str}  # section 9 grammar; unauthenticated
Artifact = {path:A, size:int, sha256:H}
CaptureLimits = {
 max_files:int, max_entries:int, max_depth:int, max_path_bytes:int,
 max_file_bytes:int, max_total_bytes:int, max_metadata_bytes:int
}
ObjectLimits = {
 max_objects:int, max_commit_bytes:int, max_commit_header_bytes:int,
 max_parent_oids:int, max_tree_bytes:int, max_total_tree_bytes:int,
 max_total_preimage_bytes:int, max_proof_json_bytes:int, max_proof_bytes:int
}
```

Limits are positive, no greater than section 6 ceilings. The custody record
matches the actual seven-field #392 type. Compare limits across all artifacts;
they cannot raise hard bounds. Artifact names derive only from fixed layout,
verified OIDs and the trusted module table, never arbitrary read/execute paths.

`request.json` (32 KiB maximum), exactly:

```text
{
 schema:"scanipy-git-capture-request/1", operation:"offline-objects",
 binding:Binding, repository_claim:RepositoryClaim|null,
 content_policy:"git-committed-blobs/1",
 capture_limits:CaptureLimits, object_limits:ObjectLimits
}
```

Input/store/evidence roots remain explicit trusted invocation arguments, not
path authority from request JSON. Replay uses its trusted roots and UUIDs.

`objects.json` (8 MiB maximum), exactly:

```text
{
 schema:"scanipy-git-object-inventory/1", commit_oid:OID,
 objects:[{oid:OID, type:"commit"|"tree"|"blob", size:int,
           preimage_sha256:H, payload_sha256:H}, ...]
}
```

Rows are OID-sorted, at most 20,002; size is PAYLOAD size. Set equality is one
expected commit plus its unique reachable tree/blob closure, without parent
history or extras. Recompute every field. A retained commit/tree preimage's
Artifact.sha256 equals its preimage_sha256, not its payload hash.

`capture-receipt.json` (2 MiB maximum), exactly:

```text
{
 schema:"scanipy-source-capture-receipt/1", object_id:UUID,
 binding:Binding, limits:CaptureLimits, tree_digest:H,
 inventory_bytes_b64:str, inventory_digest:H, manifest_digest:H,
 file_count:int, content_bytes:int
}
```

This is a NEW adapter-owned codec for ACTUAL #392 CaptureReceipt fields, not a
fictional existing helper. #392 exposes no public receipt serializer. The b64
field maps receipt.inventory_bytes exactly using canonical padded standard
base64, capped before decode at 1,398,104 ASCII chars and afterward at 1 MiB;
base64 re-encoding must match. All remaining names directly map existing
dataclass fields, with hashes decoded to bytes and exact binding/limits types.

Decoded inventory is exactly the existing canonical
`{schema:"scanipy-execution/source-inventory/1",files:[{path:P,sha256:H,size:int},...]}`.
Paths are Unicode-scalar sorted; count/sum/digest match receipt and limits.
Call ACTUAL `LocalSourceCaptureStore.verify` for manifest/marker/source checks;
codec validity does not replace it. The expected receipt still comes from a
trusted operator/store, not the candidate's own receipt file.

`producer.json` (128 KiB maximum), exactly:

```text
{
 schema:"scanipy-git-producer-observation/1",
 entrypoint:"integrations.scm.source_acquisition.capture_offline_objects",
 invocation_kind:"library_call", child_argv:null,
 python:{implementation:str, version:str, executable_path:str, executable_sha256:H},
 source_files:[{module:str, observed_path:str, artifact:Artifact}, ...],
 source_file_binding:"observed-file-bytes-only", code_revision:null,
 image_manifest_digest:null, controller_receipt_digest:null,
 execution_artifact_attestation:"not_established"
}
```

Source rows are module-sorted and EXACTLY the actually loaded trusted modules
integrations.scm.git_objects, integrations.scm.source_acquisition and
services.scan.source_capture. Fixed artifacts are respectively code/git_objects.py,
code/source_acquisition.py and code/source_capture.py. Each is capped at 1 MiB,
3 MiB aggregate. Obtain actual loaded source-file observations internally; never
load a module from input/evidence or use caller-provided identities or Git HEAD.
Read/copy/read back actual regular bytes with observable-change checks. Required
source-file read failure is fatal, not an empty/missing provenance row.
The three module-file observations do not require private source-file modes:
development checkout modes are not execution authority. No-follow, regular-file,
single-link, bounded-size, actual hash/readback and observable-change checks
remain required. Input/staging/custody/proof permissions are not relaxed.

These bytes are NOT proof they executed: existing bytecode, prior imports and
mutable globals cannot be authenticated by __file__. No marshal/code-object
expansion is added. Later #400 must bind fresh isolated read-only loaded closure.
The library invents no child argv and does not collect unrelated host argv/env
that might contain credentials. It invokes no Git to obtain a revision.

Interpreter implementation/version are observed from this process, at most
32/4,096 UTF-8 bytes. Executable path is internally observed absolute text,
at most 4,096 bytes; hash the actual Linux self executable through the fixed
kernel `/proc/self/exe` descriptor, streamed under 128 MiB. That fixed proc
link is not arbitrary input-path following. Missing/read/hash failure is fatal.
This observation does not attest shared libraries/imports/image; no supplied
hash or code revision can fill the three fixed-null authority fields.

`proof.json` (8 MiB maximum), exactly:

```text
{
 schema:"scanipy-git-source-consistency/1", binding:Binding,
 capture_object_id:UUID, proof_id:UUID, commit_oid:OID,
 commit_preimage_sha256:H, root_tree_oid:OID,
 content_policy:"git-committed-blobs/1", repository_claim:RepositoryClaim|null,
 capture_limits:CaptureLimits, object_limits:ObjectLimits,
 custody_profile:"scanipy-local-source-custody/1",
 source_tree_algorithm:"sha256-length-prefixed-path-and-content-v1",
 source_tree_digest:H, source_inventory_digest:H, source_manifest_digest:H,
 file_count:int, content_bytes:int,
 files:[{path:P, mode:"100644"|"100755", blob_oid:OID, size:int, payload_sha256:H}, ...],
 directories:[{path:P, tree_oid:OID}, ...], artifacts:[Artifact, ...],
 object_consistency:"verified", source_capture:"verified",
 remote_authentication:"not_established", commit_signature_verification:"not_checked",
 native_execution:"not_performed", controller_attestation:"not_established"
}
```

Files/directories are Unicode-path-sorted, disjoint and equal the FULL expanded
raw tree. Directories excludes the separately named root. Modes/types/hashes/
sizes come from verified objects. Counts/content/inventory match receipt;
binding/commit/claim/limits match request and all artifacts. Custody hashes are
actual verified receipt identities, never Git tree/blob hashes.

Artifacts is path-sorted and equals EXACTLY request.json, objects.json,
capture-receipt.json, producer.json, commit.object, reachable raw tree files and
the three named source-code files. It excludes proof.json/COMPLETE to avoid
circular hashing. Rehash each artifact; reject missing/extra roles/paths, unsafe
files, size/hash mismatch and cross-request/capture substitution. Newly
self-rehashed metadata cannot replace the trusted expected proof/receipt or
disagree with independently re-expanded raw objects and actual source bytes.

COMPLETE is exactly 65 ASCII bytes: lowercase hex of
`D("scanipy-git-source-consistency/1", exact proof bytes)` plus LF. No second
line, JSON or path content. Exclusive publication/fsync/readback is required.
Presence/self-hash alone is not expected authority, a DB seal or active lease.

Result wire (32 KiB maximum), exactly:

```text
{
 schema:"scanipy-git-capture-result/1", operation:"created-offline"|"verified-existing",
 binding:Binding, capture_object_id:UUID, proof_id:UUID, proof_digest:H,
 source_tree_digest:H, source_inventory_digest:H, source_manifest_digest:H,
 file_count:int, content_bytes:int,
 remote_authentication:"not_established", controller_attestation:"not_established",
 caller:{kind:"library_call",entrypoint:str}
      | {kind:"cli",entrypoint:"scripts/capture_git_source.py",argv:[str,...]}
}
```

Library entrypoint is exactly capture_offline_objects or verify_offline_capture
in the fixed module and matches operation; no argv field. CLI constructs its
own caller observation from ACTUAL bounded startup argv, not a provided identity
object: at most 64 args, 4 KiB each, 16 KiB aggregate plus encoded result cap.
It is actual CLI argv, not a spawned Git invocation or artifact attestation.
It does not rewrite the immutable library producer proof to claim the CLI was
one of that record's three loaded source modules. Complete CLI/runtime closure
remains #400's later obligation. No caller union value enables online mode.

Verification is read-only and does not create a proof or mutate the original
producer record. Return the trusted matched original identities with operation
verified-existing/current caller; do not restamp original runtime observations.

Private failure wire, if storage remains writable (8 KiB maximum), exactly:

```text
{
 schema:"scanipy-git-capture-failure/1", binding:Binding|null, attempt_id:UUID|null,
 stage:"input"|"objects"|"staging"|"custody"|"capture-verification"|"proof-publication"|"result",
 reason:"invalid-input"|"unsupported-object"|"limit"|"changed-input"|"storage"|"evidence"|"unavailable-online",
 capture_object_id:UUID|null,
 capture_state:"not-started"|"unknown"|"receipt-returned-unverified"|"verified-orphan",
 proof_id:UUID|null, completion_claim:false, cleanup:"not-attempted-retained-for-review"
}
```

IDs exist only if actually allocated/returned. Custody failure without receipt
leaves object identity unknown; never scan/adopt an orphan by discovery. A
receipt whose later verification fails is not verified. Failure-record write
failure is fatal and establishes NO retained record; no planned path is reported
as written. Public errors are fixed categories. No failure record/marker allows
path reuse, cleanup or restart adoption outside the later reviewed protocol.

Additional required wire tests: two independent raw-object builders agree on
positive object/tree identity; receipt bytes round-trip exactly; every unknown
key/type/order/nullability violation fails; metadata-only/self-rehashed proof,
role/path/source/code/receipt substitutions fail against trusted expected
evidence; library observations never invent child argv/revision/image authority;
legitimate repeated CLI argument values are retained unchanged.

## 6. Conservative bounds and CLI

Independent initial ceilings, not measured stage budgets:

| Quantity | Maximum |
| --- | ---: |
| Expanded files / entries / depth / UTF-8 path | 10,000 / 20,000 / 64 / 1,024 bytes |
| Blob payload per file / total expanded source | 64 MiB / 512 MiB |
| Unique objects, including root tree and commit | 20,002 |
| Commit payload / commit header / parent OIDs | 1 MiB / 64 KiB / 64 |
| One tree payload / all tree payloads | 8 MiB / 32 MiB |
| Input object preimages, including headers | 547 MiB |
| Custody inventory/manifest | Existing independent 1 MiB ceiling |
| One external proof JSON / all finalized proof bytes | 8 MiB / 64 MiB |
| Copy/read/hash chunk | 64 KiB |
| Proposed outer offline process | 512 MiB memory, 300 seconds, 2 GiB dedicated scratch |

Do not shrink source content silently to fit metadata or scratch limits. Several
independent maxima may not fit simultaneously; a limit violation is a complete
bounded refusal, not permission to return a partial source tree. Whole-object
hashing/copying must stream; no 64 MiB blob or 512 MiB repository bytes object.
The offline outer envelope must be implemented/evidenced separately before
adversarial production use; filesystem calls can block beyond user-space timing.

Proposed CLI subcommands:

- `offline-objects`: explicit objects/store/evidence roots, org/codebase/request
  UUIDs and exact commit; optional paired GitHub owner/repository CLAIM only.
- `verify-capture`: explicit store/evidence roots, proof UUID, trusted expected
  proof digest and trusted expected receipt file; no directory self-discovery.
- `github`: always exit unavailable BEFORE destination, credential or process
  staging. It must not accept an `--allow-network`/runtime-json bypass.

The operator CLI is not an authenticated service API. Scope UUIDs do not prove
tenant authority; no HTTP, queue, legacy app or DB admission route is added.
Limits are fixed/reviewed defaults, not flags that can increase the ceilings.
Exit 0 means only the named offline consistency/custody operation completed;
stdout is a closed bounded result with receipt/proof IDs and digests, not raw
source or an inferred analysis result. Invalid input exits 2, unavailable online
mode exits 69, other incomplete work exits 1. Errors use fixed categories; raw
paths/source/exception chains stay in bounded private diagnostics.

## 7. Mandatory offline implementation falsifiers

- [ ] Independently authored commit/tree/blob preimages, binary/Unicode/empty
  content, executable-mode preservation in proof but nonexecutable source,
  reused tree/blob OIDs and empty directories, without invoking Git.
- [ ] Wrong type/OID/preimage/size/header, trailing bytes, malformed commit tree
  header, duplicate/out-of-order/tree-path conflicts, missing/extra objects.
- [ ] Symlink/gitlink/special mode, invalid path/UTF-8, cycles, count/depth/byte
  caps, duplicate-content expansion accounting and LFS-pointer trust labels.
- [ ] All private-root/no-follow/single-link/exclusive-create checks; short and
  corrupt writes, observed input mutation, source/evidence read/stat/fsync failure.
- [ ] Real custody capture+verify, separate proof finalization, retained-source
  Git rehash, failure after custody publication and no false resumable/DB success.
- [ ] Replay against trusted receipt/proof digest; reject self-rehashed tampering,
  cross-request/capture/proof swaps and raw metadata deletion/replacement.
- [ ] Real offline CLI invokes this producer; native subprocess/network/Git
  entry points poisoned. Online fails before source/credential/path allocation.
- [ ] All dedicated tests selected by actual CI/pre-push markers; normal hooks,
  full configured suite, independent security review and canonical APPROVE.

## 8. Required separate controller issue — not a caller boolean

Root has created and claimed the separate bounded runtime/egress-controller
[#400](https://github.com/scanipy/scanipy/issues/400); root owns its initial
design. No controller code/runtime launch or host networking change is thereby
authorized, and the controller remains absent. Proposed deliverables: reviewed acquisition
controller contract, one trusted local launcher/runtime module, its unit
falsifiers and resource-approved isolated runtime tests. Exact files/image
integration must be approved there; they are not implicit additions here.

The controller lives OUTSIDE the native worker's untrusted execution boundary.
It owns Docker/network-namespace/cgroup/storage operations and a read-only
reviewed runtime policy. It never exposes the Docker socket, host credentials,
firewall capability or configurable helper execution to the worker/source.

Proposed authority exchange: one controller-created private Unix-domain channel,
credential-checked using SO_PEERCRED against the separately configured controller
UID/instance. The worker receives an immutable sealed descriptor via SCM_RIGHTS;
the channel path/peer identity cannot come from scan JSON/env/CLI. Its bounded
closed launch receipt binds fresh nonce/execution UUID, request digest, expected
commit/repository, code/tool/CA/runtime identity, actual child container/cgroup/
netns identity, resource/mount/egress policy and expiry. The worker independently
checks its actual namespace/cgroup and request against that receipt. A descriptor
or JSON assembled by the caller is not authority; no such acceptance code exists
in the first subset. Channel construction, privilege separation, replay/freshness
and shutdown must be security-reviewed before this interface is implemented.

The actual supervisor must enforce and observe:

- One dedicated network namespace with default-deny IPv4/IPv6 egress; only
  configured public IPv4 destination TCP 443 is reachable. No DNS, metadata,
  loopback/host gateway, private/link-local/reserved/multicast or proxy fallback.
  A Docker internal network alone is NOT evidence of all these restrictions.
- Controller-selected GitHub address, independently validated public IPv4 and
  bound to the job. Worker resolution is fixed via curl resolve mapping; TLS
  hostname remains github.com, certificate validation required, redirects off.
  URL syntax/public-IP checking alone is not enforced egress or SSRF proof.
- Read-only root and actual reviewed source/tool mounts; no capabilities,
  no-new-privileges, no host secrets/socket and private noexec scratch/storage.
- Initially proposed 2 CPU, 4 GiB memory with no extra swap, 64 PIDs, hard scratch
  quota and 300-second total watchdog, including cleanup; actual inspected
  cgroup/netns/mount settings and descendant containment retained as evidence.
- Kill/reap/retire only its own exact execution instance; never identify a user
  container by a broad name or terminate/reconfigure the running app/database.

The owner has now confirmed this machine is the presentation machine. Root is
recording its exact profile. Available memory/swap pressure remains a live
launch constraint, not a historical fixed budget; recheck before each approved
probe. No 4 GiB worker or native probe is authorized by this proposal.

## 9. Proposed future native Git profile, pending controller review

Initial endpoint subset: public GitHub HTTPS only, owner/repository fields with
closed ASCII grammars (owner 1–39 alphanumeric/internal hyphen; repository 1–100
alphanumeric, underscore, hyphen or dot, not dot/dot-dot and no `.git` suffix).
Construct exactly `https://github.com/<owner>/<repository>.git`. No arbitrary
URL, userinfo, auth, port, query/fragment, percent encoding, SSH, file/ext
protocol, private repository, redirect, branch or revision expression. Any
unsupported/not-reachable exact commit fails; no fallback clone/checkout.

Use the actual verified `/usr/bin/git` and fixed libexec/helper closure, including
the resolved `/usr/lib/git-core/git-remote-https` target and hashes. Record the
full installed Debian package/build identity, not merely upstream version. The
existing pin is `1:2.39.5-0+deb12u3`; this contract does not infer its vulnerability
status from generic upstream 2.39.5 ranges. A package pin/hash is NOT measurement
of an installed binary/helper. Image OCI manifest/RepoDigest, local config image
ID, code content, Python, CA bundle and actual executable/helper hashes are
distinct evidence. Existing locally present images are not proof of a corrected
rebuilt runtime or signed/approved environment.

Every native call uses [shared bounded transport](BOUNDED-PROCESS.md), explicit
private cwd and exact closed env. Proposed keys only: LANG/LC_ALL C.UTF-8,
fixed PATH and GIT_EXEC_PATH, private HOME/TMPDIR, GIT_CONFIG_SYSTEM and
GIT_CONFIG_GLOBAL `/dev/null`, GIT_CONFIG_NOSYSTEM=1, GIT_TERMINAL_PROMPT=0,
GIT_NO_REPLACE_OBJECTS=1, GIT_OPTIONAL_LOCKS=0 and GIT_ATTR_NOSYSTEM=1.
No inherited Git configuration count/parameters, loader/Python hooks, proxy,
SSH/askpass, credential, tracing or ambient HOME files.

Exact trusted `-c` keys/values, never a caller map: disable hooks using an empty
read-only directory, empty credential helper/askpass, attributes `/dev/null`,
fsmonitor off, gc.auto=0, maintenance.auto=false, submodule.recurse=false,
fetch.recurseSubmodules=false, fetch.parallel=1, fetch.writeCommitGraph=false,
fetch/transfer.fsckObjects=true, protocol.allow=never, protocol.https.allow=always,
protocol.version=0, HTTP redirects false, proxy empty, TLS verify true, fixed CA
bundle, maxRequests=1 and exact controller-supplied github.com:443 public-IPv4
curl resolve mapping. Full effective config must be checked against the actual
pinned implementation before enabling this profile. Do not rely on Git silently
ignoring unknown safety configuration keys.

No clone/bundle-URI operation, fetch.bundleURI configuration, bundle heuristic or
protocol-v2 bundle discovery is allowed. Fresh private configuration and the
closed protocol-0 fetch route are deliberate; upstream bundle-URI advisories
reinforce this restriction, not permission to pretend an unverified config flag
is enforcement. Egress containment remains independent of Git configuration.

Only planned operations:

1. Exclusively fresh private bare DB, `init --bare --object-format=sha1` with
   empty trusted template directory. Never reuse caller `.git`, alternates,
   config, worktree or source-selected helper/template.
2. Fetch constructed exact URL and full OID using `--depth=1 --no-tags
   --no-recurse-submodules --no-auto-maintenance --no-write-fetch-head
   --no-write-commit-graph --jobs=1`. No refspec/remote name from input.
3. `cat-file --batch-check` / `cat-file --batch` with one immutable stdin list
   of exact full OIDs only. Validate exact requested output order/type/size/OID,
   LF headers, payload lengths, delimiters and EOF. Never add textconv/filters,
   pretty-printing, path expressions, follow-symlinks, all-objects or command mode.

Pre-check sizes, group blob batches within 128 MiB spool maximum INCLUDING wire
framing, cap native invocations at 128 and cumulative elapsed at 300 seconds.
All expanded source/metadata limits still apply. Retain complete raw bounded
process evidence and real argv/env/error/exit/tool identities outside the capture.
Raw online process retention may exceed the offline 64 MiB proof budget; the
controller contract must set a separate explicit aggregate retention/quota and
proof version before activation. Do not discard successful stdout frames merely
because equivalent blob bytes now exist in the capture.

Primary behavior references inspected read-only, not runtime acceptance:
[Git v2.39.5 cat-file](https://github.com/git/git/blob/v2.39.5/Documentation/git-cat-file.txt),
[fetch options](https://github.com/git/git/blob/v2.39.5/Documentation/fetch-options.txt),
[HTTP configuration](https://github.com/git/git/blob/v2.39.5/Documentation/config/http.txt),
[transfer object checks](https://github.com/git/git/blob/v2.39.5/Documentation/config/transfer.txt).
Fetch failure may leave untrusted objects in a DB; never retry/reuse that DB as
clean or infer successful acquisition from its existence.

## 10. Required next actions; no parent acceptance implied

- [x] Root approve/adjust this offline producer's exact seven-file API/codec/
  proof/limits and mandatory falsifiers before implementation.
- [x] Implement actual offline object→custody→proof and trusted-receipt replay;
  preserve unverified-provider labels and all containment routes.
- [ ] Design/review and implement the separately claimed #400 controller with real peer/fd
  authority, egress/cgroup/storage/mount enforcement and exact file/image scope.
- [ ] Review measured runtime/tool/helper/config closure and build only with
  explicit authorization; no ad-hoc pip overlay or invented OCI identity.
- [ ] Approve a fresh resource-aware bounded online probe only after controller,
  dependencies and canonical review gates; preserve all raw success/failure data.
- [ ] Integrate real source authority with immutable DB request/seal/initial lease,
  restart/orphan policy and irreversible retirement. Do not fake an old CPG FK.
- [ ] Wire detector and identity workers to that SAME verified read-only capture;
  preserve raw detections before ANY identity, including solver canonicalization.
- [ ] Extend provider/private-repo/SCM authentication scope separately where the
  submission requires it; the initial GitHub public/offline subset is not a
  reduction of the full target or a claim of all-provider compatibility.
- [ ] Rehearse on the now-confirmed presentation machine and prove applicable
  resource, R05/R07/R08/R16/G0/G1/G2 and full submission criteria independently.

No full R-task or submitted claim is marked complete by this design, an offline
consistency receipt, the shared transport tests or a future single Git probe.

## 11. Local implementation evidence in progress

Shared transport was checkpointed separately at
`62a61583ba340405fde8b30ff636ad50d800ddaf` (102 focused tests; 1,569 full-suite
passes and 51 existing skips; normal local hooks passed). No native/controller
acceptance is implied. Initial data-only Git core: 61 passing tests.

The first adapter run stopped after two failures (with nine intervening JSON
controls passing), before proof publication: the module-file observation had
incorrectly reused private-source permissions and rejected actual checkout
files at mode 0664 (parent directories 0775). Root approved the narrow
observation-versus-authority correction above; no checkout modes were changed
and no input/custody permission check was weakened. Final integration results
and independent review are recorded below; this is not full runtime acceptance.

The implemented imports are `GitCaptureLimits`/`GitObjectLimits` from
`integrations.scm.git_objects`, and `capture_offline_objects`,
`verify_offline_capture`, `GitHubRepositoryClaim`, `GitCaptureResult`,
`encode_receipt`/`decode_receipt` from `integrations.scm.source_acquisition`.
The operator entrypoint is `python -m scripts.capture_git_source` with the
reviewed checkout explicitly installed/on the trusted Python import path.
Run it only in the authorized offline diagnostic context until #400 establishes
the outer bounds. Input is the raw preimage directory from section 3, not a
checkout, loose compressed Git DB, archive or network URL. Store/evidence/input
roots must already exist as disjoint private 0700 directories. No command
automatically acquires network objects, deletes failed work or enables a legacy
route. `verify-capture` requires the independently trusted expected receipt,
proof UUID and proof digest; discovering a candidate receipt is not authority.

The first reviewed focused checkpoint had 158 executed cases, zero
failures/errors/skips (10.101 seconds;
`/tmp/scanipy-398-offline-final-focused.xml`). Root independently reran all 158
cases successfully in 10.321 seconds
(`/tmp/scanipy-398-offline-root-review.xml`) and approved this bounded offline
scope. The raw-core peer review is narrower than that full adapter/CLI review.
The suite exercises the
actual local custody backend and CLI dispatch with native/network entry points
poisoned. The two raw-object builders are independent fixture encoders and do
not call the production encoder/hasher. Canonical peer review of the raw-object
core and root review of the full adapter/CLI identified and resolved:

- Aggregate metadata/path admission before copying/decoding and exact tree
  closure/expanded limits; stream hashes, not aggregated blob buffers.
- Child-descriptor ownership before closing its parent, no retry of a possibly
  released close-failed FD, and retention of earlier explicit failure causes.
- Aggregate escaped UTF-8 JSON bytes and queued-plus-processed values before
  serialization; already-read proof/marker bytes charged before more retention.
- Final cleanup-only failures refuse the operation result even if COMPLETE
  already exists. A new failure record uses fresh descriptors to the original
  attempt's exact dev/inode/owner/mode; replacement directories are not adopted.
- CLI result output is exact canonical JSON without an extra newline. Repeated
  argument values retain their order/multiplicity. Replay never rewrites the
  original library producer observation as a CLI execution attestation.

The subsequent approved primitive-snapshot refinement rejects poisoned UUID
integer slots and PosixPath internal containers before formatting or iteration.
It reconstructs private UUID/path values from bounded exact primitives and
actually uses the cloned roots across the custody and replay calls; cached
caller path strings are never accepted as authority. The implementation supports
the inspected CPython 3.11 `_parts` and 3.12 `_raw_paths` layouts and fails closed
on unknown layouts. Nineteen additional controls include real capture/replay
with poisoned path caches, post-copy mutation, oversized containers, and all
public receipt/binding/proof identity boundaries. The resulting focused run
passed all 177 cases, zero failures/errors/skips, in 10.890 seconds
(`/tmp/scanipy-398-offline-primitive-focused.xml`). Root independently passed
the frozen 177-case slice, zero skips, in 11.95 seconds
(`/tmp/scanipy-398-primitive-root-review.xml`) and approved the scoped delta.

Whole-tree Ruff and format checks pass (213 formatted files), and strict typing
passes for 99 source files including the owned CLI. An exploratory wider typing
check of all scripts additionally found the pre-existing unused
`import-untyped` ignore in `scripts/seed_test_org.py:244`; it is outside this
seven-file scope and the configured hook source selection, and was not changed.

An initial broad test command exited 4 before running tests because it named a
nonexistent `tests/invariants` directory. The following unit/integration run
passed 1,713 cases with 48 existing skips in 110.721 seconds
(`/tmp/scanipy-398-offline-full.xml`); this was a narrower selection, not the
repository-wide result.

The first correct `pytest tests/` run is retained as **failed**: 1,726 passes,
51 existing skips and one failure in 156.954 seconds
(`/tmp/scanipy-398-offline-repository-full.xml`). The unchanged existing
`test_distinct_semantics_are_not_collapsed[declaration]` exceeded the real
200 ms canonicalization deadline while broad suites were running concurrently
on this memory-pressured host. Its owner found no known clock-isolation leak;
host scheduling is a plausible explanation, not a demonstrated root cause.
The same unchanged target subsequently passed its diagnostic rerun
(`/tmp/scanipy-398-canonical-deadline-diagnostic.xml`). That diagnostic pass does
not erase the failed full run, and no production threshold or unrelated test
was changed. The subsequent serialized, unchanged configured `pytest tests/`
run passed 1,746 cases with 51 existing skips in 171.97 seconds
(`/tmp/scanipy-398-offline-repository-final.xml`). It includes all 177 new
offline controls and preserves the committed corpora ignore/addopts; external
AWS/DB opt-ins were unset.

Normal staged pre-commit checks passed without source rewrites, including
secret/private-key detection, Ruff/format and isolated mypy. The normal local
pre-push hook passed whole-tree Ruff/format (213 files), its complete 87-file
mypy selection and the configured unit/invariant test selection. The separate
broader strict mypy command passed all 99 source files including tools and the
new CLI. The final local commit still invokes normal pre-commit/commit-msg
hooks; exact-head CI and canonical review before merge remain required.
All online/runtime/controller and full-submission acceptance remains separate.
