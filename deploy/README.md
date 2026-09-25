# Self-hosting Scanipy (Docker)

This directory holds the packaged application deployment (`DOCKER-01`,
`CLAR-DEPLOY-25`) and its Postgres service. It requires no cloud account.

**Current containment (#396): new scans are unavailable.** The legacy Git and
Semgrep execution path has been removed pending the reviewed capture/worker
cutover. Existing stored scans remain readable. This is not the completed Black
Hat demo or a production-ready replacement. See the full
[cutover contract and remaining actions](../docs/bhmea/LEGACY-APP-CUTOVER.md).

Building or starting this version does not restore scanning. No environment
setting enables the removed legacy path. This code change does not itself
restart a running deployment, change its configuration or migrate its data.

## Quickstart

```bash
docker compose up --build          # from the repo root
# → http://localhost:8000 serves the unavailable-capability page
```

On start the entrypoint waits for Postgres, applies the configured Alembic
migrations, and serves the legacy read API. Review migrations and back up data
before starting an updated checkout against an existing deployment.

## What this path does — and doesn't

- `POST /api/scan` always returns HTTP 503, `code=native_scan_unavailable`, and
  `retryable=false`, before a new scan row, task, source staging or native work.
  It does not validate repository URLs while unavailable.
- `GET /api/scan/{scan_id}` retains its historical response and 404 behavior.
  Old `oracle` records keep their actual stored fields; this change neither
  rewrites nor certifies them. A legacy weak/location-derived identity is not
  a cross-refactor canonical identity or complete provenance proof.
- `GET /healthz` reports application liveness and explicit unavailable scan
  capability. It is not a database check or analysis-readiness certificate.
  Current `env_digest` is null (`not-observed`); `s_version` is only the configured
  label (`configured-only`), not proof of an accepted spec bundle.
- Startup keeps the existing database initialization and marks old in-process
  `running` scans interrupted, as before. It invokes no scanner/version probe.
  This is not the new durable occurrence queue or restart/retry implementation.
- The separate immutable-capture/analysis-worker, accepted-input resolver,
  occurrence persistence, final provenance and asynchronous UI still need their
  real integration tests. No full submission claim follows from this containment.

## Configuration (environment)

Set on the `scanipy` service in `docker-compose.yml` (or an `.env`):

| Variable | Default | Meaning |
|---|---|---|
| `SCANIPY_DATABASE_URL` | `postgresql://scanipy:scanipy_dev@db:5432/scanipy_dev` | Postgres DSN |
| `SCANIPY_S_VERSION` | `oracle-2026.08` | Configured legacy label exposed by health only; no new finding is emitted |
| `SCANIPY_RULES_DIR` | unused | Does not enable or configure this disabled route |
| `SEMGREP_BIN` | unused | Does not select any executable in this application |
| `LLM_TRIAGE` | `off` | No detection/triage work is launched by this legacy application |

The prior startup hash of a reported Semgrep version and rule files did not bind
the full actual runtime. It is no longer emitted as a current environment
identity. Historical stored digests are preserved without upgrading their meaning.

## Adding / editing rules

Editing `deploy/rules/` does not make this route executable or operationally
accept a rule. The replacement must bind exact immutable rule/model bytes and
actual acceptance evidence before a scan; a filename or version label is not
that binding. Correct CWE/origin mapping remains a cutover requirement.

## Upgrade

```bash
git pull
docker compose up --build -d       # rebuilds the app image; migrations re-apply idempotently
```

This version remains scan-unavailable after rebuild. Historical findings keep
their stamped values. Do not infer an observed image digest or comparability
from a configured tag, rule edit, rebuild command, or healthy web endpoint.

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

- This contained application does not acquire or analyze source. Safe native
  acquisition/analysis remains a separate prerequisite; cloning alone never
  established the promised no-execution guarantee.
- Containment does not fix legacy read authentication, historic-result bounds,
  default credentials, host isolation or every other service's native route.
- Change the default Postgres password (`scanipy_dev`) before exposing the stack beyond localhost.
- Run behind your own reverse proxy / auth if you expose port 8000; the app ships no auth on this path
  (single-tenant self-host). See [`../SECURITY.md`](../SECURITY.md).
