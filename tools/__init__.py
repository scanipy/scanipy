"""Cross-cutting platform tooling (non-service packages).

Hosts:

* ``tools.observability`` (CMP-DEPLOY-03) — OpenTelemetry initialisation +
  structured-logging surface every service imports at boot.
* ``tools.scaffold_class`` (CMP-DET-03) — one-shot CLI/library tools that author
  the on-disk ``detectors/<class>/`` layout the registry (CMP-DET-02) reads.

These tools write NO provenance fields: scaffolded/observability content carries
provenance only once the registry registers it and CMP-ORCH-03 stamps ``origin``
downstream (DOC-CMP-DET-03 §8).
"""
