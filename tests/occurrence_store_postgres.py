"""Dedicated-cluster harness; never discovers or changes the legacy test DSN.

Only the profile's separately explicit test URL opts in. Every migration targets a newly
created child database. Cleanup checks captured database/role OIDs and owner;
it never terminates sessions, uses CASCADE, or drops an unowned resource.
"""

from __future__ import annotations

import os
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from typing import Literal
from uuid import UUID, uuid4

import psycopg2
import pytest
from psycopg2 import sql
from sqlalchemy.dialects.postgresql.psycopg2 import PGDialect_psycopg2
from sqlalchemy.engine import URL, make_url

from services.scan.occurrence_store.repository import occurrence_transaction

ROOT = Path(__file__).resolve().parents[1]
RESERVED = tuple(
    "scanipy_exec_" + role
    for role in ("owner", "request", "detector", "identity", "cleanup", "read")
)
ACCEPTED_RESERVED = tuple(
    "scanipy_accepted_" + role
    for role in ("owner", "policy_admin", "publisher", "resolver", "reader")
)


class PrivatePostgres:
    def __init__(self, url: str, *, profile: Literal["occurrence", "accepted"] = "occurrence"):
        if type(profile) is not str or profile not in ("occurrence", "accepted"):
            raise ValueError("unknown dedicated database profile")
        self.profile = profile
        self.reserved = RESERVED + (ACCEPTED_RESERVED if profile == "accepted" else ())
        self.migration_target = "20260926_0006" if profile == "accepted" else "20260925_0005"
        parsed = make_url(url)
        if parsed.drivername not in ("postgresql", "postgresql+psycopg2"):
            raise ValueError("dedicated tests require PostgreSQL")
        if set(parsed.query) - {"host"}:
            raise ValueError("unsupported database-routing URL query")
        if "host" in parsed.query and parsed.host is not None:
            raise ValueError("ambiguous database host")
        host = parsed.query.get("host", parsed.host)
        if not isinstance(host, str) or not host or "\x00" in host:
            raise ValueError("explicit local database host required")
        if "," in host or (host.startswith("/") and str(PurePosixPath(host)) != host):
            raise ValueError("exactly one normalized database host required")
        if host.startswith("/") and ".." in PurePosixPath(host).parts:
            raise ValueError("socket path cannot traverse parents")
        if not host.startswith("/") and host not in ("localhost", "127.0.0.1", "::1"):
            raise ValueError("dedicated fixture is local/socket-only")
        if not parsed.username or not parsed.database:
            raise ValueError("explicit database/user required")
        if any(
            key in os.environ
            for key in (
                "PGSERVICE",
                "PGSERVICEFILE",
                "PGHOSTADDR",
                "PGOPTIONS",
                "PGHOST",
                "PGPORT",
                "PGDATABASE",
                "PGUSER",
            )
        ):
            raise ValueError("ambient libpq routing/options are forbidden")
        self.base = {
            "host": host,
            "port": parsed.port or 5432,
            "dbname": parsed.database,
            "user": parsed.username,
            "password": parsed.password or "",
        }
        # Rebuild from closed concrete fields, NEVER propagate caller query keys
        # into SQLAlchemy, whose dbname/service overrides can change the target.
        self.url = URL.create(
            "postgresql+psycopg2",
            username=parsed.username,
            password=parsed.password,
            host=None if host.startswith("/") else host,
            port=parsed.port or 5432,
            database=parsed.database,
            query={"host": host} if host.startswith("/") else {},
        )
        self.database = "scanipy_" + profile + "_" + uuid4().hex
        self.child = {**self.base, "dbname": self.database}
        self.roles: dict[str, tuple[str, str]] = {}
        self.owned_roles: dict[str, int] = {}
        self.database_identity = None

    @contextmanager
    def admin(self, *, bootstrap=False):
        connection = psycopg2.connect(**(self.base if bootstrap else self.child))
        try:
            yield connection
        finally:
            connection.close()

    def migrate(self, target=None, *, expect_success=True, action="upgrade"):
        if action not in ("upgrade", "downgrade"):
            raise ValueError("unsupported migration test action")
        target = self.migration_target if target is None else target
        permitted = ("20260925_0003", "20260925_0004", "20260925_0005") + (
            ("20260926_0006",) if self.profile == "accepted" else ()
        )
        if type(target) is not str or target not in permitted:
            raise ValueError("unsupported dedicated migration target")
        target_url = self.url.set(drivername="postgresql+psycopg2", database=self.database)
        _, resolved = PGDialect_psycopg2().create_connect_args(target_url)
        for field in ("host", "port", "dbname", "user"):
            if str(resolved.get(field)) != str(self.child[field]):
                raise AssertionError("migration driver target differs from owned child")
        result = subprocess.run(
            [sys.executable, "-m", "alembic", action, target],
            cwd=ROOT,
            env={
                **os.environ,
                "SCANIPY_DATABASE_URL": target_url.render_as_string(hide_password=False).replace(
                    "%", "%%"
                ),
            },
            text=True,
            capture_output=True,
            timeout=60,
            check=False,
        )
        if expect_success and result.returncode:
            raise AssertionError(result.stdout + result.stderr)
        return result

    def setup(self):
        with self.admin(bootstrap=True) as connection:
            connection.autocommit = True
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT rolname FROM pg_roles WHERE rolname=ANY(%s)", (list(self.reserved),)
                )
                if cursor.fetchall():
                    raise AssertionError("reserved roles already exist: refusing dedicated fixture")
                cursor.execute(
                    sql.SQL("CREATE DATABASE {} TEMPLATE template0 ENCODING 'UTF8'").format(
                        sql.Identifier(self.database)
                    )
                )
                cursor.execute(
                    "SELECT oid,datdba FROM pg_database WHERE datname=%s", (self.database,)
                )
                self.database_identity = cursor.fetchone()
        # Legacy prerequisite names may already belong to the dedicated
        # bootstrap. Never adopt them. When absent, CREATE is authoritative;
        # a concurrent duplicate raises and is not caught/adopted.
        with self.admin() as connection, connection.cursor() as cursor:
            legacy_created = {}
            for name, suffix in (
                ("scanipy_app", ""),
                ("scanipy_triage", ""),
                ("scanipy_system", " BYPASSRLS"),
            ):
                cursor.execute("SELECT oid FROM pg_roles WHERE rolname=%s", (name,))
                if cursor.fetchone() is None:
                    cursor.execute(
                        sql.SQL("CREATE ROLE {} NOLOGIN" + suffix).format(sql.Identifier(name))
                    )
                    cursor.execute("SELECT oid FROM pg_roles WHERE rolname=%s", (name,))
                    legacy_created[name] = cursor.fetchone()[0]
            connection.commit()
        self.owned_roles.update(legacy_created)
        # Existing-role hostile defaults must not leak onto any NEW objects.
        with self.admin() as connection:
            with connection.cursor() as cursor:
                hostile = "occurrence_hostile_" + uuid4().hex
                cursor.execute(sql.SQL("CREATE ROLE {} NOLOGIN").format(sql.Identifier(hostile)))
                cursor.execute("SELECT oid FROM pg_roles WHERE rolname=%s", (hostile,))
                self.owned_roles[hostile] = cursor.fetchone()[0]
                self.hostile = hostile
                for category, privileges in (
                    ("TABLES", "ALL"),
                    ("FUNCTIONS", "EXECUTE"),
                    ("SCHEMAS", "ALL"),
                ):
                    cursor.execute(
                        sql.SQL(
                            "ALTER DEFAULT PRIVILEGES GRANT "
                            + privileges
                            + " ON "
                            + category
                            + " TO PUBLIC,{}"
                        ).format(sql.Identifier(hostile))
                    )
            connection.commit()
        self.migrate("20260925_0003")
        self._seed_legacy_history()
        original_history = self._legacy_history()
        self.legacy_acl = self._legacy_acl()
        self.migrate("20260925_0004")
        assert self.rows(
            "SELECT count(*) FROM pg_namespace n CROSS JOIN LATERAL "
            "aclexplode(n.nspacl) a WHERE n.nspname='scanipy_execution' AND "
            "a.grantee<>n.nspowner"
        ) == [(0,)]
        assert self.rows(
            "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON "
            "n.oid=c.relnamespace CROSS JOIN LATERAL aclexplode(c.relacl) a "
            "WHERE n.nspname='scanipy_execution' AND a.grantee<>c.relowner"
        ) == [(0,)]
        # This superficially safe reserved role is created by THIS fixture;
        # migration B must refuse it, not adopt it. Drop only the captured OID.
        with self.admin() as connection, connection.cursor() as cursor:
            cursor.execute("CREATE ROLE scanipy_exec_owner NOLOGIN")
            cursor.execute("SELECT oid FROM pg_roles WHERE rolname='scanipy_exec_owner'")
            reserved_oid = cursor.fetchone()[0]
            connection.commit()
        self.owned_roles["scanipy_exec_owner"] = reserved_oid
        failure = self.migrate("20260925_0005", expect_success=False)
        assert failure.returncode and "reserved execution role already exists" in failure.stderr
        with self.admin() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT oid FROM pg_roles WHERE rolname='scanipy_exec_owner'")
            assert cursor.fetchone() == (reserved_oid,)
            cursor.execute("DROP ROLE scanipy_exec_owner")
            connection.commit()
        del self.owned_roles["scanipy_exec_owner"]
        self.migrate("20260925_0005")
        self._record_successful_migration_roles()
        # Empty round-trip is ONLY this uniquely created child, never bootstrap
        # or a discovered baseline. No execution history has been inserted.
        self.migrate("20260925_0003", action="downgrade")
        assert self.rows("SELECT count(*) FROM pg_namespace WHERE nspname='scanipy_execution'") == [
            (0,)
        ]
        assert self.rows(
            "SELECT count(*) FROM pg_roles WHERE rolname=ANY(%s)", (list(RESERVED),)
        ) == [(0,)]
        for name in RESERVED:
            del self.owned_roles[name]
        self.migrate("20260925_0005")
        self._record_successful_migration_roles()
        assert self._legacy_acl() == self.legacy_acl
        assert self._legacy_history() == original_history
        self.round_trip_verified = True
        if self.profile == "accepted":
            self._setup_accepted()
        self._create_logins()

    def _setup_accepted(self):
        """Only this empty fixture-owned child; failed migration grants no ownership."""
        before_definitions = self._execution_definitions()
        before_acl = self._execution_acl()
        execution_oids = {name: self.owned_roles[name] for name in RESERVED}
        with self.admin() as connection, connection.cursor() as cursor:
            cursor.execute("CREATE ROLE scanipy_accepted_owner NOLOGIN")
            cursor.execute("SELECT oid FROM pg_roles WHERE rolname='scanipy_accepted_owner'")
            reserved_oid = cursor.fetchone()[0]
            connection.commit()
        self.owned_roles["scanipy_accepted_owner"] = reserved_oid
        failure = self.migrate("20260926_0006", expect_success=False)
        assert failure.returncode and "reserved accepted role already exists" in failure.stderr
        with self.admin() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT oid FROM pg_roles WHERE rolname='scanipy_accepted_owner'")
            assert cursor.fetchone() == (reserved_oid,)
            cursor.execute("DROP ROLE scanipy_accepted_owner")
            connection.commit()
        del self.owned_roles["scanipy_accepted_owner"]
        self.migrate("20260926_0006")
        self._record_successful_migration_roles(accepted=True)
        assert self._execution_definitions() == before_definitions
        self.migrate("20260925_0005", action="downgrade")
        assert self.rows(
            "SELECT count(*) FROM pg_namespace WHERE nspname='scanipy_accepted_inputs'"
        ) == [(0,)]
        assert self.rows(
            "SELECT count(*) FROM pg_roles WHERE rolname=ANY(%s)", (list(ACCEPTED_RESERVED),)
        ) == [(0,)]
        for name in ACCEPTED_RESERVED:
            del self.owned_roles[name]
        assert self._execution_definitions() == before_definitions
        assert self._execution_acl() == before_acl
        assert (
            dict(
                self.rows(
                    "SELECT rolname,oid FROM pg_roles WHERE rolname=ANY(%s)", (list(RESERVED),)
                )
            )
            == execution_oids
        )
        self.migrate("20260926_0006")
        self._record_successful_migration_roles(accepted=True)
        assert self._execution_definitions() == before_definitions
        self.execution_definitions = before_definitions
        self.execution_acl = before_acl
        self.accepted_round_trip_verified = True

    def _execution_definitions(self):
        # New bridges/keys are excluded explicitly; every old function's exact
        # body/owner/config and old table owner/RLS/columns remain compared.
        return (
            self.rows(
                "SELECT p.oid,p.proowner,p.proconfig,pg_get_functiondef(p.oid) "
                "FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
                "WHERE n.nspname='scanipy_execution' AND p.proname NOT IN "
                "('lock_accepted_capture_context_v1','lock_accepted_detector_context_v1') "
                "ORDER BY p.oid"
            ),
            self.rows(
                "SELECT c.oid,c.relowner,c.relrowsecurity,c.relforcerowsecurity,"
                "a.attnum,a.attname,a.atttypid,a.attnotnull FROM pg_class c "
                "JOIN pg_namespace n ON n.oid=c.relnamespace "
                "JOIN pg_attribute a ON a.attrelid=c.oid "
                "WHERE n.nspname='scanipy_execution' AND c.relkind='r' AND a.attnum>0 "
                "ORDER BY c.oid,a.attnum"
            ),
        )

    def _execution_acl(self):
        return (
            self.rows("SELECT nspacl::text FROM pg_namespace WHERE nspname='scanipy_execution'"),
            self.rows(
                "SELECT p.oid,p.proacl::text FROM pg_proc p "
                "JOIN pg_namespace n ON n.oid=p.pronamespace "
                "WHERE n.nspname='scanipy_execution' AND p.proname NOT IN "
                "('lock_accepted_capture_context_v1','lock_accepted_detector_context_v1') "
                "ORDER BY p.oid"
            ),
            self.rows(
                "SELECT c.oid,c.relacl::text,a.attnum,a.attacl::text FROM pg_class c "
                "JOIN pg_namespace n ON n.oid=c.relnamespace "
                "JOIN pg_attribute a ON a.attrelid=c.oid "
                "WHERE n.nspname='scanipy_execution' AND c.relkind='r' ORDER BY c.oid,a.attnum"
            ),
        )

    def _legacy_acl(self):
        return (
            self.rows(
                "SELECT c.relname,c.relacl::text FROM pg_class c JOIN pg_namespace "
                "n ON n.oid=c.relnamespace WHERE n.nspname='public' AND "
                "c.relkind='r' ORDER BY c.relname"
            ),
            self.rows(
                "SELECT c.relname,a.attname,a.attacl::text FROM pg_attribute a "
                "JOIN pg_class c ON c.oid=a.attrelid JOIN pg_namespace n ON "
                "n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind='r' "
                "ORDER BY c.relname,a.attnum"
            ),
            self.rows(
                "SELECT defaclrole,defaclnamespace,defaclobjtype,defaclacl::text "
                "FROM pg_default_acl ORDER BY oid"
            ),
        )

    def _seed_legacy_history(self):
        # Controlled legacy bytes exercise byte preservation, not authentic
        # signatures or native analysis. This helper never consults any DSN.
        from tests.integration.test_fnd_specs import _seed_and_insert

        self.legacy_finding = str(uuid4())
        with self.admin() as connection, connection.cursor() as cursor:
            _seed_and_insert(cursor, {"id": self.legacy_finding})
            cursor.execute(
                """INSERT INTO provenance_records (
                id,record_type,org_id,codebase_id,commit_sha,scm_provider,scan_id,
                finding_id,snapshot_id,snapshot_digest,precondition_status,"S_version",
                env_digest,cpg_order_hash,fingerprint_class,slice_fingerprint,origin,
                determinism_partition,kms_key_arn,kms_key_version,signature,signature_alg,claim_label)
                SELECT id,'chain',org_id,codebase_id,commit_sha,'github',scan_id,id,snapshot_id,
                env_digest,precondition_status,"S_version",env_digest,cpg_order_hash,
                fingerprint_class,slice_fingerprint,origin,determinism_partition,
                'controlled-test-key','original-version',%s,'RSASSA_PSS_SHA_256','CONDITIONAL_THEOREM'
                FROM findings WHERE id=%s""",
                (b"original controlled signature bytes\x00\xff", self.legacy_finding),
            )
            connection.commit()

    def _legacy_history(self):
        return self.rows(
            "SELECT to_jsonb(f) FROM public.findings f WHERE id=%s", (self.legacy_finding,)
        ), self.rows(
            "SELECT to_jsonb(p) FROM public.provenance_records p WHERE id=%s",
            (self.legacy_finding,),
        )

    def _record_successful_migration_roles(self, *, accepted=False):
        # The successful atomic migration itself created/refused each reserved
        # name. Never call this after a failed or ambiguous migration result.
        names = ACCEPTED_RESERVED if accepted else RESERVED
        with self.admin(bootstrap=True) as connection, connection.cursor() as cursor:
            cursor.execute("SELECT rolname,oid FROM pg_roles WHERE rolname=ANY(%s)", (list(names),))
            created = dict(cursor.fetchall())
            if set(created) != set(names):
                raise AssertionError("successful migration role inventory changed")
            self.owned_roles.update(created)

    def _create_logins(self):
        created_roles = {}
        created_logins = {}
        with self.admin() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT current_setting('max_identifier_length')::integer")
                limit_row = cursor.fetchone()
                if (
                    type(limit_row) is not tuple
                    or len(limit_row) != 1
                    or type(limit_row[0]) is not int
                    or limit_row[0] <= 0
                ):
                    raise AssertionError("invalid server identifier limit")
                identifier_limit = limit_row[0]
                suffixes = (
                    "request",
                    "detector",
                    "identity",
                    "cleanup",
                    "read",
                    "legacy_triage",
                ) + (
                    (
                        "accepted_policy_admin",
                        "accepted_publisher",
                        "accepted_resolver",
                        "accepted_reader",
                    )
                    if self.profile == "accepted"
                    else ()
                )
                for suffix in suffixes:
                    prefix = "altest_" if suffix.startswith("accepted_") else "occurrence_"
                    name = prefix + suffix + "_" + uuid4().hex
                    if not name.isascii() or not 0 < len(name) <= identifier_limit:
                        raise AssertionError("test login exceeds server identifier limit")
                    # Generated per-test credential, never a committed secret.
                    password = uuid4().hex  # pragma: allowlist secret
                    cursor.execute(
                        sql.SQL(
                            "CREATE ROLE {} LOGIN PASSWORD %s NOSUPERUSER NOCREATEDB "
                            "NOCREATEROLE NOREPLICATION NOBYPASSRLS"
                        ).format(sql.Identifier(name)),
                        (password,),
                    )
                    cursor.execute(
                        "SELECT rolname::text,oid FROM pg_roles WHERE rolname::text=%s", (name,)
                    )
                    identity = cursor.fetchone()
                    if (
                        type(identity) is not tuple
                        or len(identity) != 2
                        or type(identity[0]) is not str
                        or identity[0] != name
                        or type(identity[1]) is not int
                        or identity[1] <= 0
                    ):
                        raise AssertionError(
                            "created login identity differs from exact requested name"
                        )
                    member = "scanipy_exec_" + suffix
                    if suffix == "legacy_triage":
                        member = "scanipy_triage"
                    elif suffix.startswith("accepted_"):
                        member = "scanipy_" + suffix
                    cursor.execute(
                        sql.SQL("GRANT {} TO {}").format(
                            sql.Identifier(member), sql.Identifier(name)
                        )
                    )
                    created_roles[name] = identity[1]
                    created_logins[suffix] = name, password
            connection.commit()
        self.owned_roles.update(created_roles)
        self.roles.update(created_logins)

    @contextmanager
    def connection(self, role):
        name, password = self.roles[role]
        connection = psycopg2.connect(**{**self.child, "user": name, "password": password})
        try:
            yield connection
        finally:
            connection.close()

    @contextmanager
    def repo(self, role, org: UUID):
        with occurrence_transaction(lambda: self.connection(role), org) as repository:
            yield repository

    def rows(self, query, parameters=()):
        with self.admin() as connection, connection.cursor() as cursor:
            cursor.execute(query, parameters)
            return cursor.fetchall()

    def scope(self):
        org, codebase = uuid4(), uuid4()
        with self.admin() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO public.orgs(id,name) VALUES(%s,%s)", (str(org), str(org))
                )
                cursor.execute(
                    (
                        "INSERT INTO "
                        "public.codebases(id,org_id,name,scm_provider,scm_repo_url) "
                        "VALUES(%s,%s,'controlled','github',%s)"
                    ),
                    (str(codebase), str(org), "controlled:" + str(codebase)),
                )
            connection.commit()
        return org, codebase

    def dispose(self):
        if self.database_identity is None:
            return
        with self.admin(bootstrap=True) as connection:
            connection.autocommit = True
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT oid,datdba FROM pg_database WHERE datname=%s", (self.database,)
                )
                if cursor.fetchone() != self.database_identity:
                    raise AssertionError("test database ownership/OID changed; refusing cleanup")
                cursor.execute(
                    "SELECT rolname,oid FROM pg_roles WHERE rolname=ANY(%s)",
                    (list(self.owned_roles),),
                )
                if dict(cursor.fetchall()) != self.owned_roles:
                    raise AssertionError("test role OIDs changed; refusing cleanup")
                # No FORCE: a leaked live connection fails visibly, not terminated.
                cursor.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(self.database)))
                for role in self.owned_roles:
                    cursor.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(role)))


@pytest.fixture(scope="session")
def occurrence_pg():
    url = os.environ.get("SCANIPY_OCCURRENCE_TEST_URL")
    if not url:
        if os.environ.get("SCANIPY_OCCURRENCE_TEST_REQUIRED") == "1":
            pytest.fail("required occurrence store database URL is missing")
        pytest.skip("explicit dedicated SCANIPY_OCCURRENCE_TEST_URL not provided")
    cluster = PrivatePostgres(url)
    try:
        cluster.setup()
        yield cluster
    finally:
        cluster.dispose()


@pytest.fixture(scope="session")
def accepted_ledger_pg():
    url = os.environ.get("SCANIPY_ACCEPTED_LEDGER_TEST_URL")
    if not url:
        if os.environ.get("SCANIPY_ACCEPTED_LEDGER_TEST_REQUIRED") == "1":
            pytest.fail("required accepted ledger database URL is missing")
        pytest.skip("explicit dedicated SCANIPY_ACCEPTED_LEDGER_TEST_URL not provided")
    cluster = PrivatePostgres(url, profile="accepted")
    try:
        cluster.setup()
        yield cluster
    finally:
        cluster.dispose()
