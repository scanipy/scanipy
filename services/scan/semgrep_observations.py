"""Bounded, data-only Semgrep observations; never an execution/coverage certificate.

Contract: docs/bhmea/SEMGREP-OBSERVATIONS-CONTRACT.md. No source path is opened,
no result is deduplicated, and no canonical graph/slice identity is produced.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Literal, cast

PROFILE = "scanipy-semgrep-observations/1"
VERSION = "1.175.0"
RAW_RESULT_NAMESPACE = "scanipy-semgrep-raw-result/1"
_SEVERITIES = frozenset(
    {"ERROR", "WARNING", "EXPERIMENT", "INVENTORY", "CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"}
)
_FIELDS = frozenset(
    {
        "version",
        "results",
        "errors",
        "paths",
        "time",
        "explanations",
        "rules_by_engine",
        "engine_requested",
        "interfile_languages_used",
        "skipped_rules",
        "subprojects",
        "mcp_scan_results",
        "profiling_results",
    }
)
_NUMBER = re.compile(rb"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?")
_SPACE = b" \t\r\n"


class ObservationInputError(ValueError):
    """Invalid caller input; no claimed scan outcome."""


class ObservationLimitError(ObservationInputError):
    """A named profile limit was exceeded; input custody remains with the caller."""

    def __init__(self, resource: str, observed: int, limit: int) -> None:
        self.resource, self.observed, self.limit = resource, observed, limit
        super().__init__(f"{resource} limit exceeded: {observed} > {limit}")


@dataclass(frozen=True, slots=True)
class ObservationLimits:
    max_stdout_bytes: int = 16 * 1024 * 1024
    max_stderr_bytes: int = 1024 * 1024
    max_result_bytes: int = 1024 * 1024
    max_results: int = 10_000
    max_depth: int = 32
    max_values: int = 250_000

    def __post_init__(self) -> None:
        for name, ceiling in (
            ("max_stdout_bytes", 16 * 1024 * 1024),
            ("max_stderr_bytes", 1024 * 1024),
            ("max_result_bytes", 1024 * 1024),
            ("max_results", 10_000),
            ("max_depth", 32),
            ("max_values", 250_000),
        ):
            value = getattr(self, name)
            if type(value) is not int or not 0 < value <= ceiling:
                raise ObservationInputError(f"{name} must be a positive integer at most {ceiling}")


@dataclass(frozen=True, slots=True)
class Issue:
    code: str
    field: str


@dataclass(frozen=True, slots=True)
class RawSpan:
    """Exact half-open byte range in the report's retained stdout."""

    start: int
    end: int
    data: bytes

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.data).hexdigest()


@dataclass(frozen=True, slots=True)
class Position:
    line: int
    column: int
    offset_present: bool
    offset: int | None


@dataclass(frozen=True, slots=True)
class MatchProjection:
    """Selected native fields only; not full native schema or a final Finding."""

    rule_id: str
    path: str
    start: Position
    end: Position
    message: str
    severity: str

    @property
    def engine(self) -> Literal["semgrep"]:
        return "semgrep"

    @property
    def origin(self) -> Literal["oracle-passthrough"]:
        return "oracle-passthrough"


@dataclass(frozen=True, slots=True)
class ResultObservation:
    tool_ordinal: int
    raw: RawSpan
    duplicate_ordinal: int
    projection: MatchProjection | None
    issues: tuple[Issue, ...]

    @property
    def disposition(self) -> Literal["projected", "rejected"]:
        return "projected" if self.projection is not None else "rejected"

    @property
    def raw_result_key(self) -> str:
        return RAW_RESULT_NAMESPACE + ":" + self.raw.sha256


@dataclass(frozen=True, slots=True)
class FieldObservation:
    name: str
    state: Literal["missing", "present", "null", "invalid"]
    raw: RawSpan | None
    recognized: bool


@dataclass(frozen=True, slots=True)
class SemgrepObservations:
    stdout: bytes
    stderr: bytes
    returncode: int
    parse_status: Literal["parsed", "invalid-report"]
    version: str | None
    version_status: Literal["matched", "missing", "mismatched", "invalid"]
    results_status: Literal["present", "missing", "invalid"]
    result_count: int | None
    results: tuple[ResultObservation, ...]
    fields: tuple[FieldObservation, ...]
    issues: tuple[Issue, ...]

    @property
    def profile(self) -> str:
        return PROFILE

    @property
    def stdout_byte_length(self) -> int:
        return len(self.stdout)

    @property
    def stderr_byte_length(self) -> int:
        return len(self.stderr)

    @property
    def stdout_sha256(self) -> str:
        return hashlib.sha256(self.stdout).hexdigest()

    @property
    def stderr_sha256(self) -> str:
        return hashlib.sha256(self.stderr).hexdigest()

    @property
    def coverage_status(self) -> Literal["unverified"]:
        return "unverified"


@dataclass(frozen=True, slots=True)
class _Value:
    start: int
    end: int
    kind: str
    value: object


class _MalformedError(ValueError):
    pass


class _Parser:
    """Bounded JSON grammar with byte spans; numbers remain exact ASCII tokens.

    Each value and object key is counted before materialization. A string token
    delegates escape/Unicode grammar to the standard JSON decoder, never eval.
    """

    def __init__(self, data: bytes, limits: ObservationLimits) -> None:
        self.data, self.limits = data, limits
        self.pos = 0
        self.values = 0

    def _count(self) -> None:
        self.values += 1
        if self.values > self.limits.max_values:
            raise ObservationLimitError("json-values", self.values, self.limits.max_values)

    def _space(self) -> None:
        while self.pos < len(self.data) and self.data[self.pos] in _SPACE:
            self.pos += 1

    def _take(self, token: int) -> None:
        self._space()
        if self.pos >= len(self.data) or self.data[self.pos] != token:
            raise _MalformedError("invalid-json-delimiter")
        self.pos += 1

    def _string(self) -> str:
        start = self.pos
        self._take(34)
        while self.pos < len(self.data):
            character = self.data[self.pos]
            self.pos += 1
            if character == 92:
                self.pos += 1
            elif character == 34:
                try:
                    value = json.loads(self.data[start : self.pos].decode("utf-8"))
                    if type(value) is not str:
                        raise _MalformedError("invalid-json-string")
                    value.encode("utf-8")
                except (ValueError, UnicodeError) as exc:
                    raise _MalformedError("invalid-json-string") from exc
                return value
        raise _MalformedError("unterminated-json-string")

    def value(self, depth: int = 0) -> _Value:
        self._space()
        self._count()
        start = self.pos
        if start >= len(self.data):
            raise _MalformedError("missing-json-value")
        token = self.data[start]
        if token == 34:
            string_value = self._string()
            return _Value(start, self.pos, "string", string_value)
        if token in (123, 91):
            depth += 1
            if depth > self.limits.max_depth:
                raise ObservationLimitError("json-depth", depth, self.limits.max_depth)
            self.pos += 1
            self._space()
            closing = 125 if token == 123 else 93
            items: list[object] = []
            keys: set[str] = set()
            if self.pos < len(self.data) and self.data[self.pos] == closing:
                self.pos += 1
            else:
                while True:
                    if token == 123:
                        self._space()
                        self._count()
                        key = self._string()
                        if key in keys:
                            raise _MalformedError("duplicate-json-key")
                        keys.add(key)
                        self._take(58)
                        items.append((key, self.value(depth)))
                    else:
                        items.append(self.value(depth))
                    self._space()
                    if self.pos < len(self.data) and self.data[self.pos] == closing:
                        self.pos += 1
                        break
                    self._take(44)
            return _Value(start, self.pos, "object" if token == 123 else "array", tuple(items))
        for literal, kind, value in (
            (b"true", "bool", True),
            (b"false", "bool", False),
            (b"null", "null", None),
        ):
            if self.data.startswith(literal, start):
                self.pos += len(literal)
                return _Value(start, self.pos, kind, value)
        number = _NUMBER.match(self.data, start)
        if number is None:
            raise _MalformedError("invalid-json-value")
        self.pos = number.end()
        # Retain lexical numeric bytes; large finite telemetry never rounds to inf.
        return _Value(start, self.pos, "number", self.data[start : self.pos])

    def parse(self) -> _Value:
        root = self.value()
        self._space()
        if self.pos != len(self.data):
            raise _MalformedError("trailing-json-input")
        if root.kind != "object":
            raise _MalformedError("report-is-not-object")
        return root


def _object(value: _Value) -> dict[str, _Value]:
    return dict(cast(tuple[tuple[str, _Value], ...], value.value))


def _array(value: _Value) -> tuple[_Value, ...]:
    return cast(tuple[_Value, ...], value.value)


def _span(value: _Value, stdout: bytes) -> RawSpan:
    return RawSpan(value.start, value.end, stdout[value.start : value.end])


def _text(value: _Value | None, field: str, *, empty: bool = False) -> str:
    if value is None or value.kind != "string":
        raise _MalformedError(field)
    text = cast(str, value.value)
    if (not empty and not text.strip()) or "\x00" in text:
        raise _MalformedError(field)
    return text


def _integer(value: _Value | None, field: str, *, low: int) -> int:
    if value is None or value.kind != "number":
        raise _MalformedError(field)
    token = cast(bytes, value.value)
    if len(token) > 20 or re.fullmatch(rb"-?(?:0|[1-9][0-9]*)", token) is None:
        raise _MalformedError(field)
    number = int(token)
    if not low <= number <= 2**63 - 1:
        raise _MalformedError(field)
    return number


def _position(value: _Value | None, field: str) -> Position:
    if value is None or value.kind != "object":
        raise _MalformedError(field)
    obj = _object(value)
    if set(obj) - {"line", "col", "offset"}:
        raise _MalformedError(field + ".unknown-field")
    return Position(
        _integer(obj.get("line"), field + ".line", low=1),
        _integer(obj.get("col"), field + ".col", low=1),
        "offset" in obj,
        _integer(obj["offset"], field + ".offset", low=-1) if "offset" in obj else None,
    )


def _project(value: _Value) -> MatchProjection:
    if value.kind != "object":
        raise _MalformedError("result")
    obj = _object(value)
    extra = obj.get("extra")
    if extra is None or extra.kind != "object":
        raise _MalformedError("extra")
    fields = _object(extra)
    start, end = _position(obj.get("start"), "start"), _position(obj.get("end"), "end")
    if (end.line, end.column) < (start.line, start.column):
        raise _MalformedError("end-before-start")
    if start.offset is not None and end.offset is not None and min(start.offset, end.offset) >= 0:
        if end.offset < start.offset:
            raise _MalformedError("end-offset-before-start")
    severity = _text(fields.get("severity"), "extra.severity")
    if severity not in _SEVERITIES:
        raise _MalformedError("extra.severity.unsupported")
    return MatchProjection(
        _text(obj.get("check_id"), "check_id"),
        _text(obj.get("path"), "path"),
        start,
        end,
        _text(fields.get("message"), "extra.message", empty=True),
        severity,
    )


def _telemetry_valid(name: str, value: _Value) -> bool:
    if name in {"errors", "skipped_rules", "subprojects", "explanations", "profiling_results"}:
        return value.kind == "array" and all(item.kind == "object" for item in _array(value))
    if name == "interfile_languages_used":
        return value.kind == "array" and all(item.kind == "string" for item in _array(value))
    if name == "engine_requested":
        return value.kind == "string" and value.value in ("OSS", "PRO")
    if name == "rules_by_engine":
        return value.kind == "array" and all(
            item.kind == "array"
            and len(_array(item)) == 2
            and _array(item)[0].kind == "string"
            and bool(_array(item)[0].value)
            and _array(item)[1].kind == "string"
            and _array(item)[1].value in ("OSS", "PRO")
            for item in _array(value)
        )
    if name == "paths":
        if value.kind != "object":
            return False
        fields = _object(value)
        scanned, skipped = fields.get("scanned"), fields.get("skipped")
        return (
            not (set(fields) - {"scanned", "skipped"})
            and (
                scanned is not None
                and scanned.kind == "array"
                and all(item.kind == "string" for item in _array(scanned))
            )
            and (
                skipped is None
                or (
                    skipped.kind == "array"
                    and all(item.kind == "object" for item in _array(skipped))
                )
            )
        )
    if name in {"time", "mcp_scan_results"}:
        return value.kind == "object"
    return True


def parse_semgrep_observations(
    stdout: bytes,
    stderr: bytes,
    returncode: int,
    *,
    limits: ObservationLimits | None = None,
) -> SemgrepObservations:
    """Observe bounded supplied bytes. Success/coverage/authenticity are not inferred.

    Input/profile limits raise without a completed prefix. Syntactically invalid
    bounded reports instead retain both streams and a structured invalid status.
    """
    if type(stdout) is not bytes or type(stderr) is not bytes:
        raise ObservationInputError("streams must be exact immutable bytes")
    if type(returncode) is not int or not -(2**31) <= returncode < 2**31:
        raise ObservationInputError("return code must be an observed signed 32-bit integer")
    policy = ObservationLimits() if limits is None else limits
    if type(policy) is not ObservationLimits:
        raise ObservationInputError("limits must use the closed profile type")
    policy.__post_init__()
    for resource, actual, maximum in (
        ("stdout-bytes", len(stdout), policy.max_stdout_bytes),
        ("stderr-bytes", len(stderr), policy.max_stderr_bytes),
    ):
        if actual > maximum:
            raise ObservationLimitError(resource, actual, maximum)
    try:
        root = _object(_Parser(stdout, policy).parse())
    except _MalformedError as exc:
        return SemgrepObservations(
            stdout,
            stderr,
            returncode,
            "invalid-report",
            None,
            "invalid",
            "invalid",
            None,
            (),
            (),
            (Issue(str(exc), "report"),),
        )
    issues: list[Issue] = []
    version_value = root.get("version")
    version = None
    version_status: Literal["matched", "missing", "mismatched", "invalid"]
    if version_value is None:
        version_status = "missing"
    elif version_value.kind != "string":
        version_status = "invalid"
    else:
        version = cast(str, version_value.value)
        version_status = "matched" if version == VERSION else "mismatched"
    if version_status != "matched":
        issues.append(Issue("version-" + version_status, "version"))
    results_value = root.get("results")
    results_status: Literal["present", "missing", "invalid"]
    result_count = None
    results: list[ResultObservation] = []
    if results_value is None:
        results_status = "missing"
    elif results_value.kind != "array":
        results_status = "invalid"
    else:
        results_status = "present"
        values = _array(results_value)
        result_count = len(values)
        if result_count > policy.max_results:
            raise ObservationLimitError("results", result_count, policy.max_results)
        duplicates: dict[bytes, int] = {}
        for ordinal, value in enumerate(values):
            size = value.end - value.start
            if size > policy.max_result_bytes:
                raise ObservationLimitError("result-bytes", size, policy.max_result_bytes)
            raw = _span(value, stdout)
            duplicate = duplicates.get(raw.data, 0)
            duplicates[raw.data] = duplicate + 1
            projection: MatchProjection | None
            errors: tuple[Issue, ...]
            try:
                projection, errors = _project(value), ()
            except _MalformedError as exc:
                projection, errors = None, (Issue("unsupported-match-field", str(exc)),)
            results.append(ResultObservation(ordinal, raw, duplicate, projection, errors))
    if results_status != "present":
        issues.append(Issue("results-" + results_status, "results"))
    fields: list[FieldObservation] = []
    for name in sorted((_FIELDS | root.keys()) - {"version", "results"}):
        field_value = root.get(name)
        state: Literal["missing", "present", "null", "invalid"]
        if field_value is None:
            state = "missing"
        elif field_value.kind == "null":
            state = "null"
        else:
            state = "present" if _telemetry_valid(name, field_value) else "invalid"
        fields.append(
            FieldObservation(
                name,
                state,
                None if field_value is None else _span(field_value, stdout),
                name in _FIELDS,
            )
        )
        if name not in _FIELDS:
            issues.append(Issue("unknown-report-field", name))
        elif state in ("null", "invalid") or (name in {"errors", "paths"} and state == "missing"):
            issues.append(Issue("telemetry-" + state, name))
    return SemgrepObservations(
        stdout,
        stderr,
        returncode,
        "parsed",
        version,
        version_status,
        results_status,
        result_count,
        tuple(results),
        tuple(fields),
        tuple(issues),
    )
