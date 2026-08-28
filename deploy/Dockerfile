# Scanipy — one-command self-host image (DOCKER-01, CLAR-DEPLOY-25).
#
# A LIGHT application image (not the digest-pinned Joern/CodeQL worker base in
# workers/*/Dockerfile): Python + git + Semgrep. It runs the oracle-passthrough
# scan API and, on start, applies the tenanted Alembic schema to the compose
# Postgres. NO AWS, no cloud account required.
#
# Semgrep is installed into its OWN venv so its (large) dependency tree can never
# clash with the application's pinned deps.
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        git ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# --- Semgrep (oracle engine) in an isolated venv ---
RUN python -m venv /opt/semgrep && \
    /opt/semgrep/bin/pip install --no-cache-dir semgrep && \
    ln -s /opt/semgrep/bin/semgrep /usr/local/bin/semgrep && \
    semgrep --version

WORKDIR /app
COPY . /app

# Application + migration deps. `http` = the pinned FastAPI/uvicorn/pydantic
# stack (CLAR-DEPLOY-19); `dev` supplies sqlalchemy/psycopg2/alembic. Together
# they cover every module the app + alembic env import.
RUN pip install --no-cache-dir -e ".[dev,http]"

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    SCANIPY_ENV=development \
    LLM_TRIAGE=off

EXPOSE 8000
# Invoke via sh so a missing exec-bit through COPY is never an issue.
ENTRYPOINT ["/bin/sh", "/app/deploy/entrypoint.sh"]
