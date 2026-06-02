"""AC-DEPLOY-02c publish gate — refuse to build on any unspecified pinned digest.

Run BEFORE ``docker buildx build`` in CI (see DOC-CMP-DEPLOY-02 §6.1 step 2).

This is the upstream INV-2 producer defence (DOC-CMP-DEPLOY-02 §5): the ECR
image digest *is* ``env_digest``. If any base-image or tool digest in
``workers/pins.json`` is empty/unspecified, the build is refused so that
``env_digest`` is never derived from an unpinned input.

Public surface:

* :func:`check_pins` — pure function; takes the parsed manifest mapping and
  returns the list of missing/empty pin-field paths (empty list ⇒ complete).
* :func:`main` — thin CLI wrapper resolving ``workers/pins.json`` relative to
  this file (not the process cwd) and exiting non-zero if any pin is missing.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

# workers/build/verify_pins.py -> repo-root/workers/pins.json
_DEFAULT_PINS_FILE = Path(__file__).resolve().parent.parent / "pins.json"


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


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: load the pins manifest and gate on completeness.

    Returns 0 when every required pin is specified, 1 otherwise (the diagnostic
    on stderr names each missing field). ``argv[0]`` may override the default
    ``workers/pins.json`` path (used by CI to point at an alternate manifest).
    """
    args = sys.argv[1:] if argv is None else argv
    pins_file = Path(args[0]) if args else _DEFAULT_PINS_FILE

    pins: dict[str, Any] = json.loads(pins_file.read_text(encoding="utf-8"))
    missing = check_pins(pins)

    if missing:
        print("ERROR (AC-DEPLOY-02c): pins are incomplete:", file=sys.stderr)
        for field in missing:
            print(f"  - {field}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
