"""Oracle (Semgrep) ``(file, line)`` -> slice-fingerprint — hermetic unit tests.

Covers :mod:`services.scan.oracle_fingerprint`: resolving a reported source
location to a CPG node, driving Algorithm 3 from a single-node witness, and the
honesty constraints that make the result meaningful rather than decorative.

The load-bearing control is
:func:`test_fingerprint_ignores_source_locations_entirely` — the executable form
of "the location is a LOOKUP KEY, never fingerprint input". If anyone ever mixes
``filename`` / ``line`` / ``column`` into the hash, that test goes red.

WHAT THESE FIXTURES DO AND DO NOT PROVE. They are small hand-written CPGs, so
they prove the *mechanism* (a one-node witness drives the backward cone; a
rename does not flip the hash; a dataflow change does; an unresolvable location
fails closed). They do NOT prove refactor-invariance on a real Joern-parsed
repository — that is corpus-scale evidence (CMP-CORP-REFAC-01) and is not
claimed here.

INVARIANCES ASSERTED: alpha-rename of a local, and file-move / package-rename.
Those are the two of Algorithm 3's five normalisation passes that do real work on
the shipped minimal CPG model; the formatting and topo-sort passes are documented
no-ops and the pure-extract pass deliberately normalises nothing (every extract
flips — the one-sided-safe choice). No test here claims otherwise.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from analysis.fingerprint import SliceRequest, compute_slice_fingerprint
from analysis.ordering import CPG, NodeId
from services.scan.oracle_fingerprint import (
    OracleSliceRequest,
    fingerprint_oracle_finding,
    locate_sink_node,
)

_FILE = "app/handlers.py"


@dataclass(frozen=True)
class _Loc:
    """Test-local stand-in for Track A's ``mapper.SourceLocation`` — same shape
    (``filename``/``line``/``column``, ``0`` = unknown), so these tests are green
    without the mapper branch."""

    filename: str
    line: int
    column: int


@dataclass(frozen=True)
class _Fixture:
    """A synthetic CPG plus its location side-table and the reported sink line."""

    cpg: CPG
    locations: dict[NodeId, _Loc]
    sink_line: int
    filename: str


def _taint_fixture(
    *,
    local_name: str = "raw",
    package: str = "com.old.app",
    sink_call: str = "db_execute",
    add_sanitizer: bool = False,
    line_offset: int = 0,
    filename: str = _FILE,
) -> _Fixture:
    """``handler(): src -> local -> [sanitizer] -> sink`` in one procedure.

    Mirrors the shape a Semgrep injection rule reports at the sink call site.
    Knobs:
      - ``local_name``    : rename a LOCAL — a refactor; must NOT flip.
      - ``package``       : package/FQN prefix — file-move; must NOT flip.
      - ``filename`` /
        ``line_offset``   : where the code sits — LOOKUP ONLY; must NOT flip.
      - ``sink_call``     : the sink call target — a genuine fix; MUST flip.
      - ``add_sanitizer`` : insert a sanitizer on the path — a genuine fix; MUST flip.
    """
    cpg = CPG()
    decl = f"{package}.handler"
    locations: dict[NodeId, _Loc] = {}

    def _at(node_id: NodeId, line: int, column: int) -> None:
        locations[node_id] = _Loc(filename=filename, line=line + line_offset, column=column)

    entry = cpg.add_node("METHOD", resolved_fqn=decl, enclosing_decl_fqn=decl)
    _at(entry, 1, 1)
    src = cpg.add_node(
        "CALL", operator_or_literal="request_args", enclosing_decl_fqn=decl, structural_path="0"
    )
    _at(src, 2, 11)
    local = cpg.add_node(
        "IDENTIFIER", operator_or_literal=local_name, enclosing_decl_fqn=decl, structural_path="1"
    )
    _at(local, 3, 5)

    prev = local
    sink_line = 4
    if add_sanitizer:
        san = cpg.add_node(
            "CALL", operator_or_literal="escape_sql", enclosing_decl_fqn=decl, structural_path="2"
        )
        _at(san, 4, 13)
        cpg.add_edge(prev, san, "CFG")
        prev = san
        sink_line = 5

    sink = cpg.add_node(
        "CALL", operator_or_literal=sink_call, enclosing_decl_fqn=decl, structural_path="3"
    )
    _at(sink, sink_line, 5)
    cpg.add_edge(entry, src, "CFG")
    cpg.add_edge(src, local, "CFG")
    cpg.add_edge(prev, sink, "CFG")
    return _Fixture(
        cpg=cpg,
        locations=locations,
        sink_line=sink_line + line_offset,
        filename=filename,
    )


def _fingerprint_hex(fx: _Fixture) -> str:
    """Fingerprint ``fx`` at its sink line; fail loudly if it does not resolve."""
    result = fingerprint_oracle_finding(
        fx.cpg, fx.locations, filename=fx.filename, line=fx.sink_line
    )
    assert result is not None, "fixture sink line must resolve"
    assert result.fingerprint_class == "strong", (
        "these fixtures must canonicalise within (B, T); an invariance proven on "
        "the weak fallback would be vacuous"
    )
    return result.slice_fingerprint.hex()


# ---------------------------------------------------------------------------
# The location is a lookup key, never fingerprint input
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_fingerprint_ignores_source_locations_entirely() -> None:
    """THE load-bearing control: identical code at a totally different position
    (different file name, every line shifted by 500) fingerprints IDENTICALLY.

    Hashing a location would manufacture a fake invariance — two scans agreeing
    because their line numbers agree — so this test is the executable form of the
    never-hash-location constraint. It goes red the moment any location field
    leaks into the hash.
    """
    here = _taint_fixture()
    moved = _taint_fixture(filename="src/v2/renamed_handlers.py", line_offset=500)

    # ANTI-VACUITY: the two location tables really are disjoint in content.
    assert here.locations != moved.locations
    assert here.sink_line != moved.sink_line
    assert here.filename != moved.filename
    # ...and the graphs the fingerprint sees are the same graph.
    assert here.cpg.nodes == moved.cpg.nodes

    assert _fingerprint_hex(here) == _fingerprint_hex(moved)


# ---------------------------------------------------------------------------
# Invariances that the implementation actually has
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_fingerprint_invariant_under_alpha_rename() -> None:
    """Renaming a local (``raw`` -> ``userSuppliedQuery``) does NOT change an
    oracle finding's fingerprint, and both sides are ``strong``.

    Anti-vacuity + mutation control: the pre-normalisation CPGs genuinely differ
    (the identifier token changed), so equal fingerprints prove Algorithm 3's
    alpha-rename pass fired rather than that the inputs were already equal.
    """
    base = _taint_fixture(local_name="raw")
    renamed = _taint_fixture(local_name="userSuppliedQuery")

    assert base.cpg.nodes != renamed.cpg.nodes
    assert _fingerprint_hex(base) == _fingerprint_hex(renamed)


@pytest.mark.unit
def test_fingerprint_invariant_under_file_move_and_package_rename() -> None:
    """Moving the file and renaming its package (``com.old.app`` ->
    ``com.new.services``, plus a new path) does NOT change the fingerprint —
    Algorithm 3's FQN-normalisation pass. Both sides ``strong``."""
    base = _taint_fixture(package="com.old.app", filename="app/handlers.py")
    moved = _taint_fixture(package="com.new.services", filename="services/handlers.py")

    assert base.cpg.nodes != moved.cpg.nodes
    assert _fingerprint_hex(base) == _fingerprint_hex(moved)


# ---------------------------------------------------------------------------
# A genuine fix FLIPS the fingerprint
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_fingerprint_flips_when_the_sink_changes() -> None:
    """Repointing the sink at a different call target (``db_execute`` ->
    ``db_execute_parameterized``) is a real change and MUST change the identity —
    the finding is not "the same finding" any more."""
    vulnerable = _taint_fixture(sink_call="db_execute")
    fixed = _taint_fixture(sink_call="db_execute_parameterized")

    assert _fingerprint_hex(vulnerable) != _fingerprint_hex(fixed)


@pytest.mark.unit
def test_fingerprint_flips_when_a_sanitizer_is_added() -> None:
    """Inserting a sanitizer into the dataflow reaching the sink — the canonical
    "fix" — MUST change the fingerprint, so the fixed code cannot be silently
    matched against (and suppressed by) the vulnerable baseline."""
    vulnerable = _taint_fixture()
    sanitized = _taint_fixture(add_sanitizer=True)

    assert _fingerprint_hex(vulnerable) != _fingerprint_hex(sanitized)


# ---------------------------------------------------------------------------
# Unresolvable locations fail closed (None, never a crash, never a wrong node)
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize(
    ("filename", "line"),
    [
        ("app/handlers.py", 9999),  # right file, no node on that line
        ("app/nonexistent.py", 4),  # unknown file
        ("app/handlers.py", 0),  # 0 = unknown-line sentinel
        ("app/handlers.py", -1),  # nonsense line
        ("", 4),  # unknown filename
        ("handlers.py", 4),  # basename only — no path normalisation, no match
    ],
)
def test_unresolvable_location_returns_none(filename: str, line: int) -> None:
    """An unresolvable ``file:line`` yields ``None`` from both entry points — no
    exception, and above all no nearest-line / path-suffix guess, which would
    attach one finding's identity to another finding's code."""
    fx = _taint_fixture()

    assert locate_sink_node(fx.cpg, fx.locations, filename=filename, line=line) is None
    assert fingerprint_oracle_finding(fx.cpg, fx.locations, filename=filename, line=line) is None


@pytest.mark.unit
def test_location_for_a_node_absent_from_the_cpg_is_never_selected() -> None:
    """A side-table entry pointing at an id the CPG does not contain is skipped,
    so the returned node can never trip ``WitnessNotInCPG`` downstream."""
    fx = _taint_fixture()
    ghost = NodeId(len(fx.cpg.nodes) + 42)
    locations = dict(fx.locations)
    locations[ghost] = _Loc(filename=fx.filename, line=fx.sink_line, column=1)

    picked = locate_sink_node(fx.cpg, locations, filename=fx.filename, line=fx.sink_line)
    assert picked is not None
    assert picked != ghost
    # And it still fingerprints (the ghost id would have raised WitnessNotInCPG).
    assert (
        fingerprint_oracle_finding(fx.cpg, locations, filename=fx.filename, line=fx.sink_line)
        is not None
    )


# ---------------------------------------------------------------------------
# locate_sink_node: deterministic + documented selection order
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_locate_sink_node_is_deterministic() -> None:
    """Same inputs ⇒ same node, including under a different ``Mapping``
    iteration order (the sort key is total, so dict insertion order cannot
    influence the choice)."""
    fx = _taint_fixture()
    forward = fx.locations
    reversed_order = dict(reversed(list(fx.locations.items())))
    assert list(forward) != list(reversed_order), "orders must actually differ"

    first = locate_sink_node(fx.cpg, forward, filename=fx.filename, line=fx.sink_line)
    again = locate_sink_node(fx.cpg, forward, filename=fx.filename, line=fx.sink_line)
    shuffled = locate_sink_node(fx.cpg, reversed_order, filename=fx.filename, line=fx.sink_line)

    assert first is not None
    assert first == again == shuffled


@pytest.mark.unit
def test_locate_sink_node_prefers_a_call_on_the_line() -> None:
    """A CALL on the reported line beats a non-CALL on the same line, even when
    the non-CALL sits earlier in the line and earlier in the graph."""
    cpg = CPG()
    ident = cpg.add_node("IDENTIFIER", operator_or_literal="query")
    call = cpg.add_node("CALL", operator_or_literal="db_execute")
    locations = {
        ident: _Loc(filename=_FILE, line=7, column=2),
        call: _Loc(filename=_FILE, line=7, column=40),
    }

    assert locate_sink_node(cpg, locations, filename=_FILE, line=7) == call


@pytest.mark.unit
def test_locate_sink_node_prefers_the_earliest_known_column() -> None:
    """Among same-kind candidates on the line: the earliest column wins, and a
    node carrying the ``column == 0`` unknown sentinel loses to any node with a
    real column."""
    cpg = CPG()
    unknown_col = cpg.add_node("CALL", operator_or_literal="a")
    late = cpg.add_node("CALL", operator_or_literal="b")
    early = cpg.add_node("CALL", operator_or_literal="c")
    locations = {
        unknown_col: _Loc(filename=_FILE, line=7, column=0),
        late: _Loc(filename=_FILE, line=7, column=30),
        early: _Loc(filename=_FILE, line=7, column=9),
    }

    assert locate_sink_node(cpg, locations, filename=_FILE, line=7) == early

    # With no real column anywhere, the unknown-column node is still selected
    # deterministically (lowest node id) rather than dropped.
    only_unknown = {
        late: _Loc(filename=_FILE, line=8, column=0),
        unknown_col: _Loc(filename=_FILE, line=8, column=0),
    }
    assert locate_sink_node(cpg, only_unknown, filename=_FILE, line=8) == unknown_col


# ---------------------------------------------------------------------------
# Port + purity + honest weak labelling
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_oracle_slice_request_satisfies_the_slice_request_port() -> None:
    """``OracleSliceRequest`` is accepted by Algorithm 3 structurally — an oracle
    finding never needs to masquerade as a ``solver.Finding`` (whose
    ``origin``/``engine`` literals are the INV-1 type-level honesty guard)."""
    fx = _taint_fixture()
    sink = locate_sink_node(fx.cpg, fx.locations, filename=fx.filename, line=fx.sink_line)
    assert sink is not None

    request: SliceRequest = OracleSliceRequest(witness=(sink,))
    direct = compute_slice_fingerprint(request, fx.cpg)

    assert direct.slice_fingerprint.hex() == _fingerprint_hex(fx)
    assert direct.cpg_order_hash_annotation == "canonical iff fingerprint_class = strong"


@pytest.mark.unit
def test_fingerprint_oracle_finding_is_pure() -> None:
    """Same ``(cpg, locations, filename, line)`` ⇒ identical result. No I/O, no
    global state."""
    fx = _taint_fixture()
    first = fingerprint_oracle_finding(
        fx.cpg, fx.locations, filename=fx.filename, line=fx.sink_line
    )
    second = fingerprint_oracle_finding(
        fx.cpg, fx.locations, filename=fx.filename, line=fx.sink_line
    )
    assert first is not None and second is not None
    assert first.slice_fingerprint == second.slice_fingerprint
    assert first.fingerprint_class == second.fingerprint_class


def _symmetric_fixture() -> _Fixture:
    """``src -> {relay, relay} -> sink`` — two 2-WL-indistinguishable CALL arms
    that both reach the sink, so the backward cone carries a residual symmetric
    class that only individualisation-refinement can break. Under a tight budget
    that forces the ``weak`` fallback; under the full budget it resolves
    ``strong`` (so the weakness is genuinely budget-driven, not fixture-driven).
    """
    cpg = CPG()
    decl = "s.main"
    entry = cpg.add_node("METHOD", resolved_fqn=decl, enclosing_decl_fqn=decl)
    src = cpg.add_node("CALL", operator_or_literal="request_args", enclosing_decl_fqn=decl)
    a = cpg.add_node("CALL", operator_or_literal="relay", enclosing_decl_fqn=decl)
    b = cpg.add_node("CALL", operator_or_literal="relay", enclosing_decl_fqn=decl)
    sink = cpg.add_node("CALL", operator_or_literal="db_execute", enclosing_decl_fqn=decl)
    cpg.add_edge(entry, src, "CFG")
    cpg.add_edge(src, a, "CFG")
    cpg.add_edge(src, b, "CFG")
    cpg.add_edge(a, sink, "CFG")
    cpg.add_edge(b, sink, "CFG")
    locations = {
        entry: _Loc(filename=_FILE, line=1, column=1),
        src: _Loc(filename=_FILE, line=2, column=11),
        a: _Loc(filename=_FILE, line=3, column=5),
        b: _Loc(filename=_FILE, line=4, column=5),
        sink: _Loc(filename=_FILE, line=5, column=5),
    }
    return _Fixture(cpg=cpg, locations=locations, sink_line=5, filename=_FILE)


@pytest.mark.unit
def test_budget_exhaustion_yields_an_honest_weak_class() -> None:
    """Forcing ``(B, T)`` exhaustion returns ``weak`` — never an exception and
    never a fake ``strong`` (INV-5 self-label truthfulness). A ``weak``
    fingerprint is a same-source identity only and must not be auto-suppressed
    across a refactor.

    ANTI-VACUITY: the same fixture under the full budget resolves ``strong``, so
    the ``weak`` verdict is caused by the budget, not by the fixture.
    """
    fx = _symmetric_fixture()
    starved = fingerprint_oracle_finding(
        fx.cpg, fx.locations, filename=fx.filename, line=fx.sink_line, B=1
    )
    full = fingerprint_oracle_finding(fx.cpg, fx.locations, filename=fx.filename, line=fx.sink_line)

    assert starved is not None and full is not None
    assert starved.fingerprint_class == "weak"
    assert starved.budget_exhausted is True
    assert len(starved.slice_fingerprint) == 32
    assert full.fingerprint_class == "strong"
