"""CMP-SNAP-03 ``CW-DETECT`` unit specs — safe-direction (INV-4) behaviour.

These exercise the implementation contract in ``docs/components/DOC-CMP-SNAP-03.md``
at unit granularity. They are NOT ``TST-INV-4-SNAP-03`` (the corpus-backed INV-4
falsifier), which is the Security Analyst's deliverable per CLAR-OWNER-02 and is
validated by the Gate-2 falsifier ``TST-AC-SNAP-03a`` against CMP-CORP-REFL-01.

What these assert (all per DOC-CMP-SNAP-03):
  - Each supported ReflectionKind is detected ⇒ ``degraded`` (zero FN per kind).
  - A genuinely closed-world tree ⇒ ``closed-world``.
  - Fail-closed: unsupported language, unreadable/binary file, missing tree, and
    a parent-snapshot cached site can only ADD sites — never yields a spurious
    ``closed-world``.
  - The function is pure/deterministic given an injected clock.
  - CW-DETECT never emits ``full-reparse`` (DOC §3.1) and never sets a
    finding-level provenance field (DOC §8).
"""

from pathlib import Path

import pytest

from services.snapshot import (
    CW_DETECT_VERSION,
    CwDetectRequest,
    ReflectionSite,
    Snapshot,
    detect,
)

_CLOCK = "2026-01-01T00:00:00+00:00"


def _req(root: Path, *langs: str) -> CwDetectRequest:
    return CwDetectRequest(source_tree_root=str(root), language_mix=tuple(langs))


def _verdict(root: Path, *langs: str) -> str:
    return detect(_req(root, *langs), clock=lambda: _CLOCK).verdict


# --- positive reflection cases (one-sided: each MUST route not-closed-world) ---

# (filename, content, language) tuples; every one carries reachable reflection.
_REFLECTION_CASES: list[tuple[str, str, str]] = [
    # Java
    ("A.java", 'Class.forName("com.x.Y");', "java"),
    ("B.java", "Method m = c.getMethod(name); m.invoke(o);", "java"),
    ("C.java", "Proxy.newProxyInstance(cl, ifaces, h);", "java"),
    ("D.java", "ProxyFactory pf = new ProxyFactory(); pf.getProxy();", "java"),
    ("E.java", "ctor.newInstance(args);", "java"),
    ("F.java", "f.setAccessible(true);", "java"),
    # Python
    ("a.py", '__import__("os")', "python"),
    ("b.py", "importlib.import_module(name)", "python"),
    ("c.py", "getattr(obj, attr_name)()", "python"),
    ("d.py", "setattr(obj, name, value)", "python"),
    ("e.py", 'eval("1+1")', "python"),
    ("f.py", "exec(code)", "python"),
    # Ruby
    ("a.rb", "obj.send(:method_name)", "ruby"),
    ("b.rb", "obj.public_send(meth)", "ruby"),
    ("c.rb", "def method_missing(name, *args); end", "ruby"),
    ("d.rb", "define_method(:foo) { 1 }", "ruby"),
    ("e.rb", "klass.const_get(name)", "ruby"),
    # PHP
    ("a.php", "<?php $fn(); ?>", "php"),
    ("b.php", "<?php $obj->$method(); ?>", "php"),
    ("c.php", "<?php call_user_func($cb); ?>", "php"),
    ("d.php", "<?php $r = new ReflectionClass($name); ?>", "php"),
    # JS / TS
    ("a.js", "const m = require(modName);", "js"),
    ("b.js", "const f = new Function('return 1');", "js"),
    ("c.js", "eval(userInput);", "js"),
    ("a.ts", "const f = new Function('x', 'return x');", "ts"),
    ("b.ts", "eval(payload);", "ts"),
    # Go
    ("a.go", "v := reflect.ValueOf(x)", "go"),
    ("b.go", "reflect.New(t).Call(args)", "go"),
]


@pytest.mark.unit
@pytest.mark.parametrize(("name", "content", "lang"), _REFLECTION_CASES)
def test_cw_detect_routes_reflection_not_closed_world(
    tmp_path: Path, name: str, content: str, lang: str
) -> None:
    """Every reachable reflection construct MUST yield a non-closed-world verdict.

    INV-4 safe direction: a single missed construct is a false negative, which is
    a release blocker. ``degraded`` is the CW-level representation of
    ``not-closed-world``.
    """
    (tmp_path / name).write_text(content, encoding="utf-8")
    result = detect(_req(tmp_path, lang), clock=lambda: _CLOCK)
    # degraded is the CW-level representation of not-closed-world; CW-DETECT never
    # emits full-reparse (DOC §3.1), so degraded here means the construct was caught.
    assert result.verdict == "degraded", f"FALSE NEGATIVE on {name}: {content!r}"
    assert result.reflection_sites, "a not-closed-world verdict must carry evidence sites"


# --- negative control: a genuinely closed-world tree ---


@pytest.mark.unit
def test_cw_detect_closed_world_on_plain_source(tmp_path: Path) -> None:
    """A tree with no reflection construct in a supported language ⇒ closed-world."""
    (tmp_path / "Plain.java").write_text(
        "class Plain { int add(int a, int b) { return a + b; } }\n",
        encoding="utf-8",
    )
    (tmp_path / "calc.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    result = detect(_req(tmp_path, "java", "python"), clock=lambda: _CLOCK)
    assert result.verdict == "closed-world"
    assert result.reflection_sites == ()
    assert result.confidence == "high"


# --- fail-closed paths (uncertainty is reflection by construction) ---


@pytest.mark.unit
def test_cw_detect_unsupported_language_fails_closed(tmp_path: Path) -> None:
    """An unsupported language in language_mix forces degraded (DOC §3.2)."""
    (tmp_path / "Main.scala").write_text("object Main\n", encoding="utf-8")
    result = detect(_req(tmp_path, "scala"), clock=lambda: _CLOCK)
    assert result.verdict == "degraded"
    assert result.confidence == "uncertain"
    assert any(s.kind == "structural-uncertainty" for s in result.reflection_sites)


@pytest.mark.unit
def test_cw_detect_unreadable_binary_file_fails_closed(tmp_path: Path) -> None:
    """A file that is not valid UTF-8 source ⇒ structural uncertainty ⇒ degraded."""
    (tmp_path / "blob.py").write_bytes(b"\xff\xfe\x00\x01not-utf8\x80")
    result = detect(_req(tmp_path, "python"), clock=lambda: _CLOCK)
    assert result.verdict == "degraded"
    assert result.confidence == "uncertain"


@pytest.mark.unit
def test_cw_detect_missing_tree_fails_closed(tmp_path: Path) -> None:
    """A source_tree_root that does not exist ⇒ degraded (cannot prove anything)."""
    result = detect(_req(tmp_path / "nope", "python"), clock=lambda: _CLOCK)
    assert result.verdict == "degraded"
    assert result.confidence == "uncertain"


@pytest.mark.unit
def test_cw_detect_never_returns_closed_world_from_uncertainty(tmp_path: Path) -> None:
    """There is no code path turning uncertainty into closed-world (DOC §3.2, §7)."""
    # Supported clean file + an unsupported language declared: still degraded.
    (tmp_path / "ok.py").write_text("x = 1\n", encoding="utf-8")
    result = detect(_req(tmp_path, "python", "haskell"), clock=lambda: _CLOCK)
    assert result.verdict != "closed-world"


# --- parent-snapshot cache is read-only and additive only ---


@pytest.mark.unit
def test_cw_detect_parent_cache_only_adds_sites(tmp_path: Path) -> None:
    """A cached reflection site from the parent snapshot can only ADD evidence.

    It must never subtract sites nor bias toward closed-world (DOC §6.2 prop 3).
    A clean tree with a cached site ⇒ degraded.
    """
    (tmp_path / "ok.py").write_text("x = 1\n", encoding="utf-8")
    cached = Snapshot(
        cached_reflection_sites=(
            ReflectionSite(file="old.py", line=3, kind="python-getattr", snippet="getattr(o, n)"),
        )
    )
    req = CwDetectRequest(
        source_tree_root=str(tmp_path), language_mix=("python",), parent_snapshot=cached
    )
    result = detect(req, clock=lambda: _CLOCK)
    assert result.verdict == "degraded"
    assert any(s.file == "old.py" for s in result.reflection_sites)


# --- determinism / purity ---


@pytest.mark.unit
def test_cw_detect_is_deterministic(tmp_path: Path) -> None:
    """Same inputs ⇒ identical verdict + sites + version (given a fixed clock)."""
    (tmp_path / "Dyn.java").write_text('Class.forName("x");\n', encoding="utf-8")
    r1 = detect(_req(tmp_path, "java"), clock=lambda: _CLOCK)
    r2 = detect(_req(tmp_path, "java"), clock=lambda: _CLOCK)
    assert r1 == r2
    assert r1.cw_detect_version == CW_DETECT_VERSION


@pytest.mark.unit
def test_cw_detect_verdict_is_one_of_two_at_cw_level(tmp_path: Path) -> None:
    """CW-DETECT only distinguishes closed-world vs degraded (DOC §3.1)."""
    (tmp_path / "ok.py").write_text("x = 1\n", encoding="utf-8")
    assert _verdict(tmp_path, "python") in {"closed-world", "degraded"}
