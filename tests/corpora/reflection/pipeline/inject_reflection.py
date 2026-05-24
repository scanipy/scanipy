"""Deterministic reflection-injection pipeline for CMP-CORP-REFL-01.

Discharges AC-CORP-REFL-01b: "Mutation-injection pipeline reproducibly generates
labelled reflection scenarios from clean closed-world repos."

Contract (DOC-CMP-CORP-REFL-01 §3.5):
    inject(clean_source, language, seed, recipe) is a PURE FUNCTION of
    (sha256(clean_source), seed, recipe). Re-running with the same triple
    reproduces byte-identical output AND the same recorded injection site.
    No random() without an explicit seed; no wall-clock; no dict-ordering
    dependence; no filesystem-iteration-order dependence.

The output item is labelled `not-closed-world` BY CONSTRUCTION, with
`expected_sites` set to the exact injection line (1-based). This is the per-finding
ground truth a CW-DETECT sub-detector must produce.

Safe-direction (INV-4): injection only ever ADDS reachable reflection, so the
post-injection label is always `not-closed-world`. The pipeline never produces a
`closed-world` item from a clean base (that would be a silent FN seed).
"""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass

# (language, recipe) -> {kind, anchor, snippet}
# anchor: the line whose seeded occurrence we insert AFTER (keeps reflection reachable).
# kind: mirrors the CMP-SNAP-03 ReflectionKind enum (DOC §3.2).
_RECIPES: dict[tuple[str, str], dict[str, object]] = {
    ("java", "class-forname"): {
        "kind": "java-class-forname",
        "anchor": "int s = add(x, y);",
        "snippet": [
            '        try { Class.forName("com.scanipy.corpus.clean.Calculator")'
            ".getDeclaredConstructor().newInstance(); }",
            "        catch (ReflectiveOperationException e) { throw new"
            " RuntimeException(e); }",
        ],
    },
    ("java", "method-invoke"): {
        "kind": "java-method-invoke",
        "anchor": "int s = add(x, y);",
        "snippet": [
            '        try { this.getClass().getMethod("add", int.class,'
            " int.class).invoke(this, x, y); }",
            "        catch (ReflectiveOperationException e) { throw new"
            " RuntimeException(e); }",
        ],
    },
    ("python", "import-dunder"): {
        "kind": "python-import-dunder",
        "anchor": "    s = add(x, y)",
        "snippet": ['    mod = __import__("os")', "    mod.getpid()"],
    },
    ("python", "getattr"): {
        "kind": "python-getattr",
        "anchor": "    s = add(x, y)",
        "snippet": ['    fn = getattr(__import__("builtins"), "abs")', "    fn(x)"],
    },
    ("python", "eval-exec"): {
        "kind": "python-eval-exec",
        "anchor": "    s = add(x, y)",
        "snippet": ['    eval("add(x, y)")'],
    },
    ("ruby", "send"): {
        "kind": "ruby-send",
        "anchor": "    s = add(x, y)",
        "snippet": ["    send(:add, x, y)"],
    },
    ("ruby", "define-method"): {
        "kind": "ruby-define-method",
        "anchor": "    s = add(x, y)",
        "snippet": [
            "    self.class.send(:define_method, :dynamic_add) { |a, b| a + b }",
            "    dynamic_add(x, y)",
        ],
    },
    ("php", "variable-function"): {
        "kind": "php-variable-function",
        "anchor": "$s = $this->add($x, $y);",
        "snippet": ['        $fn = "strlen";', '        $fn("reachable");'],
    },
    ("php", "call-user-func"): {
        "kind": "php-call-user-func",
        "anchor": "$s = $this->add($x, $y);",
        "snippet": ['        call_user_func([$this, "add"], $x, $y);'],
    },
    ("js", "require-dynamic"): {
        "kind": "js-require-dynamic",
        "anchor": "const s = add(x, y);",
        "snippet": ['  const mod = require("pa" + "th");', "  mod.basename(String(x));"],
    },
    ("js", "function-constructor"): {
        "kind": "js-function-constructor",
        "anchor": "const s = add(x, y);",
        "snippet": ['  const f = new Function("a", "b", "return a + b;");', "  f(x, y);"],
    },
    ("js", "eval"): {
        "kind": "js-eval",
        "anchor": "const s = add(x, y);",
        "snippet": ['  eval("add(x, y)");'],
    },
    ("go", "reflect-call"): {
        "kind": "go-reflect-call",
        "anchor": "s := add(x, y)",
        "snippet": [
            "\tv := reflect.ValueOf(add)",
            "\tv.Call([]reflect.Value{reflect.ValueOf(x), reflect.ValueOf(y)})",
        ],
    },
}


@dataclass(frozen=True)
class InjectionResult:
    """Output of a single deterministic injection."""

    source: str
    kind: str
    line: int  # 1-based line of the FIRST inserted reflection line
    input_sha: str
    seed: int
    recipe: str
    label: str = "not-closed-world"  # by construction


def _sha256_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def recipes_for(language: str) -> list[str]:
    """Deterministically-ordered recipe list for a language."""
    return sorted(r for (lang, r) in _RECIPES if lang == language)


def inject(clean_source: str, language: str, seed: int, recipe: str) -> InjectionResult:
    """Insert a reachable reflection construct deterministically.

    Pure function of (sha256(clean_source), seed, recipe). Uses random.Random(seed)
    -- never the global RNG -- so determinism does not depend on process state.
    """
    key = (language, recipe)
    if key not in _RECIPES:
        raise KeyError(f"no recipe {recipe!r} for language {language!r}")
    spec = _RECIPES[key]
    anchor = str(spec["anchor"])
    kind = str(spec["kind"])
    snippet = list(spec["snippet"])  # type: ignore[call-overload]

    lines = clean_source.splitlines(keepends=False)
    anchor_indices = [i for i, ln in enumerate(lines) if anchor in ln]
    if not anchor_indices:
        raise ValueError(f"anchor {anchor!r} not found in clean source for {language}")

    rng = random.Random(seed)
    chosen = anchor_indices[rng.randrange(len(anchor_indices))]

    insert_at = chosen + 1  # insert AFTER the chosen anchor line
    new_lines = lines[:insert_at] + snippet + lines[insert_at:]
    out = "\n".join(new_lines)
    if clean_source.endswith("\n"):
        out += "\n"

    return InjectionResult(
        source=out,
        kind=kind,
        line=insert_at + 1,
        input_sha=_sha256_text(clean_source),
        seed=seed,
        recipe=recipe,
    )


__all__ = ["InjectionResult", "inject", "recipes_for"]
