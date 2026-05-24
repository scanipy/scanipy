"""CMP-DET-01 — parsed-spec aggregate.

A :class:`Spec` is the frozen output of :func:`analysis.ifds.dsl.parser.parse_spec`:
a closure-checked detector spec ready for CMP-DET-02 registration. Signature is
normative per DOC-CMP-DET-01 §3.2.

CMP-DET-01 writes NO provenance fields (DOC-CMP-DET-01 §8): it emits only parsed
Spec objects. ``origin`` / ``S_version`` / ``env_digest`` / ``cpg_order_hash``
are threaded downstream (CMP-DET-02 derives ``determinism_partition`` from
``engine``; CMP-ORCH-03 stamps ``origin``; CMP-FND-*/CMP-CORE-03 carry the rest).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from analysis.ifds.dsl.primitives import Clause

EngineTag = Literal["ifds", "ide"]  # DSL specs only; oracle engines never parse here
ClassName = Literal[
    "injection",
    "path-traversal",
    "ssrf",
    "deserialization",
    "xss",
    "crypto-misuse",
    "authn-authz",
    "secrets",
    "dep-cve",
    "memory-safety",
]
Language = Literal[
    "java",
    "python",
    "javascript",
    "typescript",
    "go",
    "ruby",
    "php",
]

CLASS_NAMES: frozenset[str] = frozenset(
    (
        "injection",
        "path-traversal",
        "ssrf",
        "deserialization",
        "xss",
        "crypto-misuse",
        "authn-authz",
        "secrets",
        "dep-cve",
        "memory-safety",
    )
)
LANGUAGES: frozenset[str] = frozenset(
    ("java", "python", "javascript", "typescript", "go", "ruby", "php")
)
# Core-eligible engines for a DSL spec. Oracle engines (semgrep/cpg-query/
# external) MUST NOT appear in a DSL file (E-DSL-009).
DSL_ENGINES: frozenset[str] = frozenset(("ifds", "ide"))


@dataclass(frozen=True)
class Spec:
    """A parsed, closure-checked detector spec ready for CMP-DET-02 registration."""

    id: str
    class_: ClassName
    languages: tuple[Language, ...]
    engine: EngineTag
    clauses: tuple[Clause, ...]
