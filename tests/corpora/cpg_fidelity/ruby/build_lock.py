"""Build (and validate) tests/corpora/cpg_fidelity/ruby/corpus.lock.

CMP-CORP-CPG-ruby (DOC-CMP-CORP-CPG-ruby SS3.2, SS3.3, SS8).

Responsibilities:
  1. (--write) Re-derive every item's ground-truth AST/CFG/callgraph/PDG from the
     pinned Ruby toolchain via toolchain/derive_ground_truth.rb. Ground truth is
     reproducible-by-construction: a deterministic function of (source bytes,
     ruby version). No hand-asserted labels.
  2. Walk items/, validate each against the schema + the methodology HARD rules
     (DOC SS7 / methodology.md):
       * source/ present and parses (parse-success contributes to gate metric);
       * ground_truth/{ast,cfg,callgraph,pdg}.json all present;
       * license on the allow-list;
       * any item whose callgraph.json has a non-empty `dynamic_sites` MUST carry
         the `dynamic` category tag (INV-6 lower-bound interpretation, DOC SS7 #4).
  3. Refuse to emit the lock on any HARD failure.
  4. Emit corpus.lock with corpus_version + corpus_digest, where corpus_digest is
     the sha256 of the CANONICAL serialization (sorted-key JSON of the lock,
     EXCLUDING the volatile built_at/built_by and the digest field itself).

Run:  python3 build_lock.py --write    # re-derive ground truth + write lock
      python3 build_lock.py --check     # CI: fail on digest drift
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import yaml

CORPUS_ROOT = Path(__file__).resolve().parent
ITEMS_DIR = CORPUS_ROOT / "items"
TOOLCHAIN = CORPUS_ROOT / "toolchain" / "derive_ground_truth.rb"
LOCK_PATH = CORPUS_ROOT / "corpus.lock"

CORPUS_ID = "CORP-CPG-ruby"
CORPUS_VERSION = "0.1.0"  # README SSStatus: NOT the full per-category N bar (CLAR-CORP-15-ruby)
BUILT_BY = "corpus-agent/CMP-CORP-CPG-ruby"
LANGUAGE = "ruby"

# DOC SS7 / methodology.md: redistributable license allow-list.
LICENSE_ALLOWLIST = {"MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "MPL-2.0"}

GROUND_TRUTH_FILES = ("ast.json", "cfg.json", "callgraph.json", "pdg.json")

# Per-item provenance + category labels. SOURCED items pin source_url + commit;
# SYNTHESIZED items are `vendored`. `categories` is the curator's hand label;
# the `dynamic` tag is cross-checked against the derived callgraph (HARD rule).
ITEM_META = {
    "0001-syn-plain-calls": {
        "source": "synthesized", "source_url": "vendored", "source_commit": None,
        "license": "Apache-2.0", "categories": ["plain_calls", "closed_world"],
    },
    "0002-syn-send-dispatch": {
        "source": "synthesized", "source_url": "vendored", "source_commit": None,
        "license": "Apache-2.0", "categories": ["send", "dynamic"],
    },
    "0003-syn-method-missing": {
        "source": "synthesized", "source_url": "vendored", "source_commit": None,
        "license": "Apache-2.0", "categories": ["method_missing", "dynamic"],
    },
    "0004-syn-define-method": {
        "source": "synthesized", "source_url": "vendored", "source_commit": None,
        "license": "Apache-2.0", "categories": ["define_method", "dynamic"],
    },
    "0005-syn-monkey-patch": {
        "source": "synthesized", "source_url": "vendored", "source_commit": None,
        "license": "Apache-2.0", "categories": ["monkey_patch"],
    },
    "0006-syn-blocks-procs-lambdas": {
        "source": "synthesized", "source_url": "vendored", "source_commit": None,
        "license": "Apache-2.0", "categories": ["blocks_procs_lambdas", "dynamic"],
    },
    "0007-syn-active-record-style": {
        "source": "synthesized", "source_url": "vendored", "source_commit": None,
        "license": "Apache-2.0", "categories": ["rails_active_record", "send", "dynamic"],
    },
    "0008-src-sinatra-version": {
        "source": "sourced",
        "source_url": "https://github.com/sinatra/sinatra",
        "source_commit": "7b50a1bbb5324838908dfaa00ec53ad322673a29",
        "license": "MIT", "categories": ["sourced", "closed_world"],
    },
    "0009-src-sinatra-indifferent-hash": {
        "source": "sourced",
        "source_url": "https://github.com/sinatra/sinatra",
        "source_commit": "7b50a1bbb5324838908dfaa00ec53ad322673a29",
        "license": "MIT", "categories": ["sourced", "blocks_procs_lambdas", "dynamic"],
    },
}


class _IndentDumper(yaml.SafeDumper):
    """SafeDumper that indents block sequences under their key (yamllint default)."""

    def increase_indent(self, flow: bool = False, indentless: bool = False):
        return super().increase_indent(flow, False)


def _dump_yaml(doc: dict) -> str:
    return yaml.dump(doc, Dumper=_IndentDumper, sort_keys=True, default_flow_style=False)


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


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


def _source_file(item_dir: Path) -> Path | None:
    src_dir = item_dir / "source"
    if not src_dir.is_dir():
        return None
    rb = sorted(src_dir.glob("*.rb"))
    return rb[0] if rb else None


def derive_ground_truth() -> list[str]:
    """Re-derive ground truth for every item. Returns parse-failure item ids."""
    failures = []
    for item_dir in sorted(ITEMS_DIR.iterdir()):
        if not item_dir.is_dir():
            continue
        src = _source_file(item_dir)
        if src is None:
            failures.append(f"{item_dir.name}: no source/*.rb")
            continue
        gt = item_dir / "ground_truth"
        gt.mkdir(exist_ok=True)
        proc = subprocess.run(
            ["ruby", str(TOOLCHAIN), str(src), str(gt)],
            capture_output=True, text=True, check=False,
        )
        if proc.returncode != 0:
            failures.append(f"{item_dir.name}: parse/derive failed: {proc.stderr.strip()}")
    return failures


def assemble_lock() -> tuple[dict, list[str], list[str]]:
    """Walk items/, validate, assemble the lock dict. Returns (lock, hard, warn)."""
    hard: list[str] = []
    warn: list[str] = []
    items: list[dict] = []
    parsed_ok = 0
    total = 0

    for item_dir in sorted(ITEMS_DIR.iterdir()):
        if not item_dir.is_dir():
            continue
        total += 1
        iid = item_dir.name
        meta = ITEM_META.get(iid)
        if meta is None:
            hard.append(f"{iid}: no ITEM_META entry")
            continue

        src = _source_file(item_dir)
        if src is None:
            hard.append(f"{iid}: missing source/*.rb")
            continue

        gt = item_dir / "ground_truth"
        missing = [f for f in GROUND_TRUTH_FILES if not (gt / f).exists()]
        if missing:
            hard.append(f"{iid}: missing ground_truth {missing}")
            continue
        parsed_ok += 1

        lic = meta["license"]
        if lic not in LICENSE_ALLOWLIST:
            hard.append(f"{iid}: license {lic!r} not in allow-list")

        if meta["source"] == "sourced" and not meta.get("source_commit"):
            hard.append(f"{iid}: sourced item missing source_commit (no floating refs)")

        # HARD rule (DOC SS7 #4 / methodology.md): an item with dynamic-dispatch
        # call sites MUST carry the `dynamic` category tag so the gate harness
        # reads recall as a lower bound (INV-6).
        cg = json.loads((gt / "callgraph.json").read_text(encoding="utf-8"))
        has_dynamic = bool(cg.get("dynamic_sites"))
        tagged_dynamic = "dynamic" in meta["categories"]
        if has_dynamic and not tagged_dynamic:
            hard.append(
                f"{iid}: callgraph has dynamic_sites but item is not tagged `dynamic` "
                "(methodology HARD rule, INV-6)"
            )
        if tagged_dynamic and not has_dynamic:
            warn.append(
                f"{iid}: tagged `dynamic` but derived callgraph has no dynamic_sites"
            )

        items.append(
            {
                "id": iid,
                "source": meta["source"],
                "source_url": meta["source_url"],
                "source_commit": meta["source_commit"],
                "path_in_source": src.name,
                "license": lic,
                "categories": sorted(meta["categories"]),
                "item_digest": _sha256_dir(item_dir),
                "ground_truth_dynamic_sites": len(cg.get("dynamic_sites", [])),
                "ground_truth_call_edges": len(cg.get("edges", [])),
            }
        )

    parse_rate = round(parsed_ok / total, 4) if total else 0.0
    lock = {
        "corpus_id": CORPUS_ID,
        "corpus_version": CORPUS_VERSION,
        "corpus_digest": "sha256:PENDING",
        "built_at": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "built_by": BUILT_BY,
        "language": LANGUAGE,
        "ground_truth_method": (
            "Reproducible-by-construction: AST/CFG/call-graph/PDG derived by the "
            "pinned toolchain/derive_ground_truth.rb over RubyVM::AbstractSyntaxTree "
            "(Ruby %s). Call graph + PDG are a documented LOWER BOUND; dynamic-dispatch "
            "sites are recorded in `dynamic_sites`, never resolved into edges (INV-6). "
            "See methodology.md and README.md for the full procedure and v0.1.0 scope."
            % _ruby_version()
        ),
        "ruby_version": _ruby_version(),
        "parse_success_rate": parse_rate,
        "item_count": len(items),
        "items": items,
    }
    return lock, hard, warn


def _ruby_version() -> str:
    try:
        out = subprocess.run(
            ["ruby", "-e", "print RUBY_VERSION"], capture_output=True, text=True, check=True
        )
    except Exception as exc:
        # methodology.md ties reproducibility to the pinned ruby_version; a silent
        # "unknown" fallback would break that contract. Refuse the build instead.
        sys.exit(f"CORPUS BUILD REFUSED: ruby not found; cannot pin ruby_version ({exc})")
    return out.stdout.strip()


def canonical_digest(lock: dict) -> str:
    payload = {
        k: v for k, v in lock.items()
        if k not in ("corpus_digest", "built_at", "built_by")
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description="Build/validate the Ruby CPG-fidelity corpus.lock")
    ap.add_argument("--write", action="store_true", help="re-derive ground truth + write lock")
    ap.add_argument("--check", action="store_true", help="fail if lock digest drifts (CI)")
    args = ap.parse_args()

    if args.write:
        parse_failures = derive_ground_truth()
        if parse_failures:
            print("CORPUS BUILD REFUSED - ground-truth derivation failures:", file=sys.stderr)
            for e in parse_failures:
                print(f"  - {e}", file=sys.stderr)
            return 2

    lock, hard, warn = assemble_lock()
    for w in warn:
        print(f"[warn] {w}", file=sys.stderr)
    if hard:
        print("CORPUS BUILD REFUSED - HARD validation failures:", file=sys.stderr)
        for e in hard:
            print(f"  - {e}", file=sys.stderr)
        return 2

    lock["corpus_digest"] = canonical_digest(lock)

    if args.check:
        if not LOCK_PATH.exists():
            print("corpus.lock missing; run --write", file=sys.stderr)
            return 3
        existing = _load_yaml(LOCK_PATH)
        # Recompute from the freshly assembled `lock` (fresh item_digests hashed
        # off disk) — NOT from `existing` — so the check detects source-file drift,
        # not merely internal lock self-consistency. `canonical_digest` excludes
        # the volatile `corpus_digest`/`built_at`/`built_by` fields.
        recomputed = canonical_digest(lock)
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
        print(f"parse_success_rate: {lock['parse_success_rate']}")
        return 0

    print(canonical_digest(lock))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
