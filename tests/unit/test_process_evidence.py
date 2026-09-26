"""Pure codec vectors, never actual Docker observations or operational journals."""

from __future__ import annotations

import hashlib
import itertools
import json
from dataclasses import replace
from pathlib import PosixPath
from typing import Any

import pytest

from tools.worker import process_evidence as pe
from tools.worker.bounded_process import (
    FrozenInvocation,
    MemoryOutput,
    ProcessOutcome,
    ProcessTransportError,
    ProcessValidationError,
    SpoolOutput,
    StreamEvidence,
)

pytestmark = pytest.mark.unit

ATTEMPT = "11111111-1111-4111-8111-111111111111"
OPERATION = "22222222-2222-4222-8222-222222222222"
CALL = "33333333-3333-4333-8333-333333333333"
ERROR = "44444444-4444-4444-8444-444444444444"
CWD = "/private/jobs/" + ATTEMPT


def sha(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def encoded(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def plain(value: Any) -> Any:
    if type(value) is tuple:
        if value[0] == "object":
            return {key: plain(item) for key, item in value[1]}
        assert value[0] == "array"
        return [plain(item) for item in value[1]]
    return value


def invocation() -> FrozenInvocation:
    environment = {
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "TZ": "UTC",
        "HOME": CWD + "/cli-home",
        "TMPDIR": CWD + "/cli-tmp",
        "PATH": CWD + "/cli-bin",
        "DOCKER_API_VERSION": "1.52",
        "DOCKER_CLI_HOOKS": "false",
        "DOCKER_CLI_HINTS": "false",
        "OTEL_SDK_DISABLED": "true",
    }
    return FrozenInvocation(
        ("/trusted/docker", "version"), tuple(sorted(environment.items())), CWD, 0, sha(b"")
    )


def binding() -> pe.RuntimeCallBinding:
    return pe.RuntimeCallBinding(ATTEMPT, OPERATION, CALL, 1, pe.CliOperation.DAEMON_VERSION, None)


def memory(data: bytes = b"") -> MemoryOutput:
    return MemoryOutput(StreamEvidence(len(data), len(data), sha(data), True, False), data)


def outcome() -> ProcessOutcome:
    return ProcessOutcome(
        invocation(), "exited", 123, 123, 0, 0, memory(), memory(), 10, "completed"
    )


def result(**changes: Any) -> pe.PreparedCallResult:
    arguments = {
        "intent_event_digest": b"i" * 32,
        "outcome": outcome(),
        "error_id": None,
        "error": None,
    }
    arguments.update(changes)
    return pe.prepare_call_result(pe.prepare_call_intent(binding(), invocation()), **arguments)


def document(prepared: pe.PreparedCallResult) -> dict[str, Any]:
    reference = plain(prepared.call_ref)["outcome"]
    raw = next(blob.data for blob in prepared.blobs if blob.sha256.hex() == reference["sha256"])
    return plain(pe.decode_call_result(raw))


def test_invocation_roundtrip_is_stored_primitives() -> None:
    raw = pe.encode_invocation(invocation())
    view = pe.decode_invocation(raw)
    assert type(view) is tuple
    assert plain(view) == json.loads(raw)
    assert raw == encoded(json.loads(raw))


def test_intent_and_result_bind_backwards_without_journal_authority() -> None:
    intent = pe.prepare_call_intent(binding(), invocation())
    assert (
        plain(pe.decode_call_intent(intent.payload))["invocation"]["sha256"]
        == sha(intent.invocation_blob.data).hex()
    )
    prepared = result()
    doc = document(prepared)
    assert doc["intent_event_digest"] == (b"i" * 32).hex()
    assert doc["requested_invocation"] == doc["outcome"]["invocation"]
    assert doc["scope"] == "host-docker-client"
    assert doc["outcome"]["stdout"]["reported"]["retained_bytes"] == 0
    assert doc["error_graph"] is None
    for blob in prepared.blobs:
        assert sha(blob.data) == blob.sha256


@pytest.mark.parametrize(
    "raw",
    [
        b"{} ",
        b'{"x":1,"x":1}',
        b'{"x":1.0}',
        b'{"x":NaN}',
        b'{"x":9223372036854775808}',
        b'{"x":-9223372036854775809}',
        b'{"x":"\\u0000"}',
        b'{"x":"\\ud800"}',
    ],
)
def test_invalid_canonical_json_is_rejected(raw: bytes) -> None:
    with pytest.raises(pe.ProcessEvidenceError):
        pe.decode_invocation(raw)


def test_error_graph_is_lossy_without_mutating_live_error() -> None:
    original = ValueError("private diagnostic")
    original.__cause__ = RuntimeError("earlier")
    prepared = result(error=original, error_id=ERROR)
    doc = document(prepared)
    graph_raw = next(
        blob.data for blob in prepared.blobs if blob.sha256.hex() == doc["error_graph"]["sha256"]
    )
    graph = plain(pe.decode_error_graph(graph_raw))
    assert graph["nodes"][0]["cause"] == 1
    assert graph["nodes"][1]["class"] == "runtime-error"
    assert original.args == ("private diagnostic",)
    assert original.__cause__.args == ("earlier",)


def graph(error: BaseException) -> dict[str, Any]:
    prepared = result(error=error, error_id=ERROR)
    reference = document(prepared)["error_graph"]
    raw = next(blob.data for blob in prepared.blobs if blob.sha256.hex() == reference["sha256"])
    return plain(pe.decode_error_graph(raw))


def altered(value: Any, **changes: Any) -> Any:
    for key, member in changes.items():
        object.__setattr__(value, key, member)
    return value


class Poison:
    def __repr__(self) -> str:
        raise AssertionError("caller repr")

    def __str__(self) -> str:
        raise AssertionError("caller str")

    def __iter__(self) -> Any:
        raise AssertionError("caller iteration")

    def __eq__(self, other: object) -> bool:
        raise AssertionError("caller equality")

    def __hash__(self) -> int:
        raise AssertionError("caller hash")

    def __bool__(self) -> bool:
        raise AssertionError("caller bool")


class PoisonTuple(tuple):
    def __iter__(self) -> Any:
        raise AssertionError("caller tuple iteration")


class PoisonDict(dict):
    def items(self) -> Any:
        raise AssertionError("caller dict iteration")


@pytest.mark.parametrize("literal", [literal for _, literal in pe._OPERATIONS])
def test_one_operation_enum_roundtrips(literal: str) -> None:
    member = pe.cli_operation_from_wire(literal)
    assert pe._operation(member) == literal


@pytest.mark.parametrize("value", [Poison(), "logs", "DAEMON_VERSION", 1, True, None])
def test_operation_rejects_unknown_without_formatting(value: Any) -> None:
    with pytest.raises(pe.ProcessEvidenceError):
        pe.cli_operation_from_wire(value)


def test_poisoned_enum_internals_are_not_authority(monkeypatch: pytest.MonkeyPatch) -> None:
    member = pe.CliOperation.DAEMON_VERSION
    monkeypatch.setattr(member, "_name_", Poison())
    monkeypatch.setattr(member, "_value_", Poison())
    assert pe._operation(member) == "daemon-version"
    assert pe.prepare_call_intent(binding(), invocation()).binding.operation is member


@pytest.mark.parametrize("member,literal", pe._OPERATIONS)
def test_binding_target_syntax_and_attempt_name(member: pe.CliOperation, literal: str) -> None:
    target: str | None
    if literal.startswith("daemon-"):
        target = None
    elif literal == "image-inspect":
        target = "sha256:" + "a" * 64
    elif literal in ("container-create", "container-inspect-name"):
        target = "scanipy-runtime-" + ATTEMPT.replace("-", "")
    else:
        target = "a" * 64
    selected = replace(binding(), operation=member, target=target)
    prepared = pe.prepare_call_intent(selected, invocation())
    assert plain(pe.decode_call_intent(prepared.payload))["target"] == target
    with pytest.raises(pe.ProcessEvidenceError):
        pe.prepare_call_intent(replace(selected, target="not-a-target"), invocation())


@pytest.mark.parametrize(
    "field,value",
    [
        ("attempt_id", Poison()),
        ("operation_id", "ABC"),
        ("call_id", "0" * 36),
        ("call_sequence", True),
        ("call_sequence", 0),
        ("call_sequence", 17),
        ("operation", Poison()),
        ("target", Poison()),
    ],
)
def test_binding_slots_are_revalidated(field: str, value: Any) -> None:
    selected = altered(binding(), **{field: value})
    with pytest.raises(pe.ProcessEvidenceError):
        pe.prepare_call_intent(selected, invocation())


@pytest.mark.parametrize(
    "field,value",
    [
        ("argv", Poison()),
        ("argv", PoisonTuple(("/x",))),
        ("argv", []),
        ("argv", ()),
        ("argv", ("relative",)),
        ("argv", ("/x", Poison())),
        ("environment", PoisonTuple(())),
        ("environment", []),
        ("environment", ((Poison(), "v"),)),
        ("environment", (("a=b", "v"),)),
        ("environment", (("z", "1"), ("a", "2"))),
        ("environment", (("a", "1"), ("a", "1"))),
        ("cwd", Poison()),
        ("cwd", "/"),
        ("cwd", "relative"),
        ("cwd", "/a/../b"),
        ("stdin_bytes", True),
        ("stdin_bytes", -1),
        ("stdin_bytes", 4194305),
        ("stdin_sha256", bytearray(32)),
        ("stdin_sha256", b"short"),
    ],
)
def test_shared_invocation_poison_and_bounds(field: str, value: Any) -> None:
    candidate = altered(invocation(), **{field: value})
    with pytest.raises(pe.ProcessEvidenceError):
        pe.encode_invocation(candidate)


@pytest.mark.parametrize("storage", [PoisonDict(), {"extra": Poison()}, {}])
def test_shared_record_dictionary_exactness(storage: dict[Any, Any]) -> None:
    candidate = altered(invocation(), __dict__=storage)
    with pytest.raises(pe.ProcessEvidenceError):
        pe.encode_invocation(candidate)


def test_shared_record_poison_key_is_not_hashed_during_snapshot() -> None:
    key = Poison()
    storage: dict[Any, Any] = {}
    # Construct a dict entry with a benign hash, then forbid any further call.
    original = Poison.__hash__
    Poison.__hash__ = lambda self: 1
    try:
        storage[key] = 1
    finally:
        Poison.__hash__ = original
    candidate = altered(invocation(), __dict__=storage)
    with pytest.raises(pe.ProcessEvidenceError):
        pe.encode_invocation(candidate)


def test_subclass_record_is_not_a_shared_snapshot() -> None:
    class Derived(FrozenInvocation):
        pass

    candidate = object.__new__(Derived)
    with pytest.raises(pe.ProcessEvidenceError):
        pe.encode_invocation(candidate)


@pytest.mark.parametrize(
    "cwd",
    [
        "/private//jobs/" + ATTEMPT,
        "/private/jobs/./" + ATTEMPT,
        "/private/jobs/" + ATTEMPT + "/",
        "/" + ATTEMPT,
        "/private/jobs/" + CALL,
    ],
)
def test_intent_only_cwd_policy_does_not_rewrite_actual(cwd: str) -> None:
    candidate = replace(invocation(), cwd=cwd)
    assert plain(pe.decode_invocation(pe.encode_invocation(candidate)))["cwd"] == cwd
    with pytest.raises(pe.ProcessEvidenceError):
        pe.prepare_call_intent(binding(), candidate)
    observed = replace(outcome(), invocation=candidate)
    stored = document(result(outcome=observed))
    assert stored["requested_invocation"] != stored["outcome"]["invocation"]


@pytest.mark.parametrize("environment", [(), (("LANG", "C"),), (("PATH", "/usr/bin"),)])
def test_intent_environment_is_exact_but_actual_mismatch_survives(environment: tuple) -> None:
    candidate = replace(invocation(), environment=environment)
    with pytest.raises(pe.ProcessEvidenceError):
        pe.prepare_call_intent(binding(), candidate)
    assert document(result(outcome=replace(outcome(), invocation=candidate)))["outcome"] is not None


@pytest.mark.parametrize("field", ["binding", "invocation", "invocation_blob", "payload"])
def test_prepared_intent_constructor_does_not_grant_validity(field: str) -> None:
    prepared = altered(pe.prepare_call_intent(binding(), invocation()), **{field: Poison()})
    with pytest.raises(pe.ProcessEvidenceError):
        pe.prepare_call_result(
            prepared, intent_event_digest=b"i" * 32, outcome=outcome(), error=None, error_id=None
        )


@pytest.mark.parametrize("field,value", [("data", b"{}"), ("sha256", b"x" * 32)])
def test_prepared_blob_mismatch_is_not_repaired(field: str, value: Any) -> None:
    prepared = pe.prepare_call_intent(binding(), invocation())
    altered(prepared.invocation_blob, **{field: value})
    with pytest.raises(pe.ProcessEvidenceError):
        pe.prepare_call_result(
            prepared, intent_event_digest=b"i" * 32, outcome=outcome(), error=None, error_id=None
        )


@pytest.mark.parametrize("reason", sorted(pe._REASONS))
def test_reason_is_preserved_independent_of_cleanup(reason: str) -> None:
    observed = altered(outcome(), reason=reason)
    assert document(result(outcome=observed))["outcome"]["reason"] == reason


def test_exited_zero_incomplete_is_real_failure_evidence() -> None:
    observed = replace(outcome(), cleanup="incomplete", stderr=None)
    row = document(result(outcome=observed, error=OSError("snapshot failed"), error_id=ERROR))
    assert row["outcome"]["returncode"] == 0
    assert row["outcome"]["cleanup"] == "incomplete"
    assert row["outcome"]["stdout"]["reported"]["retained_bytes"] == 0
    assert row["outcome"]["stderr"] is None


@pytest.mark.parametrize(
    "field,value",
    [
        ("reason", Poison()),
        ("reason", "success"),
        ("cleanup", "done"),
        ("pid", True),
        ("pid", 0),
        ("pid", 2**31),
        ("pgid", 124),
        ("returncode", True),
        ("returncode", 2**31),
        ("elapsed_ms", True),
        ("elapsed_ms", -1),
        ("elapsed_ms", 2**63),
        ("stdin_sent_bytes", 1),
        ("stdin_sent_bytes", True),
        ("stdout", Poison()),
        ("invocation", Poison()),
    ],
)
def test_actual_outcome_revalidation_rejects_poison(field: str, value: Any) -> None:
    with pytest.raises(pe.ProcessEvidenceError):
        result(outcome=altered(outcome(), **{field: value}))


@pytest.mark.parametrize(
    "field,value",
    [
        ("observed_bytes", True),
        ("observed_bytes", -1),
        ("observed_bytes", 129 * 1048576 + 65537),
        ("retained_bytes", True),
        ("retained_bytes", 1),
        ("retained_bytes", None),
        ("retained_sha256", b"x" * 32),
        ("retained_sha256", None),
        ("eof", 1),
        ("truncated", 0),
    ],
)
def test_memory_evidence_is_not_repaired(field: str, value: Any) -> None:
    observed = outcome()
    altered(observed.stdout.evidence, **{field: value})
    with pytest.raises(pe.ProcessEvidenceError):
        result(outcome=observed)


@pytest.mark.parametrize("data", [Poison(), bytearray(), b"different"])
def test_memory_bytes_exactness(data: Any) -> None:
    observed = outcome()
    altered(observed.stdout, data=data)
    with pytest.raises(pe.ProcessEvidenceError):
        result(outcome=observed)


@pytest.mark.parametrize(
    "known,readback,state",
    [
        (True, b"abc", "verified"),
        (True, b"changed", "mismatch"),
        (True, None, "unavailable"),
        (False, b"abc", "diagnostic-copy"),
        (False, None, "unavailable"),
    ],
)
def test_spool_custody_preserves_unknown_and_mismatch(
    known: bool, readback: bytes | None, state: str
) -> None:
    evidence = StreamEvidence(9, 3 if known else None, sha(b"abc") if known else None, False, True)
    spool = SpoolOutput(evidence, PosixPath("/private/spool/stdout.bin"))
    observed = replace(outcome(), stdout=spool, cleanup="incomplete")
    row = document(result(outcome=observed, spool_readback=(readback, None)))["outcome"]["stdout"]
    assert row["custody"]["state"] == state
    assert row["reported"]["retained_bytes"] == (3 if known else None)
    assert row["reported"]["observed_bytes"] == 9
    assert row["reported"]["eof"] is False


@pytest.mark.parametrize(
    "readback",
    [
        [],
        PoisonTuple((None, None)),
        (None,),
        (None, None, None),
        (b"unexpected", None),
        (Poison(), None),
    ],
)
def test_readback_exactness_and_memory_confusion(readback: Any) -> None:
    with pytest.raises(pe.ProcessEvidenceError):
        result(spool_readback=readback)


def test_spool_path_caches_are_not_used() -> None:
    path = PosixPath("/private/spool/file")
    observed = replace(
        outcome(),
        stdout=SpoolOutput(StreamEvidence(0, None, None, False, False), path),
        cleanup="incomplete",
    )
    altered(observed.stdout.path, _str=Poison())
    assert document(result(outcome=observed))["outcome"]["stdout"]["path"]["size"] == len(
        "/private/spool/file"
    )


def test_spool_path_poisoned_parts_rejected_without_iteration() -> None:
    observed = replace(
        outcome(),
        stdout=SpoolOutput(StreamEvidence(0, None, None, False, False), PosixPath("/private/file")),
        cleanup="incomplete",
    )
    path = observed.stdout.path
    altered(path, **{("_raw_paths" if hasattr(path, "_raw_paths") else "_parts"): Poison()})
    with pytest.raises(pe.ProcessEvidenceError):
        result(outcome=observed)


@pytest.mark.parametrize(
    "error,reason",
    [
        (ValueError("x"), "exception-no-outcome"),
        (ProcessValidationError("x"), "validation-refused"),
        (KeyboardInterrupt(), "exception-no-outcome"),
    ],
)
def test_real_returned_exception_without_outcome(error: BaseException, reason: str) -> None:
    row = document(result(outcome=None, error=error, error_id=ERROR))
    assert row["outcome"] is None and row["unavailable_reason"] == reason


@pytest.mark.parametrize(
    "changes",
    [
        {"outcome": None},
        {"error_id": ERROR},
        {"error": ValueError()},
        {"error": Poison(), "error_id": ERROR},
        {"error": ValueError(), "error_id": Poison()},
    ],
)
def test_no_synthetic_absence_or_unpaired_errors(changes: dict[str, Any]) -> None:
    with pytest.raises(pe.ProcessEvidenceError):
        result(**changes)


@pytest.mark.parametrize("immediate", [False, True])
def test_exact_transport_carrier_preserves_complete_outcome_and_opaque_handles(
    immediate: bool,
) -> None:
    actual = outcome()
    carrier = ProcessTransportError(actual)
    carrier._owned_child = Poison()
    carrier.__notes__ = Poison()
    error: BaseException = carrier
    if immediate:
        error = KeyboardInterrupt()
        error.__cause__ = carrier
    row = document(result(outcome=outcome(), error=error, error_id=ERROR))
    assert row["outcome"]["pid"] == 123
    assert type(carrier._owned_child) is Poison and type(carrier.__notes__) is Poison


@pytest.mark.parametrize(
    "field,value",
    [
        ("elapsed_ms", 11),
        ("pid", 124),
        ("stdout", None),
        ("reason", "timeout"),
        ("invocation", None),
    ],
)
def test_carrier_complete_mismatch_or_poison_is_fatal(field: str, value: Any) -> None:
    carrier = ProcessTransportError(outcome())
    supplied = altered(outcome(), **{field: value})
    with pytest.raises(pe.ProcessEvidenceError):
        result(outcome=supplied, error=carrier, error_id=ERROR)


def test_carrier_missing_supplied_outcome_is_not_unavailable() -> None:
    with pytest.raises(pe.ProcessEvidenceError):
        result(outcome=None, error=ProcessTransportError(outcome()), error_id=ERROR)


@pytest.mark.parametrize(
    "storage",
    [
        PoisonDict(),
        {},
        {"outcome": None, "_owned_child": None},
        {"outcome": Poison(), "_owned_child": None},
        {"outcome": None, "_owned_child": None, "extra": None},
        {"outcome": None, "_owned_child": None, "__notes__": None, "extra": None},
    ],
)
def test_carrier_storage_poison_is_fatal(storage: dict[Any, Any]) -> None:
    carrier = ProcessTransportError(outcome())
    carrier.__dict__ = storage
    with pytest.raises(pe.ProcessEvidenceError):
        result(error=carrier, error_id=ERROR)


@pytest.mark.parametrize("placement", ["context", "deep-cause", "group", "subclass"])
def test_unselected_carriers_never_supply_fallback(placement: str) -> None:
    carrier = ProcessTransportError(outcome())
    carrier.__dict__ = {"poison": Poison()}
    if placement == "context":
        error: BaseException = ValueError()
        error.__context__ = carrier
    elif placement == "deep-cause":
        error = ValueError()
        error.__cause__ = RuntimeError()
        error.__cause__.__cause__ = carrier
    elif placement == "group":
        error = ExceptionGroup("x", [carrier])
    else:

        class DerivedError(ProcessTransportError):
            pass

        error = DerivedError(outcome())
        error.__dict__ = {"poison": Poison()}
    row = document(result(outcome=None, error=error, error_id=ERROR))
    assert row["unavailable_reason"] == "exception-no-outcome"


def test_direct_carrier_takes_precedence_over_its_own_cause() -> None:
    carrier = ProcessTransportError(outcome())
    carrier.__cause__ = ProcessTransportError(altered(outcome(), elapsed_ms=99))
    assert document(result(error=carrier, error_id=ERROR))["outcome"]["elapsed_ms"] == 10


@pytest.mark.parametrize(
    "value",
    [None, True, False, 0, -(2**63), 2**63 - 1, "é", '\\"\n\t', [1, 2], {"é": "x", "a": []}],
)
def test_canonical_exact_byte_preflight(value: Any) -> None:
    raw = encoded(value)
    assert pe._canonical(value, (len(raw), 8, 100)) == raw
    if len(raw) > 1:
        with pytest.raises(pe.ProcessEvidenceError):
            pe._canonical(value, (len(raw) - 1, 8, 100))


@pytest.mark.parametrize("maximum,accepted", [(4, False), (5, True), (6, True)])
def test_json_key_inclusive_value_boundary(maximum: int, accepted: bool) -> None:
    value = {"a": 1, "b": None}  # root + two keys + two values = five.
    if accepted:
        assert pe._canonical(value, (100, 1, maximum)) == encoded(value)
        pe._lexical(encoded(value), (100, 1, maximum))
    else:
        with pytest.raises(pe.ProcessEvidenceError):
            pe._canonical(value, (100, 1, maximum))
        with pytest.raises(pe.ProcessEvidenceError):
            pe._lexical(encoded(value), (100, 1, maximum))


@pytest.mark.parametrize("maximum,accepted", [(2, False), (3, True), (4, True)])
def test_container_depth_scalar_leaves_do_not_add_depth(maximum: int, accepted: bool) -> None:
    value = {"a": [{"b": 1}]}
    if accepted:
        assert pe._canonical(value, (100, maximum, 8)) == encoded(value)
        pe._lexical(encoded(value), (100, maximum, 8))
    else:
        with pytest.raises(pe.ProcessEvidenceError):
            pe._canonical(value, (100, maximum, 8))
        with pytest.raises(pe.ProcessEvidenceError):
            pe._lexical(encoded(value), (100, maximum, 8))


@pytest.mark.parametrize(
    "raw",
    [
        b'{"x":9223372036854775808}',
        b'{"x":-9223372036854775809}',
        b'{"x":00000000000000000000}',
        b'{"x":1e0}',
        b'{"x":1.0}',
        b'{"x":Infinity}',
        b'{"x":NaN}',
        b'{"x":-Infinity}',
        b'{"x":' + b"[" * 5 + b"0" + b"]" * 5 + b"}",
        b"{" + b",".join(b'"a' + str(i).encode() + b'":0' for i in range(1024)) + b"}",
    ],
)
def test_lexical_rejection_precedes_generic_json(
    raw: bytes, monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("generic decoder ran")

    monkeypatch.setattr(pe.json, "loads", forbidden)
    with pytest.raises(pe.ProcessEvidenceError):
        pe.decode_invocation(raw)


@pytest.mark.parametrize(
    "raw",
    [
        b'{"x":9223372036854775807}',
        b'{"x":-9223372036854775808}',
        b'{"x":"quoted { [ 92233720368547758089999"}',
        b'{"x":"escaped \\" [ "}',
    ],
)
def test_lexical_guard_preserves_valid_scalar_tokens(raw: bytes) -> None:
    pe._lexical(raw, (1024, 1, 3))


@pytest.mark.parametrize(
    "value", [["x" * 16384] * 100, {str(i): "x" for i in range(100)}, [[[]] * 30] * 30, [[[[]]]]]
)
def test_encoder_rejects_before_json_allocation(
    value: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("generic encoder ran")

    monkeypatch.setattr(pe.json, "dumps", forbidden)
    with pytest.raises(pe.ProcessEvidenceError):
        pe._canonical(value, (1024, 3, 64))


@pytest.mark.parametrize(
    "value",
    [
        Poison(),
        PoisonDict(),
        PoisonTuple(),
        (1,),
        {"x": Poison()},
        [2**63],
        ["\0"],
        ["\ud800"],
        [float("nan")],
        [1.1],
    ],
)
def test_json_snapshot_accepts_only_closed_primitives(value: Any) -> None:
    with pytest.raises(pe.ProcessEvidenceError):
        pe._canonical(value, (1024, 4, 64))


def test_encoder_uses_private_snapshot_after_preflight(monkeypatch: pytest.MonkeyPatch) -> None:
    value = {"safe": ["original"]}
    original = pe.json.dumps

    def encoder(snapshot: Any, **kwargs: Any) -> str:
        value["safe"].append(Poison())
        assert snapshot == {"safe": ["original"]}
        return original(snapshot, **kwargs)

    monkeypatch.setattr(pe.json, "dumps", encoder)
    assert pe._canonical(value, (1024, 4, 64)) == b'{"safe":["original"]}'


@pytest.mark.parametrize(
    "raw",
    [
        b'{"a":1,"a":2}',
        b'{"a":-0}',
        b'{"a":"\\u0061"}',
        b'{ "a":1}',
        b'{"b":0,"a":1}',
        b'{"a":01}',
        b'{"a":truefalse}',
        b'{"a":1,}',
        b'{"a":[]}',
        b'{"a":"\\ud800"}',
    ],
)
def test_invalid_or_wrong_role_json_never_becomes_invocation(raw: bytes) -> None:
    with pytest.raises(pe.ProcessEvidenceError):
        pe.decode_invocation(raw)


@pytest.mark.parametrize(
    "decoder,maximum",
    [
        (pe.decode_invocation, 1048576),
        (pe.decode_call_intent, 2048),
        (pe.decode_call_ref, 2048),
        (pe.decode_call_result, 32768),
        (pe.decode_error_graph, 8192),
    ],
)
def test_role_byte_caps_before_parsing(
    decoder: Any, maximum: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("generic decoder ran")

    monkeypatch.setattr(pe.json, "loads", forbidden)
    with pytest.raises(pe.ProcessEvidenceError):
        decoder(b" " * (maximum + 1))


@pytest.mark.parametrize(
    "decoder",
    [
        pe.decode_invocation,
        pe.decode_call_intent,
        pe.decode_call_ref,
        pe.decode_call_result,
        pe.decode_error_graph,
    ],
)
def test_decoders_reject_mutable_bytes(decoder: Any) -> None:
    with pytest.raises(pe.ProcessEvidenceError):
        decoder(bytearray(b"{}"))


@pytest.mark.parametrize("count,accepted", [(255, True), (256, True), (257, False)])
def test_argv_count_boundary(count: int, accepted: bool) -> None:
    candidate = altered(invocation(), argv=("/x",) + ("",) * (count - 1))
    if accepted:
        assert len(plain(pe.decode_invocation(pe.encode_invocation(candidate)))["argv"]) == count
    else:
        with pytest.raises(pe.ProcessEvidenceError):
            pe.encode_invocation(candidate)


@pytest.mark.parametrize("count,accepted", [(8191, True), (8192, True), (8193, False)])
def test_argv_member_byte_boundary(count: int, accepted: bool) -> None:
    candidate = altered(invocation(), argv=("/x", "x" * count))
    if accepted:
        pe.decode_invocation(pe.encode_invocation(candidate))
    else:
        with pytest.raises(pe.ProcessEvidenceError):
            pe.encode_invocation(candidate)


@pytest.mark.parametrize("total,accepted", [(65535, True), (65536, True), (65537, False)])
def test_argv_aggregate_byte_boundary(total: int, accepted: bool) -> None:
    argv = ("/x",) + ("x" * 8192,) * 7
    argv += ("x" * (total - sum(len(item) + 1 for item in argv) - 1),)
    candidate = altered(invocation(), argv=argv)
    if accepted:
        pe.encode_invocation(candidate)
    else:
        with pytest.raises(pe.ProcessEvidenceError):
            pe.encode_invocation(candidate)


@pytest.mark.parametrize("count,accepted", [(63, True), (64, True), (65, False)])
def test_environment_count_boundary(count: int, accepted: bool) -> None:
    candidate = altered(invocation(), environment=tuple((f"a{i:02}", "") for i in range(count)))
    if accepted:
        pe.encode_invocation(candidate)
    else:
        with pytest.raises(pe.ProcessEvidenceError):
            pe.encode_invocation(candidate)


@pytest.mark.parametrize("value", ["é", "\n", "\t", "\\", '"', "\x01", "😀"])
def test_invocation_unicode_and_escape_bytes_are_exact(value: str) -> None:
    candidate = replace(invocation(), argv=("/x", value))
    raw = pe.encode_invocation(candidate)
    assert plain(pe.decode_invocation(raw))["argv"][1] == value
    assert raw == encoded(json.loads(raw))


class HostileError(Exception):
    def __getattribute__(self, name: str) -> Any:
        raise AssertionError("error attribute callback")

    @property
    def args(self) -> Any:
        raise AssertionError("error args property")

    @property
    def __cause__(self) -> Any:
        raise AssertionError("error cause property")

    @property
    def __context__(self) -> Any:
        raise AssertionError("error context property")

    def __str__(self) -> str:
        raise AssertionError("error str callback")


def test_exception_subclass_callbacks_are_never_invoked() -> None:
    error = HostileError("safe primitive", Poison())
    BaseException.__dict__["__cause__"].__set__(error, ValueError("cause"))
    row = graph(error)
    assert row["nodes"][0]["class"] == "opaque"
    assert row["nodes"][0]["cause"] == 1
    assert row["nodes"][0]["args"] == [{"kind": "text", "value": "safe primitive"}]


def test_hostile_root_immediate_carrier_is_read_with_builtin_descriptor() -> None:
    error = HostileError()
    BaseException.__dict__["__cause__"].__set__(error, ProcessTransportError(outcome()))
    assert document(result(error=error, error_id=ERROR))["outcome"]["pid"] == 123


def test_group_descriptor_ignores_poisoned_subclass_property() -> None:
    class HostileGroup(ExceptionGroup):
        @property
        def exceptions(self) -> Any:
            raise AssertionError("group property callback")

    row = graph(HostileGroup("group", [ValueError("child")]))
    assert row["nodes"][0]["class"] == "opaque"
    assert row["nodes"][0]["group_children"] == [1]


def test_error_cycle_and_shared_refs_use_builtin_identity() -> None:
    first = ValueError()
    second = RuntimeError()
    first.__cause__ = second
    first.__context__ = second
    second.__cause__ = first
    row = graph(first)
    assert len(row["nodes"]) == 2
    assert row["nodes"][0]["cause"] == row["nodes"][0]["context"] == 1
    assert row["nodes"][1]["cause"] == 0
    assert first.__cause__ is second and second.__cause__ is first


def test_graph_order_cause_context_then_group() -> None:
    root = ExceptionGroup("root", [ValueError("member"), RuntimeError("shared")])
    root.__cause__ = ValueError("cause")
    root.__context__ = RuntimeError("context")
    root.exceptions[0].__cause__ = root.exceptions[1]
    row = graph(root)
    assert row["nodes"][0]["cause"] == 1
    assert row["nodes"][0]["context"] == 2
    assert row["nodes"][0]["group_children"] == [3, 4]
    assert row["nodes"][3]["cause"] == 4


@pytest.mark.parametrize(
    "value,kind",
    [
        (None, "null"),
        (True, "bool"),
        (False, "bool"),
        (-(2**63), "int"),
        (2**63 - 1, "int"),
        ("é", "text"),
        (b"\0\xff", "bytes"),
    ],
)
def test_error_argument_closed_primitive_variants(value: Any, kind: str) -> None:
    assert graph(ValueError(value))["nodes"][0]["args"][0]["kind"] == kind


@pytest.mark.parametrize(
    "value",
    [
        Poison(),
        (1,),
        [1],
        {"a": 1},
        1.0,
        2**63,
        -(2**63) - 1,
        "\0",
        "\ud800",
        "a" * 513,
        b"a" * 513,
    ],
)
def test_unsupported_error_arguments_are_explicit_omissions(value: Any) -> None:
    row = graph(ValueError(value))
    assert row["nodes"][0]["args"] == []
    assert row["omissions"][0]["field"] == "args"


@pytest.mark.parametrize(
    "count,retained,loss", [(7, 7, False), (8, 8, False), (9, 8, True), (100000, 8, True)]
)
def test_original_args_tuple_prefix_is_bounded(count: int, retained: int, loss: bool) -> None:
    error = ValueError()
    error.args = (1,) * count
    row = graph(error)
    assert len(row["nodes"][0]["args"]) == retained
    assert bool(row["omissions"]) is loss


@pytest.mark.parametrize("length,retained", [(511, True), (512, True), (513, False)])
def test_raw_argument_byte_boundary(length: int, retained: bool) -> None:
    row = graph(ValueError(b"x" * length))
    assert bool(row["nodes"][0]["args"]) is retained


def test_aggregate_inspected_arg_budget_counts_unsupported_entries() -> None:
    errors = [ValueError(*([Poison()] * 8)) for _ in range(5)]
    for first, second in itertools.pairwise(errors):
        first.__cause__ = second
    row = graph(errors[0])
    assert all(node["args"] == [] for node in row["nodes"])
    assert len(row["omissions"]) == 32
    assert row["omission_overflow"] is not None


def test_aggregate_argument_encoded_bytes_preserves_loss() -> None:
    row = graph(ValueError(*(b"x" * 512 for _ in range(8))))
    args = row["nodes"][0]["args"]
    assert sum(len(encoded(item)) for item in args) <= 2048
    assert 0 < len(args) < 8 and any(loss["reason"] == "bytes" for loss in row["omissions"])


@pytest.mark.parametrize("length", [16, 17, 18, 100])
def test_error_depth_bound_is_first_discovery_depth(length: int) -> None:
    errors = [ValueError() for _ in range(length)]
    for first, second in itertools.pairwise(errors):
        first.__cause__ = second
    row = graph(errors[0])
    assert len(row["nodes"]) == min(length, 17)
    assert any(loss["reason"] == "depth" for loss in row["omissions"]) is (length > 17)


@pytest.mark.parametrize("count", [31, 32, 33, 100000])
def test_native_group_prefix_and_edges_are_bounded(count: int) -> None:
    child = ValueError()
    error = ExceptionGroup("x", [child] * count)
    row = graph(error)
    assert len(row["nodes"][0]["group_children"]) == min(count, 32)
    assert len(row["nodes"]) == 2
    assert any(loss["field"] == "group" for loss in row["omissions"]) is (count > 32)


def test_omission_32_then_overflow_stops_before_extra_nodes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class OpaqueError(Exception):
        pass

    class OpaqueGroup(ExceptionGroup):
        pass

    children = [OpaqueError() for _ in range(32)]
    root = OpaqueGroup("root", children)
    BaseException.__dict__["args"].__set__(root, ())
    visited: list[int] = []
    original = pe._Graph._node

    def observe(error: BaseException, index: int) -> dict[str, Any]:
        visited.append(id(error))
        return original(error, index)

    monkeypatch.setattr(pe._Graph, "_node", staticmethod(observe))
    row = graph(root)
    assert len(row["omissions"]) == 32
    assert row["omission_overflow"] == {
        "additional_details_at_least": 1,
        "exact_count": None,
        "enumeration": "incomplete",
    }
    assert id(children[-1]) not in visited
    assert len(row["nodes"]) == 32


def graph_node(index: int, **changes: Any) -> dict[str, Any]:
    return {
        "id": index,
        "class": "value-error",
        "args": [],
        "cause": None,
        "context": None,
        "suppress_context": False,
        "group_children": None,
    } | changes


def graph_document(nodes: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema": "scanipy-private-error-graph/1",
        "error_id": ERROR,
        "root": 0,
        "nodes": nodes,
        "omissions": [],
        "omission_overflow": None,
    }


@pytest.mark.parametrize(
    "nodes",
    [
        [graph_node(0), graph_node(1)],
        [graph_node(0, cause=2), graph_node(1), graph_node(2, cause=1)],
        [graph_node(0, cause=1), graph_node(3)],
        [graph_node(0, cause=True)],
        [graph_node(0, cause=-1)],
        [graph_node(0, cause=1)],
        [graph_node(0, group_children=[])],
        [graph_node(0, **{"class": "exception-group"})],
        [graph_node(0, **{"class": "exception-group", "group_children": []})],
        [graph_node(0, **{"class": "opaque"})],
        [graph_node(0, suppress_context=1)],
        [graph_node(0, **{"class": "invented"})],
        [graph_node(0, **{"class": "exception-group", "group_children": [None]})],
    ],
)
def test_decoder_rejects_unreachable_reordered_or_inconsistent_graphs(
    nodes: list[dict[str, Any]],
) -> None:
    with pytest.raises(pe.ProcessEvidenceError):
        pe.decode_error_graph(encoded(graph_document(nodes)))


@pytest.mark.parametrize("length,accepted", [(16, True), (17, True), (18, False)])
def test_retained_decoder_depth_boundary(length: int, accepted: bool) -> None:
    nodes = [graph_node(i, cause=i + 1 if i + 1 < length else None) for i in range(length)]
    raw = encoded(graph_document(nodes))
    if accepted:
        assert len(plain(pe.decode_error_graph(raw))["nodes"]) == length
    else:
        with pytest.raises(pe.ProcessEvidenceError):
            pe.decode_error_graph(raw)


@pytest.mark.parametrize("count,accepted", [(31, True), (32, True), (33, False)])
def test_retained_decoder_node_boundary(count: int, accepted: bool) -> None:
    root = graph_node(0, **{"class": "exception-group", "group_children": list(range(1, count))})
    raw = encoded(graph_document([root] + [graph_node(i) for i in range(1, count)]))
    if accepted:
        pe.decode_error_graph(raw)
    else:
        with pytest.raises(pe.ProcessEvidenceError):
            pe.decode_error_graph(raw)


@pytest.mark.parametrize("edges,accepted", [(95, True), (96, True), (97, False)])
def test_retained_decoder_counts_repeated_edges(edges: int, accepted: bool) -> None:
    nodes = [
        graph_node(i, **{"class": "exception-group", "group_children": [0] * 32}) for i in range(3)
    ]
    nodes[0]["group_children"][0] = 1
    nodes[1]["group_children"][0] = 2
    if edges == 95:
        nodes[2]["group_children"].pop()
    elif edges == 97:
        nodes[2]["cause"] = 0
    raw = encoded(graph_document(nodes))
    if accepted:
        pe.decode_error_graph(raw)
    else:
        with pytest.raises(pe.ProcessEvidenceError):
            pe.decode_error_graph(raw)


@pytest.mark.parametrize(
    "argument",
    [
        {"kind": "int", "value": True},
        {"kind": "bool", "value": 1},
        {"kind": "null", "value": None},
        {"kind": "bytes", "base64": "YQ"},
        {"kind": "bytes", "base64": "YR=="},
        {"kind": "bytes", "base64": "YQ==\n"},
        {"kind": "text", "value": "x" * 513},
        {"kind": "object", "value": {}},
        {"kind": "text", "base64": "YQ=="},
        {"kind": "int"},
    ],
)
def test_retained_argument_variants_are_closed(argument: dict[str, Any]) -> None:
    raw = encoded(graph_document([graph_node(0, args=[argument])]))
    with pytest.raises(pe.ProcessEvidenceError):
        pe.decode_error_graph(raw)


@pytest.mark.parametrize("count,accepted", [(7, True), (8, True), (9, False)])
def test_retained_args_per_node_boundary(count: int, accepted: bool) -> None:
    raw = encoded(graph_document([graph_node(0, args=[{"kind": "null"}] * count)]))
    if accepted:
        pe.decode_error_graph(raw)
    else:
        with pytest.raises(pe.ProcessEvidenceError):
            pe.decode_error_graph(raw)


@pytest.mark.parametrize("count,accepted", [(31, True), (32, True), (33, False)])
def test_retained_aggregate_arg_boundary(count: int, accepted: bool) -> None:
    nodes = [graph_node(i, cause=i + 1 if i < 4 else None) for i in range(5)]
    for i in range(count):
        nodes[i // 8]["args"].append({"kind": "null"})
    if accepted:
        pe.decode_error_graph(encoded(graph_document(nodes)))
    else:
        with pytest.raises(pe.ProcessEvidenceError):
            pe.decode_error_graph(encoded(graph_document(nodes)))


@pytest.mark.parametrize(
    "loss",
    [
        {"node": True, "field": "args", "reason": "items"},
        {"node": 1, "field": "args", "reason": "items"},
        {"node": 0, "field": "args", "reason": "nodes"},
        {"node": 0, "field": "cause", "reason": "opaque-type"},
        {"node": 0, "field": "class", "reason": "opaque-type"},
        {"node": 0, "field": "other", "reason": "items"},
    ],
)
def test_retained_omission_pairs_and_references(loss: dict[str, Any]) -> None:
    doc = graph_document([graph_node(0)])
    doc["omissions"] = [loss]
    with pytest.raises(pe.ProcessEvidenceError):
        pe.decode_error_graph(encoded(doc))


@pytest.mark.parametrize(
    "footer",
    [
        {},
        {"additional_details_at_least": True, "exact_count": None, "enumeration": "incomplete"},
        {"additional_details_at_least": 1, "exact_count": 2, "enumeration": "incomplete"},
        {"additional_details_at_least": 2, "exact_count": None, "enumeration": "incomplete"},
        {"additional_details_at_least": 1, "exact_count": None, "enumeration": "complete"},
    ],
)
def test_retained_overflow_footer_is_exact(footer: dict[str, Any]) -> None:
    doc = graph_document([graph_node(0)])
    doc["omission_overflow"] = footer
    with pytest.raises(pe.ProcessEvidenceError):
        pe.decode_error_graph(encoded(doc))


def test_overflow_can_explain_missing_class_or_group_details() -> None:
    doc = graph_document([graph_node(0, **{"class": "opaque", "group_children": []})])
    doc["omission_overflow"] = pe._overflow()
    assert plain(pe.decode_error_graph(encoded(doc))) == doc


def test_suppression_without_cause_is_a_real_state() -> None:
    error = ValueError()
    error.__suppress_context__ = True
    row = graph(error)
    assert row["nodes"][0]["cause"] is None
    assert row["nodes"][0]["suppress_context"] is True


def test_graph_byte_value_reservation_records_fitting_detail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Force the same admission branch independently of incidental class text sizes.
    original = pe._Graph._fits

    def fits(instance: Any) -> bool:
        return len(instance.document["nodes"]) < 3 and original(instance)

    monkeypatch.setattr(pe._Graph, "_fits", fits)
    root = ValueError()
    root.__cause__ = ValueError()
    root.__cause__.__cause__ = ValueError()
    row = graph(root)
    assert len(row["nodes"]) == 2
    assert row["omissions"] == [{"node": 1, "field": "cause", "reason": "bytes"}]
    assert row["omission_overflow"] is None
    assert row["nodes"][1]["cause"] is None
    assert len(encoded(row)) < 8192


@pytest.mark.parametrize(
    "field,value",
    [
        ("schema", "wrong"),
        ("scope", "inner-worker"),
        ("attempt_id", "bad"),
        ("call_sequence", True),
        ("operation", "logs"),
        ("target", "other"),
        ("intent_event_digest", "A" * 64),
        ("unavailable_reason", "exception-no-outcome"),
        ("error_id", ERROR),
        ("outcome", None),
    ],
)
def test_result_decoder_closed_header_and_pairing(field: str, value: Any) -> None:
    row = document(result())
    row[field] = value
    with pytest.raises(pe.ProcessEvidenceError):
        pe.decode_call_result(encoded(row))


@pytest.mark.parametrize(
    "field,value",
    [
        ("sha256", "A" * 64),
        ("size", True),
        ("size", -1),
        ("size", 32769),
        ("key", "../../file"),
        ("key", "blobs/" + "a" * 64),
    ],
)
def test_call_ref_cannot_select_an_arbitrary_path(field: str, value: Any) -> None:
    call = plain(result().call_ref)
    call["outcome"][field] = value
    with pytest.raises(pe.ProcessEvidenceError):
        pe.decode_call_ref(encoded(call))


def test_zero_blob_ref_requires_actual_empty_hash() -> None:
    call = plain(result().call_ref)
    call["outcome"] = {"size": 0, "sha256": "0" * 64, "key": "blobs/" + "0" * 64}
    with pytest.raises(pe.ProcessEvidenceError):
        pe.decode_call_ref(encoded(call))
    call["outcome"] = {"size": 0, "sha256": sha(b"").hex(), "key": "blobs/" + sha(b"").hex()}
    pe.decode_call_ref(encoded(call))  # Only cross-blob readback can reject empty result bytes.


@pytest.mark.parametrize(
    "changes",
    [
        {"kind": "spool", "path": None},
        {"kind": "memory", "custody": {"state": "unavailable", "bytes": None}},
        {"custody": {"state": "diagnostic-copy", "bytes": None}},
        {"path": {"size": 0, "sha256": sha(b"").hex(), "key": "blobs/" + sha(b"").hex()}},
    ],
)
def test_result_decoder_rejects_inconsistent_output_custody(changes: dict[str, Any]) -> None:
    doc = document(result())
    doc["outcome"]["stdout"].update(changes)
    with pytest.raises(pe.ProcessEvidenceError):
        pe.decode_call_result(encoded(doc))


def test_cross_blob_input_relation_is_not_inferred_by_decoder() -> None:
    doc = document(result())
    doc["outcome"]["stdin_sent_bytes"] = 1
    # The decoder sees only an invocation reference, not its raw zero-input body.
    pe.decode_call_result(encoded(doc))
    with pytest.raises(pe.ProcessEvidenceError):
        result(outcome=altered(outcome(), stdin_sent_bytes=1))


@pytest.mark.parametrize("maximum", [512 * 1024 - 1, 512 * 1024, 512 * 1024 + 1])
def test_metadata_single_call_accounting_boundary(maximum: int) -> None:
    pack = pe._Pack()
    if maximum <= 512 * 1024:
        pack.charge_metadata(maximum)
    else:
        with pytest.raises(pe.ProcessEvidenceError):
            pack.charge_metadata(maximum)


def test_dedup_never_discounts_logical_metadata_work() -> None:
    pack = pe._Pack()
    data = b"x" * (256 * 1024)
    first = pack.add(data, 1048576)
    second = pack.add(data, 1048576)
    assert first == second and len(pack.blobs) == 1
    assert pack.physical == len(data) and pack.metadata == len(data) * 2
    with pytest.raises(pe.ProcessEvidenceError):
        pack.add(data, 1048576)


def test_eight_unique_blobs_maximum_and_exact_collision_guard(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pack = pe._Pack()
    for index in range(8):
        pack.add(bytes([index]), 1)
    with pytest.raises(pe.ProcessEvidenceError):
        pack.add(b"ninth", 8)

    # Hash equality alone cannot silently deduplicate different bytes.
    class FixedHash:
        def digest(self) -> bytes:
            return b"x" * 32

    monkeypatch.setattr(pe.hashlib, "sha256", lambda raw: FixedHash())
    second = pe._Pack()
    second.add(b"one", 3)
    with pytest.raises(pe.ProcessEvidenceError):
        second.add(b"two", 3)


def test_raw_stream_dedup_saves_storage_only() -> None:
    raw = b"x" * (16 * 1048576)
    observed = replace(outcome(), stdout=memory(raw), stderr=memory(raw))
    prepared = result(outcome=observed)
    row = document(prepared)["outcome"]
    assert row["stdout"]["reported"]["observed_bytes"] == len(raw)
    assert row["stderr"]["reported"]["observed_bytes"] == len(raw)
    assert row["stdout"]["custody"]["bytes"] == row["stderr"]["custody"]["bytes"]
    assert sum(len(blob.data) for blob in prepared.blobs) < 32 * 1048576


def test_distinct_maximum_streams_leave_no_room_for_required_metadata() -> None:
    observed = replace(
        outcome(), stdout=memory(b"x" * (16 * 1048576)), stderr=memory(b"y" * (16 * 1048576))
    )
    with pytest.raises(pe.ProcessEvidenceError):
        result(outcome=observed)


def test_pure_code_never_calls_filesystem_clock_or_process(monkeypatch: pytest.MonkeyPatch) -> None:
    import builtins
    import os
    import subprocess
    import time

    intended = pe.prepare_call_intent(binding(), invocation())
    actual = outcome()

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("impure operation")

    with monkeypatch.context() as guard:
        for module, name in (
            (builtins, "open"),
            (os, "open"),
            (os, "stat"),
            (os, "fstat"),
            (subprocess, "Popen"),
            (time, "time"),
            (time, "monotonic"),
        ):
            guard.setattr(module, name, forbidden)
        prepared = pe.prepare_call_result(
            intended, intent_event_digest=b"i" * 32, outcome=actual, error=None, error_id=None
        )
        pe.decode_call_ref(encoded(plain(prepared.call_ref)))
    assert prepared.blobs


def test_stored_views_contain_only_exact_immutable_primitives() -> None:
    view = pe.decode_call_result(
        next(blob.data for blob in result().blobs if blob.data.startswith(b'{"attempt_id"'))
    )

    def check(item: Any) -> None:
        if type(item) is tuple:
            tag, members = item
            assert type(members) is tuple
            if tag == "object":
                assert tuple(key for key, _ in members) == tuple(sorted(key for key, _ in members))
                for key, value in members:
                    assert type(key) is str
                    check(value)
            else:
                assert tag == "array"
                for value in members:
                    check(value)
        else:
            assert item is None or type(item) in (bool, int, str)

    check(view)


def test_carrier_mismatch_in_exact_memory_bytes_and_spool_path() -> None:
    first = replace(outcome(), stdout=memory(b"one"))
    second = replace(outcome(), stdout=memory(b"two"))
    with pytest.raises(pe.ProcessEvidenceError):
        result(outcome=second, error=ProcessTransportError(first), error_id=ERROR)
    first = replace(
        outcome(),
        stdout=SpoolOutput(StreamEvidence(0, None, None, False, False), PosixPath("/a/one")),
        cleanup="incomplete",
    )
    second = replace(
        first, stdout=SpoolOutput(StreamEvidence(0, None, None, False, False), PosixPath("/a/two"))
    )
    with pytest.raises(pe.ProcessEvidenceError):
        result(outcome=second, error=ProcessTransportError(first), error_id=ERROR)


@pytest.mark.parametrize(
    "bad", ["\\"] + [chr(code) for code in range(1, 32)] + [chr(code) for code in range(127, 160)]
)
def test_root_review_intended_path_controls_preserve_actual_diagnostics(bad: str) -> None:
    cwd = "/private/jobs" + bad + "/" + ATTEMPT
    base = invocation()
    environment = dict(base.environment)
    for key, child in (("HOME", "cli-home"), ("TMPDIR", "cli-tmp"), ("PATH", "cli-bin")):
        environment[key] = cwd + "/" + child
    candidate = replace(base, cwd=cwd, environment=tuple(sorted(environment.items())))
    # The initial Docker intent policy is narrower than actual shared evidence.
    with pytest.raises(pe.ProcessEvidenceError):
        pe.prepare_call_intent(binding(), candidate)
    raw = pe.encode_invocation(candidate)
    assert plain(pe.decode_invocation(raw))["cwd"] == cwd
    prepared = result(outcome=replace(outcome(), invocation=candidate))
    doc = document(prepared)
    assert doc["outcome"]["invocation"]["sha256"] == sha(raw).hex()
    assert any(blob.data == raw for blob in prepared.blobs)


@pytest.mark.parametrize("index", range(len(pe._CLASS_CODES)))
def test_exact_known_error_class_codes(index: int) -> None:
    cls, code = pe._CLASS_CODES[index]
    if cls in (ExceptionGroup, BaseExceptionGroup):
        children = [KeyboardInterrupt()] if cls is BaseExceptionGroup else [ValueError()]
        error = cls("group", children)
    elif cls is ProcessTransportError:
        error = cls(outcome())
    else:
        error = cls()
    raw = pe._Graph(ERROR).encode(error)
    assert plain(pe.decode_error_graph(raw))["nodes"][0]["class"] == code


@pytest.mark.parametrize("which", ["stdout", "stderr"])
def test_missing_stream_and_unknown_spool_are_not_known_empty(which: str) -> None:
    observed = replace(outcome(), cleanup="incomplete", **{which: None})
    row = document(result(outcome=observed))["outcome"]
    assert row[which] is None
    spool = SpoolOutput(StreamEvidence(0, None, None, False, False), PosixPath("/private/file"))
    observed = replace(observed, **{which: spool})
    row = document(result(outcome=observed))["outcome"]
    assert row[which]["reported"]["retained_bytes"] is None
    assert row[which]["reported"]["retained_sha256"] is None
    assert row[which]["custody"] == {"state": "unavailable", "bytes": None}


def test_exact_not_started_preserves_no_acknowledged_child() -> None:
    observed = replace(
        outcome(),
        pid=None,
        pgid=None,
        returncode=None,
        stdout=None,
        stderr=None,
        cleanup="not_started",
        reason="spawn_error",
    )
    row = document(result(outcome=observed))["outcome"]
    assert row["pid"] is None and row["pgid"] is None and row["returncode"] is None
    assert row["cleanup"] == "not_started"


@pytest.mark.parametrize(
    "changes",
    [
        {"pid": None},
        {"cleanup": "not_started"},
        {"returncode": None},
        {"stdout": None},
        {"stderr": None},
    ],
)
def test_cross_field_child_cleanup_invariants(changes: dict[str, Any]) -> None:
    with pytest.raises(pe.ProcessEvidenceError):
        result(outcome=altered(outcome(), **changes))


@pytest.mark.parametrize("field,value", [("eof", False), ("truncated", True)])
def test_completed_exited_requires_complete_streams(field: str, value: Any) -> None:
    observed = outcome()
    altered(observed.stdout.evidence, **{field: value})
    with pytest.raises(pe.ProcessEvidenceError):
        result(outcome=observed)
    altered(observed, reason="timeout")
    assert document(result(outcome=observed))["outcome"]["reason"] == "timeout"


@pytest.mark.parametrize("total,accepted", [(65535, True), (65536, True), (65537, False)])
def test_environment_aggregate_boundary(total: int, accepted: bool) -> None:
    environment = [(f"k{i}", "x" * 8192) for i in range(7)]
    remaining = total - sum(len(key) + len(value) + 2 for key, value in environment) - 4
    environment.append(("k7", "x" * remaining))
    candidate = altered(invocation(), environment=tuple(environment))
    if accepted:
        pe.encode_invocation(candidate)
    else:
        with pytest.raises(pe.ProcessEvidenceError):
            pe.encode_invocation(candidate)


@pytest.mark.parametrize("count,accepted", [(4095, True), (4096, True), (4097, False)])
def test_actual_path_byte_boundary(count: int, accepted: bool) -> None:
    candidate = altered(invocation(), cwd="/" + "x" * (count - 1))
    if accepted:
        pe.encode_invocation(candidate)
    else:
        with pytest.raises(pe.ProcessEvidenceError):
            pe.encode_invocation(candidate)


def test_derived_intent_paths_have_independent_cap() -> None:
    cwd = "/" + "x" * (4090 - len(ATTEMPT) - 2) + "/" + ATTEMPT
    env = dict(invocation().environment)
    for key, suffix in (("HOME", "/cli-home"), ("TMPDIR", "/cli-tmp"), ("PATH", "/cli-bin")):
        env[key] = cwd + suffix
    candidate = replace(invocation(), cwd=cwd, environment=tuple(sorted(env.items())))
    pe.encode_invocation(candidate)
    with pytest.raises(pe.ProcessEvidenceError):
        pe.prepare_call_intent(binding(), candidate)


def test_opaque_args_exhaustion_stops_without_touching_later_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    roots = [ValueError(*([Poison()] * 8)) for _ in range(6)]
    for first, second in itertools.pairwise(roots):
        first.__cause__ = second
    forbidden_id = id(roots[-1])
    original = pe._error_field

    def field(error: BaseException, name: str) -> Any:
        assert id(error) != forbidden_id
        return original(error, name)

    monkeypatch.setattr(pe, "_error_field", field)
    row = graph(roots[0])
    assert len(row["omissions"]) == 32 and row["omission_overflow"] is not None


def test_actual_graph_byte_budget_overflow_keeps_decodable_prefix() -> None:
    class OpaqueError(Exception):
        pass

    children = [OpaqueError() for _ in range(31)]
    root = ExceptionGroup("x" * 512, children)
    # Spend the argument allowance without spending the class-omission allowance.
    children[0].args = ("y" * 512, "z" * 512, "w" * 400)
    row = graph(root)
    assert row["omission_overflow"] is not None
    assert len(row["nodes"]) < 32 or len(row["omissions"]) < 32
    assert len(encoded(row)) <= 8192


def test_peer_review_real_edge_budget_records_fitting_loss_detail() -> None:
    class OpaqueError(Exception):
        pass

    children = [OpaqueError() for _ in range(31)]
    root = ExceptionGroup("x" * 256, children)
    children[0].args = ("y" * 512, "z" * 512, "w" * 400)
    row = graph(root)
    assert {"node": 0, "field": "group", "reason": "bytes"} in row["omissions"]
    assert len(encoded(row)) <= 8192


def test_peer_review_argument_budget_records_fitting_loss_and_continues(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = pe._Graph._fits

    def fits(instance: Any) -> bool:
        args = instance.document["nodes"][0]["args"]
        return not any(item.get("value") == "over-budget" for item in args) and original(instance)

    monkeypatch.setattr(pe._Graph, "_fits", fits)
    row = graph(ValueError("over-budget", "retained"))
    assert row["omissions"] == [{"node": 0, "field": "args", "reason": "bytes"}]
    assert row["nodes"][0]["args"] == [{"kind": "text", "value": "retained"}]
    assert row["omission_overflow"] is None
