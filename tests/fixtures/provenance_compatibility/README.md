# Frozen legacy provenance compatibility examples

These are synthetic codec/crypto fixtures captured from accepted commit
`c7eb7b3e4cad8f66d2098213998b7931474295a5` on 2026-09-26 with CPython
3.11.16. They are not real findings, source captures, installed operator keys,
accepted operation models, native runs or completed R12/G1 evidence.
The ten signed records exercise the unchanged v1/v2 implementation; no new
signed schema or production export decoder is supplied here.

## Frozen contents

- `corpus.json`: nine signed record inputs, exact canonical payload strings,
  signatures, legacy export projections, public DER key and one complete actual
  normalizer log plus its two partition payloads. SHA-256:
  `5e77533346f526cd78d06525fdc8fc805cf3f984f43747f2fac14e4ffe628932`.
- `full_log_record.json`: separate tenth v2 record whose raw `sarif_hash`
  binds that exact complete log, including its LF, plus a second public-only
  key/signature. SHA-256:
  `f6884ce5b1f41c63694a8cbbba0d7010ab29404cd4b35547dc7f81cc1a9aebf4`.
  Adding this example did not regenerate or alter the original nine records.

Each `canonical_utf8` string, encoded as UTF-8, is the exact recorded signature
input (no final LF). JSON escaping in the fixture container is not another
canonicalization rule. The old signed JSON uses ASCII escapes; the captured
full SARIF log uses literal UTF-8 and one LF. Each `export_utf8` preserves the
actual legacy projection's insertion order and values. That old projection
omits scope fields and is not a self-contained signed-record reconstruction.

The original checksum case preserves payload SHA-256
`80286e1340ddd13544872cf96b75c4245915b54f9d44901492bc00636e30bc2a`.
The other examples cover nullable oracle fields, an actual v1 repartition child,
all four independent v2 graph/slice class pairs, CPG-less absence and non-ASCII
values with SHA-384 signing. All UUIDs and graph/slice digests are controlled
fixture inputs, not evidence of real identity generation or artifact availability.
The complete normalizer log preserves SHA-256
`d6fce0db36b454b60fbae752c176ec1ccb7bdfb53db644b188f88edd870c9ff5`.

The tenth record reuses the normalizer's input scan/snapshot/codebase IDs, commit,
S version, environment and precondition values; tests compare those inputs
explicitly. Its org/finding IDs and rule/graph/slice values remain synthetic
record-builder fields, not a proven join to the SARIF result. The real legacy
verifier checks the signature, org/codebase/scan-derived artifact lookup URI and
raw full-log hash. It does **not** independently validate every SARIF
field/scope correspondence, recompute a source-tree/CPG/snapshot digest, or
authorize finalization. Missing/modified/partition/LF tests preserve that
precise artifact-binding boundary.

## Capture and replay

Both recipes below were executed once, separately, in the accepted checkout
with the declared local Python environment and checkout `PYTHONPATH`.
Application/occurrence/accepted-ledger DB settings and AWS credential variables
were unset. No source/native analysis, database, external signer or network
operation was involved. The actual `SoftwareKMSSigner` generated an ephemeral
2048-bit RSA key in process memory for each capture; only its public DER and
PSS signatures were retained. No private key bytes were printed or written.

The JSON stdout from each trusted capture was parsed for validity, then added
through `apply_patch`. Ordinary tests do not execute these inert fenced recipes,
sign, regenerate expected payloads or update fixtures. A later intentional
extension must preserve these artifacts. Re-running the recipes would create
different keys/PSS signatures; the discarded private keys cannot recreate those
signatures. Existing signatures can be verified using the retained public data.

Capture-source checksums at the accepted commit:

| Source | SHA-256 |
| --- | --- |
| `services/scan/provenance/__init__.py` | `5e6910e77e6277befaf325d901bc1454c23afa9c740d5e2195de0b0da466530b` |
| `services/scan/software_kms_signer.py` | `796204036c634a2835192668d4a9a666256b130da9326ed2069b187c9932a39a` |
| `analysis/artifact_identity.py` | `e796cedfae86cd1619d166043b54b82c623434e631c1f937a15888ad1e0c7a43` |
| `analysis/sarif/canonical_emit.py` | `a2dc1c214624ccb154cc479f33439f4353af9d7657421871b76804dba8fb2348` |
| `tests/fnd01_fakes.py` | `5d4c60ca1796f45a1e81524d3e206011cd7f931f7444dfe2e3f6434fba8390d2` |
| `tests/fnd03_fakes.py` | `f7c98e589e8a54f0e68fb54cdd4713bfff606351780ba67eb58edf619da1d496` |

The first exact recipe text below has SHA-256
`e48820c03ef3379452cfa98cd92172cfb549f83690a839331e1499870a7b8ad6`
(including its final LF):

```python
"""One-time trusted fixture capture; outputs public data only, never a key file."""

import dataclasses
import hashlib
import json
from unittest.mock import patch
from uuid import UUID

from analysis.artifact_identity import GRAPH_V2, SLICE_V2, ArtifactIdentity
from analysis.sarif.canonical_emit import normalize
from services.scan.provenance import append_repartition_event, export_auditor_record, sign_provenance
from services.scan.software_kms_signer import SoftwareKMSSigner
from tests.fnd01_fakes import ENV_DIGEST, S_VERSION, make_finding
from tests.fnd03_fakes import InMemoryProvenanceStore, make_chain_record

KEY_ID = "fixture-public-key/provenance-compatibility"
KEY_VERSION = "capture-2026-09-26"
signer = SoftwareKMSSigner(version=KEY_VERSION, env={})
store = InMemoryProvenanceStore()
captured = []


def scoped(index):
    names = ("id", "scan_id", "finding_id", "org_id", "codebase_id", "snapshot_id")
    return dataclasses.replace(
        make_chain_record(),
        **{name: UUID(int=index * 1000 + position) for position, name in enumerate(names, 1)},
    )


def keep(name, record, *, algorithm="RSASSA_PSS_SHA_256"):
    signed = sign_provenance(record, signer=signer, kms_key_arn=KEY_ID,
                             signature_alg=algorithm, store=store)
    captured.append((name, signed))
    return signed


legacy = make_chain_record()
legacy = dataclasses.replace(legacy, **{
    field.name: UUID(int=42) for field in dataclasses.fields(legacy)
    if isinstance(getattr(legacy, field.name), UUID)
})
base = keep("v1_existing_checksum", legacy)
keep("v1_nullable_oracle", dataclasses.replace(
    scoped(2), origin="oracle-passthrough", determinism_partition="oracle-passthrough",
    detector_engine="semgrep", cpg_order_hash=None, slice_fingerprint=None,
    fingerprint_class=None, witness_blob_uri=None, rule_id=None, spec_id=None,
    precondition_status="degraded", claim_label="EMPIRICAL",
))
with patch("services.scan.provenance.uuid.uuid4", return_value=UUID(int=3001)):
    child = append_repartition_event(
        parent_record_id=base.record.id, repartition_oracle_id=UUID(int=3002),
        repartition_reason="controlled compatibility disagreement",
        store=store, signer=signer,
    )
captured.append(("v1_repartition", child))


def independent(index, graph_class="strong", slice_class="strong"):
    record = dataclasses.replace(scoped(index), record_schema_version=2, fingerprint_class=None)
    graph = ArtifactIdentity("completed", record.cpg_order_hash.hex(), graph_class, GRAPH_V2)
    sliced = ArtifactIdentity("completed", record.slice_fingerprint.hex(), slice_class,
                             SLICE_V2 if slice_class == "strong" else "scanipy-witness-edge-sequence/1")
    return dataclasses.replace(record, artifact_identity={
        "schema_version": 2, "cpg_order": graph.to_dict(), "slice": sliced.to_dict(),
    })


for index, pair in enumerate((("strong", "strong"), ("strong", "weak"),
                              ("weak", "strong"), ("weak", "weak")), 4):
    keep("v2_" + "_".join(pair), independent(index, *pair))
absent = ArtifactIdentity("not-applicable").to_dict()
keep("v2_cpgless_oracle", dataclasses.replace(
    scoped(8), origin="oracle-passthrough", determinism_partition="oracle-passthrough",
    detector_engine="semgrep", cpg_order_hash=None, slice_fingerprint=None,
    fingerprint_class=None, precondition_status=None, witness_blob_uri=None,
    claim_label="EMPIRICAL", record_schema_version=2,
    artifact_identity={"schema_version": 2, "cpg_order": absent, "slice": dict(absent)},
))
keep("v2_non_ascii", dataclasses.replace(
    independent(9), rule_id="règle/注入", spec_id="Spécification/安全",
    detector_id="détecteur-注入", witness_blob_uri="file:///evidence/café/证据.json",
), algorithm="RSASSA_PSS_SHA_384")


def value(item):
    if isinstance(item, UUID):
        return str(item)
    if isinstance(item, bytes):
        return item.hex()
    return item


records = []
for name, signed in captured:
    records.append({
        "name": name,
        "input": {field.name: value(getattr(signed.record, field.name))
                  for field in dataclasses.fields(signed.record)},
        "canonical_utf8": signed.canonical_bytes.decode("utf-8"),
        "canonical_sha256": hashlib.sha256(signed.canonical_bytes).hexdigest(),
        "signature_hex": signed.signature.hex(), "signature_alg": signed.signature_alg,
        "kms_key_arn": signed.kms_key_arn, "kms_key_version": signed.kms_key_version,
        "export_utf8": json.dumps(export_auditor_record(signed.record.id, store=store),
                                   ensure_ascii=False, separators=(",", ":")),
    })
assert records[0]["canonical_sha256"] == "80286e1340ddd13544872cf96b75c4245915b54f9d44901492bc00636e30bc2a"
log = normalize(frozenset({make_finding()}), scan_id=UUID(int=1), snapshot_id=UUID(int=2),
                codebase_id=UUID(int=3), commit_sha="a" * 40, S_version=S_VERSION,
                env_digest=ENV_DIGEST, precondition_status="closed-world", llm_triage_flag=False)
assert log.sarif_hash == "d6fce0db36b454b60fbae752c176ec1ccb7bdfb53db644b188f88edd870c9ff5"
public = signer.get_public_key(KeyId=KEY_ID, KeyVersion=KEY_VERSION)["PublicKey"]
document = {
    "fixture_format": "scanipy-test-provenance-compatibility/1",
    "baseline_commit": "c7eb7b3e4cad8f66d2098213998b7931474295a5",
    "captured_on": "2026-09-26", "capture_python": "3.11.16",
    "classification": "synthetic codec/crypto compatibility; no source or operator authority",
    "public_key": {"key_id": KEY_ID, "key_version": KEY_VERSION, "der_hex": public.hex(),
                   "sha256": hashlib.sha256(public).hexdigest()},
    "records": records,
    "sarif": {"finding_builder": "tests.fnd01_fakes.make_finding()",
              "input": {"scan_id": str(UUID(int=1)), "snapshot_id": str(UUID(int=2)),
                        "codebase_id": str(UUID(int=3)), "commit_sha": "a" * 40,
                        "S_version": S_VERSION, "env_digest": ENV_DIGEST,
                        "precondition_status": "closed-world", "llm_triage_flag": False},
              "canonical_utf8": log.canonical_bytes.decode(), "sha256": log.sarif_hash,
              "partitions": [{"partition": run.partition, "canonical_utf8": run.canonical_bytes.decode(),
                              "sha256": run.sarif_hash, "result_count": run.result_count} for run in log.runs]},
}
print(json.dumps(document, ensure_ascii=False, indent=2))
```

The separate tenth-example recipe has SHA-256
`7e8965b2ac3cf60c50c8337797a24db7d9b3e7cf6a614933d8721f96c5be788c`
(including its final LF):

```python
"""Separate tenth fixture capture; the original nine fixtures stay unchanged."""

import dataclasses
import hashlib
import json
from uuid import UUID

from analysis.artifact_identity import GRAPH_V2, SLICE_V2, ArtifactIdentity
from analysis.sarif.canonical_emit import normalize
from services.scan.provenance import Sha256, export_auditor_record, sign_provenance
from services.scan.software_kms_signer import SoftwareKMSSigner
from tests.fnd01_fakes import ENV_DIGEST, S_VERSION, make_finding
from tests.fnd03_fakes import InMemoryProvenanceStore, make_chain_record

log = normalize(frozenset({make_finding()}), scan_id=UUID(int=1), snapshot_id=UUID(int=2),
                codebase_id=UUID(int=3), commit_sha="a" * 40, S_version=S_VERSION,
                env_digest=ENV_DIGEST, precondition_status="closed-world", llm_triage_flag=False)
assert log.sarif_hash == "d6fce0db36b454b60fbae752c176ec1ccb7bdfb53db644b188f88edd870c9ff5"
record = dataclasses.replace(
    make_chain_record(), id=UUID(int=10001), scan_id=UUID(int=1),
    finding_id=UUID(int=10003), org_id=UUID(int=10004), codebase_id=UUID(int=3),
    snapshot_id=UUID(int=2), S_version=S_VERSION, env_digest=ENV_DIGEST,
    sarif_hash=Sha256(bytes.fromhex(log.sarif_hash)),
    record_schema_version=2, fingerprint_class=None,
)
record = dataclasses.replace(record, artifact_identity={
    "schema_version": 2,
    "cpg_order": ArtifactIdentity("completed", record.cpg_order_hash.hex(), "strong", GRAPH_V2).to_dict(),
    "slice": ArtifactIdentity("completed", record.slice_fingerprint.hex(), "strong", SLICE_V2).to_dict(),
})
key_id = "fixture-public-key/provenance-full-log"
version = "capture-2026-09-26"
signer = SoftwareKMSSigner(version=version, env={})
store = InMemoryProvenanceStore()
signed = sign_provenance(record, signer=signer, kms_key_arn=key_id, store=store)
public = signer.get_public_key(KeyId=key_id, KeyVersion=version)["PublicKey"]

def value(item):
    if isinstance(item, UUID):
        return str(item)
    if isinstance(item, bytes):
        return item.hex()
    return item

document = {
    "fixture_format": "scanipy-test-provenance-compatibility/1",
    "baseline_commit": "c7eb7b3e4cad8f66d2098213998b7931474295a5",
    "captured_on": "2026-09-26", "capture_python": "3.11.16",
    "classification": "synthetic signed full-log binding; no source or operator authority",
    "public_key": {"key_id": key_id, "key_version": version, "der_hex": public.hex(),
                   "sha256": hashlib.sha256(public).hexdigest()},
    "records": [{
        "name": "v2_full_log",
        "input": {field.name: value(getattr(record, field.name)) for field in dataclasses.fields(record)},
        "canonical_utf8": signed.canonical_bytes.decode("utf-8"),
        "canonical_sha256": hashlib.sha256(signed.canonical_bytes).hexdigest(),
        "signature_hex": signed.signature.hex(), "signature_alg": signed.signature_alg,
        "kms_key_arn": signed.kms_key_arn, "kms_key_version": signed.kms_key_version,
        "export_utf8": json.dumps(export_auditor_record(record.id, store=store),
                                   ensure_ascii=False, separators=(",", ":")),
    }],
    "sarif_reference": {"fixture": "corpus.json", "sha256": log.sarif_hash},
}
print(json.dumps(document, ensure_ascii=False, indent=2))
```
