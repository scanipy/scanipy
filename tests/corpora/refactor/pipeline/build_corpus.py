"""Generate/check real source transformations and an acyclic schema-2 case manifest.

--check hashes current files, not just the already-recorded lock. No scanned
source is executed. --java additionally compiles fixtures with processors off.
"""

from __future__ import annotations

import argparse
import ast
import datetime
import json
import sys
from collections import Counter
from pathlib import Path

import yaml

_PIPE = Path(__file__).resolve().parent
sys.path[:0] = [str(_PIPE), str(_PIPE.parent)]

import refactor_transforms as rt  # noqa: E402
from bases import render  # noqa: E402
from manifest_contract import (  # noqa: E402
    TREE_DIGEST_ALGORITHM,
    canonical_digest,
    json_bytes,
    manifest_bytes,
    safe_relative,
    sha256_bytes,
    tree_digest,
)
from supplemental_cases import build_controls  # noqa: E402
from validate_fixtures import check_java_tree, validate_transformation  # noqa: E402

CORPUS_ROOT = _PIPE.parent
SEEDS_DIR = CORPUS_ROOT / "seeds"
LOCK_PATH = CORPUS_ROOT / "corpus.lock"
MANIFEST_PATH = CORPUS_ROOT / "case-manifest.json"
CORPUS_ID = "CMP-CORP-REFAC-01"
CORPUS_VERSION = "0.2.0"
SCHEMA_VERSION = 2
SEED_COUNT = 50
STAGE_A_CLASSES = {"injection", "path-traversal", "ssrf", "deserialization"}
STAGE_A_LANGUAGES = {"java", "python"}
_sha256_dir = tree_digest


def _load_yaml(path: Path) -> dict:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"not a regular metadata file: {path}")
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected YAML object")
    return value


def _dump_yaml(value: dict) -> str:
    class IndentDumper(yaml.SafeDumper):
        def increase_indent(self, flow=False, indentless=False):
            return super().increase_indent(flow, False)

    return yaml.dump(value, Dumper=IndentDumper, sort_keys=True, allow_unicode=False)


def read_tree(root: Path) -> dict[str, str]:
    tree_digest(root)  # validates containment/symlink policy before reading
    return {
        p.relative_to(root).as_posix(): p.read_text(encoding="utf-8")
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def write_tree(root: Path, files: dict[str, str]) -> None:
    """Own only this generated fixture tree; remove obsolete generated files."""
    root.mkdir(parents=True, exist_ok=True)
    tree_digest(root)
    for relative in files:
        safe_relative(root, relative)
    for old in sorted(root.rglob("*")):
        if old.is_file() and old.relative_to(root).as_posix() not in files:
            old.unlink()
    for relative, source in sorted(files.items()):
        target = safe_relative(root, relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source, encoding="utf-8")


def case_record(
    *,
    case_id: str,
    language: str,
    finding_class: str,
    refactor: str,
    before_dir: str,
    after_dir: str,
    before_locator: dict,
    after_locator: dict | None,
    evidence_type: str,
    expected_outcome: str,
    rationale: str,
    purity: str | None = None,
    seed_id: str | None = None,
    ground_truth: str | None = None,
    subject: str = "corresponding_sink_slice",
) -> dict:
    preconditions = {
        "fixture_syntax": "invalid_after" if evidence_type == "analysis_failure" else "valid",
        "transformation_validation": "valid",
    }
    if purity is not None:
        preconditions["purity_certificate"] = purity
    return {
        "case_id": case_id,
        "seed_id": seed_id,
        "language": language,
        "finding_class": finding_class,
        "refactor": refactor,
        "ground_truth_label": ground_truth,
        "evidence_type": evidence_type,
        "expected_outcome": expected_outcome,
        "required_strength": "strong_strong" if evidence_type == "structural_comparison" else None,
        "before_dir": before_dir,
        "after_dir": after_dir,
        "before_locator": before_locator,
        "after_locator": after_locator,
        "expected_preconditions": preconditions,
        "rationale": rationale,
        "observation_subject": subject,
        "expected_failure": {"stage": "parse", "visible": True, "must_not_resolve": True}
        if evidence_type == "analysis_failure"
        else None,
    }


def primary_metadata(index: int) -> tuple[dict, dict[str, dict[str, str]]]:
    base = render(index)
    sid = f"seed-{index + 1:03d}"
    pairs = []
    trees = {"before": base.files}
    additional = []
    for refactor in rt.REFACTORS:
        result = rt.apply_refactor(base, refactor)
        validate_transformation(base, result)
        after_dir = f"after/{refactor}"
        trees[after_dir] = result.files
        record = case_record(
            case_id=f"{sid}/{refactor}",
            seed_id=sid,
            language=base.language,
            finding_class=base.cls,
            refactor=refactor,
            ground_truth=result.ground_truth_label,
            before_dir=f"seeds/{sid}/before",
            after_dir=f"seeds/{sid}/{after_dir}",
            before_locator=result.before_locator,
            after_locator=result.after_locator,
            evidence_type=result.evidence_type,
            expected_outcome=result.expected_outcome,
            rationale=result.rationale,
            purity=result.expected_purity,
            subject="finding_lifecycle"
            if result.evidence_type == "finding_removal"
            else "corresponding_sink_slice",
        )
        pairs.append({**record, "after_dir": after_dir})
        if refactor == "genuine-fix" and base.cls != "deserialization":
            # The retained API call permits a separate structural comparison,
            # even though a correct detector should no longer report a vulnerability.
            additional.append(
                case_record(
                    case_id=f"{sid}/genuine-fix/structural",
                    seed_id=sid,
                    language=base.language,
                    finding_class=base.cls,
                    refactor="genuine-fix-structural",
                    ground_truth="should-flip",
                    before_dir=f"seeds/{sid}/before",
                    after_dir=f"seeds/{sid}/{after_dir}",
                    before_locator=result.before_locator,
                    after_locator=rt.locate(result.source, result.filename, base.sink_callee),
                    evidence_type="structural_comparison",
                    expected_outcome="flip",
                    rationale=(
                        "Separate sink-slice comparison across a security fix "
                        "retaining the API call. "
                        "This is not evidence that a post-fix vulnerability remains, "
                        "nor a substitute for the primary removal scan."
                    ),
                )
            )
    metadata = {
        "schema_version": SCHEMA_VERSION,
        "seed_id": sid,
        "template_index": index % 8,
        "seed_finding": {
            "class": base.cls,
            "language": base.language,
            "sink_file": base.filename,
            "sink_line": base.sink_line,
            "description": base.source_desc,
        },
        "before_dir": "before",
        "synthesized": True,
        "license": "Apache-2.0",
        "preconditions": list(base.preconditions),
        "refactor_pairs": pairs,
        "additional_evidence_cases": additional,
    }
    return metadata, trees


def generate_seeds() -> None:
    for index in range(SEED_COUNT):
        meta, trees = primary_metadata(index)
        root = SEEDS_DIR / meta["seed_id"]
        for relative, files in trees.items():
            write_tree(root / relative, files)
        (root / "meta.yaml").write_text(_dump_yaml(meta), encoding="utf-8")
    for control in build_controls():
        root = CORPUS_ROOT / "controls" / control.name
        write_tree(root / "before", control.before_files)
        write_tree(root / "after", control.after_files)
    (CORPUS_ROOT / "controls" / "meta.json").write_bytes(json_bytes(control_records()))


def control_records() -> list[dict]:
    return [
        case_record(
            case_id=f"control/{control.name}",
            language=control.language,
            finding_class=control.finding_class,
            refactor=control.name,
            before_dir=f"controls/{control.name}/before",
            after_dir=f"controls/{control.name}/after",
            before_locator=control.before_locator,
            after_locator=control.after_locator,
            evidence_type=control.evidence_type,
            expected_outcome=control.expected_outcome,
            rationale=control.rationale,
            purity=control.expected_purity,
        )
        for control in build_controls()
    ]


def with_tree_digests(case: dict) -> dict:
    return {
        **case,
        "before_tree_digest": tree_digest(safe_relative(CORPUS_ROOT, case["before_dir"])),
        "after_tree_digest": tree_digest(safe_relative(CORPUS_ROOT, case["after_dir"])),
    }


def assemble_case_manifest() -> dict:
    cases = []
    for index in range(SEED_COUNT):
        sid = f"seed-{index + 1:03d}"
        metadata = _load_yaml(SEEDS_DIR / sid / "meta.yaml")
        for pair in metadata["refactor_pairs"]:
            cases.append(
                with_tree_digests({**pair, "after_dir": f"seeds/{sid}/{pair['after_dir']}"})
            )
        cases.extend(with_tree_digests(case) for case in metadata["additional_evidence_cases"])
    controls = json.loads((CORPUS_ROOT / "controls" / "meta.json").read_text())
    cases.extend(with_tree_digests(case) for case in controls)
    ids = [case["case_id"] for case in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate case_id")
    return {
        "schema_version": SCHEMA_VERSION,
        "corpus_id": CORPUS_ID,
        "corpus_version": CORPUS_VERSION,
        "path_base": "corpus_root",
        "tree_digest_algorithm": TREE_DIGEST_ALGORITHM,
        "case_count": len(cases),
        "cases": sorted(cases, key=lambda c: c["case_id"]),
    }


def assemble_lock() -> tuple[dict, list[str], list[str]]:
    hard, seeds = [], []
    expected_seed_ids = {f"seed-{index + 1:03d}" for index in range(SEED_COUNT)}
    if {path.name for path in SEEDS_DIR.iterdir()} != expected_seed_ids:
        hard.append("seed inventory differs from the exact declared seed set")
    for index in range(SEED_COUNT):
        expected_meta, expected_trees = primary_metadata(index)
        sid = expected_meta["seed_id"]
        root = SEEDS_DIR / sid
        actual_meta = _load_yaml(root / "meta.yaml")
        if {path.name for path in (root / "after").iterdir()} != set(rt.REFACTORS):
            hard.append(f"{sid}: after-tree inventory differs from seven declared transforms")
        if actual_meta != expected_meta:
            hard.append(f"{sid}: metadata differs from versioned source methodology")
        for relative, files in expected_trees.items():
            if read_tree(root / relative) != files:
                hard.append(f"{sid}/{relative}: source differs from versioned transform")
        sf = actual_meta["seed_finding"]
        pairs = []
        for pair in actual_meta["refactor_pairs"]:
            pairs.append(
                {
                    "refactor": pair["refactor"],
                    "ground_truth_label": pair["ground_truth_label"],
                    "case_id": pair["case_id"],
                    "evidence_type": pair["evidence_type"],
                    "after_sha256": tree_digest(safe_relative(root, pair["after_dir"])),
                }
            )
        seeds.append(
            {
                "seed_id": sid,
                "class": sf["class"],
                "language": sf["language"],
                "sink_file": sf["sink_file"],
                "sink_line": sf["sink_line"],
                "before_sha256": tree_digest(root / "before"),
                "meta_sha256": sha256_bytes((root / "meta.yaml").read_bytes()),
                "refactor_pairs": pairs,
            }
        )
    controls = build_controls()
    expected_control_names = {control.name for control in controls} | {"meta.json"}
    if {path.name for path in (CORPUS_ROOT / "controls").iterdir()} != expected_control_names:
        hard.append("control inventory differs from the exact declared control set")
    if json.loads((CORPUS_ROOT / "controls" / "meta.json").read_text()) != control_records():
        hard.append("control metadata differs from versioned source methodology")
    for control in controls:
        root = CORPUS_ROOT / "controls" / control.name
        if (
            read_tree(root / "before") != control.before_files
            or read_tree(root / "after") != control.after_files
        ):
            hard.append(f"control/{control.name}: source differs from versioned control")
    manifest = assemble_case_manifest()
    label_counts = Counter(
        pair["ground_truth_label"] for seed in seeds for pair in seed["refactor_pairs"]
    )
    lock = {
        "schema_version": SCHEMA_VERSION,
        "corpus_id": CORPUS_ID,
        "corpus_version": CORPUS_VERSION,
        "corpus_digest": "sha256:PENDING",
        "built_at": datetime.datetime.now(datetime.UTC).isoformat(),
        "built_by": "corpus-curator/BHMEA-361",
        "seed_count": len(seeds),
        "refactor_count": len(rt.REFACTORS),
        "pair_count": sum(len(s["refactor_pairs"]) for s in seeds),
        "distinct_topologies": 8,
        "supplemental_case_count": manifest["case_count"] - SEED_COUNT * 7,
        "case_count": manifest["case_count"],
        "languages": sorted(STAGE_A_LANGUAGES),
        "classes": sorted(STAGE_A_CLASSES),
        "label_distribution": dict(label_counts),
        "refactor_taxonomy": rt.GROUND_TRUTH,
        "annotation_methodology_ref": "annotation-methodology.md",
        "case_manifest_file": "case-manifest.json",
        "case_manifest_sha256": sha256_bytes(manifest_bytes(manifest)),
        "tree_digest_algorithm": TREE_DIGEST_ALGORITHM,
        "evidence_type_distribution": dict(Counter(c["evidence_type"] for c in manifest["cases"])),
        "seeds": seeds,
    }
    return (
        lock,
        hard,
        [
            "50 primary seeds repeat eight base topologies; "
            "supplemental controls are reported separately."
        ],
    )


def _ac_check(lock: dict) -> list[str]:
    errors = []
    for key, value in (("seed_count", 50), ("refactor_count", 7), ("pair_count", 350)):
        if lock[key] != value:
            errors.append(f"{key} {lock[key]} != {value}")
    if lock["label_distribution"] != {"should-stay": 250, "should-flip": 100}:
        errors.append("historical primary label inventory changed")
    return errors


def validate_syntax(manifest: dict, *, java: bool) -> dict:
    results = []
    directories = {}
    for case in manifest["cases"]:
        for side in ("before", "after"):
            relative = case[f"{side}_dir"]
            expected = not (case["evidence_type"] == "analysis_failure" and side == "after")
            previous = directories.setdefault(relative, (case["language"], expected))
            if previous != (case["language"], expected):
                raise ValueError(f"inconsistent syntax expectations for {relative}")
    for relative, (language, expected) in sorted(directories.items()):
        root = CORPUS_ROOT / relative
        if language == "java":
            if not java:
                continue
            observation = check_java_tree(root)
        else:
            try:
                paths = list(root.rglob("*.py"))
                if not paths:
                    raise ValueError("no Python source")
                for path in paths:
                    ast.parse(path.read_text(), filename=str(path))
                observation = {"valid": True, "file_count": len(paths)}
            except SyntaxError as exc:
                observation = {"valid": False, "error": str(exc)}
        results.append(
            {
                "directory": relative,
                "language": language,
                "expected_valid": expected,
                **observation,
                "matches_expectation": observation["valid"] == expected,
            }
        )
    return {
        "kind": "fixture_syntax_validation_not_engine_acceptance",
        "java_checked": java,
        "scanned_source_executed": False,
        "results": results,
        "all_as_expected": all(r["matches_expectation"] for r in results),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument(
        "--syntax", action="store_true", help="validate Python source without execution"
    )
    parser.add_argument(
        "--java",
        action="store_true",
        help="also javac --release17 -proc:none (not Joern acceptance)",
    )
    parser.add_argument("--syntax-report", type=Path)
    args = parser.parse_args()
    try:
        if args.write:
            generate_seeds()
        lock, hard, warnings = assemble_lock()
        hard.extend(_ac_check(lock))
        for warning in warnings:
            print(f"WARNING: {warning}", file=sys.stderr)
        if hard:
            raise ValueError("\n".join(hard))
        manifest = assemble_case_manifest()
        lock["corpus_digest"] = canonical_digest(lock)
        if args.write:
            MANIFEST_PATH.write_bytes(manifest_bytes(manifest))
            LOCK_PATH.write_text(_dump_yaml(lock), encoding="utf-8")
        elif args.check:
            existing = _load_yaml(LOCK_PATH)
            if (
                existing.get("corpus_digest") != canonical_digest(existing)
                or canonical_digest(existing) != lock["corpus_digest"]
            ):
                raise ValueError(
                    "corpus.lock drift: current source/metadata/inventory "
                    "does not match pinned corpus"
                )
            if MANIFEST_PATH.read_bytes() != manifest_bytes(manifest):
                raise ValueError("case-manifest drift")
        if args.syntax or args.java:
            report = validate_syntax(manifest, java=args.java)
            if args.syntax_report:
                args.syntax_report.write_bytes(json_bytes(report))
            if not report["all_as_expected"]:
                raise ValueError(
                    "source syntax validation disagrees with declared case expectations"
                )
            print(f"syntax observations: {len(report['results'])}")
        print(
            f"corpus_version={CORPUS_VERSION} pairs={lock['pair_count']} cases={lock['case_count']}"
        )
        print(f"corpus_digest={lock['corpus_digest']}")
        return 0
    except (ValueError, OSError, KeyError) as exc:
        print(f"CORPUS VALIDATION FAILED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
