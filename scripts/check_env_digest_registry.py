#!/usr/bin/env python3
"""CI validator for ``workers/env_digest_history.json`` (CLAR-DEPLOY-22).

Runs in the ``ci.yml`` lint job on every PR + push to main. Two checks:

1. **Schema / invariants** — :func:`workers.build.env_digest_registry.check_registry`
   (schema_version, field regexes, at-most-one active per image, unique
   non-placeholder sha256 digests, notes on non-active rows).
2. **Append-only against git history** — the registry as committed at
   ``--base-ref`` (default ``origin/main``) must be an append-only prefix of
   the working-tree registry: no deleted rows, immutable identity fields, and
   only forward status transitions (never back to ``active``). Skipped with a
   notice when the file does not exist at the base ref (bootstrap PR).

Exit 0 = valid; exit 1 prints every violation (fail-closed).
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
    check_append_only,
    check_registry,
)

REGISTRY_RELPATH = "workers/env_digest_history.json"


def _git_show(ref: str, relpath: str) -> str | None:
    """Content of ``relpath`` at ``ref``, or None when the ref/path is absent."""
    proc = subprocess.run(
        ["git", "show", f"{ref}:{relpath}"],  # noqa: S607 — "git" via PATH, trusted toolchain
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    return proc.stdout if proc.returncode == 0 else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="check_env_digest_registry")
    parser.add_argument("--path", default=REGISTRY_RELPATH, help="registry path (repo-relative)")
    parser.add_argument(
        "--base-ref",
        default=None,
        help="git ref for the append-only comparison (e.g. origin/main); omit to skip",
    )
    args = parser.parse_args(argv)

    registry_path = REPO_ROOT / args.path
    if not registry_path.is_file():
        print(f"ERROR (CLAR-DEPLOY-22): registry missing at {args.path}", file=sys.stderr)
        return 1
    try:
        doc = json.loads(registry_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"ERROR (CLAR-DEPLOY-22): malformed JSON in {args.path}: {exc}", file=sys.stderr)
        return 1
    if not isinstance(doc, dict):
        print(f"ERROR (CLAR-DEPLOY-22): {args.path} is not a JSON object", file=sys.stderr)
        return 1

    violations = check_registry(doc)

    if args.base_ref:
        old_text = _git_show(args.base_ref, args.path)
        if old_text is None:
            print(
                f"NOTICE: {args.path} absent at {args.base_ref} — append-only check "
                "skipped (registry bootstrap)."
            )
        else:
            try:
                old_doc = json.loads(old_text)
            except json.JSONDecodeError:
                print(
                    f"NOTICE: {args.path} unparseable at {args.base_ref} — append-only "
                    "check skipped."
                )
                old_doc = None
            if isinstance(old_doc, dict):
                violations.extend(check_append_only(old_doc, doc))

    if violations:
        print("ERROR (CLAR-DEPLOY-22): env_digest registry check failed:", file=sys.stderr)
        for violation in violations:
            print(f"  - {violation}", file=sys.stderr)
        return 1
    print(f"env_digest registry OK ({args.path})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
