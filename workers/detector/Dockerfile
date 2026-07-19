# workers/detector/Dockerfile
# CMP-DEPLOY-02 — detector worker base image. Structurally identical to the
# snapshot worker (DOC-CMP-DEPLOY-02 §3.1) with the detector worker entrypoint.
# Every FROM and every tool MUST be digest-pinned. The ECR digest of this image
# IS env_digest (AC-SNAP-05b / INV-2 producer).
#
# Build with: docker buildx build --provenance=true --sbom=true (CLAR-DEPLOY-13).
# The sha256 placeholders below MUST be replaced with the concrete digests in
# workers/pins.json before publish; verify_pins.py (AC-DEPLOY-02c) gates that
# the pins are non-empty.

# ----- Stage 1: tool fetcher (pinned by digest) -----
FROM debian:12-slim@sha256:0104b334637a5f19aa9c983a91b54c89887c0984081f2068983107a6f6c21eeb AS tools
ARG JOERN_VERSION
ARG JOERN_SHA256
ARG CODEQL_VERSION
ARG CODEQL_SHA256
ARG GIT_VERSION
ARG GIT_SHA256

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
LABEL org.opencontainers.image.title="scanipy-detector-worker"
LABEL org.opencontainers.image.source="https://github.com/scanipy/scanipy-v3.2"
ARG GIT_VERSION

# ca-certificates + git installed via apt in the runtime stage — same fix as
# workers/snapshot/Dockerfile (see that file's comment for the full story:
# copying git binaries across stages misses the OS dependency closure —
# libcurl3-gnutls/perl/liberror-perl — so every https:// clone failed; found
# live via one-shot ECS smoke tests on v0.1.4 + v0.1.6).
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates "git=${GIT_VERSION}" && \
    rm -rf /var/lib/apt/lists/*

# Copy the pinned tooling from the fetcher stage.
COPY --from=tools /opt/joern        /opt/joern
COPY --from=tools /opt/codeql       /opt/codeql

# Python deps pinned by hash in requirements.txt (lockfile sha256 in pins.json).
COPY workers/detector/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --require-hashes -r /tmp/requirements.txt

# Worker code. SCANIPY_ENV_DIGEST is filled at runtime by ECS task metadata.
#
# CMP-ORCH-03 entrypoint gap fix (Track 1C, services/scan/detector_worker.py):
# the previous COPY set below only brought in services/scan + tools/worker, but
# services/scan/worker.py (already-shipped CMP-ORCH-03) imports analysis.*,
# services/scan/detector_worker.py additionally imports detectors.registry
# (CMP-DET-02) + services.substrate.object_store/queue (CMP-DEPLOY-01), and
# services/scan/worker.py imports tools.observability.metrics — none of which
# were on the image (verified by direct import-graph inspection). Without this,
# `python -m services.scan.detector_worker` fails at import time with
# ModuleNotFoundError even though the module itself is correct.
COPY services/scan        /app/services/scan
COPY services/substrate   /app/services/substrate
COPY analysis             /app/analysis
COPY detectors            /app/detectors
COPY tools/worker         /app/tools/worker
COPY tools/observability  /app/tools/observability

ENV PATH=/opt/joern/bin:/opt/codeql:/usr/bin:/usr/local/bin
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Non-root user; image hardening (no shell access from the running task).
RUN /usr/sbin/useradd --system --uid 10001 --shell /usr/sbin/nologin scanipy
USER 10001:10001
WORKDIR /app

# Exec form: no shell. argv allowlist enforced by tools/worker/secure_subprocess.py.
ENTRYPOINT ["python", "-m", "services.scan.detector_worker"]
