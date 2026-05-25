"""Build (and validate) tests/corpora/reflection/corpus.lock for CMP-CORP-REFL-01.

Responsibilities (DOC-CMP-CORP-REFL-01 §3.2, §3.5, §7):
  1. Deterministically (re)generate the mutation-injected items from the pinned
     clean bases via pipeline/inject_reflection.py (AC-CORP-REFL-01b).
  2. Walk every category directory, load each item's label.yaml + provenance.yaml,
     validate against the schema + safe-direction invariant (pipeline/label.py).
  3. Refuse to emit the lock on any DOC §7 HARD failure (missing
     sha256/source_url/commit_sha/license; bad license; label/expected_sites
     mismatch; invalid review_status).
  4. Emit corpus.lock with corpus_version + corpus_digest, where corpus_digest is the
     sha256 of the CANONICAL serialization (sorted-key JSON of the lock content,
     EXCLUDING the volatile built_at/built_by and the digest field itself), so the
     digest pins the evaluation set, not the wall clock (DOC §8).

Run:  python3 pipeline/build_lock.py --write    # regenerate items + write lock
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

sys.path.insert(0, str(Path(__file__).resolve().parent))
import inject_reflection as inj  # noqa: E402
from label import counts_toward_hand_bar, validate_label  # noqa: E402


class _IndentDumper(yaml.SafeDumper):
    """SafeDumper that indents block sequences under their key (yamllint default)."""

    def increase_indent(self, flow: bool = False, indentless: bool = False):  # noqa: D401
        return super().increase_indent(flow, False)


def _dump_yaml(doc: dict) -> str:
    """Deterministic, yamllint-clean YAML serialization for corpus artifacts."""
    return yaml.dump(doc, Dumper=_IndentDumper, sort_keys=True, default_flow_style=False)

CORPUS_ROOT = Path(__file__).resolve().parent.parent
CATEGORIES_DIR = CORPUS_ROOT / "categories"
CLEAN_BASES_DIR = CORPUS_ROOT / "clean_bases"
LOCK_PATH = CORPUS_ROOT / "corpus.lock"

CORPUS_ID = "CMP-CORP-REFL-01"
CORPUS_VERSION = "0.1.1"  # README §Status: NOT the v1.0.0 N>=50 hand-curated bar
BUILT_BY = "corpus-agent/CMP-CORP-REFL-01"

LICENSE_ALLOWLIST = {"MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "MPL-2.0"}

# Per-language pinned clean base + how many mutation items to emit.
# CLAR-CORP-01: >= 20 mutation-injected per language.
CLEAN_BASES = {
    "java": ("java/Calculator.java", "Calculator.java"),
    "python": ("python/calculator.py", "calculator.py"),
    "ruby": ("ruby/calculator.rb", "calculator.rb"),
    "php": ("php/Calculator.php", "Calculator.php"),
    "js": ("js/calculator.js", "calculator.js"),
    "go": ("go/calculator.go", "calculator.go"),
}
MUTATION_COUNT_PER_LANG = 20


def _sha256_bytes(b: bytes) -> str:
    return "sha256:" + hashlib.sha256(b).hexdigest()


def _sha256_dir(path: Path) -> str:
    """Deterministic sha256 over a source/ tree: sorted relpaths + contents."""
    h = hashlib.sha256()
    for p in sorted(path.rglob("*")):
        if p.is_file():
            h.update(p.relative_to(path).as_posix().encode("utf-8"))
            h.update(b"\0")
            h.update(p.read_bytes())
            h.update(b"\0")
    return "sha256:" + h.hexdigest()


def generate_mutation_items() -> None:
    """(Re)generate every mutation-injected item from the pinned clean bases."""
    for lang, (base_rel, base_filename) in CLEAN_BASES.items():
        clean_source = (CLEAN_BASES_DIR / base_rel).read_text(encoding="utf-8")
        input_sha = _sha256_bytes(clean_source.encode("utf-8"))
        recipes = inj.recipes_for(lang)
        out_dir = CATEGORIES_DIR / "mutation-injected" / lang
        out_dir.mkdir(parents=True, exist_ok=True)

        for idx in range(MUTATION_COUNT_PER_LANG):
            recipe = recipes[idx % len(recipes)]
            seed = idx
            res = inj.inject(clean_source, lang, seed, recipe)

            item_dir = out_dir / f"{idx + 1:04d}-{lang}-{recipe}"
            (item_dir / "source").mkdir(parents=True, exist_ok=True)
            (item_dir / "source" / base_filename).write_text(res.source, encoding="utf-8")

            label_doc = {
                "label": "not-closed-world",
                "expected_sites": [
                    {"file": base_filename, "line": res.line, "kind": res.kind}
                ],
                "rationale": (
                    f"Mutation-injected {res.kind} reflection construct inserted at "
                    f"line {res.line} of a clean closed-world base. not-closed-world "
                    "by construction (INV-4 safe direction)."
                ),
                "labelled_by": "pipeline",
                "review_status": "single-pass",
            }
            (item_dir / "label.yaml").write_text(
                _dump_yaml(label_doc), encoding="utf-8"
            )
            prov_doc = {
                "source_url": f"local:clean_bases/{base_rel}",
                "commit_sha": input_sha,  # content-addressed; base is in-repo
                # path_in_source records the analysis-scope-relative path: the
                # falsifier (tests/falsifier/cw) derives the CW-DETECT source
                # root from parts[0] of this path, which must be the per-item
                # `source/` directory (README: categories/<cat>/<id>/source/<file>).
                "path_in_source": f"source/{base_filename}",
                "seed": seed,
                "recipe": recipe,
                "input_sha": res.input_sha,
                "license": "Apache-2.0",  # synthetic bases authored for this corpus
                "synthetic": True,
            }
            (item_dir / "provenance.yaml").write_text(
                _dump_yaml(prov_doc), encoding="utf-8"
            )


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _build_category(name, language, kind, cat_dir, hard, warn, items_dirs=None):
    if items_dirs is None:
        items_dirs = sorted(d for d in cat_dir.iterdir() if d.is_dir())
    items: list[dict] = []
    hand_bar_count = 0
    for item_dir in items_dirs:
        label_path = item_dir / "label.yaml"
        prov_path = item_dir / "provenance.yaml"
        src_dir = item_dir / "source"
        iid = f"{name}/{item_dir.name}"
        if not label_path.exists() or not prov_path.exists() or not src_dir.exists():
            hard.append(f"{iid}: missing label/provenance/source")
            continue

        label_doc = _load_yaml(label_path)
        prov = _load_yaml(prov_path)

        for issue in validate_label(iid, label_doc):
            (hard if issue.severity == "hard" else warn).append(
                f"{issue.item_id}: {issue.message}"
            )
        for req in ("source_url", "commit_sha", "license"):
            if not prov.get(req):
                hard.append(f"{iid}: provenance missing {req}")
        lic = prov.get("license")
        if lic and lic not in LICENSE_ALLOWLIST:
            hard.append(f"{iid}: license {lic!r} not in allow-list")

        if counts_toward_hand_bar(label_doc):
            hand_bar_count += 1

        items.append(
            {
                "id": item_dir.name,
                "source_url": prov.get("source_url"),
                "commit_sha": prov.get("commit_sha"),
                "path_in_source": prov.get("path_in_source"),
                "sha256": _sha256_dir(src_dir),
                "license": prov.get("license"),
                "label": label_doc.get("label"),
                "expected_sites": label_doc.get("expected_sites") or [],
            }
        )

    return {
        "name": name,
        "language": language,
        "kind": kind,
        "sample_size": len(items),
        "hand_curated_second_pass": hand_bar_count,
        "items": items,
    }


def assemble_lock() -> tuple[dict, list[str], list[str]]:
    """Walk categories/, validate, assemble lock dict. Returns (lock, hard, warn)."""
    hard: list[str] = []
    warn: list[str] = []
    categories: list[dict] = []

    for cat_dir in sorted(d for d in CATEGORIES_DIR.iterdir() if d.is_dir()):
        if cat_dir.name == "mutation-injected":
            for lang_dir in sorted(d for d in cat_dir.iterdir() if d.is_dir()):
                categories.append(
                    _build_category(
                        # Slash so the falsifier's pathlib join resolves to the
                        # existing nested on-disk tree categories/mutation-injected/<lang>/.
                        f"mutation-injected/{lang_dir.name}",
                        lang_dir.name,
                        "mixed",
                        lang_dir,
                        hard,
                        warn,
                    )
                )
            continue
        lang = cat_dir.name.split("-", 1)[0]
        categories.append(
            _build_category(cat_dir.name, lang, cat_dir.name, cat_dir, hard, warn)
        )

    lock = {
        "corpus_id": CORPUS_ID,
        "corpus_version": CORPUS_VERSION,
        "corpus_digest": "sha256:PENDING",
        "built_at": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "built_by": BUILT_BY,
        "ground_truth_method": (
            "Per-category hand-labelling by Corpus Curator with second-pass review; "
            "mutation-injection ground-truth by construction (a known reflection site "
            "inserted by pipeline/inject_reflection.py at a recorded line). See "
            "README.md for the full methodology and the v0.1.0 scope note."
        ),
        "categories": categories,
    }
    return lock, hard, warn


def canonical_digest(lock: dict) -> str:
    """sha256 over canonical serialization, excluding volatile + digest fields."""
    payload = {
        k: v for k, v in lock.items() if k not in ("corpus_digest", "built_at", "built_by")
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description="Build/validate the reflection corpus.lock")
    ap.add_argument("--write", action="store_true", help="regenerate items + write lock")
    ap.add_argument("--check", action="store_true", help="fail if lock digest drifts (CI)")
    args = ap.parse_args()

    if args.write:
        generate_mutation_items()

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
        return 0

    print(canonical_digest(lock))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
