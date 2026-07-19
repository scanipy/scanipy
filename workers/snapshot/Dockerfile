# workers/snapshot/Dockerfile
# CMP-DEPLOY-02 — snapshot worker base image. Every FROM and every tool MUST be
# digest-pinned (DOC-CMP-DEPLOY-02 §3.1). The ECR digest of this image IS
# env_digest (AC-SNAP-05b / INV-2 producer); changing any bundled tool changes
# the digest by construction.
#
# Build with: docker buildx build --provenance=true --sbom=true (CLAR-DEPLOY-13).
# The sha256 placeholders below MUST be replaced with the concrete digests in
# workers/pins.json before publish; verify_pins.py (AC-DEPLOY-02c) gates that
# the pins are non-empty, and a CI grep for `FROM .*:.*` without `@sha256:`
# (DOC §7) rejects any un-pinned base.

# ----- Stage 1: tool fetcher (pinned by digest) -----
FROM debian:12-slim@sha256:0104b334637a5f19aa9c983a91b54c89887c0984081f2068983107a6f6c21eeb AS tools
ARG JOERN_VERSION
ARG JOERN_SHA256
ARG CODEQL_VERSION
ARG CODEQL_SHA256
ARG GIT_VERSION
ARG GIT_SHA256
ARG TEMURIN_JRE_VERSION
ARG TEMURIN_JRE_SHA256

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl unzip && \
    rm -rf /var/lib/apt/lists/*

# joern — pinned by published release SHA256 (verified after download).
RUN curl -fsSL -o /tmp/joern.zip \
        "https://github.com/joernio/joern/releases/download/${JOERN_VERSION}/joern-cli.zip" && \
    echo "${JOERN_SHA256}  /tmp/joern.zip" | sha256sum -c - && \
    unzip /tmp/joern.zip -d /opt && \
    mv /opt/joern-cli /opt/joern && \
    rm /tmp/joern.zip

# Joern is JVM-based and requires JDK 21+ (joernio/joern README "Requirements";
# not bundled in the joern-cli release archive, and NOT installable via apt on
# this pinned Debian release — bookworm main ships only openjdk-17, and
# bookworm-backports carries no openjdk package at all, verified against the
# live Debian package index). Pinned Eclipse Temurin JRE tarball instead,
# fetched/verified the same way as joern/codeql above. Discovered missing via
# a real one-shot ECS smoke test (`joern: command not found`-class failure
# would have followed the ca-certificates fix, v0.1.4 proof run) — a headless
# JRE (not a full JDK) is sufficient since this worker only ever RUNS joern,
# never compiles anything.
RUN curl -fsSL -o /tmp/temurin-jre.tar.gz \
        "https://github.com/adoptium/temurin21-binaries/releases/download/${TEMURIN_JRE_VERSION}/OpenJDK21U-jre_x64_linux_hotspot_21.0.11_10.tar.gz" && \
    echo "${TEMURIN_JRE_SHA256}  /tmp/temurin-jre.tar.gz" | sha256sum -c - && \
    mkdir -p /opt/temurin-jre && \
    tar -xzf /tmp/temurin-jre.tar.gz -C /opt/temurin-jre --strip-components=1 && \
    rm /tmp/temurin-jre.tar.gz

# codeql — pinned by published release SHA256.
RUN curl -fsSL -o /tmp/codeql.zip \
        "https://github.com/github/codeql-cli-binaries/releases/download/${CODEQL_VERSION}/codeql-linux64.zip" && \
    echo "${CODEQL_SHA256}  /tmp/codeql.zip" | sha256sum -c - && \
    unzip /tmp/codeql.zip -d /opt && \
    rm /tmp/codeql.zip

# git — pinned via Debian package version (base layer is already digest-pinned).
RUN apt-get update && apt-get install -y --no-install-recommends \
        "git=${GIT_VERSION}" && \
    rm -rf /var/lib/apt/lists/*

# ----- Stage 2: runtime -----
FROM python:3.11-slim-bookworm@sha256:8dca233de9f3d9bb410665f00a4da6dd06f331083137e0e98ccf227236fcc438
LABEL org.opencontainers.image.title="scanipy-snapshot-worker"
LABEL org.opencontainers.image.source="https://github.com/scanipy/scanipy-v3.2"
ARG GIT_VERSION

# ca-certificates + git are installed HERE, via apt, in the runtime stage —
# NOT copied from the fetcher stage. Two live one-shot ECS smoke tests
# (v0.1.4, v0.1.6) each caught a different piece of the same underlying bug
# class: copying `/usr/bin/git` + `/usr/lib/git-core` across stages brings
# the binaries but NOT their OS-level dependency closure. v0.1.4: no CA
# trust store in the runtime base (slim ships none), so HTTPS clones failed
# TLS verification. v0.1.6: still exit 128, because `git-remote-https` (the
# helper every https:// clone execs) links `libcurl3-gnutls` — a hard
# Depends of Debian's git package (alongside perl/liberror-perl/libexpat1)
# that the slim runtime base does not ship and the binary COPY never
# brought. A real apt install of the SAME pinned git version resolves the
# complete dependency closure by construction; the pin (GIT_VERSION, from
# workers/pins.json) is unchanged, and the base image both stages share the
# same Debian release (bookworm), so the installed binary is identical to
# what the fetcher stage verified.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates "git=${GIT_VERSION}" && \
    rm -rf /var/lib/apt/lists/*

# Copy the pinned tooling from the fetcher stage.
COPY --from=tools /opt/joern        /opt/joern
COPY --from=tools /opt/codeql       /opt/codeql
COPY --from=tools /opt/temurin-jre  /opt/temurin-jre

# Joern's own launcher script resolves `java` off PATH (and some JVM tooling
# additionally checks JAVA_HOME) — both are set here rather than relying on
# either alone.
ENV JAVA_HOME=/opt/temurin-jre

# Python deps pinned by hash in requirements.txt (lockfile sha256 in pins.json).
COPY workers/snapshot/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --require-hashes -r /tmp/requirements.txt

# Worker code. SCANIPY_ENV_DIGEST is filled at runtime by ECS task metadata
# (CMP-SNAP-05 reads it and refuses to start if empty).
COPY services/snapshot    /app/services/snapshot
COPY tools/worker         /app/tools/worker

# services.substrate (S3ObjectStore/SQSQueue), services.scan (worker.py imports
# services.scan.provenance.InvariantViolation), and tools.observability
# (get_logger/record_job_completion) — all three were missing from this
# Dockerfile despite being module-load imports of worker.py; the container
# would ModuleNotFoundError on `python -m services.snapshot.worker` before a
# single job was ever processed. Same class of bug as the `analysis` COPY gap
# below (caught by claude-review on PR #319), found via a full first-party
# import-graph trace while wiring the real parse_source/SQSQueue defaults
# (CLAR-SNAP-03/05 landing). `services/scan` is copied wholesale (not just the
# `provenance`/`models` subpackages worker.py touches today) to match the
# detector Dockerfile's own precedent and avoid re-discovering this class of
# gap on the next transitive import.
COPY services/substrate   /app/services/substrate
COPY services/scan        /app/services/scan
COPY tools/observability  /app/tools/observability

# CLAR-SNAP-03: analysis.cpg_ingest (this worker's CPG-ingest sub-scope) and its
# analysis.ordering dependency. joern_frontend.py imports both at module load —
# omitting this COPY makes the package invisible in-container (ModuleNotFoundError
# at the first parse_source() call), caught by claude-review on PR #319.
COPY analysis /app/analysis

# CLAR-SNAP-05: fixed in-image CPGQL export script, parameterized at runtime
# via env vars (SCANIPY_CPG_BIN_PATH / SCANIPY_EXPORT_JSON_PATH — see
# analysis/cpg_ingest/joern_frontend.py's EXPORT_SCRIPT_PATH constant, which
# MUST match this destination path). Never src_root-relative — a trusted,
# versioned, in-image artifact invoked via the sanctioned `--script` flag
# (JOERN_ARGV_ALLOWLIST), not tenant-controlled.
COPY workers/snapshot/joern-scripts/export_cpg.sc /opt/joern/scripts/export_cpg.sc

ENV PATH=/opt/joern/bin:/opt/codeql:/opt/temurin-jre/bin:/usr/bin:/usr/local/bin
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Non-root user; image hardening (no shell access from the running task).
RUN /usr/sbin/useradd --system --uid 10001 --shell /usr/sbin/nologin scanipy
USER 10001:10001
WORKDIR /app

# Exec form: no shell. argv allowlist enforced by tools/worker/secure_subprocess.py.
ENTRYPOINT ["python", "-m", "services.snapshot.worker"]
