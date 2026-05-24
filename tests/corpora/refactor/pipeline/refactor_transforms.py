"""Deterministic refactor transforms for CMP-CORP-REFAC-01.

Each transform maps a seeded-vuln base (the ``before/`` tree) to an ``after/``
tree, encoding exactly one named refactor from ``PLAN.md §"Algorithm 3"`` plus
the two ``AC-CORE-02b`` flip cases. The seven labels and their ground-truth
outcome (DOC-CMP-CORP-REFAC-01 §3.2):

    alpha-rename-local          should-stay
    pdg-only-formatting         should-stay
    independent-reordering      should-stay
    pure-extract                should-stay
    fqn-move-package-rename     should-stay
    genuine-fix                 should-flip
    aliasing-changing-extract   should-flip

Ground-truth basis (METHODOLOGY, not hand-labelling — see annotation-methodology.md):
  * should-stay  := the transform provably preserves the backward interprocedural
                    slice from the seeded sink to the tainted source. A
                    refactor-stable fingerprint MUST be byte-identical before/after.
  * should-flip  := the transform changes that slice (the dangerous sink is removed
                    or made safe, or the aliasing/points-to relation feeding the sink
                    changes), so a correct fingerprint MUST differ before/after.

Transforms take the rendered ``Base`` (not bare text) so genuine-fix and the
aliasing extract can reference the seed's actual identifiers and be dispatched on
the seeded class. Determinism: each transform is a pure function of the Base; no
RNG, no clock.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from bases import Base  # type: ignore[import-not-found]

REFACTORS = [
    "alpha-rename-local",
    "pdg-only-formatting",
    "independent-reordering",
    "pure-extract",
    "fqn-move-package-rename",
    "genuine-fix",
    "aliasing-changing-extract",
]

SHOULD_STAY = {
    "alpha-rename-local",
    "pdg-only-formatting",
    "independent-reordering",
    "pure-extract",
    "fqn-move-package-rename",
}
SHOULD_FLIP = {"genuine-fix", "aliasing-changing-extract"}

GROUND_TRUTH = {r: ("should-stay" if r in SHOULD_STAY else "should-flip") for r in REFACTORS}


@dataclass(frozen=True)
class RefactorResult:
    """Output of applying one refactor to a base."""

    refactor: str
    ground_truth_label: str
    source: str
    rationale: str


# ---------------------------------------------------------------------------
# Identifier helpers (alpha-rename basis, shared by transforms)
# ---------------------------------------------------------------------------


def _seeded_idents(source: str) -> dict[str, str]:
    """Return {old_ident: new_ident} for every NNN-suffixed seeded identifier.

    The bases name their tainted param + temporaries with a `NNN`-suffixed stem;
    we map every such identifier to a fresh canonical alpha-equivalent name.
    """
    idents = sorted(set(re.findall(r"\b[a-zA-Z_]+\d{3}\b", source)))
    return {old: f"renamed{i}" for i, old in enumerate(idents)}


def _tainted_param(base: Base) -> str:
    """The seeded tainted parameter name in the rendered base (first NNN ident)."""
    idents = re.findall(r"\b[a-zA-Z_]+\d{3}\b", base.source)
    return idents[0] if idents else ""


def _replace_word(source: str, old: str, new: str) -> str:
    return re.sub(rf"\b{re.escape(old)}\b", new, source)


# ---------------------------------------------------------------------------
# should-stay transforms
# ---------------------------------------------------------------------------


def _rename_local(base: Base) -> str:
    """alpha-rename-local: consistent alpha-rename of the seeded locals/params."""
    out = base.source
    for old, new in _seeded_idents(base.source).items():
        out = _replace_word(out, old, new)
    return out


def _reformat(base: Base) -> str:
    """pdg-only-formatting: whitespace/comment-only churn the PDG ignores."""
    comment = (
        "// reformatted (no semantic change)"
        if base.language == "java"
        else "# reformatted (no semantic change)"
    )
    out: list[str] = [comment, ""]
    for ln in base.source.splitlines():
        out.append(ln)
        if ln.strip().endswith("{") or ln.strip().endswith(":"):
            out.append("")  # blank line after block openers
    return "\n".join(out) + "\n"


def _reorder_independent(base: Base) -> str:
    """independent-reordering: insert a PDG-independent statement (reorder no-op)."""
    decl = (
        "        int unrelated = 7 + 35;\n"
        if base.language == "java"
        else "        unrelated = 7 + 35\n"
    )
    lines = base.source.splitlines(keepends=True)
    idx = _first_body_index(lines, base.language)
    lines.insert(idx, decl)
    return "".join(lines)


def _pure_extract(base: Base) -> str:
    """pure-extract: extract a pure (side-effect-free, alias-stable) helper."""
    if base.language == "java":
        helper = (
            "    private static String prefix() {\n"
            '        return "";  // pure, alias-stable extract\n'
            "    }\n"
        )
        return _insert_before_last(base.source, helper, "}")
    helper = (
        "    @staticmethod\n"
        "    def _prefix():\n"
        '        return ""  # pure, alias-stable extract\n'
    )
    return base.source.rstrip("\n") + "\n\n" + helper


def _fqn_move(base: Base) -> str:
    """fqn-move-package-rename: move the class/module to a new FQN."""
    if base.language == "java":
        return base.source.replace(
            "package com.scanipy.corpus.refac;",
            "package com.scanipy.corpus.relocated.refac;",
        )
    return "# moved to scanipy.corpus.relocated\n" + base.source


# ---------------------------------------------------------------------------
# should-flip transforms (class-dispatched, parameter-aware)
# ---------------------------------------------------------------------------


def _genuine_fix(base: Base) -> str:
    """genuine-fix (should-flip): remove the seeded vulnerability for the seed's class.

    The dangerous sink is replaced by a safe/parameterized equivalent so the
    tainted source no longer reaches it. The backward slice changes -> flip.
    """
    src = base.source
    idents = re.findall(r"\b[a-zA-Z_]+\d{3}\b", src)
    p = idents[0] if idents else "arg"
    q = idents[1] if len(idents) > 1 else "tmp"
    if base.language == "java":
        if base.cls == "injection":
            src = src.replace(
                f'String {q} = "SELECT * FROM orders WHERE id = \'" + {p} + "\'";',
                'String sqlText = "SELECT * FROM orders WHERE id = ?";',
            )
            src = src.replace(
                "Statement st = conn.createStatement();",
                "java.sql.PreparedStatement st = conn.prepareStatement(sqlText);",
            )
            src = src.replace(
                f"st.executeQuery({q});",
                f"st.setString(1, {p});\n        st.executeQuery();",
            )
        elif base.cls == "path-traversal":
            src = src.replace(
                f'File target = new File(root + "/" + {p});',
                f"File target = new File(root, "
                f"java.nio.file.Paths.get(\"/\", {p}).normalize()"
                ".getFileName().toString());  // contained to root",
            )
        elif base.cls == "ssrf":
            src = src.replace(
                f'URL url = new URL("http://" + {p} + "/status");',
                f'if (!"allowlisted.internal".equals({p})) '
                'throw new SecurityException("ssrf");\n'
                '        URL url = new URL("http://allowlisted.internal/status");',
            )
        elif base.cls == "deserialization":
            src = src.replace(
                "ObjectInputStream ois = new ObjectInputStream(bin);",
                "ObjectInputStream ois = new SafeObjectInputStream(bin);  "
                "// resolveClass allow-list",
            )
    else:  # python
        if base.cls == "injection":
            src = src.replace(
                f'{q} = "SELECT * FROM orders WHERE id = \'" + {p} + "\'"',
                f'{q} = "SELECT * FROM orders WHERE id = %s"  # parameterized',
            )
            src = src.replace(
                f"self.cursor.execute({q})",
                f"self.cursor.execute({q}, ({p},))  # bound parameter",
            )
        elif base.cls == "path-traversal":
            src = src.replace(
                f"target = os.path.join(self.root, {p})",
                f"target = os.path.join(self.root, os.path.basename({p}))  "
                "# contained to root",
            )
        elif base.cls == "ssrf":
            src = src.replace(
                f'url = "http://" + {p} + "/status"',
                'url = "http://allowlisted.internal/status"  # fixed allow-listed host',
            )
        elif base.cls == "deserialization":
            src = src.replace("import pickle", "import json")
            src = src.replace(
                f"data = pickle.loads({p})",
                f"data = json.loads({p})  # JSON, not pickle",
            )
    return src


def _aliasing_changing_extract(base: Base) -> str:
    """aliasing-changing-extract (should-flip): extract that changes aliasing.

    Unlike pure-extract, this routes the tainted value through a mutable
    container / out-parameter so the points-to relation feeding the sink changes.
    Algorithm 3's summary-inlining does NOT cover impure/aliasing extracts
    (DOC §3.2), so the fingerprint MUST flip.
    """
    p = _tainted_param(base)
    src = base.source
    if base.language == "java":
        holder = (
            "        String[] box = new String[]{String.valueOf(" + p + ")};\n"
            "        alias(box);\n"
        )
        method = (
            "\n    private void alias(String[] b) {\n"
            "        b[0] = b[0];  // aliasing-introducing extract\n"
            "    }\n"
        )
        src = _inject_after_first_body(src, holder, base.language)
        src = _insert_before_last(src, method, "}")
        return src
    holder = "        box = [" + p + "]\n        self._route(box)\n"
    method = (
        "\n    @staticmethod\n"
        "    def _route(box):\n"
        "        box.append(box[0])  # aliasing-introducing extract\n"
    )
    src = _inject_after_first_body(src, holder, base.language)
    src = src.rstrip("\n") + "\n" + method
    return src


# ---------------------------------------------------------------------------
# Structural helpers
# ---------------------------------------------------------------------------


def _first_body_index(lines: list[str], language: str) -> int:
    """Index just inside the first non-constructor method body."""
    if language == "java":
        for i, ln in enumerate(lines):
            s = ln.strip()
            if s.endswith("{") and any(
                tok in s for tok in ("public ", "void ", "byte[]", "Object ", "int ")
            ):
                return i + 1
        return 1
    for i, ln in enumerate(lines):
        s = ln.strip()
        if s.startswith("def ") and "__init__" not in s:
            return i + 1
    return 1


def _insert_before_last(source: str, fragment: str, marker: str) -> str:
    idx = source.rstrip().rfind(marker)
    if idx == -1:
        return source + fragment
    return source[:idx] + fragment + source[idx:]


def _inject_after_first_body(source: str, fragment: str, language: str) -> str:
    lines = source.splitlines(keepends=True)
    idx = _first_body_index(lines, language)
    lines.insert(idx, fragment)
    return "".join(lines)


_TRANSFORMS = {
    "alpha-rename-local": _rename_local,
    "pdg-only-formatting": _reformat,
    "independent-reordering": _reorder_independent,
    "pure-extract": _pure_extract,
    "fqn-move-package-rename": _fqn_move,
    "genuine-fix": _genuine_fix,
    "aliasing-changing-extract": _aliasing_changing_extract,
}

_RATIONALES = {
    "alpha-rename-local": "Consistent alpha-rename of seeded locals/params; slice preserved, fingerprint must stay.",
    "pdg-only-formatting": "Whitespace/comment-only churn; no PDG edge changes, fingerprint must stay.",
    "independent-reordering": "Reorder a PDG-independent statement; canonical topo-sort no-op, fingerprint must stay.",
    "pure-extract": "Extract a pure alias-stable helper; summary-inlining covers it, fingerprint must stay.",
    "fqn-move-package-rename": "Move class/module to a new FQN; FQN normalization covers it, fingerprint must stay.",
    "genuine-fix": "Seeded sink replaced by a safe/parameterized equivalent for this class; slice changes, fingerprint must flip.",
    "aliasing-changing-extract": "Extract routes taint through a freshly-aliased holder; aliasing changes, fingerprint must flip.",
}


def apply_refactor(base: Base, refactor: str) -> RefactorResult:
    """Apply one named refactor to a base. Pure + deterministic."""
    if refactor not in _TRANSFORMS:
        raise KeyError(f"unknown refactor: {refactor}")
    after = _TRANSFORMS[refactor](base)
    return RefactorResult(
        refactor=refactor,
        ground_truth_label=GROUND_TRUTH[refactor],
        source=after,
        rationale=_RATIONALES[refactor],
    )
