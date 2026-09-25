"""Portable canonical storage envelopes; raw detection bytes are not JSON values."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, cast
from uuid import UUID

from analysis.artifact_identity import validate_identity_metadata

from ._schemas import MAX_COUNT, MAX_DEPTH, MAX_ENVELOPE, PREFIX, SCHEMAS


class EnvelopeError(ValueError):
    """Malformed, ambiguous, unsupported or noncanonical storage input."""


def _scalar(value: object, depth: int = 0) -> None:
    if depth > MAX_DEPTH:
        raise EnvelopeError("envelope nesting exceeds 32")
    if value is None or type(value) is bool:
        return
    if type(value) is int:
        if not -(2**63) <= value < 2**63:
            raise EnvelopeError("integer outside signed 64-bit domain")
        return
    if type(value) is str:
        if len(value) > MAX_ENVELOPE:
            raise EnvelopeError("envelope string exceeds byte bound")
        if "\x00" in value or any(0xD800 <= ord(c) <= 0xDFFF for c in value):
            raise EnvelopeError("strings must be Unicode scalars without NUL")
        return
    if type(value) is list:
        for item in value:
            _scalar(item, depth + 1)
        return
    if type(value) is dict:
        for key, item in value.items():
            if type(key) is not str:
                raise EnvelopeError("object keys must be strings")
            _scalar(key, depth + 1)
            _scalar(item, depth + 1)
        return
    raise EnvelopeError("unsupported envelope value")


def _path(value: str) -> bool:
    return (
        bool(value)
        and "\\" not in value
        and all(p not in ("", ".", "..") for p in value.split("/"))
    )


def _shape(value: Any, shape: Any) -> None:  # noqa: ANN401 -- recursive validated JSON DSL
    if isinstance(shape, dict):
        if "$nullable" in shape:
            if value is not None:
                _shape(value, shape["$nullable"])
        elif "$enum" in shape:
            if not any(type(value) is type(item) and value == item for item in shape["$enum"]):
                raise EnvelopeError("invalid enum")
        elif "$array" in shape:
            if type(value) is not list:
                raise EnvelopeError("expected array")
            for item in value:
                _shape(item, shape["$array"])
        else:
            if type(value) is not dict or set(value) != set(shape):
                raise EnvelopeError("missing or unknown envelope field")
            for key, child in shape.items():
                _shape(value[key], child)
        return
    if shape == "bool":
        valid = type(value) is bool
    elif shape in ("nat", "positive") or shape.startswith("int:"):
        low, high = ((0 if shape == "nat" else 1), 2**63 - 1)
        if shape.startswith("int:"):
            _, lower, upper = shape.split(":")
            low, high = int(lower), int(upper)
        valid = type(value) is int and low <= value <= high
    else:
        valid = type(value) is str
        if valid:
            if shape == "nonempty":
                valid = bool(value)
            elif shape == "digest":
                valid = re.fullmatch(r"[0-9a-f]{64}", value) is not None
            elif shape == "env":
                valid = re.fullmatch(r"sha256:[0-9a-f]{64}", value) is not None
            elif shape == "commit":
                valid = re.fullmatch(r"[0-9a-f]{40}", value) is not None and value != "0" * 40
            elif shape == "uuid":
                try:
                    valid = str(UUID(value)) == value
                except ValueError:
                    valid = False
            elif shape == "path":
                valid = _path(value)
            elif shape != "text":
                raise EnvelopeError("unknown shape validator")
    if not valid:
        raise EnvelopeError(f"invalid {shape} value")


def _unique(values: list[Any], label: str) -> None:
    if len(set(values)) != len(values):
        raise EnvelopeError(f"duplicate {label}")


def _location(value: dict[str, Any]) -> None:
    path, start, column, end, end_column = (
        value[key] for key in ("path", "start_line", "start_column", "end_line", "end_column")
    )
    observed = any(item is not None for item in (path, start, column, end, end_column))
    known = path is not None and start is not None
    expected = "known" if known else "partial" if observed else "unknown"
    if value["status"] != expected:
        raise EnvelopeError("location status contradicts observed fields")
    if (column is not None and start is None) or (end_column is not None and end is None):
        raise EnvelopeError("location column requires its observed line")
    if end is not None and (start is None or end < start):
        raise EnvelopeError("end location requires ordered observed start")
    if end == start and end_column is not None and (column is None or end_column < column):
        raise EnvelopeError("same-line end requires ordered observed start column")


def _semantic(name: str, value: dict[str, Any]) -> None:
    if name in ("request", "retry-policy"):
        retry = value["retry_policy"] if name == "request" else value
        if retry["initial_backoff_seconds"] > retry["max_backoff_seconds"]:
            raise EnvelopeError("initial backoff exceeds maximum")
    if name in ("request", "work-payload", "planned-policy"):
        policy = value["policy"] if name == "work-payload" else value["identity_policy"]
        if policy["mode"] == "not-applicable" and policy["reason"] is None:
            raise EnvelopeError("not-applicable requires explicit policy reason")
    if name == "work-payload":
        if (value["kind"] == "identity") != (value["occurrence_id"] is not None):
            raise EnvelopeError("work kind and occurrence disagree")
    if name == "source-inventory":
        paths = [item["path"] for item in value["files"]]
        _unique(paths, "file path")
        if paths != sorted(paths):
            raise EnvelopeError("inventory paths must be sorted")
    if name in ("seal", "planned-policy"):
        if name == "seal":
            _unique(value["intended_files"], "intended file")
        _unique([item["key"] for item in value["bindings"]], "binding key")
        for binding in value["bindings"]:
            if not binding["engines"] or not binding["rules"]:
                raise EnvelopeError("binding requires engines and rules")
            _unique(binding["engines"], "engine")
            _unique([item["rule_id"] for item in binding["rules"]], "rule")
    if name in ("detection-batch", "occurrence-inventory"):
        rows = value["occurrences"]
        if len(rows) > MAX_COUNT:
            raise EnvelopeError("occurrence count limit")
        _unique([(row["result_key"], row["duplicate_ordinal"]) for row in rows], "occurrence key")
        if [row["tool_ordinal"] for row in rows] != list(range(len(rows))):
            raise EnvelopeError("tool ordinals must preserve contiguous returned order")
        for row in rows:
            _location(row["location"])
    if name == "detection-batch":
        coverage = value["coverage"]
        _unique(coverage["files"], "covered file")
        _unique(coverage["rules"], "covered rule")
        if value["status"] == "completed" and (
            coverage["status"] != "complete" or coverage["errors"]
        ):
            raise EnvelopeError("completed run requires complete error-free coverage")
        if (
            value["inventory_digest"]
            != encode_envelope(
                "occurrence-inventory",
                {"schema": PREFIX + "occurrence-inventory/1", "occurrences": value["occurrences"]},
            ).digest.hex()
        ):
            raise EnvelopeError("occurrence inventory digest mismatch")
    if name == "attempt-result":
        _unique(value["completed_run_ids"], "completed run ID")
        if value["identity"] is not None:
            validate_identity_metadata(value["identity"])
        if value["status"] == "completed" and (value["retryable"] or value["error"] is not None):
            raise EnvelopeError("completed attempt cannot report retry/error")
        if value["status"] == "failed" and value["error"] is None:
            raise EnvelopeError("failed attempt requires error")


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise EnvelopeError("duplicate JSON key")
        result[key] = value
    return result


def _integer(token: str) -> int:
    if len(token) > 20:
        raise EnvelopeError("integer outside signed 64-bit domain")
    result = int(token)
    if not -(2**63) <= result < 2**63:
        raise EnvelopeError("integer outside signed 64-bit domain")
    return result


def _no_float(token: str) -> None:
    raise EnvelopeError(f"unsupported numeric token: {token[:32]}")


def _canonical(value: dict[str, Any]) -> bytes:
    _scalar(value)
    encoder = json.JSONEncoder(
        sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )
    result = bytearray()
    for chunk in encoder.iterencode(value):
        if len(chunk) > MAX_ENVELOPE:
            raise EnvelopeError("envelope size limit")
        encoded = chunk.encode("utf-8")
        if len(result) + len(encoded) > MAX_ENVELOPE:
            raise EnvelopeError("envelope size limit")
        result.extend(encoded)
    return bytes(result)


def decode_envelope(name: str, data: bytes, digest: bytes | None = None) -> dict[str, Any]:
    if name not in SCHEMAS or type(data) is not bytes or len(data) > MAX_ENVELOPE:
        raise EnvelopeError("unsupported schema, bytes type or envelope size")
    try:
        value = json.loads(
            data.decode("utf-8"),
            object_pairs_hook=_pairs,
            parse_int=_integer,
            parse_float=_no_float,
            parse_constant=_no_float,
        )
        _scalar(value)
        _shape(value, SCHEMAS[name])
        _semantic(name, value)
        if _canonical(value) != data:
            raise EnvelopeError("noncanonical envelope bytes")
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise EnvelopeError("invalid envelope encoding") from exc
    expected = hashlib.sha256((PREFIX + name + "/1\n").encode("ascii") + data).digest()
    if digest is not None and (type(digest) is not bytes or digest != expected):
        raise EnvelopeError("envelope digest mismatch")
    return cast(dict[str, Any], value)


@dataclass(frozen=True)
class CanonicalEnvelope:
    name: str
    data: bytes
    digest: bytes

    def __post_init__(self) -> None:
        decode_envelope(self.name, self.data, self.digest)

    @property
    def value(self) -> dict[str, Any]:
        return decode_envelope(self.name, self.data, self.digest)


def encode_envelope(name: str, value: dict[str, Any]) -> CanonicalEnvelope:
    data = _canonical(value)
    digest = hashlib.sha256((PREFIX + name + "/1\n").encode("ascii") + data).digest()
    return CanonicalEnvelope(name, data, digest)
