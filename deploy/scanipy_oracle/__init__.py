"""Scanipy self-host oracle-scan service (DOCKER-01, CLAR-DEPLOY-25).

The one-command Docker deployment's scan surface. Runs the **oracle-passthrough**
detection path (Semgrep) — clone a public repo, scan it, return findings — and
persists results to a clearly-namespaced ``oracle`` Postgres schema.

This is deliberately NOT the deterministic-core (IFDS/CPG) pipeline: that path is
CPG-centric and staged (see PLAN.md honest-labeling ledger). Every finding here is
labeled ``origin = oracle-passthrough`` and carries a ``weak`` same-source
fingerprint — no canonical-CPG claim is made or faked (INV-1 / INV-5 honest).
"""
