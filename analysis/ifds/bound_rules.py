"""Closed scalar-profile metadata and rule codecs, never acceptance authority.

Contract: docs/bhmea/SOURCE-BOUND-SCALAR-IFDS.md (#397). This module must
remain independent of services: the accepted-input resolver re-exports the
same QualifiedRuleKey and delegates to its codec. Legacy DSL is unchanged.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import InitVar, asdict, dataclass, field, fields
from typing import TYPE_CHECKING, Final, cast
from uuid import UUID

if TYPE_CHECKING:
    from analysis.cpg_ingest.typed_observed import FrozenObject

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


_PYTHON_TARGET: Final = "scanipy-target-cpython311-posix/1"
_JAVA_TARGET: Final = "scanipy-target-java21-jdbc/1"
_TYPE_IDS: Final = frozenset(
    (
        "python.exact-str",
        "python.int",
        "java.lang.String",
        "java.sql.Statement",
        "java.sql.ResultSet",
    )
)


def _array(value: object, *, maximum: int, minimum: int = 0) -> list[object]:
    if type(value) is not list or not minimum <= len(value) <= maximum:
        raise BoundRuleError("invalid-array")
    return cast("list[object]", value)


def _enum(value: object, choices: tuple[str, ...] | frozenset[str]) -> str:
    if type(value) is not str or value not in choices:
        raise BoundRuleError("invalid-enum")
    return value


def _position(value: object, *, result: bool = False) -> dict[str, object]:
    row = _closed(value, {"kind", "index"})
    expected = "result" if result else "argument"
    if row["kind"] != expected or type(row["kind"]) is not str:
        raise BoundRuleError("invalid-position")
    index = row["index"]
    if type(index) is not int or not 0 <= index <= (0 if result else 255):
        raise BoundRuleError("invalid-position")
    return row


def _argument(index: int) -> dict[str, object]:
    return {"kind": "argument", "index": index}


def _initial_model(model_id: str) -> dict[str, object]:
    """A fresh closed capability row, not an artifact/model authority registry."""
    if model_id not in (
        "python.string-concat/1",
        "python.os-system/1",
        "java.string-concat/1",
        "java.jdbc-execute-query/1",
    ):
        raise BoundRuleError("unsupported-model")
    python = model_id.startswith("python.")
    concat = model_id.endswith("string-concat/1")
    string_type = "python.exact-str" if python else "java.lang.String"
    checks: tuple[tuple[str, str], ...]
    if concat:
        checks = (
            (("python-exact-str-operands/1", "checked"),)
            if python
            else (
                ("java-standard-string-semantics/1", "assumed"),
                ("java-string-operands/1", "checked"),
            )
        )
    elif python:
        checks = (
            ("python-direct-os-import/1", "checked"),
            ("python-exact-str-argument/1", "checked"),
            ("python-no-external-binding-mutation/1", "assumed"),
            ("python-no-local-binding-mutation/1", "checked"),
            ("python-standard-os-implementation/1", "assumed"),
            ("terminal-selected-entry-call/1", "checked"),
        )
    else:
        checks = (
            ("java-declared-statement-receiver/1", "checked"),
            ("java-string-argument/1", "checked"),
            ("java21-jdbc-contract/1", "assumed"),
            ("terminal-selected-entry-call/1", "checked"),
        )
    symbol: dict[str, object] | None = None
    if not concat:
        symbol = {
            "owner": "os" if python else "java.sql.Statement",
            "member": "system" if python else "executeQuery",
        }
    result = {"kind": "result", "index": 0}
    return {
        "model_id": model_id,
        "language": "python" if python else "java",
        "kind": "builtin-operator" if concat else "external-call",
        "target_platform_profile": _PYTHON_TARGET if python else _JAVA_TARGET,
        "operation": "string-concat" if concat else "external-api",
        "symbol": symbol,
        "signature": {
            "receiver": None if concat or python else "java.sql.Statement",
            "parameters": [string_type] * (2 if concat else 1),
            "result": string_type if concat else ("python.int" if python else "java.sql.ResultSet"),
        },
        "preconditions": [{"id": name, "evidence_kind": kind} for name, kind in checks],
        "normal": {
            "result": "defined",
            "effects": ["allocation"]
            if concat
            else ["external-io", "external-process" if python else "unknown-external-effect"],
        },
        "exceptional": {
            "result": "absent",
            "continuation": "exit-unknown-exception",
            "effects": ["resource-failure"] if concat else ["unknown-external-effect"],
        },
        "transfer_authorization": {
            "sink_inputs": []
            if concat
            else [
                {
                    "position": _argument(0),
                    "class_id": "injection",
                    "context_id": "posix-shell-command" if python else "sql-query-text",
                }
            ],
            "propagation": [{"from": _argument(index), "to": result} for index in range(2)]
            if concat
            else [],
            "sanitization": [],
        },
    }


def _models(
    value: object, limits: ScalarLimits
) -> tuple[dict[str, object], dict[str, dict[str, object]]]:
    root = _closed(value, {"schema", "target_platform_profiles", "models"})
    if root["schema"] != MODEL_SCHEMA:
        raise BoundRuleError("unknown-model-schema")
    profiles = [
        _enum(profile, (_PYTHON_TARGET, _JAVA_TARGET))
        for profile in _array(root["target_platform_profiles"], maximum=2, minimum=1)
    ]
    if profiles != sorted(set(profiles)):
        raise BoundRuleError("invalid-profile-order")
    models: dict[str, dict[str, object]] = {}
    used_profiles: set[str] = set()
    previous: str | None = None
    for value in _array(root["models"], maximum=limits.max_models, minimum=1):
        if type(value) is not dict or "model_id" not in value:
            raise BoundRuleError("invalid-model")
        row = cast("dict[str, object]", value)
        model_id = _identifier(row["model_id"])
        if previous is not None and model_id <= previous:
            raise BoundRuleError("invalid-model-order")
        # The strict parser below rejects every boolean before equality: Python
        # otherwise considers true==1 and false==0 inside nested structures.
        if row != _initial_model(model_id):
            raise BoundRuleError("unsupported-model")
        models[model_id] = row
        used_profiles.add(cast("str", row["target_platform_profile"]))
        previous = model_id
    if set(profiles) != used_profiles:
        raise BoundRuleError("unbound-target-profile")
    return root, models


def _source_selector(value: object, languages: list[str], limits: ScalarLimits) -> str:
    row = _closed(
        value, {"kind", "language", "source_file", "declaration", "formal_index", "parameter_types"}
    )
    if row["kind"] != "entry_parameter":
        raise BoundRuleError("unsupported-selector")
    language = _enum(row["language"], ("python", "java"))
    if language not in languages:
        raise BoundRuleError("selector-language")
    path = _checked_string(row["source_file"], maximum=limits.max_path_bytes)
    components = path.split("/")
    if (
        len(components) > limits.max_path_components
        or any(part in ("", ".", "..") for part in components)
        or "\\" in path
        or any(unicodedata.category(character) == "Cc" for character in path)
    ):
        raise BoundRuleError("invalid-source-path")
    names = _array(row["declaration"], maximum=32, minimum=1)
    for name in names:
        if _NAME.fullmatch(_checked_string(name, maximum=128)) is None:
            raise BoundRuleError("invalid-name")
    index = row["formal_index"]
    if type(index) is not int or not 0 <= index <= 255:
        raise BoundRuleError("invalid-formal-index")
    if language == "python":
        if len(names) != 1 or row["parameter_types"] is not None or not path.endswith(".py"):
            raise BoundRuleError("unsupported-entry-selector")
    else:
        for parameter in _array(row["parameter_types"], maximum=256):
            _enum(parameter, _TYPE_IDS)
    return language


def _rule(
    value: object,
    *,
    models: dict[str, dict[str, object]],
    key: QualifiedRuleKey,
    language: str,
    limits: ScalarLimits,
) -> dict[str, object]:
    # Reuse the established class vocabulary, never the legacy spec parser or
    # transfer implementation. Lazy import keeps QualifiedRuleKey stdlib-only.
    from analysis.ifds.dsl.spec import CLASS_NAMES

    root = _closed(
        value,
        {
            "schema",
            "semantics",
            "spec_id",
            "class_id",
            "engine",
            "languages",
            "projection_profile",
            "model_artifact_digest",
            "clauses",
        },
    )
    if root["schema"] != RULE_SCHEMA or root["semantics"] != SCALAR_SEMANTICS:
        raise BoundRuleError("unknown-rule-semantics")
    if root["engine"] != "ifds" or root["projection_profile"] != PROJECTION_PROFILE:
        raise BoundRuleError("unsupported-profile")
    if (
        _identifier(root["spec_id"]) != key.rule_id
        or _digest(root["model_artifact_digest"]) != key.model_raw_sha256
    ):
        raise BoundRuleError("rule-content-binding")
    class_id = _enum(root["class_id"], CLASS_NAMES)
    languages = [
        _enum(item, ("python", "java")) for item in _array(root["languages"], maximum=2, minimum=1)
    ]
    if len(set(languages)) != len(languages) or language not in languages:
        raise BoundRuleError("invalid-languages")
    source_count = sink_count = 0
    contexts: set[str] = set()
    for value in _array(root["clauses"], maximum=limits.max_clauses, minimum=1):
        if type(value) is not dict:
            raise BoundRuleError("invalid-clause")
        clause = cast("dict[str, object]", value)
        primitive = _enum(clause.get("primitive"), ("source", "sink", "propagate", "sanitize"))
        if primitive == "source":
            _closed(clause, {"primitive", "selector"})
            source_count += _source_selector(clause["selector"], languages, limits) == language
            continue
        additions = {"from", "to"} if primitive == "propagate" else {"position", "context_id"}
        _closed(clause, {"primitive", "selector"} | additions)
        selector = _closed(clause["selector"], {"kind", "language", "model_id"})
        if selector["kind"] != "model":
            raise BoundRuleError("unsupported-selector")
        selected_language = _enum(selector["language"], ("python", "java"))
        model_id = _identifier(selector["model_id"])
        if model_id not in models:
            raise BoundRuleError("missing-model")
        model = models[model_id]
        if selected_language not in languages or selected_language != model["language"]:
            raise BoundRuleError("selector-language")
        authorization = cast("dict[str, object]", model["transfer_authorization"])
        requested: dict[str, object]
        if primitive == "propagate":
            requested = {
                "from": _position(clause["from"]),
                "to": _position(clause["to"], result=True),
            }
            allowed = _array(authorization["propagation"], maximum=256)
        else:
            context = _enum(clause["context_id"], ("posix-shell-command", "sql-query-text"))
            requested = {
                "position": _position(clause["position"], result=primitive == "sanitize"),
                "class_id": class_id,
                "context_id": context,
            }
            allowed = _array(
                authorization["sink_inputs" if primitive == "sink" else "sanitization"], maximum=256
            )
            if selected_language == language:
                contexts.add(context)
                sink_count += primitive == "sink"
        if requested not in allowed:
            raise BoundRuleError("unauthorized-transfer")
    if source_count == 0 or sink_count == 0 or len(contexts) != 1:
        raise BoundRuleError("incomplete-rule")
    expected_context = "posix-shell-command" if language == "python" else "sql-query-text"
    if class_id != "injection" or contexts != {expected_context}:
        raise BoundRuleError("unsupported-class-context")
    return root


def _rule_json(data: bytes, *, maximum: int, limits: ScalarLimits) -> object:
    value = decode_bounded_json(
        data,
        max_bytes=maximum,
        max_depth=limits.max_rule_json_depth,
        max_values=limits.max_rule_json_values,
        max_string_bytes=limits.max_rule_string_bytes,
    )
    pending = [value]
    while pending:
        item = pending.pop()
        if type(item) is bool:
            raise BoundRuleError("unsupported-boolean")
        if type(item) is dict:
            pending.extend(item.values())
        elif type(item) is list:
            pending.extend(item)
    return value


@dataclass(frozen=True, slots=True)
class BoundRule:
    """Validated immutable content, NOT operational authority or execution readiness.

    Java content is decodable so a resolver can retain and inspect it; the first
    semantic producer separately refuses Java execution. Supplied Python objects
    cannot replace the raw byte decoding or introduce arbitrary model callbacks.
    """

    key: QualifiedRuleKey
    rule_bytes: bytes = field(repr=False)
    model_bytes: bytes = field(repr=False)
    language: str
    limits: InitVar[ScalarLimits | None] = None
    rule_document: FrozenObject = field(init=False, repr=False)
    model_document: FrozenObject = field(init=False, repr=False)

    def __post_init__(self, limits: ScalarLimits | None) -> None:
        from analysis.cpg_ingest.typed_observed import freeze_value

        checked = checked_limits(ScalarLimits() if limits is None else limits)
        if type(self.key) is not QualifiedRuleKey:
            raise BoundRuleError("key-type")
        self.key.__post_init__()
        _enum(self.language, ("python", "java"))
        if type(self.rule_bytes) is not bytes or type(self.model_bytes) is not bytes:
            raise BoundRuleError("input-type")
        if (
            len(self.rule_bytes) > checked.max_rule_bytes
            or len(self.model_bytes) > checked.max_model_bytes
            or len(self.rule_bytes) + len(self.model_bytes) > checked.max_accepted_bytes
        ):
            raise BoundRuleError("json-byte-limit")
        if (
            hashlib.sha256(self.rule_bytes).hexdigest() != self.key.rule_raw_sha256
            or hashlib.sha256(self.model_bytes).hexdigest() != self.key.model_raw_sha256
        ):
            raise BoundRuleError("raw-content-binding")
        model_document, models = _models(
            _rule_json(self.model_bytes, maximum=checked.max_model_bytes, limits=checked), checked
        )
        rule_document = _rule(
            _rule_json(self.rule_bytes, maximum=checked.max_rule_bytes, limits=checked),
            models=models,
            key=self.key,
            language=self.language,
            limits=checked,
        )
        object.__setattr__(self, "rule_document", cast("FrozenObject", freeze_value(rule_document)))
        object.__setattr__(
            self, "model_document", cast("FrozenObject", freeze_value(model_document))
        )


def decode_bound_rule(
    rule_bytes: bytes,
    model_bytes: bytes,
    *,
    key: QualifiedRuleKey,
    language: str,
    limits: ScalarLimits,
) -> BoundRule:
    """Decode one qualified rule's exact bytes without changing legacy DSL semantics."""
    return BoundRule(key, rule_bytes, model_bytes, language, limits)
