"""Frozen pre-extension R09/R12 bytes, not a source/finalization acceptance test.

The corpus was captured once from accepted c7eb7b3. Tests consume fixed payloads,
exports and public signatures; they never regenerate expectations or sign.
"""

from __future__ import annotations

import copy
import dataclasses
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, cast
from uuid import UUID

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import load_der_public_key

from analysis.artifact_identity import GRAPH_V2, SLICE_V2
from analysis.sarif.canonical_emit import WorkerFinding, normalize, validate_sarif_210
from services.scan import provenance
from services.scan.provenance import (
    KMSAsymmetricSigner,
    ProvenanceRecord,
    SignedProvenanceRecord,
)
from tests.fnd01_fakes import make_finding

pytestmark = pytest.mark.unit

_ROOT = Path(__file__).resolve().parents[2]
_CORPUS = _ROOT / "tests/fixtures/provenance_compatibility/corpus.json"
_CORPUS_SHA256 = "5e77533346f526cd78d06525fdc8fc805cf3f984f43747f2fac14e4ffe628932"
_FULL_LOG = _CORPUS.with_name("full_log_record.json")
_FULL_LOG_SHA256 = "f6884ce5b1f41c63694a8cbbba0d7010ab29404cd4b35547dc7f81cc1a9aebf4"
_BASELINE = "c7eb7b3e4cad8f66d2098213998b7931474295a5"
_NAMES = (
    "v1_existing_checksum",
    "v1_nullable_oracle",
    "v1_repartition",
    "v2_strong_strong",
    "v2_strong_weak",
    "v2_weak_strong",
    "v2_weak_weak",
    "v2_cpgless_oracle",
    "v2_non_ascii",
)
_UUID_FIELDS = (
    "id",
    "parent_record_id",
    "scan_id",
    "finding_id",
    "org_id",
    "codebase_id",
    "snapshot_id",
    "repartition_oracle_id",
)
_BYTES_FIELDS = ("cpg_order_hash", "slice_fingerprint", "sarif_hash")


@pytest.fixture(scope="module")
def corpus() -> dict[str, Any]:
    raw = _CORPUS.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == _CORPUS_SHA256
    value: dict[str, Any] = json.loads(raw)
    assert value["baseline_commit"] == _BASELINE
    assert tuple(case["name"] for case in value["records"]) == _NAMES
    return value


@pytest.fixture(scope="module")
def full_log_record() -> dict[str, Any]:
    raw = _FULL_LOG.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == _FULL_LOG_SHA256
    value: dict[str, Any] = json.loads(raw)
    assert value["baseline_commit"] == _BASELINE
    assert [row["name"] for row in value["records"]] == ["v2_full_log"]
    return value


def _case(corpus: dict[str, Any], name: str) -> dict[str, Any]:
    return cast(dict[str, Any], next(row for row in corpus["records"] if row["name"] == name))


def _record(case: dict[str, Any]) -> ProvenanceRecord:
    # Fixture-only type restoration, NOT a production export decoder. No
    # serializer logic, digest inference or current-schema field enumeration.
    fields = copy.deepcopy(case["input"])
    for name in _UUID_FIELDS:
        if fields[name] is not None:
            fields[name] = UUID(fields[name])
    for name in _BYTES_FIELDS:
        if fields[name] is not None:
            fields[name] = bytes.fromhex(fields[name])
    return ProvenanceRecord(**fields)


def _signed(case: dict[str, Any]) -> SignedProvenanceRecord:
    return SignedProvenanceRecord(
        record=_record(case),
        canonical_bytes=case["canonical_utf8"].encode("utf-8"),
        kms_key_arn=case["kms_key_arn"],
        kms_key_version=case["kms_key_version"],
        signature=bytes.fromhex(case["signature_hex"]),
        signature_alg=case["signature_alg"],
    )


class _PublicKeys:
    """Recorded synthetic public material only; deliberately has no sign method."""

    def __init__(self, corpus: dict[str, Any]) -> None:
        self.key_id: str = corpus["public_key"]["key_id"]
        self.version: str = corpus["public_key"]["key_version"]
        self.der = bytes.fromhex(corpus["public_key"]["der_hex"])

    def get_public_key(self, *, KeyId: str, KeyVersion: str) -> dict[str, object]:  # noqa: N803
        if KeyId != self.key_id or KeyVersion != self.version:
            return {}
        return {"PublicKey": self.der}


class _ReadStore:
    def __init__(self, corpus: dict[str, Any]) -> None:
        self.rows = {_signed(case).record.id: _signed(case) for case in corpus["records"]}

    def append(self, _signed_record: SignedProvenanceRecord) -> None:
        raise AssertionError("compatibility tests must not append or sign")

    def get(self, record_id: UUID) -> SignedProvenanceRecord | None:
        return self.rows.get(record_id)

    def children(self, parent_record_id: UUID) -> list[SignedProvenanceRecord]:
        return [
            row for row in self.rows.values() if row.record.parent_record_id == parent_record_id
        ]


def _verify(signed: SignedProvenanceRecord, corpus: dict[str, Any]) -> str:
    keys = _PublicKeys(corpus)
    assert not hasattr(keys, "sign")
    return provenance.verify_chain(
        signed,
        signer=cast(KMSAsymmetricSigner, keys),
        store=_ReadStore(corpus),
    )


@pytest.mark.parametrize("name", _NAMES)
def test_fixed_canonical_payload_and_public_signature(corpus: dict[str, Any], name: str) -> None:
    case = _case(corpus, name)
    signed = _signed(case)
    expected = case["canonical_utf8"].encode("utf-8")
    assert hashlib.sha256(expected).hexdigest() == case["canonical_sha256"]
    assert provenance.canonical_record_bytes(signed.record) == expected
    assert not expected.endswith(b"\n")
    assert _verify(signed, corpus) == "VERIFIED"
    # Every frozen input field, not just the four main provenance fields, is
    # restored exactly. Metadata stays an independent, mutable caller copy.
    for field, expected_value in case["input"].items():
        actual = getattr(signed.record, field)
        if isinstance(actual, UUID):
            actual = str(actual)
        elif isinstance(actual, bytes):
            actual = actual.hex()
        assert actual == expected_value, field


@pytest.mark.parametrize("name", _NAMES)
def test_legacy_export_values_and_insertion_order_stay_frozen(
    corpus: dict[str, Any], name: str
) -> None:
    case = _case(corpus, name)
    expected = json.loads(case["export_utf8"])
    actual = provenance.export_auditor_record(_record(case).id, store=_ReadStore(corpus))
    assert actual == expected
    assert list(actual) == list(expected)
    assert json.dumps(actual, ensure_ascii=False, separators=(",", ":")) == case["export_utf8"]
    # These old views do not reconstruct the full signed record. Do not label
    # the public-only fixture input below as a newly implemented export codec.
    assert not {"org_id", "codebase_id", "scan_id", "snapshot_id", "finding_id"} & actual.keys()


def test_existing_v1_checksum_and_nullable_independent_scope(corpus: dict[str, Any]) -> None:
    checksum = _case(corpus, "v1_existing_checksum")
    assert (
        checksum["canonical_sha256"]
        == "80286e1340ddd13544872cf96b75c4245915b54f9d44901492bc00636e30bc2a"
    )
    record = _record(_case(corpus, "v1_nullable_oracle"))
    ids = [
        record.id,
        record.scan_id,
        record.finding_id,
        record.org_id,
        record.codebase_id,
        record.snapshot_id,
    ]
    assert len(set(ids)) == 6
    assert record.cpg_order_hash is record.slice_fingerprint is None
    assert record.fingerprint_class is None
    assert record.witness_blob_uri is record.rule_id is record.spec_id is None
    assert record.precondition_status == "degraded"
    payload = json.loads(provenance.canonical_record_bytes(record))
    assert "artifact_identity" not in payload and "record_schema_version" not in payload


def test_retained_repartition_is_actual_v1_child_without_rewriting_parent(
    corpus: dict[str, Any],
) -> None:
    parent = _signed(_case(corpus, "v1_existing_checksum"))
    child = _signed(_case(corpus, "v1_repartition"))
    assert child.record.record_type == "repartition"
    assert child.record.parent_record_id == parent.record.id
    assert child.record.record_schema_version == 1
    assert child.record.artifact_identity is None
    assert child.record.cpg_order_hash is None
    assert child.record.slice_fingerprint == parent.record.slice_fingerprint
    assert child.record.origin == "oracle-passthrough"
    assert _verify(child, corpus) == "VERIFIED"
    assert provenance.canonical_record_bytes(parent.record) == parent.canonical_bytes


@pytest.mark.parametrize(
    "graph,sliced", [("strong", "strong"), ("strong", "weak"), ("weak", "strong"), ("weak", "weak")]
)
def test_v2_descriptors_remain_independent(corpus: dict[str, Any], graph: str, sliced: str) -> None:
    record = _record(_case(corpus, f"v2_{graph}_{sliced}"))
    metadata = record.artifact_identity
    assert metadata is not None
    assert record.fingerprint_class is None
    graph_row = cast(dict[str, Any], metadata["cpg_order"])
    slice_row = cast(dict[str, Any], metadata["slice"])
    assert graph_row["fingerprint_class"] == graph
    assert slice_row["fingerprint_class"] == sliced
    assert graph_row["namespace"] == GRAPH_V2
    assert slice_row["namespace"] == (
        SLICE_V2 if sliced == "strong" else "scanipy-witness-edge-sequence/1"
    )
    assert (
        graph_row["annotation"]
        == slice_row["annotation"]
        == "canonical iff fingerprint_class = strong"
    )


def test_cpgless_and_non_ascii_examples_preserve_actual_old_spelling(
    corpus: dict[str, Any],
) -> None:
    oracle = _record(_case(corpus, "v2_cpgless_oracle"))
    assert oracle.origin == "oracle-passthrough"
    assert oracle.cpg_order_hash is oracle.slice_fingerprint is None
    assert oracle.precondition_status is None
    assert oracle.artifact_identity is not None
    for role in ("cpg_order", "slice"):
        descriptor = cast(dict[str, Any], oracle.artifact_identity[role])
        assert descriptor["status"] == "not-applicable"
        assert (
            descriptor["digest"]
            is descriptor["fingerprint_class"]
            is descriptor["namespace"]
            is None
        )
    case = _case(corpus, "v2_non_ascii")
    assert _record(case).rule_id == "règle/注入"
    raw = case["canonical_utf8"].encode("utf-8")
    assert raw.isascii() and b"\\u00e8" in raw and b"\\u6ce8" in raw
    assert case["signature_alg"] == "RSASSA_PSS_SHA_384"
    assert "règle/注入" in case["export_utf8"]


_CHANGES: tuple[tuple[str, Any], ...] = (
    ("id", UUID(int=100_001)),
    ("parent_record_id", UUID(int=100_002)),
    ("scan_id", UUID(int=100_003)),
    ("finding_id", UUID(int=100_004)),
    ("org_id", UUID(int=100_005)),
    ("codebase_id", UUID(int=100_006)),
    ("snapshot_id", UUID(int=100_007)),
    ("commit_sha", "b" * 40),
    ("scm_provider", "gitlab"),
    ("snapshot_digest", "sha256:" + "d" * 64),
    ("S_version", "1.2.4"),
    ("env_digest", "sha256:" + "e" * 64),
    ("rule_id", "different-rule"),
    ("spec_id", "different-spec"),
    ("detector_id", "different-detector"),
    ("detector_engine", "ide"),
    ("origin", "oracle-passthrough"),
    ("determinism_partition", "oracle-passthrough"),
    ("witness_blob_uri", "file:///different-witness"),
    ("precondition_status", "degraded"),
    ("claim_label", "STAGED"),
    ("record_type", "witness-update"),
)


@pytest.mark.parametrize("field,value", _CHANGES, ids=[row[0] for row in _CHANGES])
def test_signed_field_mutation_fails(corpus: dict[str, Any], field: str, value: Any) -> None:
    signed = _signed(_case(corpus, "v2_strong_strong"))
    assert getattr(signed.record, field) != value
    changed = dataclasses.replace(signed.record, **{field: value})
    assert _verify(dataclasses.replace(signed, record=changed), corpus) == "TAMPERED"


@pytest.mark.parametrize("field", _BYTES_FIELDS)
def test_digest_mutation_fails_even_with_matching_descriptor(
    corpus: dict[str, Any], field: str
) -> None:
    signed = _signed(_case(corpus, "v2_strong_strong"))
    digest = provenance.Sha256(b"z" * 32)
    if field == "cpg_order_hash":
        changed = dataclasses.replace(signed.record, cpg_order_hash=digest)
    elif field == "slice_fingerprint":
        changed = dataclasses.replace(signed.record, slice_fingerprint=digest)
    else:
        assert field == "sarif_hash"
        changed = dataclasses.replace(signed.record, sarif_hash=digest)
    # Keep both graph/slice representations internally consistent, so these
    # controls reach signature comparison rather than merely shape rejection.
    if field != "sarif_hash":
        assert changed.artifact_identity is not None
        role = "cpg_order" if field == "cpg_order_hash" else "slice"
        cast(dict[str, Any], changed.artifact_identity[role])["digest"] = digest.hex()
    assert provenance.canonical_record_bytes(changed) != signed.canonical_bytes
    assert _verify(dataclasses.replace(signed, record=changed), corpus) == "TAMPERED"


@pytest.mark.parametrize("role", ["cpg_order", "slice"])
@pytest.mark.parametrize(
    "field,value",
    [("fingerprint_class", "weak"), ("namespace", "unknown/9"), ("annotation", "wrong annotation")],
)
def test_postconstruction_descriptor_mutation_fails(
    corpus: dict[str, Any], role: str, field: str, value: str
) -> None:
    signed = _signed(_case(corpus, "v2_strong_strong"))
    assert signed.record.artifact_identity is not None
    cast(dict[str, Any], signed.record.artifact_identity[role])[field] = value
    assert _verify(signed, corpus) == "TAMPERED"


@pytest.mark.parametrize("version", [None, True, False, 0, -1, 3, "1", "2", 2.0])
def test_unknown_record_versions_remain_rejected(corpus: dict[str, Any], version: Any) -> None:
    signed = _signed(_case(corpus, "v2_strong_strong"))
    changed = dataclasses.replace(signed.record, record_schema_version=version)
    with pytest.raises(ValueError, match="unsupported provenance record schema version"):
        provenance.canonical_record_bytes(changed)
    assert _verify(dataclasses.replace(signed, record=changed), corpus) == "TAMPERED"


def test_v1_unsigned_metadata_v2_shared_class_and_flat_mismatch_stay_rejected(
    corpus: dict[str, Any],
) -> None:
    legacy = _record(_case(corpus, "v1_existing_checksum"))
    current = _record(_case(corpus, "v2_strong_strong"))
    with pytest.raises(ValueError, match="unsigned artifact metadata"):
        provenance.canonical_record_bytes(
            dataclasses.replace(legacy, artifact_identity=current.artifact_identity)
        )
    with pytest.raises(ValueError, match="ambiguous shared class"):
        provenance.canonical_record_bytes(dataclasses.replace(current, fingerprint_class="strong"))
    with pytest.raises(ValueError, match="does not match"):
        provenance.canonical_record_bytes(
            dataclasses.replace(current, cpg_order_hash=provenance.Sha256(b"z" * 32))
        )


def test_public_material_verification_does_not_sign_and_rederives_payload(
    corpus: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("signing/key generation is forbidden in compatibility tests")

    monkeypatch.setattr(provenance, "sign_provenance", forbidden)
    monkeypatch.setattr(rsa, "generate_private_key", forbidden)
    public = _PublicKeys(corpus)
    assert hashlib.sha256(public.der).hexdigest() == corpus["public_key"]["sha256"]
    key = load_der_public_key(public.der)
    assert isinstance(key, rsa.RSAPublicKey) and key.key_size == 2048
    signed = _signed(_case(corpus, "v2_strong_strong"))
    assert _verify(signed, corpus) == "VERIFIED"
    # This is the actual legacy guarantee: cached bytes are ignored, not a new
    # assertion that the old verifier authenticates a supplied byte cache.
    assert (
        _verify(dataclasses.replace(signed, canonical_bytes=b"untrusted cache"), corpus)
        == "VERIFIED"
    )
    assert (
        _verify(dataclasses.replace(signed, kms_key_version="unknown"), corpus) == "KEY_NOT_FOUND"
    )
    changed_signature = bytes([signed.signature[0] ^ 1]) + signed.signature[1:]
    assert _verify(dataclasses.replace(signed, signature=changed_signature), corpus) == "TAMPERED"


def test_fixed_normalizer_full_log_and_partition_hashes(corpus: dict[str, Any]) -> None:
    frozen = corpus["sarif"]
    options = dict(frozen["input"])
    for field in ("scan_id", "snapshot_id", "codebase_id"):
        options[field] = UUID(options[field])
    # The existing checksum fixture is frozen/read-only; the legacy protocol
    # declares writable fields although normalize only reads this object.
    log = normalize(frozenset({cast(WorkerFinding, make_finding())}), **options)
    assert log.canonical_bytes == frozen["canonical_utf8"].encode("utf-8")
    assert (
        log.sarif_hash
        == frozen["sha256"]
        == "d6fce0db36b454b60fbae752c176ec1ccb7bdfb53db644b188f88edd870c9ff5"
    )
    assert log.canonical_bytes.endswith(b"\n") and not log.canonical_bytes.endswith(b"\n\n")
    assert validate_sarif_210(log.canonical_bytes) == []
    assert hashlib.sha256(log.canonical_bytes[:-1]).hexdigest() != log.sarif_hash
    for run, captured in zip(log.runs, frozen["partitions"], strict=True):
        assert run.partition == captured["partition"]
        assert run.canonical_bytes == captured["canonical_utf8"].encode("utf-8")
        assert run.sarif_hash == captured["sha256"] != log.sarif_hash
        assert run.result_count == captured["result_count"]
        assert not run.canonical_bytes.endswith(b"\n")


def test_tenth_example_matches_shared_log_context_without_claiming_result_join(
    corpus: dict[str, Any], full_log_record: dict[str, Any]
) -> None:
    case = _case(full_log_record, "v2_full_log")
    signed = _signed(case)
    assert provenance.canonical_record_bytes(signed.record) == signed.canonical_bytes
    assert hashlib.sha256(signed.canonical_bytes).hexdigest() == case["canonical_sha256"]
    assert _verify(signed, full_log_record) == "VERIFIED"
    frozen = corpus["sarif"]
    for field, expected in frozen["input"].items():
        if field == "llm_triage_flag":
            continue  # Not a field of the old signed record.
        assert str(getattr(signed.record, field)) == str(expected)
    assert signed.record.sarif_hash is not None
    assert signed.record.sarif_hash.hex() == frozen["sha256"]
    assert full_log_record["sarif_reference"] == {
        "fixture": "corpus.json",
        "sha256": frozen["sha256"],
    }
    actual = provenance.export_auditor_record(signed.record.id, store=_ReadStore(full_log_record))
    assert json.dumps(actual, ensure_ascii=False, separators=(",", ":")) == case["export_utf8"]


@pytest.mark.parametrize(
    "variant,expected",
    [
        ("full", "VERIFIED"),
        ("missing", "ARTIFACT_MISSING"),
        ("modified", "TAMPERED"),
        ("without-lf", "TAMPERED"),
        ("extra-lf", "TAMPERED"),
        ("core-partition", "TAMPERED"),
        ("oracle-partition", "TAMPERED"),
    ],
)
def test_real_public_verifier_checks_exact_full_log_artifact(
    corpus: dict[str, Any],
    full_log_record: dict[str, Any],
    variant: str,
    expected: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("artifact replay must not sign or generate private material")

    monkeypatch.setattr(provenance, "sign_provenance", forbidden)
    monkeypatch.setattr(rsa, "generate_private_key", forbidden)
    signed = _signed(_case(full_log_record, "v2_full_log"))
    frozen = corpus["sarif"]
    raw = frozen["canonical_utf8"].encode("utf-8")
    options: dict[str, bytes | None] = {
        "full": raw,
        "missing": None,
        "modified": raw.replace(b"2.1.0", b"2.0.0", 1),
        "without-lf": raw[:-1],
        "extra-lf": raw + b"\n",
        "core-partition": frozen["partitions"][0]["canonical_utf8"].encode("utf-8"),
        "oracle-partition": frozen["partitions"][1]["canonical_utf8"].encode("utf-8"),
    }
    calls: list[str] = []

    class Artifacts:
        def fetch(self, uri: str) -> bytes | None:
            calls.append(uri)
            return options[variant]

    verdict = provenance.verify_chain(
        signed,
        signer=cast(KMSAsymmetricSigner, _PublicKeys(full_log_record)),
        artifacts=Artifacts(),
    )
    assert verdict == expected
    assert calls == [
        f"orgs/{signed.record.org_id}/codebases/{signed.record.codebase_id}/"
        f"sarif/{signed.record.scan_id}.sarif.json"
    ]


_FRESH_VERIFY = r"""
import copy
import dataclasses
import importlib.abc
import json
import sys
from pathlib import Path
from uuid import UUID

blocked = ("analysis.ifds", "detectors", "services.scan.worker",
           "services.snapshot.worker", "services.scan.software_kms_signer", "tests")
class RefuseExecutionImports(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if any(fullname == item or fullname.startswith(item + ".") for item in blocked):
            raise AssertionError("unexpected execution import: " + fullname)
        return None
sys.meta_path.insert(0, RefuseExecutionImports())
sys.path.insert(0, sys.argv[1])
from services.scan import provenance as p
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
def forbidden(*args, **kwargs):
    raise AssertionError("no signing/private material in public fixture replay")
p.sign_provenance = forbidden
rsa.generate_private_key = forbidden
serialization.load_der_private_key = forbidden
serialization.load_pem_private_key = forbidden
document = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
class PublicOnly:
    def get_public_key(self, *, KeyId, KeyVersion):
        key = document["public_key"]
        return {"PublicKey": bytes.fromhex(key["der_hex"])} if (
            KeyId == key["key_id"] and KeyVersion == key["key_version"]
        ) else {}
public = PublicOnly()
assert not hasattr(public, "sign")
records = {}
for case in document["records"]:
    fields = copy.deepcopy(case["input"])
    for field in ("id", "parent_record_id", "scan_id", "finding_id", "org_id",
                  "codebase_id", "snapshot_id", "repartition_oracle_id"):
        if fields[field] is not None:
            fields[field] = UUID(fields[field])
    for field in ("cpg_order_hash", "slice_fingerprint", "sarif_hash"):
        if fields[field] is not None:
            fields[field] = bytes.fromhex(fields[field])
    record = p.ProvenanceRecord(**fields)
    expected = case["canonical_utf8"].encode("utf-8")
    assert p.canonical_record_bytes(record) == expected
    records[record.id] = p.SignedProvenanceRecord(
        record, expected, case["kms_key_arn"], case["kms_key_version"],
        bytes.fromhex(case["signature_hex"]), case["signature_alg"])
class ReadOnly:
    def get(self, record_id):
        return records.get(record_id)
store = ReadOnly()
for signed in records.values():
    assert p.verify_chain(signed, signer=public, store=store) == "VERIFIED"
    changed = dataclasses.replace(signed.record, S_version="99.0.0")
    changed_signed = dataclasses.replace(signed, record=changed)
    assert p.verify_chain(changed_signed, signer=public, store=store) == "TAMPERED"
assert not any(
    any(name == item or name.startswith(item + ".") for item in blocked)
    for name in sys.modules
)
print(json.dumps({
    "verified": len(records), "mutations_rejected": len(records),
    "sign_available": hasattr(public, "sign"),
}))
"""


@pytest.mark.parametrize("fixture_path,count", [(_CORPUS, 9), (_FULL_LOG, 1)])
def test_fresh_process_verifies_public_examples_without_signer_or_analysis(
    corpus: dict[str, Any],
    full_log_record: dict[str, Any],
    tmp_path: Path,
    fixture_path: Path,
    count: int,
) -> None:
    result = subprocess.run(
        [sys.executable, "-I", "-B", "-c", _FRESH_VERIFY, str(_ROOT), str(fixture_path)],
        cwd=tmp_path,
        env={"LANG": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1"},
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "verified": count,
        "mutations_rejected": count,
        "sign_available": False,
    }
