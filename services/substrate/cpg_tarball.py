"""Shared CPG-tarball wire format — the CMP-SNAP-05 <-> CMP-ORCH-03 handoff.

Resolves CLAR-ORCH-10 / CLAR-SNAP-08 (WBS.md §17): the snapshot worker
(producer, ``services/snapshot/worker.py``) and the detector worker (consumer,
``services/scan/detector_worker.py``) were built on parallel tracks and each
independently defaulted the ``cpg_tarball`` artifact body to a different
internal layout. This module is the single canonical implementation both
sides import, so there is exactly one format to keep in sync, not two.

Format: a gzip-compressed tar (stdlib ``tarfile``/``gzip`` only — no extra
dependency) containing exactly one member, ``cpg.json``:
``{"format_version": "1", "nodes": [...], "edges": [...]}``. Each node object
mirrors ``analysis.ordering.CPGNode`` field-for-field; ``node_id`` is the
array POSITION (dense ``0..N-1``, the producer's own deterministic
node-emission order per INV-5 — this module never re-sorts). Each edge object
mirrors ``analysis.ordering.CPGEdge`` field-for-field.

The S3 key suffix (``SNAPSHOT_ARTIFACT_SUFFIXES['cpg_tarball']`` = ``cpg.tar.zst``)
still names zstd for historical reasons (no ``zstandard`` dependency is
pinned); the bytes here are always gzip. Renaming the suffix is deferred as a
cosmetic follow-up, not a functional gap — nothing parses the suffix string
itself, only the byte contents matter.

Byte-determinism: ``tarfile``'s ``"w:gz"`` mode delegates to
``gzip.GzipFile``'s default ``mtime=time.time()`` for the gzip WRAPPER header,
even when the TAR member's own ``info.mtime`` is pinned — so the gzip layer is
opened explicitly with ``mtime=0`` here, making the whole archive
byte-identical across repeated calls on identical input (load-bearing for the
CMP-CP-05 Attestor's byte-identical-SARIF guarantee).
"""

from __future__ import annotations

import gzip
import io
import json
import tarfile
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from analysis.ordering import CPG

CPG_TARBALL_MEMBER_NAME = "cpg.json"
CPG_TARBALL_FORMAT_VERSION = "1"


class CPGDeserializationError(Exception):
    """The fetched CPG tarball does not satisfy this module's format contract
    (fail-closed; mirrors DOC-CMP-ORCH-03 §3.5's "message fails validation ->
    reject" posture for the CPG artifact instead of the SQS message)."""


def serialize_cpg_tarball(cpg: CPG) -> bytes:
    """Serialize ``cpg`` to the canonical ``cpg_tarball`` artifact body.

    See the module docstring for the exact format. Deterministic: two calls
    on an equal ``cpg`` produce byte-identical output.
    """
    payload = {
        "format_version": CPG_TARBALL_FORMAT_VERSION,
        "nodes": [
            {
                "node_id": int(n.node_id),
                "kind": n.kind,
                "operator_or_literal": n.operator_or_literal,
                "resolved_fqn": n.resolved_fqn,
                "enclosing_decl_fqn": n.enclosing_decl_fqn,
                "structural_path": n.structural_path,
            }
            for n in cpg.nodes
        ],
        "edges": [{"src": int(e.src), "dst": int(e.dst), "kind": e.kind} for e in cpg.edges],
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb", mtime=0) as gz:
        with tarfile.open(fileobj=gz, mode="w|") as tar:
            info = tarfile.TarInfo(name=CPG_TARBALL_MEMBER_NAME)
            info.size = len(raw)
            info.mtime = 0
            tar.addfile(info, io.BytesIO(raw))
    return buf.getvalue()


def deserialize_cpg_tarball(data: bytes) -> CPG:
    """Deserialize the canonical ``cpg_tarball`` format into a real
    :class:`analysis.ordering.CPG` (fail-closed on any shape violation).

    Trusts the producer's node ORDER (position in the ``nodes`` array) as the
    canonical insertion order — this consumer never re-sorts nodes (INV-5's
    node-emission-order requirement is the PRODUCER's obligation). It only
    verifies the contract: each node's declared ``node_id`` must equal its
    array position (dense ``0..N-1``), and edges may only reference in-range
    node ids.
    """
    from analysis.ordering import CPG, NodeId  # local import: keeps CPG optional at module import

    try:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
            member = tar.getmember(CPG_TARBALL_MEMBER_NAME)
            extracted = tar.extractfile(member)
            if extracted is None:  # pragma: no cover — extractfile(regular file) never None
                raise CPGDeserializationError(
                    f"tarball member {CPG_TARBALL_MEMBER_NAME!r} is not a regular file"
                )
            raw = extracted.read()
    except (tarfile.TarError, KeyError) as exc:
        raise CPGDeserializationError(f"malformed CPG tarball: {exc}") from exc

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CPGDeserializationError(f"CPG tarball member is not valid JSON: {exc}") from exc

    if not isinstance(payload, dict) or "nodes" not in payload or "edges" not in payload:
        raise CPGDeserializationError(
            "CPG tarball JSON must be an object with 'nodes' and 'edges' keys"
        )
    nodes, edges = payload["nodes"], payload["edges"]
    if not isinstance(nodes, list) or not isinstance(edges, list):
        raise CPGDeserializationError("CPG tarball 'nodes'/'edges' must both be arrays")

    cpg = CPG()
    for position, raw_node in enumerate(nodes):
        if not isinstance(raw_node, dict):
            raise CPGDeserializationError(f"node at position {position} is not an object")
        node_id = raw_node.get("node_id")
        if node_id != position:
            raise CPGDeserializationError(
                "CPG tarball nodes must be dense and sorted by node_id 0..N-1 "
                f"(the producer's own deterministic emission order, INV-5); "
                f"position {position} carries node_id={node_id!r}"
            )
        assigned = cpg.add_node(
            str(raw_node.get("kind", "")),
            operator_or_literal=str(raw_node.get("operator_or_literal", "")),
            resolved_fqn=str(raw_node.get("resolved_fqn", "")),
            enclosing_decl_fqn=str(raw_node.get("enclosing_decl_fqn", "")),
            structural_path=str(raw_node.get("structural_path", "")),
        )
        if int(assigned) != position:  # pragma: no cover — CPG.add_node is insertion-ordered
            raise CPGDeserializationError("CPG.add_node did not preserve insertion order")

    node_count = len(nodes)
    for raw_edge in edges:
        if not isinstance(raw_edge, dict):
            raise CPGDeserializationError(f"edge entry is not an object: {raw_edge!r}")
        src, dst, kind = raw_edge.get("src"), raw_edge.get("dst"), raw_edge.get("kind")
        if not isinstance(src, int) or not isinstance(dst, int) or not isinstance(kind, str):
            raise CPGDeserializationError(f"malformed edge entry: {raw_edge!r}")
        if not (0 <= src < node_count) or not (0 <= dst < node_count):
            raise CPGDeserializationError(f"edge references an out-of-range node id: {raw_edge!r}")
        cpg.add_edge(NodeId(src), NodeId(dst), kind)
    return cpg


__all__ = [
    "CPG_TARBALL_FORMAT_VERSION",
    "CPG_TARBALL_MEMBER_NAME",
    "CPGDeserializationError",
    "deserialize_cpg_tarball",
    "serialize_cpg_tarball",
]
