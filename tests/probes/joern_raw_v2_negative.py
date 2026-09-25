"""Opt-in real exporter failure probes; never executes target source."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

from joern_raw_v2 import run_phase

from analysis.cpg_ingest.raw_v2 import RawExportFailedError, parse_raw_export


def main() -> None:
    work = Path("/job/negative")
    work.mkdir(exist_ok=False)
    temporary = work / "tmp"
    temporary.mkdir()
    script = "/repo/workers/snapshot/joern-scripts/export_cpg_v2.sc"
    env = {
        "PATH": "/opt/joern:/opt/joern/bin:/opt/temurin-jre/bin:/usr/bin:/usr/local/bin",
        "JAVA_HOME": "/opt/temurin-jre",
        "JAVA_TOOL_OPTIONS": (
            f"-Xmx1536m -XX:ActiveProcessorCount=2 -Duser.home={work} -Djava.io.tmpdir={temporary}"
        ),
        "TMPDIR": str(temporary),
        "SCANIPY_CPG_BIN_PATH": "/job/python/cpg.bin",
        "SCANIPY_EXPORT_V2_SCRIPT_PATH": script,
        "SCANIPY_EXPORT_V2_SOURCE_ROOT": "/repo/tests/fixtures/joern_raw_v2/python",
        "SCANIPY_EXPORT_V2_IMAGE_ID": os.environ["SCANIPY_PROBE_IMAGE_ID"],
    }
    outcomes = []
    for case in ("wrong_frontend", "existing_output", "symlink_source"):
        output = work / f"{case}.json"
        attempt_env = dict(env)
        attempt_env["SCANIPY_EXPORT_V2_FRONTEND"] = (
            "javasrc" if case == "wrong_frontend" else "pythonsrc"
        )
        attempt_env["SCANIPY_EXPORT_V2_JSON_PATH"] = str(output)
        original = b"preexisting evidence must not be overwritten\n"
        if case == "existing_output":
            output.write_bytes(original)
        if case == "symlink_source":
            source = work / "symlink-source"
            source.mkdir()
            (source / "flow.py").symlink_to("/repo/tests/fixtures/joern_raw_v2/python/flow.py")
            attempt_env["SCANIPY_EXPORT_V2_SOURCE_ROOT"] = str(source)
        try:
            run_phase("joern", ["--script", script], attempt_env, work, case)
        except subprocess.CalledProcessError as exc:
            if exc.returncode == 0:
                raise AssertionError("expected real nonzero exporter process status") from exc
        else:
            raise AssertionError(f"{case} unexpectedly succeeded")
        outcome = {"case": case, "export_process": "failed_as_required"}
        if case == "wrong_frontend":
            parsed = parse_raw_export(output.read_bytes(), require_completed=False)
            if parsed["status"] != "failed" or parsed["nodes"] is not None:
                raise AssertionError("mismatched metadata published usable graph")
            try:
                parse_raw_export(output.read_bytes())
            except RawExportFailedError:
                pass
            else:
                raise AssertionError("default reader accepted failed export")
            outcome["envelope"] = "failed_not_completed"
        elif case == "existing_output":
            if output.read_bytes() != original:
                raise AssertionError("existing output was modified")
            outcome["preserved_sha256"] = hashlib.sha256(original).hexdigest()
        elif output.exists():
            raise AssertionError("invalid source provenance published an envelope")
        else:
            outcome["envelope"] = "absent_provenance_failure"
        outcomes.append(outcome)
    (work / "outcomes.json").write_text(
        json.dumps(outcomes, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"negative_probes": "completed", "cases": len(outcomes)}), flush=True)


if __name__ == "__main__":
    main()
