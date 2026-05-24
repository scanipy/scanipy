"""CMP-DET-01 — structured DSL rejection diagnostics.

Every rejection raises :class:`DSLError` with one of the stable
``E-DSL-001..009`` codes (DOC-DSL §6, DOC-CMP-DET-01 §7.1). The diagnostic is
structured ``{code, message, line, col, suggested_fix}`` and is emitted *before*
any registration side effect; rejection is total (no partial-parse Spec).

INV-4 safe direction: any spec outside the distributive-by-construction grammar
is rejected here, never analyzed.
"""

from __future__ import annotations

from typing import Literal

DSLErrorCode = Literal[
    "E-DSL-001",  # raw regex outside AccessPathPattern grammar
    "E-DSL-002",  # embedded Semgrep oracle pattern
    "E-DSL-003",  # embedded cpg-query / CodeQL expression
    "E-DSL-004",  # non-declarative callable (lambda / def)
    "E-DSL-005",  # sequencing operator not in sanctioned compositions
    "E-DSL-006",  # conditional operator not in sanctioned compositions
    "E-DSL-007",  # user fixpoint operator not in sanctioned compositions
    "E-DSL-008",  # unknown primitive head
    "E-DSL-009",  # engine not in {ifds, ide} for a DSL-parsed spec
]


class DSLError(Exception):
    """Structured, total DSL-rejection diagnostic.

    Attributes mirror DOC-DSL §6/§7: a stable ``code`` downstream tooling
    (CMP-DET-02 AC-DET-02a) matches on, a human ``message``, source
    ``line``/``col``, and a ``suggested_fix`` hint. ``__str__`` renders the
    DOC-DSL §8 diagnostic shape.
    """

    def __init__(
        self: DSLError,
        code: DSLErrorCode,
        message: str,
        *,
        line: int,
        col: int,
        suggested_fix: str,
        source_path: str | None = None,
    ) -> None:
        self.code: DSLErrorCode = code
        self.message: str = message
        self.line: int = line
        self.col: int = col
        self.suggested_fix: str = suggested_fix
        self.source_path: str | None = source_path
        super().__init__(self._render())

    def _render(self: DSLError) -> str:
        loc = self.source_path or "<dsl-spec>"
        return (
            f"{loc}:{self.line}:{self.col}: error [{self.code}]\n"
            f"  {self.message}\n"
            f"hint: {self.suggested_fix}\n"
            f"spec rejected; not registered"
        )
