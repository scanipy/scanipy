#!/usr/bin/env python3
"""AC-DEPLOY-04a rollover-ceremony lint (CI — CLAR-DEPLOY-22).

Verbatim AC (WBS §2.4 / DOC-CMP-DEPLOY-04 §9): *"A merge to the main branch
cannot deploy a worker image whose tool digests differ from those committed in
the substrate decision record without an explicit ``env_digest`` rollover
ceremony."*

This lint fails any PR that

* modifies ``workers/pins.json`` (a tool-digest change ⇒ a new image digest ⇒
  a new ``env_digest``), OR
* changes which registry entry is ``active`` in
  ``workers/env_digest_history.json`` (the machine registration itself),

unless the PR title carries the ceremony marker from DOC-CMP-DEPLOY-02 §6.2
step 2 / DOC-CMP-DEPLOY-04 §6.2 step 1 (verbatim: the title contains
``env_digest rollover``). Fail-closed: an unparseable new registry counts as an
active flip.

Exit 0 = no ceremony needed, or ceremony correctly declared; exit 1 otherwise.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from workers.build.env_digest_registry import (  # noqa: E402
    CEREMONY_MARKER,
    active_map,
)

PINS_RELPATH = "workers/pins.json"
REGISTRY_RELPATH = "workers/env_digest_history.json"


def ceremony_title_ok(title: str) -> bool:
    """True iff the PR title carries the DOC-CMP-DEPLOY-02 §6.2 ceremony marker."""
    return CEREMONY_MARKER in title


def ceremony_reasons(
    old_pins: str | None,
    new_pins: str | None,
    old_registry: str | None,
    new_registry: str | None,
) -> list[str]:
    """Why this change requires the rollover ceremony (empty list = not required).

    Pure function over the four file states (base-ref vs working tree) so
    TST-AC-DEPLOY-04a can exercise it hermetically.
    """
    reasons: list[str] = []

    if old_pins != new_pins:
        reasons.append(f"{PINS_RELPATH} modified (tool-digest change => env_digest change)")

    def _actives(text: str | None) -> dict[str, str] | None:
        if text is None:
            return {}
        try:
            doc = json.loads(text)
        except json.JSONDecodeError:
            return None
        if not isinstance(doc, dict):
            return None
        return active_map(doc)

    old_actives = _actives(old_registry)
    new_actives = _actives(new_registry)
    if new_actives is None or old_actives is None:
        reasons.append(f"{REGISTRY_RELPATH} unparseable — treating as an active flip (fail-closed)")
    elif old_actives != new_actives:
        reasons.append(
            f"active env_digest registry entries changed: {old_actives} -> {new_actives}"
        )

    return reasons


def _git_show(ref: str, relpath: str) -> str | None:
    proc = subprocess.run(
        ["git", "show", f"{ref}:{relpath}"],  # noqa: S607 — "git" via PATH, trusted toolchain
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    return proc.stdout if proc.returncode == 0 else None


def _working_tree(relpath: str) -> str | None:
    path = REPO_ROOT / relpath
    return path.read_text(encoding="utf-8") if path.is_file() else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="check_rollover_ceremony")
    parser.add_argument("--base-ref", required=True, help="git ref of the PR base (origin/<base>)")
    parser.add_argument("--title", required=True, help="the PR title")
    args = parser.parse_args(argv)

    reasons = ceremony_reasons(
        _git_show(args.base_ref, PINS_RELPATH),
        _working_tree(PINS_RELPATH),
        _git_show(args.base_ref, REGISTRY_RELPATH),
        _working_tree(REGISTRY_RELPATH),
    )

    if not reasons:
        print("No env_digest-bearing change detected — rollover ceremony not required.")
        return 0
    if ceremony_title_ok(args.title):
        print(f"Rollover ceremony declared ({CEREMONY_MARKER!r} in PR title) for:")
        for reason in reasons:
            print(f"  - {reason}")
        return 0
    print(
        "ERROR (AC-DEPLOY-04a): this PR requires the env_digest rollover ceremony:",
        file=sys.stderr,
    )
    for reason in reasons:
        print(f"  - {reason}", file=sys.stderr)
    print(
        f"\nThe PR title must contain the marker {CEREMONY_MARKER!r} "
        "(DOC-CMP-DEPLOY-02 §6.2 / DOC-CMP-DEPLOY-04 §6.2) and the description must "
        "name which tool(s) changed and why.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
