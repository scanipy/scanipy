"""Transaction ambiguity, bounded inputs, and fixture target/ownership falsifiers."""

import hashlib
from contextlib import contextmanager
from unittest.mock import Mock
from uuid import uuid4

import pytest
from psycopg2 import sql
from sqlalchemy.dialects.postgresql.psycopg2 import PGDialect_psycopg2

from services.scan.occurrence_store.codec import EnvelopeError
from services.scan.occurrence_store.models import Fence
from services.scan.occurrence_store.repository import OccurrenceRepository, occurrence_transaction
from tests.occurrence_store_fixtures import batch, capture_seal, envelope, request_input
from tests.occurrence_store_postgres import RESERVED, PrivatePostgres

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "query",
    [
        "dbname=foreign",
        "database=foreign",
        "service=foreign",
        "servicefile=/elsewhere",
        "options=-csearch_path=public",
        "hostaddr=192.0.2.1",
    ],
)
def test_database_query_cannot_redirect_migrations(query):
    with pytest.raises(ValueError, match="routing"):
        PrivatePostgres("postgresql://controlled@localhost/occurrence_bootstrap?" + query)


@pytest.mark.parametrize(
    "host",
    [
        "/private/socket,192.0.2.1",
        "/private/socket%2C192.0.2.1",
        "/private/socket,",
        "/private//socket",
        "/private/../socket",
    ],
)
def test_socket_host_cannot_enable_remote_fallback_or_ambiguous_paths(host):
    with pytest.raises(ValueError):
        PrivatePostgres("postgresql://controlled@/occurrence_bootstrap?host=" + host)


@pytest.mark.parametrize(
    "key",
    [
        "PGSERVICE",
        "PGSERVICEFILE",
        "PGHOSTADDR",
        "PGOPTIONS",
        "PGHOST",
        "PGPORT",
        "PGDATABASE",
        "PGUSER",
    ],
)
def test_ambient_libpq_routing_is_rejected(monkeypatch, key):
    monkeypatch.setenv(key, "controlled-adversarial-setting")
    with pytest.raises(ValueError, match="ambient"):
        PrivatePostgres("postgresql://controlled@localhost/occurrence_bootstrap")


def test_migration_url_targets_exact_created_child_without_query_override():
    cluster = PrivatePostgres("postgresql://controlled@/occurrence_bootstrap?host=/private/socket")
    target = cluster.url.set(database=cluster.database)
    _, arguments = PGDialect_psycopg2().create_connect_args(target)
    assert arguments["dbname"] == cluster.child["dbname"] == cluster.database
    assert arguments["host"] == cluster.child["host"] == "/private/socket"


def test_failed_migration_does_not_adopt_or_dispose_racing_reserved_role(monkeypatch):
    cluster = PrivatePostgres("postgresql://controlled@localhost/occurrence_bootstrap")
    foreign = RESERVED[0]
    roles = {}
    deleted = []

    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def execute(self, query, parameters=()):
            self.query, self.parameters = query, parameters
            if isinstance(query, sql.Composed):
                text = repr(query)
                identifiers = [
                    part.string for part in query.seq if isinstance(part, sql.Identifier)
                ]
                if "CREATE ROLE" in text:
                    roles[identifiers[0]] = 99
                elif "DROP ROLE" in text:
                    deleted.append(identifiers[0])
                    roles.pop(identifiers[0])

        def fetchall(self):
            if "SELECT rolname FROM" in self.query:
                return [(name,) for name in roles if name in self.parameters[0]]
            return [(name, oid) for name, oid in roles.items() if name in self.parameters[0]]

        def fetchone(self):
            if "pg_database" in self.query:
                return (123, 456)
            if self.parameters[0] not in roles:
                return None
            return (roles[self.parameters[0]],)

    class Connection:
        autocommit = False

        def cursor(self):
            return Cursor()

        def commit(self):
            pass

    @contextmanager
    def admin(**_):
        yield Connection()

    def migrate(*_, **__):
        roles[foreign] = 777  # competitor arrives AFTER reserved-name precheck
        raise AssertionError("reserved execution role already exists")

    monkeypatch.setattr(cluster, "admin", admin)
    monkeypatch.setattr(cluster, "migrate", migrate)
    with pytest.raises(AssertionError, match="already exists"):
        cluster.setup()
    assert foreign not in cluster.owned_roles
    cluster.dispose()
    assert roles[foreign] == 777 and foreign not in deleted


@pytest.mark.parametrize("commit_error", [False, True])
def test_transaction_acknowledgement_waits_for_commit_and_discards_connection(commit_error):
    connection = Mock()
    connection.autocommit = False
    connection.cursor.return_value.fetchone.return_value = None
    if commit_error:
        connection.commit.side_effect = RuntimeError("ambiguous commit")

    @contextmanager
    def factory():
        try:
            yield connection
        finally:
            connection.close()

    acknowledged = False
    try:
        with occurrence_transaction(factory, uuid4()):
            pass
        acknowledged = True
    except RuntimeError as exc:
        assert str(exc) == "ambiguous commit"
    assert acknowledged is not commit_error
    connection.commit.assert_called_once()
    connection.close.assert_called_once()
    statements = [call.args[0] for call in connection.cursor.return_value.execute.call_args_list]
    assert any("statement_timeout" in query and "lock_timeout" in query for query in statements)


def test_transaction_body_failure_rolls_back_and_closes():
    connection = Mock()
    connection.autocommit = False

    @contextmanager
    def factory():
        try:
            yield connection
        finally:
            connection.close()

    with pytest.raises(RuntimeError, match="body"), occurrence_transaction(factory, uuid4()):
        raise RuntimeError("body")
    connection.rollback.assert_called_once()
    connection.commit.assert_not_called()
    connection.close.assert_called_once()


@pytest.mark.parametrize("change", ["prefix", "count", "unknown_count", "full_hash", "oversized"])
def test_invalid_failed_prefix_is_rejected_before_rpc(change):
    connection = Mock()
    connection.autocommit = False
    repo = OccurrenceRepository(connection, uuid4())
    prefix = b"actual\x00\xff"
    fields = {
        "code": "controlled",
        "message": "observed failure",
        "prefix_sha256": hashlib.sha256(prefix).hexdigest(),
        "observed_byte_count": len(prefix),
        "truncated": False,
        "observed_full_sha256": hashlib.sha256(prefix).hexdigest(),
    }
    if change == "prefix":
        fields["prefix_sha256"] = "a" * 64
    elif change == "count":
        fields["observed_byte_count"] = 0
    elif change == "unknown_count":
        fields["observed_byte_count"] = None
    elif change == "full_hash":
        fields["observed_full_sha256"] = "a" * 64
    else:
        prefix = b"x" * 65537
    previous = connection.cursor.return_value.execute.call_count
    with pytest.raises(EnvelopeError):
        repo.fail_detector_run(
            Fence(uuid4(), uuid4(), "capture_detection", 1, 0),
            uuid4(),
            envelope("run-failure", **fields),
            prefix,
        )
    assert connection.cursor.return_value.execute.call_count == previous


@pytest.mark.parametrize("target", ["request", "capture", "batch", "fence"])
def test_repository_rejects_subclass_validation_overrides_before_rpc(target):
    org = uuid4()
    requested = request_input(org, uuid4())
    fence = Fence(uuid4(), uuid4(), "capture_detection", 1, 0)
    values = {
        "request": requested,
        "capture": capture_seal(uuid4(), requested),
        "batch": batch(uuid4()),
        "fence": fence,
    }
    original = values[target]

    def poison(_):
        raise AssertionError("subclass validation override must not be called")

    subclass = type("UntrustedModel", (type(original),), {"__post_init__": poison})
    untrusted = object.__new__(subclass)
    for key, value in vars(original).items():
        object.__setattr__(untrusted, key, value)
    connection = Mock()
    connection.autocommit = False
    repo = OccurrenceRepository(connection, org)
    previous = connection.cursor.return_value.execute.call_count
    operations = {
        "request": lambda: repo.create_request(untrusted),
        "capture": lambda: repo.register_capture_and_seal(fence, untrusted),
        "batch": lambda: repo.retain_detection_batch(fence, uuid4(), untrusted),
        "fence": lambda: repo.renew(untrusted),
    }
    with pytest.raises(EnvelopeError, match="exact"):
        operations[target]()
    assert connection.cursor.return_value.execute.call_count == previous


@pytest.mark.parametrize("target", ["detectors", "rules", "observations"])
def test_repository_revalidates_mutable_alias_injection_before_rpc(target):
    org = uuid4()
    fence = Fence(uuid4(), uuid4(), "capture_detection", 1, 0)
    value = (
        batch(uuid4())
        if target == "observations"
        else capture_seal(uuid4(), request_input(org, uuid4()))
    )
    # Frozen annotations are not the SQL trust boundary. Simulate a caller
    # bypassing normal construction after initial successful validation.
    object.__setattr__(value, target, list(getattr(value, target)))
    connection = Mock()
    connection.autocommit = False
    repo = OccurrenceRepository(connection, org)
    previous = connection.cursor.return_value.execute.call_count
    with pytest.raises(EnvelopeError, match="exact tuple"):
        if target == "observations":
            repo.retain_detection_batch(fence, uuid4(), value)
        else:
            repo.register_capture_and_seal(fence, value)
    assert connection.cursor.return_value.execute.call_count == previous
