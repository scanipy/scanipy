# Fresh-install dependency compatibility — BHMEA prerequisite

Status: scoped local verification passed; remote CI/review pending. Addresses
#370 as a prerequisite of #366 under #362; does not complete clean Docker
installation, stage readiness, or R15.

## Observed failures

Fresh `.[dev,http]` resolution selected AnyIO 4.15.1 and SQLAlchemy 2.1.0.
Pinned Starlette 1.3.1 accesses `anyio.abc.BlockingPortal`; the new AnyIO loader
warns on that deprecated alias, stopping pytest collection under the existing
warnings-as-errors rule. This was observed locally and in PR #369's remote
attestor job, before canonical tests ran.

SQLAlchemy 2.1 defaults bare `postgresql://` URLs to psycopg 3, while Scanipy
declares psycopg2-binary and uses bare URLs. The default change and retained
explicit psycopg2 support are documented in the
[SQLAlchemy migration guide](https://docs.sqlalchemy.org/en/21/changelog/migration_21.html#default-postgresql-driver-changed-to-psycopg-psycopg-3).
The [AnyIO version history](https://anyio.readthedocs.io/en/stable/versionhistory.html)
records the 4.15 lazy-import change and its pytest >=9.2 compatibility fix.

## Scoped correction

- Pin AnyIO 4.14.2 alongside the existing HTTP stack in both HTTP and deployed
  oracle extras; do not suppress deprecation warnings.
- Keep SQLAlchemy on its 2.0 line in dev and oracle extras until a deliberate
  driver/URL migration. Snapshot/detector requirement files already pin 2.0.50.
- Bound pytest below 9.2 while this AnyIO stack is selected, so its older pytest
  plugin does not encounter the later deprecated alias described upstream.
- Add installed-constraint, actual HTTP request and no-connection database
  driver tests. Resolve and test a fresh supported-Python environment without
  ad hoc post-install downgrades.

This is a compatibility decision, not a security audit or an indefinite promise
that pinned packages need no updates. Review dependency advisories and upgrade
the stack deliberately; retain the actual complete environment manifest. The
full R15 clean-build/offline workflow still needs its own measured acceptance.

## Verification record

On 2026-09-25, a new Python 3.11.16 virtual environment installed `.[dev,http]`
using `uv pip install`, with no package downgrades or overrides afterward.
The declared constraints resolved AnyIO 4.14.2, SQLAlchemy 2.0.54, pytest 9.1.1,
Starlette 1.3.1, and psycopg2-binary 2.9.13. The complete observed package list
is retained in [environment.json](evidence/2026-09-25-dependency-compatibility/environment.json);
it is an observation, not a hash-pinned release lock or analysis `env_digest`.

Commands on the corrected branch based on `940d440`:

- `python -m pytest tests/unit tests/integration`: **862 passed, 47 skipped**
  in 30.39 seconds. Existing opt-in/external-service skips remain; this does
  not claim those services or their live integration tests were exercised.
- `ruff check .`: passed.
- `ruff format --check .`: 182 files passed.
- `mypy --config-file pyproject.toml analysis detectors integrations services workers`:
  81 source files passed.

The new seven tests exercise installed constraints, an actual in-process HTTP
request, and database driver selection without contacting a database. Repository
warnings-as-errors remain enabled. Normal hooks, remote CI and canonical review
are separate merge gates; their pending status is recorded in the PR, not
inferred from the local result.

The secret scanner's one new finding is the public Git base revision in the
environment inventory. Its exact file/value hash is recorded as a reviewed
non-secret in `.secrets.baseline`; no detector or evidence path was excluded.
