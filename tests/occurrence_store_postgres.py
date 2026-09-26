"""Dedicated-cluster harness; never discovers or changes the legacy test DSN.

Only the profile's separately explicit test URL opts in. Every migration targets a newly
created child database. Cleanup checks captured database/role OIDs and owner;
it never terminates sessions, uses CASCADE, or drops an unowned resource.
"""

from __future__ import annotations

import os
import stat
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path, PosixPath, PurePosixPath
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
ADMINISTRATION_URL = (
    "postgresql://a2_fixture_admin@:5432/a2_fixture_bootstrap?host=/run/scanipy-a2-postgres"
)
_ADMINISTRATION_ROUTES = {
    "owner": ("accepted_owner", "scanipy_accepted_owner", "altest_a2_owner_"),
    "policy_admin": ("accepted_policy_admin", "scanipy_accepted_policy_admin", None),
    "publisher": ("accepted_publisher", "scanipy_accepted_publisher", None),
    "admin_reader": ("accepted_admin_reader", "scanipy_accepted_reader", "altest_a2_admin_reader_"),
    "publisher_reader": (
        "accepted_publisher_reader",
        "scanipy_accepted_reader",
        "altest_a2_pub_reader_",
    ),
}
_ADMIN_OPTIONS = "-c statement_timeout=15000 -c lock_timeout=2000"
_DIRECTORY_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
_MIGRATION_BOOTSTRAP = """
import os, sys
assert sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode
assert sys.platform == 'linux' and os.getresuid() == (0, 0, 0) and os.getresgid() == (0, 0, 0)
assert len(sys.argv) == 5
root, dependencies, action, target = sys.argv[1:]
assert action in ('upgrade', 'downgrade')
assert target in ('20260925_0003', '20260925_0004', '20260925_0005',
                  '20260926_0006', '20260926_0007')
assert all(p.startswith('/') and '\\x00' not in p and len(p.encode()) <= 4096
           for p in (root, dependencies))
sys.path[:0] = [root, dependencies]
from alembic import command
from alembic.config import Config
config = Config(os.path.join(root, 'alembic.ini'))
config.set_main_option('script_location', os.path.join(root, 'db', 'migrations'))
config.set_main_option('prepend_sys_path', root)
{'upgrade': command.upgrade, 'downgrade': command.downgrade}[action](config, target)
"""
_ADMIN_LOGIN_PROOF = """SELECT r.rolname::text,r.oid,r.rolcanlogin,r.rolsuper,
r.rolinherit,r.rolcreaterole,r.rolcreatedb,r.rolreplication,r.rolbypassrls,
(r.rolpassword LIKE 'SCRAM-SHA-256$%%'),g.rolname::text,g.oid,a.grantor,
a.admin_option,a.inherit_option,a.set_option,
pg_has_role(r.oid,'scanipy_accepted_owner','MEMBER'),
pg_has_role(r.oid,'scanipy_accepted_policy_admin','MEMBER'),
pg_has_role(r.oid,'scanipy_accepted_publisher','MEMBER'),
pg_has_role(r.oid,'scanipy_accepted_reader','MEMBER'),
pg_has_role(r.oid,g.oid,'SET'),pg_has_role(r.oid,g.oid,'USAGE')
FROM pg_authid r LEFT JOIN pg_auth_members a ON a.member=r.oid
LEFT JOIN pg_roles g ON g.oid=a.roleid
WHERE r.oid=ANY(%s) ORDER BY r.rolname::text,g.rolname::text,a.grantor LIMIT 6"""


def _administration_path(value):
    if type(value) is not PosixPath:
        raise ValueError("administration requires exact absolute paths")
    try:
        raw = object.__getattribute__(value, "_raw_paths")
    except AttributeError:
        raw = object.__getattribute__(value, "_parts")
    if type(raw) is not list or not 1 <= len(raw) <= 128:
        raise ValueError("invalid administration path")
    parts = tuple(raw[:129])
    if len(parts) > 128 or any(type(part) is not str or len(part) > 4096 for part in parts):
        raise ValueError("invalid administration path")
    if sum(len(part.encode("utf-8")) for part in parts) > 4096:
        raise ValueError("invalid administration path")
    text = "/".join(parts).replace("//", "/", 1) if parts[0] == "/" else "/".join(parts)
    if (
        not text.startswith("/")
        or "\x00" in text
        or len(text.encode("utf-8")) > 4096
        or any(part in ("", ".", "..") for part in text.split("/")[1:])
    ):
        raise ValueError("invalid administration path")
    return PosixPath(text)


def _administration_errors(primary, failures):
    if primary is None and failures:
        primary = failures.pop(0)
    if primary is not None:
        prior = primary.__cause__ if primary.__cause__ is not None else primary.__context__
        evidence = ([prior] if prior is not None else []) + failures
        if failures:
            primary.__cause__ = BaseExceptionGroup("administration fixture cleanup", evidence)
            primary.__suppress_context__ = True
        raise primary


def _close_administration_slot(owned, index, *, descriptor=False):
    if owned[index] is not None:
        try:
            if descriptor:
                os.close(owned[index])
            else:
                owned[index].close()
        finally:
            owned[index] = None


@contextmanager
def _administration_cursor(connection):
    owned, primary, failures = [None], None, []
    try:
        owned[0] = connection.cursor()
        yield owned[0]
    except BaseException as error:
        primary = error
    finally:
        try:
            _close_administration_slot(owned, 0)
        except BaseException as error:
            failures.append(error)
    _administration_errors(primary, failures)


def _administration_directory(path, *, private=False, empty=False):
    owned, scan, primary, failures = [None, None], [None], None, []
    try:
        owned[0] = os.open("/", _DIRECTORY_FLAGS)
        for part in path.parts[1:]:
            owned[1] = os.open(part, _DIRECTORY_FLAGS, dir_fd=owned[0])
            _close_administration_slot(owned, 0, descriptor=True)
            owned[0], owned[1] = owned[1], None
        info = os.fstat(owned[0])
        mode = stat.S_IMODE(info.st_mode)
        if (
            not stat.S_ISDIR(info.st_mode)
            or info.st_uid != 0
            or (mode != 0o700 if private else bool(mode & 0o022))
        ):
            raise ValueError("unsafe administration directory")
        if empty:
            scan[0] = os.scandir(owned[0])
            if next(scan[0], None) is not None:
                raise ValueError("administration working directory is not empty")
    except BaseException as error:
        primary = error
    finally:
        for slots, index, descriptor in ((scan, 0, False), (owned, 1, True), (owned, 0, True)):
            try:
                _close_administration_slot(slots, index, descriptor=descriptor)
            except BaseException as error:
                failures.append(error)
    _administration_errors(primary, failures)


def _administration_rows(cursor, query, parameters=(), *, maximum, columns, budget=None):
    cursor.execute(query, parameters)
    rows = cursor.fetchmany(maximum + 1)
    if type(rows) is not list or len(rows) > maximum:
        raise AssertionError("administration catalog row bound")
    budget = [0] if budget is None else budget
    for row in rows:
        if type(row) is not tuple or len(row) != columns:
            raise AssertionError("administration catalog shape")
        for value in row:
            values = value if type(value) is list else [value]
            if len(values) > 4:
                raise AssertionError("administration catalog array bound")
            for item in values:
                if item is None or type(item) is bool:
                    budget[0] += 8
                elif type(item) is int and -(2**63) <= item < 2**63:
                    budget[0] += 24
                elif type(item) is str and len(item) <= 4096:
                    budget[0] += len(item.encode("utf-8")) + 8
                else:
                    raise AssertionError("administration catalog primitive")
                if budget[0] > 16384:
                    raise AssertionError("administration catalog byte bound")
    return rows


class PrivatePostgres:
    def __init__(
        self,
        url: str,
        *,
        profile: Literal["occurrence", "accepted"] = "occurrence",
        administration: bool = False,
        migration_cwd: Path | None = None,
        migration_site_packages: Path | None = None,
    ):
        if type(administration) is not bool:
            raise ValueError("invalid administration mode")
        if not administration and (
            migration_cwd is not None or migration_site_packages is not None
        ):
            raise ValueError("administration paths require explicit mode")
        if type(profile) is not str or profile not in ("occurrence", "accepted"):
            raise ValueError("unknown dedicated database profile")
        if administration and profile != "accepted":
            raise ValueError("invalid administration mode")
        self.administration = administration
        self.administration_routes = {}
        self.migration_evidence = []
        self._migration_calls = 0
        self._migration_failed = False
        self._administration_setup_complete = False
        if administration:
            self.migration_cwd = _administration_path(migration_cwd)
            self.migration_site_packages = _administration_path(migration_site_packages)
            if type(url) is not str or url != ADMINISTRATION_URL:
                raise ValueError("administration requires its exact peer bootstrap URL")
            self._administration_runtime()
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

    def _administration_runtime(self):
        if (
            sys.platform != "linux"
            or os.getresuid() != (0, 0, 0)
            or os.getresgid() != (0, 0, 0)
            or not sys.flags.isolated
            or not sys.flags.no_site
            or not sys.dont_write_bytecode
        ):
            raise ValueError("administration requires isolated root fixture runtime")
        forbidden = (
            "DATABASE_URL",
            "SCANIPY_DATABASE_URL",
            "SCANIPY_TEST_DATABASE_URL",
            "SCANIPY_ACCEPTED_LEDGER_TEST_URL",
            "SCANIPY_ACCEPTED_LEDGER_TEST_REQUIRED",
            "SCANIPY_OCCURRENCE_TEST_URL",
            "SCANIPY_OCCURRENCE_TEST_REQUIRED",
        )
        if any(key in os.environ for key in forbidden) or any(
            key.startswith(("PG", "AWS_")) for key in os.environ
        ):
            raise ValueError("ambient administration database/credential selectors are forbidden")
        self.migration_cwd = _administration_path(self.migration_cwd)
        self.migration_site_packages = _administration_path(self.migration_site_packages)
        if self.migration_cwd in (self.migration_site_packages, ROOT):
            raise ValueError("administration working directory must be separate")
        _administration_directory(self.migration_cwd, private=True, empty=True)
        _administration_directory(self.migration_site_packages)
        _administration_path(PosixPath(sys.executable))

    @contextmanager
    def _administration_admin(self, *, bootstrap=False):
        self._administration_runtime()
        owned, primary, failures = [None], None, []
        try:
            owned[0] = psycopg2.connect(
                **(self.base if bootstrap else self.child),
                connect_timeout=2,
                options=_ADMIN_OPTIONS,
                application_name="scanipy-a2-fixture-setup",
            )
            yield owned[0]
        except BaseException as error:
            primary = error
        finally:
            try:
                _close_administration_slot(owned, 0)
            except BaseException as error:
                failures.append(error)
        _administration_errors(primary, failures)

    def _check_administration_cluster(self):
        with self.admin(bootstrap=True) as connection, _administration_cursor(connection) as cursor:
            settings = _administration_rows(
                cursor,
                "SELECT current_setting('server_version_num')::integer,"
                "left(current_setting('listen_addresses'),64),"
                "left(current_setting('password_encryption'),64),"
                "session_user::text,current_user::text,r.rolcanlogin,r.rolsuper,"
                "left(current_setting('statement_timeout'),64),"
                "left(current_setting('lock_timeout'),64) "
                "FROM pg_roles r WHERE r.rolname::text=session_user::text",
                maximum=1,
                columns=9,
            )
            if (
                len(settings) != 1
                or type(settings[0][0]) is not int
                or not 160000 <= settings[0][0] < 170000
                or type(settings[0][5]) is not bool
                or type(settings[0][6]) is not bool
                or settings[0][1:7]
                != (
                    "",
                    "scram-sha-256",
                    "a2_fixture_admin",
                    "a2_fixture_admin",
                    True,
                    True,
                )
                or settings[0][7] not in ("15s", "15000ms")
                or settings[0][8] not in ("2s", "2000ms")
            ):
                raise AssertionError("administration bootstrap configuration differs")
            budget = [0]
            hba = _administration_rows(
                cursor,
                "SELECT left(type,64),"
                "CASE WHEN cardinality(database)=1 THEN ARRAY[left(database[1],64)] "
                "ELSE ARRAY['invalid-array'] END,"
                "CASE WHEN cardinality(user_name)=1 THEN ARRAY[left(user_name[1],64)] "
                "ELSE ARRAY['invalid-array'] END,left(address,64),left(netmask,64),"
                "left(auth_method,64),CASE WHEN options IS NULL THEN NULL "
                "WHEN cardinality(options)=1 THEN ARRAY[left(options[1],64)] "
                "ELSE ARRAY['invalid-array'] END,"
                "CASE WHEN error IS NULL THEN NULL ELSE 'invalid-rule' END "
                "FROM pg_hba_file_rules ORDER BY rule_number NULLS LAST,line_number LIMIT 5",
                maximum=4,
                columns=8,
                budget=budget,
            )
            ident = _administration_rows(
                cursor,
                "SELECT left(map_name,64),left(sys_name,64),left(pg_username,64),"
                "CASE WHEN error IS NULL THEN NULL ELSE 'invalid-map' END "
                "FROM pg_ident_file_mappings "
                "ORDER BY map_number NULLS LAST,line_number LIMIT 2",
                maximum=1,
                columns=4,
                budget=budget,
            )
            if hba != [
                (
                    "local",
                    ["all"],
                    ["a2_fixture_admin"],
                    None,
                    None,
                    "peer",
                    ["map=a2_root_setup"],
                    None,
                ),
                ("local", ["all"], ["all"], None, None, "scram-sha-256", None, None),
                ("host", ["all"], ["all"], "0.0.0.0", "0.0.0.0", "reject", None, None),
                ("host", ["all"], ["all"], "::", "::", "reject", None, None),
            ] or ident != [("a2_root_setup", "root", "a2_fixture_admin", None)]:
                raise AssertionError("administration peer/SCRAM files differ")
            # Catalog views describe current files, NOT the last loaded version.
            # A separately reviewed startup recipe and real auth controls remain required.

    def _migrate_administration(self, target_url, action, target, expect_success):
        from tools.worker.bounded_process import MemoryOutput, ProcessLimits, run_bounded_process

        self._administration_runtime()
        if self._migration_failed or self._migration_calls >= 11:
            raise AssertionError("administration migration is unavailable or exhausted")
        if (target == "20260926_0007" and self._migration_calls < 10) or (
            self._migration_calls == 10
            and (
                not self._administration_setup_complete
                or action != "upgrade"
                or target != "20260926_0007"
                or expect_success is not True
            )
        ):
            raise AssertionError("administration migration is unavailable or exhausted")
        self._migration_calls += 1
        self._migration_failed = True
        argv = (
            sys.executable,
            "-I",
            "-S",
            "-B",
            "-c",
            _MIGRATION_BOOTSTRAP,
            str(ROOT),
            str(self.migration_site_packages),
            action,
            target,
        )
        environment = {
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "PGPASSFILE": "/dev/null",
            "PGCONNECT_TIMEOUT": "2",
            "PGOPTIONS": _ADMIN_OPTIONS,
            "SCANIPY_DATABASE_URL": target_url.render_as_string(hide_password=False).replace(
                "%", "%%"
            ),
        }
        try:
            outcome = run_bounded_process(
                argv,
                stdin=None,
                env=environment,
                cwd=self.migration_cwd,
                limits=ProcessLimits(0, 1048576, 1048576, 1048576, 60000, 5000),
            )
        except BaseException as error:
            # Retain actual owner's partial outcome, including beneath its exact interruption.
            from tools.worker.bounded_process import ProcessTransportError

            partial = error if type(error) is ProcessTransportError else error.__cause__
            if type(partial) is ProcessTransportError:
                self.migration_evidence.append(partial.outcome)
            raise
        self.migration_evidence.append(outcome)
        outputs = (outcome.stdout, outcome.stderr)
        if (
            outcome.reason != "exited"
            or outcome.cleanup != "completed"
            or type(outcome.returncode) is not int
            or outcome.stdin_sent_bytes != 0
            or any(
                type(output) is not MemoryOutput
                or not output.evidence.eof
                or output.evidence.truncated
                or output.evidence.observed_bytes != len(output.data)
                or output.evidence.retained_bytes != len(output.data)
                for output in outputs
            )
            or sum(len(output.data) for output in outputs) > 1048576
        ):
            raise AssertionError("administration migration transport incomplete")
        expected = 0 if expect_success else 1
        if outcome.returncode != expected:
            raise AssertionError("administration migration exit differs")
        result = subprocess.CompletedProcess(
            argv,
            outcome.returncode,
            outcome.stdout.data.decode("utf-8", errors="replace"),
            outcome.stderr.data.decode("utf-8", errors="replace"),
        )
        self._migration_failed = False
        return result

    def _check_administration_logins(self, cursor, created_roles, created_logins):
        expected = {}
        for route, (key, group, _prefix) in _ADMINISTRATION_ROUTES.items():
            name = created_logins[key][0]
            expected[name] = (created_roles[name], group, route != "owner")
        rows = _administration_rows(
            cursor,
            _ADMIN_LOGIN_PROOF,
            ([value[0] for value in expected.values()],),
            maximum=5,
            columns=22,
        )
        if len(rows) != 5 or len({row[0] for row in rows}) != 5:
            raise AssertionError("administration login inventory differs")
        groups = (*ACCEPTED_RESERVED[:3], ACCEPTED_RESERVED[4])
        for row in rows:
            if row[0] not in expected:
                raise AssertionError("administration login identity differs")
            oid, group, inherit = expected[row[0]]
            if (
                type(row[1]) is not int
                or row[1] != oid
                or any(type(row[index]) is not bool for index in (*range(2, 10), *range(13, 22)))
                or row[2:10] != (True, False, inherit, False, False, False, False, True)
                or row[10] != group
                or type(row[11]) is not int
                or row[11] <= 0
                or type(row[12]) is not int
                or row[12] <= 0
                or row[13:16] != (False, inherit, True)
                or row[16:20] != tuple(candidate == group for candidate in groups)
                or row[20:22] != (True, inherit)
            ):
                raise AssertionError("administration login privilege proof differs")

    def _create_administration_logins(self):
        created_roles, created_logins = {}, {}
        selected = {
            row[0]: (route, row[1], row[2]) for route, row in _ADMINISTRATION_ROUTES.items()
        }
        suffixes = (
            "request",
            "detector",
            "identity",
            "cleanup",
            "read",
            "legacy_triage",
            "accepted_policy_admin",
            "accepted_publisher",
            "accepted_resolver",
            "accepted_reader",
            "accepted_owner",
            "accepted_admin_reader",
            "accepted_publisher_reader",
        )
        with self.admin() as connection:
            with _administration_cursor(connection) as cursor:
                cursor.execute("SELECT current_setting('max_identifier_length')::integer")
                limit = cursor.fetchone()
                if (
                    type(limit) is not tuple
                    or len(limit) != 1
                    or type(limit[0]) is not int
                    or limit[0] <= 0
                ):
                    raise AssertionError("invalid server identifier limit")
                cursor.execute(
                    "SET LOCAL password_encryption='scram-sha-256'"  # pragma: allowlist secret
                )
                for suffix in suffixes:
                    route, group, fixed_prefix = selected.get(suffix, (None, None, None))
                    prefix = fixed_prefix or (
                        ("altest_" if suffix.startswith("accepted_") else "occurrence_")
                        + suffix
                        + "_"
                    )
                    token = uuid4().hex
                    if (
                        type(token) is not str
                        or len(token) != 32
                        or any(ch not in "0123456789abcdef" for ch in token)
                    ):
                        raise AssertionError("invalid administration login UUID")
                    name = prefix + token
                    if not name.isascii() or not 0 < len(name) <= min(63, limit[0]):
                        raise AssertionError("test login exceeds server identifier limit")
                    password = uuid4().hex  # pragma: allowlist secret
                    if (
                        type(password) is not str
                        or len(password) != 32
                        or any(ch not in "0123456789abcdef" for ch in password)
                    ):
                        raise AssertionError("invalid administration fixture credential")
                    inherit = (" NOINHERIT" if route == "owner" else " INHERIT") if route else ""
                    cursor.execute(
                        sql.SQL(
                            "CREATE ROLE {} LOGIN PASSWORD %s NOSUPERUSER NOCREATEDB "
                            "NOCREATEROLE NOREPLICATION NOBYPASSRLS" + inherit
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
                    if route:
                        options = (
                            "ADMIN FALSE",
                            "INHERIT FALSE" if route == "owner" else "INHERIT TRUE",
                            "SET TRUE",
                        )
                    else:
                        group = (
                            "scanipy_triage"
                            if suffix == "legacy_triage"
                            else (
                                "scanipy_" + suffix
                                if suffix.startswith("accepted_")
                                else "scanipy_exec_" + suffix
                            )
                        )
                        options = (None,)
                    for option in options:
                        cursor.execute(
                            sql.SQL(
                                "GRANT {} TO {}" + (" WITH " + option if option else "")
                            ).format(
                                sql.Identifier(group),
                                sql.Identifier(name),
                            )
                        )
                    created_roles[name] = identity[1]
                    created_logins[suffix] = name, password
                self._check_administration_logins(cursor, created_roles, created_logins)
            connection.commit()
        self.owned_roles.update(created_roles)
        self.roles.update(created_logins)
        self.administration_routes = {
            route: row[0] for route, row in _ADMINISTRATION_ROUTES.items()
        }

    @contextmanager
    def admin(self, *, bootstrap=False):
        if self.administration:
            with self._administration_admin(bootstrap=bootstrap) as connection:
                yield connection
            return
        connection = psycopg2.connect(**(self.base if bootstrap else self.child))
        try:
            yield connection
        finally:
            connection.close()

    def migrate(self, target=None, *, expect_success=True, action="upgrade"):
        if self.administration and (type(action) is not str or type(expect_success) is not bool):
            raise ValueError("invalid administration migration primitives")
        if action not in ("upgrade", "downgrade"):
            raise ValueError("unsupported migration test action")
        target = self.migration_target if target is None else target
        permitted = ("20260925_0003", "20260925_0004", "20260925_0005") + (
            ("20260926_0006", "20260926_0007") if self.profile == "accepted" else ()
        )
        if type(target) is not str or target not in permitted:
            raise ValueError("unsupported dedicated migration target")
        target_url = self.url.set(drivername="postgresql+psycopg2", database=self.database)
        _, resolved = PGDialect_psycopg2().create_connect_args(target_url)
        for field in ("host", "port", "dbname", "user"):
            if str(resolved.get(field)) != str(self.child[field]):
                raise AssertionError("migration driver target differs from owned child")
        if self.administration:
            return self._migrate_administration(target_url, action, target, expect_success)
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
        if self.administration:
            self._check_administration_cluster()
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
        if self.administration:
            if self._migration_calls != 10 or self._migration_failed:
                raise AssertionError("administration setup migration schedule is incomplete")
            self._administration_setup_complete = True

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
        if self.administration:
            return self._create_administration_logins()
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
