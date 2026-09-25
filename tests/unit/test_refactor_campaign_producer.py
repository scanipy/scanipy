"""Controlled orchestration/evidence tests; no real Joern or scanned-code execution."""

from __future__ import annotations

import copy
import json
import os
import py_compile
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from scripts import run_refactor_campaign as campaign
from scripts import run_refactor_campaign_container as controller
from scripts.check_refactor_report import load_corpus, read_json, sha256_bytes, validate_policy

from analysis.cpg_ingest import joern_frontend as frontend
from analysis.cpg_ingest.mapper import map_export, map_export_with_locations
from analysis.ordering import CanonicalizationDeadlineExceeded
from tools.worker.joern_java_safety import JoernEnvironmentProfile

pytestmark = pytest.mark.unit
CORPUS = campaign.REPO / "tests/corpora/refactor"
POLICY = campaign.REPO / "docs/bhmea/refactor-gate-policy-v2.json"


@pytest.fixture(scope="module")
def cases():
    return load_corpus(CORPUS, validate_policy(read_json(POLICY)))


@pytest.fixture
def context():
    names = [
        "analysis/fingerprint.py",
        "analysis/ordering.py",
        "analysis/cpg_ingest/mapper.py",
        "analysis/cpg_ingest/joern_frontend.py",
        "tools/worker/secure_subprocess.py",
        "tools/worker/joern_java_safety.py",
        "scripts/run_refactor_campaign.py",
        "scripts/check_refactor_report.py",
    ]
    return {
        "code_revision": "a" * 40,
        "code_files": {name: sha256_bytes((campaign.REPO / name).read_bytes()) for name in names},
        "note": "controlled test context, not real checkout provenance",
    }


def export_for(locator, *, filename=None, name=None):
    return {
        "nodes": [
            {
                "id": "method",
                "label": "METHOD",
                "filename": filename or locator["file"],
                "lineNumber": 1,
                "columnNumber": 1,
                "fullName": "controlled.method",
            },
            {
                "id": "call",
                "label": "CALL",
                "filename": filename or locator["file"],
                "lineNumber": locator["line"],
                "columnNumber": 1,
                "name": name or locator["callee"],
                "code": locator["call_text"],
                "methodFullName": "<unknownFullName>",
            },
        ],
        "edges": [{"src": "method", "dst": "call", "kind": "AST"}],
    }


class ControlledBackend(campaign._RealBackend):
    def __init__(self, cases, *, fail_before=False, fingerprint_failure=False):
        self.calls = []
        self.fail_before = fail_before
        self.fingerprint_failure = fingerprint_failure
        self.locators = {}
        for case in cases.values():
            for side in ("before", "after"):
                locator = case[f"{side}_locator"]
                if locator is not None:
                    self.locators.setdefault((CORPUS / case[f"{side}_dir"]).resolve(), locator)

    def parse(self, source, language, *, env, workdir, observer):
        self.calls.append((source, language, workdir, dict(env)))
        failed = self.fail_before and len(self.calls) % 2 == 1
        event = frontend.JoernProcessEvent(
            phase="parse",
            tool="joern-parse",
            requested_argv=(str(source),),
            argv=("/opt/joern/joern-parse", str(source)),
            cwd=str(workdir),
            timeout_s=600,
            started_at=campaign.utc_now(),
            completed_at=campaign.utc_now(),
            elapsed_seconds=0.001,
            returncode=7 if failed else 0,
            stdout=b"controlled stdout\x00",
            stderr=b"controlled stderr\xff",
            error_type="CalledProcessError" if failed else None,
            error_message="controlled failure" if failed else None,
        )
        observer(event)
        if failed:
            (workdir / "cpg_export.json").write_bytes(b'{"malformed":')
            raise subprocess.CalledProcessError(
                7, list(event.argv), output=event.stdout, stderr=event.stderr
            )
        locator = self.locators.get(source)
        raw = export_for(locator) if locator else {"nodes": [], "edges": []}
        (workdir / "cpg_export.json").write_text(json.dumps(raw))
        return map_export(raw)

    def fingerprint(self, cpg, sink, digest, states, seconds):
        if self.fingerprint_failure:
            raise CanonicalizationDeadlineExceeded("controlled deadline")
        return super().fingerprint(cpg, sink, digest, states, seconds)


class SharedFrontendBackend(ControlledBackend):
    """Use the production frontend/observer with a hermetic subprocess result."""

    def __init__(self, cases, monkeypatch, *, failure=None, rejected_input=False):
        super().__init__(cases)
        self.process_calls = []
        self.failure = failure
        self.rejected_input = rejected_input
        self.sources = {}
        monkeypatch.setattr(frontend, "secure_run", self.secure_run)

    def secure_run(self, tool, argv, *, timeout_s, env, cwd, environment_profile=None):
        phase = "parse" if tool == "joern-parse" else "export"
        self.process_calls.append((phase, list(argv), dict(env), environment_profile))
        if phase == "parse":
            self.sources[cwd] = Path(argv[4])
            (Path(cwd) / "cpg.bin").write_bytes(b"controlled CPG bytes")
        else:
            locator = self.locators[self.sources[cwd]]
            Path(env[frontend.ENV_EXPORT_JSON_PATH]).write_text(json.dumps(export_for(locator)))
        if self.failure is not None and self.failure[0] == phase:
            raise self.failure[1]
        return subprocess.CompletedProcess(
            ["/opt/joern/" + tool, *argv], 0, b"shared stdout\x00", b"shared stderr\xff"
        )

    def parse(self, source, language, *, env, workdir, observer):
        self.calls.append((source, language, workdir, dict(env)))
        if self.rejected_input:
            env = {**env, "JAVA_TOOL_OPTIONS": "controlled-private-input-never-log"}
        return frontend.parse_source(source, language, env=env, workdir=workdir, observer=observer)


def run(tmp_path, context, cases, selected, *, backend=None):
    backend = backend or ControlledBackend(cases)
    report = campaign.run_campaign(
        corpus=CORPUS,
        policy_path=POLICY,
        output=tmp_path / "evidence",
        work=tmp_path / "work",
        context=context,
        command=["controlled-test"],
        selected=selected,
        backend=backend,
    )
    return report, backend


def first_case(cases, *, kind="structural_comparison", language="python"):
    return next(
        case
        for case in cases.values()
        if case["evidence_type"] == kind and case["language"] == language
    )


def test_subset_keeps_exact_inventory_and_cannot_claim_g0_or_purity(tmp_path, context, cases):
    case = first_case(cases)
    report, backend = run(tmp_path, context, cases, {case["case_id"]})
    assert len(report["cases"]) == 422
    assert len(backend.calls) == 2
    assert report["run"]["execution_kind"] == "controlled_fixture"
    observed = next(row for row in report["cases"] if row["case_id"] == case["case_id"])
    for side in ("before", "after"):
        assert observed[side]["processing_status"] == "completed"
        assert observed[side]["fingerprint"]["namespace"] == "scanipy-slice-normal-form/2"
        assert observed[side]["finding"]["status"] == "not_run"
        assert observed[side]["scan"]["status"] == "not_run"
    assert all(
        value["status"] == "not_run" for value in observed["observed_preconditions"].values()
    )
    assert observed["lifecycle"] is None
    gates = read_json(tmp_path / "evidence/gates.json")
    assert gates["baseline"]["passed"] is False
    assert gates["acceptance"]["passed"] is False
    assert backend.calls[0][3]["PATH"].startswith("/opt/joern:/opt/joern/bin:")


def test_after_attempt_happens_after_before_failure_and_raw_bytes_survive(tmp_path, context, cases):
    case = first_case(cases)
    backend = ControlledBackend(cases, fail_before=True)
    report, backend = run(tmp_path, context, cases, {case["case_id"]}, backend=backend)
    assert len(backend.calls) == 2
    observed = next(row for row in report["cases"] if row["case_id"] == case["case_id"])
    assert observed["before"]["processing_status"] == "failed"
    assert observed["after"]["processing_status"] == "completed"
    assert observed["before"]["fingerprint"] is None
    files = [tmp_path / "evidence" / item["path"] for item in observed["before"]["evidence"]]
    assert any(
        path.name == "cpg_export.json" and path.read_bytes() == b'{"malformed":' for path in files
    )
    assert any(
        path.name.endswith("stdout.bin") and path.read_bytes() == b"controlled stdout\x00"
        for path in files
    )
    assert any(
        path.name.endswith("stderr.bin") and path.read_bytes() == b"controlled stderr\xff"
        for path in files
    )
    assert all(row["after"]["finding"]["status"] != "absent" for row in report["cases"])


@pytest.mark.parametrize("failed_phase", [None, "parse", "export"])
def test_shared_java_effective_profile_is_retained_separately_from_input(
    tmp_path, context, cases, monkeypatch, failed_phase
):
    case = first_case(cases, language="java")
    error = subprocess.CalledProcessError(
        7, ["/opt/joern/joern"], output=b"partial\x00", stderr=b"failure\xff"
    )
    backend = SharedFrontendBackend(
        cases, monkeypatch, failure=(failed_phase, error) if failed_phase else None
    )
    monkeypatch.setenv("JAVA_TOOL_OPTIONS", "controlled-ambient-value-never-log")
    old_umask = os.umask(0)
    try:
        report, _ = run(tmp_path, context, cases, {case["case_id"]}, backend=backend)
    finally:
        os.umask(old_umask)
    row = next(item for item in report["cases"] if item["case_id"] == case["case_id"])
    assert len(backend.calls) == 2
    assert report["run"]["execution_kind"] == "controlled_fixture"
    runtime = read_json(tmp_path / "evidence/runtime.json")
    assert "joern_environment" not in runtime
    assert "JAVASRC_FETCH_DEPENDENCIES" not in runtime["joern_environment_input"]
    assert "tools/worker/joern_java_safety.py" in runtime["code_files"]
    assert "tools.worker.joern_java_safety" in runtime["imported_module_files"]
    for side in ("before", "after"):
        assert row[side]["processing_status"] == ("failed" if failed_phase else "completed")
        refs = row[side]["evidence"]
        attempt = read_json(
            tmp_path
            / "evidence"
            / next(ref["path"] for ref in refs if ref["path"].endswith("/attempt.json"))
        )
        assert attempt["frontend_environment_input"]["HOME"] == attempt["workdir"]
        process_records = [
            read_json(tmp_path / "evidence" / ref["path"])
            for ref in refs
            if "/process-" in ref["path"] and ref["path"].endswith(".json")
        ]
        assert [event["phase"] for event in process_records] == (
            ["parse"] if failed_phase == "parse" else ["parse", "export"]
        )
        for event in process_records:
            observation = event["environment_observation"]
            assert observation["profile"] == JoernEnvironmentProfile.JAVA_STATIC_V1.value
            assert observation["phase"] == event["phase"]
            effective = observation["effective_environment"]
            assert effective["JAVASRC_FETCH_DEPENDENCIES"] == "no-fetch"
            assert effective["HOME"] == str(Path(event["cwd"]) / ".scanipy-java-home")
            assert effective["TMPDIR"] == str(Path(effective["HOME"]) / "tmp")
            assert observation["directories"]["home"]["mode"] == "0700"
            assert observation["directories"]["workdir"]["mode"] == "0700"
            assert "controlled-ambient-value-never-log" not in json.dumps(event)
            if event["phase"] == "parse":
                assert event["requested_argv"][-3:] == [
                    "--frontend-args",
                    "--delombok-mode",
                    "no-delombok",
                ]
            else:
                assert effective["SCANIPY_CPG_BIN_PATH"] == str(Path(event["cwd"]) / "cpg.bin")
            if event["phase"] == failed_phase:
                assert event["returncode"] == 7
                assert (
                    tmp_path / "evidence" / event["stdout"]["path"]
                ).read_bytes() == b"partial\x00"
        assert row[side]["finding"]["status"] == "not_run"
    assert all(call[3] is JoernEnvironmentProfile.JAVA_STATIC_V1 for call in backend.process_calls)


def test_rejected_java_input_has_no_invented_effective_observation_or_private_value(
    tmp_path, context, cases, monkeypatch
):
    case = first_case(cases, language="java")
    backend = SharedFrontendBackend(cases, monkeypatch, rejected_input=True)
    report, _ = run(tmp_path, context, cases, {case["case_id"]}, backend=backend)
    row = next(item for item in report["cases"] if item["case_id"] == case["case_id"])
    assert len(backend.calls) == 2
    assert not backend.process_calls
    assert all(row[side]["processing_status"] == "failed" for side in ("before", "after"))
    assert not list((tmp_path / "evidence").rglob("process-*.json"))
    for path in (tmp_path / "evidence").rglob("*.json"):
        assert "controlled-private-input-never-log" not in path.read_text()


@pytest.mark.parametrize("child_failure", [False, True])
def test_process_evidence_write_loss_is_fatal_even_under_original_child_error(
    tmp_path, context, cases, monkeypatch, child_failure
):
    case = first_case(cases, language="java")
    child = subprocess.CalledProcessError(
        9, ["/opt/joern/joern-parse"], output=b"child-out", stderr=b"child-err"
    )
    backend = SharedFrontendBackend(
        cases, monkeypatch, failure=("parse", child) if child_failure else None
    )
    original_open = Path.open
    failed_paths = []

    def fail_one_write(path, mode="r", *args, **kwargs):
        if mode == "xb" and path.name.endswith(".stdout.bin") and not failed_paths:
            failed_paths.append(path)
            raise OSError("controlled evidence disk failure")
        return original_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", fail_one_write)
    expected = subprocess.CalledProcessError if child_failure else campaign.EvidenceStoreError
    with pytest.raises(expected) as raised:
        run(tmp_path, context, cases, {case["case_id"]}, backend=backend)
    assert campaign._has_evidence_store_error(raised.value)
    if child_failure:
        assert raised.value is child
        assert isinstance(child.__cause__, campaign.EvidenceStoreError)
        assert child.stdout == b"child-out" and child.stderr == b"child-err"
    assert len(backend.calls) == 1  # Infrastructure failure aborts the campaign.
    assert len(failed_paths) == 1  # A later successful write must not mask the first loss.
    assert not (tmp_path / "evidence/report.json").exists()
    assert not (tmp_path / "evidence/gates.json").exists()
    assert (tmp_path / "evidence/checkpoints/0000.json").is_file()


def test_evidence_serialization_and_exception_cycles_are_fail_closed(tmp_path):
    store = campaign.EvidenceStore(tmp_path / "evidence")
    with pytest.raises(campaign.EvidenceStoreError):
        store.json("invalid.json", {"number": float("nan")})
    first, second = RuntimeError("first"), RuntimeError("second")
    first.__cause__, second.__context__ = second, first
    assert not campaign._has_evidence_store_error(first)
    second.__cause__ = campaign.EvidenceStoreError("lost evidence")
    assert campaign._has_evidence_store_error(first)
    grouped = RuntimeError("child with multiple failures")
    grouped.__cause__ = ExceptionGroup("failures", [ValueError("parse"), second])
    assert campaign._has_evidence_store_error(grouped)


@pytest.mark.parametrize("child_failure", [False, True])
@pytest.mark.parametrize(
    ("filename", "operation"),
    [("cpg_export.json", "read_bytes"), ("cpg.bin", "read_bytes"), ("cpg.bin", "stat")],
)
def test_existing_output_observation_failure_is_fatal_and_preserves_child(
    tmp_path, context, cases, monkeypatch, child_failure, filename, operation
):
    case = first_case(cases, language="java")
    child = subprocess.CalledProcessError(9, ["/opt/joern/joern"], stderr=b"export failed")
    backend = SharedFrontendBackend(
        cases, monkeypatch, failure=("export", child) if child_failure else None
    )
    original = getattr(Path, operation)
    failed_paths = []

    def fail_observation(path, *args, **kwargs):
        if (
            len(backend.process_calls) == 2
            and path.name == filename
            and path.is_relative_to(tmp_path / "work")
        ):
            failed_paths.append(path)
            raise PermissionError("controlled output observation failure")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, operation, fail_observation)
    expected = subprocess.CalledProcessError if child_failure else campaign.EvidenceStoreError
    with pytest.raises(expected) as raised:
        run(tmp_path, context, cases, {case["case_id"]}, backend=backend)
    assert campaign._has_evidence_store_error(raised.value)
    if child_failure:
        assert raised.value is child
        assert isinstance(child.__cause__, campaign.EvidenceStoreError)
        assert child.stderr == b"export failed"
    assert len(backend.calls) == 1
    assert failed_paths
    assert not (tmp_path / "evidence/report.json").exists()
    assert not (tmp_path / "evidence/gates.json").exists()


@pytest.mark.parametrize("kind", ["directory", "symlink"])
def test_output_retention_rejects_existing_nonregular_output(tmp_path, kind):
    work = tmp_path / "work"
    work.mkdir()
    output = work / "cpg.bin"
    if kind == "directory":
        output.mkdir()
    else:
        output.symlink_to(tmp_path / "missing")
    with pytest.raises(campaign.EvidenceStoreError, match="required Joern output evidence"):
        campaign._retain_parse_outputs(
            work, "case", campaign.EvidenceStore(tmp_path / "evidence"), []
        )


@pytest.mark.parametrize("error_type", [OSError, ValueError])
def test_cli_preserves_evidence_failure_chain(tmp_path, monkeypatch, error_type):
    child = error_type("controlled frontend failure")
    evidence = campaign.EvidenceStoreError("controlled required evidence loss")

    def fail(**kwargs):
        raise child from evidence

    monkeypatch.setattr(campaign, "run_campaign", fail)
    monkeypatch.setattr(campaign, "read_json", lambda path: {})
    with pytest.raises(error_type) as raised:
        campaign.main(
            [
                "--execute",
                "--output",
                str(tmp_path / "evidence"),
                "--work",
                str(tmp_path / "work"),
                "--context",
                str(tmp_path / "context.json"),
            ]
        )
    assert raised.value is child and child.__cause__ is evidence


def test_child_observer_and_output_read_failures_all_survive(tmp_path, context, cases, monkeypatch):
    case = first_case(cases, language="java")
    child = subprocess.CalledProcessError(9, ["/opt/joern/joern-parse"], stderr=b"parse failed")
    backend = SharedFrontendBackend(cases, monkeypatch, failure=("parse", child))
    original_open, original_read = Path.open, Path.read_bytes

    def fail_write(path, mode="r", *args, **kwargs):
        if mode == "xb" and path.name.endswith(".stdout.bin"):
            raise OSError("controlled process-evidence failure")
        return original_open(path, mode, *args, **kwargs)

    def fail_read(path):
        if path.name == "cpg.bin" and path.is_relative_to(tmp_path / "work"):
            raise PermissionError("controlled binary-evidence failure")
        return original_read(path)

    monkeypatch.setattr(Path, "open", fail_write)
    monkeypatch.setattr(Path, "read_bytes", fail_read)
    with pytest.raises(subprocess.CalledProcessError) as raised:
        run(tmp_path, context, cases, {case["case_id"]}, backend=backend)
    assert raised.value is child
    assert isinstance(child.__cause__, ExceptionGroup)
    assert len(child.__cause__.exceptions) == 2
    assert all(
        isinstance(error, campaign.EvidenceStoreError) for error in child.__cause__.exceptions
    )
    assert campaign._has_evidence_store_error(child)
    assert child.stderr == b"parse failed"
    assert not (tmp_path / "evidence/report.json").exists()


def test_runtime_rejects_missing_java_safety_code_binding(context):
    del context["code_files"]["tools/worker/joern_java_safety.py"]
    with pytest.raises(ValueError, match="omitted a required production collaborator"):
        campaign.runtime_observation(context, require_tools=False)


@pytest.mark.parametrize("kind", ["finding_removal", "analysis_failure"])
def test_no_after_locator_still_parses_and_does_not_fabricate_absence_or_failure(
    tmp_path, context, cases, kind
):
    case = first_case(cases, kind=kind)
    report, backend = run(tmp_path, context, cases, {case["case_id"]})
    observed = next(row for row in report["cases"] if row["case_id"] == case["case_id"])
    assert len(backend.calls) == 2
    assert observed["after"]["processing_status"] == "completed"
    assert observed["after"]["fingerprint"] is None
    assert observed["after"]["error"] is None
    assert observed["after"]["finding"]["status"] == "not_run"
    assert observed["lifecycle"] is None


def test_fingerprint_deadline_is_failure_not_weak_success(tmp_path, context, cases):
    case = first_case(cases)
    report, _ = run(
        tmp_path,
        context,
        cases,
        {case["case_id"]},
        backend=ControlledBackend(cases, fingerprint_failure=True),
    )
    observed = next(row for row in report["cases"] if row["case_id"] == case["case_id"])
    assert all(observed[side]["fingerprint"] is None for side in ("before", "after"))
    assert all(
        observed[side]["error"] == {"stage": "timeout", "visible": True}
        for side in ("before", "after")
    )


def test_export_failure_is_not_retyped_as_intentional_parse_failure(tmp_path, context, cases):
    case = first_case(cases, kind="analysis_failure")

    class ExportFailure(ControlledBackend):
        def parse(self, source, language, *, env, workdir, observer):
            super().parse(source, language, env=env, workdir=workdir, observer=observer)
            observer(
                frontend.JoernProcessEvent(
                    phase="export",
                    tool="joern",
                    requested_argv=("--script", "trusted.sc"),
                    argv=("/opt/joern/joern", "--script", "trusted.sc"),
                    cwd=str(workdir),
                    timeout_s=300,
                    started_at=campaign.utc_now(),
                    completed_at=campaign.utc_now(),
                    elapsed_seconds=0.01,
                    returncode=9,
                    stdout=b"",
                    stderr=b"export exception",
                    error_type="CalledProcessError",
                    error_message="export exception",
                )
            )
            raise subprocess.CalledProcessError(9, ["/opt/joern/joern"])

    report, _ = run(tmp_path, context, cases, {case["case_id"]}, backend=ExportFailure(cases))
    observed = next(row for row in report["cases"] if row["case_id"] == case["case_id"])
    assert observed["after"]["processing_status"] == "failed"
    assert observed["after"]["error"] is None
    error_ref = next(
        ref for ref in observed["after"]["evidence"] if ref["path"].endswith("/error.json")
    )
    assert read_json(tmp_path / "evidence" / error_ref["path"])["stage"] == "export"


def test_full_inventory_attempts_all_844_sides_without_reusing_source_parses(
    tmp_path, context, cases, monkeypatch
):
    # Checkpoints are irrelevant to this call-count test; avoid hundreds of MB
    # of repeated JSON while retaining every real per-attempt/final test artifact.
    original = campaign.EvidenceStore.json

    def without_checkpoints(self, name, value):
        if name.startswith("checkpoints/"):
            return {"path": name, "sha256": "sha256:" + "0" * 64}
        return original(self, name, value)

    monkeypatch.setattr(campaign.EvidenceStore, "json", without_checkpoints)
    report, backend = run(
        tmp_path, context, cases, None, backend=ControlledBackend(cases, fail_before=True)
    )
    assert len(report["cases"]) == 422
    assert len(backend.calls) == 844
    assert len({call[2] for call in backend.calls}) == 844
    assert len({call[0] for call in backend.calls}) == 468
    assert all(
        row[side]["processing_status"] != "not_run"
        for row in report["cases"]
        for side in ("before", "after")
    )


def test_dirty_runtime_and_invalid_selection_are_refused_before_work(tmp_path, context, cases):
    context["code_files"]["analysis/fingerprint.py"] = "sha256:" + "0" * 64
    with pytest.raises(ValueError, match="differs"):
        run(tmp_path, context, cases, {first_case(cases)["case_id"]})
    assert not (tmp_path / "work").exists()
    with pytest.raises(ValueError, match="existing case"):
        run(tmp_path, context, cases, {"invented-case"})


def test_existing_output_is_never_overwritten(tmp_path, context, cases):
    output = tmp_path / "evidence"
    output.mkdir()
    (output / "keep").write_bytes(b"unaltered")
    with pytest.raises(ValueError, match="fresh"):
        run(tmp_path, context, cases, {first_case(cases)["case_id"]})
    assert (output / "keep").read_bytes() == b"unaltered"


def test_source_and_graph_locator_binding_handles_absolute_path_and_distinct_columns(cases):
    case = first_case(cases)
    source = (CORPUS / case["before_dir"]).resolve()
    locator = case["before_locator"]
    raw = export_for(locator, filename=str(source / locator["file"]))
    cpg, locations = map_export_with_locations(raw)
    _, observed, proof = campaign.locate_observed_call(source, locator, raw, cpg, locations)
    assert observed == locator
    assert proof["mapped_location"]["column"] == 1
    assert observed["column"] != 1


@pytest.mark.parametrize(
    "mutation", ["duplicate", "wrong-callee", "operator", "wrong-source", "outside-file"]
)
def test_ambiguous_or_noncorresponding_calls_are_not_fingerprinted(cases, mutation):
    case = first_case(cases)
    source = (CORPUS / case["before_dir"]).resolve()
    expected = copy.deepcopy(case["before_locator"])
    raw = export_for(expected)
    if mutation == "duplicate":
        duplicate = {**raw["nodes"][1], "id": "other"}
        raw["nodes"].append(duplicate)
        raw["edges"].append({"src": "method", "dst": "other", "kind": "AST"})
    elif mutation == "wrong-callee":
        raw["nodes"][1]["name"] = "different"
    elif mutation == "operator":
        raw["nodes"][1]["name"] = "<operator>.assignment"
    elif mutation == "wrong-source":
        expected["call_text"] += " # invented"
    else:
        raw["nodes"][1]["filename"] = "/outside/source.py"
    cpg, locations = map_export_with_locations(raw)
    with pytest.raises(campaign.LocatorError):
        campaign.locate_observed_call(source, expected, raw, cpg, locations)


def test_constructor_binding_requires_class_named_in_actual_code(cases):
    case = next(
        case for case in cases.values() if case["before_locator"]["callee"] == "FileInputStream"
    )
    source = (CORPUS / case["before_dir"]).resolve()
    raw = export_for(case["before_locator"], name="<init>")
    cpg, locations = map_export_with_locations(raw)
    campaign.locate_observed_call(source, case["before_locator"], raw, cpg, locations)
    raw["nodes"][1]["code"] = "OtherClass()"
    with pytest.raises(campaign.LocatorError):
        campaign.locate_observed_call(source, case["before_locator"], raw, cpg, locations)


def test_frontend_observer_preserves_actual_secure_run_results(tmp_path, monkeypatch):
    events = []
    commands = []

    def fake_run(tool, argv, *, timeout_s, env, cwd, environment_profile=None):
        commands.append((tool, argv, timeout_s, env, cwd))
        if tool == "joern":
            Path(env[frontend.ENV_EXPORT_JSON_PATH]).write_text('{"nodes":[],"edges":[]}')
        return subprocess.CompletedProcess(["/opt/joern/" + tool, *argv], 0, b"raw\x00", b"err\xff")

    monkeypatch.setattr(frontend, "secure_run", fake_run)
    frontend.parse_source(
        tmp_path / "source",
        "python",
        env={"SECRET": "not-observed"},  # pragma: allowlist secret -- controlled redaction probe
        workdir=tmp_path / "work",
        observer=events.append,
    )
    assert [event.phase for event in events] == ["parse", "export"]
    assert events[0].argv[0] == "/opt/joern/joern-parse"
    assert all(event.stdout == b"raw\x00" and event.stderr == b"err\xff" for event in events)
    assert [item[2] for item in commands] == [600, 300]
    assert "not-observed" not in repr(events)


@pytest.mark.parametrize(
    "error",
    [
        subprocess.CalledProcessError(9, ["/opt/joern/joern-parse"], output=b"out", stderr=b"err"),
        subprocess.TimeoutExpired(
            ["/opt/joern/joern-parse"], 600, output=b"partial", stderr=b"slow"
        ),
        FileNotFoundError("launcher absent"),
    ],
)
def test_frontend_observer_retains_errors_without_changing_them(tmp_path, monkeypatch, error):
    events = []

    def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr(frontend, "secure_run", fail)
    with pytest.raises(type(error)) as observed:
        frontend.parse_source(
            tmp_path / "source", "python", env={}, workdir=tmp_path / "work", observer=events.append
        )
    assert observed.value is error
    assert len(events) == 1
    assert events[0].error_type == type(error).__name__
    assert (
        events[0].argv is None
        if isinstance(error, FileNotFoundError)
        else events[0].argv[0] == "/opt/joern/joern-parse"
    )


def test_frontend_observer_failure_is_not_silently_ignored(tmp_path, monkeypatch):
    monkeypatch.setattr(
        frontend,
        "secure_run",
        lambda *args, **kwargs: subprocess.CompletedProcess(["actual"], 0, b"", b""),
    )

    def reject(event):
        raise OSError("evidence disk full")

    with pytest.raises(OSError, match="disk full"):
        frontend.parse_source(
            tmp_path / "source", "python", env={}, workdir=tmp_path / "work", observer=reject
        )


def test_container_command_is_explicit_pinned_nonroot_isolated_and_uncached(tmp_path):
    argv = controller.container_command(
        docker="/usr/bin/docker",
        image_id="sha256:" + "1" * 64,
        name="scanipy-refactor-campaign-test-001",
        repo=campaign.REPO,
        output=tmp_path,
        uid=1000,
        gid=1000,
        selected=["control/python-parser-failure"],
        states=65536,
        seconds=0.2,
    )
    assert argv[:2] == ["/usr/bin/docker", "create"]
    for flag, value in {
        "--network": "none",
        "--cpus": "2",
        "--memory": "4g",
        "--memory-swap": "4g",
        "--pids-limit": "256",
        "--user": "1000:1000",
        "--cap-drop": "ALL",
    }.items():
        assert argv[argv.index(flag) + 1] == value
    assert "--read-only" in argv and "--privileged" not in argv and "--rm" not in argv
    assert f"type=bind,src={campaign.REPO},dst=/workspace,readonly" in argv
    assert not any("docker.sock" in item for item in argv)
    assert "--case-id" in argv
    assert f"PYTHONPYCACHEPREFIX={campaign.CONTAINER_PYCACHE}" in argv
    assert "PYTHONDONTWRITEBYTECODE=1" in argv


@pytest.mark.parametrize(
    "field,value", [("image_id", "worker:latest"), ("name", "scanipy-app"), ("uid", 0)]
)
def test_controller_rejects_unpinned_broad_or_root_targets(tmp_path, field, value):
    args = {
        "docker": "/usr/bin/docker",
        "image_id": "sha256:" + "1" * 64,
        "name": "scanipy-refactor-campaign-test-001",
        "repo": campaign.REPO,
        "output": tmp_path,
        "uid": 1000,
        "gid": 1000,
        "selected": [],
        "states": 65536,
        "seconds": 0.2,
    }
    args[field] = value
    with pytest.raises(ValueError):
        controller.container_command(**args)


def test_host_resource_sample_does_not_assert_presentation_identity(tmp_path, monkeypatch):
    def meminfo(path):
        assert path == "/proc/meminfo"
        return SimpleNamespace(read_text=lambda: "MemAvailable: 8388608 kB\n")

    monkeypatch.setattr(controller, "Path", meminfo)
    monkeypatch.setattr(controller.os, "cpu_count", lambda: 32)
    monkeypatch.setattr(controller.shutil, "disk_usage", lambda _: SimpleNamespace(free=42))
    monkeypatch.setattr(controller, "utc_now", lambda: "2026-09-25T14:00:00Z")
    assert controller.host_resources(tmp_path) == {
        "observed_at": "2026-09-25T14:00:00Z",
        "cpu_count": 32,
        "available_memory_bytes": 8 * controller.GIB,
        "disk_free_bytes": 42,
        "host_role": "observed launch host; compare with owner-confirmed presentation evidence",
    }


@pytest.mark.parametrize(
    "key,value",
    [
        ("available_memory_bytes", 5 * controller.GIB),
        ("disk_free_bytes", 19 * controller.GIB),
        ("cpu_count", 1),
    ],
)
def test_controller_stops_without_safe_resources(key, value):
    resources = {
        "available_memory_bytes": 6 * controller.GIB,
        "disk_free_bytes": 20 * controller.GIB,
        "cpu_count": 2,
    }
    resources[key] = value
    with pytest.raises(ValueError):
        controller.require_resources(resources)


@pytest.mark.parametrize("scenario", ["complete", "disk-reserve", "wrong-label"])
def test_controller_only_stops_or_removes_its_verified_created_id(tmp_path, monkeypatch, scenario):
    image_id = "sha256:" + "1" * 64
    container_id = "2" * 64
    name = "scanipy-refactor-campaign-lifecycle-001"
    calls = []
    inspections = 0
    resources = {
        "available_memory_bytes": 6 * controller.GIB,
        "disk_free_bytes": 20 * controller.GIB,
        "cpu_count": 2,
    }
    monkeypatch.setattr(controller, "host_resources", lambda path: resources)
    monkeypatch.setattr(controller.shutil, "which", lambda tool: "/usr/bin/" + tool)
    monkeypatch.setattr(
        controller.shutil, "disk_usage", lambda path: SimpleNamespace(free=4 * controller.GIB)
    )
    monkeypatch.setattr(controller.os, "getuid", lambda: 1000)
    monkeypatch.setattr(controller.os, "getgid", lambda: 1000)
    monkeypatch.setattr(controller, "sleep", lambda seconds: None)
    monkeypatch.setattr(
        controller,
        "clean_checkout_context",
        lambda repo, image: {"code_revision": "a" * 40, "code_files": {}, "image": image},
    )

    def fake_run(argv, **kwargs):
        nonlocal inspections
        calls.append(argv)
        operation = argv[1]
        output = b""
        if operation == "image":
            output = json.dumps([{"Id": image_id}]).encode()
        elif operation == "create":
            output = container_id.encode() + b"\n"
        elif operation == "inspect":
            inspections += 1
            output = json.dumps(
                [
                    {
                        "Id": container_id,
                        "Config": {
                            "Labels": {
                                controller.LABEL: "not-ours" if scenario == "wrong-label" else name
                            }
                        },
                        "State": {
                            "Running": scenario != "complete" and inspections == 1,
                            "ExitCode": 0,
                        },
                    }
                ]
            ).encode()
        elif operation == "logs":
            output = b"actual controlled process logs\x00"
        elif operation == "ps":
            output = b"existing-app\texisting-db\n"
        return subprocess.CompletedProcess(argv, 0, output, b"")

    monkeypatch.setattr(controller.subprocess, "run", fake_run)
    args = {
        "repo": campaign.REPO,
        "output": tmp_path / "run",
        "image_id": image_id,
        "name": name,
        "selected": [],
        "states": 65536,
        "seconds": 0.2,
        "maximum_seconds": 1200,
        "execute": True,
    }
    if scenario == "wrong-label":
        with pytest.raises(ValueError, match="ownership mismatch"):
            controller.run_container(**args)
        assert not any(call[1] in {"stop", "rm"} for call in calls)
    else:
        assert controller.run_container(**args) == (2 if scenario == "disk-reserve" else 0)
        assert [call for call in calls if call[1] == "rm"] == [
            ["/usr/bin/docker", "rm", container_id]
        ]
        stops = [call for call in calls if call[1] == "stop"]
        assert stops == (
            [["/usr/bin/docker", "stop", "--time", "10", container_id]]
            if scenario == "disk-reserve"
            else []
        )
    assert read_json(tmp_path / "run/container-id.json")["container_id"] == container_id
    assert (tmp_path / "run/controller-context.json").is_file()
    assert (tmp_path / "run/data").is_dir()
    create = next(call for call in calls if call[1] == "create")
    assert (
        f"type=bind,src={tmp_path / 'run/controller-context.json'},"
        "dst=/controller-context.json,readonly" in create
    )
    assert not any(call[1] in {"kill", "restart", "pull", "build"} for call in calls)


def test_private_prefix_avoids_valid_but_stale_source_adjacent_bytecode(tmp_path):
    # Executes only this trusted constant-valued test module, never corpus code.
    source = tmp_path / "controlled_cache_probe.py"
    source.write_text("value = 'old'\n")
    original = source.stat()
    py_compile.compile(str(source), doraise=True)
    source.write_text("value = 'new'\n")
    os.utime(source, ns=(original.st_atime_ns, original.st_mtime_ns))
    argv = [
        sys.executable,
        "-B",
        "-c",
        "import controlled_cache_probe; print(controlled_cache_probe.value)",
    ]
    env = {"PYTHONPATH": str(tmp_path)}
    stale = subprocess.run(argv, env=env, cwd=tmp_path, capture_output=True, check=True, timeout=10)
    assert stale.stdout == b"old\n"  # -B alone does not forbid cache reads.
    fresh = subprocess.run(
        argv,
        env={**env, "PYTHONPYCACHEPREFIX": str(tmp_path / "empty-cache")},
        cwd=tmp_path,
        capture_output=True,
        check=True,
        timeout=10,
    )
    assert fresh.stdout == b"new\n"
    assert not (tmp_path / "empty-cache").exists()  # no-bytecode-write is still active


def test_runtime_requires_no_write_and_empty_private_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "dont_write_bytecode", True)
    monkeypatch.setattr(sys, "pycache_prefix", None)
    with pytest.raises(ValueError, match="private empty"):
        campaign.python_cache_observation(require_private=True)
    prefix = tmp_path / "private-cache"
    monkeypatch.setattr(sys, "pycache_prefix", str(prefix))
    assert campaign.python_cache_observation(require_private=True)["private_cache_empty"] is True
    prefix.mkdir()
    (prefix / "old.pyc").write_bytes(b"not permitted")
    with pytest.raises(ValueError, match="private empty"):
        campaign.python_cache_observation(require_private=True)


def test_controller_timeout_preserves_partial_output_without_restarting(tmp_path, monkeypatch):
    # Reuse the lifecycle test's safety path indirectly through a create timeout:
    # no ID exists yet, therefore no guessed container mutation is permitted.
    image_id = "sha256:" + "1" * 64
    calls = []
    monkeypatch.setattr(controller.shutil, "which", lambda tool: "/usr/bin/" + tool)
    monkeypatch.setattr(controller.os, "getuid", lambda: 1000)
    monkeypatch.setattr(controller.os, "getgid", lambda: 1000)
    monkeypatch.setattr(
        controller,
        "host_resources",
        lambda path: {
            "available_memory_bytes": 6 * controller.GIB,
            "disk_free_bytes": 20 * controller.GIB,
            "cpu_count": 2,
        },
    )
    monkeypatch.setattr(
        controller,
        "clean_checkout_context",
        lambda repo, image: {"code_revision": "a" * 40, "code_files": {}, "image": image},
    )

    def timeout_create(argv, **kwargs):
        calls.append(argv)
        if argv[1] == "create":
            raise subprocess.TimeoutExpired(argv, 30, output=b"partial-id", stderr=b"daemon slow")
        output = json.dumps([{"Id": image_id}]).encode() if argv[1] == "image" else b"existing\n"
        return subprocess.CompletedProcess(argv, 0, output, b"")

    monkeypatch.setattr(controller.subprocess, "run", timeout_create)
    with pytest.raises(subprocess.TimeoutExpired):
        controller.run_container(
            repo=campaign.REPO,
            output=tmp_path / "run",
            image_id=image_id,
            name="scanipy-refactor-campaign-timeout-001",
            selected=[],
            states=65536,
            seconds=0.2,
            maximum_seconds=1200,
            execute=True,
        )
    event = read_json(tmp_path / "run/controller/001.json")
    assert event["error_type"] == "TimeoutExpired" and event["returncode"] is None
    assert (tmp_path / "run/controller/001.stdout.bin").read_bytes() == b"partial-id"
    assert (tmp_path / "run/controller/001.stderr.bin").read_bytes() == b"daemon slow"
    assert not any(call[1] in {"start", "stop", "rm", "restart"} for call in calls)
