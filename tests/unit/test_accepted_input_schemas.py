"""Closed finite schemas reject extra authority or invented execution evidence."""

from copy import deepcopy

import pytest

from services.scan.accepted_inputs import codec as c
from services.scan.accepted_inputs import schemas as s
from tests import accepted_input_fixtures as fixtures

pytestmark = pytest.mark.unit
material = fixtures.material
test_only_keys = fixtures.test_only_keys
bundle_fixture = fixtures.bundle_fixture


@pytest.mark.parametrize(
    "schema,role",
    [
        (s.APPROVAL, "approval-statement"),
        (s.POLICY, "publication-policy"),
        (s.ADMISSION, "admission-checkpoint"),
        (s.ADOPTION, "operator-adoption"),
        (s.PUBLICATION, "publication-receipt"),
        (s.INVENTORY, "approval-evidence-inventory"),
    ],
)
@pytest.mark.parametrize("change", ["extra", "missing", "wrong-schema"])
def test_all_authority_documents_are_closed(material, schema, role, change):
    value = c.decode_document(material.objects[role], schema)
    if change == "extra":
        value["accepted"] = True
    elif change == "missing":
        del value["schema"]
    else:
        value["schema"] = schema + "-future"
    with pytest.raises(s.VerificationError):
        c.encode_document(value, schema)


@pytest.mark.parametrize(
    "field,value",
    [
        ("approval_kind", "statistical-spec"),
        ("proposal_id", "00000000-0000-0000-0000-000000000001"),
        ("key_version", True),
        ("signature_profile", "rsa-pkcs1v15"),
        ("scope", "global"),
    ],
)
def test_operator_lane_cannot_acquire_other_authority(material, field, value):
    row = c.decode_document(material.objects["approval-statement"], s.APPROVAL)
    row[field] = value
    with pytest.raises(s.VerificationError):
        c.encode_document(row, s.APPROVAL)


@pytest.mark.parametrize(
    "field,value",
    [
        ("capability", "publish-statistical"),
        ("status", "unknown"),
        ("status", "revoked"),
        ("status_changed_at", "2026-09-25T00:00:00Z"),
        ("not_after", "2026-09-25T00:00:00Z"),
    ],
)
def test_policy_grant_closed_status_and_capability(material, field, value):
    row = c.decode_document(material.objects["current-policy"], s.POLICY)
    row["grants"][0][field] = value
    with pytest.raises(s.VerificationError):
        c.encode_document(row, s.POLICY)


@pytest.mark.parametrize(
    "field,value",
    [
        ("reason", ""),
        ("reason", "x" * 4097),
        ("expires_at", "2026-10-03T00:00:00Z"),
        ("issued_at", "2026-02-30T00:00:00Z"),
        ("generation", 2),
        ("generation", False),
    ],
)
def test_checkpoint_exact_time_generation_and_reason(material, field, value):
    row = c.decode_document(material.objects["admission-checkpoint"], s.ADMISSION)
    row[field] = value
    with pytest.raises(s.VerificationError):
        c.encode_document(row, s.ADMISSION)


@pytest.mark.parametrize(
    "field,value",
    [
        ("cwes", []),
        ("cwes", [78]),
        ("cwes", ["CWE-078"]),
        ("cwes", ["CWE-78", "CWE-78"]),
        ("languages", ["python", "python"]),
        ("frameworks", ["x"] * 33),
        ("engine", "ide"),
        ("severity_default", "urgent"),
        ("profiles", []),
        ("rule_ids", []),
    ],
)
def test_descriptor_exact_vocabularies(field, value):
    bundle = bundle_fixture()
    row = c.decode_document(bundle.detector_blobs[0], s.DETECTOR)
    row[field] = value
    with pytest.raises(s.VerificationError):
        c.encode_document(row, s.DETECTOR)


@pytest.mark.parametrize(
    "change",
    ["duplicate-model", "unused-model", "missing-model", "rule-collision", "detector-collision"],
)
def test_manifest_inventory_is_unambiguous(change):
    row = deepcopy(c.decode_spec(bundle_fixture().spec_bytes)[0])
    if change == "duplicate-model":
        row["models"].append(row["models"][0])
    elif change == "unused-model":
        row["models"].append(dict(row["models"][0], artifact_id="unused", raw_sha256="0" * 64))
    elif change == "missing-model":
        row["models"] = []
    elif change == "rule-collision":
        row["detectors"][0]["rules"] *= 2
    else:
        row["detectors"] *= 2
    with pytest.raises(s.VerificationError):
        c.encode_document(row, s.S_MANIFEST)


@pytest.mark.parametrize(
    "field,value",
    [
        ("purpose", "identity-attempt"),
        ("work_kind", "identity"),
        ("occurrence_id", "00000000-0000-0000-0000-000000000001"),
        ("action", "renew"),
        ("lease_expires_at", "2026-09-25T00:00:01.000000Z"),
    ],
)
def test_execution_target_fields_and_exact_leases(material, field, value):
    row = dict(material.authorization)
    row[field] = value
    with pytest.raises(s.VerificationError):
        c.encode_document(row, s.EXECUTION)
