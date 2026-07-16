#!/usr/bin/env python3
"""TEST-ONLY seed: one org row + one fixed test API key (CLAR-CP-01-02).

****************************************************************************
* TEST-ONLY. This script's entire purpose is a test-auth bypass. It MUST   *
* NEVER be run, and its output MUST NEVER be reachable, when ENV or        *
* SCANIPY_ENV is "prod" — see :func:`refuse_if_prod`, which is the FIRST   *
* thing :func:`main` calls. Superseded by real Auth0 JWKS verification     *
* once CMP-CP-04 lands (CLAR-CP-01-02).                                    *
****************************************************************************

Context (CLAR-CP-01-02, WBS.md §17): there is no `api_keys` table in the
CMP-CP-03 schema (`db/migrations/versions/20260524_0001_initial_tenancy_tables.py`)
and no production `JWTVerifierPort` implementation in-tree yet — Auth0 JWKS
verification is deferred to CMP-CP-04 (`services/control_plane/http/adapter.py`
ships only `fail_closed_jwt_verifier`, which raises). Building the consuming
`JWTVerifierPort` test-mode implementation is explicitly OUT OF SCOPE for this
script (RULE-4 — do not invent scope beyond the assigned track); this script
only creates the two pieces of state a future test-mode verifier would need
to consult:

  1. One fixed, deterministic `orgs` row (RLS is NOT enabled on `orgs` per
     `db/migrations/versions/20260524_0002_rls_policies.py`, so a direct
     insert as the connecting role is sufficient — no BYPASSRLS role switch
     needed).
  2. One fixed test API key, generated locally and stored in AWS Secrets
     Manager as `{org_id, role, api_key}` — matching the platform's existing
     secrets-injection decision (CLAUDE.md §8 / CLAR-DEPLOY-05: "AWS Secrets
     Manager -> ECS task"), NOT a new `api_keys` table (no new migration is
     written per the assigned track's constraint: "already-complete
     migrations, just execute them, don't write new ones unless you hit an
     actual failure").

`role="scanner"` is what a future verifier would place on the synthesized
`JWTClaims` — the RBAC matrix (`services/control_plane/constants.py`) grants
`scanner` submit+read on `scans`, which is the capability
`POST /api/v1/scans` requires (DOC-API §2.6). No `memberships` row is seeded:
`db/session.py::request_binding_args` hard-codes `user_id="scanner"` for the
scanner role (DOC-CMP-CP-01 §3.1 step 4) rather than looking one up, and the
RLS policies key only on `org_id`, not membership.

Idempotent: safe to re-run. The org id is a fixed, obviously-synthetic UUID
(never `gen_random_uuid()`-issued in practice), and the insert uses
``ON CONFLICT (id) DO UPDATE`` on the org row. The API key is only
(re)generated if the Secrets Manager secret does not already exist — re-runs
reuse the existing key rather than silently rotating it out from under
whichever test harness holds it.

Usage::

    export SCANIPY_DATABASE_URL="postgresql://scanipy_admin:...@host:5432/scanipy"
    python scripts/seed_test_org.py --region us-east-1

The database URL is read exactly as ``db/migrations/env.py`` reads it (same
``SCANIPY_DATABASE_URL`` contract), so this script never invents a second
notion of how to find the database.
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol
from uuid import UUID

if TYPE_CHECKING:
    from collections.abc import Mapping

# Fixed, deterministic test-org identity (CLAR-CP-01-02). Never issued by
# `gen_random_uuid()` in production use — obviously-synthetic by construction
# (all-zero except a single sentinel byte), so an operator scanning `orgs`
# can spot it as test fixture at a glance.
TEST_ORG_ID = UUID("00000000-0000-4000-8000-000000000001")
TEST_ORG_NAME = "scanipy-test-org"
TEST_ORG_ROLE = "scanner"  # matches services.control_plane.constants.Role

DEFAULT_SECRET_NAME = "scanipy/test-org/api-key"  # noqa: S105 — a Secrets Manager secret NAME, not a credential value


class SeedProdRefusalError(RuntimeError):
    """Raised by :func:`refuse_if_prod` — the fail-closed ENV/SCANIPY_ENV gate."""


def refuse_if_prod(env: Mapping[str, str] | None = None) -> None:
    """Fail closed: refuse to run when ENV or SCANIPY_ENV is "prod".

    This is a HARD requirement (not a warning) — this script's entire output
    is a test-auth bypass, and CLAR-CP-01-02 records explicitly that it must
    never be reachable in production. Checked against BOTH env var names in
    use across this repo: shell apply scripts read ``ENV``
    (`infra/*-apply.sh`), application code reads ``SCANIPY_ENV``
    (`tools/observability/init.py`). Comparison is case-insensitive and
    whitespace-trimmed so `Prod`/`PROD `/etc. all refuse too. An unset value
    does NOT refuse (this script is meant to run in exactly those unset/dev
    contexts) — only an explicit "prod" trips the gate.
    """
    source = env if env is not None else os.environ
    for var_name in ("ENV", "SCANIPY_ENV"):
        value = source.get(var_name)
        if value is not None and value.strip().casefold() == "prod":
            raise SeedProdRefusalError(
                f"refusing to run: {var_name}={value!r} — seed_test_org.py is a "
                "TEST-ONLY auth bypass (CLAR-CP-01-02) and must never run against "
                "a production environment"
            )


def generate_api_key() -> str:
    """A fresh, high-entropy test API key. Never persisted to source control."""
    return "scanipy_test_" + secrets.token_hex(24)


@dataclass(frozen=True)
class SeedResult:
    org_id: UUID
    org_name: str
    secret_name: str
    api_key_created: bool  # True iff a NEW key was generated this run


class _Cursor(Protocol):
    def execute(self, sql: str, params: tuple[object, ...] = ()) -> object: ...
    def fetchone(self) -> tuple[object, ...] | None: ...
    def close(self) -> None: ...


class _Connection(Protocol):
    def cursor(self) -> _Cursor: ...
    def commit(self) -> None: ...
    def rollback(self) -> None: ...


def _seed_org_row(conn: _Connection) -> None:
    """Idempotent upsert of the fixed test org (RLS is NOT enabled on `orgs`)."""
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO orgs (id, name, status)
            VALUES (%s, %s, 'active')
            ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, status = 'active';
            """,
            (str(TEST_ORG_ID), TEST_ORG_NAME),
        )
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        cur.close()


class _SecretsClient(Protocol):
    """Structural shape of the one boto3 `secretsmanager` client this script
    uses. Methods are declared `**kwargs` (rather than boto3's real positional
    signature) because boto3 clients are dynamically generated at runtime with
    no first-party type stubs (mirrors the repo's existing `boto3.*`
    `ignore_missing_imports` mypy override) — this Protocol exists only so the
    hermetic test double (`tests/unit/test_seed_test_org.py`) has a checkable
    contract to satisfy, not to fully model the real client.
    """

    def describe_secret(self, **kwargs: object) -> Mapping[str, object]: ...
    def create_secret(self, **kwargs: object) -> object: ...


def _secret_exists(secrets_manager: _SecretsClient, secret_name: str) -> bool:
    try:
        secrets_manager.describe_secret(SecretId=secret_name)
        return True
    except Exception as exc:  # boto3 raises a dynamic ClientError subclass per-call
        if type(exc).__name__ == "ResourceNotFoundException":
            return False
        raise


def _seed_api_key_secret(
    *, region: str, secret_name: str, boto3_client: _SecretsClient | None = None
) -> bool:
    """Create the test API key secret iff it does not already exist.

    Returns True iff a NEW key was generated this run. Never calls
    `get_secret_value` — this script only ever WRITES the secret; a caller
    that already knows the secret exists does not need to read it back to
    confirm the org/role pairing (that pairing is deterministic — this
    module's own constants — not something that needs round-tripping through
    AWS to verify).
    """
    if boto3_client is not None:
        client = boto3_client
    else:
        import boto3  # lazy import — repo precedent (S3ObjectStore, KMS lambda)

        client = boto3.client("secretsmanager", region_name=region)

    if _secret_exists(client, secret_name):
        return False

    payload = json.dumps(
        {
            "org_id": str(TEST_ORG_ID),
            "role": TEST_ORG_ROLE,
            "api_key": generate_api_key(),
        }
    )
    client.create_secret(
        Name=secret_name,
        Description=(
            "TEST-ONLY Scanipy API key (CLAR-CP-01-02). Never reachable when "
            "ENV/SCANIPY_ENV=prod. Superseded by Auth0 JWKS once CMP-CP-04 lands."
        ),
        SecretString=payload,
        Tags=[
            {"Key": "Component", "Value": "CMP-CP-01"},
            {"Key": "Purpose", "Value": "test-auth-bypass"},
        ],
    )
    return True


def seed(
    *,
    database_url: str,
    region: str = "us-east-1",
    secret_name: str = DEFAULT_SECRET_NAME,
    connection: _Connection | None = None,
    boto3_client: _SecretsClient | None = None,
) -> SeedResult:
    """Seed the fixed test org row + the test API key secret.

    ``connection``/``boto3_client`` are injectable seams for hermetic tests
    (matching the Protocol-based DI pattern already used throughout the
    codebase, e.g. `services/scan/api.py`'s ports) — production calls supply
    neither and this function opens a real `psycopg2` connection + a lazily
    imported `boto3` client.
    """
    if connection is not None:
        conn = connection
    else:
        import psycopg2  # type: ignore[import-untyped] # lazy import — mirrors the boto3 lazy-import precedent

        conn = psycopg2.connect(database_url)

    try:
        _seed_org_row(conn)
    finally:
        if connection is None:
            conn.close()  # type: ignore[attr-defined]

    created = _seed_api_key_secret(
        region=region, secret_name=secret_name, boto3_client=boto3_client
    )
    return SeedResult(
        org_id=TEST_ORG_ID,
        org_name=TEST_ORG_NAME,
        secret_name=secret_name,
        api_key_created=created,
    )


def main(argv: list[str] | None = None) -> int:
    refuse_if_prod()  # MUST be the first thing main() does — fail closed.

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--region", default=os.environ.get("AWS_REGION", "us-east-1"))
    parser.add_argument("--secret-name", default=DEFAULT_SECRET_NAME)
    args = parser.parse_args(argv)

    database_url = os.environ.get("SCANIPY_DATABASE_URL")
    if not database_url:
        print(
            "ERROR: SCANIPY_DATABASE_URL is not set (same contract as "
            "db/migrations/env.py) — refusing to guess a target database.",
            file=sys.stderr,
        )
        return 1

    result = seed(database_url=database_url, region=args.region, secret_name=args.secret_name)

    print(f"org_id:          {result.org_id}")
    print(f"org_name:        {result.org_name}")
    print(f"secret_name:     {result.secret_name}")
    print(f"api_key_created: {result.api_key_created}")
    print("(the API key VALUE is never printed by this script)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
