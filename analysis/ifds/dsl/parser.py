"""CMP-DET-01 — DSL parser entry point (``parse_spec``).

The parser is the **decidable membership test** against the
distributive-by-construction combinator grammar (DOC-DSL §2). It is the
operational owner of INV-4's safe direction: a spec is either in the grammar
(parse succeeds, frozen :class:`Spec` returned) or it is not (parse fails,
:class:`DSLError` raised). There is no partial-success path and no fallback
(DOC-CMP-DET-01 §7.3).

Spec file shape (DOC-DSL §8 examples): a YAML-style header block
(``id``/``class``/``languages``/``engine``) followed by a clause list of
``source`` / ``sink`` / ``sanitize`` / ``propagate`` lines. Comments (``#``) and
blank lines are ignored.

Every rejection carries a precise ``E-DSL-001..009`` code per DOC-DSL §6.
"""

from __future__ import annotations

import re
from typing import cast

from analysis.ifds.dsl.errors import DSLError, DSLErrorCode
from analysis.ifds.dsl.primitives import (
    AccessPathPattern,
    ArgRef,
    Clause,
    FieldRef,
    Propagate,
    Sanitize,
    Sink,
    Source,
)
from analysis.ifds.dsl.spec import (
    CLASS_NAMES,
    DSL_ENGINES,
    LANGUAGES,
    ClassName,
    EngineTag,
    Language,
    Spec,
)

# Primitive heads pinned by SDD CMP-DET-01 / DOC-DSL §2.
_PRIMITIVE_HEADS: frozenset[str] = frozenset(("source", "sink", "sanitize", "propagate"))

# Sequencing / conditional / fixpoint keywords excluded by DOC-DSL §4.3. Matched
# as standalone tokens so an identifier like "ifds_then_x" does not false-trip.
_SEQUENCING_KW: frozenset[str] = frozenset(("then", "seq", ";"))
_CONDITIONAL_KW: frozenset[str] = frozenset(("if", "when", "guard", "else"))
_FIXPOINT_KW: frozenset[str] = frozenset(("fixpoint", "closure", "rec"))

# Escape-hatch signatures (DOC-DSL §6). Checked inside a clause body.
_RE_RAW_REGEX = re.compile(r"\bre\.compile\b|\bregex\s*\(|r['\"]")
_RE_SEMGREP = re.compile(r"\bsemgrep\b")
_RE_CPG_QUERY = re.compile(r"\bcpg\.|\bcpg-query\b|\bcodeql\b", re.IGNORECASE)
# ``lambda`` / ``def`` signal an embedded Python callable. Both are Python
# keywords and therefore never legal access-path identifiers, so matching them
# as whole words cannot collide with a real AccessPathPattern.
_RE_LAMBDA = re.compile(r"\blambda\b|\bdef\b")

_PROPAGATE_ARROW = "→"  # the Unicode rightwards arrow used in PropagateBody

_ARG_REF = re.compile(r"^arg\[(?:\d+|[A-Za-z_]\w*)\]$")
_FIELD_REF = re.compile(r"^(?:field\[[A-Za-z_]\w*\]|this\.[A-Za-z_]\w*)$")
_RETURN_REF = "ret"


def _word_tokens(text: str) -> list[str]:
    """Lowercase word tokens plus a bare ``;`` token, for keyword detection."""
    toks = re.findall(r"[A-Za-z_]\w*|;", text)
    return [t.lower() for t in toks]


def _reject(
    code: DSLErrorCode,
    message: str,
    *,
    line: int,
    col: int,
    suggested_fix: str,
    source_path: str | None,
) -> DSLError:
    return DSLError(
        code,
        message,
        line=line,
        col=col,
        suggested_fix=suggested_fix,
        source_path=source_path,
    )


def _check_escape_hatches(
    body: str, head: str, *, line: int, base_col: int, source_path: str | None
) -> None:
    """Reject any non-grammar escape hatch inside a clause body (DOC-DSL §6)."""
    if _RE_SEMGREP.search(body):
        raise _reject(
            "E-DSL-002",
            "embedded oracle pattern in DSL spec — use engine=semgrep instead",
            line=line,
            col=base_col,
            suggested_fix=(
                "move this clause to specs/oracle/ with engine: semgrep, or replace "
                "the embedded pattern with a DSL propagate(...) clause"
            ),
            source_path=source_path,
        )
    if _RE_CPG_QUERY.search(body):
        raise _reject(
            "E-DSL-003",
            "embedded cpg-query expression — use engine=cpg-query instead",
            line=line,
            col=base_col,
            suggested_fix="express this as an engine=cpg-query oracle detector, not a DSL clause",
            source_path=source_path,
        )
    if _RE_LAMBDA.search(body):
        raise _reject(
            "E-DSL-004",
            "non-declarative callable in DSL spec",
            line=line,
            col=base_col,
            suggested_fix="DSL specs are declarative data; remove the embedded callable",
            source_path=source_path,
        )
    if _RE_RAW_REGEX.search(body):
        raise _reject(
            "E-DSL-001",
            "raw regex outside AccessPathPattern grammar",
            line=line,
            col=base_col,
            suggested_fix="use an AccessPathPattern (FQN / ?T<:Type / wildcard), not a raw regex",
            source_path=source_path,
        )


def _check_composition_keywords(raw_line: str, *, line: int, source_path: str | None) -> None:
    """Reject sequencing / conditional / fixpoint combinators (DOC-DSL §4.3).

    Conditional is checked before sequencing: an ``if ... then ...`` construct is
    fundamentally a conditional (E-DSL-006), even though it also contains the
    ``then`` keyword. A bare ``then``/``;``/``seq`` without a conditional head is
    sequencing (E-DSL-005).
    """
    tokens = set(_word_tokens(raw_line))
    if tokens & _CONDITIONAL_KW:
        raise _reject(
            "E-DSL-006",
            "conditional operator not in sanctioned compositions (§4.3)",
            line=line,
            col=1,
            suggested_fix="conditional transfers break distributivity; remove the if/when/guard",
            source_path=source_path,
        )
    if tokens & _SEQUENCING_KW:
        kw = next(iter(tokens & _SEQUENCING_KW))
        raise _reject(
            "E-DSL-005",
            f"sequencing operator '{kw}' not in sanctioned compositions (§4.3)",
            line=line,
            col=1,
            suggested_fix=(
                "list clauses without a sequencing keyword; the IFDS solver composes "
                "transfers along the program supergraph (DOC-DSL §4.1)"
            ),
            source_path=source_path,
        )
    if tokens & _FIXPOINT_KW:
        kw = next(iter(tokens & _FIXPOINT_KW))
        raise _reject(
            "E-DSL-007",
            f"fixpoint operator '{kw}' not in sanctioned compositions (§4.3)",
            line=line,
            col=1,
            suggested_fix="the solver already computes the supergraph fixpoint; drop the operator",
            source_path=source_path,
        )


def _parse_clause(raw_line: str, *, line: int, source_path: str | None) -> Clause:
    """Parse a single well-formed clause or raise the precise E-DSL diagnostic."""
    _check_composition_keywords(raw_line, line=line, source_path=source_path)

    m = re.match(r"^\s*([A-Za-z_]\w*)\s*\((.*)\)\s*$", raw_line)
    if m is None:
        raise _reject(
            "E-DSL-008",
            f"malformed clause; expected one of {sorted(_PRIMITIVE_HEADS)}",
            line=line,
            col=1,
            suggested_fix="write head(access-path-pattern), e.g. source(pkg.api(*))",
            source_path=source_path,
        )

    head = m.group(1).lower()
    body = m.group(2).strip()
    body_col = m.start(2) + 1

    if head not in _PRIMITIVE_HEADS:
        raise _reject(
            "E-DSL-008",
            f"unknown primitive '{head}'; expected one of {sorted(_PRIMITIVE_HEADS)}",
            line=line,
            col=1,
            suggested_fix=(
                "declare source(...) and sink(...) separately; the solver computes the flow"
            ),
            source_path=source_path,
        )

    _check_escape_hatches(body, head, line=line, base_col=body_col, source_path=source_path)

    if head == "propagate":
        return _parse_propagate(body, line=line, source_path=source_path)
    pattern = AccessPathPattern(body)
    if head == "source":
        return Source(pattern)
    if head == "sink":
        return Sink(pattern)
    return Sanitize(pattern)


def _parse_propagate(body: str, *, line: int, source_path: str | None) -> Propagate:
    """Parse a PropagateBody: one of the four sanctioned source->target forms."""
    if _PROPAGATE_ARROW not in body:
        raise _reject(
            "E-DSL-008",
            "propagate body must be 'source → target' (one of the four §3.4 forms)",
            line=line,
            col=1,
            suggested_fix="use propagate(arg[0] → ret) and similar sanctioned forms",
            source_path=source_path,
        )
    left, _, right = body.partition(_PROPAGATE_ARROW)
    src = left.strip()
    tgt = right.strip()

    src_is_arg = bool(_ARG_REF.match(src))
    src_is_field = bool(_FIELD_REF.match(src))
    tgt_is_ret = tgt == _RETURN_REF
    tgt_is_field = bool(_FIELD_REF.match(tgt))

    if not (src_is_arg or src_is_field) or not (tgt_is_ret or tgt_is_field):
        raise _reject(
            "E-DSL-008",
            "propagate endpoints must be arg[..]/field[..]/this.x -> ret/field[..]",
            line=line,
            col=1,
            suggested_fix="use one of arg->ret, arg->field, field->ret, field->field",
            source_path=source_path,
        )
    source_ref: ArgRef | FieldRef = ArgRef(src) if src_is_arg else FieldRef(src)
    if tgt_is_ret:
        return Propagate(source_ref, "ret")
    return Propagate(source_ref, FieldRef(tgt))


def _parse_header(
    header: dict[str, str], *, source_path: str | None
) -> tuple[str, ClassName, tuple[Language, ...], EngineTag]:
    spec_id = header.get("id", "").strip().strip('"')
    class_raw = header.get("class", "").strip().strip('"')
    engine_raw = header.get("engine", "").strip().strip('"')
    langs_raw = header.get("languages", "").strip()

    if engine_raw not in DSL_ENGINES:
        raise _reject(
            "E-DSL-009",
            f"engine={engine_raw or '<missing>'} specs do not parse through the DSL "
            "— file under specs/oracle/",
            line=1,
            col=1,
            suggested_fix="a DSL spec must declare engine: ifds or engine: ide",
            source_path=source_path,
        )
    if class_raw not in CLASS_NAMES:
        raise _reject(
            "E-DSL-008",
            f"unknown class '{class_raw}'; expected one of {sorted(CLASS_NAMES)}",
            line=1,
            col=1,
            suggested_fix="use a pinned ClassName (DOC-DSL §2)",
            source_path=source_path,
        )
    langs = tuple(x.strip().strip('"') for x in langs_raw.strip("[]").split(",") if x.strip())
    bad = [x for x in langs if x not in LANGUAGES]
    if bad or not langs:
        raise _reject(
            "E-DSL-008",
            f"unknown or empty languages {bad or '[]'}; expected from {sorted(LANGUAGES)}",
            line=1,
            col=1,
            suggested_fix="declare languages as a list of pinned Language values",
            source_path=source_path,
        )
    # The membership checks above guarantee the Literal types; cast to record it.
    return (
        spec_id,
        cast(ClassName, class_raw),
        cast(tuple[Language, ...], langs),
        cast(EngineTag, engine_raw),
    )


def parse_spec(source_text: str, *, source_path: str | None = None) -> Spec:
    """Parse a DSL spec file (YAML header + clause list) into a frozen Spec.

    Returns a frozen :class:`Spec` on success. Raises :class:`DSLError` with one
    of the ``E-DSL-001..009`` codes on any rejection. Never returns a
    partially-valid Spec; failure is total (DOC-CMP-DET-01 §3.3, §7.3).
    """
    header: dict[str, str] = {}
    clauses: list[Clause] = []

    lines = source_text.splitlines()
    for idx, raw in enumerate(lines, start=1):
        # Strip trailing comments and surrounding whitespace.
        stripped = raw.split("#", 1)[0].rstrip()
        if not stripped.strip():
            continue

        # Header lines are ``key: value`` (no clause head paren before the colon).
        head_match = re.match(r"^\s*(id|class|languages|engine)\s*:\s*(.*)$", stripped)
        if head_match and "(" not in head_match.group(1):
            header[head_match.group(1)] = head_match.group(2).strip()
            continue

        clauses.append(_parse_clause(stripped.strip(), line=idx, source_path=source_path))

    spec_id, class_, langs, engine = _parse_header(header, source_path=source_path)

    if not clauses:
        raise _reject(
            "E-DSL-008",
            "spec has no clauses; expected at least one source/sink/sanitize/propagate",
            line=1,
            col=1,
            suggested_fix="add at least one DSL clause",
            source_path=source_path,
        )

    return Spec(
        id=spec_id,
        class_=class_,
        languages=langs,
        engine=engine,
        clauses=tuple(clauses),
    )
