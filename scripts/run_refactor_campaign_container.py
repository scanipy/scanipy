#!/usr/bin/env python3
"""Run one fresh campaign in a newly created, resource-limited local container.

No image pull/build/install, network, privileged mount, or existing-container
mutation is performed. Read the runbook before authorizing --execute.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from time import monotonic, sleep
from typing import Any

from scripts.check_refactor_report import sha256_bytes
from scripts.run_refactor_campaign import (
    CONTAINER_PYCACHE,
    REPO,
    EvidenceStore,
    python_cache_observation,
    utc_now,
)

GIB = 1024**3
LABEL = "io.scanipy.refactor-campaign"


def checked(argv: list[str], *, cwd: Path = REPO) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(argv, cwd=cwd, check=True, capture_output=True, timeout=30, shell=False)


def host_resources(parent: Path) -> dict[str, Any]:
    values = {}
    for line in Path("/proc/meminfo").read_text().splitlines():
        key, value = line.split(":", 1)
        values[key] = int(value.strip().split()[0]) * 1024
    return {
        "observed_at": utc_now(),
        "cpu_count": os.cpu_count(),
        "available_memory_bytes": values["MemAvailable"],
        "disk_free_bytes": shutil.disk_usage(parent).free,
        "host_role": "reference host; presentation hardware not confirmed",
    }


def require_resources(resources: dict[str, Any]) -> None:
    if resources["available_memory_bytes"] < 6 * GIB:
        raise ValueError("need at least 6 GiB available memory before reserving 4 GiB")
    if resources["disk_free_bytes"] < 20 * GIB:
        raise ValueError("need at least 20 GiB free for raw artifacts and per-case fresh work")
    if (resources["cpu_count"] or 0) < 2:
        raise ValueError("at least two host CPUs required")


def clean_checkout_context(repo: Path, image: dict[str, Any]) -> dict[str, Any]:
    git = shutil.which("git")
    if git is None:
        raise ValueError("git not available for actual analysis revision verification")
    status = checked([git, "status", "--porcelain", "--untracked-files=all"], cwd=repo).stdout
    if status:
        raise ValueError(
            "analysis checkout is dirty; commit/review the exact producer before running"
        )
    revision = checked([git, "rev-parse", "HEAD"], cwd=repo).stdout.decode().strip()
    paths = checked([git, "ls-files", "-z", "--", "analysis", "tools", "scripts"], cwd=repo).stdout
    files = {}
    for raw in paths.split(b"\0"):
        if not raw:
            continue
        name = raw.decode()
        path = repo / name
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"unsupported analysis artifact: {name}")
        files[name] = sha256_bytes(path.read_bytes())
    return {
        "code_revision": revision,
        "code_files": files,
        "image": image,
        "analysis_repo": str(repo),
        "observation": "clean tracked analysis checkout",
    }


def container_command(
    *,
    docker: str,
    image_id: str,
    name: str,
    repo: Path,
    output: Path,
    uid: int,
    gid: int,
    selected: Sequence[str],
    states: int,
    seconds: float,
) -> list[str]:
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", image_id):
        raise ValueError("image must be an exact locally resolved immutable image ID")
    if not re.fullmatch(r"scanipy-refactor-campaign-[a-z0-9-]{6,50}", name):
        raise ValueError("container name must use a unique scanipy-refactor-campaign- suffix")
    if uid <= 0 or gid < 0:
        raise ValueError("campaign must run as a non-root host/container user")
    for path in (repo, output):
        if not path.is_absolute() or "," in str(path) or "\n" in str(path):
            raise ValueError("mount paths must be absolute and contain no comma/newline")
    command = [
        docker,
        "create",
        "--name",
        name,
        "--label",
        f"{LABEL}={name}",
        "--network",
        "none",
        "--read-only",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges:true",
        "--cpus",
        "2",
        "--memory",
        "4g",
        "--memory-swap",
        "4g",
        "--pids-limit",
        "256",
        "--user",
        f"{uid}:{gid}",
        "--workdir",
        "/workspace",
        "--mount",
        f"type=bind,src={repo},dst=/workspace,readonly",
        "--mount",
        f"type=bind,src={output / 'data'},dst=/output",
        "--mount",
        f"type=bind,src={output / 'controller-context.json'},dst=/controller-context.json,readonly",
        "--tmpfs",
        "/tmp:rw,nosuid,nodev,size=536870912",  # noqa: S108 -- private container tmpfs
        "--env",
        "PYTHONPATH=/workspace",
        "--env",
        "PYTHONDONTWRITEBYTECODE=1",
        "--env",
        f"PYTHONPYCACHEPREFIX={CONTAINER_PYCACHE}",
        "--entrypoint",
        "/usr/local/bin/python",
        image_id,
        "-m",
        "scripts.run_refactor_campaign",
        "--execute",
        "--context",
        "/controller-context.json",
        "--output",
        "/output/evidence",
        "--work",
        "/output/work",
        "--states",
        str(states),
        "--seconds",
        str(seconds),
    ]
    for identifier in selected:
        command.extend(["--case-id", identifier])
    return command


def run_container(
    *,
    repo: Path,
    output: Path,
    image_id: str,
    name: str,
    selected: Sequence[str],
    states: int,
    seconds: float,
    maximum_seconds: int,
    execute: bool,
) -> int:
    docker = shutil.which("docker")
    if docker is None:
        raise ValueError("Docker is not available")
    repo = repo.resolve()
    if repo != REPO:
        raise ValueError("controller must run from the exact checkout it mounts")
    output = output.absolute()
    if output.exists() or output.is_symlink() or not output.parent.is_dir():
        raise ValueError("output must be a new directory beneath an existing parent")
    if output.parent.resolve() != output.parent or repo == output or repo in output.parents:
        raise ValueError("output must be outside the analysis checkout and have no symlink parent")
    if maximum_seconds < 1 or maximum_seconds > 86400:
        raise ValueError("campaign watchdog must be between 1 second and 24 hours")
    resources = host_resources(output.parent)
    require_resources(resources)
    # Inspect ONLY the explicitly supplied local image; never pull or resolve a tag.
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", image_id):
        raise ValueError("--image-id requires sha256:<64 lowercase hex>")
    image_raw = json.loads(checked([docker, "image", "inspect", image_id]).stdout)[0]
    if image_raw["Id"] != image_id:
        raise ValueError("local image identity mismatch")
    image = {key: image_raw.get(key) for key in ("Id", "RepoDigests", "Architecture", "Os", "Size")}
    context = clean_checkout_context(repo, image)
    command = container_command(
        docker=docker,
        image_id=image_id,
        name=name,
        repo=repo,
        output=output,
        uid=os.getuid(),
        gid=os.getgid(),
        selected=selected,
        states=states,
        seconds=seconds,
    )
    context.update(
        {
            "create_command": command,
            "host_resources": resources,
            "controller_command": list(sys.orig_argv),
            "maximum_seconds": maximum_seconds,
        }
    )
    if not execute:
        print(json.dumps({"plan_only": True, "context": context}, indent=2))
        return 0
    store = EvidenceStore(output)
    store.json("controller-context.json", context)
    (output / "data").mkdir(mode=0o700)
    store.bytes(
        "existing-containers-before.txt",
        checked(
            [docker, "ps", "--no-trunc", "--format", "{{.ID}}\t{{.Names}}\t{{.Image}}\t{{.Status}}"]
        ).stdout,
    )
    sequence = 0

    def call(argv: list[str]) -> subprocess.CompletedProcess[bytes]:
        nonlocal sequence
        sequence += 1
        started_at, started = utc_now(), monotonic()
        prefix = f"controller/{sequence:03d}"
        try:
            result = subprocess.run(argv, capture_output=True, timeout=30, shell=False, check=False)
        except subprocess.TimeoutExpired as exc:
            out_ref = store.bytes(prefix + ".stdout.bin", exc.stdout or b"")
            err_ref = store.bytes(prefix + ".stderr.bin", exc.stderr or b"")
            store.json(
                prefix + ".json",
                {
                    "argv": argv,
                    "started_at": started_at,
                    "completed_at": utc_now(),
                    "elapsed_seconds": monotonic() - started,
                    "returncode": None,
                    "error_type": "TimeoutExpired",
                    "stdout": out_ref,
                    "stderr": err_ref,
                    "note": "Observation timeout: inspect live ID; do not restart automatically.",
                },
            )
            raise
        out_ref = store.bytes(prefix + ".stdout.bin", result.stdout)
        err_ref = store.bytes(prefix + ".stderr.bin", result.stderr)
        store.json(
            prefix + ".json",
            {
                "argv": argv,
                "started_at": started_at,
                "completed_at": utc_now(),
                "elapsed_seconds": monotonic() - started,
                "returncode": result.returncode,
                "stdout": out_ref,
                "stderr": err_ref,
            },
        )
        result.check_returncode()
        return result

    created = call(command)
    container_id = created.stdout.decode().strip()
    if not re.fullmatch(r"[0-9a-f]{64}", container_id):
        raise ValueError(
            "Docker create returned no exact container ID; inspect retained create event"
        )
    store.json("container-id.json", {"container_id": container_id, "name": name})
    print(json.dumps({"created_container_id": container_id, "output": str(output)}), flush=True)
    call([docker, "start", container_id])
    started = monotonic()
    watchdog = None
    while True:
        inspected = json.loads(call([docker, "inspect", container_id]).stdout)[0]
        if inspected["Id"] != container_id or inspected["Config"]["Labels"].get(LABEL) != name:
            raise ValueError("live container ownership mismatch; refusing any mutation")
        if not inspected["State"]["Running"]:
            break
        if monotonic() - started >= maximum_seconds:
            watchdog = "explicit campaign wall-clock ceiling exceeded"
        elif shutil.disk_usage(output).free < 5 * GIB:
            watchdog = "disk safety reserve below 5 GiB"
        if watchdog:
            # This is the sole container mutation after start, addressed by the
            # exact ID created above and freshly ownership-checked, never name/glob.
            call([docker, "stop", "--time", "10", container_id])
            inspected = json.loads(call([docker, "inspect", container_id]).stdout)[0]
            break
        sleep(10)
    logs = call([docker, "logs", container_id])
    store.bytes("container.stdout.bin", logs.stdout)
    store.bytes("container.stderr.bin", logs.stderr)
    store.json("container-final.json", inspected)
    store.json(
        "controller-final.json",
        {
            "container_id": container_id,
            "watchdog": watchdog,
            "elapsed_seconds": monotonic() - started,
            "exit_code": inspected["State"]["ExitCode"],
            "host_resources": host_resources(output),
        },
    )
    if inspected["State"]["Running"]:
        raise ValueError(
            f"owned container still running: {container_id}; no restart/removal attempted"
        )
    call([docker, "rm", container_id])
    print(
        json.dumps(
            {
                "removed_stopped_container": container_id,
                "raw_evidence": str(output),
                "note": "No existing application/database container was modified.",
            }
        ),
        flush=True,
    )
    return 2 if watchdog else int(inspected["State"]["ExitCode"])


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--image-id", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument("--states", type=int, default=65536)
    parser.add_argument("--seconds", type=float, default=0.2)
    parser.add_argument("--maximum-seconds", type=int, default=86400)
    parser.add_argument(
        "--execute", action="store_true", help="otherwise only inspect/print the plan"
    )
    args = parser.parse_args(argv)
    try:
        python_cache_observation(require_private=True)
        return run_container(
            repo=args.repo,
            output=args.output,
            image_id=args.image_id,
            name=args.name,
            selected=args.case_id,
            states=args.states,
            seconds=args.seconds,
            maximum_seconds=args.maximum_seconds,
            execute=args.execute,
        )
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(
            f"controller stopped: {exc}; inspect container-id.json before further action",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
