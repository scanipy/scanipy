"""Build (and validate) tests/corpora/cpg_fidelity/php/corpus.lock for CMP-CORP-CPG-php.

Responsibilities (DOC-CMP-CORP-CPG-php §3.2, §3.3, §7):
  1. Walk every item under items/, load its meta.yaml + ground_truth/*.json + source/.
  2. Validate the DOC §7 HARD rules:
       - source/ present; ground_truth ast/cfg/callgraph/pdg present and valid JSON.
       - meta.yaml carries source_url, source_commit (or 'content-addressed'),
         license on the allow-list, and a non-empty categories list.
       - dynamic-tag invariant (DOC §3.3, §7 "Dynamism mis-labelled" row): an item
         whose callgraph.json declares any dynamic resolution / eval_sites /
         include_sites MUST have meta.dynamic == true; a `pure_php` item MUST have
         meta.dynamic == false and an exact (is_lower_bound == false) call graph.
  3. Emit corpus.lock per the DOC §3.2 schema (corpus_id, corpus_version,
     corpus_digest, language, items[]), where corpus_digest is the sha256 of the
     CANONICAL serialization (sorted-key compact JSON) EXCLUDING the volatile
     built_at/built_by and the digest field itself — so the digest pins the
     evaluation set, not the wall clock (mirrors CMP-CORP-REFL-01 build_lock.py).

Run:  python3 pipeline/build_lock.py --write    # write/refresh the lock
      python3 pipeline/build_lock.py --check     # CI: fail on digest drift / HARD failures
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
    """Deterministic, yamllint-clean YAML serialization for corpus artifacts."""
    return yaml.dump(doc, Dumper=_IndentDumper, sort_keys=True, default_flow_style=False)


CORPUS_ROOT = Path(__file__).resolve().parent.parent
ITEMS_DIR = CORPUS_ROOT / "items"
LOCK_PATH = CORPUS_ROOT / "corpus.lock"

CORPUS_ID = "CORP-CPG-php"
CORPUS_VERSION = "0.1.0"  # README: NOT the v1.0.0 bar (per-category N pinned via CLAR-CORP-16)
LANGUAGE = "php"
BUILT_BY = "corpus-agent/CMP-CORP-CPG-php"

LICENSE_ALLOWLIST = {"MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "MPL-2.0"}
GROUND_TRUTH_FILES = ("ast.json", "cfg.json", "callgraph.json", "pdg.json")


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


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _callgraph_is_dynamic(cg: dict) -> bool:
    if cg.get("dynamic") is True:
        return True
    if cg.get("eval_sites") or cg.get("include_sites"):
        return True
    for edge in cg.get("edges") or []:
        if str(edge.get("resolution", "")).startswith("dynamic"):
            return True
    return False


def _build_item(item_dir: Path, hard: list[str], warn: list[str]) -> dict | None:
    iid = item_dir.name
    meta_path = item_dir / "meta.yaml"
    src_dir = item_dir / "source"
    gt_dir = item_dir / "ground_truth"

    if not meta_path.exists() or not src_dir.exists() or not gt_dir.exists():
        hard.append(f"{iid}: missing meta.yaml/source/ground_truth")
        return None

    meta = _load_yaml(meta_path)

    # Synthesized items are content-addressed: source_commit is the sha256 over
    # the source/ tree (mirrors CMP-CORP-REFL-01). Real OSS items must pin a real
    # upstream commit SHA in meta.yaml (source_commit != "content-addressed").
    declared_commit = meta.get("source_commit")
    if declared_commit == "content-addressed":
        source_commit = _sha256_dir(src_dir)
    else:
        source_commit = declared_commit

    for req in ("source_url", "license"):
        if not meta.get(req):
            hard.append(f"{iid}: meta missing {req}")
    if not source_commit:
        hard.append(f"{iid}: meta missing source_commit")
    lic = meta.get("license")
    if lic and lic not in LICENSE_ALLOWLIST:
        hard.append(f"{iid}: license {lic!r} not in allow-list")
    cats = meta.get("categories") or []
    if not cats:
        hard.append(f"{iid}: meta has no categories")

    gt: dict[str, dict] = {}
    for fname in GROUND_TRUTH_FILES:
        fpath = gt_dir / fname
        if not fpath.exists():
            hard.append(f"{iid}: ground_truth/{fname} missing")
            continue
        try:
            gt[fname] = json.loads(fpath.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            hard.append(f"{iid}: ground_truth/{fname} invalid JSON: {exc}")

    # Dynamic-tag invariant (DOC §3.3, §7).
    cg = gt.get("callgraph.json", {})
    declared_dynamic = bool(meta.get("dynamic"))
    actually_dynamic = _callgraph_is_dynamic(cg)
    if actually_dynamic and not declared_dynamic:
        hard.append(
            f"{iid}: callgraph has dynamic dispatch but meta.dynamic is not true "
            "(DOC §3.3 dynamic-tag invariant)"
        )
    if "pure_php" in cats:
        if declared_dynamic:
            hard.append(f"{iid}: pure_php item must not carry dynamic: true")
        if cg.get("is_lower_bound") is True:
            hard.append(f"{iid}: pure_php callgraph must be exact (is_lower_bound false)")

    return {
        "id": iid,
        "source_url": meta.get("source_url"),
        "source_commit": source_commit,
        "license": meta.get("license"),
        "categories": sorted(cats),
        "dynamic": declared_dynamic,
        "item_digest": _sha256_dir(item_dir),
    }


def assemble_lock() -> tuple[dict, list[str], list[str]]:
    hard: list[str] = []
    warn: list[str] = []
    items: list[dict] = []

    if not ITEMS_DIR.exists():
        hard.append("items/ directory missing")
        return {}, hard, warn

    for item_dir in sorted(d for d in ITEMS_DIR.iterdir() if d.is_dir()):
        built = _build_item(item_dir, hard, warn)
        if built is not None:
            items.append(built)

    if not items:
        warn.append("no items found")

    lock = {
        "corpus_id": CORPUS_ID,
        "corpus_version": CORPUS_VERSION,
        "corpus_digest": "sha256:PENDING",
        "language": LANGUAGE,
        "created_at": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "built_by": BUILT_BY,
        "ground_truth_method": (
            "Hand-derived per the documented procedure in methodology.md, which pins "
            "nikic/PHP-Parser + a CFG/PDG extractor and the PHP toolchain (image digest "
            "TBD pending CMP-SNAP-05). PHP is not on the corpus-build host, so the "
            "ground_truth/*.json files are the persisted projections the CMP-CP-06 "
            "harness compares against; re-derivation under a pinned toolchain bumps "
            "corpus_version. Call graphs over dynamic dispatch are a LOWER BOUND on "
            "recall (PHP dynamism is undecidable); INV-6 applies. See README.md for "
            "the v0.1.0 scope note and SOURCED vs SYNTHESIZED."
        ),
        "items": items,
    }
    return lock, hard, warn


def canonical_digest(lock: dict) -> str:
    """sha256 over canonical serialization, excluding volatile + digest fields."""
    payload = {
        k: v
        for k, v in lock.items()
        if k not in ("corpus_digest", "created_at", "built_by")
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description="Build/validate the PHP CPG-fidelity corpus.lock")
    ap.add_argument("--write", action="store_true", help="write/refresh the lock")
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
        print(f"items:          {len(lock['items'])}")
        return 0

    print(canonical_digest(lock))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
