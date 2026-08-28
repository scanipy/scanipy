"""Unit tests for the DOCKER-02 substrate factory (CLAR-DEPLOY-25).

Verifies the AWS-vs-local selection: local (non-AWS) is the default; AWS is opt-in
and requires its config. boto3 client construction is offline (creds/network are
resolved lazily on first call), so the AWS branch is hermetic here.
"""

from __future__ import annotations

import pytest

from services.substrate.factory import (
    object_store_from_env,
    queue_from_env,
    substrate_mode,
)
from services.substrate.object_store import InMemoryObjectStore, S3ObjectStore
from services.substrate.queue import SQSQueue, StandardQueue


@pytest.mark.unit
def test_defaults_to_local_non_aws(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SCANIPY_SUBSTRATE", raising=False)
    assert substrate_mode() == "local"
    assert isinstance(object_store_from_env(), InMemoryObjectStore)
    assert isinstance(queue_from_env(), StandardQueue)


@pytest.mark.unit
def test_local_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCANIPY_SUBSTRATE", "LOCAL")  # case-insensitive
    assert isinstance(object_store_from_env(), InMemoryObjectStore)
    assert isinstance(queue_from_env(), StandardQueue)


@pytest.mark.unit
def test_aws_selects_s3_and_sqs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCANIPY_SUBSTRATE", "aws")
    monkeypatch.setenv("S3_BUCKET", "scanipy-bucket")
    monkeypatch.setenv("DETECTOR_QUEUE_URL", "https://sqs.local/queue")
    # A custom endpoint exercises the MinIO/LocalStack path (offline client ctor).
    monkeypatch.setenv("AWS_ENDPOINT_URL", "http://localhost:4566")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    assert isinstance(object_store_from_env(), S3ObjectStore)
    assert isinstance(queue_from_env(), SQSQueue)


@pytest.mark.unit
def test_aws_requires_bucket(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCANIPY_SUBSTRATE", "aws")
    monkeypatch.delenv("S3_BUCKET", raising=False)
    with pytest.raises(RuntimeError, match="S3_BUCKET"):
        object_store_from_env()


@pytest.mark.unit
def test_aws_requires_queue_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCANIPY_SUBSTRATE", "aws")
    monkeypatch.delenv("DETECTOR_QUEUE_URL", raising=False)
    with pytest.raises(RuntimeError, match="DETECTOR_QUEUE_URL"):
        queue_from_env()
