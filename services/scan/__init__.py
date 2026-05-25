"""Scan services package (findings store, normalizer, orchestration worker).

Currently exports the CMP-FND-02 persistent ``findings`` row schema as a
SQLAlchemy ORM model (``services.scan.models.findings.Finding``). Sibling scan
services (CMP-FND-01 normalizer, CMP-ORCH-03 worker, CMP-FND-03 provenance)
land in this package as they are implemented.
"""
