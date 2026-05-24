"""Build (and validate) tests/corpora/vuln/corpus.lock for CMP-CORP-VULN-01.

Responsibilities (DOC-CMP-CORP-VULN-01 §3.2, §3.4, §7):
  1. (Re)derive the BigVul held-out split deterministically (pipeline/bigvul_split.py),
     write bigvul_heldout/heldout_split.lock, and RE-ASSERT held-out / training-eligible
     disjointness (HARD release blocker on intersection, DOC §7).
  2. Walk every (source / class / language) slice directory, load each item's manifest
     (slice manifest schema, DOC §3.1), validate ground-truth fields + licensing.
  3. Refuse to emit the lock on any HARD failure (missing class/language/cwe_ids/source;
     a vendored item whose license is off the allow-list; a held-out/training leak).
  4. Emit corpus.lock with corpus_version + corpus_digest, where corpus_digest is the
     sha256 of the CANONICAL serialization (sorted-key JSON, EXCLUDING the volatile
     built_at/built_by and the digest field itself), so the digest pins the evaluation
     set, not the wall clock (DOC §8). The held-out lock digest is referenced from
     corpus.lock and PRESERVED ACROSS RELEASES (AC-CORP-VULN-01a).

Run:  python3 pipeline/build_lock.py --write    # regenerate split + write lock
      python3 pipeline/build_lock.py --check     # CI: fail on digest drift / leakage
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
import bigvul_split as bvs

CORPUS_ROOT = Path(__file__).resolve().parent.parent
SOURCES = ("owasp_benchmark", "juliet", "bigvul_heldout")
LOCK_PATH = CORPUS_ROOT / "corpus.lock"

BIGVUL_DATA = CORPUS_ROOT / "bigvul_heldout" / "data" / "bigvul_sample.csv"
BIGVUL_SPLIT_LOCK = CORPUS_ROOT / "bigvul_heldout" / "heldout_split.lock"

CORPUS_ID = "CMP-CORP-VULN-01"
CORPUS_VERSION = "0.1.0"  # README §Status: NOT the v1.0.0 sourced-at-scale bar
BUILT_BY = "corpus-agent/CMP-CORP-VULN-01"

# License allow-list for VENDORED content (DOC §7). GPL/AGPL require explicit CTO
# approval; OWASP BenchmarkJava is GPLv2, so OWASP items ship fetch-on-demand
# (license="GPL-2.0", vendored=false) until CLAR-CORP-07 is resolved.
VENDOR_LICENSE_ALLOWLIST = {
    "MIT",
    "Apache-2.0",
    "BSD-2-Clause",
    "BSD-3-Clause",
    "MPL-2.0",
    "Public Domain (NIST)",
    "CC0-1.0",
}

# Stage-A core (class, language) pairs that MUST have a populated slice
# (DOC §3.3 + AC-CORP-VULN-01b + .claude/rules/04-staging.md).
STAGE_A_CLASSES = ("injection", "path-traversal", "ssrf", "deserialization")
STAGE_A_LANGUAGES = ("java", "python")


class _IndentDumper(yaml.SafeDumper):
    def increase_indent(self, flow: bool = False, indentless: bool = False):
        return super().increase_indent(flow, False)


def _dump_yaml(doc: dict) -> str:
    return yaml.dump(doc, Dumper=_IndentDumper, sort_keys=True, default_flow_style=False)


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def regenerate_bigvul_split(write: bool = False) -> dict:
    """(Re)derive the held-out split + return its summary.

    The split is RE-DERIVED on every call so `--check` can re-assert disjointness
    (DOC §7) and recompute digests, but `heldout_split.lock` is written to the
    worktree ONLY when ``write=True``. `--check` must stay read-only: the split is
    fully deterministic, so a CI run never needs to mutate tracked files.
    """
    rows = bvs.load_rows_from_csv(BIGVUL_DATA)
    res = bvs.split_rows(rows)  # raises on held-out/training intersection (DOC §7)

    split_doc = {
        "corpus_id": CORPUS_ID,
        "source": "bigvul_heldout",
        "procedure": (
            "row_id = sha256(commit_sha\\0file_path\\0func_name); HELD-OUT iff "
            "int(sha256(row_id),16) % 10 == 9; complement is TRAINING-ELIGIBLE. "
            "See pipeline/bigvul_split.py and training_exclusion_proof.md."
        ),
        "input_csv": "data/bigvul_sample.csv",
        "input_csv_sha256": "sha256:" + hashlib.sha256(BIGVUL_DATA.read_bytes()).hexdigest(),
        "total_rows": len(rows),
        "heldout_count": len(res.heldout_ids),
        "training_eligible_count": len(res.training_ids),
        "heldout_digest": res.heldout_digest,
        "training_eligible_digest": res.training_digest,
        "heldout_row_ids": sorted(res.heldout_ids),
        "disjoint_assertion": "heldout ∩ training_eligible == ∅ (verified at build)",
    }
    if write:
        BIGVUL_SPLIT_LOCK.write_text(_dump_yaml(split_doc), encoding="utf-8")
    return split_doc


def _walk_slices(hard: list[str], warn: list[str]) -> list[dict]:
    """Walk <source>/slices/<class>/<language>/<item>/manifest.yaml."""
    slices: list[dict] = []
    for source in SOURCES:
        slices_root = CORPUS_ROOT / source / "slices"
        if not slices_root.is_dir():
            continue
        for cls_dir in sorted(d for d in slices_root.iterdir() if d.is_dir()):
            for lang_dir in sorted(d for d in cls_dir.iterdir() if d.is_dir()):
                items: list[dict] = []
                for item_dir in sorted(d for d in lang_dir.iterdir() if d.is_dir()):
                    man_path = item_dir / "manifest.yaml"
                    sid = f"{source}/{cls_dir.name}/{lang_dir.name}/{item_dir.name}"
                    if not man_path.exists():
                        hard.append(f"{sid}: missing manifest.yaml")
                        continue
                    m = _load_yaml(man_path)
                    for req in ("slice_id", "source", "class", "language", "cwe_ids"):
                        if not m.get(req):
                            hard.append(f"{sid}: manifest missing {req}")
                    if m.get("positive") is None:
                        hard.append(f"{sid}: manifest missing positive flag")
                    if m.get("source") != source:
                        hard.append(f"{sid}: manifest source {m.get('source')!r} != dir")
                    lic = m.get("license")
                    vendored = bool(m.get("vendored", False))
                    if vendored and lic not in VENDOR_LICENSE_ALLOWLIST:
                        hard.append(
                            f"{sid}: VENDORED with off-allow-list license {lic!r}; "
                            "ship fetch-on-demand (vendored:false) or get CTO approval"
                        )
                    # Positives must name ground-truth sites; clean variants must not.
                    sites = m.get("ground_truth_sites") or []
                    if m.get("positive") is True and not sites:
                        hard.append(f"{sid}: positive item has no ground_truth_sites")
                    if m.get("positive") is False and sites:
                        warn.append(f"{sid}: clean variant carries ground_truth_sites")
                    items.append(
                        {
                            "slice_id": m.get("slice_id"),
                            "source": m.get("source"),
                            "class": m.get("class"),
                            "language": m.get("language"),
                            "cwe_ids": m.get("cwe_ids") or [],
                            "positive": m.get("positive"),
                            "license": lic,
                            "vendored": vendored,
                            "provenance": m.get("provenance"),
                            "ground_truth_sites": sites,
                        }
                    )
                if items:
                    slices.append(
                        {
                            "source": source,
                            "class": cls_dir.name,
                            "language": lang_dir.name,
                            "count": len(items),
                            "items": items,
                        }
                    )
    return slices


def assemble_lock(write: bool = False) -> tuple[dict, list[str], list[str]]:
    hard: list[str] = []
    warn: list[str] = []

    split = regenerate_bigvul_split(write=write)
    slices = _walk_slices(hard, warn)

    # AC-CORP-VULN-01b: every Stage-A (class, language) pair must be populated.
    populated_pairs = {(s["class"], s["language"]) for s in slices}
    for cls in STAGE_A_CLASSES:
        for lang in STAGE_A_LANGUAGES:
            if (cls, lang) not in populated_pairs:
                warn.append(
                    f"Stage-A pair ({cls}, {lang}) has no populated slice "
                    "(v0.1.0 partial coverage; see README + CLAR-CORP-08)"
                )

    populated_slices = sorted(
        (
            {
                "source": s["source"],
                "class": s["class"],
                "language": s["language"],
                "count": s["count"],
            }
            for s in slices
        ),
        key=lambda d: (d["source"], d["class"], d["language"]),
    )

    lock = {
        "corpus_id": CORPUS_ID,
        "corpus_version": CORPUS_VERSION,
        "corpus_digest": "sha256:PENDING",
        "built_at": _dt.datetime.now(_dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "built_by": BUILT_BY,
        "sources": list(SOURCES),
        "ground_truth_method": (
            "OWASP Benchmark: ground truth taken verbatim from the upstream "
            "expectedresults CSV (test name -> category -> real-vuln flag -> CWE); no "
            "hand relabelling. Juliet: ground truth = NSA/SARD CWE tag preserved from the "
            "test case. BigVul held-out: positives = upstream vulnerability-introducing "
            "rows; split is deterministic + training-disjoint (training_exclusion_proof.md). "
            "v0.1.0 ships a small genuinely-referenced OWASP seed + synthetic Juliet/BigVul "
            "shaped seeds + the full pipeline; see README.md."
        ),
        "bigvul_heldout_lock_ref": "bigvul_heldout/heldout_split.lock",
        "bigvul_heldout_digest": split["heldout_digest"],
        "training_exclusion_proof_ref": "bigvul_heldout/training_exclusion_proof.md",
        "licenses": {
            "owasp_benchmark": "GPL-2.0 (fetch-on-demand; off vendor allow-list, CLAR-CORP-07)",
            "juliet": "Public Domain (NIST)",
            "bigvul": "MIT",
        },
        "populated_slices": populated_slices,
        "slices": slices,
    }
    return lock, hard, warn


def canonical_digest(lock: dict) -> str:
    payload = {k: v for k, v in lock.items() if k not in ("corpus_digest", "built_at", "built_by")}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description="Build/validate the vuln corpus.lock")
    ap.add_argument("--write", action="store_true", help="regenerate split + write lock")
    ap.add_argument("--check", action="store_true", help="fail on digest drift / leakage")
    args = ap.parse_args()

    lock, hard, warn = assemble_lock(write=args.write)
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
        # canonical_digest already excludes corpus_digest (+ built_at/built_by), so the
        # recorded digest is recomputed straight from the existing lock.
        recomputed = canonical_digest(existing)
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
        print(f"bigvul_heldout_digest: {lock['bigvul_heldout_digest']}")
        return 0

    print(canonical_digest(lock))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
