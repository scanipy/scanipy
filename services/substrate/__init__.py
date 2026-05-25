"""CMP-DEPLOY-01 — runtime-substrate abstraction primitives.

This package holds the *substrate-abstraction primitives* exercised by the
CMP-DEPLOY-01 acceptance criteria (AC-DEPLOY-01b/c). The substrate *decisions*
themselves live in the written decision record
``docs/cross-cutting/DOC-DEPLOY-DECISIONS.md`` (16 RESOLVED CLAR-DEPLOY-*), and
the production IaC half lives under ``infra/`` (Terraform/CDK). The code here is
the deterministic, offline-testable *port surface* that downstream components
(CMP-SNAP-01, CMP-ORCH-01..03, CMP-SNAP-05) program against:

  * :mod:`services.substrate.object_store` — the deterministic S3 key scheme of
    ``CLAR-DEPLOY-02`` plus an in-memory object store with a path-traversal
    guard (the CLAR-DEPLOY-16 layer-1 backstop, modelled offline).
  * :mod:`services.substrate.queue` — the SQS-equivalent at-least-once queue
    with a per-queue Dead Letter Queue (``CLAR-DEPLOY-06``, max-receive 3) and
    an idempotent-consumer contract keyed on ``snapshot_id``.

The KMS-equivalent primitive (``CLAR-DEPLOY-04``, AC-DEPLOY-01e) is *not*
re-implemented here: it is owned by ``services.credential_encryption`` (CMP-CP-02)
and reused directly, so there is exactly one envelope-encryption surface.

Everything is wired against in-memory fakes; no boto3 / AWS call is made. The
production wiring binds the same Protocols to boto3 S3 / SQS clients.
"""
