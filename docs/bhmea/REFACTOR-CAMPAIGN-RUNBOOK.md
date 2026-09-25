# R05 fresh real-Joern campaign producer

Status: implementation and controlled validation; **no new real campaign, corrected G0,
feature acceptance, or full R05 completion is claimed by this document**. Issue #374
tracks this work. The full submission/review remains the target. December 2/3 is the
presentation context; there is no October 23 deadline. The owner confirmed this
development machine as the presentation machine. That designation is not a
latency, resource-headroom, offline-readiness or runtime-isolation acceptance.
Every launch still needs fresh resource and independently bound host evidence.
The [retained stage-machine observation](../evidence/2026-09-25-stage-machine/README.md)
records the owner's designation and the limitations of the observed capacity.

## Contract and scope

`scripts/run_refactor_campaign_container.py` is the current diagnostic controller
and `scripts/run_refactor_campaign.py` is the in-container producer. The legacy
`scripts/validate_refactor_fingerprints.py` remains unchanged by this work.
The diagnostic controller's subprocess capture and requested container flags do
not supply the separately required #400 bounded transport, effective runtime
checks, trusted installation or lifecycle/cleanup proof. No native campaign is
authorized by this source checkpoint or the command examples below.

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
- [x] Canonical API #369 (`bcce692`), typed report gate #375 (`cd62f5f`),
  independent artifact metadata #371 (`c540644`), snapshot hash-lock correction
  #383 (`85a9600`), and fail-closed developer hooks #387 (`0223651`) are merged.
  Those scoped merges do not establish a runnable image or feature acceptance.
- [x] Java static safety #390 merged at
  `8d38c06addc49f382b36d17fee4125fdf4628b3d` from exact tested head
  `16252b21db172b967f13a815ca9bd8fe3078dd19`, after all required checks and a
  successful canonical APPROVE action. The earlier failed session-limit action
  remains historical evidence, not approval. This branch now incorporates
  reviewed main `69f7f480e2bb04febec103b04d2b753924d3090a`, including the later
  reviewed documentation reconciliation #401.
- [ ] Complete this producer's combined checks, exact-head CI and successful
  canonical review, then its reviewed merge before collecting protected G0.
  Local dependency merges and controlled tests do not authorize a real run.
- [ ] Integrate the reviewed bounded controller/runtime enforcement under #400
  and obtain explicit readiness/resource approval before any native campaign.
  A successful preview or a supplied `--execute` flag is not that approval.
- [ ] Use a clean committed analysis checkout containing those changes. The
  controller refuses dirty tracked or untracked files. It records Git revision and
  hashes all tracked `analysis/`, `tools/`, and `scripts/` files, including the
  required Java safety module; the container verifies those mounted bytes before
  any case runs. Do not edit the checkout
  during execution or run a hook that temporarily stashes its source changes.
- [ ] Start the host controller with `-B` and `-X pycache_prefix=<private empty path>`
  as shown below. `-B` alone can still read an old ignored `.pyc`; the fresh prefix
  prevents reuse of source-adjacent caches. The controller enforces these flags,
  and the container has its own empty private prefix plus no-bytecode-write.
- [ ] Select a locally present, reviewed worker image by exact
  `sha256:<64 lowercase hex>` image ID, never a tag. It must contain Python >=3.11,
  PyYAML, cryptography, the pinned Joern launchers, Java, and export script. No
  runtime install, image pull, or image build is performed by the controller.
- [ ] Verify/rebuild the worker dependency set through reviewed work using the
  committed exact snapshot input/generator/hash-lock validator from #383. No ad hoc
  package overlay establishes readiness. The earlier
  diagnostic image `sha256:911e6f836fcf5e183a0c559e04e1868ba9d1838c35263728fe85dc1e9cce987b`
  had Python 3.11.15 and PyYAML but lacked cryptography. Its earlier successful
  single parse is not proof that this producer's full runtime is ready.
- [ ] Confirm available resources immediately before launch: at least two CPUs,
  6 GiB available memory and 20 GiB free disk. The controller refuses otherwise.
  Compare the actual launch host with the separately retained owner-confirmed
  presentation-machine evidence; this resource sample alone does not identify it.
- [ ] Review and run bounded Python **and** Java cases first on the selected image.
  Inspect actual launcher events, exported graph capabilities, unique locators and
  returned identity namespaces. A syntax pass does not substitute for this step.

The controller creates exactly one new explicitly named/labeled container, pinned
to the selected image ID, with network disabled, read-only analysis/source mount
and root filesystem, non-root user, no capabilities, no-new-privileges, two CPUs,
4 GiB memory with no additional swap, 256 PIDs and private writable run directories.
Fresh controller data, evidence and case-side work directories are explicitly
mode 0700; a permissive caller umask cannot make a Java workdir group-writable.
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

Only after the prerequisites and separate native-run approval, the intended
interface repeats that command with `--execute` for a bounded two-side attempt.
For Java use a new output path/name and
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

Add `--execute` only after the required controller/readiness approval as well as
reviewing that preview and fresh resource check. Default
fingerprint budgets are `--states 65536 --seconds 0.2`; actual values are retained
in runtime evidence. Changing a budget must be deliberate and included in the
eventual full environment manifest. A prior single Python parse/export took about
39 seconds; this is not a reliable full-campaign estimate, and 844 fresh attempts
can take hours. Do not launch a second campaign because an observation call times
out. Track the emitted live container ID.

The production launcher's **pre-adapter input** is explicit:

```text
PATH=/opt/joern:/opt/joern/bin:/opt/codeql:/opt/temurin-jre/bin:/usr/bin:/bin
JAVA_HOME=/opt/temurin-jre
HOME=<fresh case-side work directory>
LC_ALL=C.UTF-8
```

`secure_run` still resolves absolute `/opt/joern/joern-parse` and
`/opt/joern/joern` and enforces its reviewed value-aware allowlists. PATH supports
launcher children; this override is not a claim that default image packaging was fixed.
Parse/export timeout ceilings remain the production 600/300 seconds.

Java uses the shared [closed static profile](JAVA-STATIC-INVOCATION.md) for BOTH
parser and fixed-v1 exporter: exact `--frontend-args --delombok-mode no-delombok`,
`JAVASRC_FETCH_DEPENDENCIES=no-fetch`, private mode-0700 HOME/TMPDIR and fixed
locale/tool paths. The adapter validates and transforms the input above; it does
not inherit arbitrary environment variables. Each Java process event retains the
validated **post-adapter** mapping supplied to `secure_run`, including its profile,
phase and observed directory modes. This observation is not proof the child
started, used a particular JVM/classpath, or satisfied full environment provenance.
Unknown launch still has unknown actual argv/return code. Unprofiled calls do not
record arbitrary environment values.

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

Runtime `joern_environment_input` and each attempt's `frontend_environment_input`
are labeled pre-adapter inputs. Only an event's `environment_observation` records
the validated closed Java child mapping; the producer does not copy input fields
into an invented effective observation.

The observer preserves actual subprocess argv from `CompletedProcess` or
subprocess exceptions, cwd, timeouts, start/end times, elapsed time, exit status
and byte-exact stdout/stderr. If launch failed before subprocess supplied argv,
actual argv is null and requested arguments are separately labeled. It never
logs an arbitrary inherited worker environment. Partial/malformed export bytes
are retained even when export or mapping fails. Missing graph capabilities and parser recovery
are not manufactured into detector findings, semantic proofs or expected failures.
Report v2 has no export/map error enum: those failures remain visible in the side's
failed status, reason and concrete raw error artifact, with normalized error null.
They are never relabeled as the intentional parse-failure control's required error.

Required evidence-write/serialization and existing-output read/stat failures are
fatal infrastructure errors, not ordinary side-analysis failures. Missing outputs
are explicitly distinguished from unreadable or non-regular outputs. This includes an evidence error retained as
the explicit cause of an original subprocess exception: both errors survive and
the campaign aborts without a final report/gate result. A simultaneous observer
failure and raw-output retention failure are both preserved under the original
child exception, including through the CLI failure boundary. A later successful
write must not hide earlier missing stdout/stderr/metadata. Existing partial artifacts
and checkpoints remain diagnostic only. The independent after-side attempt rule
applies to analysis failures, not permission to continue after evidence loss.

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
5. Bind the actual launch host to the owner-confirmed presentation-machine
   evidence, then measure runtime/disk budgets, operator walkthrough and demo
   fallback independently. Historical and controlled artifacts remain separately
   labeled; they never become a new real G0 through rewriting.

Controlled tests: `tests/unit/test_refactor_campaign_producer.py` is unit-marked for
the actual CI selector and exercises exact
inventory, all 844 attempts, independent after-side attempts, locator negatives,
raw-output preservation, missing proof semantics, source drift rejection,
no-overwrite behavior, container isolation command construction, shared Java
both-phase profile serialization/privacy, required safety-module binding and
fatal direct/chained evidence loss. These tests
validate orchestration, not real Joern accuracy, parser coverage or invariance.

## Local reviewed-main integration record

Normal local integration checkpoint `cf19d22` incorporated reviewed main
`e79dc54`; the later documentation merge incorporates reviewed main
`69f7f480e2bb04febec103b04d2b753924d3090a`. Incoming raw-v2 evidence, continuity
and stage-machine records remain intact. Against checkpoint `11dba03`, producer
and shared observer behavior are unchanged. The only controller change is the
host-role description; a hermetic resource test checks that it does not assert
that an arbitrary launch host is the designated presentation machine.

An initial focused command named a nonexistent report-gate test file, exiting
4 with no tests run. After discovering the actual filename, the four-module
producer/Java-profile/observer/report-gate selection passed 223 tests without
skips in 96.90 seconds (`/tmp/scanipy-r05-main-refresh-focused.xml`). The new
host-role regression separately passed one test, 53 deselected, in 0.39 seconds
(`/tmp/scanipy-r05-host-role.xml`). The correction did not change a product
fence or test expectation. An independent read-only delta review found no
scoped blocker; it performed no tests or native probes.

The configured full suite on the reviewed-main integration passed **1,613 tests
with 51 existing skips and zero failures/errors**, 1,664 total, in 235.90 seconds
(`/tmp/scanipy-r05-reviewed-main-full.xml`). Repository Ruff/format passed
(214 files); broader strict mypy, including both producer scripts and `tools`,
passed all 98 selected source files. Root requested the next normal pre-push
wait for the separately reviewed #395 main integration; no manual pre-push or
new remote candidate is claimed for this checkpoint. These local paths are
diagnostic records, not immutable G0/feature-acceptance artifacts or execution
authorization. Exact-head remote gates remain pending.
