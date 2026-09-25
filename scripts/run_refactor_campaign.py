#!/usr/bin/env python3
"""Produce evidence-backed report v2 through real Joern collaborators.

This is a structural measurement producer, not a detector or purity prover.
There is deliberately no parse cache. No code from a corpus is imported or run.
Use the isolated container controller described in the campaign runbook.
"""

from __future__ import annotations

import argparse
import importlib
import importlib.metadata
import json
import math
import os
import re
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic
from typing import Any, Protocol

from analysis.cpg_ingest.joern_frontend import (
    EXPORT_SCRIPT_PATH,
    JoernProcessEvent,
    parse_source,
)
from analysis.cpg_ingest.mapper import SourceLocation, map_export_with_locations
from analysis.fingerprint import SliceFingerprintResult, compute_slice_fingerprint_v2
from analysis.ordering import CPG, DEFAULT_B, DEFAULT_T, Duration, NodeId, Sha256
from scripts.check_refactor_report import (
    ReportError,
    check_files,
    load_corpus,
    policy_digest,
    read_json,
    safe_path,
    sha256_bytes,
    tree_digest,
    validate_policy,
    validate_report,
)
from tools.worker.secure_subprocess import resolve_pinned_binary

REPO = Path(__file__).resolve().parents[1]
JOERN_PATH = "/opt/joern:/opt/joern/bin:/opt/codeql:/opt/temurin-jre/bin:/usr/bin:/bin"
JAVA_HOME = "/opt/temurin-jre"
CONTAINER_PYCACHE = "/tmp/scanipy-refactor-private-bytecode"  # noqa: S108 -- private tmpfs


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def python_cache_observation(*, require_private: bool) -> dict[str, Any]:
    prefix = Path(sys.pycache_prefix) if sys.pycache_prefix else None
    empty = prefix is not None and (not prefix.exists() or not any(prefix.iterdir()))
    safe = bool(prefix and prefix.is_absolute() and not prefix.is_symlink() and empty)
    if require_private and (not sys.dont_write_bytecode or not safe):
        raise ValueError("use Python -B and -X pycache_prefix=<private empty absolute path>")
    return {
        "dont_write_bytecode": sys.dont_write_bytecode,
        "pycache_prefix": str(prefix) if prefix else None,
        "private_cache_empty": empty,
    }


class EvidenceStore:
    """Exclusive-create artifacts; never overwrite an earlier run or raw event."""

    def __init__(self, root: Path) -> None:
        root.mkdir(parents=True, exist_ok=False)
        self.root = root.resolve()

    def bytes(self, name: str, content: bytes) -> dict[str, str]:
        target = safe_path(self.root, name)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(content)
        return {"path": name, "sha256": sha256_bytes(content)}

    def json(self, name: str, value: object) -> dict[str, str]:
        content = (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
        return self.bytes(name, content)


class Backend(Protocol):
    """Test seam. Any supplied backend forces the report to controlled_fixture."""

    def parse(
        self,
        source: Path,
        language: str,
        *,
        env: Mapping[str, str],
        workdir: Path,
        observer: Callable[[JoernProcessEvent], None],
    ) -> CPG: ...

    def fingerprint(
        self, cpg: CPG, sink: NodeId, digest: str, states: int, seconds: float
    ) -> SliceFingerprintResult: ...


@dataclass(frozen=True)
class _SourceWitness:
    witness: tuple[NodeId, ...]
    source_tree_digest: Sha256


class _RealBackend:
    def parse(
        self,
        source: Path,
        language: str,
        *,
        env: Mapping[str, str],
        workdir: Path,
        observer: Callable[[JoernProcessEvent], None],
    ) -> CPG:
        return parse_source(source, language, env=env, workdir=workdir, observer=observer)

    def fingerprint(
        self, cpg: CPG, sink: NodeId, digest: str, states: int, seconds: float
    ) -> SliceFingerprintResult:
        return compute_slice_fingerprint_v2(
            _SourceWitness((sink,), Sha256(bytes.fromhex(digest.removeprefix("sha256:")))),
            cpg,
            B=states,
            T=Duration(seconds),
        )


class LocatorError(ValueError):
    def __init__(self, message: str, *, ambiguous: bool = False) -> None:
        super().__init__(message)
        self.ambiguous = ambiguous


def _relative_location(filename: str, source: Path) -> str | None:
    path = Path(filename)
    if path.is_absolute():
        try:
            return path.relative_to(source).as_posix()
        except ValueError:
            return None
    if ".." in path.parts or not filename:
        return None
    return path.as_posix()


def locate_observed_call(
    source: Path,
    expected: dict[str, Any],
    raw: dict[str, Any],
    cpg: CPG,
    locations: dict[NodeId, SourceLocation],
) -> tuple[NodeId, dict[str, Any], dict[str, Any]]:
    """Bind source text to exactly one raw CALL and exactly one mapped node.

    A filename/line-only first-match lookup is not sufficient. Joern columns
    identify the whole call expression; the manifest column identifies the
    callee token. Both are retained and are not incorrectly equated.
    """
    path = safe_path(source, expected["file"])
    lines = path.read_text(encoding="utf-8").splitlines()
    line_number = expected["line"]
    if line_number > len(lines):
        raise LocatorError("expected line is outside actual source")
    line = lines[line_number - 1]
    calls = list(re.finditer(r"\b" + re.escape(expected["callee"]) + r"\s*\(", line))
    if len(calls) != 1:
        raise LocatorError("source callee token is absent or ambiguous", ambiguous=len(calls) > 1)
    observed = {
        "file": path.relative_to(source).as_posix(),
        "line": line_number,
        "column": calls[0].start() + 1,
        "callee": line[calls[0].start() : calls[0].start() + len(expected["callee"])],
        "call_text": line.strip(),
    }
    if observed != expected:
        raise LocatorError("actual source locator differs from locked manifest")
    compact_line = "".join(line.split())
    candidates = []
    for node in raw.get("nodes", []):
        name, code = node.get("name", ""), node.get("code", "")
        constructor = name == "<init>" and expected["callee"] in code
        if (
            node.get("label") != "CALL"
            or (name != observed["callee"] and not constructor)
            or node.get("lineNumber") != line_number
            or not code
            or "".join(code.split()) not in compact_line
        ):
            continue
        filename = node.get("filename", "")
        if filename and _relative_location(filename, source) != observed["file"]:
            continue
        mapped = [
            item
            for item in cpg.nodes
            if item.kind == "CALL"
            and not item.operator_or_literal
            and item.resolved_fqn == (node.get("methodFullName") or "")
            and item.node_id in locations
            and _relative_location(locations[item.node_id].filename, source) == observed["file"]
            and locations[item.node_id].line == line_number
            and locations[item.node_id].column == (node.get("columnNumber") or 0)
        ]
        if len(mapped) > 1:
            raise LocatorError(
                "multiple mapped CALLs share the observed raw binding", ambiguous=True
            )
        if mapped:
            candidates.append((node, mapped[0]))
    if len(candidates) != 1:
        raise LocatorError(
            "raw/mapped CALL correspondence absent or ambiguous", ambiguous=len(candidates) > 1
        )
    raw_node, mapped_node = candidates[0]
    proof = {
        "source_file_sha256": sha256_bytes(path.read_bytes()),
        "observed_locator": observed,
        "raw_call": raw_node,
        "mapped_node": asdict(mapped_node),
        "mapped_location": asdict(locations[mapped_node.node_id]),
        "raw_candidate_count": 1,
        "mapped_candidate_count": 1,
        "limitation": "Unique source/graph binding, not detection or semantic purity proof.",
    }
    return mapped_node.node_id, observed, proof


def unrun_side(digest: str) -> dict[str, Any]:
    return {
        "source_tree_digest": digest,
        "processing_status": "not_run",
        "reason": "case-side not attempted in this diagnostic/checkpoint",
        "fingerprint": None,
        "locator": {"status": "not_run", "value": None},
        "finding": {"status": "not_run", "id": None, "rule_id": None, "origin": None},
        "scan": {
            "status": "not_run",
            "scan_id": None,
            "source_tree_digest": digest,
            "covered_files": [],
            "covered_rules": [],
            "skipped_files": [],
            "failed_files": [],
        },
        "error": None,
        "evidence": [],
    }


def _process_side(
    case: dict[str, Any],
    side: str,
    *,
    corpus: Path,
    work: Path,
    prefix: str,
    store: EvidenceStore,
    backend: Backend,
    states: int,
    seconds: float,
    runtime_ref: dict[str, str],
) -> dict[str, Any]:
    source = safe_path(corpus, case[f"{side}_dir"]).resolve()
    digest = tree_digest(source)
    if digest != case[f"{side}_tree_digest"]:
        raise ReportError("source changed after corpus validation; no valid report can be emitted")
    result = unrun_side(digest)
    references = result["evidence"]
    references.append(runtime_ref)
    started_at, started = utc_now(), monotonic()
    references.append(
        store.json(
            f"{prefix}/attempt.json",
            {
                "case_id": case["case_id"],
                "side": side,
                "source": str(source),
                "source_tree_digest": digest,
                "started_at": started_at,
                "workdir": str(work),
                "cache_mode": "disabled",
            },
        )
    )
    events: list[JoernProcessEvent] = []

    def observe(event: JoernProcessEvent) -> None:
        events.append(event)
        name = f"{prefix}/process-{len(events):02d}-{event.phase}"
        stdout_ref = store.bytes(name + ".stdout.bin", event.stdout)
        stderr_ref = store.bytes(name + ".stderr.bin", event.stderr)
        metadata = asdict(event)
        metadata["stdout"], metadata["stderr"] = stdout_ref, stderr_ref
        references.extend([stdout_ref, stderr_ref, store.json(name + ".json", metadata)])

    stage = "parse"
    try:
        work.mkdir(parents=True, exist_ok=False)
        env = {"PATH": JOERN_PATH, "JAVA_HOME": JAVA_HOME, "HOME": str(work), "LC_ALL": "C.UTF-8"}
        export_path = work / "cpg_export.json"
        try:
            backend.parse(source, case["language"], env=env, workdir=work, observer=observe)
        finally:
            # Preserve even malformed or partially written export bytes when
            # the production mapper/exporter raises before returning a CPG.
            if export_path.is_file():
                references.append(
                    store.bytes(f"{prefix}/cpg_export.json", export_path.read_bytes())
                )
            cpg_bin = work / "cpg.bin"
            if cpg_bin.is_file():
                references.append(
                    store.json(
                        f"{prefix}/cpg-bin-reference.json",
                        {
                            "path": str(cpg_bin),
                            "size": cpg_bin.stat().st_size,
                            "sha256": sha256_bytes(cpg_bin.read_bytes()),
                            "retention": "Original bytes retained in isolated run work directory.",
                        },
                    )
                )
        raw = read_json(export_path)
        cpg, locations = map_export_with_locations(raw)
        references.append(
            store.json(
                f"{prefix}/mapped.json",
                {
                    "nodes": [asdict(node) for node in cpg.nodes],
                    "edges": [asdict(edge) for edge in cpg.edges],
                    "locations": {str(key): asdict(value) for key, value in locations.items()},
                },
            )
        )
        if case[f"{side}_locator"] is not None:
            stage = "locate"
            sink, locator, proof = locate_observed_call(
                source, case[f"{side}_locator"], raw, cpg, locations
            )
            references.append(store.json(f"{prefix}/correspondence.json", proof))
            result["locator"] = {"status": "matched", "value": locator}
            stage = "fingerprint"
            fingerprint = backend.fingerprint(cpg, sink, digest, states, seconds)
            observed_result = asdict(fingerprint)
            observed_result["slice_fingerprint"] = "sha256:" + fingerprint.slice_fingerprint.hex()
            references.append(store.json(f"{prefix}/fingerprint.json", observed_result))
            result["fingerprint"] = {
                "hash": observed_result["slice_fingerprint"],
                "class": fingerprint.fingerprint_class,
                "namespace": fingerprint.identity_namespace,
            }
        result["processing_status"], result["reason"] = "completed", None
    except Exception as exc:
        # A side failure never suppresses the independent attempt of the other
        # side. Storage errors that prevent evidence capture still propagate.
        result["processing_status"], result["reason"] = "failed", f"{type(exc).__name__}: {exc}"
        result["fingerprint"] = None
        if isinstance(exc, LocatorError):
            result["locator"] = {
                "status": "ambiguous" if exc.ambiguous else "not_found",
                "value": None,
            }
        error_stage = (
            "timeout" if isinstance(exc, TimeoutError | subprocess.TimeoutExpired) else stage
        )
        observed_stage = stage
        if stage == "parse":
            observed_stage = (
                events[-1].phase
                if events and events[-1].error_type is not None
                else "frontend-launch-output-or-map"
            )
        # Report v2 has no export/map error enum. Retain those concrete failures
        # in raw evidence and reason, but never relabel them as the intentional
        # parse-failure control's required error. A failed side may have no
        # normalized error record; it still has mandatory visible evidence.
        result["error"] = (
            None
            if error_stage == "parse" and observed_stage != "parse"
            else {"stage": error_stage, "visible": True}
        )
        references.append(
            store.json(
                f"{prefix}/error.json",
                {
                    "stage": observed_stage,
                    "exception_type": type(exc).__name__,
                    "message": str(exc),
                    "last_process_phase": events[-1].phase if events else None,
                    "note": "Frontend failure is not detector absence or a resolved finding.",
                },
            )
        )
    if tree_digest(source) != digest:
        raise ReportError(
            "source mutated during attempt; retaining diagnostics, refusing final report"
        )
    references.append(
        store.json(
            f"{prefix}/completion.json",
            {
                "started_at": started_at,
                "completed_at": utc_now(),
                "elapsed_seconds": monotonic() - started,
                "processing_status": result["processing_status"],
                "process_event_count": len(events),
            },
        )
    )
    return result


def runtime_observation(context: dict[str, Any], *, require_tools: bool) -> dict[str, Any]:
    """Validate mounted analysis bytes against controller's clean Git checkout."""
    cache = python_cache_observation(require_private=require_tools)
    if require_tools and cache["pycache_prefix"] != CONTAINER_PYCACHE:
        raise ValueError("real campaign requires the controller's isolated bytecode cache prefix")
    if not re.fullmatch(r"[0-9a-f]{40}", str(context.get("code_revision", ""))):
        raise ValueError("controller context lacks exact code revision")
    files = context.get("code_files")
    if not isinstance(files, dict) or not files:
        raise ValueError("controller context lacks analysis source hashes")
    actual = {name: sha256_bytes(safe_path(REPO, name).read_bytes()) for name in files}
    if actual != files:
        raise ValueError("mounted analysis source differs from controller's checkout")
    required = {
        "analysis/fingerprint.py",
        "analysis/ordering.py",
        "analysis/cpg_ingest/mapper.py",
        "analysis/cpg_ingest/joern_frontend.py",
        "tools/worker/secure_subprocess.py",
        "scripts/run_refactor_campaign.py",
        "scripts/check_refactor_report.py",
    }
    if not required <= set(actual):
        raise ValueError("controller omitted a required production collaborator")
    imported_files = {}
    for name in required - {"scripts/run_refactor_campaign.py"}:
        module = importlib.import_module(name.removesuffix(".py").replace("/", "."))
        location = Path(module.__file__ or "").resolve()
        if location != REPO / name:
            raise ValueError(f"production collaborator imported from unexpected path: {name}")
        imported_files[module.__name__] = str(location)
    tools = {}
    if require_tools:
        if sys.version_info < (3, 11):  # noqa: UP036 -- diagnose a misbuilt runtime explicitly
            raise ValueError("Python >= 3.11 required")
        for name in ("joern", "joern-parse"):
            path = Path(resolve_pinned_binary(name))
            if not os.access(path, os.X_OK):
                raise ValueError(f"pinned launcher is not executable: {path}")
            tools[name] = {"path": str(path), "sha256": sha256_bytes(path.read_bytes())}
        java = Path(JAVA_HOME) / "bin/java"
        if not os.access(java, os.X_OK):
            raise ValueError(f"pinned Java launcher is not executable: {java}")
        tools["java"] = {"path": str(java), "sha256": sha256_bytes(java.read_bytes())}
        script = Path(EXPORT_SCRIPT_PATH)
        tools["export_script"] = {"path": str(script), "sha256": sha256_bytes(script.read_bytes())}
    packages = {}
    for name in ("PyYAML", "cryptography"):
        packages[name] = importlib.metadata.version(name)
    return {
        "controller_context": context,
        "python": sys.version,
        "executable": sys.executable,
        "python_cache": cache,
        "code_files": actual,
        "imported_module_files": imported_files,
        "tools": tools,
        "packages": packages,
        "joern_environment": {"PATH": JOERN_PATH, "JAVA_HOME": JAVA_HOME, "LC_ALL": "C.UTF-8"},
        "joern_path_directories": {name: Path(name).is_dir() for name in JOERN_PATH.split(":")},
        "environment_manifest": None,
        "limitation": "Partial runtime observation; not the full analysis environment digest.",
    }


def run_campaign(
    *,
    corpus: Path,
    policy_path: Path,
    output: Path,
    work: Path,
    context: dict[str, Any],
    command: Sequence[str],
    selected: set[str] | None = None,
    states: int = DEFAULT_B,
    seconds: float = DEFAULT_T,
    backend: Backend | None = None,
) -> dict[str, Any]:
    if states < 1 or not math.isfinite(seconds) or seconds <= 0:
        raise ValueError("invalid canonicalization work/deadline budget")
    output, work, corpus = output.absolute(), work.absolute(), corpus.resolve()
    for target in (output, work):
        if target.exists() or target.is_symlink():
            raise ValueError("output and work must be fresh directories")
        if target.parent.resolve() != target.parent:
            raise ValueError("output/work parent must not contain symlinks")
        if target == corpus or corpus in target.parents or target == REPO or REPO in target.parents:
            raise ValueError("output/work must be outside corpus and analysis source")
    if output == work or output in work.parents or work in output.parents:
        raise ValueError("output and work must be disjoint")
    policy = validate_policy(read_json(policy_path))
    cases = load_corpus(corpus, policy)
    if selected is not None and (not selected or not selected <= set(cases)):
        raise ValueError("diagnostic selection must name existing case IDs")
    runtime = runtime_observation(context, require_tools=backend is None)
    work.mkdir(parents=True, exist_ok=False)
    store = EvidenceStore(output)
    runtime["canonicalization"] = {"B": states, "T_seconds": seconds}
    runtime_ref = store.json("runtime.json", runtime)
    store.bytes("case-manifest.json", (corpus / "case-manifest.json").read_bytes())
    store.bytes("corpus.lock", (corpus / "corpus.lock").read_bytes())
    store.bytes("gate-policy.json", policy_path.read_bytes())
    report = {
        "schema_version": 2,
        "gate_policy_id": policy["policy_id"],
        "gate_policy_digest": policy_digest(policy),
        "report_id": output.name,
        "corpus": policy["corpus"],
        "run": {
            "code_revision": context["code_revision"],
            "started_at": utc_now(),
            "completed_at": utc_now(),
            "execution_kind": "real_joern" if backend is None else "controlled_fixture",
            "freshness": "fresh",
            "cache_mode": "disabled",
            "command": list(command),
            "environment_digest": None,
            "environment_manifest": None,
        },
        "cases": [
            {
                "case_id": key,
                "language": case["language"],
                "evidence_type": case["evidence_type"],
                "before": unrun_side(case["before_tree_digest"]),
                "after": unrun_side(case["after_tree_digest"]),
                "correspondence": {"status": "not_run", "evidence": []},
                "observed_preconditions": {
                    key: {"status": "not_run", "producer": None, "evidence": []}
                    for key in case["expected_preconditions"]
                },
                "lifecycle": None,
            }
            for key, case in sorted(cases.items())
        ],
    }
    collaborator = _RealBackend() if backend is None else backend
    store.json("checkpoints/0000.json", report)
    for index, record in enumerate(report["cases"], 1):
        if selected is not None and record["case_id"] not in selected:
            continue
        case = cases[record["case_id"]]
        for side in ("before", "after"):
            prefix = f"attempts/{index:04d}/{side}"
            record[side] = _process_side(
                case,
                side,
                corpus=corpus,
                work=work / prefix,
                prefix=prefix,
                store=store,
                backend=collaborator,
                states=states,
                seconds=seconds,
                runtime_ref=runtime_ref,
            )
        if all(record[side]["locator"]["status"] == "matched" for side in ("before", "after")):
            proof = store.json(
                f"attempts/{index:04d}/pair-correspondence.json",
                {
                    "case_id": record["case_id"],
                    "before": record["before"]["locator"],
                    "after": record["after"]["locator"],
                    "limitation": "Unique source/graph locations only, not semantic equivalence.",
                },
            )
            record["correspondence"] = {"status": "established", "evidence": [proof]}
        elif any(record[side]["locator"]["status"] == "ambiguous" for side in ("before", "after")):
            record["correspondence"] = {"status": "ambiguous", "evidence": []}
        report["run"]["completed_at"] = utc_now()
        store.json(f"checkpoints/{index:04d}.json", report)
        print(
            json.dumps(
                {
                    "case_id": record["case_id"],
                    "completed_case_index": index,
                    "before": record["before"]["processing_status"],
                    "after": record["after"]["processing_status"],
                }
            ),
            flush=True,
        )
    load_corpus(corpus, policy)  # Refuse source/metadata changes during the campaign.
    runtime_observation(context, require_tools=False)  # Refuse analysis source drift too.
    report["run"]["completed_at"] = utc_now()
    validate_report(
        report, policy=policy, cases=cases, corpus_root=corpus, evidence_root=store.root
    )
    store.json("report.json", report)
    store.json(
        "gates.json",
        {
            "baseline": check_files(
                report=store.root / "report.json",
                corpus_root=corpus,
                policy_path=policy_path,
                mode="baseline",
                expected_revision=context["code_revision"],
            ),
            "acceptance": {
                "passed": False,
                "status": "not_run",
                "reason": "Independent checking requires protected history and full proof inputs.",
            },
            "nonregression": {
                "passed": False,
                "status": "not_run",
                "reason": "Protected baseline/improvement reports were not supplied.",
            },
        },
    )
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=REPO / "tests/corpora/refactor")
    parser.add_argument(
        "--policy", type=Path, default=REPO / "docs/bhmea/refactor-gate-policy-v2.json"
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--context", type=Path, required=True)
    parser.add_argument(
        "--case-id", action="append", help="bounded diagnostic only; omitted cases remain not_run"
    )
    parser.add_argument("--states", type=int, default=DEFAULT_B)
    parser.add_argument("--seconds", type=float, default=float(DEFAULT_T))
    parser.add_argument(
        "--execute", action="store_true", help="explicitly authorize Joern tool execution"
    )
    args = parser.parse_args(argv)
    if not args.execute:
        parser.error("--execute is required; use the isolated container controller and runbook")
    try:
        run_campaign(
            corpus=args.corpus.resolve(),
            policy_path=args.policy.resolve(),
            output=args.output,
            work=args.work,
            context=read_json(args.context),
            command=(
                sys.orig_argv
                if argv is None
                else [sys.executable, "-m", "scripts.run_refactor_campaign", *argv]
            ),
            selected=set(args.case_id) if args.case_id else None,
            states=args.states,
            seconds=args.seconds,
        )
    except (OSError, ValueError, importlib.metadata.PackageNotFoundError) as exc:
        print(f"campaign refused/incomplete: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
