"""Build (and validate) tests/corpora/cpg_fidelity/go/corpus.lock for CMP-CORP-CPG-go.

Responsibilities (DOC-CMP-CORP-CPG-go §3.2, §3.3, §7):
  1. Walk every item under items/, read its README.md provenance front-matter
     (provenance.yaml) and confirm the tool-derived ground_truth/ artifacts exist
     (ast.json, cfg.json, callgraph.json, pdg.json).
  2. Refuse to emit the lock on any HARD failure: missing ground-truth artifact;
     missing source_url/source_commit/license; license not in the redistribution
     allow-list for a *vendored* item.
  3. Emit corpus.lock with corpus_version + corpus_digest, where corpus_digest is
     the sha256 of the CANONICAL serialization (sorted-key JSON of the lock
     content, EXCLUDING the volatile built_at/built_by and the digest field
     itself), so the digest pins the evaluation set, not the wall clock (DOC §8).

The ground truth itself is NOT produced here: it is derived by the pinned Go
tool tools/derive (go/ast + x/tools/go/ssa + callgraph/cha), recorded in
methodology.md. This script only pins and validates what the deriver emitted.

Run:  python3 pipeline/build_lock.py --write    # write lock from on-disk items
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

    def increase_indent(self, flow: bool = False, indentless: bool = False):  # noqa: D401
        return super().increase_indent(flow, False)


def _dump_yaml(doc: dict) -> str:
    """Deterministic, yamllint-clean YAML serialization for corpus artifacts."""
    return yaml.dump(doc, Dumper=_IndentDumper, sort_keys=True, default_flow_style=False)


CORPUS_ROOT = Path(__file__).resolve().parent.parent
ITEMS_DIR = CORPUS_ROOT / "items"
LOCK_PATH = CORPUS_ROOT / "corpus.lock"

CORPUS_ID = "CORP-CPG-go"
CORPUS_VERSION = "0.1.0"  # README §Status: tool-derived ground truth; not the gate-pass bar
BUILT_BY = "corpus-agent/CMP-CORP-CPG-go"
LANGUAGE = "go"

# Toolchain pins recorded in the lock for reproducibility (methodology.md is the
# authoritative audit trail; these mirror it so the lock is self-describing).
GROUND_TRUTH_TOOLCHAIN = {
    "go": "go1.22.2",
    "x_tools": "v0.21.0",
    "ast_deriver": "go/parser+go/ast",
    "cfg_deriver": "x/tools/go/ssa",
    "callgraph_deriver": "x/tools/go/callgraph/cha",
    "pdg_deriver": "x/tools/go/ssa def-use (intra-procedural data dependence)",
}

# Vendored (redistributed) sources must carry a redistribution-friendly SPDX id.
LICENSE_ALLOWLIST = {"MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "MPL-2.0"}

REQUIRED_GROUND_TRUTH = ("ast.json", "cfg.json", "callgraph.json", "pdg.json")


def _sha256_dir(path: Path) -> str:
    """Deterministic sha256 over a directory tree: sorted relpaths + contents."""
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


def _gt_stats(gt_dir: Path) -> dict:
    """Summarise the tool-derived ground truth: edge/func/node counts.

    These counts are recorded in the lock so an auditor can immediately see an
    under-populated item (e.g. a vacuous 0/0 call graph that would let any
    front-end score a free 100% recall, DOC §5). A `single_function` item with
    0 call edges is legitimately empty; the counts let a reviewer tell the two
    apart instead of trusting a bare `[]`.
    """
    cg = json.loads((gt_dir / "callgraph.json").read_text(encoding="utf-8"))
    edges = cg.get("edges") or []
    dyn = sum(1 for e in edges if e.get("dynamic"))

    cfg = json.loads((gt_dir / "cfg.json").read_text(encoding="utf-8"))
    funcs = cfg.get("funcs") or []

    pdg = json.loads((gt_dir / "pdg.json").read_text(encoding="utf-8"))
    pdg_edges = pdg.get("edges") or []

    ast = json.loads((gt_dir / "ast.json").read_text(encoding="utf-8"))
    ast_files = ast.get("files") or []
    ast_nodes = sum(f.get("total_nodes", 0) for f in ast_files)

    return {
        "call_edges": {"total": len(edges), "dynamic": dyn, "static": len(edges) - dyn},
        "ssa_funcs": len(funcs),
        "pdg_edges": len(pdg_edges),
        "ast_nodes": ast_nodes,
        # Ground truth is `complete` when the deriver processed the item without a
        # load/build error (it exits non-zero otherwise) and wrote all 4 artifacts.
        # `complete` does NOT imply non-empty: a single-function item may have 0
        # call edges. CP-06 must not include an item with 0 ground-truth call
        # edges in its call-edge recall denominator (would be a free pass).
        "status": "complete",
    }


def assemble_lock() -> tuple[dict, list[str]]:
    """Walk items/, validate, assemble the lock dict. Returns (lock, hard_errors)."""
    hard: list[str] = []
    items: list[dict] = []

    for item_dir in sorted(d for d in ITEMS_DIR.iterdir() if d.is_dir()):
        iid = item_dir.name
        src_dir = item_dir / "source"
        gt_dir = item_dir / "ground_truth"
        prov_path = item_dir / "provenance.yaml"

        if not src_dir.is_dir():
            hard.append(f"{iid}: missing source/ directory")
            continue
        if not prov_path.exists():
            hard.append(f"{iid}: missing provenance.yaml")
            continue
        for gt in REQUIRED_GROUND_TRUTH:
            if not (gt_dir / gt).exists():
                hard.append(f"{iid}: missing ground_truth/{gt}")

        prov = _load_yaml(prov_path)
        for req in ("source_url", "source_commit", "license", "origin", "categories"):
            if not prov.get(req):
                hard.append(f"{iid}: provenance missing {req}")

        origin = prov.get("origin")  # SOURCED | SYNTHESIZED
        lic = prov.get("license")
        # Vendored/SOURCED items that are redistributed must carry an allow-listed SPDX id.
        if origin == "SOURCED" and lic and lic not in LICENSE_ALLOWLIST:
            hard.append(f"{iid}: SOURCED license {lic!r} not in redistribution allow-list")

        if hard:
            # Keep collecting per-item errors but skip stat collection on broken items.
            if not (gt_dir / "callgraph.json").exists():
                continue

        stats = (
            _gt_stats(gt_dir)
            if all((gt_dir / g).exists() for g in REQUIRED_GROUND_TRUTH)
            else {"status": "incomplete"}
        )

        items.append(
            {
                "id": iid,
                "source_url": prov.get("source_url"),
                "source_commit": prov.get("source_commit"),
                "license": lic,
                "origin": origin,
                "categories": prov.get("categories") or [],
                "item_digest": _sha256_dir(item_dir),
                "ground_truth": stats,
            }
        )

    lock = {
        "corpus_id": CORPUS_ID,
        "corpus_version": CORPUS_VERSION,
        "corpus_digest": "sha256:PENDING",
        "language": LANGUAGE,
        "created_at": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "built_by": BUILT_BY,
        "ground_truth_toolchain": GROUND_TRUTH_TOOLCHAIN,
        "ground_truth_method": (
            "Ground truth is tool-derived, never hand-labelled (DOC §3.3): AST from "
            "go/parser+go/ast; CFG from x/tools/go/ssa basic blocks; call graph from "
            "x/tools/go/callgraph/cha (recall-safe over-approximation for dynamic "
            "dispatch, matching the Stage-C soundness direction, INV-6); PDG dependence "
            "edges from intra-procedural SSA def-use. Re-derive with tools/derive under "
            "the pinned toolchain. See methodology.md."
        ),
        "items": items,
    }
    return lock, hard


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
    ap = argparse.ArgumentParser(description="Build/validate the Go CPG-fidelity corpus.lock")
    ap.add_argument("--write", action="store_true", help="write lock from on-disk items")
    ap.add_argument("--check", action="store_true", help="fail if lock digest drifts (CI)")
    args = ap.parse_args()

    lock, hard = assemble_lock()
    if hard:
        print("CORPUS BUILD REFUSED — HARD failures:", file=sys.stderr)
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
