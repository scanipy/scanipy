"""Strict observed-only archive, actual legacy refusal and bounded tamper controls."""

from __future__ import annotations

import base64
import gzip
import hashlib
import io
import json
import random
import struct
import tarfile
from pathlib import Path

import pytest

from analysis.cpg_ingest import typed_observed_wire
from analysis.cpg_ingest.mapper import map_export
from analysis.cpg_ingest.typed_observed import (
    ObservedGraphArtifactError,
    ObservedGraphInputError,
    ObservedGraphLimitError,
    ObservedGraphLimits,
    ObservedGraphUnsupportedError,
    parse_observed_graph,
    to_raw_document,
)
from analysis.cpg_ingest.typed_observed_wire import (
    deserialize_observed_graph,
    serialize_observed_graph,
)
from analysis.ordering import CPG
from services.substrate.cpg_tarball import (
    CPGDeserializationError,
    deserialize_cpg_tarball,
    serialize_cpg_tarball,
)

pytestmark = pytest.mark.unit
FIXTURES = Path(__file__).parents[1] / "fixtures" / "joern_raw_v2" / "exports"


def _pack(payload, *, name="cpg.json", member_type=tarfile.REGTYPE, extra=False):
    encoded = payload if type(payload) is bytes else json.dumps(payload).encode()
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.USTAR_FORMAT) as archive:
        member = tarfile.TarInfo(name)
        member.mode = 0o600
        member.size = len(encoded)
        member.type = member_type
        archive.addfile(member, io.BytesIO(encoded))
        if extra:
            archive.addfile(member, io.BytesIO(encoded))
    return gzip.compress(buffer.getvalue(), mtime=0)


def _payload(artifact):
    with tarfile.open(fileobj=io.BytesIO(artifact), mode="r:gz") as archive:
        return json.load(archive.extractfile("cpg.json"))


@pytest.fixture
def graph():
    return parse_observed_graph((FIXTURES / "java.json").read_bytes())


@pytest.fixture
def payload(graph):
    return _payload(serialize_observed_graph(graph))


@pytest.mark.parametrize("language", ["java", "python"])
def test_repeat_writer_and_lossless_round_trip(language):
    raw = (FIXTURES / f"{language}.json").read_bytes()
    graph = parse_observed_graph(raw)
    artifact = serialize_observed_graph(graph)
    restored = deserialize_observed_graph(
        artifact,
        expected_artifact_sha256="sha256:" + hashlib.sha256(artifact).hexdigest(),
        expected_raw_export_sha256=graph.raw_export_sha256,
    )
    assert restored == graph
    assert serialize_observed_graph(restored) == artifact == serialize_observed_graph(graph)
    assert artifact[3:8] == b"\x00" * 5
    payload = _payload(artifact)
    assert payload["nodes"] is payload["edges"] is None
    assert base64.b64decode(payload["original_raw_export"]["data"]) == raw


def test_original_spelling_not_confused_with_normalized(graph):
    original = json.dumps(to_raw_document(graph), indent=3, sort_keys=False).encode() + b"\n\n"
    restored = deserialize_observed_graph(serialize_observed_graph(parse_observed_graph(original)))
    assert restored.original_raw_export_bytes == original
    assert to_raw_document(restored) == to_raw_document(graph)
    assert restored.raw_export_sha256 != graph.raw_export_sha256


@pytest.mark.parametrize(
    "field,value",
    [
        ("format", "other"),
        ("format_version", True),
        ("format_version", "2"),
        ("format_version", 1),
        ("model_version", "scanipy-cpg/3"),
        ("role_profile", "unknown"),
        ("stage", "resolved"),
    ],
)
def test_unsupported_version_never_falls_back(payload, field, value):
    payload[field] = value
    with pytest.raises(ObservedGraphUnsupportedError):
        deserialize_observed_graph(_pack(payload))


@pytest.mark.parametrize(
    "field,value", [("nodes", []), ("edges", []), ("nodes", {}), ("stage", None)]
)
def test_fences_and_stage_are_exact(payload, field, value):
    payload[field] = value
    with pytest.raises(ObservedGraphInputError):
        deserialize_observed_graph(_pack(payload))


@pytest.mark.parametrize("field", ["nodes", "edges", "graph", "original_raw_export"])
def test_missing_fields_fail(payload, field):
    del payload[field]
    with pytest.raises(ObservedGraphInputError):
        deserialize_observed_graph(_pack(payload))


@pytest.mark.parametrize(
    "field,value",
    [
        ("encoding", "base64url"),
        ("byte_length", True),
        ("byte_length", -1),
        ("byte_length", 1),
        ("sha256", "0" * 64),
        ("sha256", "A" * 64),
        ("data", "!!!!"),
        ("data", "Zg==\n"),
        ("data", "Zh=="),
        ("data", []),
    ],
)
def test_original_bytes_binding_tampering(payload, field, value):
    payload["original_raw_export"][field] = value
    with pytest.raises(ObservedGraphArtifactError):
        deserialize_observed_graph(_pack(payload))


def test_normalized_original_disagreement_and_duplicate_keys(payload):
    payload["graph"]["nodes"].reverse()
    with pytest.raises(ObservedGraphInputError, match="observation-mismatch"):
        deserialize_observed_graph(_pack(payload))
    encoded = json.dumps(payload).encode()
    with pytest.raises(ObservedGraphInputError, match="duplicate-key"):
        deserialize_observed_graph(_pack(b'{"stage":"observed-only",' + encoded[1:]))


@pytest.mark.parametrize("option", ["expected_artifact_sha256", "expected_raw_export_sha256"])
@pytest.mark.parametrize("value", ["sha256:" + "0" * 64, "0" * 64, True, "sha256:" + "A" * 64])
def test_trusted_digest_format_and_actual_comparison(graph, option, value):
    with pytest.raises(ObservedGraphArtifactError):
        deserialize_observed_graph(serialize_observed_graph(graph), **{option: value})


@pytest.mark.parametrize(
    "name,member_type,extra",
    [
        ("../cpg.json", tarfile.REGTYPE, False),
        ("/cpg.json", tarfile.REGTYPE, False),
        ("other", tarfile.REGTYPE, False),
        ("cpg.json", tarfile.SYMTYPE, False),
        ("cpg.json", tarfile.LNKTYPE, False),
        ("cpg.json", tarfile.DIRTYPE, False),
        ("cpg.json", tarfile.GNUTYPE_SPARSE, False),
        ("cpg.json", tarfile.XHDTYPE, False),
        ("cpg.json", tarfile.XGLTYPE, False),
        ("cpg.json", tarfile.REGTYPE, True),
    ],
)
def test_archive_members_reject_before_graph(payload, name, member_type, extra):
    with pytest.raises(ObservedGraphArtifactError):
        deserialize_observed_graph(_pack(payload, name=name, member_type=member_type, extra=extra))


@pytest.mark.parametrize(
    "mutation", ["truncated", "corrupt", "concat", "trailing", "padding", "nonzero", "header"]
)
def test_gzip_and_tar_integrity(graph, mutation):
    artifact = serialize_observed_graph(graph)
    if mutation == "truncated":
        artifact = artifact[:-5]
    elif mutation == "corrupt":
        artifact = artifact[:-8] + b"invalid!"
    elif mutation == "concat":
        artifact += gzip.compress(b"second stream", mtime=0)
    elif mutation == "trailing":
        artifact += b"trailing"
    else:
        tar = gzip.decompress(artifact)
        if mutation == "padding":
            tar += b"\0" * 10240
        elif mutation == "nonzero":
            tar = tar[:-1] + b"x"
        else:
            tar = b"x" + tar[1:]
        artifact = gzip.compress(tar, mtime=0)
    with pytest.raises(ObservedGraphArtifactError):
        deserialize_observed_graph(artifact)


@pytest.mark.parametrize(
    "limit", ["max_artifact_bytes", "max_tar_bytes", "max_json_bytes", "max_raw_bytes", "max_nodes"]
)
def test_reader_limits(graph, limit):
    with pytest.raises(ObservedGraphLimitError):
        deserialize_observed_graph(
            serialize_observed_graph(graph), limits=ObservedGraphLimits(**{limit: 1})
        )


@pytest.mark.parametrize("limit", ["max_artifact_bytes", "max_tar_bytes", "max_json_bytes"])
def test_writer_output_limits(graph, limit):
    limited = parse_observed_graph(
        graph.original_raw_export_bytes, limits=ObservedGraphLimits(**{limit: 1})
    )
    with pytest.raises(ObservedGraphLimitError):
        serialize_observed_graph(limited)


def test_actual_legacy_refusal_and_missing_fence_trap(graph):
    artifact = serialize_observed_graph(graph)
    payload = _payload(artifact)
    with pytest.raises((TypeError, ValueError)):
        map_export(payload)
    with pytest.raises(CPGDeserializationError):
        deserialize_cpg_tarball(artifact)
    del payload["nodes"]
    del payload["edges"]
    assert len(map_export(payload).nodes) == 0  # Actual historical trap, NOT a new success.
    with pytest.raises(ObservedGraphInputError):
        deserialize_observed_graph(_pack(payload))


def test_real_v1_reader_unchanged_and_new_reader_refuses():
    cpg = CPG()
    cpg.add_node("METHOD", resolved_fqn="legacy")
    original = serialize_cpg_tarball(cpg)
    restored = deserialize_cpg_tarball(original)
    assert restored.nodes == cpg.nodes
    assert serialize_cpg_tarball(restored) == original
    with pytest.raises(ObservedGraphInputError):
        deserialize_observed_graph(original)


def test_source_algorithm_and_three_byte_identities_remain_distinct(graph):
    source = graph.producer.get("source")
    assert source.get("tree_namespace") == "scanipy-source-tree/1"
    files = source.get("files").values
    manifest = hashlib.sha256(b"scanipy-source-tree/1\0")
    content_framed = hashlib.sha256()
    for entry in files:
        path = entry.get("path").encode()
        content = (FIXTURES.parent / "java" / entry.get("path")).read_bytes()
        assert len(content) == entry.get("size")
        manifest.update(struct.pack(">Q", len(path)) + path + struct.pack(">Q", len(content)))
        manifest.update(hashlib.sha256(content).digest())
        content_framed.update(
            struct.pack(">Q", len(path)) + path + struct.pack(">Q", len(content)) + content
        )
    assert manifest.hexdigest() == source.get("tree_sha256")
    assert content_framed.hexdigest() != source.get("tree_sha256")
    artifact = serialize_observed_graph(graph)
    assert (
        len(
            {
                graph.raw_export_sha256[7:],
                graph.producer.get("input_cpg").get("sha256"),
                hashlib.sha256(artifact).hexdigest(),
            }
        )
        == 3
    )
    assert deserialize_observed_graph(artifact).producer == graph.producer


@pytest.mark.parametrize("value", [b"", b"not gzip", bytearray(b"x"), "x", None])
def test_invalid_archive_types_and_empty_bytes(value):
    with pytest.raises(ObservedGraphArtifactError):
        deserialize_observed_graph(value)


def test_gzip_bomb_and_compressed_bound_fail_before_json(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("JSON parsing reached before compression/decompression bound")

    monkeypatch.setattr(typed_observed_wire, "decode_json_bytes", forbidden)
    compressed = gzip.compress(b"\0" * 100000, mtime=0)
    with pytest.raises(ObservedGraphLimitError, match="tar-byte-limit"):
        deserialize_observed_graph(compressed, limits=ObservedGraphLimits(max_tar_bytes=10240))
    with pytest.raises(ObservedGraphLimitError, match="artifact-byte-limit"):
        deserialize_observed_graph(compressed, limits=ObservedGraphLimits(max_artifact_bytes=1))


def test_tar_member_bound_before_json_and_original_bound_before_base64(payload, monkeypatch):
    artifact = _pack(payload)

    def forbidden(*args, **kwargs):
        pytest.fail("expansion reached before byte bound")

    with monkeypatch.context() as patch:
        patch.setattr(typed_observed_wire, "decode_json_bytes", forbidden)
        with pytest.raises(ObservedGraphLimitError, match="json-byte-limit"):
            deserialize_observed_graph(artifact, limits=ObservedGraphLimits(max_json_bytes=1))
    monkeypatch.setattr(typed_observed_wire.base64, "b64decode", forbidden)
    with pytest.raises(ObservedGraphLimitError, match="raw-byte-limit"):
        deserialize_observed_graph(artifact, limits=ObservedGraphLimits(max_raw_bytes=1))


def test_impossible_writer_tar_budget_precedes_base64_expansion(graph, monkeypatch):
    limited = parse_observed_graph(
        graph.original_raw_export_bytes, limits=ObservedGraphLimits(max_tar_bytes=1)
    )

    def forbidden(*args, **kwargs):
        pytest.fail("base64 allocation before impossible tar ceiling")

    monkeypatch.setattr(typed_observed_wire.base64, "b64encode", forbidden)
    with pytest.raises(ObservedGraphLimitError, match="tar-output-limit"):
        serialize_observed_graph(limited)


def test_exact_archive_json_tar_raw_boundaries(graph):
    artifact = serialize_observed_graph(graph)
    tar = gzip.decompress(artifact)
    with tarfile.open(fileobj=io.BytesIO(tar), mode="r:") as archive:
        payload_size = archive.getmember("cpg.json").size
    limits = ObservedGraphLimits(
        max_artifact_bytes=len(artifact),
        max_tar_bytes=len(tar),
        max_json_bytes=payload_size,
        max_raw_bytes=len(graph.original_raw_export_bytes),
    )
    captured = parse_observed_graph(graph.original_raw_export_bytes, limits=limits)
    assert serialize_observed_graph(captured) == artifact
    assert deserialize_observed_graph(artifact, limits=limits) == captured


def test_same_json_value_comparison_is_type_sensitive():
    # Direct comparator falsifier: Python dict/list equality alone is insufficient.
    assert not typed_observed_wire._same_value({"x": [True]}, {"x": [1]})
    assert typed_observed_wire._same_value({"x": [False, 0, "", None]}, {"x": [False, 0, "", None]})


def test_valid_but_noncanonical_base64_pad_bits_rejected(payload):
    # Same decoded byte f: Zg== is canonical while Zh== uses nonzero ignored pad bits.
    payload["original_raw_export"] = {
        "encoding": "base64",
        "byte_length": 1,
        "sha256": hashlib.sha256(b"f").hexdigest(),
        "data": "Zh==",
    }
    with pytest.raises(ObservedGraphArtifactError, match="base64-canonical"):
        deserialize_observed_graph(_pack(payload))


def test_normalized_is_independently_schema_validated(payload):
    payload["graph"]["nodes"][0]["properties"]["UNKNOWN"] = "invalid"
    with pytest.raises(ObservedGraphUnsupportedError):
        deserialize_observed_graph(_pack(payload))


@pytest.mark.parametrize(
    "member_field,value",
    [("mode", 0o644), ("uid", 1), ("gid", 1), ("mtime", 1), ("uname", "other"), ("gname", "other")],
)
def test_nonprofile_ustar_metadata_rejected(payload, member_field, value):
    encoded = json.dumps(payload).encode()
    member = tarfile.TarInfo("cpg.json")
    member.mode = 0o600
    member.size = len(encoded)
    setattr(member, member_field, value)
    archive = member.tobuf(format=tarfile.USTAR_FORMAT) + encoded
    archive += b"\0" * (typed_observed_wire._tar_size(len(encoded)) - len(archive))
    with pytest.raises(ObservedGraphArtifactError, match="tar-header"):
        deserialize_observed_graph(gzip.compress(archive, mtime=0))


def test_nested_duplicate_keys_rejected(payload):
    encoded = (
        json.dumps(payload)
        .encode()
        .replace(b'"encoding": "base64"', b'"encoding":"base64","encoding":"base64"')
    )
    with pytest.raises(ObservedGraphInputError, match="duplicate-key"):
        deserialize_observed_graph(_pack(encoded))


def test_incompressible_stream_bounds_every_compressed_input_chunk(monkeypatch):
    # Deterministic transport stress bytes, never source execution or entropy credentials.
    raw = random.Random(391393).randbytes(4 * 1024 * 1024)
    compressed = gzip.compress(raw, compresslevel=9, mtime=0)
    assert len(compressed) > len(raw)
    original_factory = typed_observed_wire.zlib.decompressobj
    input_lengths = []

    class InstrumentedDecompressor:
        def __init__(self, *args, **kwargs):
            self.wrapped = original_factory(*args, **kwargs)

        def decompress(self, data, max_length):
            input_lengths.append(len(data))
            return self.wrapped.decompress(data, max_length)

        def __getattr__(self, name):
            return getattr(self.wrapped, name)

    monkeypatch.setattr(typed_observed_wire.zlib, "decompressobj", InstrumentedDecompressor)
    assert typed_observed_wire._decompress(compressed, ObservedGraphLimits()) == raw
    assert len(input_lengths) >= 64
    assert max(input_lengths) <= typed_observed_wire._CHUNK
    # At most a small bounded tail can be replayed; never the whole remaining stream.
    assert sum(input_lengths) < 2 * len(compressed)


def test_stream_end_before_next_input_chunk_rejects_trailing_data(graph):
    artifact = serialize_observed_graph(graph)
    # Exercise unread subsequent chunks, not only zlib.unused_data in the same chunk.
    with pytest.raises(ObservedGraphArtifactError, match="gzip-trailing"):
        deserialize_observed_graph(artifact + b"x" * (2 * typed_observed_wire._CHUNK))
