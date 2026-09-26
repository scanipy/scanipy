"""Lossless bounded SARIF observations, not a CodeQL runner or finding emitter.

See docs/bhmea/CODEQL-OBSERVATIONS-CONTRACT.md. Public carriers are inert data;
all encoder inputs are detached and rederived. No FS, process, authority or
native identity is established by parsing or archive replay.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import cast

from services.scan.source_capture import INVENTORY_SCHEMA

PROFILE = "scanipy-codeql-sarif-observations/1"
ARCHIVE_SCHEMA = "scanipy-codeql-observation-archive/1"
RAW_RESULT_NAMESPACE = "scanipy-codeql-sarif-result/1"
EXPECTED_CLI_VERSION = "2.20.0"
_MAGIC = b"SCANIPY-CODEQL-OBSERVATION/1\n"
_PARTS = ("report", "stdout", "stderr", "source_inventory")
_MAX_INT = 2**63 - 1
_NUMBER = re.compile(rb"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?\Z")
_INTEGER = re.compile(r"-?(?:0|[1-9][0-9]*)\Z")
_HEX = re.compile(r"[0-9a-f]{64}\Z")


class CodeQLInputError(ValueError):
    """Invalid public data; message never contains supplied report content."""


class CodeQLLimitError(CodeQLInputError):
    """Admission limit exceeded; there is no accepted partial observation."""


class CodeQLArchiveError(CodeQLInputError):
    """Malformed frame or inconsistent supplied derived view."""


def _require(condition: bool, code: str = "invalid-input") -> None:
    if not condition:
        raise CodeQLInputError(code)


def _bound(value: int, maximum: int, code: str) -> None:
    if value > maximum:
        raise CodeQLLimitError(code)


@dataclass(frozen=True, slots=True, repr=False)
class CodeQLObservationLimits:
    max_report_bytes: int = 16 * 1024**2
    max_stdout_bytes: int = 1024**2
    max_stderr_bytes: int = 1024**2
    max_inventory_bytes: int = 1024**2
    max_archive_bytes: int = 20 * 1024**2
    max_manifest_bytes: int = 65536
    max_result_bytes: int = 1024**2
    max_runs: int = 8
    max_results: int = 10000
    max_rules: int = 10000
    max_artifacts: int = 20000
    max_depth: int = 32
    max_values: int = 250000
    max_string_bytes: int = 1024**2
    max_number_bytes: int = 128
    max_inventory_files: int = 10000
    max_source_path_bytes: int = 1024
    max_source_root_aliases: int = 8

    def __post_init__(self) -> None:
        for name, maximum in _LIMITS:
            value = object.__getattribute__(self, name)
            _require(type(value) is int and 1 <= value <= maximum, "invalid-limit")


_LIMITS = (
    ("max_report_bytes", 16 * 1024**2),
    ("max_stdout_bytes", 1024**2),
    ("max_stderr_bytes", 1024**2),
    ("max_inventory_bytes", 1024**2),
    ("max_archive_bytes", 20 * 1024**2),
    ("max_manifest_bytes", 65536),
    ("max_result_bytes", 1024**2),
    ("max_runs", 8),
    ("max_results", 10000),
    ("max_rules", 10000),
    ("max_artifacts", 20000),
    ("max_depth", 32),
    ("max_values", 250000),
    ("max_string_bytes", 1024**2),
    ("max_number_bytes", 128),
    ("max_inventory_files", 10000),
    ("max_source_path_bytes", 1024),
    ("max_source_root_aliases", 8),
)


def _limits(value: CodeQLObservationLimits | None) -> CodeQLObservationLimits:
    if value is None:
        return CodeQLObservationLimits()
    _require(type(value) is CodeQLObservationLimits, "invalid-limit-type")
    try:
        members = tuple(object.__getattribute__(value, name) for name, _ in _LIMITS)
    except AttributeError as exc:
        raise CodeQLInputError("invalid-limit-storage") from exc
    return CodeQLObservationLimits(*members)


@dataclass(frozen=True, slots=True, repr=False)
class ByteSpan:
    start: int
    end: int


@dataclass(frozen=True, slots=True, repr=False)
class FieldSpan:
    name: str
    key: ByteSpan
    value: ByteSpan


@dataclass(frozen=True, slots=True, repr=False)
class Issue:
    code: str
    span: ByteSpan | None


@dataclass(frozen=True, slots=True, repr=False)
class RuleJoin:
    status: str
    rule_ordinal: int | None


@dataclass(frozen=True, slots=True, repr=False)
class PathJoin:
    status: str
    source_path: str | None
    inventory_ordinal: int | None


@dataclass(frozen=True, slots=True, repr=False)
class LocationObservation:
    ordinal: int
    raw: ByteSpan
    fields: tuple[FieldSpan, ...]
    path_join: PathJoin
    region: ByteSpan | None
    issues: tuple[Issue, ...]


@dataclass(frozen=True, slots=True, repr=False)
class ResultObservation:
    run_ordinal: int
    result_ordinal: int
    duplicate_ordinal: int
    raw: ByteSpan
    raw_sha256: str
    fields: tuple[FieldSpan, ...]
    rule_join: RuleJoin
    locations: tuple[LocationObservation, ...]
    issues: tuple[Issue, ...]


@dataclass(frozen=True, slots=True, repr=False)
class RunObservation:
    ordinal: int
    raw: ByteSpan
    fields: tuple[FieldSpan, ...]
    results_status: str
    results: tuple[ResultObservation, ...]
    issues: tuple[Issue, ...]


@dataclass(frozen=True, slots=True, repr=False)
class CodeQLObservations:
    profile: str
    report: bytes | None
    stdout: bytes | None
    stderr: bytes | None
    returncode: int | None
    source_inventory: bytes | None
    source_root_aliases: tuple[str, ...]
    limits: CodeQLObservationLimits
    parse_status: str
    format_status: str
    inventory_status: str
    runs: tuple[RunObservation, ...]
    issues: tuple[Issue, ...]


class _SyntaxError(ValueError):
    pass


@dataclass(slots=True, repr=False)
class _Budget:
    limits: CodeQLObservationLimits
    values: int = 0

    def charge(self) -> None:
        self.values += 1
        _bound(self.values, self.limits.max_values, "json-values")


@dataclass(slots=True, repr=False)
class _Node:
    kind: str
    span: ByteSpan
    scalar: str | bool | None = None
    members: tuple[tuple[str, ByteSpan, _Node], ...] = ()
    items: tuple[_Node, ...] = ()

    def get(self, name: str) -> _Node | None:
        return next((node for key, _, node in self.members if key == name), None)

    def fields(self) -> tuple[FieldSpan, ...]:
        return tuple(FieldSpan(name, key, node.span) for name, key, node in self.members)


def _syntax(condition: bool) -> None:
    if not condition:
        raise _SyntaxError()


class _Parser:
    """Private bounded byte grammar. Unknown numbers retain lexical spelling."""

    def __init__(self, data: bytes, budget: _Budget) -> None:
        self.data, self.budget, self.pos = data, budget, 0

    def whitespace(self) -> None:
        while self.pos < len(self.data) and self.data[self.pos] in b" \t\r\n":
            self.pos += 1

    def string(self) -> _Node:
        self.budget.charge()
        start = self.pos
        _syntax(self.pos < len(self.data) and self.data[self.pos] == 34)
        self.pos += 1
        decoded = 0
        while self.pos < len(self.data):
            byte = self.data[self.pos]
            if byte == 34:
                self.pos += 1
                raw = self.data[start : self.pos]
                try:
                    value = json.loads(raw.decode("utf-8"))
                except (ValueError, UnicodeError) as exc:
                    raise _SyntaxError() from exc
                return _Node("string", ByteSpan(start, self.pos), value)
            _syntax(byte >= 32)
            if byte != 92:
                decoded += 1
                self.pos += 1
            else:
                _syntax(self.pos + 1 < len(self.data))
                escaped = self.data[self.pos + 1]
                if escaped in b'"\\/bfnrt':
                    self.pos += 2
                    decoded += 1
                else:
                    _syntax(escaped == 117)
                    first = self.hex4(self.pos + 2)
                    self.pos += 6
                    if 0xD800 <= first <= 0xDBFF:
                        _syntax(self.data[self.pos : self.pos + 2] == b"\\u")
                        second = self.hex4(self.pos + 2)
                        _syntax(0xDC00 <= second <= 0xDFFF)
                        self.pos += 6
                        decoded += 4
                    else:
                        _syntax(not 0xDC00 <= first <= 0xDFFF)
                        decoded += 1 if first < 128 else 2 if first < 2048 else 3
            _bound(decoded, self.budget.limits.max_string_bytes, "json-string")
        raise _SyntaxError()

    def hex4(self, position: int) -> int:
        chunk = self.data[position : position + 4]
        _syntax(len(chunk) == 4 and all(c in b"0123456789abcdefABCDEF" for c in chunk))
        return int(chunk, 16)

    def value(self, depth: int = 0) -> _Node:
        self.whitespace()
        _bound(depth, self.budget.limits.max_depth, "json-depth")
        _syntax(self.pos < len(self.data))
        if self.data[self.pos] == 34:
            return self.string()
        self.budget.charge()
        start, byte = self.pos, self.data[self.pos]
        if byte in (123, 91):
            self.pos += 1
            close = 125 if byte == 123 else 93
            members: list[tuple[str, ByteSpan, _Node]] = []
            items: list[_Node] = []
            seen: set[str] = set()
            self.whitespace()
            if self.pos < len(self.data) and self.data[self.pos] == close:
                self.pos += 1
            else:
                while True:
                    if byte == 123:
                        key = self.string()
                        assert isinstance(key.scalar, str)
                        _syntax(key.scalar not in seen)
                        seen.add(key.scalar)
                        self.whitespace()
                        _syntax(self.pos < len(self.data) and self.data[self.pos] == 58)
                        self.pos += 1
                        members.append((key.scalar, key.span, self.value(depth + 1)))
                    else:
                        items.append(self.value(depth + 1))
                    self.whitespace()
                    _syntax(self.pos < len(self.data))
                    token = self.data[self.pos]
                    self.pos += 1
                    if token == close:
                        break
                    _syntax(token == 44)
                    self.whitespace()
            return _Node(
                "object" if byte == 123 else "array",
                ByteSpan(start, self.pos),
                members=tuple(members),
                items=tuple(items),
            )
        for literal, kind, scalar in (
            (b"true", "bool", True),
            (b"false", "bool", False),
            (b"null", "null", None),
        ):
            if self.data.startswith(literal, self.pos):
                self.pos += len(literal)
                return _Node(kind, ByteSpan(start, self.pos), scalar)
        while self.pos < len(self.data) and self.data[self.pos] in b"0123456789.eE+-":
            self.pos += 1
            _bound(self.pos - start, self.budget.limits.max_number_bytes, "json-number")
        raw = self.data[start : self.pos]
        _syntax(_NUMBER.fullmatch(raw) is not None)
        return _Node("number", ByteSpan(start, self.pos), raw.decode("ascii"))

    def parse(self) -> _Node:
        result = self.value()
        self.whitespace()
        _syntax(self.pos == len(self.data))
        return result


def _text(node: _Node | None, *, nonempty: bool = False) -> str | None:
    if node is None or node.kind != "string":
        return None
    assert isinstance(node.scalar, str)
    return node.scalar if node.scalar or not nonempty else None


def _integer(node: _Node | None, low: int = 0, high: int = _MAX_INT) -> int | None:
    if node is None or node.kind != "number":
        return None
    assert isinstance(node.scalar, str)
    if len(node.scalar) > 20 or _INTEGER.fullmatch(node.scalar) is None:
        return None
    number = int(node.scalar)
    return number if low <= number <= high else None


def _blob(value: bytes | None, maximum: int, code: str) -> bytes | None:
    _require(value is None or type(value) is bytes, "invalid-bytes-type")
    if value is not None:
        _bound(len(value), maximum, code)
    return value


def _strings(value: tuple[str, ...], limits: CodeQLObservationLimits) -> tuple[str, ...]:
    _require(type(value) is tuple, "invalid-aliases")
    _bound(len(value), limits.max_source_root_aliases, "source-root-aliases")
    result = []
    for item in value:
        _require(type(item) is str and 0 < len(item) <= 128, "invalid-alias")
        try:
            encoded = item.encode("utf-8")
        except UnicodeError as exc:
            raise CodeQLInputError("invalid-alias") from exc
        _require(
            len(encoded) <= 128 and not any(ord(c) < 32 or 127 <= ord(c) <= 159 for c in item),
            "invalid-alias",
        )
        result.append(item)
    _require(result == sorted(set(result), key=lambda x: x.encode("utf-8")), "invalid-alias-order")
    return tuple(result)


def _canonical(value: object, maximum: int) -> bytes:
    """Precharge escaped UTF-8 output before json.dumps allocates it."""
    size = 0
    pending = [value]
    while pending:
        item = pending.pop()
        if item is None:
            size += 4
        elif type(item) is bool:
            size += 4 if item else 5
        elif type(item) is int:
            _require(-(2**63) <= item <= _MAX_INT, "invalid-json-int")
            size += len(str(item))
        elif type(item) is str:
            _bound(len(item), maximum, "encoded-json")
            size += 2
            for character in item:
                code = ord(character)
                _require(not 0xD800 <= code <= 0xDFFF, "invalid-json-string")
                size += (
                    2
                    if character in '\\"\b\f\n\r\t'
                    else 6
                    if code < 32
                    else 1
                    if code < 128
                    else 2
                    if code < 2048
                    else 3
                    if code < 65536
                    else 4
                )
                _bound(size, maximum, "encoded-json")
        elif type(item) is list:
            size += 2 + max(0, len(item) - 1)
            _bound(len(pending) + len(item), 250000, "encoded-values")
            pending.extend(item)
        elif type(item) is dict:
            size += 2 + max(0, len(item) - 1) + len(item)
            _bound(len(pending) + 2 * len(item), 250000, "encoded-values")
            for key, member in item.items():
                _require(type(key) is str, "invalid-json-key")
                pending.extend((key, member))
        else:
            raise CodeQLInputError("invalid-json-value")
        _bound(size, maximum, "encoded-json")
    return json.dumps(
        value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":")
    ).encode("utf-8")


def _inventory(data: bytes | None, budget: _Budget) -> tuple[str, dict[str, int]]:
    if data is None:
        return "not-supplied", {}
    try:
        root = _Parser(data, budget).parse()
        _syntax(root.kind == "object" and {k for k, _, _ in root.members} == {"schema", "files"})
        _syntax(_text(root.get("schema")) == INVENTORY_SCHEMA)
        rows = root.get("files")
        _syntax(rows is not None and rows.kind == "array")
        assert rows is not None
        _bound(len(rows.items), budget.limits.max_inventory_files, "inventory-files")
        files, paths, total = [], [], 0
        for row in rows.items:
            _syntax(
                row.kind == "object"
                and {k for k, _, _ in row.members} == {"path", "size", "sha256"}
            )
            path, size, digest = (
                _text(row.get("path")),
                _integer(row.get("size"), 0, 64 * 1024**2),
                _text(row.get("sha256")),
            )
            _syntax(path is not None and size is not None and digest is not None)
            assert path is not None and size is not None and digest is not None
            _bound(len(path.encode("utf-8")), budget.limits.max_source_path_bytes, "source-path")
            _syntax(
                bool(path)
                and "\\" not in path
                and not any(ord(c) < 32 or 127 <= ord(c) <= 159 for c in path)
                and all(part not in ("", ".", "..") for part in path.split("/"))
            )
            _syntax(_HEX.fullmatch(digest) is not None)
            total += size
            _syntax(total <= 512 * 1024**2)
            paths.append(path)
            files.append({"path": path, "size": size, "sha256": digest})
        _syntax(paths == sorted(set(paths), key=lambda x: x.encode("utf-8")))
        _syntax(
            _canonical(
                {"schema": INVENTORY_SCHEMA, "files": files}, budget.limits.max_inventory_bytes
            )
            == data
        )
        return "valid-data", {path: index for index, path in enumerate(paths)}
    except _SyntaxError:
        return "invalid-data", {}


_ROOT_FIELDS = frozenset(("$schema", "version", "runs", "inlineExternalProperties", "properties"))
_RUN_FIELDS = frozenset(
    (
        "tool",
        "invocations",
        "conversion",
        "language",
        "versionControlProvenance",
        "originalUriBaseIds",
        "artifacts",
        "logicalLocations",
        "graphs",
        "results",
        "automationDetails",
        "runAggregates",
        "baselineGuid",
        "redactionTokens",
        "defaultEncoding",
        "defaultSourceLanguage",
        "newlineSequences",
        "columnKind",
        "externalPropertyFileReferences",
        "threadFlowLocations",
        "taxonomies",
        "addresses",
        "translations",
        "policies",
        "webRequests",
        "webResponses",
        "specialLocations",
        "properties",
    )
)
_RESULT_FIELDS = frozenset(
    (
        "ruleId",
        "ruleIndex",
        "rule",
        "kind",
        "level",
        "message",
        "analysisTarget",
        "locations",
        "guid",
        "correlationGuid",
        "occurrenceCount",
        "partialFingerprints",
        "fingerprints",
        "stacks",
        "codeFlows",
        "graphs",
        "graphTraversals",
        "relatedLocations",
        "suppressions",
        "baselineState",
        "rank",
        "attachments",
        "hostedViewerUri",
        "workItemUris",
        "provenance",
        "fixes",
        "taxa",
        "webRequest",
        "webResponse",
        "properties",
    )
)
_LOCATION_FIELDS = frozenset(
    (
        "id",
        "physicalLocation",
        "logicalLocations",
        "message",
        "annotations",
        "relationships",
        "properties",
    )
)
_ENUMS = {
    "kind": ("notApplicable", "pass", "fail", "review", "open", "informational"),
    "level": ("none", "note", "warning", "error"),
    "baselineState": ("new", "unchanged", "updated", "absent"),
}


@dataclass(slots=True, repr=False)
class _RunContext:
    rules: tuple[_Node, ...]
    artifacts: tuple[_Node, ...]
    bases: _Node | None
    rule_ids: dict[str, tuple[int, ...]]


class _Projection:
    def __init__(
        self,
        raw: bytes,
        limits: CodeQLObservationLimits,
        inventory: dict[str, int],
        inventory_status: str,
        aliases: tuple[str, ...],
    ) -> None:
        self.raw, self.limits, self.inventory = raw, limits, inventory
        self.inventory_status, self.aliases = inventory_status, aliases
        self.rank = 0
        self.issue_count = self.result_count = self.rule_count = self.artifact_count = 0

    def issue(self, issues: list[Issue], code: str, node: _Node | None, *, level: int = 2) -> None:
        self.rank = max(self.rank, level)
        self.issue_count += 1
        _bound(self.issue_count, self.limits.max_values, "observation-issues")
        issues.append(Issue(code, None if node is None else node.span))

    def unknown(self, node: _Node, known: frozenset[str], issues: list[Issue]) -> None:
        for name, _, value in node.members:
            if name not in known:
                self.issue(issues, "unknown-field", value, level=0)

    def typed(self, node: _Node, name: str, kind: str, issues: list[Issue]) -> _Node | None:
        value = node.get(name)
        if value is not None and value.kind != kind:
            self.issue(issues, "known-field-shape", value)
            return None
        return value

    def rule_join(self, result: _Node, context: _RunContext, issues: list[Issue]) -> RuleJoin:
        descriptor = result.get("rule")
        if descriptor is not None and descriptor.kind != "object":
            self.issue(issues, "rule-reference", descriptor)
            return RuleJoin("invalid", None)
        ids, indexes = [], []
        for parent, id_key, index_key in (
            (result, "ruleId", "ruleIndex"),
            (descriptor, "id", "index"),
        ):
            if parent is None:
                continue
            id_node, index_node = parent.get(id_key), parent.get(index_key)
            if id_node is not None:
                identifier = _text(id_node, nonempty=True)
                if identifier is None:
                    self.issue(issues, "rule-reference", id_node)
                    return RuleJoin("invalid", None)
                ids.append(identifier)
            if index_node is not None:
                index = _integer(index_node, -1)
                if index is None:
                    self.issue(issues, "rule-reference", index_node)
                    return RuleJoin("invalid", None)
                indexes.append(index)
        if len(set(ids)) > 1 or len(set(indexes)) > 1:
            self.issue(issues, "rule-contradiction", result)
            return RuleJoin("inconsistent", None)
        guid = None if descriptor is None else descriptor.get("guid")
        if guid is not None and _text(guid) is None:
            self.issue(issues, "rule-reference", guid)
            return RuleJoin("invalid", None)
        if descriptor is not None and descriptor.get("toolComponent") is not None:
            self.issue(issues, "component-unsupported", descriptor.get("toolComponent"), level=1)
            return RuleJoin("unsupported-component", None)
        index = indexes[0] if indexes and indexes[0] >= 0 else None
        identifier = ids[0] if ids else None
        if index is None:
            if identifier is None:
                self.issue(issues, "rule-reference", descriptor, level=0)
                return RuleJoin("missing", None)
            matches = context.rule_ids.get(identifier, ())
            if not matches:
                return RuleJoin("unindexed-id", None)
            if len(matches) > 1:
                self.issue(issues, "rule-ambiguity", result, level=0)
                return RuleJoin("ambiguous", None)
            index = matches[0]
        if index >= len(context.rules):
            self.issue(issues, "rule-reference", result)
            return RuleJoin("invalid", None)
        row = context.rules[index]
        row_id = _text(row.get("id"), nonempty=True)
        if row.kind != "object" or row_id is None:
            self.issue(issues, "rule-reference", row)
            return RuleJoin("invalid", None)
        if identifier is not None and identifier != row_id:
            self.issue(issues, "rule-contradiction", result)
            return RuleJoin("inconsistent", None)
        if guid is not None and (_text(guid) is None or _text(guid) != _text(row.get("guid"))):
            self.issue(issues, "rule-contradiction", guid)
            return RuleJoin("inconsistent", None)
        return RuleJoin("matched-driver-rule", index)

    def uri(self, node: _Node | None) -> tuple[str, str | None]:
        value = _text(node)
        if value is None:
            return ("missing" if node is None else "invalid"), None
        _bound(len(value), 3 * self.limits.max_source_path_bytes, "source-uri")
        if not value or value.startswith("/") or any(c in value for c in "?#\\"):
            return "unsupported-uri", None
        if ":" in value.split("/", 1)[0]:
            return "unsupported-uri", None
        decoded = bytearray()
        position = 0
        while position < len(value):
            character = value[position]
            if character == "%":
                chunk = value[position + 1 : position + 3]
                if len(chunk) != 2 or any(c not in "0123456789abcdefABCDEF" for c in chunk):
                    return "unsupported-uri", None
                byte = int(chunk, 16)
                if byte in (47, 92):
                    return "unsupported-uri", None
                decoded.append(byte)
                position += 3
            else:
                decoded.extend(character.encode("utf-8"))
                position += 1
            _bound(len(decoded), self.limits.max_source_path_bytes, "source-path")
        try:
            path = decoded.decode("utf-8")
        except UnicodeError:
            return "unsupported-uri", None
        if (
            any(ord(c) < 32 or 127 <= ord(c) <= 159 for c in path)
            or any(p in ("", ".", "..") for p in path.split("/"))
            or "\\" in path
            or ":" in path.split("/", 1)[0]
        ):
            return "unsupported-uri", None
        return "path", path

    def base(self, node: _Node | None, context: _RunContext) -> tuple[str, str | None]:
        if node is None:
            return "base", None
        alias = _text(node, nonempty=True)
        if alias is None:
            return "invalid", None
        if alias not in self.aliases:
            return "unsupported-base", None
        if context.bases is not None:
            if context.bases.kind != "object":
                return "invalid", None
            native = context.bases.get(alias)
            if native is not None:
                if native.kind != "object" or (
                    native.get("uri") is not None and _text(native.get("uri")) is None
                ):
                    return "invalid", None
                if native.get("uriBaseId") is not None or native.get("index") is not None:
                    return "unsupported-base", None
        return "base", alias

    def path_join(
        self, artifact: _Node | None, context: _RunContext, issues: list[Issue]
    ) -> PathJoin:
        status, path, alias = "missing", None, None
        if artifact is not None:
            if artifact.kind != "object":
                status = "invalid"
            else:
                index_node = artifact.get("index")
                index = -1 if index_node is None else _integer(index_node, -1)
                target: _Node | None = artifact
                if index is None or index >= len(context.artifacts):
                    status = "invalid"
                    target = None
                elif index >= 0:
                    target = context.artifacts[index].get("location")
                    if target is None or target.kind != "object" or target.get("index") is not None:
                        status, target = "inconsistent", None
                if target is not None:
                    status, path = self.uri(target.get("uri"))
                    base_status, alias = self.base(target.get("uriBaseId"), context)
                    if base_status != "base" and status not in ("invalid", "inconsistent"):
                        status, path = base_status, None
                    if index is not None and index >= 0:
                        if artifact.get("uri") is not None:
                            inline_status, inline_path = self.uri(artifact.get("uri"))
                            if inline_status != "path" or status != "path" or inline_path != path:
                                status, path = "inconsistent", None
                            # URI plus index supplies a complete URI/base identity.
                            inline_base_status, inline_alias = self.base(
                                artifact.get("uriBaseId"), context
                            )
                            if inline_base_status != "base" or inline_alias != alias:
                                status, path = "inconsistent", None
                        elif artifact.get("uriBaseId") is not None:
                            inline_base_status, inline_alias = self.base(
                                artifact.get("uriBaseId"), context
                            )
                            if inline_base_status != "base" or inline_alias != alias:
                                status, path = "inconsistent", None
        malformed = status in ("invalid", "inconsistent")
        if status == "path":
            assert path is not None
            if self.inventory_status != "valid-data":
                status = "not-supplied" if self.inventory_status == "not-supplied" else "invalid"
            elif path not in self.inventory:
                status = "outside-inventory"
            else:
                return PathJoin("inventory-match", path, self.inventory[path])
        code = {
            "missing": "location-shape",
            "invalid": "artifact-reference",
            "inconsistent": "artifact-contradiction",
            "unsupported-uri": "uri-unsupported",
            "unsupported-base": "base-unsupported",
            "not-supplied": "inventory-missing",
            "outside-inventory": "path-outside-inventory",
        }[status]
        self.issue(issues, code, artifact, level=2 if malformed else 0)
        return PathJoin(status, None, None)

    def region(self, node: _Node | None, issues: list[Issue]) -> None:
        if node is None:
            return
        self.issue(issues, "coordinates-unverified", node, level=0)
        if node.kind != "object":
            self.issue(issues, "region-shape", node)
            return
        values: dict[str, int] = {}
        ranges = {
            "startLine": 1,
            "endLine": 1,
            "startColumn": 1,
            "endColumn": 1,
            "charOffset": -1,
            "byteOffset": -1,
            "charLength": 0,
            "byteLength": 0,
        }
        for name, low in ranges.items():
            member = node.get(name)
            if member is not None:
                number = _integer(member, low)
                if number is None:
                    self.issue(issues, "region-range", member)
                else:
                    values[name] = number
        if not any(
            node.get(name) is not None for name in ("startLine", "charOffset", "byteOffset")
        ):
            self.issue(issues, "region-shape", node)
        if "endLine" in values and (
            "startLine" not in values or values["endLine"] < values["startLine"]
        ):
            self.issue(issues, "region-range", node)
        if (
            values.get("endLine", values.get("startLine")) == values.get("startLine")
            and "endColumn" in values
            and "startColumn" in values
            and values["endColumn"] < values["startColumn"]
        ):
            self.issue(issues, "region-range", node)
        for stem in ("char", "byte"):
            if values.get(stem + "Offset", -1) >= 0 and stem + "Length" in values:
                if values[stem + "Offset"] + values[stem + "Length"] > _MAX_INT:
                    self.issue(issues, "region-range", node)

    def location(self, ordinal: int, node: _Node, context: _RunContext) -> LocationObservation:
        issues: list[Issue] = []
        region = None
        if node.kind != "object":
            self.issue(issues, "location-shape", node)
            join = PathJoin("invalid", None, None)
        else:
            self.unknown(node, _LOCATION_FIELDS, issues)
            physical = node.get("physicalLocation")
            if physical is None:
                join = PathJoin("missing", None, None)
                self.issue(issues, "location-shape", node, level=1)
            elif physical.kind != "object":
                self.issue(issues, "location-shape", physical)
                join = PathJoin("invalid", None, None)
            else:
                join = self.path_join(physical.get("artifactLocation"), context, issues)
                region = physical.get("region")
                self.region(region, issues)
        return LocationObservation(
            ordinal,
            node.span,
            node.fields(),
            join,
            None if region is None else region.span,
            tuple(issues),
        )

    def message(self, value: _Node | None, issues: list[Issue]) -> None:
        if value is None or value.kind != "object":
            self.issue(issues, "message-shape", value)
            return
        if _text(value.get("text")) is None and _text(value.get("id")) is None:
            self.issue(issues, "message-shape", value)
        for field in ("text", "id", "markdown"):
            self.typed(value, field, "string", issues)
        arguments = self.typed(value, "arguments", "array", issues)
        if arguments is not None:
            for argument in arguments.items:
                if argument.kind != "string":
                    self.issue(issues, "message-shape", argument)

    def result(
        self, run: int, ordinal: int, node: _Node, duplicate: int, context: _RunContext
    ) -> ResultObservation:
        issues: list[Issue] = []
        locations: tuple[LocationObservation, ...] = ()
        if node.kind != "object":
            self.issue(issues, "result-shape", node)
            rule = RuleJoin("invalid", None)
        else:
            self.unknown(node, _RESULT_FIELDS, issues)
            self.message(node.get("message"), issues)
            for key, choices in _ENUMS.items():
                member = node.get(key)
                if member is not None and _text(member) not in choices:
                    self.issue(issues, "known-field-shape", member)
            for key in ("guid", "correlationGuid"):
                self.typed(node, key, "string", issues)
            count = node.get("occurrenceCount")
            if count is not None and _integer(count, 1) is None:
                self.issue(issues, "known-field-shape", count)
            for key in ("partialFingerprints", "fingerprints"):
                fingerprints = self.typed(node, key, "object", issues)
                if fingerprints is not None:
                    for _, _, value in fingerprints.members:
                        if value.kind != "string":
                            self.issue(issues, "known-field-shape", value)
            for key in ("locations", "relatedLocations", "codeFlows", "suppressions", "taxa"):
                self.typed(node, key, "array", issues)
            suppressions = node.get("suppressions")
            if suppressions is not None and suppressions.kind == "array":
                for suppression in suppressions.items:
                    if suppression.kind != "object" or _text(suppression.get("kind")) not in (
                        "inSource",
                        "external",
                    ):
                        self.issue(issues, "known-field-shape", suppression)
                    elif suppression.get("status") is not None and _text(
                        suppression.get("status")
                    ) not in ("accepted", "underReview", "rejected"):
                        self.issue(issues, "known-field-shape", suppression.get("status"))
            self.traces(node.get("codeFlows"), issues)
            rule = self.rule_join(node, context, issues)
            native_locations = node.get("locations")
            if (
                native_locations is None
                or native_locations.kind != "array"
                or len(native_locations.items) != 1
            ):
                self.issue(issues, "location-count-unsupported", native_locations, level=1)
            if native_locations is not None and native_locations.kind == "array":
                locations = tuple(
                    self.location(i, item, context) for i, item in enumerate(native_locations.items)
                )
        raw = self.raw[node.span.start : node.span.end]
        return ResultObservation(
            run,
            ordinal,
            duplicate,
            node.span,
            hashlib.sha256(raw).hexdigest(),
            node.fields(),
            rule,
            locations,
            tuple(issues),
        )

    def traces(self, flows: _Node | None, issues: list[Issue]) -> None:
        if flows is None or flows.kind != "array":
            return
        for flow in flows.items:
            threads = flow.get("threadFlows")
            if threads is None or threads.kind != "array":
                continue
            for thread in threads.items:
                locations = thread.get("locations")
                if locations is None or locations.kind != "array":
                    continue
                for location in locations.items:
                    index = location.get("index")
                    if index is not None:
                        number = _integer(index, -1)
                        if number is None:
                            self.issue(issues, "known-field-shape", index)
                        elif number != -1:
                            self.issue(issues, "threadflow-reference-unresolved", index, level=1)

    def invocations(self, run: _Node, issues: list[Issue]) -> None:
        invocations = self.typed(run, "invocations", "array", issues)
        if invocations is None:
            return
        for invocation in invocations.items:
            success = invocation.get("executionSuccessful")
            if invocation.kind != "object" or success is None or success.kind != "bool":
                self.issue(issues, "native-execution-claim-invalid", invocation)
            elif success.scalar is False:
                self.issue(issues, "native-execution-failure", success, level=0)
            exit_code = invocation.get("exitCode")
            if exit_code is not None:
                code = _integer(exit_code, -(2**31), 2**31 - 1)
                if code is None:
                    self.issue(issues, "native-execution-claim-invalid", exit_code)
                elif code != 0:
                    self.issue(issues, "native-execution-failure", exit_code, level=0)
            notifications = self.typed(invocation, "toolExecutionNotifications", "array", issues)
            if notifications is not None:
                for notification in notifications.items:
                    if _text(notification.get("level")) == "error":
                        self.issue(issues, "native-execution-failure", notification, level=0)

    def run(self, ordinal: int, run: _Node) -> RunObservation:
        issues: list[Issue] = []
        if run.kind != "object":
            self.issue(issues, "run-shape", run)
        self.unknown(run, _RUN_FIELDS, issues)
        tool = run.get("tool")
        driver = None if tool is None else tool.get("driver")
        if tool is None or tool.kind != "object":
            self.issue(issues, "tool-shape", tool)
        if driver is None or driver.kind != "object":
            self.issue(issues, "driver-shape", driver)
        else:
            if _text(driver.get("name"), nonempty=True) is None:
                self.issue(issues, "driver-name-invalid", driver.get("name"))
            versions = [driver.get(key) for key in ("version", "semanticVersion")]
            present = [value for value in versions if value is not None]
            if not present:
                self.issue(issues, "driver-version-missing", driver, level=1)
            elif any(_text(value) is None for value in present):
                self.issue(issues, "driver-version-invalid", driver)
            elif len({_text(value) for value in present}) > 1:
                self.issue(issues, "driver-version-conflict", driver)
            elif _text(present[0]) != EXPECTED_CLI_VERSION:
                self.issue(issues, "driver-version-mismatch", present[0], level=1)
        rules: tuple[_Node, ...] = ()
        components = [] if driver is None else [driver]
        extensions = None if tool is None else self.typed(tool, "extensions", "array", issues)
        if extensions is not None:
            components.extend(extensions.items)
        for component in components:
            if component.kind != "object":
                self.issue(issues, "driver-shape", component)
            table = self.typed(component, "rules", "array", issues)
            if table is not None:
                self.rule_count += len(table.items)
                _bound(self.rule_count, self.limits.max_rules, "rules")
                if component is driver:
                    rules = table.items
                for row in table.items:
                    if row.kind != "object" or _text(row.get("id"), nonempty=True) is None:
                        self.issue(issues, "rule-reference", row)
        artifacts_node = self.typed(run, "artifacts", "array", issues)
        artifacts = () if artifacts_node is None else artifacts_node.items
        self.artifact_count += len(artifacts)
        _bound(self.artifact_count, self.limits.max_artifacts, "artifacts")
        bases = self.typed(run, "originalUriBaseIds", "object", issues)
        column_kind = run.get("columnKind")
        if column_kind is not None and _text(column_kind) not in (
            "utf16CodeUnits",
            "unicodeCodePoints",
        ):
            self.issue(issues, "known-field-shape", column_kind)
        external = run.get("externalPropertyFileReferences")
        if external is not None:
            if external.kind != "object":
                self.issue(issues, "known-field-shape", external)
            elif external.members:
                self.issue(issues, "external-properties-unresolved", external, level=1)
        self.invocations(run, issues)
        rule_ids: dict[str, list[int]] = {}
        for i, row in enumerate(rules):
            identifier = _text(row.get("id"), nonempty=True)
            if identifier is not None:
                rule_ids.setdefault(identifier, []).append(i)
        context = _RunContext(
            rules, artifacts, bases, {key: tuple(indices) for key, indices in rule_ids.items()}
        )
        native = run.get("results")
        result_status = (
            "missing"
            if native is None
            else "null"
            if native.kind == "null"
            else "present"
            if native.kind == "array"
            else "invalid"
        )
        results = []
        if result_status != "present":
            self.issue(issues, "results-shape", native)
        else:
            assert native is not None
            self.result_count += len(native.items)
            _bound(self.result_count, self.limits.max_results, "results")
            duplicates: dict[bytes, int] = {}
            for index, node in enumerate(native.items):
                _bound(
                    node.span.end - node.span.start, self.limits.max_result_bytes, "result-bytes"
                )
                raw = self.raw[node.span.start : node.span.end]
                duplicate = duplicates.get(raw, 0)
                duplicates[raw] = duplicate + 1
                results.append(self.result(ordinal, index, node, duplicate, context))
        return RunObservation(
            ordinal, run.span, run.fields(), result_status, tuple(results), tuple(issues)
        )

    def project(self, root: _Node, issues: list[Issue]) -> tuple[RunObservation, ...]:
        if root.kind != "object":
            self.issue(issues, "root-shape", root)
            return ()
        self.unknown(root, _ROOT_FIELDS, issues)
        version = root.get("version")
        if version is None:
            self.issue(issues, "version-missing", None)
        elif _text(version) is None:
            self.issue(issues, "version-invalid", version)
        elif _text(version) != "2.1.0":
            self.issue(issues, "version-unsupported", version, level=1)
        schema = root.get("$schema")
        if schema is not None and _text(schema) is None:
            self.issue(issues, "schema-field-invalid", schema)
        runs = root.get("runs")
        if runs is None or runs.kind != "array":
            self.issue(issues, "runs-missing" if runs is None else "runs-shape", runs)
            return ()
        _bound(len(runs.items), self.limits.max_runs, "runs")
        if len(runs.items) != 1:
            self.issue(issues, "run-count-unsupported", runs, level=1)
        return tuple(self.run(index, row) for index, row in enumerate(runs.items))


def parse_codeql_observations(
    report: bytes | None,
    *,
    stdout: bytes | None = None,
    stderr: bytes | None = None,
    returncode: int | None = None,
    source_inventory: bytes | None = None,
    source_root_aliases: tuple[str, ...] = (),
    limits: CodeQLObservationLimits | None = None,
) -> CodeQLObservations:
    """Observe supplied data only. Inventory joins never establish source custody."""
    policy = _limits(limits)
    report = _blob(report, policy.max_report_bytes, "report-bytes")
    stdout = _blob(stdout, policy.max_stdout_bytes, "stdout-bytes")
    stderr = _blob(stderr, policy.max_stderr_bytes, "stderr-bytes")
    source_inventory = _blob(source_inventory, policy.max_inventory_bytes, "inventory-bytes")
    _require(
        returncode is None or (type(returncode) is int and -(2**31) <= returncode < 2**31),
        "invalid-returncode",
    )
    aliases = _strings(source_root_aliases, policy)
    budget = _Budget(policy)
    inventory_status, inventory = _inventory(source_inventory, budget)
    issues: list[Issue] = []
    if inventory_status == "invalid-data":
        issues.append(Issue("inventory-invalid", None))
    if returncode is not None and returncode != 0:
        issues.append(Issue("native-execution-failure", None))
    parse_status, format_status = "missing", "not-evaluated"
    runs: tuple[RunObservation, ...] = ()
    if report is not None:
        try:
            root = _Parser(report, budget).parse()
        except _SyntaxError:
            parse_status = "invalid-json"
            issues.append(Issue("invalid-json", None))
        else:
            parse_status = "parsed"
            projection = _Projection(report, policy, inventory, inventory_status, aliases)
            projection.issue_count = len(issues)
            runs = projection.project(root, issues)
            format_status = ("supported-projection", "unsupported", "invalid")[projection.rank]
    _bound(len(issues), policy.max_values, "observation-issues")
    return CodeQLObservations(
        PROFILE,
        report,
        stdout,
        stderr,
        returncode,
        source_inventory,
        aliases,
        policy,
        parse_status,
        format_status,
        inventory_status,
        runs,
        tuple(issues),
    )


_CARRIERS = (
    (CodeQLObservationLimits, tuple(name for name, _ in _LIMITS)),
    (ByteSpan, ("start", "end")),
    (FieldSpan, ("name", "key", "value")),
    (Issue, ("code", "span")),
    (RuleJoin, ("status", "rule_ordinal")),
    (PathJoin, ("status", "source_path", "inventory_ordinal")),
    (LocationObservation, ("ordinal", "raw", "fields", "path_join", "region", "issues")),
    (
        ResultObservation,
        (
            "run_ordinal",
            "result_ordinal",
            "duplicate_ordinal",
            "raw",
            "raw_sha256",
            "fields",
            "rule_join",
            "locations",
            "issues",
        ),
    ),
    (RunObservation, ("ordinal", "raw", "fields", "results_status", "results", "issues")),
    (
        CodeQLObservations,
        (
            "profile",
            "report",
            "stdout",
            "stderr",
            "returncode",
            "source_inventory",
            "source_root_aliases",
            "limits",
            "parse_status",
            "format_status",
            "inventory_status",
            "runs",
            "issues",
        ),
    ),
)


def _archive(condition: bool, code: str = "invalid-archive") -> None:
    if not condition:
        raise CodeQLArchiveError(code)


class _ViewSnapshot:
    """Detach fixed slots, never caller validators/equality/iterators.

    Bounds derive from the admitted JSON forest: a source value can produce
    spans, fields and issues, but never an unbounded expansion. The tagged
    private token sequence distinguishes bool/int and every carrier type.
    """

    def __init__(self, limits: CodeQLObservationLimits) -> None:
        self.limits = limits
        self.tokens: list[tuple[str, object]] = []
        self.active: set[int] = set()
        self.maximum = 32 * limits.max_values + 512
        self.string_bytes = 0
        self.blob_bytes = 0
        self.records: dict[int, int] = {}

    def copy(self, value: object, depth: int = 0) -> object:
        _bound(depth, 16, "view-depth")
        _bound(len(self.tokens) + 1, self.maximum, "view-values")
        kind = type(value)
        if value is None:
            self.tokens.append(("null", None))
            return None
        if type(value) is bool:
            self.tokens.append(("bool", value))
            return value
        if type(value) is int:
            _archive(-(2**63) <= value <= _MAX_INT, "invalid-view-integer")
            self.tokens.append(("int", value))
            return value
        if type(value) is str:
            _bound(len(value), max(self.limits.max_string_bytes, 256), "view-string")
            try:
                size = len(value.encode("utf-8"))
            except UnicodeError as exc:
                raise CodeQLArchiveError("invalid-view-string") from exc
            _bound(size, max(self.limits.max_string_bytes, 256), "view-string")
            self.string_bytes += size
            _bound(
                self.string_bytes,
                self.limits.max_report_bytes
                + self.limits.max_inventory_bytes
                + 64 * self.limits.max_values
                + 65536,
                "view-string-total",
            )
            self.tokens.append(("str", value))
            return value
        if type(value) is bytes:
            self.blob_bytes += len(value)
            _bound(self.blob_bytes, self.limits.max_archive_bytes, "view-bytes")
            self.tokens.append(("bytes", value))
            return value
        _archive(id(value) not in self.active, "cyclic-view")
        self.active.add(id(value))
        try:
            if type(value) is tuple:
                _bound(len(value) + len(self.tokens), self.maximum, "view-values")
                self.tokens.append(("tuple", len(value)))
                return tuple(self.copy(item, depth + 1) for item in value)
            for index, (carrier, names) in enumerate(_CARRIERS):
                if kind is carrier:
                    count = self.records.get(index, 0) + 1
                    maximum = (
                        self.limits.max_runs
                        if kind is RunObservation
                        else self.limits.max_results
                        if kind is ResultObservation
                        else 1
                        if kind is CodeQLObservations or kind is CodeQLObservationLimits
                        else self.maximum
                        if kind is ByteSpan
                        else self.limits.max_values
                    )
                    _bound(count, maximum, "view-records")
                    self.records[index] = count
                    self.tokens.append(("record", index))
                    try:
                        members = tuple(object.__getattribute__(value, name) for name in names)
                    except AttributeError as exc:
                        raise CodeQLArchiveError("invalid-view-storage") from exc
                    for name, member in zip(names, members, strict=True):
                        if type(member) is tuple:
                            cap = (
                                self.limits.max_runs
                                if name == "runs"
                                else self.limits.max_results
                                if name == "results"
                                else self.limits.max_source_root_aliases
                                if name == "source_root_aliases"
                                else self.limits.max_values
                            )
                            _bound(len(member), cap, "view-sequence")
                    # Private own-class allocation, not caller constructor/validator dispatch.
                    detached = object.__new__(carrier)
                    for name, member in zip(names, members, strict=True):
                        object.__setattr__(detached, name, self.copy(member, depth + 1))
                    return detached
            raise CodeQLArchiveError("invalid-view-type")
        finally:
            self.active.remove(id(value))


def _permitted(stored: CodeQLObservationLimits, allowed: CodeQLObservationLimits) -> None:
    for name, _ in _LIMITS:
        _archive(
            object.__getattribute__(stored, name) <= object.__getattribute__(allowed, name),
            "stored-limits-exceed-policy",
        )


def _manifest(observations: CodeQLObservations) -> dict[str, object]:
    parts: dict[str, object] = {}
    for name in _PARTS:
        data = object.__getattribute__(observations, name)
        parts[name] = (
            None
            if data is None
            else {"length": len(data), "sha256": hashlib.sha256(data).hexdigest()}
        )
    return {
        "schema": ARCHIVE_SCHEMA,
        "profile": PROFILE,
        "limits": {name: object.__getattribute__(observations.limits, name) for name, _ in _LIMITS},
        "returncode": observations.returncode,
        "source_root_aliases": list(observations.source_root_aliases),
        "parts": parts,
    }


def encode_codeql_observations(
    observations: CodeQLObservations,
    *,
    limits: CodeQLObservationLimits | None = None,
) -> bytes:
    """Reparse and compare the ENTIRE detached view before framing raw bytes."""
    allowed = _limits(limits)
    _archive(type(observations) is CodeQLObservations, "invalid-observations-type")
    supplied_snapshot = _ViewSnapshot(allowed)
    private = cast(CodeQLObservations, supplied_snapshot.copy(observations))
    _archive(type(private.limits) is CodeQLObservationLimits, "invalid-view-limits")
    policy = _limits(private.limits)
    _permitted(policy, allowed)
    fresh = parse_codeql_observations(
        private.report,
        stdout=private.stdout,
        stderr=private.stderr,
        returncode=private.returncode,
        source_inventory=private.source_inventory,
        source_root_aliases=private.source_root_aliases,
        limits=policy,
    )
    expected_snapshot = _ViewSnapshot(allowed)
    expected_snapshot.copy(fresh)
    _archive(supplied_snapshot.tokens == expected_snapshot.tokens, "inconsistent-derived-view")
    manifest = _canonical(_manifest(fresh), policy.max_manifest_bytes)
    parts = tuple(object.__getattribute__(fresh, name) for name in _PARTS)
    total = len(_MAGIC) + 4 + len(manifest) + sum(len(data) for data in parts if data is not None)
    _bound(total, policy.max_archive_bytes, "archive-bytes")
    return b"".join(
        (
            _MAGIC,
            len(manifest).to_bytes(4, "big"),
            manifest,
            *(data for data in parts if data is not None),
        )
    )


def _keys(node: _Node | None, names: tuple[str, ...]) -> _Node:
    _archive(node is not None and node.kind == "object", "manifest-shape")
    assert node is not None
    _archive({key for key, _, _ in node.members} == set(names), "manifest-keys")
    return node


def decode_codeql_observations(
    archive: bytes,
    *,
    limits: CodeQLObservationLimits | None = None,
) -> CodeQLObservations:
    """Replay an exact self-contained frame; this is not execution/authentication."""
    allowed = _limits(limits)
    _archive(type(archive) is bytes, "invalid-archive-type")
    _bound(len(archive), allowed.max_archive_bytes, "archive-bytes")
    prefix = len(_MAGIC)
    _archive(archive.startswith(_MAGIC) and len(archive) >= prefix + 4, "archive-magic")
    length = int.from_bytes(archive[prefix : prefix + 4], "big")
    _bound(length, allowed.max_manifest_bytes, "manifest-bytes")
    start, end = prefix + 4, prefix + 4 + length
    _archive(length > 0 and end <= len(archive), "manifest-length")
    raw_manifest = archive[start:end]
    manifest_limits = CodeQLObservationLimits(max_depth=8, max_values=256, max_string_bytes=65536)
    try:
        root = _Parser(raw_manifest, _Budget(manifest_limits)).parse()
    except _SyntaxError as exc:
        raise CodeQLArchiveError("manifest-json") from exc
    root = _keys(
        root, ("schema", "profile", "limits", "returncode", "source_root_aliases", "parts")
    )
    _archive(
        _text(root.get("schema")) == ARCHIVE_SCHEMA and _text(root.get("profile")) == PROFILE,
        "archive-version",
    )
    stored = _keys(root.get("limits"), tuple(name for name, _ in _LIMITS))
    values = tuple(_integer(stored.get(name), 1, maximum) for name, maximum in _LIMITS)
    _archive(all(value is not None for value in values), "manifest-limits")
    policy = CodeQLObservationLimits(*values)  # type: ignore[arg-type]
    _permitted(policy, allowed)
    _bound(len(archive), policy.max_archive_bytes, "stored-archive-bytes")
    _bound(length, policy.max_manifest_bytes, "stored-manifest-bytes")
    native_return = root.get("returncode")
    _archive(native_return is not None, "manifest-returncode")
    assert native_return is not None
    returncode = (
        None if native_return.kind == "null" else _integer(native_return, -(2**31), 2**31 - 1)
    )
    _archive(native_return.kind == "null" or returncode is not None, "manifest-returncode")
    alias_node = root.get("source_root_aliases")
    _archive(alias_node is not None and alias_node.kind == "array", "manifest-aliases")
    assert alias_node is not None
    _archive(all(_text(node) is not None for node in alias_node.items), "manifest-aliases")
    alias_values = tuple(_text(node) for node in alias_node.items)
    aliases = _strings(tuple(value for value in alias_values if value is not None), policy)
    descriptors = _keys(root.get("parts"), _PARTS)
    parts: dict[str, bytes | None] = {}
    normalized_parts: dict[str, object] = {}
    for name in _PARTS:
        descriptor = descriptors.get(name)
        assert descriptor is not None
        if descriptor.kind == "null":
            parts[name], normalized_parts[name] = None, None
            continue
        descriptor = _keys(descriptor, ("length", "sha256"))
        maximum = object.__getattribute__(
            policy,
            "max_inventory_bytes" if name == "source_inventory" else "max_" + name + "_bytes",
        )
        size, digest = _integer(descriptor.get("length")), _text(descriptor.get("sha256"))
        _archive(
            size is not None and digest is not None and _HEX.fullmatch(digest) is not None,
            "manifest-part",
        )
        assert size is not None and digest is not None
        _bound(size, maximum, "part-bytes")
        _archive(end + size <= len(archive), "part-length")
        data = archive[end : end + size]
        _archive(hashlib.sha256(data).hexdigest() == digest, "part-digest")
        end += size
        parts[name], normalized_parts[name] = data, {"length": size, "sha256": digest}
    _archive(end == len(archive), "archive-eof")
    manifest: dict[str, object] = {
        "schema": ARCHIVE_SCHEMA,
        "profile": PROFILE,
        "limits": {name: object.__getattribute__(policy, name) for name, _ in _LIMITS},
        "returncode": returncode,
        "source_root_aliases": list(aliases),
        "parts": normalized_parts,
    }
    _archive(_canonical(manifest, policy.max_manifest_bytes) == raw_manifest, "manifest-canonical")
    return parse_codeql_observations(
        parts["report"],
        stdout=parts["stdout"],
        stderr=parts["stderr"],
        returncode=returncode,
        source_inventory=parts["source_inventory"],
        source_root_aliases=aliases,
        limits=policy,
    )
