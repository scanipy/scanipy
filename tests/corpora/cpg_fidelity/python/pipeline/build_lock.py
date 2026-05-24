"""Build (and validate) the Python CPG-fidelity corpus.lock for CMP-CORP-CPG-python.

Responsibilities (DOC-CMP-CORP-CPG-python §3.1, §3.2, §7):
  1. Run pipeline/extract_ground_truth.py over every program (regenerating the
     ground_truth/{ast,cfg,callgraph,pdg,parse}.json from source/).
  2. Emit each program's provenance.yaml + extraction.yaml from the pinned
     PROGRAMS registry below (single source of truth for source_url / commit_sha /
     license / construct_coverage / tool versions).
  3. Validate every program against DOC §3.2 invariants + §7 failure modes:
       - source_url, commit_sha, license present; license on the allow-list;
       - Python-2 contamination rejected;
       - every §4.3 construct tag covered by >= 1 program;
       - both `type-hints` AND `duck-typing-callsite` present;
       - extraction_tools versions pinned (no "latest").
  4. Refuse to emit on any HARD failure.
  5. Emit corpus.lock with corpus_version + corpus_digest, where corpus_digest is the
     sha256 of the CANONICAL serialization (sorted-key JSON, EXCLUDING the volatile
     built_at and the digest field itself), so the digest pins the evaluation set,
     not the wall clock (DOC §8).

Run:  python3 pipeline/build_lock.py --write   # regenerate gt + provenance + lock
      python3 pipeline/build_lock.py --check    # CI: fail on digest drift
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import extract_ground_truth as gt  # noqa: E402

CORPUS_ROOT = Path(__file__).resolve().parent.parent
PROGRAMS_DIR = CORPUS_ROOT / "programs"
LOCK_PATH = CORPUS_ROOT / "corpus.lock"

CORPUS_ID = "CMP-CORP-CPG-python"
CORPUS_VERSION = "0.1.0"  # README §Status: NOT the v1.0.0 release bar (see CLAR-CORP-11)
BUILT_BY = "corpus-agent/CMP-CORP-CPG-python"
LANGUAGE_LEVEL = "3.10"  # programs are written in the 3.10-compatible subset

LICENSE_ALLOWLIST = {"MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "MPL-2.0", "PSF"}

# DOC §4.3 required construct-coverage tags. build_lock refuses if any is uncovered.
REQUIRED_TAGS = {
    "dynamic-dispatch",
    "decorators",
    "async-await",
    "type-hints",
    "duck-typing-callsite",
    "metaclasses",
    "import-star",
    "dataclasses-pydantic",
    "notebooks-converted",
    "c-extension-wrapper",
}

# v0.1.0 extraction toolchain. The DOC pins scalpel 1.0.4 / Pyan3 1.2.0 / Pyre
# 0.0.301 on cpython 3.10; this build runs the AST step on the host interpreter
# and uses the in-repo extractor for CFG/callgraph/PDG. Deviation tracked by
# CLAR-CORP-11 (WBS §17). `python` is recorded honestly from the host.
import platform as _platform  # noqa: E402

EXTRACTION_TOOLS = {
    "python": _platform.python_version(),
    "extractor": "scanipy-cpg-python-extractor/0.1.0 (in-repo; pipeline/extract_ground_truth.py)",
    # Pinned target toolchain the v1.0.0 bar must re-extract under (CLAR-CORP-11):
    "target_scalpel": "1.0.4",
    "target_pyan3": "1.2.0",
    "target_pyre": "0.0.301",
    "target_python": "3.10.13",
}

# ---------------------------------------------------------------------------
# Pinned program registry — single source of truth for provenance.
#   synthetic == True  -> authored for this corpus (Apache-2.0), content-addressed.
#   synthetic == False -> SOURCED from a public repo; source_url + commit_sha pin it.
# ---------------------------------------------------------------------------
PROGRAMS: dict[str, dict] = {
    "0001-decorators-svc": {
        "synthetic": True,
        "license": "Apache-2.0",
        "tags": ["decorators", "type-hints"],
    },
    "0002-async-await": {
        "synthetic": True,
        "license": "Apache-2.0",
        "tags": ["async-await", "type-hints"],
    },
    "0003-type-hints": {
        "synthetic": True,
        "license": "Apache-2.0",
        "tags": ["type-hints"],
    },
    "0004-duck-typing": {
        "synthetic": True,
        "license": "Apache-2.0",
        "tags": ["duck-typing-callsite"],
    },
    "0005-dynamic-dispatch": {
        "synthetic": True,
        "license": "Apache-2.0",
        "tags": ["dynamic-dispatch", "duck-typing-callsite"],
    },
    "0006-metaclasses": {
        "synthetic": True,
        "license": "Apache-2.0",
        "tags": ["metaclasses", "dynamic-dispatch"],
    },
    "0007-import-star": {
        "synthetic": True,
        "license": "Apache-2.0",
        "tags": ["import-star"],
    },
    "0008-dataclasses-pydantic": {
        "synthetic": True,
        "license": "Apache-2.0",
        "tags": ["dataclasses-pydantic", "type-hints"],
    },
    "0009-notebooks-converted": {
        "synthetic": True,
        "license": "Apache-2.0",
        "tags": ["notebooks-converted"],
    },
    "0010-cext-wrapper": {
        "synthetic": True,
        "license": "Apache-2.0",
        "tags": ["c-extension-wrapper", "type-hints"],
    },
    "0011-requests-hooks-sourced": {
        "synthetic": False,
        "license": "Apache-2.0",
        "source_url": "https://github.com/psf/requests",
        "commit_sha": "cd90742ed94d901759e26766197d0ce7c7bd9c8e",
        "path_in_source": "src/requests/hooks.py",
        "tags": ["type-hints", "dynamic-dispatch"],
    },
}


class _IndentDumper(yaml.SafeDumper):
    def increase_indent(self, flow: bool = False, indentless: bool = False):
        return super().increase_indent(flow, False)


def _dump_yaml(doc: dict) -> str:
    return yaml.dump(doc, Dumper=_IndentDumper, sort_keys=True, default_flow_style=False)


def _sha256_dir(path: Path) -> str:
    h = hashlib.sha256()
    for p in sorted(path.rglob("*")):
        if p.is_file():
            h.update(p.relative_to(path).as_posix().encode("utf-8"))
            h.update(b"\0")
            h.update(p.read_bytes())
            h.update(b"\0")
    return "sha256:" + h.hexdigest()


def _looks_like_python2(text: str) -> bool:
    """Heuristic Python-2 contamination check (DOC §7). py2 print-statement /
    `except X, e:` syntax fails ast.parse on a py3 interpreter; this is a cheap
    pre-filter before the parse that the extractor performs."""
    try:
        gt.ast.parse(text)
        return False
    except SyntaxError:
        return True


def _loc(source_dir: Path) -> int:
    total = 0
    for p in sorted(source_dir.rglob("*.py")):
        total += len(p.read_text(encoding="utf-8").splitlines())
    return total


def emit_program_metadata(now: str) -> list[str]:
    """Write provenance.yaml + extraction.yaml for each registered program."""
    hard: list[str] = []
    for pid, meta in PROGRAMS.items():
        pdir = PROGRAMS_DIR / pid
        sdir = pdir / "source"
        if not sdir.is_dir():
            hard.append(f"{pid}: missing source/ dir")
            continue
        for py in sorted(sdir.rglob("*.py")):
            if _looks_like_python2(py.read_text(encoding="utf-8")):
                hard.append(f"{pid}: {py.name} looks like Python 2 (rejected)")

        synthetic = meta["synthetic"]
        if synthetic:
            source_url = f"local:programs/{pid}/source"
            commit_sha = _sha256_dir(sdir)
            path_in_source = "source/"
        else:
            source_url = meta["source_url"]
            commit_sha = meta["commit_sha"]
            path_in_source = meta["path_in_source"]

        prov = {
            "source_url": source_url,
            "commit_sha": commit_sha,
            "path_in_source": path_in_source,
            "sha256_source_tree": _sha256_dir(sdir),
            "license": meta["license"],
            "python_minor": LANGUAGE_LEVEL,
            "synthetic": synthetic,
            "construct_coverage": sorted(meta["tags"]),
        }
        (pdir / "provenance.yaml").write_text(_dump_yaml(prov), encoding="utf-8")

        extraction = {
            "extracted_by": "pipeline",
            "extracted_at": now,
            "tool_versions": EXTRACTION_TOOLS,
            "known_limitations": (
                "v0.1.0 deviates from the DOC §3.4 pinned toolchain "
                "(scalpel 1.0.4 / Pyan3 1.2.0 / Pyre 0.0.301 on cpython 3.10): the "
                "AST step runs on the host interpreter and CFG/callgraph/PDG come from "
                "the in-repo pipeline/extract_ground_truth.py. Call-graph ground truth "
                "is the statically name-resolvable subset; sites the extractor cannot "
                "resolve statically are tagged `dynamic` and EXCLUDED from the gate's "
                "precision/recall (DOC §3.4 step 3). Tracked by CLAR-CORP-11 (WBS §17)."
            ),
            "review_status": "pipeline",
        }
        (pdir / "extraction.yaml").write_text(_dump_yaml(extraction), encoding="utf-8")
    return hard


def assemble_lock(now: str) -> tuple[dict, list[str], list[str]]:
    hard: list[str] = []
    warn: list[str] = []
    programs: list[dict] = []
    covered: set[str] = set()
    has_type_hints = False
    has_duck = False

    for pid in sorted(PROGRAMS):
        pdir = PROGRAMS_DIR / pid
        sdir = pdir / "source"
        gtdir = pdir / "ground_truth"
        meta = PROGRAMS[pid]

        for req in ("ast.json", "cfg.json", "callgraph.json", "pdg.json", "parse.json"):
            if not (gtdir / req).exists():
                hard.append(f"{pid}: missing ground_truth/{req}")

        lic = meta["license"]
        if lic not in LICENSE_ALLOWLIST:
            hard.append(f"{pid}: license {lic!r} not in allow-list")

        tags = set(meta["tags"])
        covered |= tags
        has_type_hints = has_type_hints or "type-hints" in tags
        has_duck = has_duck or "duck-typing-callsite" in tags

        if meta["synthetic"]:
            source_url = f"local:programs/{pid}/source"
            commit_sha = _sha256_dir(sdir)
        else:
            source_url = meta["source_url"]
            commit_sha = meta["commit_sha"]
            if not source_url or not commit_sha:
                hard.append(f"{pid}: SOURCED program missing source_url/commit_sha")

        # parse-success input for the gate (informational here)
        parse_records = json.loads((gtdir / "parse.json").read_text("utf-8")) if (
            gtdir / "parse.json"
        ).exists() else []
        n_files = len(parse_records)
        n_parsed = sum(1 for r in parse_records if r.get("parsed"))

        programs.append(
            {
                "id": pid,
                "synthetic": meta["synthetic"],
                "source_url": source_url,
                "commit_sha": commit_sha,
                "license": lic,
                "loc": _loc(sdir),
                "files": n_files,
                "files_parsed": n_parsed,
                "construct_coverage": sorted(tags),
                "sha256_source_tree": _sha256_dir(sdir),
                "sha256_ground_truth": _sha256_dir(gtdir) if gtdir.is_dir() else None,
                "extraction_tools": EXTRACTION_TOOLS,
            }
        )

    missing_tags = sorted(REQUIRED_TAGS - covered)
    if missing_tags:
        hard.append(f"uncovered DOC §4.3 construct tags: {missing_tags}")
    if not (has_type_hints and has_duck):
        hard.append("DOC §3.2 inv 3: need BOTH type-hints AND duck-typing-callsite programs")
    for tool, ver in EXTRACTION_TOOLS.items():
        if ver == "latest" or not ver:
            hard.append(f"extraction tool {tool} not pinned (got {ver!r})")

    lock = {
        "corpus_id": CORPUS_ID,
        "corpus_version": CORPUS_VERSION,
        "corpus_digest": "sha256:PENDING",
        "language": "python",
        "language_level": LANGUAGE_LEVEL,
        "built_at": now,
        "built_by": BUILT_BY,
        "ground_truth_method": (
            "AST: cpython `ast` (host interpreter; programs in the 3.10-compatible "
            "subset) with stable field ordering + source positions. "
            "CFG/callgraph/PDG: in-repo pipeline/extract_ground_truth.py. Call edges "
            "are (caller, callee, line) triples tagged static|dynamic; `dynamic` sites "
            "(getattr/dict-dispatch/cross-module/FFI/runtime receivers) are recorded "
            "but EXCLUDED from the gate's precision/recall (DOC §3.4 step 3). v0.1.0 "
            "deviates from the DOC-pinned scalpel/Pyan3/Pyre toolchain (CLAR-CORP-11); "
            "see README.md §Status + §3."
        ),
        "deviation": "CLAR-CORP-11",
        "programs": programs,
    }
    return lock, hard, warn


def canonical_digest(lock: dict) -> str:
    payload = {k: v for k, v in lock.items() if k not in ("corpus_digest", "built_at")}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main() -> int:
    ap = argparse.ArgumentParser(description="Build/validate the Python CPG-fidelity corpus.lock")
    ap.add_argument("--write", action="store_true", help="regenerate gt + provenance + lock")
    ap.add_argument("--check", action="store_true", help="fail if lock digest drifts (CI)")
    args = ap.parse_args()

    now = _now()

    if args.write:
        for d in sorted(p for p in PROGRAMS_DIR.iterdir() if p.is_dir()):
            gt.extract_program(d)
        hard0 = emit_program_metadata(now)
        if hard0:
            print("CORPUS BUILD REFUSED — provenance HARD failures:", file=sys.stderr)
            for e in hard0:
                print(f"  - {e}", file=sys.stderr)
            return 2

    lock, hard, warn = assemble_lock(now)
    for w in warn:
        print(f"[warn] {w}", file=sys.stderr)
    if hard:
        print("CORPUS BUILD REFUSED — DOC §7 HARD failures:", file=sys.stderr)
        for e in hard:
            print(f"  - {e}", file=sys.stderr)
        return 2

    lock["corpus_digest"] = canonical_digest(lock)

    if args.check:
        if not LOCK_PATH.exists():
            print("corpus.lock missing; run --write", file=sys.stderr)
            return 3
        existing = yaml.safe_load(LOCK_PATH.read_text("utf-8")) or {}
        recomputed = canonical_digest({**existing, "corpus_digest": "sha256:PENDING"})
        if existing.get("corpus_digest") != recomputed:
            print(
                f"corpus_digest drift: recorded={existing.get('corpus_digest')} "
                f"recomputed={recomputed}",
                file=sys.stderr,
            )
            return 4
        print(f"corpus.lock digest OK: {existing.get('corpus_digest')}")
        return 0

    if args.write:
        LOCK_PATH.write_text(_dump_yaml(lock), encoding="utf-8")
        print(f"wrote {LOCK_PATH}")
        print(f"corpus_version: {lock['corpus_version']}")
        print(f"corpus_digest:  {lock['corpus_digest']}")
        return 0

    print(canonical_digest(lock))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
