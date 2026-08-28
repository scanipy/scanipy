# Self-hosting Scanipy (Docker)

One command, no cloud account, no AWS. This directory holds the packaged application deployment
(`DOCKER-01`, `CLAR-DEPLOY-25`): a light `python:3.11-slim` image (git + Semgrep in an isolated venv)
plus the compose file that runs it alongside Postgres.

## Quickstart

```bash
docker compose up --build          # from the repo root
# → open http://localhost:8000  and paste a public GitHub repo URL
```

On start the app waits for Postgres, applies the Alembic (tenanted) schema, and serves the scan API.

## What this path does — and doesn't

- **Detection is oracle-passthrough** (engine: Semgrep). Every finding is
  `origin=oracle-passthrough`, `engine=semgrep`, `fingerprint_class=weak` — a stable same-source id,
  **not** a canonical-graph claim. Findings persist to the `oracle` Postgres schema, kept separate from
  the tenanted deterministic-core `findings` table.
- **The deterministic-core (IFDS/CPG) engine is staged** and not on this path. Byte-identical
  reproducibility and refactor-invariant identity are guarantees of that engine — see the
  honest-labeling ledger in [`../PLAN.md`](../PLAN.md).
- The stack is **single-tenant per deployment** and **single-node** (API + scan run in one service).
  Multi-container substrate (MinIO / a shared queue) is tracked as `DOCKER-02`.

## Configuration (environment)

Set on the `scanipy` service in `docker-compose.yml` (or an `.env`):

| Variable | Default | Meaning |
|---|---|---|
| `SCANIPY_DATABASE_URL` | `postgresql://scanipy:scanipy_dev@db:5432/scanipy_dev` | Postgres DSN |
| `SCANIPY_S_VERSION` | `oracle-2026.08` | spec-set version stamped on findings (INV-2) |
| `SCANIPY_RULES_DIR` | `/app/deploy/rules` | Semgrep ruleset directory |
| `SEMGREP_BIN` | `semgrep` | Semgrep executable |
| `LLM_TRIAGE` | `off` | keeps the LLM strictly off the detection path (INV-3) |

`env_digest` (INV-2) is computed at startup as a real `sha256` over the Semgrep version + ruleset
content — the identity a re-run must match to be comparable. Check it at `GET /healthz`.

## Adding / editing rules

Drop or edit `*.yaml` Semgrep rules in `deploy/rules/`. Changing the ruleset changes `env_digest` by
construction (rebuild or restart to pick it up). Rules are CWE-mapped; keep `metadata.cwe` and
`metadata.title` set so findings render with a CWE and a human title.

## Upgrade

```bash
git pull
docker compose up --build -d       # rebuilds the app image; migrations re-apply idempotently
```

A new image (or ruleset) is a new `env_digest`. Findings recorded under a prior digest keep their
stamped value, so results stay comparable only within a fixed digest.

## Backup / restore

State lives in the `scanipy-pgdata` volume (Postgres). Back it up with `pg_dump`:

```bash
docker exec scanipy-db pg_dump -U scanipy scanipy_dev > backup.sql          # backup
cat backup.sql | docker exec -i scanipy-db psql -U scanipy -d scanipy_dev   # restore
```

## Teardown

```bash
docker compose down       # stop (keeps the data volume)
docker compose down -v    # stop AND wipe the database volume
```

## Security posture

- The scanned code is **never executed** — only cloned and statically analyzed.
- Change the default Postgres password (`scanipy_dev`) before exposing the stack beyond localhost.
- Run behind your own reverse proxy / auth if you expose port 8000; the app ships no auth on this path
  (single-tenant self-host). See [`../SECURITY.md`](../SECURITY.md).
