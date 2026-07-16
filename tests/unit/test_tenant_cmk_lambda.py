"""Hermetic unit tests for the per-tenant CMK provisioning Lambda (CMP-DEPLOY-05 §3.3).

Covers the 2026-07-15 hardening:

1. **Strict org_id validation** — canonical lowercase UUID (the DB ``orgs.id``
   column is ``uuid``, db/migrations 20260524_0001) enforced BEFORE any
   interpolation into the KMS alias or key-policy JSON, and before any KMS
   client call.
2. **Rotation-retry gap** — ``enable_key_rotation`` is (re-)ensured even when
   ``describe_key`` finds an existing key, so a crash between ``create_alias``
   and ``enable_key_rotation`` on a prior invocation heals on retry.

No AWS SDK, no network: a fake KMS client is injected (moto is not a dev-dep
in this repo yet; per CLAR-DEPLOY-21 these are construction/mechanics
assertions only — policy *enforcement* is live-window territory).

The Lambda file lives outside the package tree (``infra/modules/kms/``), so it
is loaded by path, mirroring how the Lambda runtime itself loads it.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

pytestmark = pytest.mark.unit

_LAMBDA_PATH = (
    Path(__file__).resolve().parents[2] / "infra" / "modules" / "kms" / "tenant_cmk_lambda.py"
)


def _load_lambda_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("tenant_cmk_lambda", _LAMBDA_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


lam = _load_lambda_module()

ORG_A = "0f7e9b1a-3c2d-4e5f-8a9b-0c1d2e3f4a5b"


class _NotFoundError(Exception):
    """Stands in for kms.exceptions.NotFoundException (boto3's own name; ours
    ends in ``Error`` per N818 — only the *attribute* below must be spelled
    ``NotFoundException`` to match the real botocore exceptions namespace)."""


class _Exceptions:
    NotFoundException = _NotFoundError


class FakeKms:
    """Minimal in-memory KMS double for the provisioning call surface."""

    exceptions = _Exceptions

    def __init__(self) -> None:
        self.aliases: dict[str, str] = {}
        self.key_policies: dict[str, str] = {}
        self.key_tags: dict[str, list[dict[str, str]]] = {}
        self.rotation_enabled: set[str] = set()
        self.calls: list[str] = []
        self._seq = 0

    def _arn(self, key_id: str) -> str:
        return f"arn:aws:kms:us-east-1:123456789012:key/{key_id}"

    def describe_key(self, **kwargs: str) -> dict[str, Any]:
        self.calls.append("describe_key")
        key_ref = kwargs["KeyId"]
        if key_ref.startswith("alias/"):
            if key_ref not in self.aliases:
                raise _NotFoundError(key_ref)
            key_id = self.aliases[key_ref]
        else:
            key_id = key_ref
        return {"KeyMetadata": {"KeyId": key_id, "Arn": self._arn(key_id)}}

    def create_key(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append("create_key")
        self._seq += 1
        key_id = f"key-{self._seq:04d}"
        self.key_policies[key_id] = kwargs["Policy"]
        self.key_tags[key_id] = kwargs["Tags"]
        return {"KeyMetadata": {"KeyId": key_id, "Arn": self._arn(key_id)}}

    def create_alias(self, **kwargs: str) -> None:
        self.calls.append("create_alias")
        self.aliases[kwargs["AliasName"]] = kwargs["TargetKeyId"]

    def enable_key_rotation(self, **kwargs: str) -> None:
        self.calls.append("enable_key_rotation")
        self.rotation_enabled.add(kwargs["KeyId"])


@pytest.fixture()
def env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ACCOUNT_ID", "123456789012")
    monkeypatch.setenv("WORKER_TASK_ROLE_ARN", "arn:aws:iam::123456789012:role/scanipy-ecs-worker")


# ---------------------------------------------------------------------------
# org_id validation — strict canonical lowercase UUID, checked pre-interpolation
# ---------------------------------------------------------------------------


def test_validate_accepts_canonical_lowercase_uuid() -> None:
    assert lam.validate_org_id(ORG_A) == ORG_A


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "acme-corp",
        ORG_A.upper(),  # uppercase would mint a *different* case-sensitive alias
        ORG_A.replace("-", ""),
        "{" + ORG_A + "}",
        ORG_A + "\n",
        ORG_A[:-1],
        "../../orgs/victim",
        "alias/scanipy-tenant-*",
        '0f7e9b1a-3c2d-4e5f-8a9b-0c1d2e3f4a5b"},{"Sid":"Evil',
        "0f7e9b1a-3c2d-4e5f-8a9b-0c1d2e3f4a5g",  # non-hex char
    ],
)
def test_validate_rejects_non_canonical_org_ids(bad: str) -> None:
    with pytest.raises(lam.OrgIdValidationError):
        lam.validate_org_id(bad)


def test_validate_rejects_non_string_org_id() -> None:
    with pytest.raises(lam.OrgIdValidationError):
        lam.validate_org_id(12345)


def test_org_id_validation_error_is_a_value_error() -> None:
    """CMP-CP-02 catches ValueError on the onboarding path; keep the contract."""
    assert issubclass(lam.OrgIdValidationError, ValueError)


def test_invalid_org_id_rejected_before_any_kms_call() -> None:
    """The validator is an input boundary: no KMS API may see a bad org_id."""
    fake = FakeKms()
    with pytest.raises(lam.OrgIdValidationError):
        lam.provision_tenant_cmk("../../orgs/victim", kms_client=fake)
    assert fake.calls == []


# ---------------------------------------------------------------------------
# Fresh-provision path — key, alias, policy shape, rotation
# ---------------------------------------------------------------------------


def test_fresh_provision_creates_key_alias_and_rotation(env: None) -> None:
    fake = FakeKms()
    arn = lam.provision_tenant_cmk(ORG_A, kms_client=fake)

    assert arn == fake._arn("key-0001")
    assert fake.aliases == {f"alias/scanipy-tenant-{ORG_A}": "key-0001"}
    assert "key-0001" in fake.rotation_enabled

    policy = json.loads(fake.key_policies["key-0001"])
    worker = next(s for s in policy["Statement"] if s["Sid"] == "WorkerDecrypt")
    assert worker["Condition"]["StringEquals"]["kms:EncryptionContext:org_id"] == ORG_A
    assert worker["Condition"]["StringLike"]["aws:RoleSessionName"] == "scan-*"
    assert {"TagKey": "org_id", "TagValue": ORG_A} in fake.key_tags["key-0001"]


def test_fresh_provision_orders_rotation_after_alias(env: None) -> None:
    fake = FakeKms()
    lam.provision_tenant_cmk(ORG_A, kms_client=fake)
    assert fake.calls == ["describe_key", "create_key", "create_alias", "enable_key_rotation"]


# ---------------------------------------------------------------------------
# Existing-key path — idempotency + the rotation-retry gap fix
# ---------------------------------------------------------------------------


def test_existing_key_returns_same_arn_without_recreating(env: None) -> None:
    fake = FakeKms()
    first = lam.provision_tenant_cmk(ORG_A, kms_client=fake)
    second = lam.provision_tenant_cmk(ORG_A, kms_client=fake)
    assert first == second
    assert fake.calls.count("create_key") == 1


def test_existing_key_with_rotation_off_is_healed(env: None) -> None:
    """Rotation-retry gap: alias exists but rotation was never enabled
    (crash between create_alias and enable_key_rotation on a prior run).
    A retry must re-ensure rotation before returning."""
    fake = FakeKms()
    fake.aliases[f"alias/scanipy-tenant-{ORG_A}"] = "key-preexisting"
    assert "key-preexisting" not in fake.rotation_enabled

    arn = lam.provision_tenant_cmk(ORG_A, kms_client=fake)

    assert arn == fake._arn("key-preexisting")
    assert "key-preexisting" in fake.rotation_enabled
    assert "create_key" not in fake.calls


# ---------------------------------------------------------------------------
# Handler contract
# ---------------------------------------------------------------------------


def test_handler_requires_org_id() -> None:
    with pytest.raises(ValueError, match="org_id"):
        lam.provision_tenant_cmk_handler({}, None)


def test_handler_rejects_malformed_org_id_before_kms() -> None:
    # No env vars and no AWS SDK are available here: if validation did not
    # fire first, this would fail with a RuntimeError/ImportError instead.
    with pytest.raises(lam.OrgIdValidationError):
        lam.provision_tenant_cmk_handler({"org_id": "ACME/../*"}, None)
