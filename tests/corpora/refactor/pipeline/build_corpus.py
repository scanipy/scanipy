"""Build (and validate) tests/corpora/refactor/ for CMP-CORP-REFAC-01.

Responsibilities (DOC-CMP-CORP-REFAC-01 §3, §7; AC-CORP-REFAC-01a/b):
  1. Deterministically (re)generate the 50 seeded findings from the pinned
     synthetic bases (bases/__init__.py), balanced across the four Stage-A
     classes and the two Stage-A languages by round-robin construction.
  2. For each seed, apply each of the 7 named refactors (refactor_transforms.py)
     to produce the before/ -> after/ pair and its ground-truth label.
  3. Validate the AC bar: pair_count == 50 * 7 == 350; every pair has a
     non-empty ground_truth_label drawn from exactly {should-stay, should-flip};
     every should-flip pair's after/ source actually differs from before/.
  4. Emit corpus.lock with corpus_version + corpus_digest, where corpus_digest is
     the sha256 of the CANONICAL serialization (sorted-key JSON of the lock
     content, EXCLUDING volatile built_at/built_by and the digest field), so the
     digest pins the corpus contents, not the wall clock.

Run:  python3 pipeline/build_corpus.py --write    # regenerate seeds + write lock
      python3 pipeline/build_corpus.py --check     # CI: fail on digest drift
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import sys
from pathlib import Path

import yaml

_PIPE = Path(__file__).resolve().parent
sys.path.insert(0, str(_PIPE))
sys.path.insert(0, str(_PIPE.parent))

import refactor_transforms as rt  # noqa: E402
from bases import render  # noqa: E402


class _IndentDumper(yaml.SafeDumper):
    """SafeDumper that indents block sequences under their key (yamllint default)."""

    def increase_indent(self, flow: bool = False, indentless: bool = False):
        return super().increase_indent(flow, False)


def _dump_yaml(doc: dict) -> str:
    return yaml.dump(doc, Dumper=_IndentDumper, sort_keys=True, default_flow_style=False)


CORPUS_ROOT = _PIPE.parent
SEEDS_DIR = CORPUS_ROOT / "seeds"
LOCK_PATH = CORPUS_ROOT / "corpus.lock"

CORPUS_ID = "CMP-CORP-REFAC-01"
CORPUS_VERSION = "0.1.0"  # AC-CORP-REFAC-01a count met (50x7); topology diversity
# capped at 8 templates -> v0.1.0, see CLAR-CORP-04 + README "Status".
BUILT_BY = "corpus-agent/CMP-CORP-REFAC-01"

SEED_COUNT = 50
STAGE_A_CLASSES = {"injection", "path-traversal", "ssrf", "deserialization"}
STAGE_A_LANGUAGES = {"java", "python"}
LICENSE = "Apache-2.0"  # all bases SYNTHESIZED for this corpus


def _sha256_bytes(b: bytes) -> str:
    return "sha256:" + hashlib.sha256(b).hexdigest()


def _sha256_dir(path: Path) -> str:
    """Deterministic sha256 over a tree: sorted relpaths + contents."""
    h = hashlib.sha256()
    for p in sorted(path.rglob("*")):
        if p.is_file():
            h.update(p.relative_to(path).as_posix().encode("utf-8"))
            h.update(b"\0")
            h.update(p.read_bytes())
            h.update(b"\0")
    return "sha256:" + h.hexdigest()


def _write_tree(root: Path, filename: str, source: str) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / filename).write_text(source, encoding="utf-8")


def generate_seeds() -> None:
    """(Re)generate every seed dir with before/, after/ per refactor, and meta.yaml."""
    for idx in range(SEED_COUNT):
        seed_id = f"seed-{idx + 1:03d}"
        base = render(idx)
        seed_dir = SEEDS_DIR / seed_id
        before_dir = seed_dir / "before"
        _write_tree(before_dir, base.filename, base.source)

        refactor_pairs: list[dict] = []
        for refactor in rt.REFACTORS:
            res = rt.apply_refactor(base, refactor)
            after_dir = seed_dir / "after" / refactor
            _write_tree(after_dir, base.filename, res.source)
            refactor_pairs.append(
                {
                    "refactor": refactor,
                    "ground_truth_label": res.ground_truth_label,
                    "rationale": res.rationale,
                    "after_dir": f"after/{refactor}",
                }
            )

        meta = {
            "seed_id": seed_id,
            "seed_finding": {
                "class": base.cls,
                "language": base.language,
                "sink_file": base.filename,
                "sink_line": base.sink_line,
                "description": base.source_desc,
            },
            "before_dir": "before",
            "synthesized": True,
            "license": LICENSE,
            "base_sha256": _sha256_bytes(base.source.encode("utf-8")),
            "refactor_pairs": refactor_pairs,
        }
        (seed_dir / "meta.yaml").write_text(_dump_yaml(meta), encoding="utf-8")


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def assemble_lock() -> tuple[dict, list[str], list[str]]:
    """Walk seeds/, validate, assemble the lock dict. Returns (lock, hard, warn)."""
    hard: list[str] = []
    warn: list[str] = []
    seeds: list[dict] = []
    label_counter: dict[str, int] = {"should-stay": 0, "should-flip": 0}
    class_counter: dict[str, int] = {c: 0 for c in STAGE_A_CLASSES}
    lang_counter: dict[str, int] = {ln: 0 for ln in STAGE_A_LANGUAGES}

    seed_dirs = sorted(d for d in SEEDS_DIR.iterdir() if d.is_dir()) if SEEDS_DIR.exists() else []
    for seed_dir in seed_dirs:
        sid = seed_dir.name
        meta_path = seed_dir / "meta.yaml"
        if not meta_path.exists():
            hard.append(f"{sid}: missing meta.yaml")
            continue
        meta = _load_yaml(meta_path)
        sf = meta.get("seed_finding", {})
        cls = sf.get("class")
        lang = sf.get("language")
        if cls not in STAGE_A_CLASSES:
            hard.append(f"{sid}: class {cls!r} not a Stage-A core class")
        else:
            class_counter[cls] += 1
        if lang not in STAGE_A_LANGUAGES:
            hard.append(f"{sid}: language {lang!r} not Stage-A (java|python)")
        else:
            lang_counter[lang] += 1
        if not meta.get("license"):
            hard.append(f"{sid}: provenance missing license")

        before_dir = seed_dir / "before"
        if not before_dir.exists():
            hard.append(f"{sid}: missing before/ tree")
            continue
        before_sha = _sha256_dir(before_dir)

        pairs = meta.get("refactor_pairs") or []
        seen_refactors = set()
        pair_records: list[dict] = []
        for pair in pairs:
            refactor = pair.get("refactor")
            label = pair.get("ground_truth_label")
            seen_refactors.add(refactor)
            if refactor not in rt.REFACTORS:
                hard.append(f"{sid}/{refactor}: unknown refactor")
            if label not in ("should-stay", "should-flip"):
                hard.append(f"{sid}/{refactor}: bad ground_truth_label {label!r}")
                continue
            if label != rt.GROUND_TRUTH.get(refactor):
                hard.append(
                    f"{sid}/{refactor}: label {label!r} disagrees with methodology "
                    f"{rt.GROUND_TRUTH.get(refactor)!r}"
                )
            label_counter[label] += 1
            after_dir = seed_dir / "after" / refactor
            if not after_dir.exists():
                hard.append(f"{sid}/{refactor}: missing after/ tree")
                continue
            after_sha = _sha256_dir(after_dir)
            # should-flip MUST change the source; should-stay MAY change syntax
            # but the corpus only asserts the flip cases differ (the stay cases'
            # fingerprint stability is the implementation's obligation, not ours).
            if label == "should-flip" and after_sha == before_sha:
                hard.append(f"{sid}/{refactor}: should-flip but after/ == before/")
            pair_records.append(
                {
                    "refactor": refactor,
                    "ground_truth_label": label,
                    "after_sha256": after_sha,
                }
            )

        missing = set(rt.REFACTORS) - seen_refactors
        if missing:
            hard.append(f"{sid}: missing refactors {sorted(missing)}")

        seeds.append(
            {
                "seed_id": sid,
                "class": cls,
                "language": lang,
                "sink_file": sf.get("sink_file"),
                "sink_line": sf.get("sink_line"),
                "license": meta.get("license"),
                "before_sha256": before_sha,
                "refactor_pairs": pair_records,
            }
        )

    pair_count = sum(len(s["refactor_pairs"]) for s in seeds)
    distinct_topologies = len({(s["class"], s["language"]) for s in seeds})

    lock = {
        "corpus_id": CORPUS_ID,
        "corpus_version": CORPUS_VERSION,
        "corpus_digest": "sha256:PENDING",
        "built_at": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "built_by": BUILT_BY,
        "seed_count": len(seeds),
        "refactor_count": len(rt.REFACTORS),
        "pair_count": pair_count,
        # Honesty marker (CLAR-CORP-04): seeds round-robin a small set of base
        # templates, so distinct (class, language) sink-topologies < seed_count.
        # v0.1.0 ships count-complete but topology-thin; v1.0.0 expands diversity.
        "distinct_topologies": distinct_topologies,
        "languages": sorted(STAGE_A_LANGUAGES),
        "classes": sorted(STAGE_A_CLASSES),
        "label_distribution": label_counter,
        "class_distribution": class_counter,
        "language_distribution": lang_counter,
        "refactor_taxonomy": {r: rt.GROUND_TRUTH[r] for r in rt.REFACTORS},
        "annotation_methodology_ref": "annotation-methodology.md",
        "ground_truth_method": (
            "Synthetic seeded-vuln bases (one source->sink slice each) transformed "
            "by deterministic refactor functions. Ground-truth label per refactor is "
            "derived from a documented slice-preservation rule (annotation-methodology.md), "
            "not hand-assigned: should-stay refactors provably preserve the backward "
            "interprocedural slice; should-flip refactors change it."
        ),
        "seeds": seeds,
    }
    return lock, hard, warn


def canonical_digest(lock: dict) -> str:
    """sha256 over canonical serialization, excluding volatile + digest fields."""
    payload = {
        k: v for k, v in lock.items() if k not in ("corpus_digest", "built_at", "built_by")
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _ac_check(lock: dict) -> list[str]:
    """AC-CORP-REFAC-01a hard inventory checks beyond per-seed validation."""
    errs: list[str] = []
    if lock["seed_count"] != SEED_COUNT:
        errs.append(f"seed_count {lock['seed_count']} != {SEED_COUNT}")
    if lock["refactor_count"] != 7:
        errs.append(f"refactor_count {lock['refactor_count']} != 7")
    if lock["pair_count"] != SEED_COUNT * 7:
        errs.append(f"pair_count {lock['pair_count']} != {SEED_COUNT * 7}")
    if lock["label_distribution"]["should-stay"] != SEED_COUNT * 5:
        errs.append("should-stay count != 50*5")
    if lock["label_distribution"]["should-flip"] != SEED_COUNT * 2:
        errs.append("should-flip count != 50*2")
    return errs


def main() -> int:
    ap = argparse.ArgumentParser(description="Build/validate the refactor corpus.lock")
    ap.add_argument("--write", action="store_true", help="regenerate seeds + write lock")
    ap.add_argument("--check", action="store_true", help="fail if lock digest drifts (CI)")
    args = ap.parse_args()

    if args.write:
        generate_seeds()

    lock, hard, warn = assemble_lock()
    hard += _ac_check(lock)
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
        print(f"seeds={lock['seed_count']} pairs={lock['pair_count']}")
        return 0

    print(canonical_digest(lock))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
