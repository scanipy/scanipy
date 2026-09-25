# R05 fresh real-Joern campaign producer

Status: implementation and controlled validation; **no new real campaign, corrected G0,
feature acceptance, or full R05 completion is claimed by this document**. Issue #374
tracks this work. The full submission/review remains the target. December 2/3 is the
presentation context; there is no October 23 deadline. The current machine is a
reference host, not confirmed presentation hardware.

## Contract and scope

Use `scripts/run_refactor_campaign_container.py` as the local controller and
`scripts/run_refactor_campaign.py` as the in-container producer. The legacy
`scripts/validate_refactor_fingerprints.py` remains unchanged by this work.

The authoritative machine contract is [report v2](REFACTOR-REPORT-V2.md) and its
repository-owned gate policy. The producer calls actual production `parse_source`,
`map_export_with_locations`, and `compute_slice_fingerprint_v2`. It never imports
Python from a corpus or evidence directory, and never executes a scanned program.
Joern is a parser/export tool; its trusted in-image export script is executable
analysis tooling, not target program code.

The frozen corpus contains exactly 422 cases: 270 structural stays, 100 structural
flips, 50 finding removals, and two intentional analysis failures. A full uncached
run makes **844 independent case-side parse/export/map attempts**, even when source
directories repeat (468 distinct directories). After is attempted even if before
fails. There is no hidden source-directory cache, retry, or resume shortcut.

## Preconditions: must be satisfied before a real run

- [x] Runtime dependency repair #373 merged at `89ed803`; corrected corpus #372
  merged at `c3444e7`. These are scoped prerequisites, not full R03/R05/G0 acceptance.
- [ ] Confirm reviewed merges of the canonical API (#369), typed report gate
  (#375), and this producer before collecting a protected full G0. Local dependency
  merges are development only, even when controlled tests pass.
- [ ] Use a clean committed analysis checkout containing those changes. The
  controller refuses dirty tracked or untracked files. It records Git revision and
  hashes all tracked `analysis/`, `tools/`, and `scripts/` files; the container
  verifies those mounted bytes before any case runs. Do not edit the checkout
  during execution or run a hook that temporarily stashes its source changes.
- [ ] Start the host controller with `-B` and `-X pycache_prefix=<private empty path>`
  as shown below. `-B` alone can still read an old ignored `.pyc`; the fresh prefix
  prevents reuse of source-adjacent caches. The controller enforces these flags,
  and the container has its own empty private prefix plus no-bytecode-write.
- [ ] Select a locally present, reviewed worker image by exact
  `sha256:<64 lowercase hex>` image ID, never a tag. It must contain Python >=3.11,
  PyYAML, cryptography, the pinned Joern launchers, Java, and export script. No
  runtime install, image pull, or image build is performed by the controller.
- [ ] Verify/rebuild the worker dependency set through reviewed work. The earlier
  diagnostic image `sha256:911e6f836fcf5e183a0c559e04e1868ba9d1838c35263728fe85dc1e9cce987b`
  had Python 3.11.15 and PyYAML but lacked cryptography. Its earlier successful
  single parse is not proof that this producer's full runtime is ready.
- [ ] Confirm available resources immediately before launch: at least two CPUs,
  6 GiB available memory and 20 GiB free disk. The controller refuses otherwise.
  Obtain the actual presentation hardware specification separately.
- [ ] Review and run bounded Python **and** Java cases first on the selected image.
  Inspect actual launcher events, exported graph capabilities, unique locators and
  returned identity namespaces. A syntax pass does not substitute for this step.

The controller creates exactly one new explicitly named/labeled container, pinned
to the selected image ID, with network disabled, read-only analysis/source mount
and root filesystem, non-root user, no capabilities, no-new-privileges, two CPUs,
4 GiB memory with no additional swap, 256 PIDs and private writable run directories.
It does not mount the Docker socket or modify existing application/database
containers. Its 24-hour maximum watchdog and 5 GiB disk reserve only stop the exact
owned container ID after checking its label; neither condition starts another run.

## Commands

Run from the clean reviewed repository with its supported Python environment.
Set `CAMPAIGN_IMAGE_ID` to the locally inspected reviewed worker image ID; this is
an operator decision, not a value copied from a candidate report. Choose a unique
container name. The controller without `--execute` performs read-only readiness
checks and prints the exact proposed command; it creates no container or output.

```sh
CAMPAIGN_PARENT=$(mktemp -d /tmp/scanipy-refactor-campaign-XXXXXXXX)
python -B -X pycache_prefix="$CAMPAIGN_PARENT/host-bytecode" \
  -m scripts.run_refactor_campaign_container \
  --output "$CAMPAIGN_PARENT/python-check" \
  --image-id "$CAMPAIGN_IMAGE_ID" \
  --name scanipy-refactor-campaign-python-check-001 \
  --case-id control/python-injection-inline-method \
  --maximum-seconds 1200
```

After checking the printed context, repeat that exact command with `--execute` to
authorize the bounded two-side attempt. For Java use a new output path/name and
`--case-id control/java-injection-inline-method`. A bounded diagnostic still emits
all 422 case identities: every omitted case stays `not_run`, so G0 remains false.
Do not relabel it a full campaign.

Once the preconditions above are satisfied, preview a full run with no `--case-id`:

```sh
python -B -X pycache_prefix="$CAMPAIGN_PARENT/host-bytecode" \
  -m scripts.run_refactor_campaign_container \
  --output "$CAMPAIGN_PARENT/full-run" \
  --image-id "$CAMPAIGN_IMAGE_ID" \
  --name scanipy-refactor-campaign-full-run-001 \
  --maximum-seconds 86400
```

Add `--execute` only after reviewing that preview and resource check. Default
fingerprint budgets are `--states 65536 --seconds 0.2`; actual values are retained
in runtime evidence. Changing a budget must be deliberate and included in the
eventual full environment manifest. A prior single Python parse/export took about
39 seconds; this is not a reliable full-campaign estimate, and 844 fresh attempts
can take hours. Do not launch a second campaign because an observation call times
out. Track the emitted live container ID.

The production launcher override is explicit:

```text
PATH=/opt/joern:/opt/joern/bin:/opt/codeql:/opt/temurin-jre/bin:/usr/bin:/bin
JAVA_HOME=/opt/temurin-jre
HOME=<fresh case-side work directory>
LC_ALL=C.UTF-8
```

`secure_run` still resolves absolute `/opt/joern/joern-parse` and
`/opt/joern/joern` and enforces its original allowlists. PATH supports launcher
children; this override is not a claim that default image packaging was fixed.
Parse/export timeout ceilings remain the production 600/300 seconds.

## Evidence and failure handling

The new output directory contains controller commands and byte-exact output,
local image identity, clean analysis revision/content hashes, initial existing
container list, the created container ID, resource observations and final state.
`data/evidence/` contains manifest/lock/policy copies, runtime observation, immutable
per-case-side artifacts, numbered report checkpoints, final `report.json` and
`gates.json` with the independent baseline check; acceptance/non-regression remain
explicitly not run until their protected history and proof inputs are supplied.
Original `cpg.bin` files remain under `data/work/`, with their
paths, sizes and hashes referenced in evidence. Preserve both directories when
archiving a complete run; do not move only report.json. The container receives a
read-only context-file mount and can write only under `data/`; it cannot overwrite
the host controller's initial commands, context, or ownership records.

The observer preserves actual subprocess argv from `CompletedProcess` or
subprocess exceptions, cwd, timeouts, start/end times, elapsed time, exit status
and byte-exact stdout/stderr. If launch failed before subprocess supplied argv,
actual argv is null and requested arguments are separately labeled. It never
logs the inherited worker environment. Partial/malformed export bytes are retained
even when export or mapping fails. Missing graph capabilities and parser recovery
are not manufactured into detector findings, semantic proofs or expected failures.
Report v2 has no export/map error enum: those failures remain visible in the side's
failed status, reason and concrete raw error artifact, with normalized error null.
They are never relabeled as the intentional parse-failure control's required error.

Source-derived locator text, callee token/column and a unique raw CALL must bind to
one mapped CALL at the correct relative file/line/FQN/Joern column. Ambiguity,
missing calls, wrong text, operators and outside-file matches fail explicitly.
The source callee column and Joern expression column are distinct observations.
Returned fingerprint class and identity namespace are recorded verbatim alongside
budget and conditional-canonicality telemetry; source-aware weak hashes are not
promoted to strong refactor evidence.

No detector is run here: finding and scan records stay `not_run`; lifecycle stays
null. A removed sink is not an inferred absent finding and has no invented after
hash. Intentional malformed source is only an expected negative: if Joern recovers
and returns a graph, the report records that outcome instead of inventing failure.
All semantic preconditions, including purity, remain `not_run` until independent
real producers exist. The partial runtime observation is not the full environment
manifest: `environment_digest` and `environment_manifest` remain null. Therefore
feature acceptance remains false even if some structural hashes compare as expected.

The controller removes only its own stopped container after retaining final state
and logs; all disk evidence remains. On an unexpected interruption/failure, inspect
`container-id.json` and the recorded live ID before further action. Never restart
on a monitoring timeout, stop a container by guessed name, remove application/DB
containers, or delete a broad workspace/temp root. Cleanup of retained run data is
a separate explicit decision after archival.

## Independent gate verification

Take `ANALYSIS_REVISION` from the reviewed clean analysis checkout/controller
context independently of the report. The checker must not accept a candidate's
self-reported revision as its expected release revision.

```sh
ANALYSIS_REVISION=$(git rev-parse HEAD)
python scripts/check_refactor_report.py \
  --report "$CAMPAIGN_PARENT/full-run/data/evidence/report.json" \
  --corpus-root tests/corpora/refactor --mode baseline \
  --expected-revision "$ANALYSIS_REVISION"
```

Use the same explicit revision for `--mode acceptance` and `--mode nonregression`;
the latter also requires the protected baseline and accepted improvement reports
configured in the reviewed policy. Do not rewrite `history` to erase prior passes,
change accepted namespaces to discard a prior success, narrow case inventory, or
trust report totals. Policy digest excludes only the history registry; all other
policy semantics are bound. Exit 0 means the selected gate passed, 1 a valid red
report, and 2 invalid/missing evidence. Producer/controller exit 0 only means the
measurement process completed; it is not a feature acceptance assertion.

## Remaining TODOs and acceptance boundaries

1. Complete reviewed image/dependency readiness, bounded real Java/Python checks,
   then one full 844-attempt fresh run. Preserve actual incomplete cases.
2. Review the resulting full G0 through the independent gate and evidence policy;
   register its immutable hash only after approval, not because the command exited 0.
3. Implement/validate the full analysis-environment manifest, semantic purity and
   transformation certificates, graph capabilities, actual detector coverage and
   R07 lifecycle producers. Do not populate those fields from expected metadata.
4. Fix observed graph/fingerprint failures without denominator or expectation
   changes that merely conceal failures; run non-regression against protected
   prior successes as well as final all-feature acceptance.
5. Establish stage hardware, runtime/disk budget, operator walkthrough and demo
   fallback independently. Historical and controlled artifacts remain separately
   labeled; they never become a new real G0 through rewriting.

Controlled tests: `tests/unit/test_refactor_campaign_producer.py` exercises exact
inventory, all 844 attempts, independent after-side attempts, locator negatives,
raw-output preservation, missing proof semantics, source drift rejection,
no-overwrite behavior and container isolation command construction. These tests
validate orchestration, not real Joern accuracy, parser coverage or invariance.
