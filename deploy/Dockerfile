# Scanipy — one-command self-host image (DOCKER-01, CLAR-DEPLOY-25).
#
# A LIGHT application image (not the digest-pinned Joern/CodeQL worker base in
# workers/*/Dockerfile): Python + git + Semgrep. It runs the oracle-passthrough
# scan API and, on start, applies the tenanted Alembic schema to the compose
# Postgres. NO AWS, no cloud account required.
#
# Semgrep is installed into its OWN venv so its (large) dependency tree can never
# clash with the application's pinned deps.
#
# Base is digest-pinned and Semgrep is version-pinned so the image — and therefore
# env_digest (INV-2) — is REPRODUCIBLE, per the project's pinned-tooling ethos.
# Bump both deliberately.
FROM python:3.11-slim@sha256:1042b61448fef4ba92d16a8c7eb4996d027568ce64792a7877fd88511e0af7c6

RUN apt-get update && apt-get install -y --no-install-recommends \
        git ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# --- Semgrep (oracle engine) in an isolated venv, version-pinned ---
RUN python -m venv /opt/semgrep && \
    /opt/semgrep/bin/pip install --no-cache-dir semgrep==1.175.0 && \
    ln -s /opt/semgrep/bin/semgrep /usr/local/bin/semgrep && \
    semgrep --version

WORKDIR /app
COPY . /app

# Application + migration deps — the LEAN `oracle` extra (FastAPI/uvicorn/pydantic
# + sqlalchemy/psycopg2/alembic) covers the scan API + the Alembic env without the
# dev/test toolchain (pytest, moto, boto3, ruff), keeping the shipped image small.
RUN pip install --no-cache-dir -e ".[oracle]"

# Run as a non-root system user. Everything written at runtime — the git clone
# (tempfile.mkdtemp → /tmp) and Semgrep's cache (HOME=/tmp) — lives under /tmp,
# so the container runs cleanly with a read-only root filesystem + tmpfs /tmp
# and dropped capabilities (see docker-compose.yml).
RUN useradd --system --uid 10001 --no-create-home appuser

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    HOME=/tmp \
    SCANIPY_ENV=development \
    LLM_TRIAGE=off

USER appuser
EXPOSE 8000
# Invoke via sh so a missing exec-bit through COPY is never an issue.
ENTRYPOINT ["/bin/sh", "/app/deploy/entrypoint.sh"]
