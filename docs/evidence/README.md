# Evidence storage and acceptance conventions

This directory separates preserved observations from authored interpretation.
Its presence, a successful command exit, or a `strong` label does not establish
an acceptance criterion. Use the claim ledger and gates in
[the Black Hat remediation backlog](../REVIEW-BHMEA-EXECUTION-ACTION-ITEMS-2026-09-23.md).

## Current inventory

| Bundle | Kind | What it establishes |
|---|---|---|
| [2026-08-31 refactor report](historical/2026-08-31/README.md) | Historical recovery on 2026-09-25 | Original report bytes, declared scope, and internally consistent counts; not a new run, corrected G0, or feature acceptance |
| [2026-09-25 frontend readiness](2026-09-25-r05-readiness/README.md) | One bounded real Python parse/export/map | Production frontend and mapper succeeded in an isolated Docker container on reference hardware; not detection, refactor, G0, or stage acceptance |
| [2026-09-25 execution-ledger checks](2026-09-25-execution-ledger/README.md) | Planning-tool tests and retained-artifact hash checks | Ledger inventory/DAG/negative controls; not semantic report or feature acceptance |
| [2026-09-25 presentation machine](2026-09-25-stage-machine/README.md) | Owner confirmation and selected read-only host observations | Actual demo machine identified; transient capacity and resource pressure, not measured budgets or offline stage acceptance |

No corrected-corpus G0 or final full-submission acceptance bundle is recorded
by this inventory. Add future bundles explicitly; do not reuse the historical
directory for new results.

## Raw artifacts versus interpretation

- Store each new execution in a unique run directory. Keep raw tool output,
  source/corpus manifests, logs, and hashes under `raw/`; keep authored
  summaries and gate decisions outside `raw/`.
- Treat raw evidence as immutable by convention. Preserve bytes, including
  formatting and contrary results. SHA-256 manifests detect changes; this
  repository does not provide write-once storage merely by naming a directory
  `raw` or `historical`.
- Corrections belong in a new note or run with an explicit `supersedes` link.
  Never silently repair JSON, regenerate an old summary, replace a failed run,
  or change expected labels inside a historical artifact.
- A human-readable summary emitted by a tool is still preserved output. An
  authored write-up is interpretation, even when archived without modification.
  Label those artifact kinds separately.
- Inspect outputs for secrets and unrelated private source before including
  them. If an artifact requires redaction, keep the original only in an
  approved restricted location and publish a distinctly named derivative with
  its own digest and redaction record. Do not call redacted bytes the original.
- A content digest proves equality to the hashed bytes, not authenticity of
  the execution, soundness of the algorithm, or truth of a report's assertions.

## Required metadata for a new acceptance run

Record these fields in a machine-readable manifest beside the raw artifacts.
Use `null` plus an explanation for unknown historical facts; missing facts do
not become established when written into a recovery note. Placeholder values
must never satisfy an acceptance gate.

| Area | Required evidence |
|---|---|
| Identity | Unique run ID, evidence kind (`real_execution`, `synthetic_diagnostic`, or `historical_recovery`), UTC start/end, success/failure status, responsible role |
| Code/source | Commit, dirty-worktree status, exact relevant code/source-tree content digests and path policy; source commit/tree and snapshot identity for scanned projects |
| Contract | Versions/digests of the gate manifest, supported transformation/purity contract, selected policies, accepted spec set and `S_version`, fingerprint/schema version |
| Corpus | Corpus ID/version/digest, actual source-tree integrity verification, explicit required case IDs, languages/classes, declared topology count and diversity limitations |
| Toolchain | Resolved image digest, frontend/engine/exporter/mapper versions or content digests, pinned dependencies, parse flags, platform/architecture, applicable `env_digest`; record actual values, not only a mutable image tag |
| Invocation | Exact argv, working directory, mounts, output ownership/permissions, relevant non-secret environment, resource/time/work budgets, network mode; secrets must remain references, never plaintext |
| Cache/freshness | Fresh/shared-cache mode, cache key schema and relevant identities, hits/misses/parse counts; separate parse executions for independent reproducibility runs |
| Coverage | Expected and observed case inventory, duplicate/missing cases, per-language and per-evidence-type denominators, skipped/xfail/not-run cases and reasons, relevant fidelity/staging status |
| Observations | Per-case raw outcomes, source/sink correspondence, whole-graph and slice classifications separately where applicable, errors/timeouts, gate output/exit codes and logs |
| Artifact binding | Relative artifact path, kind, byte size, SHA-256, producer, and parent run IDs; source/destination hashes and byte comparison for historical transfers |
| Interpretation | Claim/gate IDs, exact evidence references, limitations, unresolved decisions, and acceptance status distinct from process completion |

Keep `structural_comparison`, `finding_removal`, and `analysis_failure` records
separate. Missing fingerprints do not prove a flip or successful removal.
Removal evidence needs a completed sufficiently scoped scan and lifecycle
confirmation. A deliberately failed analysis can prove error handling, not
refactor stability. Recompute counts from per-case observations rather than
trusting aggregate totals or a report's `matches_expectation` field.

## Promotion and rerun rules

1. Validate schema, content hashes, exact case inventory, and observation
   consistency before accepting a baseline artifact. An honest red baseline can
   be valid evidence without passing a feature gate.
2. Apply the independently pinned semantic gate for feature acceptance. Preserve
   per-case and per-language nonregression requirements and accepted improvements.
3. A historical recovery cannot be promoted to a fresh run, and a hand-built
   graph diagnostic cannot be promoted to a real-source Joern result.
4. Require fresh evidence after relevant code, schema, source, corpus, toolchain,
   configuration, or decision changes. Document which gates are invalidated;
   do not carry forward a green claim merely because its old artifact exists.
5. Keep release and stage readiness distinct from feature fulfillment. Public
   links, image signatures, clean installation, offline rehearsal, and attendee
   instructions each require their own observed evidence and authorization.

These conventions are prerequisite documentation for R17, not a declaration
that R17 or any submitted capability is complete.
