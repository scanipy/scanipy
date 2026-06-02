"""CMP-TRI-01 — LLM triage ranking (Triage & Spec-Inference subsystem).

Implementation contract: ``docs/components/DOC-CMP-TRI-01.md``.
Cross-cutting refs: ``DOC-DB §4.14`` (``triage_scores`` schema + the
``scanipy_triage`` grants block), ``DOC-INV §5`` (INV-3 four-discharge-mechanism
exposition), ``DOC-PARTITION §2`` (``LLM_TRIAGE=off`` in the core Attestor
pipeline), ``.claude/rules/01-invariants.md §INV-3``,
``.claude/rules/02-provenance.md`` (the TRI-01 write-surface table).

``CMP-TRI-01`` is the **INV-3 OWNER** surface: a post-hoc, *additive* ranker that
helps human triagers prioritise work. It runs **after** the deterministic core
has emitted a finding into ``findings``; it reads a column-restricted projection
of each finding plus a bounded source-code window, sends both to an injected LLM
collaborator, and writes the resulting score / reason into a **separate** table
(``triage_scores``). It is not on any detection path, not on any attestation
path, and not in the signed provenance chain that backs reproducibility theorem
(a).

The non-negotiable, schema-enforced, triply-tested contract (DOC-CMP-TRI-01 §2):

  * It MUST NOT write any column on ``findings`` (the ``scanipy_triage`` DB role
    holds ``GRANT INSERT ON triage_scores`` only; ``REVOKE ALL ON findings``).
  * It MUST NOT delete a finding, and MUST NOT set ``findings.status`` (or any
    status transition) from its own output — ranking is strictly **additive**.
  * It MUST NOT influence ``origin``, ``S_version``, ``env_digest``,
    ``slice_fingerprint``, ``cpg_order_hash``, ``fingerprint_class``,
    ``determinism_partition``, ``engine`` or any detection-content column.
  * It MUST NOT read or write ``spec_versions``, ``proposed_specs`` or
    ``provenance_records``.

Feature-flag default OFF (``LLM_TRIAGE=off``): when OFF, ``run_triage_cycle`` is
a no-op — no LLM call is made and no ``triage_scores`` row is written
(DOC-CMP-TRI-01 §5 mechanism (b); ``TST-AC-TRI-01a``).

Every external collaborator (the LLM client, the column-restricted findings read
surface, the ``triage_scores`` write surface) is injected as a ``Protocol`` so
the component is testable offline without a real Anthropic API or PostgreSQL —
mirroring the DI + in-memory-fake convention of
``services/credential_encryption.py`` and ``services/scan/provenance``.
"""

from __future__ import annotations

from services.triage.triage import (
    ALLOWED_TRIAGE_COLUMNS,
    DEFAULT_CODE_WINDOW_BYTE_BUDGET,
    MODEL_ID,
    TRIAGE_SCORES_TABLE,
    FindingsReadSurface,
    FindingView,
    LLMClient,
    LLMTriageVerdict,
    TriageCycleResult,
    TriageInput,
    TriageScore,
    TriageScoresWriteSurface,
    TriageWriteSurfaceViolation,
    run_triage_cycle,
    triage_finding,
)

__all__ = [
    "ALLOWED_TRIAGE_COLUMNS",
    "DEFAULT_CODE_WINDOW_BYTE_BUDGET",
    "MODEL_ID",
    "TRIAGE_SCORES_TABLE",
    "FindingView",
    "FindingsReadSurface",
    "LLMClient",
    "LLMTriageVerdict",
    "TriageCycleResult",
    "TriageInput",
    "TriageScore",
    "TriageScoresWriteSurface",
    "TriageWriteSurfaceViolation",
    "run_triage_cycle",
    "triage_finding",
]
