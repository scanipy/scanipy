# R05 bounded frontend readiness diagnostic — 2026-09-25

One real Python fixture parse/export/map **succeeded** in 38.785 seconds under
the explicit container limits and environment recorded below. This is partial
R05 readiness evidence, not corrected-corpus G0, a refactor comparison, detector
acceptance, a stage-hardware benchmark, or completion of C18.

## Observation

| Item | Observed value |
|---|---|
| Input | Existing `seed-002/before/order_service.py`; 315 bytes; parsed as data, not imported as a Python module |
| Runtime | Python 3.11.15; PyYAML 6.0.3; production frontend/mapper/oracle-fingerprint module imports succeeded |
| Execution | Exactly one `parse_source` call; one Joern parse subprocess and one export subprocess; fresh isolated workdir; no cache reuse |
| Mapping | 222 nodes, 500 edges: AST 195, CFG 77, PDG 228; 222 location records, 153 with positive line numbers |
| Agreement | Production `map_export` result equals production `map_export_with_locations` graph |
| Result | Probe exit 0; container exit 0; `OOMKilled=false`; no retry |
| Time | Probe elapsed 38.785 seconds; container UTC start `08:20:53.643047811`, finish `08:21:33.181143208` |
| Isolation | 4 GiB RAM/no container swap, 2 CPUs, 256 PIDs, non-root UID/GID 1000, network disabled, read-only root/repository, no capabilities, no-new-privileges |

The image's export-script content matched the worktree's script byte-for-byte.
The probe imported the actual worktree modules mounted read-only and did not
replace `parse_source`, `map_export`, `map_export_with_locations`, or
`secure_run`. The audit hook only recorded actual subprocess creation events.

## Reproduction identity and artifacts

See [commands.md](commands.md) for the exact allocation, container, environment,
and cleanup commands; [manifest.yaml](manifest.yaml) for input/code/image/output
identities; and [the executed probe text](raw/executed-probe.py.txt) for the
byte-preserved evidence-local driver. Its run-time path was `probe.py`; after
execution it was archived as text, not installed as maintained application
code. The original run commands remain unchanged in the command record.

- [Raw diagnostic report](raw/diagnostic.json): preflight, real invocation argv,
  timestamps, graph observations, and output hashes.
- [Container output](raw/container.log): probe output and invocation events.
- [Final container inspection](raw/container-inspect.json): actual limits,
  mounts, image ID, exit state, and configuration.
- [Raw Joern export](raw/cpg_export.json) and [CPG binary](raw/cpg.bin): preserved
  parser/export artifacts from the single fixture.

All five generated raw files were copied without modification and compared
byte-for-byte with their temporary originals. The executed probe was also
archived without changing its bytes. Their SHA-256 values are in `manifest.yaml`.
Static inspection of the text artifacts found the known synthetic fixture and
tool/container metadata, including a public Python release-signing-key
fingerprint, not a private key or application credential. This is not a full
repository/history security audit. The binary is retained as the parser output
of this scoped synthetic fixture, not executed.

## Scope and remaining work

- This machine is a **reference host**, not confirmed presentation hardware.
  Preflight found 8,984 MiB available memory and 114 GiB disk free. No measured
  peak-memory claim is made; the configured cap is not peak usage.
- The command pins an existing local image ID. It does not demonstrate a clean
  build/install, verify the image's release signature, identify its original
  build recipe, or fix the missing dependencies in other images.
- The explicit child PATH includes `/opt/joern` and `/opt/joern/bin`. Production
  `secure_run` already uses fixed absolute launcher paths; this diagnostic must
  not be cited as proof that default PATH omission prevents its launch. Default
  packaging and default environment behavior were not tested here.
- The test covers one Python before-fixture only. It does not validate Java,
  after-fixtures, transformation semantics, full corpus inventory, CALL-edge
  fidelity, finding detection/removal, fingerprint canonicality, strong/weak
  behavior, or byte-identical independent reruns.
- There was no accepted-spec execution, `S_version`, emitted finding,
  provenance signature, or production `env_digest` claim. No LLM was involved
  in the invoked analysis path. This is not R16's no-execution security campaign.
- Successful Joern child stdout/stderr is captured then discarded by the
  existing production wrapper; the bundle preserves the probe/container output
  and generated artifacts, not an invented transcript of those child streams.

The one diagnostic container was removed **after** it exited normally and its
inspection/logs were archived. No existing container was stopped or modified;
`scanipy-app` and `scanipy-db` remained healthy. Temporary artifacts remain at
`/tmp/scanipy-r05-readiness-20260925-Z4ppNJvT` as an additional recoverable copy.
No process from this diagnostic remains running.
