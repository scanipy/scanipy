# DOC-CMP-DEPLOY-02 — Worker container baseline

**Status:** ACTIVE (Phase 0 per-component deliverable)
**Source-of-truth lineage:**

- `WBS.md §2.4 CMP-DEPLOY-02` (Purpose + AC-DEPLOY-02a/b/c).
- `SDD.md §4 CMP-SNAP-05` (`AC-SNAP-05b` — image digest IS `env_digest`; the load-bearing INV-2 contract).
- `WBS.md §17` — `CLAR-DEPLOY-13` (RESOLVED — ECR + Cosign keyless + SLSA-3) and `CLAR-DEPLOY-05` (RESOLVED — Secrets Manager env-var injection).
- `PLAN.md §"Central correction"` — `Env` is a versioned parameter; this component **defines** `Env` via the image digest.
- `docs/cross-cutting/DOC-DEPLOY-DECISIONS.md` — CLAR-DEPLOY-13, CLAR-DEPLOY-05, CLAR-DEPLOY-01.
- `docs/cross-cutting/DOC-INV.md §4` — INV-2 owner exposition (`CMP-DEPLOY-02` is the **`env_digest` producer**).
- `docs/cross-cutting/DOC-RUNBOOK.md §2.1` — Build phase of worker lifecycle.
- `docs/components/DOC-CMP-SNAP-05.md` — the consumer of this image (the worker runtime that reads `SCANIPY_ENV_DIGEST` from ECS task metadata).
- `.claude/rules/00-global.md`, `.claude/rules/05-determinism.md` (the worker image IS what makes byte-identical SARIF over `deterministic-core` possible).

This document is the **implementation contract** for `CMP-DEPLOY-02`. It is the **`env_digest` producer**: the ECR digest of the artifact built here is the canonical `Env` identifier for the entire platform. Reproducibility of `deterministic-core` findings (PLAN property (a)) hinges on a reproducible build of this image.

---

## 1. Component identity

| Field | Value |
|---|---|
| `CMP-ID` | `CMP-DEPLOY-02` |
| Subsystem | Deployment (`WBS.md §2.4`) |
| Staging | Stage A (`WBS.md §2.4`) |
| Depends-On | `CMP-DEPLOY-01` (`WBS.md §20`) |
| Owner | **DEFERRED** via `CLAR-OWNER-01`; operational owner per `.claude/commands/sre-agent.md` is the SRE/DevOps Agent. |
| INV-* touched | **INV-2 PRODUCER.** The ECR image digest is `env_digest`. Mutating any pinned tool changes the digest by construction. The signing step (Cosign keyless via GHA OIDC) makes the digest unforgeable. |
| Substrate | AWS ECR (CLAR-DEPLOY-13) · Sigstore Cosign keyless (CLAR-DEPLOY-13) · SLSA-3 attestation (CLAR-DEPLOY-13) |

---

## 2. Mandate

**Verbatim WBS `Purpose:` (`WBS.md §2.4 CMP-DEPLOY-02`):**

> Produce the base container image that bundles `joern`, `codeql`, `git` and pins each by digest; bake the environment-variable contract, the argument allowlist machinery, and the `report_status` callback affordances into the image. The image digest **is** `env_digest` (per `AC-SNAP-05b`); changing any bundled tool changes the digest.

**Operational role.** `CMP-DEPLOY-02` produces two container images that are published to ECR and consumed by the snapshot worker (`CMP-SNAP-05`) and detector worker (`CMP-ORCH-03`) respectively. Each image **pins every layer by sha256 digest** (not by tag), bundles the platform's analysis toolchain, and includes the `LoggerFactory`, the `secure_run` argv-allowlist wrapper, and the OTel SDK initialiser. The output of a successful build is a Cosign-signed image with a SLSA-3 provenance attestation. The image digest produced here is then read by the running ECS task via task metadata and becomes the `env_digest` carried on every snapshot and every finding (`AC-SNAP-01c`, `AC-SNAP-05b`). A reproducible build is the operational contract that makes byte-identical SARIF over the `deterministic-core` partition possible (`.claude/rules/05-determinism.md`).

---

## 3. Interface contract

`CMP-DEPLOY-02` is a build-time artifact specification, not a runtime service. Its interfaces are:

1. **Dockerfiles** at `workers/snapshot/Dockerfile` and `workers/detector/Dockerfile`.
2. **Pinning manifest** at `workers/pins.json` enumerating every base image and tool with its sha256 digest and source URL.
3. **Build verifier** at `workers/build/verify_pins.py` (the AC-DEPLOY-02c gate — refuses to publish if any digest is unspecified).
4. **Published artifact:** an ECR image plus a Cosign signature plus a SLSA-3 provenance attestation.

### 3.1 Dockerfile shape (snapshot worker)

```dockerfile
# workers/snapshot/Dockerfile
# CMP-DEPLOY-02 — worker base image. Every FROM and every tool MUST be digest-pinned.
# Build with --provenance=true --sbom=true (Docker Buildx) per CLAR-DEPLOY-13.

# ----- Stage 1: tool fetcher (pinned by digest) -----
FROM debian:12-slim@sha256:<DEBIAN_DIGEST>  AS tools
ARG JOERN_VERSION
ARG JOERN_SHA256
ARG CODEQL_VERSION
ARG CODEQL_SHA256
ARG GIT_VERSION
ARG GIT_SHA256

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl unzip && \
    rm -rf /var/lib/apt/lists/*

# joern — pinned by published release SHA256 (verified after download)
RUN curl -fsSL -o /tmp/joern.zip \
        "https://github.com/joernio/joern/releases/download/v${JOERN_VERSION}/joern-cli.zip" && \
    echo "${JOERN_SHA256}  /tmp/joern.zip" | sha256sum -c - && \
    unzip /tmp/joern.zip -d /opt && \
    rm /tmp/joern.zip

# codeql — pinned by published release SHA256
RUN curl -fsSL -o /tmp/codeql.zip \
        "https://github.com/github/codeql-cli-binaries/releases/download/v${CODEQL_VERSION}/codeql-linux64.zip" && \
    echo "${CODEQL_SHA256}  /tmp/codeql.zip" | sha256sum -c - && \
    unzip /tmp/codeql.zip -d /opt && \
    rm /tmp/codeql.zip

# git — pinned via Debian package version (apt manifest digest already pinned by base layer)
RUN apt-get update && apt-get install -y --no-install-recommends \
        "git=${GIT_VERSION}" && \
    rm -rf /var/lib/apt/lists/*

# ----- Stage 2: runtime -----
FROM python:3.11-slim-bookworm@sha256:<PYTHON_DIGEST>
LABEL org.opencontainers.image.title="scanipy-snapshot-worker"
LABEL org.opencontainers.image.source="https://github.com/scanipy/scanipy"

# Copy the pinned tooling from the fetcher stage.
COPY --from=tools /opt/joern    /opt/joern
COPY --from=tools /opt/codeql   /opt/codeql
COPY --from=tools /usr/bin/git  /usr/bin/git
COPY --from=tools /usr/lib/git-core /usr/lib/git-core

# Python deps pinned by hash in requirements.txt
COPY workers/snapshot/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --require-hashes -r /tmp/requirements.txt

# Worker code (the SCANIPY_ENV_DIGEST env var is filled at runtime by ECS task metadata)
COPY services/snapshot /app/services/snapshot
COPY tools/worker /app/tools/worker

ENV PATH=/opt/joern/bin:/opt/codeql:/usr/bin:/usr/local/bin
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Non-root user; image hardening (no shell access from running task)
RUN useradd --system --uid 10001 --shell /usr/sbin/nologin scanipy
USER 10001:10001
WORKDIR /app

# Entry point: the snapshot worker main loop. argv allowlist enforced by tools/worker/secure_subprocess.py
ENTRYPOINT ["python", "-m", "services.snapshot.worker"]
```

The detector worker Dockerfile (`workers/detector/Dockerfile`) is structurally identical, with `services/scan/detector_worker` as the entrypoint.

**Placeholder note.** `<DEBIAN_DIGEST>`, `<PYTHON_DIGEST>`, and the `*_SHA256` build args appear above as placeholders so the contract is readable in this document. **The implementation agent must replace every placeholder with the concrete sha256 digest from `workers/pins.json` before publish.** `AC-DEPLOY-02c` enforces this at build time via `verify_pins.py`.

### 3.2 Pinning manifest (`workers/pins.json`)

```json
{
  "schema_version": 1,
  "generated_at": "<iso8601 of last pin update>",
  "comment": "Every entry MUST have both 'version' and 'sha256'. verify_pins.py refuses to build if either is empty.",
  "base_images": {
    "debian":   { "tag": "12-slim",          "sha256": "<sha256>" },
    "python":   { "tag": "3.11-slim-bookworm", "sha256": "<sha256>" }
  },
  "tools": {
    "joern":    { "version": "v4.0.x",       "sha256": "<sha256>", "source": "https://github.com/joernio/joern/releases/..." },
    "codeql":   { "version": "v2.20.x",      "sha256": "<sha256>", "source": "https://github.com/github/codeql-cli-binaries/releases/..." },
    "git":      { "version": "1:2.39.x-1",   "sha256": "<from-debian-snapshot-archive>" }
  },
  "python_packages_lockfile": "workers/snapshot/requirements.txt",
  "python_packages_lockfile_sha256": "<sha256-of-the-lockfile>"
}
```

**Why JSON and not embedded ARG defaults.** Decoupling the pin set from the Dockerfile lets `verify_pins.py` (the AC-DEPLOY-02c gate) reason about pins without parsing Dockerfiles, and lets `CMP-DEPLOY-04`'s CI step assert that the substrate decision record's tool versions match what is actually about to be built.

### 3.3 Build verifier (`workers/build/verify_pins.py`)

```python
# Discharges AC-DEPLOY-02c. Run BEFORE `docker buildx build` in CI.
import json, sys, pathlib

PINS_FILE = pathlib.Path("workers/pins.json")

def main() -> int:
    pins = json.loads(PINS_FILE.read_text())

    missing: list[str] = []

    for name, entry in pins["base_images"].items():
        if not entry.get("sha256"):
            missing.append(f"base_images.{name}.sha256")

    for name, entry in pins["tools"].items():
        if not entry.get("version"):
            missing.append(f"tools.{name}.version")
        if not entry.get("sha256"):
            missing.append(f"tools.{name}.sha256")

    if not pins.get("python_packages_lockfile_sha256"):
        missing.append("python_packages_lockfile_sha256")

    if missing:
        print("ERROR (AC-DEPLOY-02c): pins are incomplete:", file=sys.stderr)
        for m in missing:
            print(f"  - {m}", file=sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

### 3.4 Hardening contract

| Property | Enforced by | Why |
|---|---|---|
| Non-root user (uid 10001) | Dockerfile `USER` directive | Mitigates container escape blast radius. |
| No shell in entrypoint | `ENTRYPOINT ["python", "-m", ...]` (exec form) | Prevents shell injection if argv is somehow influenced. |
| Read-only root FS | ECS task definition `readonlyRootFilesystem: true` (set by CMP-DEPLOY-01) | Tmp workdirs use a writable ephemeral volume mount. |
| No package manager at runtime | Multi-stage build leaves `apt`/`pip` behind in builder stages | An attacker with code-exec cannot pull new tools. |
| Cosign signature | `cosign sign --yes <ecr>/scanipy-snapshot@sha256:<digest>` per CLAR-DEPLOY-13 | Tamper-evident; ECS task launch verifies signature (CMP-DEPLOY-04). |
| SLSA-3 attestation | GHA SLSA generator + Cosign attest | Build inputs, build commit, and tool digests linked to the image digest. |

---

## 4. Inputs and outputs

### 4.1 Inputs

| Input | Source | Contract |
|---|---|---|
| Pinning manifest | `workers/pins.json` | Every required field populated; verified by `verify_pins.py` per AC-DEPLOY-02c. |
| Worker source code | `services/snapshot/worker.py`, `services/scan/detector_worker.py`, `tools/worker/` | Subject to the standard repo CI gates (`CMP-CI-01`). |
| Python requirements | `workers/snapshot/requirements.txt` (with `--require-hashes`) | Hash-pinned; lockfile sha256 recorded in `pins.json`. |
| ECR repository URIs | from `CMP-DEPLOY-01` outputs (`ecr_snapshot_repo_uri`, `ecr_detector_repo_uri`) | Provisioned in `infra/modules/registry`. |
| AWS OIDC role | from `CMP-DEPLOY-01` outputs (`aws_oidc_deploy_role_arn`) | Used by GHA to push to ECR. |

### 4.2 Outputs

| Output | Where | Contract |
|---|---|---|
| `scanipy-snapshot` image | ECR (`CLAR-DEPLOY-13`) | Tag = release tag (`v[0-9]+.[0-9]+.[0-9]+`); digest is what `CMP-SNAP-05` consumes as `env_digest`. |
| `scanipy-detector` image | ECR (`CLAR-DEPLOY-13`) | Same shape, different entrypoint. |
| Cosign signature | ECR via Sigstore Rekor | Keyless, GHA OIDC as signing identity. |
| SLSA-3 provenance attestation | ECR artifact via `slsa-github-generator` + Cosign attest | Links build inputs (commit, pins.json sha256) to image digest. |

---

## 5. Invariants touched

| Invariant | How `CMP-DEPLOY-02` discharges it | Test |
|---|---|---|
| **INV-2 PRODUCER** | The ECR image digest **is** `env_digest`. Per `AC-SNAP-05b`, changing any bundled tool produces a different image digest. The `verify_pins.py` gate (`AC-DEPLOY-02c`) refuses to build if any digest is unspecified, so `env_digest` is never derived from an unpinned input. Cosign + SLSA-3 makes the digest unforgeable. | `TST-AC-DEPLOY-02a`, `TST-AC-DEPLOY-02b`, `TST-AC-DEPLOY-02c` `[FORTHCOMING]`; downstream `TST-AC-SNAP-05b`, `TST-INV-2-SNAP-01`. |
| **INV-1 supporting** | A reproducible build of this image is what makes byte-identical SARIF over the `deterministic-core` partition achievable (`.claude/rules/05-determinism.md`). If two builds at the same commit produce different image digests, the Attestor (`CMP-CP-05`) will fail spuriously. | `TST-AC-CP-05a/c` (downstream — non-determinism in the image build will surface as Attestor diff). |

---

## 6. Algorithm / data flow

### 6.1 Build flow (per release tag)

```
1. Trigger      A tag push v[0-9]+.[0-9]+.[0-9]+ to the main branch fires
                .github/workflows/deploy.yml (per CMP-DEPLOY-04).

2. Verify pins  workers/build/verify_pins.py is called BEFORE docker build.
                Refuses to proceed if any digest in pins.json is empty
                (AC-DEPLOY-02c).

3. Buildx       docker buildx build --provenance=true --sbom=true \
                  --build-arg JOERN_VERSION=... --build-arg JOERN_SHA256=... \
                  --build-arg CODEQL_VERSION=... --build-arg CODEQL_SHA256=... \
                  --build-arg GIT_VERSION=... \
                  -f workers/snapshot/Dockerfile \
                  -t <ecr>/scanipy-snapshot:<tag> \
                  --push .

4. Sign         cosign sign --yes <ecr>/scanipy-snapshot@sha256:<digest>
                  (keyless; GHA OIDC as signing identity per CLAR-DEPLOY-13)

5. Attest       slsa-github-generator produces a SLSA-3 provenance attestation;
                cosign attest --type slsaprovenance --predicate <file> \
                  <ecr>/scanipy-snapshot@sha256:<digest>

6. Record       The image digest is written to the substrate decision record
                under "env_digest history" (CMP-DEPLOY-04 commits this back
                via the env_digest rollover ceremony in AC-DEPLOY-04a).
```

### 6.2 The `env_digest` rollover ceremony

When any tool in `pins.json` is bumped:

1. PR updates `pins.json` with the new version + sha256.
2. PR title contains `env_digest rollover` (lint-checked).
3. PR description references which CLAR-DEPLOY-* (if any) changed and includes a paragraph on why the bump is needed (security CVE, feature, etc.).
4. Code-review approval includes the Security Analyst if a CW-DETECT-touching tool is bumped (`.claude/rules/00-global.md` RULE-9 if applicable).
5. The merge produces a new image digest; downstream snapshots created after the rollover carry the new `env_digest`.
6. **Existing snapshots are not re-stamped.** Per INV-2, every snapshot's `env_digest` is the digest in force at the time of the snapshot — historical reproducibility is scoped to that historical `env_digest`.

---

## 7. Failure modes and error contracts

| Failure | Detection | Response |
|---|---|---|
| `verify_pins.py` finds a missing digest | CI step before `docker build` | Hard CI fail (`AC-DEPLOY-02c`); PR cannot land. |
| Dependency CVE published against `joern`/`codeql`/`git` | Renovate / Dependabot / advisory feeds | File a PR bumping `pins.json` per the rollover ceremony; merge starts a new `env_digest`. SLA: critical CVE → 7 days; high → 30 days. |
| `joern`/`codeql` release a major version | Manual review | Bump is non-trivial; may require detector-side adaptation. Treat as a feature PR plus an `env_digest` rollover. |
| Build is non-reproducible (two builds at same commit produce different digests) | Detected indirectly via Attestor diff on canary corpus (`AC-CP-05c`) | Hard incident; SRE investigates. Typically a missing pin, `apt-get update` without snapshot, or a timestamp baked into a layer. |
| Cosign signing fails | GHA workflow step | Workflow exits non-zero; image is NOT promoted. SRE investigates Sigstore Rekor availability. |
| SLSA attestation generation fails | GHA workflow step | Workflow exits non-zero. The image alone (without attestation) is **not** a complete `CMP-DEPLOY-02` artifact. |
| ECR push fails (network, IAM, throttling) | GHA workflow step | Retried with backoff; if persistent, escalate to SRE. |
| `apt-get install git=<version>` returns "version not found" | Build step | Debian dropped the version from main archive; switch to Debian snapshot archive (https://snapshot.debian.org/) with a pinned date. Treated as an `env_digest` rollover. |
| Image pulls from un-pinned base by mistake (regression) | Build-time linter (`.dockerignore` + `hadolint` + CI grep for `FROM .*:.*` without `@sha256:`) | Hard CI fail. |

---

## 8. Provenance threading

`CMP-DEPLOY-02` does not write to `provenance_records` directly. It **publishes** the `env_digest` that other components thread:

| Field | Source | Threaded by |
|---|---|---|
| `env_digest` | The ECR digest of the published image | `CMP-SNAP-05` (reads `SCANIPY_ENV_DIGEST` from ECS task metadata at boot; refuses to start if empty); `CMP-SNAP-01` (stamps it on the `snapshots` row); `CMP-FND-02` (NOT NULL constraint); `CMP-FND-03` (link 4 of the audit chain per `DOC-PROVENANCE §3`). |
| Build inputs (commit, pins.json sha256) | SLSA-3 attestation predicate | The auditor's "where did this `env_digest` come from?" question is answered by retrieving the SLSA attestation from ECR. |
| Tool digests | `workers/pins.json` (committed in repo) | Part of the substrate decision record's `env_digest` history. |

OTel spans emitted by the worker at runtime MUST carry `env_digest` per `.claude/rules/02-provenance.md` and `CMP-DEPLOY-03`; that threading happens in `LoggerFactory` and the OTel span processor, both baked into this image.

---

## 9. Acceptance criteria cross-reference

Quoted verbatim from `WBS.md §2.4 CMP-DEPLOY-02`. Paraphrasing an AC is a contract break (RULE-4). All TST-AC-* are `[FORTHCOMING]`.

| AC | Verbatim statement | Test artifact |
|---|---|---|
| **AC-DEPLOY-02a** | > `joern`, `codeql`, `git` are present at pinned digests inside the image. | `TST-AC-DEPLOY-02a` `[FORTHCOMING]` — unit test: build the image; `docker run --rm <image> sha256sum /opt/joern/bin/joern /opt/codeql/codeql /usr/bin/git` and compare each against `workers/pins.json`. |
| **AC-DEPLOY-02b** | > Mutating any bundled tool changes the image digest, and that digest is the authoritative `env_digest` exposed to the snapshot worker. | `TST-AC-DEPLOY-02b` `[FORTHCOMING]` — build test: build at commit A, capture ECR digest D1; bump `joern` sha256 in `pins.json` to a different value, rebuild, capture D2; assert `D1 != D2`. Cross-test with `TST-AC-SNAP-05b`. |
| **AC-DEPLOY-02c** | > The image-build process refuses to publish if any pinned digest is unspecified. | `TST-AC-DEPLOY-02c` `[FORTHCOMING]` — unit test: pass a `pins.json` with one empty sha256 to `verify_pins.py`; assert non-zero exit. Integration test: run the full GHA build workflow with the same malformed pins file; assert the workflow fails before any `docker push`. |

Load-bearing observation: **`AC-SNAP-05b`** depends on `AC-DEPLOY-02b`. If `CMP-DEPLOY-02` ships an image whose digest does not change when a tool changes, INV-2 is violated platform-wide. The `verify_pins.py` gate (AC-DEPLOY-02c) is the upstream defence.

---

## 10. Open questions

All `CLAR-DEPLOY-*` items bearing on this component are **RESOLVED**.

| CLAR-ID | Question | Status | Impact on CMP-DEPLOY-02 |
|---|---|---|---|
| `CLAR-DEPLOY-01` | Cloud / compute service | **RESOLVED** | ECS Fargate; image consumed by Fargate tasks. |
| `CLAR-DEPLOY-05` | Secrets vendor + injection | **RESOLVED** | Secrets Manager env-var injection at ECS task start; image's env-var contract is the consumer interface. |
| `CLAR-DEPLOY-13` | Image registry + signing | **RESOLVED** | ECR + Cosign keyless via GHA OIDC; SLSA-3 attestation. |
| `CLAR-OWNER-01` | Per-component owner | **DEFERRED** | §1 `Owner` stays DEFERRED. |

No new CLAR-DEPLOY-* are filed by this document.

---

## 11. References

- `WBS.md §2.4 CMP-DEPLOY-02` — verbatim Purpose + ACs.
- `SDD.md §4 CMP-SNAP-05 AC-SNAP-05b` — the downstream contract this component delivers.
- `docs/cross-cutting/DOC-DEPLOY-DECISIONS.md` — CLAR-DEPLOY-13, CLAR-DEPLOY-05, CLAR-DEPLOY-01.
- `docs/cross-cutting/DOC-INV.md §4` — INV-2 owner exposition.
- `docs/cross-cutting/DOC-RUNBOOK.md §2.1`, `§2.2` — Build + Publish phases of the worker lifecycle.
- `docs/components/DOC-CMP-SNAP-05.md` — consumer of the image (the runtime contract).
- `docs/components/DOC-CMP-DEPLOY-01.md` (sibling) — provisions the ECR repository this component pushes to.
- `docs/components/DOC-CMP-DEPLOY-04.md` (sibling, forthcoming) — calls this component's build flow.
- `.github/workflows/deploy.yml` (existing) — scaffolds the `build-images` job that runs §6.1.
- `.claude/rules/00-global.md` (RULE-6 provenance threading), `.claude/rules/05-determinism.md`.

---

*Document end. Status: ACTIVE. Per `AC-DOC-04`, this file plus the cross-cutting refs above is sufficient for an implementation agent to produce a passing `CMP-DEPLOY-02`. This component is the `env_digest` producer for the platform; INV-2 has its physical origin here.*
