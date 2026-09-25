# Local source custody — filesystem foundation

Status: locally implemented and independently security-reviewed for #392 under
#378/#362; required CI/canonical review and production acceptance remain pending.
Root owns the backend, this contract and its unit tests. Authority:
[DECISION-BHMEA-01](../DECISION-BHMEA-01-current-execution-authority-2026-09-25.md).
The separate occurrence-store agent owns DB grants, leases and retirement.

## Boundary and caller obligations

The backend copies a trusted resolver's private source-only directory into a
new per-request object. It never executes Git, a parser, scanned source, target
tests or build hooks. It neither resolves a branch nor proves that a supplied
commit names these bytes. A future trusted SCM resolver must verify the actual
commit/tree and exclude concurrent mutation throughout capture. Source custody
is one prerequisite of that protocol, not complete SCM provenance.

The source directory and store root must be absolute, disjoint, real directories
owned by the current effective UID with no group/other write permission. The
store root must additionally be private (0700). Every path component is opened
without following symlinks. Trusted container/host administrators, mounts and
concurrent same-UID adversaries are outside this process-local boundary. The
launcher must provide an exclusively controlled checkout and store root.

Only regular single-link files and real directories are supported. Refuse
symlinks, hard-linked files, devices, sockets, FIFOs, non-UTF-8/scalar names,
backslashes, control characters and any `.git` component. Nothing is silently
excluded. A normal clone including `.git` must first be converted into a verified
source-only tree by the acquisition adapter; this backend is not that adapter.
Empty directories do not contribute to the source digest, consistently with the
existing source-tree algorithm, but their safe structure is preserved.

Version-1 conservative configured caps are bounded independently: 10,000 files,
20,000 total directory entries, depth 64, 1,024 UTF-8 bytes per relative path,
64 MiB per file, 512 MiB total content and 1 MiB inventory/manifest bytes. These
are implementation limits, not measured stage budgets. A bound violation fails
capture; no truncated tree is returned as complete. Copying/hashing streams in
64 KiB chunks. Files are checked before/after reading for observable changes;
this is not a substitute for the caller's exclusive checkout or SCM verification.

## Objects, publication and exact digests

The store creates a fresh random UUID directory with exclusive `mkdir`. The
directory name is never caller selected. Existing objects are never overwritten,
repaired, replaced or reused. This first backend has no deletion operation;
failed partial objects remain explicitly unsealed for a later controlled orphan
cleanup protocol. A future retirement adapter must retain the object directory
as a permanent non-reuse tombstone while retiring only its source payload.

Object layout is `UUID/source/...`, `UUID/manifest.json` and `UUID/SEALED`.
Private construction precedes publication. Source files are copied with
exclusive creation, flushed/fsynced and made read-only; source directories are
fsynced and made non-writable. The exact manifest is persisted before a seal
marker binding its digest. The object and store directories are fsynced before
the receipt is returned. A marker alone is not a DB seal or lease.

Before manifest/marker publication, independently re-read the stored source and
compare its complete tree digest, inventory bytes and counts with the copied
input. Hashing bytes supplied to `write` alone does not verify the retained
destination. A failed final directory flush can leave a marker but returns no
receipt; neither orphan discovery nor that marker establishes a DB commit.
Manifest and marker bytes are also read back with bounded no-follow reads and
compared with the expected buffers before a receipt is returned.

The source tree hash is exactly the existing
`sha256-length-prefixed-path-and-content-v1`: sorted POSIX relative file paths,
each UTF-8 path length and content length framed with unsigned 64-bit big-endian
integers, followed by the corresponding bytes. There is **no ASCII domain
prefix** in this hash. File permissions, timestamps, empty directories and
operational UUIDs are not source-tree content.

Inventory bytes match the occurrence store's versioned envelope:

```json
{"files":[{"path":"example.py","sha256":"<64 lowercase hex>","size":123}],"schema":"scanipy-execution/source-inventory/1"}
```

Encode compact sorted-key UTF-8 JSON with `ensure_ascii=False`. Files are sorted
by their Unicode-scalar relative path; no duplicate paths. Its digest is SHA256
of `scanipy-execution/source-inventory/1`, LF and the exact bytes. The manifest
separately binds scope (org/codebase/request UUIDs), nonzero lowercase Git SHA-1
commit, tree algorithm/digest, inventory, object UUID and custody-profile version.
Manifest integrity uses its own named domain plus LF, never a canonical graph
or signature claim. SHA strings in these envelopes are 64 lowercase hex;
internal digest values are 32 bytes. Raw file bytes may contain arbitrary binary
content, including NUL. Filename restrictions do not change file contents.

## Receipt verification and immutability limits

A frozen receipt contains actual generated object identity, source metadata,
exact inventory bytes/digest and manifest digest. `verify` requires this expected
receipt from the trusted caller/store, verifies manifest and seal bytes and
recomputes the actual retained tree/inventory under the same bounds. It rejects
extra/missing/changed files or unsafe entries. A directory name or a manifest
that validates against its own newly calculated digest is insufficient.

Read-only modes prevent ordinary accidental writes, not the owner or a host
administrator changing permissions. Actual consumers need read-only Docker
mounts plus the DB's active capture lease and immutable seal; only the capture
service may hold a writable store mount. No claim of enforced immutability
against an equally privileged process is made. Verification and later tool
opening still require that trusted launcher/mount boundary.

This implementation supplies no generic path-to-delete API and performs no
retirement. DB cleanup-token validation, irreversible retirement, permanent path
non-reuse and safe exact-object deletion require a separate reviewed integration.
Never delete an object merely because a lease timestamp appears expired.

## Required tests and remaining actions

- [x] Independent exact framing for binary, Unicode, multiple-file and empty
  trees; inventory bytes agree with the store contract and existing corpus hash.
- [x] Refuse symlinked components/entries, hard links, special files, unsafe
  names, overlapping roots, unsuitable ownership/modes and all declared bounds.
- [x] Inject mid-copy/storage failure: no returned complete receipt or partial
  completion; never overwrite an existing object; failed bytes remain diagnosable.
- [x] Verify tamper detection for manifest, marker and source file additions,
  removals or changes; no arbitrary subprocess/tool invocation.
- [x] Distinct requests/attempts get distinct objects even for identical source;
  immutable source bytes and generated evidence agree after a fresh store open.
- [ ] All dedicated tests are selected by actual CI/pre-push markers; independent
  security review and successful exact-head canonical review precede merge.
- [ ] Implement trusted SCM acquisition/commit verification, atomic DB seal and
  initial lease, restart/idempotency/orphan policy and token-fenced retirement.
- [ ] Wire real detector/analysis workers to the same capture using read-only
  mounts; retain source across identity failure and test restart/race behavior.
- [ ] Measure resource/retention policy on actual stage hardware; this backend's
  controlled tests are not offline rehearsal, G1/G2, or a submitted claim PASS.

## Local review and verification record

The independent corpus/tooling agent performed a Security Analyst-style review
on 2026-09-25 and approved the scoped code after requiring destination, manifest
and seal readback. Root added corrupt-write, short-write and publication-flush
falsifiers; these controls are present in the reviewed implementation. This is
not the required canonical PR verdict and does not authorize a merge.

At this checkpoint, 64 dedicated unit tests passed; actual CI/pre-push marker
selection includes all 64. The full normal repository test selection passed
1,313 tests with 51 existing skips in 146.635 seconds, with live DB/AWS opt-ins
unset. Scoped Ruff and strict mypy passed. JUnit records on the reference host:
`/tmp/scanipy-source-custody-392-unit.xml` and
`/tmp/scanipy-source-custody-392-full.xml`. These temporary records must be
supplemented by final-head CI before merge, not treated as portable stage proof.

Initial source fixtures inherited the host's group-writable umask and correctly
failed custody checks; only fixture modes were corrected. An initial broad test
command accidentally cleared pytest's configured corpus exclusion and stopped
with two duplicate-module collection errors before running tests. The corrected
full command preserved the normal configuration/exclusion and passed as above.
No corpus build/native frontend, scanned source or user database was executed.
