"""Strict opt-in reader for the R19-A raw Joern export; never maps to a CPG.

Contract: docs/CONTRACT-BHMEA-JOERN-RAW-V2-2026-09-25.md. Raw observations do
not establish resolved dispatch, binding, effects, purity or canonical identity.
The existing v1 producer/reader/default path is deliberately untouched.
"""

from __future__ import annotations

import hashlib
import json
import re
import struct
from pathlib import PurePosixPath
from typing import Final, cast

from analysis.cpg_ingest.joern_schema_v2 import EDGE_PROPERTIES, NODE_PROPERTIES

_SHA256: Final = re.compile(r"[0-9a-f]{64}\Z")
_ID: Final = re.compile(r"(?:0|[1-9][0-9]*)\Z")
_RAW_CAPS: Final = frozenset({"raw_nodes", "raw_edges", "typed_properties"})
_DERIVED_CAPS: Final = frozenset(
    {
        "call_target_completeness",
        "actual_formal_binding",
        "return_result_binding",
        "effect_analysis",
        "purity_certification",
    }
)
_TOOL_VERSIONS: Final = {
    "joern-console": "4.0.554",
    "frontend": "4.0.554",
    "cpg-domain": "1.7.65",
    "flatgraph-core": "0.1.31",
}


class RawExportError(ValueError):
    """Malformed, unsupported or internally inconsistent raw export."""


class RawExportFailedError(RawExportError):
    """A well-formed failure report is not a usable completed graph."""


def _object(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict) or any(not isinstance(k, str) for k in value):
        raise RawExportError(f"{label} must be an object with string keys")
    return cast("dict[str, object]", value)


def _shape(value: object, keys: set[str] | frozenset[str], label: str) -> dict[str, object]:
    obj = _object(value, label)
    if set(obj) != keys:
        raise RawExportError(f"{label} has missing or unknown fields")
    return obj


def _string(value: object, label: str, *, nonempty: bool = True) -> str:
    if not isinstance(value, str) or (nonempty and not value):
        raise RawExportError(f"{label} must be a {'nonempty ' if nonempty else ''}string")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise RawExportError(f"{label} must be valid UTF-8") from exc
    return value


def _digest(value: object, label: str) -> str:
    text = _string(value, label)
    if not _SHA256.fullmatch(text):
        raise RawExportError(f"{label} must be lowercase SHA256 hex")
    return text


def _array(value: object, label: str) -> list[object]:
    if not isinstance(value, list):
        raise RawExportError(f"{label} must be an array")
    return value


def _artifact(value: object, label: str, *, tool: bool = False) -> dict[str, object]:
    keys = {"path", "sha256"} | ({"role", "version"} if tool else set())
    obj = _shape(value, keys, label)
    path = _string(obj["path"], f"{label}.path")
    if not PurePosixPath(path).is_absolute() or "\x00" in path:
        raise RawExportError(f"{label}.path must be an absolute locator")
    _digest(obj["sha256"], f"{label}.sha256")
    return obj


def source_tree_digest(files: object) -> str:
    """Hash a validated manifest, not unseen source bytes or canonical program semantics."""
    md = hashlib.sha256(b"scanipy-source-tree/1\0")
    previous: bytes | None = None
    for value in _array(files, "source.files"):
        entry = _shape(value, {"path", "size", "sha256"}, "source file")
        path = _string(entry["path"], "source file.path")
        parts = path.split("/")
        if path.startswith("/") or any(p in {"", ".", ".."} for p in parts) or "\0" in path:
            raise RawExportError("source file.path must be a normalized relative POSIX path")
        encoded = path.encode("utf-8")
        if previous is not None and encoded <= previous:
            raise RawExportError("source file paths must be unique and UTF-8-byte sorted")
        previous = encoded
        size = entry["size"]
        if type(size) is not int or not 0 <= size <= 2**53 - 1:
            raise RawExportError("source file.size must be an exact nonnegative JSON integer")
        digest = _digest(entry["sha256"], "source file.sha256")
        md.update(struct.pack(">Q", len(encoded)))
        md.update(encoded)
        md.update(struct.pack(">Q", size))
        md.update(bytes.fromhex(digest))
    return md.hexdigest()


def _producer(value: object) -> str:
    producer = _shape(
        value,
        {
            "schema_version",
            "image",
            "tools",
            "script",
            "input_cpg",
            "source",
            "frontend",
            "import_mode",
            "java_runtime_version",
            "java_tool_options",
        },
        "producer",
    )
    if type(producer["schema_version"]) is not int or producer["schema_version"] != 1:
        raise RawExportError("unsupported producer schema version")
    image = _shape(producer["image"], {"kind", "reference", "observation"}, "producer.image")
    if image["kind"] != "docker-image-id" or image["observation"] != "caller-observed":
        raise RawExportError("unsupported image identity/observation contract")
    reference = _string(image["reference"], "image.reference")
    if not reference.startswith("sha256:"):
        raise RawExportError("image reference must be a SHA256 Docker image ID")
    _digest(reference[7:], "image.reference")
    roles: set[str] = set()
    for raw_tool in _array(producer["tools"], "producer.tools"):
        tool = _artifact(raw_tool, "producer tool", tool=True)
        role = _string(tool["role"], "tool.role")
        if role in roles or role not in _TOOL_VERSIONS:
            raise RawExportError("unknown or duplicate producer tool role")
        roles.add(role)
        if tool["version"] != _TOOL_VERSIONS[role]:
            raise RawExportError(f"unsupported runtime version for {role}")
    if roles != set(_TOOL_VERSIONS):
        raise RawExportError("missing producer tool identity")
    _artifact(producer["script"], "producer.script")
    _artifact(producer["input_cpg"], "producer.input_cpg")
    source = _shape(
        producer["source"], {"root", "tree_namespace", "tree_sha256", "files"}, "producer.source"
    )
    root = _string(source["root"], "source.root")
    if not PurePosixPath(root).is_absolute() or "\0" in root:
        raise RawExportError("source root must be an absolute locator")
    if source["tree_namespace"] != "scanipy-source-tree/1":
        raise RawExportError("unsupported source-tree namespace")
    if _digest(source["tree_sha256"], "source.tree_sha256") != source_tree_digest(source["files"]):
        raise RawExportError("source tree digest does not bind the manifest")
    frontend = _string(producer["frontend"], "producer.frontend")
    if frontend not in {"javasrc", "pythonsrc"}:
        raise RawExportError("unsupported raw-v2 frontend")
    if producer["import_mode"] != "importCpg-default-overlays":
        raise RawExportError("unsupported import mode")
    _string(producer["java_runtime_version"], "producer.java_runtime_version")
    _string(producer["java_tool_options"], "producer.java_tool_options", nonempty=False)
    return frontend


def _property(value: object, kind: str, quantity: str, label: str) -> None:
    values = _array(value, label) if quantity == "many" else [value]
    expected = {"str": str, "int": int, "bool": bool}[kind]
    for item in values:
        if type(item) is not expected:
            raise RawExportError(f"{label} has incorrect native property type")
        if expected is str:
            _string(item, label, nonempty=False)
        if expected is int and not -(2**31) <= cast("int", item) < 2**31:
            raise RawExportError(f"{label} exceeds pinned IntType range")


def _nodes(value: object, frontend: str) -> dict[str, dict[str, object]]:
    by_id: dict[str, dict[str, object]] = {}
    metadata: list[dict[str, object]] = []
    for raw_node in _array(value, "nodes"):
        node = _shape(raw_node, {"id", "kind", "properties", "missing_properties"}, "node")
        node_id = _string(node["id"], "node.id")
        if not _ID.fullmatch(node_id) or int(node_id) > 2**63 - 1 or node_id in by_id:
            raise RawExportError("invalid or duplicate node ID")
        kind = _string(node["kind"], "node.kind")
        if kind not in NODE_PROPERTIES:
            raise RawExportError(f"unsupported pinned node kind: {kind}")
        properties = _object(node["properties"], "node.properties")
        allowed = NODE_PROPERTIES[kind]
        if set(properties) - set(allowed):
            raise RawExportError(f"unknown property for {kind}")
        for key, property_value in properties.items():
            native_type, quantity = allowed[key]
            _property(property_value, native_type, quantity, f"{kind}.{key}")
        required = {key for key, (_, quantity) in allowed.items() if quantity == "one"}
        missing = _array(node["missing_properties"], "node.missing_properties")
        if missing != sorted(required - set(properties)):
            raise RawExportError(f"missing pinned properties must be explicit for {kind}")
        by_id[node_id] = node
        if kind == "META_DATA":
            metadata.append(properties)
    if len(metadata) != 1 or metadata[0].get("LANGUAGE") != frontend.upper():
        raise RawExportError("expected one metadata node matching the declared frontend")
    return by_id


def _edges(value: object, nodes: dict[str, dict[str, object]]) -> None:
    expression_kinds = {
        kind for kind, props in NODE_PROPERTIES.items() if "ARGUMENT_INDEX" in props
    }
    ast_parents: dict[str, str] = {}
    parameter_links: list[tuple[str, str]] = []
    for raw_edge in _array(value, "edges"):
        edge = _shape(raw_edge, {"src", "dst", "kind", "properties"}, "edge")
        src = _string(edge["src"], "edge.src")
        dst = _string(edge["dst"], "edge.dst")
        if src not in nodes or dst not in nodes:
            raise RawExportError("dangling edge endpoint")
        kind = _string(edge["kind"], "edge.kind")
        if kind not in EDGE_PROPERTIES:
            raise RawExportError(f"unsupported pinned edge kind: {kind}")
        properties = _object(edge["properties"], "edge.properties")
        allowed_key = EDGE_PROPERTIES[kind]
        if set(properties) - ({allowed_key} if allowed_key else set()):
            raise RawExportError(f"unknown property for {kind}")
        for item in properties.values():
            _string(item, f"{kind} property", nonempty=False)
        source_kind, target_kind = nodes[src]["kind"], nodes[dst]["kind"]
        if kind == "AST":
            if dst in ast_parents and ast_parents[dst] != src:
                raise RawExportError("AST node cannot have multiple owners")
            ast_parents[dst] = src
        if kind == "PARAMETER_LINK":
            parameter_links.append((src, dst))
        if kind == "CALL" and (source_kind != "CALL" or target_kind != "METHOD"):
            raise RawExportError("CALL must connect a call to a method")
        if kind == "PARAMETER_LINK" and (
            source_kind != "METHOD_PARAMETER_IN" or target_kind != "METHOD_PARAMETER_OUT"
        ):
            raise RawExportError("PARAMETER_LINK must connect formal input to formal output")
        if kind == "RECEIVER" and (source_kind != "CALL" or target_kind not in expression_kinds):
            raise RawExportError("RECEIVER must connect a call to its callee expression")
        if kind == "ARGUMENT" and (
            source_kind not in {"CALL", "RETURN"} or target_kind not in expression_kinds
        ):
            raise RawExportError("ARGUMENT must connect a call/return to an expression")
        if (
            kind == "REF"
            and source_kind == "IDENTIFIER"
            and target_kind not in {"LOCAL", "METHOD_PARAMETER_IN", "MEMBER", "TYPE_DECL", "METHOD"}
        ):
            raise RawExportError("identifier REF must target a declaration")
    _ownership(nodes, ast_parents, parameter_links)


def _ownership(
    nodes: dict[str, dict[str, object]],
    ast_parents: dict[str, str],
    parameter_links: list[tuple[str, str]],
) -> None:
    checked: set[str] = set()
    for node_id in ast_parents:
        trail: set[str] = set()
        cursor = node_id
        while cursor in ast_parents and cursor not in checked:
            if cursor in trail:
                raise RawExportError("cyclic AST ownership")
            trail.add(cursor)
            cursor = ast_parents[cursor]
        checked.update(trail)
    for node_id, node in nodes.items():
        if node["kind"] in {"METHOD_PARAMETER_IN", "METHOD_PARAMETER_OUT", "METHOD_RETURN"}:
            owner = ast_parents.get(node_id)
            if owner is None or nodes[owner]["kind"] != "METHOD":
                raise RawExportError("formal/return node must have a direct METHOD AST owner")
    for src, dst in parameter_links:
        if ast_parents[src] != ast_parents[dst]:
            raise RawExportError("PARAMETER_LINK endpoints must belong to the same method")


def validate_raw_export(value: object, *, require_completed: bool = True) -> None:
    """Validate one document without coercion or semantic enrichment."""
    document = _shape(
        value,
        {
            "format",
            "format_version",
            "status",
            "producer",
            "capabilities",
            "nodes",
            "edges",
            "error",
        },
        "raw export",
    )
    if document["format"] != "scanipy-joern-export":
        raise RawExportError("unsupported export format")
    if type(document["format_version"]) is not int or document["format_version"] != 2:
        raise RawExportError("unsupported raw export version")
    frontend = _producer(document["producer"])
    status = _string(document["status"], "status")
    if status not in {"completed", "failed"}:
        raise RawExportError("unsupported export status")
    capabilities = _shape(document["capabilities"], _RAW_CAPS | _DERIVED_CAPS, "capabilities")
    for name, value in capabilities.items():
        capability = _shape(value, {"status", "reason"}, f"capability {name}")
        expected = status if name in _RAW_CAPS else "unsupported"
        if capability["status"] != expected:
            raise RawExportError(f"invalid certainty for capability {name}")
        _string(capability["reason"], f"capability {name}.reason")
    if status == "failed":
        if document["nodes"] is not None or document["edges"] is not None:
            raise RawExportError("failed export cannot publish partially complete arrays")
        error = _shape(document["error"], {"code", "message"}, "error")
        if error["code"] != "raw-export-failed":
            raise RawExportError("unknown export error code")
        _string(error["message"], "error.message")
        if require_completed:
            raise RawExportFailedError("raw export failed; no completed graph is available")
    else:
        if document["error"] is not None:
            raise RawExportError("completed export cannot contain an error")
        _edges(document["edges"], _nodes(document["nodes"], frontend))


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise RawExportError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def parse_raw_export(
    data: str | bytes, *, require_completed: bool = True, max_bytes: int = 64 * 1024 * 1024
) -> dict[str, object]:
    """Decode a bounded UTF-8 raw-v2 document; reject JSON ambiguity and failure by default."""
    if type(max_bytes) is not int or max_bytes <= 0:
        raise RawExportError("max_bytes must be a positive integer")
    try:
        encoded = data.encode("utf-8") if isinstance(data, str) else data
        if len(encoded) > max_bytes:
            raise RawExportError("raw export exceeds reader byte limit")
        decoded = encoded.decode("utf-8")
        value: object = json.loads(decoded, object_pairs_hook=_unique_object)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise RawExportError("raw export is not valid UTF-8 JSON") from exc
    validate_raw_export(value, require_completed=require_completed)
    return _object(value, "raw export")
