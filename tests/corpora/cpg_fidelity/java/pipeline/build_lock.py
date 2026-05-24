"""Build (and validate) tests/corpora/cpg_fidelity/java/corpus.lock for CMP-CORP-CPG-java.

Responsibilities (DOC-CMP-CORP-CPG-java §3.2, §3.3, §7):
  1. Walk programs/<id>/, load each program's provenance.yaml + extraction.yaml +
     the four ground_truth/*.json files; validate the on-disk layout.
  2. Refuse to emit the lock on any DOC §7 HARD failure (missing
     source_url/commit_sha/license; bad license; missing a ground_truth/*.json
     file; missing provenance/extraction).
  3. Check construct-tag coverage (§4.3). Because this is an explicitly-labelled
     v0.1.0 SYNTHESIZED build, a missing required tag is reported as a WARN with a
     "v0.1.0 missing tags" note rather than a hard refuse (the v1.0.0 bar flips it
     to a refuse). The 10%-generated-code balance rule (§3.3) is checked the same way.
  4. Emit corpus.lock with corpus_version + corpus_digest, where corpus_digest is
     the sha256 of the CANONICAL serialization (sorted-key JSON, EXCLUDING the
     volatile built_at/built_by and the digest field itself), so the digest pins the
     evaluation set, not the wall clock (DOC §8). Identical scheme to the reflection
     corpus's build_lock.py.

Run:  python3 pipeline/build_lock.py --write    # write lock
      python3 pipeline/build_lock.py --check     # CI: fail on digest drift
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import sys
from pathlib import Path

import yaml


class _IndentDumper(yaml.SafeDumper):
    """SafeDumper that indents block sequences under their key (yamllint default)."""

    def increase_indent(self, flow: bool = False, indentless: bool = False):
        return super().increase_indent(flow, False)


def _dump_yaml(doc: dict) -> str:
    return yaml.dump(doc, Dumper=_IndentDumper, sort_keys=True, default_flow_style=False)


CORPUS_ROOT = Path(__file__).resolve().parent.parent
PROGRAMS_DIR = CORPUS_ROOT / "programs"
LOCK_PATH = CORPUS_ROOT / "corpus.lock"

CORPUS_ID = "CMP-CORP-CPG-java"
CORPUS_VERSION = "0.1.0"  # README §Status: NOT the v1.0.0 gate-ready bar
BUILT_BY = "corpus-agent/CMP-CORP-CPG-java"
LANGUAGE = "java"
LANGUAGE_LEVEL = 17

LICENSE_ALLOWLIST = {"MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "MPL-2.0"}

GROUND_TRUTH_FILES = ("ast.json", "cfg.json", "callgraph.json", "pdg.json")

# DOC §4.3 — every tag MUST be carried by >= 1 program.
REQUIRED_TAGS = {
    "interface-dispatch",
    "inheritance-chain",
    "generics",
    "lambdas",
    "method-references",
    "inner-class",
    "try-with-resources",
    "spring-di",
    "annotation-heavy",
    "recent-language",
    "generated-code",
}
# DOC §3.3 — >= 10% of programs carry a hard-to-parse / generated tag.
GENERATED_MIN_FRACTION = 0.10


def _sha256_dir(path: Path) -> str:
    """Deterministic sha256 over a directory: sorted relpaths + contents."""
    h = hashlib.sha256()
    for p in sorted(path.rglob("*")):
        if p.is_file():
            h.update(p.relative_to(path).as_posix().encode("utf-8"))
            h.update(b"\0")
            h.update(p.read_bytes())
            h.update(b"\0")
    return "sha256:" + h.hexdigest()


def _now_utc() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _count_loc(source_dir: Path) -> int:
    total = 0
    for p in sorted(source_dir.rglob("*.java")):
        total += len(p.read_text(encoding="utf-8").splitlines())
    return total


def assemble_lock() -> tuple[dict, list[str], list[str]]:
    """Walk programs/, validate, assemble lock dict. Returns (lock, hard, warn)."""
    hard: list[str] = []
    warn: list[str] = []
    programs: list[dict] = []
    seen_tags: set[str] = set()
    generated_count = 0

    program_dirs = sorted(d for d in PROGRAMS_DIR.iterdir() if d.is_dir())
    for pdir in program_dirs:
        pid = pdir.name
        prov_path = pdir / "provenance.yaml"
        extr_path = pdir / "extraction.yaml"
        src_dir = pdir / "source"
        gt_dir = pdir / "ground_truth"

        if not prov_path.exists() or not extr_path.exists() or not src_dir.exists():
            hard.append(f"{pid}: missing provenance/extraction/source")
            continue

        prov = _load_yaml(prov_path)
        for req in ("source_url", "commit_sha", "license"):
            if not prov.get(req):
                hard.append(f"{pid}: provenance missing {req}")
        lic = prov.get("license")
        if lic and lic not in LICENSE_ALLOWLIST:
            hard.append(f"{pid}: license {lic!r} not in allow-list")

        for gt in GROUND_TRUTH_FILES:
            gtp = gt_dir / gt
            if not gtp.exists():
                hard.append(f"{pid}: missing ground_truth/{gt}")
            else:
                try:
                    json.loads(gtp.read_text(encoding="utf-8"))
                except json.JSONDecodeError as exc:
                    hard.append(f"{pid}: ground_truth/{gt} is not valid JSON: {exc}")

        tags = list(prov.get("construct_coverage") or [])
        if not tags:
            warn.append(f"{pid}: no construct_coverage tags")
        seen_tags.update(tags)
        if "generated-code" in tags:
            generated_count += 1

        programs.append(
            {
                "id": pid,
                "source_url": prov.get("source_url"),
                "commit_sha": prov.get("commit_sha"),
                "sha256_source_tree": _sha256_dir(src_dir),
                "sha256_ground_truth": _sha256_dir(gt_dir),
                "license": lic,
                "language_level": prov.get("language_level", LANGUAGE_LEVEL),
                "loc": _count_loc(src_dir),
                "construct_coverage": tags,
                "synthetic": bool(prov.get("synthetic", False)),
            }
        )

    # §4.3 tag coverage — v0.1.0 downgrades a shortfall to WARN (documented).
    missing = sorted(REQUIRED_TAGS - seen_tags)
    if missing:
        warn.append(
            f"v0.1.0 missing required construct tags {missing} "
            "(CLAR-CORP-10-java-generated-balance); v1.0.0 must cover all of §4.3."
        )
    # §3.3 generated-code balance.
    if programs:
        frac = generated_count / len(programs)
        if frac < GENERATED_MIN_FRACTION:
            warn.append(
                f"generated-code fraction {frac:.2f} < {GENERATED_MIN_FRACTION} "
                "(DOC §3.3); add more generated-code programs for v1.0.0."
            )

    lock = {
        "corpus_id": CORPUS_ID,
        "corpus_version": CORPUS_VERSION,
        "corpus_digest": "sha256:PENDING",
        "language": LANGUAGE,
        "language_level": LANGUAGE_LEVEL,
        "built_at": _now_utc(),
        "built_by": BUILT_BY,
        "ground_truth_method": (
            "SYNTHESIZED v0.1.0. Programs are hand-authored tiny Java modules; "
            "parse-success is empirically verified with javac (JDK 21, -source 17). "
            "AST detail, CFG, call-graph and PDG dependence edges are derived BY "
            "INSPECTION of the tiny programs, NOT by running the DOC-pinned Soot "
            "4.4.1 / WALA 1.6.5 toolchain (unavailable in this sandbox; "
            "CLAR-CORP-07-java-tooling). JDK is 21, not the pinned 17 "
            "(CLAR-CORP-08-java-jdk). over_approximate edges "
            "(reflective DI, 0-CFA lambda merges) are tagged and MUST be excluded "
            "from precision but included in recall (DOC §3.3). See README.md."
        ),
        "construct_tags_covered": sorted(seen_tags),
        "construct_tags_required": sorted(REQUIRED_TAGS),
        "construct_tags_missing": missing,
        "programs": programs,
    }
    return lock, hard, warn


def canonical_digest(lock: dict) -> str:
    """sha256 over canonical serialization, excluding volatile + digest fields."""
    payload = {
        k: v
        for k, v in lock.items()
        if k not in ("corpus_digest", "built_at", "built_by")
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description="Build/validate the Java CPG-fidelity corpus.lock")
    ap.add_argument("--write", action="store_true", help="write corpus.lock")
    ap.add_argument("--check", action="store_true", help="fail if lock digest drifts (CI)")
    args = ap.parse_args()

    lock, hard, warn = assemble_lock()
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
        existing = _load_yaml(LOCK_PATH)
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
        print(f"programs:       {len(lock['programs'])}")
        return 0

    print(canonical_digest(lock))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
