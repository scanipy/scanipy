"""CMP-DET-03 — class-plugin scaffolding generator (AC-DET-03a).

Authors the ``detectors/<class>/`` directory skeleton that the registry
(CMP-DET-02, ``detectors/registry.py``) discovers and loads at boot. The output
of :func:`scaffold_class` over the ten ``ClassName`` values is a tree on which
``DetectorRegistry.load_manifests()`` completes without error (stub manifests
permitted — AC-DET-03a).

Provenance (DOC-CMP-DET-03 §8): this tool writes NO provenance fields. The
scaffolded ``manifest.engine`` is the only authored signal; CMP-DET-02 derives
``determinism_partition`` from it and CMP-ORCH-03 stamps ``origin`` per finding
downstream. The scaffold is pass-through with respect to the four-field rule.

Single-spec-per-detector (CLAR-DET-03, OPEN): the scaffold assumes one DSL spec
per core detector — the provisional default. Mixed classes (``crypto-misuse``,
``authn-authz``) are scaffolded core-only here; their oracle portion is authored
later (it is not part of the AC-DET-03a stub contract).

Idempotency (DOC-CMP-DET-03 §7.3): re-running refreshes ``README.md`` and the
``per_language_readiness`` block without overwriting authored DSL files under
``specs/``. A structurally unexpected target tree raises :class:`ScaffoldError`;
the tool never guesses.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml

# The ten pinned detector classes (DOC-CMP-DET-03 §3.1, SDD §11). Mirrors
# ``analysis.ifds.dsl.spec.CLASS_NAMES`` but is restated here so the scaffold
# tool does not depend on the DSL package's internal ordering.
ClassName = Literal[
    "injection",
    "path-traversal",
    "ssrf",
    "deserialization",
    "xss",
    "crypto-misuse",
    "authn-authz",
    "memory-safety",
    "secrets",
    "dep-cve",
]

Engine = Literal["ifds", "ide", "semgrep", "cpg-query", "external"]

CLASS_NAMES: tuple[ClassName, ...] = (
    "injection",
    "path-traversal",
    "ssrf",
    "deserialization",
    "xss",
    "crypto-misuse",
    "authn-authz",
    "memory-safety",
    "secrets",
    "dep-cve",
)

# Engines that read a DSL spec from ``specs/`` vs. a native query from a path
# named in the manifest. Kept in lockstep with ``detectors.registry`` (the
# normative source); restated to avoid a load-time import cycle through yaml.
_CORE_ENGINES: frozenset[str] = frozenset(("ifds", "ide"))
_ORACLE_ENGINES: frozenset[str] = frozenset(("semgrep", "cpg-query", "external"))
_ALL_ENGINES: frozenset[str] = _CORE_ENGINES | _ORACLE_ENGINES

# Default engine per class for the AC-DET-03a stub, chosen so the registry's
# DERIVED ``determinism_partition`` matches each class's current Stage-A posture
# (DOC-STAGING / .claude/rules/04-staging.md), not a future stage:
#   - The four Stage-A core classes (injection, path-traversal, ssrf,
#     deserialization) -> ``ifds`` (deterministic-core).
#   - ``crypto-misuse`` / ``authn-authz`` are mixed with a real IFDS portion that
#     follows language staging -> ``ifds`` for the core stub (the oracle pattern
#     portion is authored later; not part of the AC-DET-03a stub contract).
#   - ``xss`` is oracle in Stage A (core only AFTER the Stage-B gate) -> oracle
#     stub here so its derived partition is honest about today's posture.
#   - ``memory-safety`` (oracle via CodeQL, OOS-CC-01), ``secrets``, ``dep-cve``
#     are always oracle -> ``external``.
# A caller may override via ``default_engine``.
_DEFAULT_ENGINE_BY_CLASS: dict[ClassName, Engine] = {
    "injection": "ifds",
    "path-traversal": "ifds",
    "ssrf": "ifds",
    "deserialization": "ifds",
    "xss": "external",
    "crypto-misuse": "ifds",
    "authn-authz": "ifds",
    "memory-safety": "external",
    "secrets": "external",
    "dep-cve": "external",
}

# Stub manifest metadata per class (AC-DET-03a permits stubs). These are
# placeholders authored later by the Implementation / Corpus agents; the values
# only need to be schema-valid for the registry to load them.
_STUB_CWES: dict[ClassName, list[str]] = {
    "injection": ["CWE-89"],
    "path-traversal": ["CWE-22"],
    "ssrf": ["CWE-918"],
    "deserialization": ["CWE-502"],
    "xss": ["CWE-79"],
    "crypto-misuse": ["CWE-327"],
    "authn-authz": ["CWE-285"],
    "memory-safety": ["CWE-787"],
    "secrets": ["CWE-798"],
    "dep-cve": ["CWE-1395"],
}

# Default per-class languages used when the caller passes no ``languages=``.
_DEFAULT_LANGUAGES: dict[ClassName, tuple[str, ...]] = {
    "injection": ("java", "python"),
    "path-traversal": ("java", "python"),
    "ssrf": ("java", "python"),
    "deserialization": ("java", "python"),
    "xss": ("javascript", "typescript"),
    "crypto-misuse": ("java", "python"),
    "authn-authz": ("java", "python"),
    "memory-safety": ("cpp",),
    "secrets": ("java", "python", "javascript"),
    "dep-cve": ("java", "python", "javascript"),
}

# Languages the DSL parser accepts in a spec header (mirror of
# ``analysis.ifds.dsl.spec.LANGUAGES``). A core stub spec header must use one of
# these; ``cpp`` is intentionally absent (C/C++ is oracle-only, OOS-CC-01).
_DSL_LANGUAGES: frozenset[str] = frozenset(
    ("java", "python", "javascript", "typescript", "go", "ruby", "php")
)

_README_TEMPLATE = """\
# `{class_name}` detector class

Scaffolded by `tools/scaffold_class.py` (CMP-DET-03, AC-DET-03a). This directory
holds the detector content for the `{class_name}` class.

## Layout

- `manifest.yaml` — registry manifest (CMP-DET-02 reads this at boot).
- `specs/` — combinator-DSL specs (`*.dsl.yaml`), parsed by CMP-DET-01 for
  core engines (`engine ∈ {{ifds, ide}}`).
- `oracle/` — native oracle queries (`engine ∈ {{semgrep, cpg-query, external}}`).
- `README.md` — this file.

## Stub status

This is a **stub** scaffold (AC-DET-03a): the manifest and any DSL/oracle
placeholder load through `DetectorRegistry.load_manifests()` without error, but
the detection content is not yet authored. Provenance is threaded downstream
(CMP-DET-02 derives `determinism_partition` from `engine`; CMP-ORCH-03 stamps
`origin`) — this scaffold writes no provenance fields.
"""


class ScaffoldError(Exception):
    """A scaffold operation found unexpected file-system state.

    Raised when ``root / class_name`` exists with a structure the generator did
    not author (e.g. a ``manifest.yml`` instead of ``manifest.yaml``, or a file
    where a skeleton directory is expected). The tool refuses to guess; the
    operator must clean up first (DOC-CMP-DET-03 §7.3).
    """


def _stub_dsl_spec(spec_id: str, class_name: ClassName, languages: tuple[str, ...]) -> str:
    """A minimal, parseable DSL spec for a core-engine stub.

    Picks a DSL-legal language for the header (falling back to ``java``), and a
    source/sink clause pair whose access-path patterns avoid every DSL escape
    hatch (no raw regex / semgrep / cpg-query / callable / sequencing keyword).
    Parses through ``analysis.ifds.dsl.parse_spec`` so the registry admits it.
    """
    dsl_langs = tuple(lang for lang in languages if lang in _DSL_LANGUAGES) or ("java",)
    langs_block = ", ".join(f'"{lang}"' for lang in dsl_langs)
    return (
        f'id: "{spec_id}"\n'
        f'class: "{class_name}"\n'
        f"languages: [{langs_block}]\n"
        'engine: "ifds"\n'
        "# Stub spec (AC-DET-03a): placeholder source/sink, not detection content.\n"
        "source(stub.placeholder.taint(*))\n"
        "sink(stub.placeholder.exec(arg[0]))\n"
    )


def _write_if_absent(path: Path, content: str) -> None:
    """Write ``content`` to ``path`` only if it does not already exist.

    Authored content under ``specs/`` is never overwritten by the scaffold
    (DOC-CMP-DET-03 §7.3).
    """
    if not path.exists():
        path.write_text(content, encoding="utf-8")


def _merged_manifest(
    manifest_path: Path,
    *,
    class_name: ClassName,
    engine: Engine,
    languages: tuple[str, ...],
    oracle_query_path: str | None,
) -> dict[str, object]:
    """Build the manifest dict, merging an existing one if present.

    Idempotency (DOC-CMP-DET-03 §7.3): authored scalar fields (``id``, ``cwes``,
    ``frameworks``, ``severity_default``, ``engine``) are preserved when already
    present; ``per_language_readiness`` is refreshed from ``languages``.
    """
    existing: dict[str, object] = {}
    if manifest_path.is_file():
        loaded = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        if loaded is not None and not isinstance(loaded, dict):
            raise ScaffoldError(
                f"existing manifest {str(manifest_path)!r} is not a mapping; "
                "refusing to overwrite — clean up first"
            )
        existing = loaded or {}

    per_language_readiness = dict.fromkeys(languages, "stage-gated")

    manifest: dict[str, object] = {
        "id": existing.get("id", class_name),
        "cwes": existing.get("cwes", _STUB_CWES[class_name]),
        "languages": existing.get("languages", list(languages)),
        "frameworks": existing.get("frameworks", []),
        "engine": existing.get("engine", engine),
        "severity_default": existing.get("severity_default", "medium"),
        "per_language_readiness": per_language_readiness,
    }
    if oracle_query_path is not None:
        manifest["oracle_query_path"] = existing.get("oracle_query_path", oracle_query_path)
    return manifest


def scaffold_class(
    class_name: ClassName,
    *,
    root: Path = Path("detectors/"),
    languages: tuple[str, ...] = (),
    default_engine: Engine | None = None,
    stub_only: bool = True,
) -> None:
    """Create the directory skeleton for one detector class (DOC-CMP-DET-03 §3.1).

    Produces (relative to ``root / class_name``)::

        manifest.yaml   — stub: id / cwes / languages / frameworks / engine /
                          severity_default / per_language_readiness
                          (+ oracle_query_path for oracle engines)
        specs/          — DSL spec directory; a minimal stub spec for core engines
        oracle/         — native query directory; a stub query for oracle engines
        README.md       — class-level documentation

    The output is loadable by ``DetectorRegistry.load_manifests()`` without error
    (AC-DET-03a): a core engine carries a parseable ``specs/*.dsl.yaml`` stub; an
    oracle engine carries an existing ``oracle/*`` file named by
    ``oracle_query_path``. The unused subtree gets an empty ``.gitkeep``.

    Idempotent: re-running refreshes ``README.md`` and ``per_language_readiness``
    in ``manifest.yaml`` without overwriting authored DSL files under ``specs/``.

    Raises :class:`ScaffoldError` if ``root / class_name`` exists with a
    structure the generator did not author (e.g. ``manifest.yaml`` is not a
    mapping). ``stub_only`` is accepted for signature compatibility with
    DOC-CMP-DET-03 §3.1; the AC-DET-03a scaffold always emits a loadable stub.
    """
    if class_name not in CLASS_NAMES:
        raise ScaffoldError(f"unknown class {class_name!r}; expected one of {list(CLASS_NAMES)}")
    _ = stub_only  # signature compatibility (DOC §3.1); stub is always loadable

    engine: Engine = default_engine or _DEFAULT_ENGINE_BY_CLASS[class_name]
    if engine not in _ALL_ENGINES:
        raise ScaffoldError(f"engine {engine!r} not in {{ifds, ide, semgrep, cpg-query, external}}")

    class_languages = languages or _DEFAULT_LANGUAGES[class_name]

    class_dir = root / class_name
    if class_dir.exists() and not class_dir.is_dir():
        raise ScaffoldError(
            f"target {str(class_dir)!r} exists and is not a directory; clean up first"
        )

    specs_dir = class_dir / "specs"
    oracle_dir = class_dir / "oracle"
    class_dir.mkdir(parents=True, exist_ok=True)
    specs_dir.mkdir(parents=True, exist_ok=True)
    oracle_dir.mkdir(parents=True, exist_ok=True)

    oracle_query_path: str | None = None
    if engine in _CORE_ENGINES:
        # Core engine: needs a parseable specs/*.dsl.yaml; oracle/ is a placeholder.
        _write_if_absent(
            specs_dir / f"{class_name}.stub.dsl.yaml",
            _stub_dsl_spec(class_name, class_name, class_languages),
        )
        _write_if_absent(oracle_dir / ".gitkeep", "")
    else:
        # Oracle engine: needs an existing query file named by oracle_query_path;
        # specs/ is a placeholder.
        query_name = f"{class_name}.stub.query"
        _write_if_absent(
            oracle_dir / query_name,
            f"# Stub oracle query for {class_name} (AC-DET-03a placeholder).\n",
        )
        _write_if_absent(specs_dir / ".gitkeep", "")
        oracle_query_path = f"oracle/{query_name}"

    manifest = _merged_manifest(
        class_dir / "manifest.yaml",
        class_name=class_name,
        engine=engine,
        languages=class_languages,
        oracle_query_path=oracle_query_path,
    )
    (class_dir / "manifest.yaml").write_text(
        yaml.safe_dump(manifest, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )

    (class_dir / "README.md").write_text(
        _README_TEMPLATE.format(class_name=class_name), encoding="utf-8"
    )


def scaffold_all(root: Path = Path("detectors/")) -> None:
    """Scaffold every one of the ten pinned classes under ``root`` (AC-DET-03a)."""
    for class_name in CLASS_NAMES:
        scaffold_class(class_name, root=root)
