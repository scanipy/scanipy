"""CMP-SNAP-03 — ``CW-DETECT`` closed-world precondition detector.

Implementation contract: ``docs/components/DOC-CMP-SNAP-03.md``.
Canonical INV-4 exposition: ``docs/cross-cutting/DOC-INV.md §6.2.a``.

``CW-DETECT`` is the **INV-4 owner** for Algorithm 1's closed-world precondition.
It is a one-sided conservative over-approximation of the undecidable property
"does this snapshot contain a reflection / dynamic-dispatch construct that can
reach analyzed code?". Its required soundness direction is **zero false
negatives**: any source bearing a reachable reflection construct MUST yield a
``not-closed-world`` verdict (represented at this level as ``degraded``). False
positives are permitted — they cost performance, never correctness.

The detector is a pure, deterministic function of ``(source_tree_root,
language_mix, parent_snapshot)``: same inputs ⇒ byte-identical verdict (the
``decided_at`` clock is injectable so callers control non-determinism). It does
NOT emit findings and does NOT touch ``origin`` / ``S_version`` / ``env_digest``
/ ``cpg_order_hash`` (DOC-CMP-SNAP-03 §8) — those live on the finding path, not
the routing-oracle path.

Safe-direction contract (load-bearing, DOC-CMP-SNAP-03 §7): for every input
where the analysis cannot *prove* the absence of reflection, the verdict is
``degraded``. There is no "best-effort closed-world" fast path. Uncertainty —
an unsupported language, an unreadable/unparseable file, an internal error — is
reflection by construction.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

# Semver of this detector. Sealed into provenance (precondition_status.json) so
# CMP-SNAP-04 can identify which CW version produced a verdict on a
# disagreement (DOC-CMP-SNAP-03 §8). Bump on any change to detection behaviour.
CW_DETECT_VERSION = "0.1.1"

Verdict = Literal["closed-world", "degraded", "full-reparse"]
Confidence = Literal["high", "uncertain"]

# DOC-CMP-SNAP-03 §3 ReflectionKind enumeration (verbatim membership).
ReflectionKind = Literal[
    "java-class-forname",
    "java-method-invoke",
    "java-proxy-newproxy",
    "java-spring-dynamic-proxy",
    "python-import-dunder",
    "python-getattr",
    "python-eval-exec",
    "ruby-send",
    "ruby-method-missing",
    "ruby-define-method",
    "php-variable-function",
    "php-call-user-func",
    "js-require-dynamic",
    "js-function-constructor",
    "js-eval",
    "go-reflect-call",
    "structural-uncertainty",
]

# Language → set of file extensions. A language present in language_mix but
# absent from this map is unsupported ⇒ fail-closed (DOC-CMP-SNAP-03 §3.2).
_LANG_EXTENSIONS: dict[str, frozenset[str]] = {
    "java": frozenset({".java"}),
    "python": frozenset({".py", ".pyi"}),
    "ruby": frozenset({".rb"}),
    "php": frozenset({".php", ".phtml"}),
    "js": frozenset({".js", ".jsx", ".mjs", ".cjs"}),
    "ts": frozenset({".ts", ".tsx"}),
    "go": frozenset({".go"}),
}

# The set of languages CW-DETECT has a one-sided sub-detector for. Anything
# else is structural uncertainty by construction.
SUPPORTED_LANGUAGES: frozenset[str] = frozenset(_LANG_EXTENSIONS.keys())

_EXT_TO_LANG: dict[str, str] = {
    ext: lang for lang, exts in _LANG_EXTENSIONS.items() for ext in exts
}

# Provably-inert extensions: documentation, images, data, lockfiles, VCS/editor
# meta. A file that is NEITHER a scanned source language NOR in this allowlist
# is treated as structural uncertainty (⇒ degraded) — the INV-4 safe direction
# (CLAR-SNAP-01, ratified by the Security Analyst). Config formats
# (.xml/.yaml/.yml/.properties/.toml/.ini/.cfg/.json, and extensionless files
# such as META-INF/services entries) are deliberately ABSENT: they can wire
# runtime reflection (Spring AOP, service loaders, entry-points) and MUST demote
# to `degraded` until a dedicated config sub-detector exists. Over-demotion (FP)
# is acceptable; a false `closed-world` (FN) is forbidden.
_INERT_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".md",
        ".markdown",
        ".rst",
        ".txt",
        ".adoc",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".svg",
        ".ico",
        ".webp",
        ".bmp",
        ".pdf",
        ".csv",
        ".tsv",
        ".lock",
        ".gitignore",
        ".gitattributes",
        ".editorconfig",
        ".dockerignore",
    }
)


@dataclass(frozen=True)
class ReflectionSite:
    """A single reflection / dynamic-dispatch evidence site (DOC §3)."""

    file: str
    line: int
    kind: ReflectionKind
    snippet: str  # 1-line evidence string


@dataclass(frozen=True)
class Snapshot:
    """Minimal parent-snapshot view CW-DETECT reads (read-only).

    The cached reflection-site index can only ADD sites (carry forward a known
    site for an unchanged file); it can never subtract them or bias the verdict
    toward ``closed-world`` (DOC-CMP-SNAP-03 §4.1, §6.2 property 3).
    """

    cached_reflection_sites: tuple[ReflectionSite, ...] = ()


@dataclass(frozen=True)
class CwDetectRequest:
    """Input to ``detect`` (DOC-CMP-SNAP-03 §3)."""

    source_tree_root: str
    language_mix: tuple[str, ...] = ()
    parent_snapshot: Snapshot | None = None


@dataclass(frozen=True)
class CwDetectVerdict:
    """Output of ``detect`` (DOC-CMP-SNAP-03 §3).

    ``verdict`` is one of ``closed-world | degraded``. ``CW-DETECT`` never emits
    ``full-reparse`` — that demotion is owned by CMP-SNAP-02 (DOC §3.1). The
    ``full-reparse`` member exists in the type only because the shared
    precondition-status enum carries all three values.
    """

    verdict: Verdict
    cw_detect_version: str
    reflection_sites: tuple[ReflectionSite, ...]
    decided_at: str  # iso-8601
    confidence: Confidence


# ---------------------------------------------------------------------------
# Per-language one-sided sub-detectors.
#
# Each pattern is a CONSERVATIVE over-approximation: it is permitted (indeed
# expected) to over-match (false positives cost performance), but it must never
# miss a construct of its kind (a false negative is a release blocker —
# AC-SNAP-03a). When in doubt, match. Patterns are compiled once at import.
# ---------------------------------------------------------------------------

# (kind, compiled-pattern) tuples, evaluated per matching line.
_LANG_PATTERNS: dict[str, tuple[tuple[ReflectionKind, re.Pattern[str]], ...]] = {
    "java": (
        # Class.forName(...) and any *.forName( reflective load.
        ("java-class-forname", re.compile(r"\bforName\s*\(")),
        # java.lang.reflect.Method#invoke, Constructor#newInstance, getMethod, etc.
        (
            "java-method-invoke",
            re.compile(
                r"\b(?:invoke|getMethod|getDeclaredMethod|getDeclaredMethods|"
                r"getMethods|newInstance|getConstructor|getDeclaredConstructor|"
                r"getField|getDeclaredField|setAccessible)\s*\("
            ),
        ),
        # java.lang.reflect.Proxy.newProxyInstance(...)
        ("java-proxy-newproxy", re.compile(r"\bnewProxyInstance\s*\(")),
        # Spring dynamic proxy / AOP surfaces (interface-dispatch over open hierarchy).
        (
            "java-spring-dynamic-proxy",
            re.compile(
                r"\b(?:ProxyFactory|ProxyFactoryBean|getProxy|createAopProxy|"
                r"AopProxy|ScopedProxyMode|@EnableAspectJAutoProxy)\b"
            ),
        ),
    ),
    "python": (
        # __import__(...) and importlib dynamic import.
        (
            "python-import-dunder",
            re.compile(r"(?:\b__import__\s*\(|\bimportlib\.import_module\s*\()"),
        ),
        # getattr / setattr / hasattr — attribute-name-driven dynamic dispatch.
        (
            "python-getattr",
            re.compile(r"\b(?:getattr|setattr|delattr|hasattr|vars|globals|locals)\s*\("),
        ),
        # eval / exec / compile.
        ("python-eval-exec", re.compile(r"\b(?:eval|exec|compile)\s*\(")),
    ),
    "ruby": (
        # send / public_send / __send__.
        ("ruby-send", re.compile(r"\.(?:public_send|__send__|send)\b|\bsend\s*\(")),
        # method_missing / respond_to_missing? hooks.
        ("ruby-method-missing", re.compile(r"\b(?:method_missing|respond_to_missing\?)\b")),
        # define_method / instance_eval / class_eval / const_get.
        (
            "ruby-define-method",
            re.compile(
                r"\b(?:define_method|instance_eval|class_eval|module_eval|"
                r"const_get|instance_variable_get|instance_variable_set)\b"
            ),
        ),
    ),
    "php": (
        # $var() variable-function call and $obj->$var() variable method.
        (
            "php-variable-function",
            re.compile(r"\$[A-Za-z_]\w*\s*\(|->\s*\$[A-Za-z_]\w*\s*\("),
        ),
        # call_user_func / call_user_func_array / ReflectionClass / eval.
        (
            "php-call-user-func",
            re.compile(
                r"\b(?:call_user_func(?:_array)?|ReflectionClass|ReflectionMethod|"
                r"forward_static_call(?:_array)?|eval)\s*\(|\bnew\s+Reflection"
            ),
        ),
    ),
    "js": (
        # Dynamic require. Safe direction (INV-4, zero-FN): treat a require argument
        # as static ONLY when it is a single plain string literal immediately followed
        # by ')'. Everything else — bare identifier, string concatenation
        # (require("pa" + "th")), template-literal interpolation (require(`${x}`)),
        # function calls — is not-closed-world. FP is permitted; a missed dynamic
        # require is a release blocker.
        (
            "js-require-dynamic",
            re.compile(r"""\brequire\s*\(\s*(?!(?:'[^'\n]*'|"[^"\n]*")\s*\))"""),
        ),
        # new Function(...) constructor.
        ("js-function-constructor", re.compile(r"\bnew\s+Function\s*\(")),
        # eval(...) and indirect eval; setTimeout/setInterval with string body.
        ("js-eval", re.compile(r"\beval\s*\(|\bFunction\s*\(")),
    ),
    "ts": (
        (
            "js-require-dynamic",
            re.compile(r"""\brequire\s*\(\s*(?!(?:'[^'\n]*'|"[^"\n]*")\s*\))"""),
        ),
        ("js-function-constructor", re.compile(r"\bnew\s+Function\s*\(")),
        ("js-eval", re.compile(r"\beval\s*\(|\bFunction\s*\(")),
    ),
    "go": (
        # reflect.* dynamic call / value construction.
        (
            "go-reflect-call",
            re.compile(r"\breflect\s*\.\s*(?:ValueOf|TypeOf|New|Call|MakeFunc|Indirect|NewAt)\b"),
        ),
    ),
}


def _detect_language(path: Path) -> str | None:
    """Map a file to a language by extension; ``None`` if not source we route on."""
    return _EXT_TO_LANG.get(path.suffix.lower())


def _scan_text(rel_path: str, lang: str, text: str) -> list[ReflectionSite]:
    """One-sided per-language scan of a file's text.

    Conservative: matches per line, records the first matching kind per line per
    pattern. Over-matching is acceptable (FP permitted); missing a construct is
    forbidden (FN is a release blocker).
    """
    sites: list[ReflectionSite] = []
    patterns = _LANG_PATTERNS.get(lang, ())
    for lineno, raw_line in enumerate(text.splitlines(), start=1):
        for kind, pattern in patterns:
            if pattern.search(raw_line):
                sites.append(
                    ReflectionSite(
                        file=rel_path,
                        line=lineno,
                        kind=kind,
                        snippet=raw_line.strip()[:200],
                    )
                )
    return sites


def _iter_source_files(root: Path) -> Iterable[Path]:
    """Deterministically walk the source tree (sorted) yielding regular files."""
    if root.is_file():
        yield root
        return
    yield from sorted(p for p in root.rglob("*") if p.is_file())


def _default_clock() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class _ScanState:
    sites: list[ReflectionSite] = field(default_factory=list)
    confidence: Confidence = "high"


def _add_uncertainty(state: _ScanState, rel_path: str) -> None:
    """Fail-closed: record structural uncertainty for a file we cannot prove."""
    state.sites.append(
        ReflectionSite(
            file=rel_path,
            line=0,
            kind="structural-uncertainty",
            snippet="",
        )
    )
    state.confidence = "uncertain"


def detect(
    req: CwDetectRequest,
    *,
    clock: Callable[[], str] = _default_clock,
) -> CwDetectVerdict:
    """Decide the closed-world precondition for a snapshot (DOC-CMP-SNAP-03 §6.2).

    Returns ``closed-world`` ONLY when every source file was parseable, in a
    supported language, and contained no reflection construct. Any uncertainty
    (unsupported language, unreadable file, internal error) is recorded as a
    ``structural-uncertainty`` site and forces ``degraded`` — the INV-4 safe
    direction. Reflection sites likewise force ``degraded``.

    The function is pure and deterministic given ``clock``; the default clock is
    the only source of run-to-run variation (the verdict/sites are stable).
    """
    state = _ScanState()
    root = Path(req.source_tree_root)

    # A language declared in language_mix but unsupported by CW-DETECT is
    # structural uncertainty at the tree level (DOC §3.2 LanguageNotSupported):
    # we cannot prove the absence of reflection in a language we do not scan.
    for lang in req.language_mix:
        if lang not in SUPPORTED_LANGUAGES:
            _add_uncertainty(state, f"<language:{lang}>")

    if not root.exists():
        # We cannot prove anything about a tree we cannot read. Fail-closed.
        _add_uncertainty(state, req.source_tree_root)

    for src_file in _iter_source_files(root) if root.exists() else ():
        try:
            rel_path = str(src_file.relative_to(root)) if root.is_dir() else str(src_file)
        except ValueError:  # pragma: no cover - defensive; src_file is under root
            rel_path = str(src_file)

        file_lang = _detect_language(src_file)
        if file_lang is None:
            # INV-4 safe direction (CLAR-SNAP-01, Security-Analyst-ratified):
            # only files we can affirmatively account for — a scanned source
            # language OR a provably-inert extension — may leave the verdict at
            # `closed-world`. Anything else (config formats that can wire runtime
            # reflection: .xml Spring AOP, META-INF/services, .properties, .yaml,
            # .toml, ...; or unknown / extensionless files) is structural
            # uncertainty ⇒ degraded. A false `closed-world` here would be a
            # forbidden false negative; over-demotion (FP) is acceptable.
            if src_file.suffix.lower() not in _INERT_EXTENSIONS:
                _add_uncertainty(state, rel_path)
            continue

        try:
            text = src_file.read_text(encoding="utf-8", errors="strict")
        except (OSError, UnicodeDecodeError):
            # Unreadable / unparseable file ⇒ structural uncertainty (fail-closed).
            _add_uncertainty(state, rel_path)
            continue

        try:
            state.sites.extend(_scan_text(rel_path, file_lang, text))
        except Exception:  # any sub-detector failure fails closed (DOC §3.2)
            _add_uncertainty(state, rel_path)

    # Read-only carry-forward from the parent snapshot's cached index. Can only
    # ADD sites; never subtracts and never biases toward closed-world.
    if req.parent_snapshot is not None:
        state.sites.extend(req.parent_snapshot.cached_reflection_sites)

    decided_at = clock()
    sites = tuple(state.sites)

    if sites:
        return CwDetectVerdict(
            verdict="degraded",
            cw_detect_version=CW_DETECT_VERSION,
            reflection_sites=sites,
            decided_at=decided_at,
            confidence=state.confidence,
        )
    if state.confidence == "uncertain":
        # Defensive: uncertainty always carries a site, so this is unreachable
        # in normal flow. Still fail-closed if we ever reach it.
        return CwDetectVerdict(
            verdict="degraded",
            cw_detect_version=CW_DETECT_VERSION,
            reflection_sites=(ReflectionSite("", 0, "structural-uncertainty", ""),),
            decided_at=decided_at,
            confidence="uncertain",
        )
    return CwDetectVerdict(
        verdict="closed-world",
        cw_detect_version=CW_DETECT_VERSION,
        reflection_sites=(),
        decided_at=decided_at,
        confidence="high",
    )


# ---------------------------------------------------------------------------
# AC-SNAP-03b — combined TP+FP routing-rate measurement (economics signal).
#
# NOT a release blocker. Measures the fraction of a representative repo
# population that CW-DETECT routes not-closed-world (TP + FP together) and emits
# it as a numeric report artifact. The ≤15% figure is an economics target; this
# function only measures + surfaces the rate. FN tolerance is governed
# separately by AC-SNAP-03a (which is zero). DOC-CMP-SNAP-03 §9.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RoutingRateReport:
    """Numeric report artifact for AC-SNAP-03b."""

    total: int
    routed_not_closed_world: int
    combined_tp_fp_rate: float


def measure_routing_rate(
    requests: Iterable[CwDetectRequest],
    *,
    clock: Callable[[], str] = _default_clock,
) -> RoutingRateReport:
    """Measure the combined TP+FP not-closed-world routing rate over a population.

    Returns a numeric report; the caller decides whether the rate clears the
    ≤15% economics target. A false negative is never tolerated here (that is
    AC-SNAP-03a's job) — this function only measures routing economics.
    """
    total = 0
    routed = 0
    for req in requests:
        total += 1
        if detect(req, clock=clock).verdict != "closed-world":
            routed += 1
    rate = (routed / total) if total else 0.0
    return RoutingRateReport(
        total=total,
        routed_not_closed_world=routed,
        combined_tp_fp_rate=rate,
    )
