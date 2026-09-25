# R19-A real raw-export evidence

Issue #376 / umbrella #362. These are real static-parser observations, not
solver witnesses, verified overload bindings, purity proofs or full R19/demo
acceptance. Source fixtures are never imported, compiled, tested or executed.
Only the pinned trusted static frontend and exporter process the source bytes.

## Retained artifacts

- `java/Flow.java` and `python/flow.py`: exact immutable inputs.
- `exports/{java,python}.json`: exact producer output bytes, including native
  property types, explicit missing properties and directed parallel edges.
- `schema-catalog.json`: actual pinned GraphSchema catalog (43 node kinds,
  34 edge kinds). `tests/probes/joern_schema_catalog.sc` is the exact probe used;
  schema container command/result are retained under `evidence/schema/`.
- `evidence/{java,python}/`: exact parse/export events, stdout/stderr, Docker
  inspection and container logs. Both phases returned zero and strict validation
  succeeded. Java parse/export took 11.65/25.65 seconds; Python 10.74/27.87 seconds.
- `evidence/negative/`: actual wrong-language, existing-output and symlink-source
  failures. Each real exporter process returned nonzero; the trusted driver
  verified the expected failure boundary and itself exited zero. Wrong language
  has a failed null-array envelope; invalid source provenance has no envelope;
  existing output's original bytes were unchanged.
  The three negative stderr streams use explicit `.stderr.json` base64 wrappers
  to preserve their original trailing blank lines without text-hook mutation.
  Each wrapper records the original byte length and SHA256; the inventory records
  the separate stored-wrapper SHA256. The verifier decodes base64 strictly and
  checks both identities. Original raw stderr files remain in the local task
  evidence directory; no lossy decoding or transformed-as-original claim is used.
- `evidence-manifest.json`: SHA256 inventory of the exact checked-in observations,
  input/probe/export scripts, and explicit local-only binary CPG locations/hashes.
  It is an evidence inventory, not an independent signature/attestation.

The additional exact-value secret-baseline entries are individually reviewed
false positives: SHA256 content/evidence digests, Docker-local object identifiers
and metadata paths, and the base64 encoding of three inspected Java exception
streams from these synthetic inputs. No detector or directory is excluded;
unknown values will still be scanned. Existing baseline records are preserved.

The two binary CPGs remain in the task-owned local evidence directory identified
in the manifest; they are not in Git. Their hashes were rechecked after all
negative probes and still match both producer records. Initial development
diagnostics are separate and are not substituted for these fresh successful
runs. All four temporary containers (schema, Java, Python, negative) were removed
after inspection/log retention; the application/DB containers were untouched.

## Reproduction contract

Use the exact locally available Docker image ID in the manifest:
`sha256:911e6f836fcf5e183a0c559e04e1868ba9d1838c35263728fe85dc1e9cce987b`.
Do not silently resolve a mutable image tag or substitute a host Java toolchain.
Inspect the chosen container/image outside the sandbox and pass the observed ID
as `SCANIPY_PROBE_IMAGE_ID`. Its selected tool JAR hashes and manifest versions
are measured again by the exporter. Image ID is explicitly caller-observed.

Create a new task-owned job directory (for example with `mktemp -d`), writable
by UID/GID 1000. Bind this repository at `/repo` read-only and the job directory
at `/job` read/write. Use the exact safety configuration retained in the container
inspections: read-only root, network none, non-root 1000:1000, 4 GiB memory and
equal swap limit, 2 CPUs, 256 PIDs, all capabilities dropped, no-new-privileges,
and 256 MiB no-suid/no-dev `/tmp`. The producer invocations additionally have
120-second per-process timeouts and a 1,536 MiB JVM heap cap.

Run these trusted commands sequentially in separate disposable containers using
that configuration, working directory `/job`, `PYTHONPATH=/repo`,
`PYTHONDONTWRITEBYTECODE=1` and `PYTHONUNBUFFERED=1`:

```text
/usr/bin/timeout 250 python /repo/tests/probes/joern_raw_v2.py python
/usr/bin/timeout 250 python /repo/tests/probes/joern_raw_v2.py java
/usr/bin/timeout 400 python /repo/tests/probes/joern_raw_v2_negative.py
```

Each driver refuses reuse of its output directory. Preserve Docker inspect/logs
before removing only the explicitly identified temporary containers. Retain
original exports and process events; do not replace process failure with an old
output file or edit results to obtain a passing schema validation. Fixture file
digests bind exact bytes, so source/probe/exporter edits require fresh evidence.
Raw IDs and overlays are observations; byte-for-byte cross-run graph stability
is not claimed by R19-A. A new tool/runtime version requires explicit schema and
producer-contract validation, not a pin-string edit.

## Required limitations / next work

Tests deliberately retain Java unresolved String types, colliding overloaded
method signatures, an incorrect single overload candidate, a varargs external
placeholder, missing stored IS_VARIADIC and source-static/dynamic-dispatch
disagreement. Python tests retain unknown external dispatch, receiver-expression
versus bound-object differences, named/default/star actuals, a BLOCK return and
distinct parallel REACHING_DEF VARIABLE values.

R19-B must specify a real Java toolchain/classpath and richer versioned graph;
R19-C must establish correct language-specific bindings and completeness;
R19-D must implement access-path flow and matched call/return summaries. R02/R06
still need actual binding/type/effect/purity certification for positive and
negative extraction cases. All five derived capability statuses are therefore
`unsupported`, even when raw role edges are present. The existing production
v1 exporter, mapper, solver and canonical encoder are unchanged.
