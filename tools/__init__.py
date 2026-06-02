"""CMP-DET-03 — detector-catalog scaffolding + migration tools.

One-shot CLI/library tools that author the on-disk ``detectors/<class>/`` layout
the registry (CMP-DET-02) reads at boot. These tools write NO provenance fields
(DOC-CMP-DET-03 §8): scaffolded content carries provenance only once the registry
registers it and CMP-ORCH-03 stamps ``origin`` downstream.
"""
