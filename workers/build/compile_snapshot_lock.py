"""Generate only the snapshot's hash lock; never install or build packages.

The reviewed Linux x86-64 uv distribution and version are checked before use.
Inputs permit only exact registry pins. Resolver configuration, inherited uv
options, source builds, Python downloads and shared caches are excluded. This
is dependency resolution, not evidence that the resulting image can start.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

UV_VERSION = "uv 0.12.19 (x86_64-unknown-linux-gnu)"
# Public generator executable hash, not a credential.
UV_SHA256 = (
    "242e462a63f5a3c0421d68557006193ecbfb61321cba0fe8542213ac62d92563"  # pragma: allowlist secret
)
PYTHON_VERSION = "3.11"
PYTHON_PLATFORM = "x86_64-unknown-linux-gnu"
EXCLUDE_NEWER = "2026-09-25T09:49:02Z"
COMPILE_COMMAND = "python workers/build/compile_snapshot_lock.py --uv /path/to/verified/uv"
_ROOT = Path(__file__).resolve().parents[2]
_INPUT = Path("workers/snapshot/requirements.in")
_OUTPUT = Path("workers/snapshot/requirements.txt")
_EXACT_PIN = re.compile(r"([A-Za-z0-9][A-Za-z0-9_.-]*)(?:\[[a-z0-9,-]+\])?==[A-Za-z0-9_.+!-]+")


def validate_input(content: str) -> None:
    """Reject directives, editable/path/URL inputs, ranges and duplicate names."""
    names: set[str] = set()
    for line in content.splitlines():
        value = line.partition("#")[0].strip()
        if not value:
            continue
        match = _EXACT_PIN.fullmatch(value)
        if match is None:
            raise ValueError(f"Only exact registry pins are allowed: {value!r}")
        name = re.sub(r"[-_.]+", "-", match.group(1)).lower()
        if name in names:
            raise ValueError(f"Duplicate package pin: {name}")
        names.add(name)
    if not names:
        raise ValueError("Empty snapshot requirements input")


def resolver_environment() -> dict[str, str]:
    """Do not inherit UV_*, PIP_*, index credentials or build backend options."""
    return {
        "PATH": os.pathsep.join((str(Path(sys.executable).parent), "/usr/bin", "/bin")),
        "LANG": "C.UTF-8",
    }


def compile_argv(uv: Path, output: Path, cache: Path) -> list[str]:
    """Fixed, auditable wheel-only resolution; output path is not in its header."""
    return [
        str(uv),
        "--no-config",
        "pip",
        "compile",
        str(_INPUT),
        "--python",
        sys.executable,
        "--python-version",
        PYTHON_VERSION,
        "--python-platform",
        PYTHON_PLATFORM,
        "--no-python-downloads",
        "--only-binary",
        ":all:",
        "--generate-hashes",
        "--no-strip-extras",
        "--emit-build-options",
        "--default-index",
        "https://pypi.org/simple",
        "--keyring-provider",
        "disabled",
        "--exclude-newer",
        EXCLUDE_NEWER,
        "--cache-dir",
        str(cache),
        "--custom-compile-command",
        COMPILE_COMMAND,
        "--output-file",
        str(output),
    ]


def _repository_file(relative: Path, *, allow_missing: bool = False) -> Path:
    """Resolve only the fixed checkout paths without following any symlinks."""
    if _ROOT.is_symlink() or not _ROOT.is_dir():
        raise ValueError("Generator repository root must be a real directory")
    path = _ROOT
    for index, part in enumerate(relative.parts):
        path = path / part
        if path.is_symlink():
            raise ValueError(f"Refusing symlink input/output path component: {relative}")
        last = index == len(relative.parts) - 1
        try:
            mode = path.stat().st_mode
        except FileNotFoundError:
            if last and allow_missing:
                return path
            raise ValueError(f"Missing input/output path component: {relative}") from None
        if not (stat.S_ISREG(mode) if last else stat.S_ISDIR(mode)):
            raise ValueError(
                f"Input/output must use real directories and regular files: {relative}"
            )
    return path


def generate(uv: Path, *, check: bool) -> str:
    """Return measured lock SHA256; --check leaves repository files untouched."""
    if sys.version_info[:2] != (3, 11):
        raise ValueError("Run this generator with Python 3.11, matching the snapshot base")
    source = _repository_file(_INPUT)
    destination = _repository_file(_OUTPUT, allow_missing=not check)
    validate_input(source.read_text(encoding="utf-8"))
    uv = uv.resolve(strict=True)
    if not uv.is_file() or hashlib.sha256(uv.read_bytes()).hexdigest() != UV_SHA256:
        raise ValueError("uv executable does not match the reviewed Linux x86-64 SHA256")
    environment = resolver_environment()
    version = subprocess.run(
        [str(uv), "--version"],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
        timeout=10,
    )
    if version.stdout.strip() != UV_VERSION:
        raise ValueError("uv version differs from the reviewed generator")
    with tempfile.TemporaryDirectory(prefix="scanipy-snapshot-lock-") as temporary:
        directory = Path(temporary)
        output = directory / "requirements.txt"
        result = subprocess.run(
            compile_argv(uv, output, directory / "cache"),
            cwd=_ROOT,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.stderr:
            print(result.stderr, file=sys.stderr, end="")
        generated = output.read_bytes()
        if check:
            if generated != destination.read_bytes():
                raise ValueError("Generated snapshot lock differs from committed bytes")
        else:
            destination.write_bytes(generated)
    return hashlib.sha256(generated).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--uv", type=Path, required=True, help="Reviewed uv executable (not installed)"
    )
    parser.add_argument("--check", action="store_true", help="Compare without modifying the lock")
    args = parser.parse_args(argv)
    try:
        digest = generate(args.uv, check=args.check)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"Snapshot lock generation refused: {error}", file=sys.stderr)
        if isinstance(error, subprocess.CalledProcessError) and error.stderr:
            print(error.stderr, file=sys.stderr, end="")
        return 1
    print(f"sha256:{digest}  {_OUTPUT}")
    print("pins.json is not updated automatically; review and record this exact hash.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
