# DOC-CMP-SNAP-05 — Snapshot worker + environment pinning

**Status:** ACTIVE (Phase 0 per-component deliverable)
**Source-of-truth lineage:**

- `SDD.md §4 CMP-SNAP-05` (Purpose, AC-SNAP-05a/b)
- `PLAN.md §"Phase 3 — Snapshotter + CW-DETECT + differential oracle"` — `"Env pinned by image digest"`
- `PLAN.md §"Central correction"` — `env_digest` defines `Env`; INV-2 scoping
- `docs/cross-cutting/DOC-DEPLOY-DECISIONS.md` CLAR-DEPLOY-13 (ECR + Cosign keyless), CLAR-DEPLOY-05 (Secrets Manager env-var injection)
- `docs/cross-cutting/DOC-INV.md §4` — INV-2 owner (this component is the **`env_digest` origin**)
- `docs/cross-cutting/DOC-RUNBOOK.md §2` — Worker lifecycle (build → publish → launch → execute → failure)
- `docs/cross-cutting/DOC-API.md` — HMAC-bearer `report_status` callback
- `.claude/rules/00-global.md`, `.claude/rules/02-provenance.md`

This document is the **implementation contract** for `CMP-SNAP-05`. It is the **`env_digest` origin** for the entire platform: the container image digest of this worker is the authoritative `env_digest` (per `AC-SNAP-05b`).

---

## 1. Component identity

| Field | Value |
|---|---|
| `CMP-ID` | `CMP-SNAP-05` |
| Subsystem | Snapshotter (`SDD.md §4`) |
| Staging | Stage A |
| Depends-On | `CMP-SNAP-01`, `CMP-DEPLOY-02` (`WBS.md §20`) |
| Owner | **DEFERRED** via `CLAR-OWNER-01` |
| INV-* touched | **INV-2 ORIGIN** (the worker image digest defines `env_digest`). Provenance threading: emits `env_digest` into snapshot creation via `CMP-SNAP-01`. |
| Substrate | AWS ECS Fargate (CLAR-DEPLOY-01) · ECR + Cosign keyless (CLAR-DEPLOY-13) · Secrets Manager env-var injection (CLAR-DEPLOY-05) |

---

## 2. Mandate

**Verbatim SDD `Purpose:` (`SDD.md §4 CMP-SNAP-05`):**

> Worker mirroring the existing semgrep worker contract (env-var contract, `report_status`, argument allowlist, secure `subprocess.run`); Dockerfile bundling `joern`, `codeql`, `git` pinned by digest into `Env`.

**Operational role.** `CMP-SNAP-05` is the **execution substrate** of the Snapshotter. It is a containerized ECS Fargate task that consumes `SnapshotJob` SQS messages from `CMP-SNAP-01`, clones source via `CMP-SCM-*`, invokes `CMP-SNAP-03 CW-DETECT` for the precondition verdict, dispatches to `CMP-SNAP-02` for the actual CPG construction (incremental or full reparse), uploads the five artifacts to S3 at the deterministic keys from `DOC-CMP-SNAP-01 §4.2`, and reports back via the HMAC-bearer `report_status` callback. Critically, the **worker container image digest is the `env_digest`**: changing any bundled tool (`joern`, `codeql`, `git`) produces a new image digest and therefore a new `env_digest`, and snapshots produced under different `env_digest`s are scoped to different `Env`s per INV-2. This is the operational substrate that makes the determinism partition's reproducibility theorem (`PLAN.md` property (a)) hold for a fixed `Env`.

---

## 3. Interface contract

`CMP-SNAP-05` has no public HTTP surface. Its interfaces are:

1. **SQS dequeue** of `SnapshotJob` messages (queued by `CMP-SNAP-01`).
2. **HMAC-bearer callback** to `CMP-SNAP-01` `report_status`.
3. **In-process** invocation of `CMP-SNAP-02`, `CMP-SNAP-03`, `CMP-SCM-*`.
4. **`subprocess.run`** invocation of pinned external tools (`joern`, `codeql`, `git`) under an **argument allowlist**.

### 3.1 Env-var contract

Per `CLAR-DEPLOY-05` (RESOLVED) — secrets injected as env vars via the ECS task `secrets` block. The worker reads its configuration **exclusively** from environment variables; no filesystem secrets.

```bash
# Identity + tracing
SCANIPY_WORKER_VERSION=...        # injected at image build; equals image tag
SCANIPY_ENV_DIGEST=sha256:...     # injected from ECS task metadata (the running image's digest)
SCANIPY_JOB_ID=...                # injected per task from the SQS message
SCANIPY_REGION=us-east-1          # CLAR-DEPLOY-08

# Callback
SCANIPY_API_BASE_URL=https://api.scanipy.io
SCANIPY_HMAC_SECRET=...           # via Secrets Manager -> ECS secrets block

# Storage
S3_BUCKET=scanipy-prod-artifacts  # per CLAR-DEPLOY-02 prefix scheme
AWS_REGION=us-east-1

# Observability
OTEL_EXPORTER_OTLP_ENDPOINT=...   # CLAR-DEPLOY-07
OTEL_SERVICE_NAME=scanipy-snapshot-worker

# RLS / tenancy (set per request from SQS message)
SCANIPY_ORG_ID=...                # CLAR-DEPLOY-16 isolation
```

**Forbidden:**

- No file-based config (`config.yaml`, `~/.aws/credentials`, etc.) — Secrets Manager → ECS secrets only (CLAR-DEPLOY-05).
- No long-lived IAM access keys — IRSA / ECS Task Role only.
- No CI secrets in workers — CI uses GitHub OIDC to AWS; workers never see CI tokens.

### 3.2 `report_status` callback

```http
POST /snapshots/{snapshot_id}/status
Authorization: HMAC-SHA256 <signed-bytes>=<base64(hmac)>
Content-Type: application/json

{
  "snapshot_id": "uuid",
  "state": "snapshotting" | "ready" | "failed",
  "precondition_status": "closed-world" | "degraded" | "full-reparse",  // null until 'ready'
  "snapshot_digest": "sha256:...",                                       // null until 'ready'
  "env_digest": "sha256:...",                                            // INV-2; the worker's image digest
  "error": "string" | null
}
```

Authentication: HMAC-SHA256 over the canonical request bytes with `SCANIPY_HMAC_SECRET`. The pattern mirrors the existing semgrep worker contract referenced in `SDD.md §4 CMP-SNAP-05` Purpose.

### 3.3 Argv allowlist (`AC-SNAP-05a`)

Every `subprocess.run` call from the worker MUST run under an **argv allowlist** that rejects any flag not on the sanctioned list. The allowlist is per-tool and is enforced at the call site by a wrapper:

```python
# tools/worker/secure_subprocess.py

# Static allowlists per tool (sanctioned flags only).
JOERN_ARGV_ALLOWLIST: frozenset[str] = frozenset({
    "--language", "--output", "--script", "--src", "--cpg-only",
})
CODEQL_ARGV_ALLOWLIST: frozenset[str] = frozenset({
    "database", "create", "analyze", "--source-root", "--db",
    "--format", "--output", "--ram", "--threads",
})
GIT_ARGV_ALLOWLIST: frozenset[str] = frozenset({
    "clone", "checkout", "fetch", "log", "diff", "ls-files",
    "--depth", "--branch", "--no-tags", "--quiet",
    "-c", "core.sshCommand",   # for SSH key handling
})

def secure_run(tool: str, argv: list[str], *,
               timeout_s: int, env: dict[str, str], cwd: str) -> CompletedProcess:
    allowlist = {
        "joern":  JOERN_ARGV_ALLOWLIST,
        "codeql": CODEQL_ARGV_ALLOWLIST,
        "git":    GIT_ARGV_ALLOWLIST,
    }[tool]
    for arg in argv:
        if arg.startswith("-") and arg.split("=", 1)[0] not in allowlist:
            raise ArgvAllowlistViolation(f"flag {arg!r} not in {tool} allowlist")
    return subprocess.run(
        [resolve_pinned_binary(tool)] + argv,
        capture_output=True, check=True, timeout=timeout_s, env=env, cwd=cwd,
        shell=False,           # never shell=True
    )
```

**Invariants of `secure_run`:**

- `shell=False` always.
- Positional arguments are listed (no string interpolation into a single command line).
- `env` is constructed from the worker's env-var contract; the host env is **not** inherited.
- `timeout_s` is mandatory.
- The tool binary path is resolved via `resolve_pinned_binary(tool)` which reads from a fixed in-image path; the host `PATH` is not consulted (this is what makes `env_digest` characterize `Env` per `DOC-INV §4.5` counter-example).

### 3.4 Error contracts

| Error | Cause | Response |
|---|---|---|
| `ArgvAllowlistViolation` | Caller passed a non-sanctioned flag to `secure_run` | Hard fail; this is a security-relevant bug. Alarm. |
| `EnvDigestMissing` | `SCANIPY_ENV_DIGEST` env var not injected at boot | Refuse to start the worker. INV-2 requires a real `env_digest`. |
| `ECRImageNotSigned` | (At ECS task launch — Cosign verification fails) | ECS refuses to start the task; image promotion gate per `CMP-DEPLOY-04`. |
| `SCMCloneFailed` | Source clone fails after `CMP-SCM-05` retries | `report_status(state='failed', error=...)`; SQS retry. |
| `WorkerTimeout` | Task exceeds SQS visibility-timeout (15 min snapshot jobs per CLAR-DEPLOY-06) | SQS message returned to queue; max-receive 3 → DLQ. |

---

## 4. Inputs and outputs

### 4.1 Inputs

| Input | Source | Contract |
|---|---|---|
| `SnapshotJob` message | SQS (CLAR-DEPLOY-06) | `{snapshot_id, codebase_id, commit_sha, env_digest, artifact_keys, parent_snapshot_id?}` |
| `SCANIPY_ENV_DIGEST` env var | ECS task metadata (the running image's digest) | INV-2; must equal `SnapshotJob.env_digest` else hard fail. |
| Pinned tools (`joern`, `codeql`, `git`) | Bundled into the worker image at build time, with image-internal pinned paths | Per `AC-SNAP-05b`, changing any of them changes the image digest. |
| Secrets (`SCANIPY_HMAC_SECRET`, SCM credentials) | Secrets Manager via ECS task `secrets` block (CLAR-DEPLOY-05) | Env-var injection; no filesystem secrets. |
| Source @ commit | Cloned via `CMP-SCM-*` to ephemeral working dir | Read-only after clone. |

### 4.2 Outputs

| Output | Where | Contract |
|---|---|---|
| 5 snapshot artifacts | S3 at keys from `DOC-CMP-SNAP-01 §4.2` | Persisted before `report_status(state='ready')` fires. |
| `report_status` callback | `CMP-SNAP-01` via HMAC-bearer POST | Triggers DB update of `snapshots` row. |
| OTel spans / metrics | CloudWatch Logs + X-Ray (CLAR-DEPLOY-07) | Every span carries `S_version`, `env_digest`, `org_id` attributes per `.claude/rules/02-provenance.md`. |
| `OracleRunJob` (for `CMP-SNAP-04`) | A separate SQS queue, enqueued at `report_status(state='ready')` iff `precondition_status='closed-world'` | Enqueued by `CMP-SNAP-01` `report_status` handler, not by the worker itself. |

---

## 5. Invariants touched

| Invariant | How `CMP-SNAP-05` discharges it | Test |
|---|---|---|
| **INV-2 ORIGIN** | The container image digest **is** `env_digest`. Per `AC-SNAP-05b`, changing any bundled tool (`joern`, `codeql`, `git`) changes the digest. ECR + Cosign keyless signing (CLAR-DEPLOY-13) makes the digest unforgeable. The worker reads `SCANIPY_ENV_DIGEST` from ECS task metadata (the live image digest), refusing to start if absent. | `TST-AC-SNAP-05b` `[FORTHCOMING]`; `TST-INV-2-SNAP-01` (downstream — the snapshot row carries the value). |
| **Tool isolation (operational, INV-1/INV-2 supporting)** | `secure_run` consults pinned in-image paths; the host `PATH` is not used. This is what makes `env_digest` actually characterize `Env` (`DOC-INV §4.5` counter-example). | `TST-AC-SNAP-05a` `[FORTHCOMING]` — argv allowlist negative test. |

---

## 6. Algorithm / data flow

### 6.1 Worker lifecycle (per `DOC-RUNBOOK §2`)

```
1. Build  — Dockerfile (workers/snapshot/Dockerfile):
            FROM <pinned base image>@sha256:<digest>
            RUN curl -L <joern-pinned-tag>/joern-cli.zip ...
            RUN curl -L <codeql-pinned-version>/codeql-bundle ...
            RUN apt-get install -y git=<pinned-version>
            (every step pinned by digest or fixed version)
2. Publish — Push to ECR; Cosign keyless signature via GHA OIDC; SLSA-3 attestation
             stored as ECR artifact (CLAR-DEPLOY-13).
3. Launch  — ECS Fargate task with the Cosign-verified image; ECS injects
             SCANIPY_ENV_DIGEST from task metadata; secrets injected via task
             `secrets` block (CLAR-DEPLOY-05).
4. Execute — SQS dequeue -> clone -> CW-DETECT -> compute_incremental_cpg
             -> upload artifacts -> report_status.
5. Shutdown — Task exits after ACKing the SQS message; no persistent state on
              the task filesystem.
```

### 6.2 Execute phase (per job)

```
on dequeue SnapshotJob{snapshot_id, codebase_id, commit_sha, env_digest, artifact_keys, parent?}:
    assert env_digest == os.environ["SCANIPY_ENV_DIGEST"]   # INV-2 guard
    creds = secrets_manager.get(scm_credentials_arn)
    src_root = cmp_scm_clone(codebase_id, commit_sha, creds)

    cw_verdict = cmp_snap_03.detect(CwDetectRequest(src_root, detect_langs(src_root), parent))
    incr_result = cmp_snap_02.compute_incremental_cpg(IncrementalCpgRequest(
        parent_snapshot=parent,
        current_commit=commit_sha,
        cw_verdict=cw_verdict.verdict,
        theta_cone=0.25,                # CLAR-PARAM-01
        theta_files=0.4,                # CLAR-PARAM-01
        source_tree_root=src_root,
    ))

    # Upload exactly 5 artifacts at deterministic S3 keys (DOC-CMP-SNAP-01 §4.2)
    for artifact, key in zip(
        (incr_result.new_cpg.tarball(),
         incr_result.new_cpg.reverse_symbol_index(),
         incr_result.new_cpg.dynamic_call_graph(),
         incr_result.delta_graph,
         build_precondition_status_json(cw_verdict, incr_result)),
        artifact_keys.all()
    ):
        s3_put(S3_BUCKET, key, artifact)

    snapshot_digest = sha256(canonical_artifact_bytes(...))
    report_status(snapshot_id, state="ready",
                  precondition_status=incr_result.precondition_status,
                  snapshot_digest=snapshot_digest,
                  env_digest=os.environ["SCANIPY_ENV_DIGEST"])
```

### 6.3 Tool invocation example (secure)

> **AMENDED 2026-07-19 (Wave-4 real-Joern validation):** the original example
> (`secure_run("joern", ["--language", …, "--src", …, "--cpg-only"])`) does
> NOT match the pinned joern v4.0.554 release — the main `joern` launcher has
> no `--output`/`--cpg-only` flags (it warns "Unknown option", drops into
> interactive REPL mode, and exits 0 without producing a `cpg.bin`). The real
> headless parse surface is the separate `joern-parse` binary (source root
> positional). The Scanipy language id is mapped to Joern's bundled-frontend
> name first (`python` → `pythonsrc`; bare `python` selects a legacy
> generator that is not bundled). `analysis/cpg_ingest/joern_frontend.py` is
> the authoritative implementation.

```python
secure_run(
    "joern-parse",
    argv=["--language", "javasrc",       # JOERN_LANGUAGE_BY_SCANIPY_LANG["java"]
          "--output", str(tmp_cpg_path),
          str(src_root)],                # positional input, no --src
    timeout_s=600,
    env={"PATH": "/opt/joern/bin:/opt/temurin-jre/bin", "JAVA_HOME": "/opt/temurin-jre",
         "HOME": str(tmp_workdir)},      # JVM/joern-console need a WRITABLE HOME
    cwd=tmp_workdir,
)
```

### 6.4 CPG-ingest sub-scope (`analysis/cpg_ingest/`; CLAR-SNAP-03/05, both RESOLVED 2026-07-16)

**Ownership.** `CMP-SNAP-05` owns "parse source into `analysis.ordering.CPG`" as a sub-scope, not a
separate component (CLAR-SNAP-03) — this code executes entirely inside the worker's own execute
loop (§6.2), invoked immediately after `CMP-SNAP-03 CW-DETECT` clears the precondition. It is never
independently scheduled or deployed.

**Handshake contract** (the interface `§6.2`'s execute loop calls against):

```python
def parse_source(
    src_root: Path, language: str, *, env: Mapping[str, str], workdir: Path
) -> analysis.ordering.CPG: ...
```

Implemented by `analysis.cpg_ingest.joern_frontend.parse_source`, a two-phase `secure_run`
orchestration:

1. **Parse phase** — exactly the `§6.3` invocation above, producing a binary `cpg.bin`.
2. **Export phase (CLAR-SNAP-05)** — `secure_run("joern", argv=["--script", "/opt/joern/scripts/export_cpg.sc"], env={..., "SCANIPY_CPG_BIN_PATH": ..., "SCANIPY_EXPORT_JSON_PATH": ...}, ...)`.
   `JOERN_ARGV_ALLOWLIST` has no `joern-export`/`--param` pair (verified,
   `tools/worker/secure_subprocess.py:42-50`), so the export script is a **fixed, in-image CPGQL
   script** (`workers/snapshot/joern-scripts/export_cpg.sc`) parameterized via the `env` dict
   `secure_run` already threads — no allowlist widening. The script dumps a flat JSON node/edge
   array which `analysis.cpg_ingest.mapper.map_export` maps onto `analysis.ordering.CPG`.

**Determinism obligation (INV-5).** The mapper computes its **own** deterministic node-emission
order, `structural_path`, and `enclosing_decl_fqn` — it never trusts Joern's raw export array order,
since that order is not guaranteed stable across runs (threaded/overlay parser passes) and directly
feeds Algorithm 5's (`analysis/ordering.py`) canonical-order seed label and tie-breaks. Proven by an
anti-vacuity control: `map_export(fixture) == map_export(shuffled_export(fixture))`
(`tests/unit/test_cpg_ingest.py`).

**Property → `CPGNode` mapping table and the `CPGEdge.kind` vocabulary** (`AST`/`CFG` direct
passthrough; `CDG`+`REACHING_DEF` collapsed to `PDG`; any other raw kind is fail-closed,
`UnknownEdgeKindError`) are single-sourced in `analysis/cpg_ingest/mapper.py`'s module docstring —
not duplicated here to avoid drift.

**Status:** the `.sc` export script is **unverified against a real Joern install** (no `joern`
binary available in the dev sandbox that built it) — every API assumption is documented in the
script's own header pending a Wave-4 real-Joern diff. `graph_views.py` (the `GraphView` builder for
`CMP-SNAP-02`'s incremental path) and `decl_reparser.py` are honest, typed `NotImplementedError`
stubs — `CMP-SNAP-02`/`compute_incremental_cpg` is bypassed entirely for a first-ever (no-parent)
snapshot per CLAR-SNAP-04; this sub-scope only needs to satisfy the bootstrap path today.

---

## 7. Failure modes and error contracts

| Failure | Detection | Response |
|---|---|---|
| `SCANIPY_ENV_DIGEST` env var missing or empty at boot | Worker bootstrap | Refuse to start; ECS task exits non-zero; task definition flagged in CloudWatch. INV-2 absolutely requires a real digest. |
| Worker image not signed by Cosign | ECS task launch hook | ECS refuses to launch; promotion gate per `CMP-DEPLOY-04`. |
| Argv allowlist violation | `secure_run` wrapper | Hard fail; alarm. This is treated as a security-relevant bug (could indicate code injection attempt). |
| `subprocess.run` shell injection attempt (e.g. `shell=True`) | Code review + linter (CI gate) | Blocked at PR; if it ships, hard fail at runtime via `secure_run` enforcement. |
| Joern / CodeQL / git binary missing in image | `secure_run` resolution | Hard fail; image build verification gate (`CMP-CI-01`). |
| SCM clone fails | `cmp_scm_clone` raises after `CMP-SCM-05` retry exhaustion | `report_status(state='failed')`; SQS retry; max-receive → DLQ. |
| Visibility-timeout exceeded (job > 15 min) | SQS | Message redelivered; max-receive 3 → DLQ; alarm. |
| Out-of-memory during CPG construction | ECS task killed by Linux OOMKiller | ECS task exits; SQS redelivers; if it persists, the job is DLQ'd and SRE re-runs with a larger Fargate task size. |
| HMAC signature on `report_status` rejected by API | `CMP-SNAP-01` returns 401 | Retry up to 3× with backoff; if still rejected, the worker exits the job as `failed` and DLQs. (HMAC mismatch is a configuration bug.) |
| Secrets Manager fetch fails | Worker bootstrap or per-job lookup | Exponential backoff; alarm on sustained failure. |

---

## 8. Provenance threading

`CMP-SNAP-05` does not write directly to the `provenance_records` table; it threads the following values into the `report_status` callback (which `CMP-SNAP-01` then persists on the snapshot row):

| Field | Source | Threading rule |
|---|---|---|
| `env_digest` | `SCANIPY_ENV_DIGEST` (ECS task metadata; the running image digest) | INV-2 — the **authoritative value** for the platform. |
| `snapshot_digest` | sha256 over canonical artifact bytes | Link 2 of the audit chain. |
| `precondition_status` | from `CMP-SNAP-03 CW-DETECT` (the actual route from `CMP-SNAP-02`) | Threaded faithfully; never overridden. |

OTel spans emitted by the worker MUST include attributes `S_version`, `env_digest`, `origin` (for any span that touches a finding emission path) per `.claude/rules/02-provenance.md`.

**Must NOT touch:** `origin` (set by `CMP-ORCH-03`), `S_version` (set by `CMP-ORCH-01` from scan submission), `cpg_order_hash` (set by `CMP-CORE-03`), `slice_fingerprint` (set by `CMP-CORE-02`).

---

## 9. Acceptance criteria cross-reference

Quoted verbatim from `SDD.md §4 CMP-SNAP-05`. Paraphrasing an AC is a contract break (RULE-4). All TST-AC-* are `[FORTHCOMING]`.

| AC | Verbatim statement | Test artifact |
|---|---|---|
| **AC-SNAP-05a** | > The argument allowlist rejects any flag not on the sanctioned list (negative test). | `TST-AC-SNAP-05a` `[FORTHCOMING]` — unit test: assert `secure_run("joern", argv=["--evil-flag"])` raises `ArgvAllowlistViolation`. |
| **AC-SNAP-05b** | > The container image digest is the authoritative `env_digest` and changing any bundled tool changes the digest. | `TST-AC-SNAP-05b` `[FORTHCOMING]` — build test: rebuild the image with a different `joern` pin and assert the resulting ECR digest differs. Also covered by `TST-INV-2-SNAP-01` for the downstream stamping. |

Invariant tests cross-referenced:

- `TST-INV-2-SNAP-01 [FORTHCOMING]` — the `snapshots` row writes a non-empty `env_digest` equal to the container image digest.

---

## 10. Open questions

| CLAR-ID | Question | Status | Impact on CMP-SNAP-05 |
|---|---|---|---|
| `CLAR-DEPLOY-01` | Cloud / compute service | **RESOLVED** | ECS Fargate. |
| `CLAR-DEPLOY-05` | Secrets vendor + injection path | **RESOLVED** | Secrets Manager → ECS task `secrets` env-var injection. |
| `CLAR-DEPLOY-06` | Queue technology | **RESOLVED** | SQS standard + DLQ, 15-min visibility timeout for snapshot jobs. |
| `CLAR-DEPLOY-13` | Image registry + signing | **RESOLVED** | ECR + Cosign keyless via GHA OIDC; SLSA-3 attestation. |
| `CLAR-DEPLOY-16` | Per-tenant isolation backstop | **RESOLVED** | Worker IAM session scoped to a single `org_id` per scan. |
| `CLAR-OWNER-01` | Per-component owner | **DEFERRED** | §1 `Owner` stays DEFERRED. |

No new CLAR-SNAP-* are filed by this document.

---

## 11. References

- `SDD.md §4 CMP-SNAP-05` — verbatim ACs.
- `PLAN.md §"Phase 3 — Snapshotter + CW-DETECT + differential oracle"`, `§"Central correction"`.
- `docs/cross-cutting/DOC-DEPLOY-DECISIONS.md` — CLAR-DEPLOY-01, 05, 06, 13, 16.
- `docs/cross-cutting/DOC-INV.md §4` — INV-2 owner exposition.
- `docs/cross-cutting/DOC-API.md` — HMAC-bearer `report_status` callback contract.
- `docs/cross-cutting/DOC-RUNBOOK.md §2` — worker lifecycle.
- `docs/components/DOC-CMP-SNAP-01.md` (sibling) — API + persistence (callback target).
- `docs/components/DOC-CMP-SNAP-02.md` (sibling) — in-process invocation of incremental CPG.
- `docs/components/DOC-CMP-SNAP-03.md` (sibling) — in-process invocation of CW-DETECT.
- `docs/components/DOC-CMP-DEPLOY-02.md` (sibling, forthcoming) — worker base image.
- `docs/components/DOC-CMP-DEPLOY-04.md` (sibling, forthcoming) — CI/CD pipeline (Cosign verification).
- `.claude/rules/00-global.md` (RULE-6 provenance threading), `.claude/rules/02-provenance.md`.

---

*Document end. Status: ACTIVE. Per `AC-DOC-04`, this file plus the cross-cutting refs above is sufficient for an implementation agent to produce a passing `CMP-SNAP-05`. This component is the `env_digest` origin for the platform; INV-2 begins here.*
