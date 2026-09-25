"""AC-DEPLOY-02c publish gate — refuse to build on any unspecified pinned digest.

Run BEFORE ``docker buildx build`` in CI (see DOC-CMP-DEPLOY-02 §6.1 step 2).

This is the upstream INV-2 producer defence (DOC-CMP-DEPLOY-02 §5): the ECR
image digest *is* ``env_digest``. If any base-image or tool digest in
``workers/pins.json`` is empty/unspecified, the build is refused so that
``env_digest`` is never derived from an unpinned input.

Public surface:

* :func:`check_pins` — pure function; takes the parsed manifest mapping and
  returns the list of missing/empty pin-field paths (empty list ⇒ complete).
* :func:`check_lockfile` — bind the manifest to the exact snapshot lock bytes
  used by the Dockerfile; a nonempty but stale hash is not a valid pin.
* :func:`main` — resolve inputs relative to this repository (not the cwd),
  refusing missing pins, unsafe lock paths, malformed digests or changed bytes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
import sys
from pathlib import Path
from typing import Any

# workers/build/verify_pins.py -> repo-root/workers/pins.json
_DEFAULT_PINS_FILE = Path(__file__).resolve().parent.parent / "pins.json"
_DEFAULT_REPO_ROOT = _DEFAULT_PINS_FILE.parent.parent
# This must be the file COPY'd by workers/snapshot/Dockerfile, not any other
# attacker-selected file whose digest happens to match the manifest.
SNAPSHOT_LOCKFILE = "workers/snapshot/requirements.txt"


def check_pins(pins: dict[str, Any]) -> list[str]:
    """Return the dotted paths of every required pin field that is missing/empty.

    A complete manifest yields an empty list. Each ``base_images.<name>`` entry
    must carry a non-empty ``sha256``; each ``tools.<name>`` entry must carry a
    non-empty ``version`` *and* ``sha256``; and the top-level
    ``python_packages_lockfile_sha256`` must be non-empty (AC-DEPLOY-02c). A
    field counts as "unspecified" when it is absent, ``None``, or an empty
    string — emptiness, not validity, is what the gate checks.
    """
    missing: list[str] = []

    base_images = pins.get("base_images")
    if not isinstance(base_images, dict) or not base_images:
        missing.append("base_images")
    else:
        for name, entry in base_images.items():
            if not isinstance(entry, dict) or not entry.get("sha256"):
                missing.append(f"base_images.{name}.sha256")

    tools = pins.get("tools")
    if not isinstance(tools, dict) or not tools:
        missing.append("tools")
    else:
        for name, entry in tools.items():
            if not isinstance(entry, dict):
                missing.append(f"tools.{name}")
                continue
            if not entry.get("version"):
                missing.append(f"tools.{name}.version")
            if not entry.get("sha256"):
                missing.append(f"tools.{name}.sha256")

    if not pins.get("python_packages_lockfile_sha256"):
        missing.append("python_packages_lockfile_sha256")

    return missing


def check_lockfile(pins: dict[str, Any], repo_root: Path) -> list[str]:
    """Validate the declared lock path and SHA256 against actual regular bytes.

    The repository root comes from this trusted tool or an explicit CLI option,
    never from the untrusted manifest. Symlinks in any lock path component are
    refused, including ones that resolve to another file inside the repository.
    """
    field = "python_packages_lockfile"
    if pins.get(field) != SNAPSHOT_LOCKFILE:
        return [f"{field}: must be exactly {SNAPSHOT_LOCKFILE}"]
    expected = pins.get(f"{field}_sha256")
    if not isinstance(expected, str) or re.fullmatch(r"[0-9a-f]{64}", expected) is None:
        return [f"{field}_sha256: must be 64 lowercase hexadecimal characters"]
    path = repo_root
    try:
        if not path.is_dir():
            return [f"{field}: repository root is not a directory"]
        for part in Path(SNAPSHOT_LOCKFILE).parts:
            path = path / part
            if path.is_symlink():
                return [f"{field}: symlink path components are forbidden"]
        if not stat.S_ISREG(path.stat().st_mode):
            return [f"{field}: lock must be a regular file"]
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as error:
        return [f"{field}: cannot read lock: {error}"]
    if actual != expected:
        return [f"{field}_sha256: expected {expected}, actual {actual}"]
    return []


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Refuse ambiguous duplicate JSON fields at any manifest depth."""
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate pins manifest key: {key}")
        result[key] = value
    return result


def main(argv: list[str] | None = None) -> int:
    """Gate completeness and actual bytes; never infer the root from a manifest.

    Returns 0 when every required pin is specified, 1 otherwise (the diagnostic
    on stderr names each invalid field). The optional positional argument selects
    an alternate pins manifest. ``--repo-root`` explicitly selects its checkout;
    otherwise the checkout containing this tool is used, even from another cwd.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pins_file", type=Path, nargs="?", default=_DEFAULT_PINS_FILE)
    parser.add_argument("--repo-root", type=Path, default=_DEFAULT_REPO_ROOT)
    args = parser.parse_args(argv)
    try:
        pins = json.loads(
            args.pins_file.read_text(encoding="utf-8"), object_pairs_hook=_unique_object
        )
        if not isinstance(pins, dict):
            raise ValueError("pins manifest must be a JSON object")
    except (OSError, UnicodeError, ValueError) as error:
        print(f"ERROR (AC-DEPLOY-02c): cannot load pins: {error}", file=sys.stderr)
        return 1
    errors = check_pins(pins) + check_lockfile(pins, args.repo_root)
    if errors:
        print("ERROR (AC-DEPLOY-02c): pins are incomplete or invalid:", file=sys.stderr)
        for field in errors:
            print(f"  - {field}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
