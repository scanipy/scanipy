"""Strict opt-in observed-only artifact/2 transport; no default routing changes.

Contract: docs/bhmea/TYPED-OBSERVED-CPG-CONTRACT.md. Integrity/replay are not
authentication, source coverage, semantic canonicality or resolved bindings.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
import tarfile
import zlib
from typing import Final, cast

from analysis.cpg_ingest.typed_observed import (
    MODEL_VERSION,
    OBSERVED_STAGE,
    ROLE_PROFILE,
    ObservedGraphArtifactError,
    ObservedGraphInputError,
    ObservedGraphLimitError,
    ObservedGraphLimits,
    ObservedGraphUnsupportedError,
    TypedObservedGraph,
    checked_limits,
    decode_json_bytes,
    parse_observed_graph,
    to_raw_document,
    validate_document,
)

ARTIFACT_FORMAT: Final = "scanipy-cpg-artifact"
ARTIFACT_VERSION: Final = 2
_SHA: Final = re.compile(r"[0-9a-f]{64}\Z")
_CHUNK: Final = 65536
_RECORD: Final = 10240


def _header(size: int) -> bytes:
    member = tarfile.TarInfo("cpg.json")
    member.mode = 0o600
    member.size = size
    # TarInfo defaults uid/gid/mtime to 0, owner names/linkname to empty.
    return member.tobuf(format=tarfile.USTAR_FORMAT, encoding="utf-8", errors="strict")


def _tar_size(size: int) -> int:
    unpadded = 512 + ((size + 511) // 512) * 512 + 1024
    return ((unpadded + _RECORD - 1) // _RECORD) * _RECORD


def _expected_digest(expected: str | None, actual: bytes) -> None:
    if expected is None:
        return
    if (
        type(expected) is not str
        or not expected.startswith("sha256:")
        or not _SHA.fullmatch(expected[7:])
    ):
        raise ObservedGraphArtifactError(
            "digest-format", "expected digest must be lowercase sha256-prefixed hex"
        )
    if expected[7:] != hashlib.sha256(actual).hexdigest():
        raise ObservedGraphArtifactError(
            "digest-mismatch", "actual bytes do not match expected digest"
        )


def _json_payload(value: dict[str, object], maximum: int) -> bytes:
    encoder = json.JSONEncoder(
        ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )
    # Count before retaining chunks. The input's scalar sizes were already bounded.
    size = 0
    for chunk in encoder.iterencode(value):
        size += len(chunk.encode("utf-8"))
        if size > maximum:
            raise ObservedGraphLimitError("json-output-limit", "artifact JSON exceeds ceiling")
    return b"".join(chunk.encode("utf-8") for chunk in encoder.iterencode(value))


def _compress(parts: tuple[bytes, ...], maximum: int) -> bytes:
    compressor = zlib.compressobj(level=9, wbits=31)  # Single gzip, MTIME=0, no filename/comment.
    result: list[bytes] = []
    size = 0
    for part in parts:
        for offset in range(0, len(part), _CHUNK):
            chunk = compressor.compress(part[offset : offset + _CHUNK])
            size += len(chunk)
            if size > maximum:
                raise ObservedGraphLimitError(
                    "artifact-output-limit", "compressed artifact exceeds ceiling"
                )
            result.append(chunk)
    last = compressor.flush()
    if size + len(last) > maximum:
        raise ObservedGraphLimitError(
            "artifact-output-limit", "compressed artifact exceeds ceiling"
        )
    result.append(last)
    return b"".join(result)


def serialize_observed_graph(graph: TypedObservedGraph) -> bytes:
    """Byte-repeatable archive in this runtime; NOT a canonical semantic graph."""
    document = to_raw_document(graph)  # Revalidates constructor data and all derived views.
    limits = graph.limits
    # A USTAR record always occupies at least 10,240 bytes. Restrict the JSON
    # count pass to what can fit the configured tar layout BEFORE retaining it.
    max_member = (limits.max_tar_bytes // _RECORD) * _RECORD - 1536
    if max_member < 0:
        raise ObservedGraphLimitError("tar-output-limit", "no USTAR record fits the ceiling")
    json_ceiling = min(limits.max_json_bytes, max_member)
    raw = graph.original_raw_export_bytes
    encoded_size = 4 * ((len(raw) + 2) // 3)
    if encoded_size > json_ceiling:
        raise ObservedGraphLimitError(
            "json-output-limit", "original-byte encoding exceeds JSON ceiling"
        )
    payload = _json_payload(
        {
            "format": ARTIFACT_FORMAT,
            "format_version": ARTIFACT_VERSION,
            "model_version": MODEL_VERSION,
            "role_profile": ROLE_PROFILE,
            "stage": OBSERVED_STAGE,
            "nodes": None,
            "edges": None,  # Tested current legacy-reader refusal fences.
            "original_raw_export": {
                "encoding": "base64",
                "byte_length": len(raw),
                "sha256": graph.raw_export_sha256[7:],
                "data": base64.b64encode(raw).decode("ascii"),
            },
            "graph": document,
        },
        json_ceiling,
    )
    total = _tar_size(len(payload))
    if total > limits.max_tar_bytes:
        raise ObservedGraphLimitError("tar-output-limit", "uncompressed artifact exceeds ceiling")
    return _compress(
        (_header(len(payload)), payload, b"\0" * (total - 512 - len(payload))),
        limits.max_artifact_bytes,
    )


def _decompress(data: bytes, limits: ObservedGraphLimits) -> bytes:
    if type(data) is not bytes:
        raise ObservedGraphArtifactError("artifact-type", "artifact must be exact immutable bytes")
    if len(data) > limits.max_artifact_bytes:
        raise ObservedGraphLimitError("artifact-byte-limit", "compressed artifact exceeds ceiling")
    decompressor = zlib.decompressobj(wbits=31)
    parts: list[bytes] = []
    size = 0
    pending = b""
    offset = 0
    try:
        while True:
            if not pending and offset < len(data):
                pending = data[offset : offset + _CHUNK]
                offset += len(pending)
            part = decompressor.decompress(pending, min(_CHUNK, limits.max_tar_bytes - size + 1))
            size += len(part)
            if size > limits.max_tar_bytes:
                raise ObservedGraphLimitError(
                    "tar-byte-limit", "decompressed artifact exceeds ceiling"
                )
            parts.append(part)
            pending = decompressor.unconsumed_tail
            if decompressor.eof:
                if decompressor.unused_data or pending or offset < len(data):
                    raise ObservedGraphArtifactError(
                        "gzip-trailing", "multiple streams or trailing bytes are forbidden"
                    )
                break
            if not part and not pending and offset == len(data):
                raise ObservedGraphArtifactError("gzip-incomplete", "gzip stream did not complete")
    except zlib.error as exc:
        raise ObservedGraphArtifactError("gzip-invalid", "invalid gzip stream") from exc
    return b"".join(parts)


def _member(data: bytes, limits: ObservedGraphLimits) -> bytes:
    if len(data) < 512:
        raise ObservedGraphArtifactError("tar-header", "missing tar header")
    try:
        member = tarfile.TarInfo.frombuf(data[:512], encoding="utf-8", errors="strict")
    except (tarfile.TarError, UnicodeError, ValueError) as exc:
        raise ObservedGraphArtifactError("tar-header", "invalid tar header") from exc
    if member.size < 0 or member.size > limits.max_json_bytes:
        raise ObservedGraphLimitError("json-byte-limit", "tar member size exceeds JSON ceiling")
    # Exact USTAR metadata/header encoding makes links, extensions, prefixes,
    # sparse/GNU records, alternate paths and hidden owner fields fail closed.
    if data[:512] != _header(member.size):
        raise ObservedGraphArtifactError(
            "tar-header", "expected the exact regular USTAR cpg.json header"
        )
    if len(data) != _tar_size(member.size):
        raise ObservedGraphArtifactError(
            "tar-layout", "unexpected members, missing EOF or excess padding"
        )
    end = 512 + member.size
    if any(memoryview(data)[end:]):
        raise ObservedGraphArtifactError(
            "tar-padding", "only zero padding and EOF may follow the member"
        )
    return data[512:end]


def _shape(value: object, keys: set[str]) -> dict[str, object]:
    if type(value) is not dict or set(cast("dict[str, object]", value)) != keys:
        raise ObservedGraphArtifactError(
            "artifact-shape", "artifact object has missing or unknown fields"
        )
    return cast("dict[str, object]", value)


def _original(value: object, limits: ObservedGraphLimits) -> bytes:
    original = _shape(value, {"encoding", "byte_length", "sha256", "data"})
    size, data, digest = original["byte_length"], original["data"], original["sha256"]
    if (
        original["encoding"] != "base64"
        or type(size) is not int
        or size < 0
        or type(data) is not str
        or type(digest) is not str
        or not _SHA.fullmatch(digest)
    ):
        raise ObservedGraphArtifactError(
            "original-shape", "invalid original-byte encoding metadata"
        )
    if size > limits.max_raw_bytes or len(data) > 4 * ((limits.max_raw_bytes + 2) // 3):
        raise ObservedGraphLimitError("raw-byte-limit", "original raw bytes exceed ceiling")
    if len(data) != 4 * ((size + 2) // 3):
        raise ObservedGraphArtifactError(
            "base64-length", "base64 length does not match declared raw length"
        )
    try:
        raw = base64.b64decode(data, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ObservedGraphArtifactError("base64-invalid", "invalid standard base64") from exc
    if len(raw) != size or base64.b64encode(raw).decode("ascii") != data:
        raise ObservedGraphArtifactError(
            "base64-canonical", "noncanonical base64 or incorrect raw length"
        )
    if hashlib.sha256(raw).hexdigest() != digest:
        raise ObservedGraphArtifactError("raw-digest", "original raw digest mismatch")
    return raw


def _same_value(left: object, right: object) -> bool:
    # Explicit type equality prevents Python's True == 1 equivalence.
    pending = [(left, right)]
    while pending:
        first, second = pending.pop()
        if type(first) is not type(second):
            return False
        if type(first) is dict:
            a, b = cast("dict[str, object]", first), cast("dict[str, object]", second)
            if a.keys() != b.keys():
                return False
            pending.extend((value, b[key]) for key, value in a.items())
        elif type(first) is list:
            x, y = cast("list[object]", first), cast("list[object]", second)
            if len(x) != len(y):
                return False
            pending.extend(zip(x, y, strict=True))
        elif first != second:
            return False
    return True


def deserialize_observed_graph(
    artifact_bytes: bytes,
    *,
    limits: ObservedGraphLimits | None = None,
    expected_artifact_sha256: str | None = None,
    expected_raw_export_sha256: str | None = None,
) -> TypedObservedGraph:
    """Verify exact framing and byte bindings; never route failures to legacy readers."""
    checked = checked_limits(limits)
    if type(artifact_bytes) is not bytes:
        raise ObservedGraphArtifactError("artifact-type", "artifact must be exact immutable bytes")
    if len(artifact_bytes) > checked.max_artifact_bytes:
        raise ObservedGraphLimitError("artifact-byte-limit", "compressed artifact exceeds ceiling")
    _expected_digest(expected_artifact_sha256, artifact_bytes)
    payload = _shape(
        decode_json_bytes(
            _member(_decompress(artifact_bytes, checked), checked),
            max_bytes=checked.max_json_bytes,
            max_depth=checked.max_json_depth + 1,  # One transport object outside the raw document.
        ),
        {
            "format",
            "format_version",
            "model_version",
            "role_profile",
            "stage",
            "nodes",
            "edges",
            "original_raw_export",
            "graph",
        },
    )
    if (
        payload["format"] != ARTIFACT_FORMAT
        or type(payload["format_version"]) is not int
        or payload["format_version"] != ARTIFACT_VERSION
        or payload["model_version"] != MODEL_VERSION
        or payload["role_profile"] != ROLE_PROFILE
        or payload["stage"] != OBSERVED_STAGE
    ):
        raise ObservedGraphUnsupportedError(
            "artifact-version", "unsupported artifact model/profile/stage"
        )
    if payload["nodes"] is not None or payload["edges"] is not None:
        raise ObservedGraphArtifactError(
            "legacy-fence", "both legacy compatibility fences must be null"
        )
    raw = _original(payload["original_raw_export"], checked)
    _expected_digest(expected_raw_export_sha256, raw)
    graph = parse_observed_graph(raw, limits=checked)
    normalized = validate_document(payload["graph"], checked)
    if not _same_value(to_raw_document(graph), normalized):
        raise ObservedGraphInputError(
            "observation-mismatch", "original and normalized observations disagree"
        )
    return graph
