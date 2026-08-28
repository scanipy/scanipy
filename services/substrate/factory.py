"""Substrate factory (DOCKER-02, CLAR-DEPLOY-25).

Selects the object-store + queue implementations from the environment, **defaulting
to the self-hostable, non-AWS implementations**. Before this, callers constructed a
concrete substrate directly, hard-wiring AWS at every call site; this factory is the
single place the AWS-vs-local choice is made, so a self-hosted deployment is
AWS-free by default and AWS is strictly opt-in.

Selection (env ``SCANIPY_SUBSTRATE``):

* unset / ``local`` (default) → :class:`~services.substrate.object_store.InMemoryObjectStore`
  + :class:`~services.substrate.queue.StandardQueue`. No cloud, no boto3.
* ``aws`` → :class:`~services.substrate.object_store.S3ObjectStore` (needs ``S3_BUCKET``)
  + :class:`~services.substrate.queue.SQSQueue` (needs ``DETECTOR_QUEUE_URL``). With
  ``AWS_ENDPOINT_URL`` set, both target a self-hosted S3/SQS-compatible service
  (MinIO / LocalStack) instead of real AWS.
"""

from __future__ import annotations

import os

from services.substrate.object_store import (
    InMemoryObjectStore,
    ObjectStore,
    S3ObjectStore,
)
from services.substrate.queue import Queue, SQSQueue, StandardQueue

_AWS = "aws"
_DEFAULT_QUEUE_NAME = "scanipy-local"


def substrate_mode() -> str:
    """The selected substrate mode: ``"aws"`` or ``"local"`` (default)."""
    return os.environ.get("SCANIPY_SUBSTRATE", "local").strip().lower()


def object_store_from_env() -> ObjectStore:
    """Build the object store for the current environment (local by default)."""
    if substrate_mode() == _AWS:
        bucket = os.environ.get("S3_BUCKET")
        if not bucket:
            raise RuntimeError("SCANIPY_SUBSTRATE=aws requires S3_BUCKET to be set")
        return S3ObjectStore(bucket)
    return InMemoryObjectStore()


def queue_from_env() -> Queue:
    """Build the job queue for the current environment (local by default)."""
    if substrate_mode() == _AWS:
        url = os.environ.get("DETECTOR_QUEUE_URL")
        if not url:
            raise RuntimeError("SCANIPY_SUBSTRATE=aws requires DETECTOR_QUEUE_URL to be set")
        return SQSQueue(url)
    return StandardQueue(name=os.environ.get("SCANIPY_QUEUE_NAME", _DEFAULT_QUEUE_NAME))
