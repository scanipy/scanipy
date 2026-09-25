"""Trusted bounded probe driver; parses fixtures, never imports/executes them.

Run only inside the documented disposable network-none container. This is
opt-in evidence tooling, not the production frontend or an automatic pytest job.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

from analysis.cpg_ingest.raw_v2 import parse_raw_export
from tools.worker.secure_subprocess import resolve_pinned_binary, secure_run


def run_phase(tool: str, argv: list[str], env: dict[str, str], work: Path, phase: str) -> None:
    started = time.monotonic()
    event: dict[str, object] = {
        "argv": [resolve_pinned_binary(tool), *argv],
        "env": env,
        "cwd": str(work),
        "timeout_s": 120,
    }
    stdout: bytes = b""
    stderr: bytes = b""
    try:
        result = secure_run(tool, argv, timeout_s=120, env=env, cwd=str(work))
        stdout, stderr = result.stdout, result.stderr
        event["returncode"] = result.returncode
    except subprocess.CalledProcessError as exc:
        stdout, stderr = exc.stdout or b"", exc.stderr or b""
        event["returncode"] = exc.returncode
        event["error"] = type(exc).__name__
        raise
    except subprocess.TimeoutExpired as exc:
        stdout, stderr = exc.stdout or b"", exc.stderr or b""
        event["error"] = type(exc).__name__
        raise
    finally:
        event["elapsed_seconds"] = time.monotonic() - started
        (work / f"{phase}.stdout").write_bytes(stdout)
        (work / f"{phase}.stderr").write_bytes(stderr)
        (work / f"{phase}.event.json").write_text(
            json.dumps(event, sort_keys=True, indent=2) + "\n", encoding="utf-8"
        )


def main() -> None:
    language = sys.argv[1]
    frontend = {"python": "pythonsrc", "java": "javasrc"}[language]
    source = Path("/repo/tests/fixtures/joern_raw_v2") / language
    work = Path("/job") / language
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
    }
    run_phase(
        "joern-parse",
        ["--language", frontend, "--output", str(work / "cpg.bin"), str(source)],
        dict(env),
        work,
        "parse",
    )
    env.update(
        {
            "SCANIPY_CPG_BIN_PATH": str(work / "cpg.bin"),
            "SCANIPY_EXPORT_V2_JSON_PATH": str(work / "export.json"),
            "SCANIPY_EXPORT_V2_SCRIPT_PATH": script,
            "SCANIPY_EXPORT_V2_SOURCE_ROOT": str(source),
            "SCANIPY_EXPORT_V2_FRONTEND": frontend,
            "SCANIPY_EXPORT_V2_IMAGE_ID": os.environ["SCANIPY_PROBE_IMAGE_ID"],
        }
    )
    run_phase("joern", ["--script", script], env, work, "export")
    parsed = parse_raw_export((work / "export.json").read_bytes())
    print(json.dumps({"language": language, "status": parsed["status"]}), flush=True)


if __name__ == "__main__":
    main()
