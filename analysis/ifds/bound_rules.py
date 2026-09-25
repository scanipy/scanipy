"""Closed scalar-profile metadata and rule codecs, never acceptance authority.

Contract: docs/bhmea/SOURCE-BOUND-SCALAR-IFDS.md (#397). This module must
remain independent of services: the accepted-input resolver re-exports the
same QualifiedRuleKey and delegates to its codec. Legacy DSL is unchanged.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, fields
from typing import Final, cast
from uuid import UUID

QUALIFIED_RULE_SCHEMA: Final = "scanipy-qualified-rule/1"
RULE_SCHEMA: Final = "scanipy-bound-rule-set/1"
MODEL_SCHEMA: Final = "scanipy-operation-models/1"
SCALAR_SEMANTICS: Final = "scanipy-scalar-ifds/1"
PROJECTION_PROFILE: Final = "scanipy-java-python-scalar-flow/1"

_IDENTIFIER = re.compile(r"[A-Za-z][A-Za-z0-9_.:/-]{0,127}\Z", re.ASCII)
_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,127}\Z", re.ASCII)
_DIGEST = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
_VERSION = re.compile(r"(0|[1-9][0-9]{0,9})\.(0|[1-9][0-9]{0,9})\.(0|[1-9][0-9]{0,9})\Z", re.ASCII)


class BoundRuleError(ValueError):
    """Stable safe failure code; input content is never included in the message."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ScalarLimits:
    """Trusted coordinator settings; every field can only lower its ceiling."""

    max_files: int = 16
    max_file_bytes: int = 262144
    max_source_bytes: int = 1048576
    max_path_bytes: int = 1024
    max_path_components: int = 32
    max_rule_bytes: int = 262144
    max_model_bytes: int = 524288
    max_accepted_bytes: int = 1048576
    max_clauses: int = 256
    max_models: int = 128
    max_rule_json_depth: int = 24
    max_rule_json_values: int = 50000
    max_rule_string_bytes: int = 16384
    max_cpg_artifact_bytes: int = 32 * 1024 * 1024
    max_raw_export_bytes: int = 16 * 1024 * 1024
    max_native_nodes: int = 10000
    max_native_edges: int = 100000
    max_ast_nodes: int = 20000
    max_ast_depth: int = 128
    max_syntax_bytes: int = 8 * 1024 * 1024
    max_procedures: int = 128
    max_calls: int = 2048
    max_call_depth: int = 32
    max_operations: int = 10000
    max_values: int = 16384
    max_relations: int = 50000
    max_origins: int = 64
    max_facts: int = 131072
    max_path_states: int = 100000
    max_incoming: int = 20000
    max_summaries: int = 50000
    max_solver_work: int = 2000000
    max_occurrences: int = 4096
    max_witness_steps: int = 4096
    max_total_witness_steps: int = 65536
    max_result_bytes: int = 8 * 1024 * 1024
    max_associations: int = 100000
    max_evidence_references: int = 100000

    def __post_init__(self) -> None:
        for definition in fields(self):
            value = getattr(self, definition.name)
            if type(value) is not int or not 0 < value <= cast("int", definition.default):
                raise BoundRuleError("invalid-limit")


def checked_limits(limits: ScalarLimits) -> ScalarLimits:
    if type(limits) is not ScalarLimits:
        raise BoundRuleError("invalid-limit")
    limits.__post_init__()
    return limits


def _checked_string(value: object, *, maximum: int = 16384) -> str:
    if type(value) is not str:
        raise BoundRuleError("invalid-string")
    if len(value) > maximum:
        raise BoundRuleError("string-limit")
    if "\x00" in value:
        raise BoundRuleError("invalid-string")
    try:
        if len(value.encode("utf-8")) > maximum:
            raise BoundRuleError("string-limit")
    except UnicodeError as exc:
        raise BoundRuleError("invalid-string") from exc
    return value


def _identifier(value: object) -> str:
    value = _checked_string(value, maximum=128)
    if _IDENTIFIER.fullmatch(value) is None:
        raise BoundRuleError("invalid-id")
    return value


def _digest(value: object) -> str:
    value = _checked_string(value, maximum=64)
    if _DIGEST.fullmatch(value) is None:
        raise BoundRuleError("invalid-digest")
    return value


def _version(value: object) -> str:
    value = _checked_string(value, maximum=32)
    match = _VERSION.fullmatch(value)
    if match is None or any(int(part) > 2147483647 for part in match.groups()):
        raise BoundRuleError("invalid-version")
    return value


def _uuid(value: object) -> str:
    value = _checked_string(value, maximum=36)
    try:
        if str(UUID(value)) != value:
            raise BoundRuleError("invalid-uuid")
    except ValueError as exc:
        raise BoundRuleError("invalid-uuid") from exc
    return value


@dataclass(frozen=True, slots=True)
class QualifiedRuleKey:
    """One immutable qualified content key; construction does NOT grant authority."""

    registry_id: str
    bundle_id: str
    scope: str
    org_id: str | None
    S_version: str
    accepted_content_digest: str
    detector_id: str
    detector_version: str
    detector_raw_sha256: str
    rule_id: str
    rule_artifact_id: str
    rule_artifact_version: str
    rule_raw_sha256: str
    model_artifact_id: str
    model_artifact_version: str
    model_raw_sha256: str
    semantic_descriptor_digest: str
    schema: str = QUALIFIED_RULE_SCHEMA

    def __post_init__(self) -> None:
        if type(self.schema) is not str or self.schema != QUALIFIED_RULE_SCHEMA:
            raise BoundRuleError("unknown-key-schema")
        _uuid(self.registry_id)
        _uuid(self.bundle_id)
        if type(self.scope) is not str or self.scope not in ("global", "customer"):
            raise BoundRuleError("invalid-scope")
        if self.scope == "global":
            if self.org_id is not None:
                raise BoundRuleError("invalid-scope")
        else:
            _uuid(self.org_id)
        for value in (
            self.S_version,
            self.detector_version,
            self.rule_artifact_version,
            self.model_artifact_version,
        ):
            _version(value)
        for value in (
            self.accepted_content_digest,
            self.detector_raw_sha256,
            self.rule_raw_sha256,
            self.model_raw_sha256,
            self.semantic_descriptor_digest,
        ):
            _digest(value)
        for value in (
            self.detector_id,
            self.rule_id,
            self.rule_artifact_id,
            self.model_artifact_id,
        ):
            _identifier(value)


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise BoundRuleError("duplicate-key")
        result[key] = value
    return result


def _integer(value: str) -> int:
    if len(value) > 20:
        raise BoundRuleError("invalid-number")
    result = int(value)
    if not -(2**63) <= result < 2**63:
        raise BoundRuleError("invalid-number")
    return result


def _invalid_number(_: str) -> object:
    raise BoundRuleError("invalid-number")


def _preflight_json(data: bytes, *, depth_limit: int, value_limit: int, string_limit: int) -> None:
    """Bound containers, tokens and raw string extent before json.loads allocates."""
    depth = count = extent = 0
    quoted = escaped = atom = False
    for byte in data:
        if quoted:
            extent += 1
            # A decoded scalar can require at most six ASCII escape bytes per
            # UTF-8 byte. Exact decoded string size is checked after parsing.
            if extent > string_limit * 6 + 1:
                raise BoundRuleError("string-limit")
            if escaped:
                escaped = False
            elif byte == 92:
                escaped = True
            elif byte == 34:
                quoted = False
            continue
        if byte in b" \r\n\t,:":
            atom = False
            continue
        if byte == 34:
            quoted = True
            extent = 0
            count += 1
            atom = False
        elif byte in (91, 123):
            depth += 1
            count += 1
            atom = False
            if depth > depth_limit:
                raise BoundRuleError("json-depth-limit")
        elif byte in (93, 125):
            depth -= 1
            atom = False
            if depth < 0:
                raise BoundRuleError("invalid-json")
        elif not atom:
            count += 1
            atom = True
        if count > value_limit:
            raise BoundRuleError("json-value-limit")


def decode_bounded_json(
    data: bytes, *, max_bytes: int, max_depth: int, max_values: int, max_string_bytes: int
) -> object:
    """Strict bounded primitive JSON; no implicit input coercion or float domain."""
    if type(data) is not bytes:
        raise BoundRuleError("input-type")
    if len(data) > max_bytes:
        raise BoundRuleError("json-byte-limit")
    _preflight_json(
        data, depth_limit=max_depth, value_limit=max_values, string_limit=max_string_bytes
    )
    try:
        result: object = json.loads(
            data.decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_int=_integer,
            parse_float=_invalid_number,
            parse_constant=_invalid_number,
        )
    except (UnicodeError, ValueError, RecursionError) as exc:
        if isinstance(exc, BoundRuleError):
            raise
        raise BoundRuleError("invalid-json") from exc
    pending = [result]
    while pending:
        value = pending.pop()
        if type(value) is str:
            _checked_string(value, maximum=max_string_bytes)
        elif type(value) is list:
            pending.extend(value)
        elif type(value) is dict:
            for key, item in value.items():
                _checked_string(key, maximum=max_string_bytes)
                pending.append(item)
    return result


def canonical_json(value: object) -> bytes:
    """Exact control-wire spelling, NOT semantic graph canonicalization."""
    try:
        return json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    except (ValueError, TypeError, UnicodeError, RecursionError) as exc:
        raise BoundRuleError("invalid-json") from exc


def _closed(value: object, names: set[str]) -> dict[str, object]:
    if type(value) is not dict or set(value) != names:
        raise BoundRuleError("invalid-fields")
    return cast("dict[str, object]", value)


def encode_qualified_rule_key(key: QualifiedRuleKey) -> bytes:
    if type(key) is not QualifiedRuleKey:
        raise BoundRuleError("key-type")
    key.__post_init__()
    encoded = canonical_json(asdict(key))
    if len(encoded) > 16384:
        raise BoundRuleError("json-byte-limit")
    return encoded


def decode_qualified_rule_key(data: bytes) -> QualifiedRuleKey:
    value = decode_bounded_json(
        data, max_bytes=16384, max_depth=4, max_values=64, max_string_bytes=16384
    )
    row = _closed(value, {definition.name for definition in fields(QualifiedRuleKey)})
    if canonical_json(row) != data:
        raise BoundRuleError("noncanonical-key")
    key = QualifiedRuleKey(
        registry_id=_checked_string(row["registry_id"]),
        bundle_id=_checked_string(row["bundle_id"]),
        scope=_checked_string(row["scope"]),
        org_id=None if row["org_id"] is None else _checked_string(row["org_id"]),
        S_version=_checked_string(row["S_version"]),
        accepted_content_digest=_checked_string(row["accepted_content_digest"]),
        detector_id=_checked_string(row["detector_id"]),
        detector_version=_checked_string(row["detector_version"]),
        detector_raw_sha256=_checked_string(row["detector_raw_sha256"]),
        rule_id=_checked_string(row["rule_id"]),
        rule_artifact_id=_checked_string(row["rule_artifact_id"]),
        rule_artifact_version=_checked_string(row["rule_artifact_version"]),
        rule_raw_sha256=_checked_string(row["rule_raw_sha256"]),
        model_artifact_id=_checked_string(row["model_artifact_id"]),
        model_artifact_version=_checked_string(row["model_artifact_version"]),
        model_raw_sha256=_checked_string(row["model_raw_sha256"]),
        semantic_descriptor_digest=_checked_string(row["semantic_descriptor_digest"]),
        schema=_checked_string(row["schema"]),
    )
    return key
