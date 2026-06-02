"""Scanipy worker container build artifacts (CMP-DEPLOY-02).

This package holds the build-time specification for the worker container
baseline: the digest-pinning manifest (`pins.json`), the multi-stage
Dockerfiles under `snapshot/` and `detector/`, and the `build.verify_pins`
publish gate that discharges AC-DEPLOY-02c.
"""
