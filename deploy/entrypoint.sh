#!/bin/sh
# DOCKER-01 entrypoint: wait for Postgres, apply the tenanted schema, launch the
# oracle scan API. POSIX sh (python:3.11-slim ships dash, not bash).
set -eu

# NB: never echo SCANIPY_DATABASE_URL — it contains the DB password.
echo "[entrypoint] waiting for the database…"
python - <<'PY'
import os, time, sqlalchemy
url = os.environ["SCANIPY_DATABASE_URL"]
last = None
for _ in range(60):
    try:
        sqlalchemy.create_engine(url).connect().close()
        print("[entrypoint] database is up")
        break
    except Exception as exc:  # noqa: BLE001
        last = exc
        time.sleep(2)
else:
    raise SystemExit(f"[entrypoint] database not reachable: {last}")
PY

echo "[entrypoint] applying Alembic migrations (tenanted schema)…"
alembic upgrade head

echo "[entrypoint] starting scan API on 0.0.0.0:8000"
exec uvicorn deploy.scanipy_oracle.app:app --host 0.0.0.0 --port 8000
