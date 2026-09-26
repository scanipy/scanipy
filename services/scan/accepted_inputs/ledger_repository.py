"""Bounded function-only AL-03 database adapter; not an authority provider.

The installed dispatcher owns the authenticated namespace/capability and a fresh
transaction. Neither this adapter nor an object returned by it supplies installed
trust, signature verification, an ExecutionAuthorityReader, or launch permission.
All application evidence retains the real accepted-input owner's types/codecs.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, TypeVar, cast
from uuid import UUID

from analysis.cpg_ingest.typed_observed import FrozenArray
from analysis.ifds.bound_rules import BoundRuleError, ScalarLimits, decode_bound_rule
from services.scan.occurrence_store.codec import EnvelopeError, decode_envelope
from services.scan.sql_adapters import Connection

from . import codec as c
from . import ledger_commands as lc
from . import models as m
from . import schemas as s

if TYPE_CHECKING:
    from services.scan.sql_adapters import ConnectionFactory

STATEMENT_TIMEOUT_MS = 15000
LOCK_TIMEOUT_MS = 2000
MAX_HASH_CALLS = 100000
MAX_HASH_BYTES = 134217728

_MUTATIONS = {
    "install-policy": ("install_policy_v1", s.POLICY),
    "record-admission": ("record_admission_v1", s.ADMISSION),
    "publish-builtin": ("publish_builtin_bundle_v1", s.PUBLICATION),
    "create-bound-request": ("create_bound_request_v1", s.SEALED),
    "seal-bound-capture": ("seal_bound_capture_v1", s.SEAL_AUTHORIZATION),
    "authorize-detector": ("authorize_detector_run_v1", s.EXECUTION),
    "renew-detector": ("renew_authorized_execution_v1", s.EXECUTION),
}
_KINDS = {
    "policy": s.POLICY,
    "admission": s.ADMISSION,
    "approval": s.APPROVAL,
    "seal-authorization": s.SEAL_AUTHORIZATION,
    "execution-authorization": s.EXECUTION,
    "execution-denial": s.DENIAL,
}
_CALLS = {
    **{name: (2, 2, False) for name, _schema in _MUTATIONS.values()},
    "initialize_registry_namespace_v1": (2, 2, False),
    "read_publication_receipt_v1": (3, 1, False),
    "read_exact_bundle_v1": (3, 3, False),
    "read_authority_event_v1": (4, 2, False),
    "read_request_binding_v1": (4, 1, False),
    "read_execution_authority_v1": (3, 3, False),
    "recheck_execution_authority_v1": (6, 1, True),
}
_SQL_CODES = frozenset(
    (
        "invalid-input",
        "ledger-mismatch",
        "content-mismatch",
        "scope-mismatch",
        "fence-stale",
        "policy-stale",
        "checkpoint-denied",
        "grant-denied",
        "policy-expired",
    )
)
T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class LedgerResult:
    """Transport result inside a caller transaction, not a durable receipt."""

    record_bytes: bytes
    replayed: bool


class _Work:
    def __init__(self, calls: int = 0, size: int = 0) -> None:
        self.calls = self.size = 0
        self.reserve(calls, size)

    def reserve(self, calls: int, size: int) -> None:
        s.require(type(calls) is int and type(size) is int)
        s.require(0 <= calls <= MAX_HASH_CALLS - self.calls)
        s.require(0 <= size <= MAX_HASH_BYTES - self.size)
        self.calls += calls
        self.size += size

    def raw(self, data: bytes) -> str:
        self.reserve(1, len(data))
        return c.raw_digest(data)

    def domain(self, schema: str, data: bytes) -> str:
        self.reserve(1, len(schema) + 1 + len(data))
        return c.domain_digest(schema, data)

    def frame(self, data: bytes, schema: str, *, stored: bool) -> c.ParsedFrame:
        self.reserve(len(s.FRAME_ROLES[schema]), len(data))
        with _stored_validation() if stored else nullcontext():
            return c.decode_frame(data, schema)

    def occurrence(self, name: str, data: bytes) -> dict[str, Any]:
        # Reuse the unchanged occurrence domain, including its wider string and
        # value bounds. One actual owner hash, including its complete prefix.
        s.require(name in ("request", "seal"))
        self.reserve(1, len("scanipy-execution/" + name + "/1\n") + len(data))
        try:
            return decode_envelope(name, data)
        except EnvelopeError as error:
            raise s.VerificationError("invalid-input") from error


@contextmanager
def _stored_validation() -> Iterator[None]:
    """Malformed stored content is not mislabeled as a caller-schema failure."""
    try:
        yield
    except s.VerificationError as error:
        if error.code in ("invalid-input", "unsupported-schema"):
            raise s.VerificationError("content-mismatch") from error
        raise


def _document(data: bytes, schema: str) -> dict[str, Any]:
    with _stored_validation():
        return c.decode_document(data, schema)


def _uuid(value: object) -> UUID:
    s.require(type(value) is UUID)
    try:
        integer = object.__getattribute__(value, "int")
    except AttributeError as error:
        raise s.VerificationError() from error
    s.require(type(integer) is int and 0 <= integer < 2**128)
    return UUID(int=integer)


def _record(value: object, kind: type[T], rules: dict[str, Any]) -> tuple[T, dict[str, Any]]:
    """Snapshot original slots BEFORE formatting/normalization or owner methods."""
    s.require(type(value) is kind)
    members: dict[str, Any] = {}
    for name, rule in rules.items():
        try:
            item = object.__getattribute__(value, name)
        except AttributeError as error:
            raise s.VerificationError() from error
        actual = rule[1] if type(rule) is tuple and rule[0] == "nullable" else rule
        if item is None:
            s.shape(item, rule)
            members[name] = None
        elif actual == "uuid":
            members[name] = str(_uuid(item))
        elif type(actual) is dict:
            s.require(kind is m.LedgerExpectation and name == "binding")
            _, members[name] = _record(item, m.ExecutionBinding, s.EXECUTION_BINDING)
        else:
            s.shape(item, rule)
            members[name] = item
    fresh = c.decode_record(members, kind, rules)
    return fresh, members


def _binary_size(value: object) -> int:
    if type(value) is bytes:
        return len(value)
    # psycopg2's bytea adapter returns a built-in memoryview. Check storage
    # properties and the aggregate BEFORE copying; no arbitrary __bytes__.
    s.require(type(value) is memoryview, "content-mismatch")
    assert isinstance(value, memoryview)
    try:
        s.require(
            value.ndim == 1 and value.itemsize == 1 and value.c_contiguous, "content-mismatch"
        )
        s.require(value.format in ("B", "b", "c"), "content-mismatch")
        return value.nbytes
    except ValueError as error:
        raise s.VerificationError("content-mismatch") from error


def _bytes(value: object, maximum: int, *, empty: bool = False) -> bytes:
    size = _binary_size(value)
    s.require((empty or size > 0) and size <= maximum, "content-mismatch")
    if type(value) is bytes:
        return value
    assert type(value) is memoryview
    return memoryview.tobytes(value)


def _array(value: object, maximum: int, *, empty: bool = False) -> tuple[object, ...]:
    s.require(type(value) in (list, tuple), "content-mismatch")
    sequence = cast("list[object] | tuple[object, ...]", value)
    s.require((empty or len(sequence) > 0) and len(sequence) <= maximum, "content-mismatch")
    # The bounded built-in slice detaches a driver list before any conversion.
    private = tuple(sequence[: maximum + 1])
    s.require((empty or len(private) > 0) and len(private) <= maximum, "content-mismatch")
    return private


def _scope(value: dict[str, Any], org: UUID | None) -> None:
    expected = None if org is None else str(org)
    s.require(value["org_id"] == expected, "scope-mismatch")
    if "scope" in value:
        s.require(value["scope"] == ("global" if org is None else "customer"), "scope-mismatch")


def _link_publication(frame: c.ParsedFrame, receipt: dict[str, Any], work: _Work) -> None:
    approval = frame.document("approval-statement")
    for name in (
        "registry_id",
        "scope",
        "org_id",
        "bundle_id",
        "publication_key",
        "accepted_content_digest",
        "evidence_inventory_digest",
    ):
        s.require(receipt[name] == approval[name], "ledger-mismatch")
    s.require(receipt["approval_event_id"] == approval["event_id"], "ledger-mismatch")
    s.require(receipt["publisher_actor_id"] == approval["issuer_actor_id"], "ledger-mismatch")
    s.require(
        receipt["approval_statement_digest"]
        == work.domain(s.APPROVAL, frame.object("approval-statement")),
        "ledger-mismatch",
    )
    s.require(
        receipt["approval_signature_sha256"] == work.raw(frame.object("approval-signature")),
        "ledger-mismatch",
    )


def _bundle(
    spec: bytes,
    detectors: tuple[bytes, ...],
    rules: tuple[bytes, ...],
    expected: dict[str, Any],
    work: _Work,
) -> m.AcceptedBundleBytes:
    # Exact reviewed owner schedule. Every helper is preceded by its entire
    # malformed-path reservation; no per-language whole-bundle recomputation.
    work.reserve(s.MAX_VALUES, len(spec))
    with _stored_validation():
        manifest, models = c.decode_spec(spec)
    for name in ("registry_id", "scope", "org_id", "bundle_id", "S_version"):
        s.require(manifest[name] == expected[name], "content-mismatch")
    model_bytes = sum(map(len, models))
    work.reserve(len(models), model_bytes)
    with _stored_validation():
        bundle = m.AcceptedBundleBytes(spec, detectors, rules)
    member_bytes = sum(map(len, detectors)) + sum(map(len, rules))
    work.reserve(
        3 * len(models) + 3 + 2 * len(detectors) + 3 * len(rules),
        3 * model_bytes
        + len(spec)
        + 2 * member_bytes
        + 2 * (s.MAX_CONTENT + len("scanipy-execution/accepted-content/1\n"))
        + len(rules) * (s.MAX_OBJECT + len(s.SEMANTIC_BINDING) + 1),
    )
    with _stored_validation():
        members = c.qualified_members(bundle)
    for key, detector_raw, rule_raw, model_raw in members:
        s.require(
            key.accepted_content_digest == expected["accepted_content_digest"], "content-mismatch"
        )
        with _stored_validation():
            detector = c.decode_document(detector_raw, s.DETECTOR, canonical=False)
        for language in detector["languages"]:
            work.reserve(2, len(rule_raw) + len(model_raw))
            try:
                bound = decode_bound_rule(
                    rule_raw, model_raw, key=key, language=language, limits=ScalarLimits()
                )
            except BoundRuleError as error:
                raise s.VerificationError("content-mismatch") from error
            rule = bound.rule_document
            s.require(
                (
                    rule.get("class_id"),
                    rule.get("engine"),
                    rule.get("spec_id"),
                    rule.get("model_artifact_digest"),
                    rule.get("projection_profile"),
                )
                == (
                    detector["class_id"],
                    detector["engine"],
                    key.rule_id,
                    key.model_raw_sha256,
                    s.PROJECTION,
                ),
                "content-mismatch",
            )
            languages = rule.get("languages")
            s.require(type(languages) is FrozenArray, "content-mismatch")
            assert type(languages) is FrozenArray
            s.require(languages.values == tuple(detector["languages"]), "content-mismatch")
    return bundle


def _driver_code(error: BaseException) -> str | None:
    """Only actual driver-defined exception/diagnostic descriptors are inspected."""
    try:
        import psycopg2
        from psycopg2 import errors
    except ImportError:
        return None
    classes = tuple(
        value
        for value in vars(errors).values()
        if type(value) is type and issubclass(value, psycopg2.Error)
    )
    if type(error) not in classes:
        return None
    code = psycopg2.Error.__dict__["pgcode"].__get__(error, type(error))
    if code not in ("P0001", "42501"):
        return None
    diagnostic = psycopg2.Error.__dict__["diag"].__get__(error, type(error))
    message = diagnostic.message_primary
    if type(message) is str and message in _SQL_CODES:
        if (code == "42501") == (message == "scope-mismatch"):
            return message
    return None


def _prior_error(primary: BaseException) -> BaseException | None:
    cause = BaseException.__dict__["__cause__"].__get__(primary, BaseException)
    context = BaseException.__dict__["__context__"].__get__(primary, BaseException)
    return cast("BaseException | None", cause if cause is not None else context)


def _cleanup_cause(
    primary: BaseException, cleanup: BaseException, prior: BaseException | None
) -> BaseException:
    items = [cleanup]
    if prior is not None and prior is not primary and prior is not cleanup:
        items.insert(0, prior)
    return BaseExceptionGroup("private ledger cleanup failures", items)


class AcceptedLedgerRepository:
    """One fixed public operation per caller transaction; no independent commit."""

    def __init__(self, connection: Connection, namespace_id: UUID, org_id: UUID | None) -> None:
        self.namespace_id = _uuid(namespace_id)
        self.org_id = None if org_id is None else _uuid(org_id)
        s.require(getattr(connection, "autocommit", False) is False)
        self.connection = connection
        self._used = False
        with self._cursor() as cursor:
            cursor.execute(
                "SELECT set_config('scanipy.accepted_namespace_id',%s,true),"
                "set_config('app.org_id',%s,true),set_config('statement_timeout',%s,true),"
                "set_config('lock_timeout',%s,true)",
                (
                    str(self.namespace_id),
                    "" if self.org_id is None else str(self.org_id),
                    str(STATEMENT_TIMEOUT_MS),
                    str(LOCK_TIMEOUT_MS),
                ),
            )

    @contextmanager
    def _cursor(self) -> Iterator[Any]:
        cursor = self.connection.cursor()
        try:
            yield cursor
        except BaseException as primary:
            prior = _prior_error(primary)
            try:
                cursor.close()
            except BaseException as cleanup:
                raise primary from _cleanup_cause(primary, cleanup, prior)
            raise
        else:
            cursor.close()

    def _call(
        self, function: str, args: tuple[object, ...], columns: int, *, void: bool = False
    ) -> tuple[object, ...]:
        s.require(not self._used)
        s.require(type(function) is str and function in _CALLS)
        s.require(_CALLS[function] == (len(args), columns, void))
        self._used = True
        # Names are private fixed literals, never requested SQL or role selectors.
        placeholders = ",".join("%s" for _ in args)
        projection = "NULL::text" if void else "*"
        try:
            with self._cursor() as cursor:
                cursor.execute(
                    f"SELECT {projection} FROM scanipy_accepted_inputs.{function}({placeholders})",  # noqa: S608 -- closed private _CALLS only
                    args,
                )
                row = cursor.fetchone()
                s.require(type(row) is tuple and len(row) == columns, "content-mismatch")
                s.require(cursor.fetchone() is None, "content-mismatch")
                return cast(tuple[object, ...], row)
        except Exception as error:
            code = _driver_code(error)
            if code is not None:
                raise s.VerificationError(code) from error
            raise

    def _mutate(
        self, action: lc.LedgerAction, data: bytes, parts: tuple[bytes, ...]
    ) -> LedgerResult:
        # AL-02 itself precharges every input helper before invocation. Adopt its
        # freshly generated accounting for subsequent result validation, not a
        # caller-constructed LedgerCommand or unverified reported work counter.
        command = lc.decode_ledger_command(data, parts, expected_action=action)
        s.require(command.namespace_id == self.namespace_id, "scope-mismatch")
        header = c.parse_json(command.command_bytes)
        for role in ("bundle",):
            if role in header["body"]:
                _scope(header["body"][role], self.org_id)
        work = _Work(command.hash_calls_reserved, command.hash_bytes_reserved)
        function, schema = _MUTATIONS[action]
        row = self._call(function, (command.command_bytes, list(command.parts)), 2)
        maximum = s.MAX_AUTHORITY if schema == s.SEALED else c.metadata_limit(schema)
        raw = _bytes(row[0], maximum)
        s.require(type(row[1]) is bool, "content-mismatch")
        if schema == s.SEALED:
            frame = work.frame(raw, schema, stored=True)
            document = frame.manifest
            request = work.occurrence("request", command.parts[0])
            s.require(document["codebase_id"] == request["codebase_id"], "ledger-mismatch")
            for key in ("bundle_id", "accepted_content_digest", "registry_id"):
                s.require(document[key] == header["body"]["bundle"][key], "ledger-mismatch")
            s.require(
                document["approval_event_id"] == header["body"]["approval_event_id"],
                "ledger-mismatch",
            )
            for key, value in header["body"]["admission"].items():
                field = "current_" + key if key in ("policy_digest", "policy_revision") else key
                s.require(document[field] == value, "ledger-mismatch")
            s.require(
                document["verifier_artifact_digest"] == header["body"]["verifier_artifact_digest"],
                "ledger-mismatch",
            )
        else:
            with _stored_validation():
                document = c.parse_json(raw, maximum=maximum)
            if schema == s.EXECUTION:
                s.require(document.get("schema") in (s.EXECUTION, s.DENIAL), "content-mismatch")
                schema = document["schema"]
            with _stored_validation():
                s.validate_document(document, schema)
            if action in ("install-policy", "record-admission"):
                s.require(raw == command.parts[0], "ledger-mismatch")
            elif action == "publish-builtin":
                frame = work.frame(command.parts[0], s.PUBLICATION_INPUT, stored=False)
                _link_publication(frame, document, work)
                for key, value in header["body"]["admission"].items():
                    s.require(document[key] == value, "ledger-mismatch")
                s.require(
                    document["publisher_artifact_digest"]
                    == header["body"]["publisher_artifact_digest"],
                    "ledger-mismatch",
                )
            else:
                s.require(
                    document["operation_key"] == str(command.operation_key), "ledger-mismatch"
                )
                for key, value in header["body"]["fence"].items():
                    if action != "renew-detector" or schema == s.DENIAL or key != "work_revision":
                        s.require(document[key] == value, "fence-stale")
                for key, value in header["body"]["admission"].items():
                    s.require(document[key] == value, "ledger-mismatch")
                s.require(
                    document["resolver_artifact_digest"]
                    == header["body"]["resolver_artifact_digest"],
                    "ledger-mismatch",
                )
                if action == "seal-bound-capture":
                    seal = work.occurrence("seal", command.parts[0])
                    for returned, supplied in (
                        ("request_id", "request_id"),
                        ("requested_policy_digest", "planned_policy_digest"),
                        ("accepted_content_digest", "accepted_content_digest"),
                        ("request_binding_digest", "acceptance_evidence_digest"),
                    ):
                        s.require(document[returned] == seal[supplied], "ledger-mismatch")
                elif action == "authorize-detector":
                    s.require(document["previous_authorization_id"] is None, "ledger-mismatch")
                    s.require(
                        document["run_input_digest"]
                        == work.domain("scanipy-execution/run-input/1", command.parts[0]),
                        "ledger-mismatch",
                    )
                    if schema == s.EXECUTION:
                        s.require(document["action"] == "initial", "ledger-mismatch")
                if action == "renew-detector":
                    s.require(
                        document["detector_run_id"] == header["body"]["detector_run_id"]
                        and document["previous_authorization_id"]
                        == header["body"]["previous_authorization_id"],
                        "ledger-mismatch",
                    )
                    if schema == s.EXECUTION:
                        s.require(
                            document["action"] == "renew"
                            and document["work_revision"]
                            == header["body"]["fence"]["work_revision"] + 1,
                            "fence-stale",
                        )
        _scope(document, self.org_id)
        return LedgerResult(raw, cast(bool, row[1]))

    def install_policy(self, data: bytes, parts: tuple[bytes, ...]) -> LedgerResult:
        return self._mutate("install-policy", data, parts)

    def record_admission(self, data: bytes, parts: tuple[bytes, ...]) -> LedgerResult:
        return self._mutate("record-admission", data, parts)

    def publish_builtin_bundle(self, data: bytes, parts: tuple[bytes, ...]) -> LedgerResult:
        return self._mutate("publish-builtin", data, parts)

    def create_bound_request(self, data: bytes, parts: tuple[bytes, ...]) -> LedgerResult:
        return self._mutate("create-bound-request", data, parts)

    def seal_bound_capture(self, data: bytes, parts: tuple[bytes, ...]) -> LedgerResult:
        return self._mutate("seal-bound-capture", data, parts)

    def authorize_detector_run(self, data: bytes, parts: tuple[bytes, ...]) -> LedgerResult:
        return self._mutate("authorize-detector", data, parts)

    def renew_authorized_execution(self, data: bytes, parts: tuple[bytes, ...]) -> LedgerResult:
        return self._mutate("renew-detector", data, parts)

    def initialize_registry_namespace(self, installed: m.InstalledTrust) -> tuple[UUID, bool]:
        _, value = _record(installed, m.InstalledTrust, s.SHAPES[s.INSTALLED_TRUST])
        _scope(value, self.org_id)
        raw = c.encode_document(value, s.INSTALLED_TRUST)
        row = self._call("initialize_registry_namespace_v1", (str(self.namespace_id), raw), 2)
        s.require(type(row[0]) is str and type(row[1]) is bool, "content-mismatch")
        with _stored_validation():
            s.shape(row[0], "uuid")
        result = UUID(cast(str, row[0]))
        s.require(result == self.namespace_id, "ledger-mismatch")
        return result, cast(bool, row[1])

    def read_publication_receipt(
        self, *, publication_key: UUID | None = None, approval_event_id: UUID | None = None
    ) -> bytes:
        s.require((publication_key is None) != (approval_event_id is None))
        key = None if publication_key is None else _uuid(publication_key)
        approval = None if approval_event_id is None else _uuid(approval_event_id)
        row = self._call(
            "read_publication_receipt_v1",
            (
                str(self.namespace_id),
                None if key is None else str(key),
                None if approval is None else str(approval),
            ),
            1,
        )
        raw = _bytes(row[0], s.MAX_OBJECT)
        document = _document(raw, s.PUBLICATION)
        _scope(document, self.org_id)
        if key is not None:
            s.require(document["publication_key"] == str(key), "ledger-mismatch")
        if approval is not None:
            s.require(document["approval_event_id"] == str(approval), "ledger-mismatch")
        return raw

    def read_exact_bundle(self, expected: m.BundleExpectation) -> m.AcceptedBundleBytes:
        private, value = _record(expected, m.BundleExpectation, s.BUNDLE_EXPECTATION)
        _scope(value, self.org_id)
        row = self._call(
            "read_exact_bundle_v1",
            (
                str(self.namespace_id),
                str(private.bundle_id),
                bytes.fromhex(private.accepted_content_digest),
            ),
            3,
        )
        detectors, rules = _array(row[1], s.MAX_VALUES), _array(row[2], s.MAX_VALUES)
        s.require(len(detectors) + len(rules) <= s.MAX_VALUES, "content-mismatch")
        size = _binary_size(row[0])
        for values in (detectors, rules):
            for item in values:
                size += _binary_size(item)
                s.require(size <= s.MAX_CONTENT, "content-mismatch")
        spec = _bytes(row[0], s.MAX_CONTENT)
        return _bundle(
            spec,
            tuple(_bytes(item, s.MAX_CONTENT) for item in detectors),
            tuple(_bytes(item, s.MAX_CONTENT) for item in rules),
            value,
            _Work(),
        )

    def read_authority_event(
        self, kind: str, event_id: UUID, record_digest: str
    ) -> tuple[bytes, tuple[bytes, ...]]:
        s.require(type(kind) is str and kind in _KINDS)
        event = _uuid(event_id)
        s.shape(record_digest, "digest")
        row = self._call(
            "read_authority_event_v1",
            (str(self.namespace_id), kind, str(event), bytes.fromhex(record_digest)),
            2,
        )
        schema = _KINDS[kind]
        support = _array(row[1], 2, empty=True)
        expected_count = 1 if kind in ("policy", "admission") else 2 if kind == "approval" else 0
        s.require(len(support) == expected_count, "content-mismatch")
        maximum = s.MAX_AUTHORITY + 2 * s.MAX_OBJECT if kind == "approval" else s.MAX_POLICY + 384
        s.require(
            _binary_size(row[0]) + sum(_binary_size(item) for item in support) <= maximum,
            "content-mismatch",
        )
        raw = _bytes(row[0], c.metadata_limit(schema))
        document = _document(raw, schema)
        _scope(document, self.org_id)
        work = _Work()
        s.require(
            document["event_id"] == str(event) and work.domain(schema, raw) == record_digest,
            "ledger-mismatch",
        )
        if kind in ("policy", "admission"):
            signature = _bytes(support[0], 384)
            s.require(len(signature) == 384, "content-mismatch")
            return raw, (signature,)
        if kind == "approval":
            original = _bytes(support[0], s.MAX_AUTHORITY)
            receipt = _bytes(support[1], s.MAX_OBJECT)
            frame = work.frame(original, s.PUBLICATION_INPUT, stored=True)
            s.require(frame.object("approval-statement") == raw, "ledger-mismatch")
            _link_publication(frame, _document(receipt, s.PUBLICATION), work)
            return raw, (original, receipt)
        return raw, ()

    def read_request_binding(self, codebase_id: UUID, request_id: UUID) -> bytes:
        s.require(self.org_id is not None, "scope-mismatch")
        codebase, request = _uuid(codebase_id), _uuid(request_id)
        row = self._call(
            "read_request_binding_v1",
            (str(self.namespace_id), str(self.org_id), str(codebase), str(request)),
            1,
        )
        raw = _bytes(row[0], s.MAX_AUTHORITY)
        frame = _Work().frame(raw, s.SEALED, stored=True)
        _scope(frame.manifest, self.org_id)
        s.require(
            frame.manifest["codebase_id"] == str(codebase)
            and frame.manifest["request_id"] == str(request),
            "ledger-mismatch",
        )
        return raw

    def _execution_inputs(
        self, binding: m.ExecutionBinding, admission: m.AdmissionExpectation
    ) -> tuple[dict[str, Any], dict[str, Any], bytes, bytes]:
        _, b = _record(binding, m.ExecutionBinding, s.EXECUTION_BINDING)
        _, a = _record(admission, m.AdmissionExpectation, s.ADMISSION_EXPECTATION)
        s.require(self.org_id is not None, "scope-mismatch")
        _scope(b, self.org_id)
        return b, a, c.canonical_bytes(b), c.canonical_bytes(a)

    def _current(
        self,
        ledger_raw: bytes,
        live: bytes,
        reference: object,
        binding: dict[str, Any],
        admission: dict[str, Any],
        *,
        stored: bool,
    ) -> m.LedgerExpectation:
        with _stored_validation() if stored else nullcontext():
            value = c.parse_json(ledger_raw)
            ledger = c.decode_record(value, m.LedgerExpectation, s.LEDGER_EXPECTATION)
        s.require(value["binding"] == binding and value["binding"] is not None, "fence-stale")
        with _stored_validation() if stored else nullcontext():
            s.shape(reference, "instant")
        work = _Work()
        frame = work.frame(live, s.LIVE, stored=stored)
        manifest = frame.manifest
        _scope(manifest, self.org_id)
        s.require(
            {key: manifest[key] for key in s.ADMISSION_EXPECTATION} == admission,
            "checkpoint-denied",
        )
        policy, checkpoint = (
            frame.document("current-policy"),
            frame.document("admission-checkpoint"),
        )
        s.require(
            policy["event_id"] == str(ledger.policy_event_id)
            and checkpoint["event_id"] == str(ledger.admission_event_id),
            "policy-stale",
        )
        s.require(
            work.domain(s.POLICY, frame.object("current-policy")) == admission["policy_digest"]
            and work.domain(s.ADMISSION, frame.object("admission-checkpoint"))
            == admission["checkpoint_digest"]
            and policy["revision"] == admission["policy_revision"]
            and checkpoint["generation"] == admission["checkpoint_generation"]
            and checkpoint["admission_epoch"] == admission["admission_epoch"],
            "checkpoint-denied",
        )
        return ledger

    def read_execution_authority(
        self, binding: m.ExecutionBinding, admission: m.AdmissionExpectation
    ) -> tuple[m.LedgerExpectation, bytes, str]:
        b, a, b_raw, a_raw = self._execution_inputs(binding, admission)
        row = self._call("read_execution_authority_v1", (str(self.namespace_id), b_raw, a_raw), 3)
        s.require(
            _binary_size(row[0]) + _binary_size(row[1]) <= s.MAX_OBJECT + s.MAX_LIVE,
            "content-mismatch",
        )
        ledger_raw, live = _bytes(row[0], s.MAX_OBJECT), _bytes(row[1], s.MAX_LIVE)
        ledger = self._current(ledger_raw, live, row[2], b, a, stored=True)
        return ledger, live, cast(str, row[2])

    def recheck_execution_authority(
        self,
        binding: m.ExecutionBinding,
        admission: m.AdmissionExpectation,
        ledger: m.LedgerExpectation,
        live: bytes,
        reference_time: str,
    ) -> None:
        b, a, b_raw, a_raw = self._execution_inputs(binding, admission)
        _, value = _record(ledger, m.LedgerExpectation, s.LEDGER_EXPECTATION)
        ledger_raw = c.canonical_bytes(value)
        s.require(type(live) is bytes and len(live) <= s.MAX_LIVE)
        self._current(ledger_raw, live, reference_time, b, a, stored=False)
        row = self._call(
            "recheck_execution_authority_v1",
            (str(self.namespace_id), b_raw, a_raw, ledger_raw, live, reference_time),
            1,
            void=True,
        )
        s.require(row[0] is None, "content-mismatch")


@contextmanager
def accepted_ledger_transaction(
    connection_factory: ConnectionFactory, namespace_id: UUID, org_id: UUID | None
) -> Iterator[AcceptedLedgerRepository]:
    """Installed caller supplies a fresh/discard-on-exit factory, never user data.

    Success is acknowledged only AFTER context exit. Ambiguous commit propagates;
    retry the identical immutable key/bytes on a new connection. Do not nest this
    helper inside an operation-owned transaction. It installs no capability.
    """
    namespace = _uuid(namespace_id)
    org = None if org_id is None else _uuid(org_id)
    with connection_factory() as connection:
        try:
            yield AcceptedLedgerRepository(connection, namespace, org)
            connection.commit()
        except BaseException as primary:
            prior = _prior_error(primary)
            try:
                connection.rollback()
            except BaseException as cleanup:
                raise primary from _cleanup_cause(primary, cleanup, prior)
            raise
