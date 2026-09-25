"""Opt-in immutable raw observations, not a semantic CPG or solver input.

Contract: docs/bhmea/TYPED-OBSERVED-CPG-CONTRACT.md (#393, R19-B1).
Native IDs/array ordinals are capture references, never canonical identities.
All views are mechanical evidence; binding/effects/purity stay unsupported.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, fields
from typing import Final, TypeAlias, cast

from analysis.cpg_ingest.joern_schema_v2 import NODE_PROPERTIES
from analysis.cpg_ingest.raw_v2 import RawExportError, RawExportFailedError, validate_raw_export

MODEL_VERSION: Final = "scanipy-cpg/2"
ROLE_PROFILE: Final = "scanipy-java-python-roles/1"
OBSERVED_STAGE: Final = "observed-only"


class ObservedGraphInputError(ValueError):
    """Capture failed; ``code`` is stable and diagnostics never echo source."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


class ObservedGraphUnsupportedError(ObservedGraphInputError):
    """An unknown profile/schema has no permissive fallback."""


class ObservedGraphLimitError(ObservedGraphInputError):
    """A hard capture/transport ceiling was exceeded; no completed prefix."""


class ObservedGraphArtifactError(ObservedGraphInputError):
    """The exact archive/byte binding is invalid."""


@dataclass(frozen=True, slots=True)
class ObservedGraphLimits:
    """Trusted coordinator may LOWER these fixed profile ceilings only."""

    max_raw_bytes: int = 16 * 1024 * 1024
    max_artifact_bytes: int = 32 * 1024 * 1024
    max_json_bytes: int = 64 * 1024 * 1024
    max_tar_bytes: int = 64 * 1024 * 1024 + 10240
    max_nodes: int = 10000
    max_edges: int = 100000
    max_source_files: int = 10000
    max_string_bytes: int = 1024 * 1024
    max_total_string_bytes: int = 8 * 1024 * 1024
    max_json_depth: int = 32
    max_json_values: int = 500000

    def __post_init__(self) -> None:
        for definition in fields(self):
            value = getattr(self, definition.name)
            if type(value) is not int or not 0 < value <= cast("int", definition.default):
                raise ObservedGraphLimitError(
                    "invalid-limit", "limits must be positive and within ceilings"
                )


def checked_limits(limits: ObservedGraphLimits | None) -> ObservedGraphLimits:
    """Shared by the separate wire module; no caller-provided limit subclasses."""
    if limits is None:
        return ObservedGraphLimits()
    if type(limits) is not ObservedGraphLimits:
        raise ObservedGraphLimitError("invalid-limit", "expected exact ObservedGraphLimits")
    limits.__post_init__()
    return limits


@dataclass(frozen=True, slots=True)
class FrozenArray:
    """An array is not interchangeable with an object or an absent property."""

    values: tuple[FrozenValue, ...]

    def __post_init__(self) -> None:
        if type(self.values) is not tuple:
            raise ObservedGraphInputError("mutable-value", "array storage must be an exact tuple")
        for value in self.values:
            _validate_frozen(value)


@dataclass(frozen=True, slots=True)
class FrozenObject:
    """Immutable sorted object entries; reconstruction always allocates fresh containers."""

    entries: tuple[tuple[str, FrozenValue], ...]

    def __post_init__(self) -> None:
        if type(self.entries) is not tuple:
            raise ObservedGraphInputError("mutable-value", "object storage must be an exact tuple")
        previous: str | None = None
        for pair in self.entries:
            if type(pair) is not tuple or len(pair) != 2 or type(pair[0]) is not str:
                raise ObservedGraphInputError("mutable-value", "invalid immutable object entry")
            key, value = pair
            if previous is not None and key <= previous:
                raise ObservedGraphInputError(
                    "object-order", "object keys must be unique and sorted"
                )
            _validate_frozen(key)
            _validate_frozen(value)
            previous = key

    def get(self, key: str) -> FrozenValue:
        """Return exact stored value; absent keys raise rather than invent a null."""
        for name, value in self.entries:
            if name == key:
                return value
        raise KeyError(key)


FrozenValue: TypeAlias = str | int | bool | None | FrozenArray | FrozenObject


def _validate_frozen(value: object) -> None:
    if type(value) in {str, int, bool, type(None)}:
        if type(value) is str:
            try:
                value.encode("utf-8")
            except UnicodeError as exc:
                raise ObservedGraphInputError("invalid-utf8", "invalid scalar text") from exc
        return
    if type(value) in {FrozenArray, FrozenObject}:
        # Their constructors validate contents. Objects bypassed with arbitrary
        # Python memory mutation are outside the value-object trust boundary.
        return
    raise ObservedGraphInputError(
        "mutable-value", "only exact supported frozen JSON values are allowed"
    )


def freeze_value(value: object) -> FrozenValue:
    """Freeze an already bounded, strictly parsed JSON value."""
    if type(value) is dict:
        obj = cast("dict[str, object]", value)
        return FrozenObject(tuple((key, freeze_value(obj[key])) for key in sorted(obj)))
    if type(value) is list:
        return FrozenArray(tuple(freeze_value(item) for item in cast("list[object]", value)))
    _validate_frozen(value)
    return cast("FrozenValue", value)


def thaw_value(value: FrozenValue) -> object:
    """Detached mutable replay, not original byte serialization."""
    if type(value) is FrozenObject:
        return {key: thaw_value(item) for key, item in value.entries}
    if type(value) is FrozenArray:
        return [thaw_value(item) for item in value.values]
    return value


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ObservedGraphInputError("duplicate-key", "duplicate JSON object key")
        result[key] = value
    return result


def _reject_number(_: str) -> object:
    raise ObservedGraphInputError(
        "invalid-number", "floats and nonfinite numbers are not supported"
    )


def decode_json_bytes(data: bytes, *, max_bytes: int, max_depth: int) -> object:
    """Bound bytes and lexical container depth BEFORE calling the JSON parser."""
    if type(data) is not bytes:
        raise ObservedGraphInputError("input-type", "input must be exact immutable bytes")
    if len(data) > max_bytes:
        raise ObservedGraphLimitError("byte-limit", "encoded JSON exceeds byte ceiling")
    depth = 0
    quoted = escaped = False
    for byte in data:
        if quoted:
            if escaped:
                escaped = False
            elif byte == 92:
                escaped = True
            elif byte == 34:
                quoted = False
        elif byte == 34:
            quoted = True
        elif byte in {91, 123}:
            depth += 1
            if depth > max_depth:
                raise ObservedGraphLimitError("depth-limit", "JSON nesting exceeds ceiling")
        elif byte in {93, 125}:
            depth -= 1
    try:
        return json.loads(
            data.decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_float=_reject_number,
            parse_constant=_reject_number,
        )
    except (UnicodeError, ValueError, RecursionError) as exc:
        if isinstance(exc, ObservedGraphInputError):
            raise
        raise ObservedGraphInputError("invalid-json", "input is not supported UTF-8 JSON") from exc


def bound_document(value: object, limits: ObservedGraphLimits) -> None:
    """Count the entire observation, including producer data, before freezing."""
    pending = [value]
    values = strings = 0
    while pending:
        item = pending.pop()
        values += 1
        if values > limits.max_json_values:
            raise ObservedGraphLimitError("value-limit", "observation value count exceeds ceiling")
        texts: list[str] = []
        if type(item) is dict:
            obj = cast("dict[str, object]", item)
            if any(type(key) is not str for key in obj):
                raise ObservedGraphInputError("invalid-json", "object keys must be strings")
            texts.extend(obj)
            pending.extend(obj.values())
        elif type(item) is list:
            pending.extend(cast("list[object]", item))
        elif type(item) is str:
            texts.append(item)
        elif type(item) not in {int, bool, type(None)}:
            raise ObservedGraphInputError("invalid-json", "unsupported primitive JSON type")
        for text in texts:
            try:
                size = len(text.encode("utf-8"))
            except UnicodeError as exc:
                raise ObservedGraphInputError("invalid-utf8", "invalid scalar text") from exc
            strings += size
            if size > limits.max_string_bytes or strings > limits.max_total_string_bytes:
                raise ObservedGraphLimitError("string-limit", "observation strings exceed ceiling")
    if type(value) is dict:
        document = cast("dict[str, object]", value)
        for key, maximum in (("nodes", limits.max_nodes), ("edges", limits.max_edges)):
            array = document.get(key)
            if type(array) is list and len(cast("list[object]", array)) > maximum:
                raise ObservedGraphLimitError(
                    "graph-count-limit", "node/edge count exceeds ceiling"
                )
        producer = document.get("producer")
        if type(producer) is dict:
            source = cast("dict[str, object]", producer).get("source")
            if type(source) is dict:
                files = cast("dict[str, object]", source).get("files")
                if (
                    type(files) is list
                    and len(cast("list[object]", files)) > limits.max_source_files
                ):
                    raise ObservedGraphLimitError(
                        "source-count-limit", "source inventory exceeds ceiling"
                    )


def validate_document(value: object, limits: ObservedGraphLimits) -> dict[str, object]:
    """Reuse the exact pinned raw schema, never a broadened alternate catalog."""
    bound_document(value, limits)
    try:
        validate_raw_export(value, require_completed=True)
    except RawExportFailedError as exc:
        raise ObservedGraphInputError("raw-incomplete", "raw export did not complete") from exc
    except RawExportError as exc:
        # Unknown kind text may be attacker-supplied. Keep the causal category,
        # but suppress that unbounded upstream exception from rendered traces.
        if "unsupported" in str(exc) or "unknown property" in str(exc):
            raise ObservedGraphUnsupportedError(
                "raw-unsupported", "unsupported pinned raw schema"
            ) from None
        raise ObservedGraphInputError(
            "raw-schema", "raw schema/reference/ownership validation failed"
        ) from None
    except (ValueError, OverflowError, RecursionError):
        raise ObservedGraphInputError(
            "raw-value", "raw value exceeds native parsing constraints"
        ) from None
    return cast("dict[str, object]", value)


@dataclass(frozen=True, slots=True)
class PropertyObservation:
    name: str
    native_type: str
    cardinality: str
    presence: str
    value: FrozenValue


@dataclass(frozen=True, slots=True)
class ObservedNode:
    node_id: str
    kind: str
    properties: tuple[PropertyObservation, ...]
    missing_properties: tuple[str, ...]

    def property(self, name: str) -> PropertyObservation:
        """Catalog-aware presence; unknown properties raise, not 'missing'."""
        for prop in self.properties:
            if prop.name == name:
                return prop
        raise KeyError(name)


@dataclass(frozen=True, slots=True)
class ObservedEdge:
    ordinal: int
    src: str
    dst: str
    kind: str
    properties: FrozenObject


@dataclass(frozen=True, slots=True)
class AstParent:
    node_id: str
    parent_id: str
    edge_ordinals: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class MethodOwnership:
    node_id: str
    method_id: str | None
    status: str


@dataclass(frozen=True, slots=True)
class MethodView:
    node_id: str
    outer_method_id: str | None
    formal_input_edges: tuple[int, ...]
    formal_output_edges: tuple[int, ...]
    method_return_edges: tuple[int, ...]
    modifier_edges: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class CallView:
    node_id: str
    target_edges: tuple[int, ...]
    receiver_edges: tuple[int, ...]
    actual_edges: tuple[int, ...]
    binding_status: str = "unsupported"


@dataclass(frozen=True, slots=True)
class FormalView:
    node_id: str
    method_id: str
    direction: str
    parameter_link_edges: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class ReturnView:
    node_id: str
    expression_edges: tuple[int, ...]
    exit_edges: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class NodeRelations:
    """Raw-directed roles; ordinals retain multiplicity and have no semantic order."""

    node_id: str
    ast_children: tuple[int, ...]
    declaration_references: tuple[int, ...]
    evaluation_types: tuple[int, ...]
    captures: tuple[int, ...]
    bindings: tuple[int, ...]
    inherits_from: tuple[int, ...]
    cfg: tuple[int, ...]
    cdg: tuple[int, ...]
    reaching_definitions: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class MethodNameGroup:
    full_name: str
    method_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SourceMethodCandidates:
    method_ids: tuple[str, ...]
    status: str = "unverified"


@dataclass(frozen=True, slots=True)
class StructuralViews:
    ast_parents: tuple[AstParent, ...]
    ownership: tuple[MethodOwnership, ...]
    methods: tuple[MethodView, ...]
    calls: tuple[CallView, ...]
    formals: tuple[FormalView, ...]
    returns: tuple[ReturnView, ...]
    relations: tuple[NodeRelations, ...]
    full_names: tuple[MethodNameGroup, ...]
    semantic_status: str = "unsupported"


def _nodes(document: dict[str, object]) -> tuple[ObservedNode, ...]:
    result: list[ObservedNode] = []
    for node in cast("list[dict[str, object]]", document["nodes"]):
        kind = cast("str", node["kind"])
        properties = cast("dict[str, object]", node["properties"])
        observations = tuple(
            PropertyObservation(
                name,
                native,
                quantity,
                "present"
                if name in properties
                else {
                    "one": "missing_required",
                    "optional": "absent_optional",
                    "many": "absent_many",
                }[quantity],
                freeze_value(properties[name]) if name in properties else None,
            )
            for name, (native, quantity) in sorted(NODE_PROPERTIES[kind].items())
        )
        result.append(
            ObservedNode(
                cast("str", node["id"]),
                kind,
                observations,
                tuple(cast("list[str]", node["missing_properties"])),
            )
        )
    return tuple(result)


def _views(nodes: tuple[ObservedNode, ...], edges: tuple[ObservedEdge, ...]) -> StructuralViews:
    by_id = {node.node_id: node for node in nodes}
    outgoing: dict[tuple[str, str], list[int]] = {}
    incoming_links: dict[str, list[int]] = {}
    parents: dict[str, str] = {}
    parent_edges: dict[str, list[int]] = {}
    for edge in edges:
        outgoing.setdefault((edge.src, edge.kind), []).append(edge.ordinal)
        if edge.kind == "AST":
            parents[edge.dst] = edge.src  # Uniqueness/cycles already strictly validated.
            parent_edges.setdefault(edge.dst, []).append(edge.ordinal)
        elif edge.kind == "PARAMETER_LINK":
            incoming_links.setdefault(edge.dst, []).append(edge.ordinal)

    def refs(node_id: str, kind: str) -> tuple[int, ...]:
        return tuple(outgoing.get((node_id, kind), ()))

    # Each node joins a trail at most once. One shared forest, not N ancestry lists.
    owners: dict[str, str | None] = {}
    for node in nodes:
        cursor = node.node_id
        trail: list[str] = []
        while cursor not in owners:
            if by_id[cursor].kind == "METHOD":
                owners[cursor] = cursor
                break
            trail.append(cursor)
            parent = parents.get(cursor)
            if parent is None:
                owners[cursor] = None
                break
            cursor = parent
        owner = owners[cursor]
        for descendant in trail:
            owners[descendant] = owner

    methods: list[MethodView] = []
    calls: list[CallView] = []
    formals: list[FormalView] = []
    returns: list[ReturnView] = []
    relations: list[NodeRelations] = []
    names: dict[str, list[str]] = {}
    for node in nodes:
        node_id = node.node_id
        ast = refs(node_id, "AST")
        if node.kind == "METHOD":
            children: dict[str, list[int]] = {}
            for ordinal in ast:
                children.setdefault(by_id[edges[ordinal].dst].kind, []).append(ordinal)
            methods.append(
                MethodView(
                    node_id,
                    owners.get(parents.get(node_id, "")),
                    tuple(children.get("METHOD_PARAMETER_IN", ())),
                    tuple(children.get("METHOD_PARAMETER_OUT", ())),
                    tuple(children.get("METHOD_RETURN", ())),
                    tuple(children.get("MODIFIER", ())),
                )
            )
            full_name = node.property("FULL_NAME")
            if full_name.presence == "present":
                names.setdefault(cast("str", full_name.value), []).append(node_id)
        elif node.kind == "CALL":
            calls.append(
                CallView(
                    node_id,
                    refs(node_id, "CALL"),
                    refs(node_id, "RECEIVER"),
                    refs(node_id, "ARGUMENT"),
                )
            )
        elif node.kind in {"METHOD_PARAMETER_IN", "METHOD_PARAMETER_OUT"}:
            formals.append(
                FormalView(
                    node_id,
                    parents[node_id],
                    node.kind,
                    refs(node_id, "PARAMETER_LINK") + tuple(incoming_links.get(node_id, ())),
                )
            )
        elif node.kind == "RETURN":
            returns.append(
                ReturnView(
                    node_id,
                    refs(node_id, "ARGUMENT"),
                    tuple(
                        ordinal
                        for ordinal in refs(node_id, "CFG")
                        if by_id[edges[ordinal].dst].kind == "METHOD_RETURN"
                    ),
                )
            )
        relations.append(
            NodeRelations(
                node_id,
                ast,
                refs(node_id, "REF"),
                refs(node_id, "EVAL_TYPE"),
                refs(node_id, "CAPTURE"),
                refs(node_id, "BINDS"),
                refs(node_id, "INHERITS_FROM"),
                refs(node_id, "CFG"),
                refs(node_id, "CDG"),
                refs(node_id, "REACHING_DEF"),
            )
        )
    return StructuralViews(
        tuple(
            AstParent(node.node_id, parents[node.node_id], tuple(parent_edges[node.node_id]))
            for node in nodes
            if node.node_id in parents
        ),
        tuple(
            MethodOwnership(
                node.node_id,
                owners[node.node_id],
                "observed" if owners[node.node_id] is not None else "no_method_ancestor",
            )
            for node in nodes
        ),
        tuple(methods),
        tuple(calls),
        tuple(formals),
        tuple(returns),
        tuple(relations),
        tuple(MethodNameGroup(name, tuple(ids)) for name, ids in sorted(names.items())),
    )


@dataclass(frozen=True, slots=True)
class TypedObservedGraph:
    """Constructor validates bytes; derived records cannot be caller-supplied.

    This prevents inconsistent direct construction and mutable input aliases.
    Trusted code must not use object.__setattr__ to bypass the frozen boundary.
    """

    original_raw_export_bytes: bytes
    limits: ObservedGraphLimits = field(default_factory=ObservedGraphLimits)
    model_version: str = field(default=MODEL_VERSION, init=False)
    role_profile: str = field(default=ROLE_PROFILE, init=False)
    stage: str = field(default=OBSERVED_STAGE, init=False)
    raw_export_sha256: str = field(init=False)
    producer: FrozenObject = field(init=False)
    capabilities: FrozenObject = field(init=False)
    nodes: tuple[ObservedNode, ...] = field(init=False)
    edges: tuple[ObservedEdge, ...] = field(init=False)
    views: StructuralViews = field(init=False)
    _document: FrozenObject = field(init=False, repr=False)

    def __post_init__(self) -> None:
        limits = checked_limits(self.limits)
        value = decode_json_bytes(
            self.original_raw_export_bytes,
            max_bytes=limits.max_raw_bytes,
            max_depth=limits.max_json_depth,
        )
        document = validate_document(value, limits)
        frozen = cast("FrozenObject", freeze_value(document))
        nodes = _nodes(document)
        edges = tuple(
            ObservedEdge(
                index,
                cast("str", edge["src"]),
                cast("str", edge["dst"]),
                cast("str", edge["kind"]),
                cast("FrozenObject", freeze_value(edge["properties"])),
            )
            for index, edge in enumerate(cast("list[dict[str, object]]", document["edges"]))
        )
        object.__setattr__(
            self,
            "raw_export_sha256",
            "sha256:" + hashlib.sha256(self.original_raw_export_bytes).hexdigest(),
        )
        object.__setattr__(self, "_document", frozen)
        object.__setattr__(self, "producer", frozen.get("producer"))
        object.__setattr__(self, "capabilities", frozen.get("capabilities"))
        object.__setattr__(self, "nodes", nodes)
        object.__setattr__(self, "edges", edges)
        object.__setattr__(self, "views", _views(nodes, edges))

    def node(self, node_id: str) -> ObservedNode:
        """Exact native-ID lookup, never a semantic tie-break."""
        for node in self.nodes:
            if node.node_id == node_id:
                return node
        raise KeyError(node_id)

    def owner(self, node_id: str) -> MethodOwnership:
        """Nearest observed METHOD, with no inferred global procedure."""
        for owner in self.views.ownership:
            if owner.node_id == node_id:
                return owner
        raise KeyError(node_id)

    def methods_by_full_name(self, full_name: str) -> tuple[str, ...]:
        """Return ALL exact-text candidates; cardinality is not resolution."""
        for group in self.views.full_names:
            if group.full_name == full_name:
                return group.method_ids
        return ()

    def methods_at_source(self, filename: str, line: int) -> SourceMethodCandidates:
        """Exact source hints only; no normalization, adapter removal or binding."""
        if type(filename) is not str or type(line) is not int:
            raise ObservedGraphInputError(
                "lookup-type", "source hints require exact string/integer"
            )
        return SourceMethodCandidates(
            tuple(
                node.node_id
                for node in self.nodes
                if node.kind == "METHOD"
                and node.property("FILENAME").presence == "present"
                and node.property("FILENAME").value == filename
                and node.property("LINE_NUMBER").presence == "present"
                and node.property("LINE_NUMBER").value == line
            )
        )


def parse_observed_graph(
    raw_export_bytes: bytes, *, limits: ObservedGraphLimits | None = None
) -> TypedObservedGraph:
    """Capture completed exact observations; never execute or canonicalize them."""
    return TypedObservedGraph(raw_export_bytes, checked_limits(limits))


def validate_observed_graph(graph: TypedObservedGraph) -> None:
    """Rebuild all fields from bounded original bytes; no conflicting cached proof."""
    if type(graph) is not TypedObservedGraph:
        raise ObservedGraphInputError("graph-type", "expected exact TypedObservedGraph")
    expected = TypedObservedGraph(graph.original_raw_export_bytes, checked_limits(graph.limits))
    if graph != expected:
        raise ObservedGraphInputError(
            "inconsistent-graph", "graph fields disagree with captured bytes"
        )


def to_raw_document(graph: TypedObservedGraph) -> dict[str, object]:
    """Detached normalized raw value; original whitespace is retained separately."""
    validate_observed_graph(graph)
    return cast("dict[str, object]", thaw_value(graph._document))
