"""env_digest registry — the canonical machine-readable ``env_digest`` surface.

Decision record: CLAR-DEPLOY-22 (fills the DOC-CMP-DEPLOY-02 §6.1.6 ↔
DOC-CMP-DEPLOY-04 §6.2.7 gap). The committed, append-only registry at
``workers/env_digest_history.json`` is the single authoritative surface for the
production ``env_digest`` (the CP-06 / INV-2 bootstrap):

* entries are ``{image, env_digest, tag, git_sha, signed_at, status, note}``;
* ``status ∈ {active, superseded, void}`` — ``void`` means *never authoritative*
  (permitted only for digests no persisted snapshot/finding carries), while
  ``superseded`` means *was authoritative, rolled over*;
* at most one ``active`` entry per worker image. Zero active entries is the
  pre-bootstrap state (CLAR-CP-06-02 record-and-warn); the moment an active
  entry lands, CP-06's :func:`services.control_plane.fidelity.enforce_production_env`
  flips to hard-fail — data-driven, no code change;
* the registry is written ONLY via an ``env_digest rollover`` PR auto-opened by
  the ``register-env-digest`` job in ``.github/workflows/deploy.yml`` (never a
  direct push — enforce-pr-only-merges.yml + RULE-10); registration is
  effective on merge.

Style mirrors :mod:`workers.build.verify_pins` (the AC-DEPLOY-02c gate): pure
check function + thin CLI. Consumed by ``scripts/check_env_digest_registry.py``
(CI lint), ``scripts/check_rollover_ceremony.py`` (AC-DEPLOY-04a lint),
``services/control_plane/fidelity.py`` (CP-06) and ``TST-AC-DEPLOY-02b``.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# workers/build/env_digest_registry.py -> repo-root/workers/env_digest_history.json
_DEFAULT_REGISTRY_FILE = Path(__file__).resolve().parent.parent / "env_digest_history.json"

VALID_IMAGES: tuple[str, ...] = ("scanipy-snapshot", "scanipy-detector")
VALID_STATUSES: tuple[str, ...] = ("active", "superseded", "void")

#: The all-zero digest is a placeholder (e.g. fidelity.py's ungated verdicts) and
#: must never be registered as a real env_digest.
PLACEHOLDER_DIGEST = "sha256:" + "0" * 64

#: The rollover-ceremony marker every registry-writing PR title must carry
#: (DOC-CMP-DEPLOY-02 §6.2 step 2 / DOC-CMP-DEPLOY-04 §6.2 step 1 — verbatim).
CEREMONY_MARKER = "env_digest rollover"

_ENV_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_TAG_RE = re.compile(r"^v[0-9]+\.[0-9]+\.[0-9]+$")
_GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
# ISO-8601 UTC, seconds precision, Z suffix (regex, not fromisoformat: py3.10's
# fromisoformat rejects "Z" and the check must not depend on interpreter version).
_SIGNED_AT_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")

_ENTRY_KEYS = frozenset({"image", "env_digest", "tag", "git_sha", "signed_at", "status", "note"})

#: Append-only status transitions. ``active -> superseded`` is the rollover;
#: ``void -> superseded`` is the (loud, ceremony-reviewed) correction path for a
#: digest later found to have stamped an artifact (CLAR-DEPLOY-22 risk note).
#: Nothing ever transitions BACK to ``active`` — a rollover appends a new row.
_ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "active": frozenset({"active", "superseded"}),
    "superseded": frozenset({"superseded"}),
    "void": frozenset({"void", "superseded"}),
}


class EnvDigestRegistryError(ValueError):
    """A malformed / invariant-violating env_digest registry (fail-closed)."""


def check_registry(doc: dict[str, object]) -> list[str]:
    """Return the list of violation strings for ``doc`` (empty list == valid).

    Enforced: ``schema_version == 1``; per-field regexes; unknown entry keys
    rejected; at most one ``status=="active"`` per image (zero is the legal
    pre-bootstrap state — CLAR-CP-06-02 record-and-warn until the first
    rollover PR merges); ``env_digest`` unique across all entries and never the
    all-zero placeholder; non-empty ``note`` on every non-active row.
    """
    violations: list[str] = []

    if doc.get("schema_version") != 1:
        violations.append("schema_version: must be 1")

    entries = doc.get("entries")
    if not isinstance(entries, list):
        violations.append("entries: must be a list")
        return violations

    seen_digests: set[str] = set()
    active_count: dict[str, int] = {}

    for i, entry in enumerate(entries):
        prefix = f"entries[{i}]"
        if not isinstance(entry, dict):
            violations.append(f"{prefix}: must be an object")
            continue

        unknown = sorted(set(entry) - _ENTRY_KEYS)
        if unknown:
            violations.append(f"{prefix}: unknown key(s): {', '.join(unknown)}")
        missing = sorted(_ENTRY_KEYS - set(entry))
        if missing:
            violations.append(f"{prefix}: missing key(s): {', '.join(missing)}")
            continue

        image = entry["image"]
        env_digest = entry["env_digest"]
        tag = entry["tag"]
        git_sha = entry["git_sha"]
        signed_at = entry["signed_at"]
        status = entry["status"]
        note = entry["note"]

        if image not in VALID_IMAGES:
            violations.append(f"{prefix}.image: {image!r} not in {VALID_IMAGES}")
        if not isinstance(env_digest, str) or not _ENV_DIGEST_RE.match(env_digest):
            violations.append(f"{prefix}.env_digest: must match ^sha256:[0-9a-f]{{64}}$")
        elif env_digest == PLACEHOLDER_DIGEST:
            violations.append(f"{prefix}.env_digest: all-zero placeholder digest is forbidden")
        elif env_digest in seen_digests:
            violations.append(f"{prefix}.env_digest: duplicate digest {env_digest}")
        else:
            seen_digests.add(env_digest)
        if not isinstance(tag, str) or not _TAG_RE.match(tag):
            violations.append(f"{prefix}.tag: must match ^v[0-9]+\\.[0-9]+\\.[0-9]+$")
        if not isinstance(git_sha, str) or not _GIT_SHA_RE.match(git_sha):
            violations.append(f"{prefix}.git_sha: must match ^[0-9a-f]{{40}}$")
        if not isinstance(signed_at, str) or not _SIGNED_AT_RE.match(signed_at):
            violations.append(f"{prefix}.signed_at: must be ISO-8601 UTC (YYYY-MM-DDTHH:MM:SSZ)")
        if status not in VALID_STATUSES:
            violations.append(f"{prefix}.status: {status!r} not in {VALID_STATUSES}")
        elif status == "active":
            if isinstance(image, str):
                active_count[image] = active_count.get(image, 0) + 1
        elif not (isinstance(note, str) and note.strip()):
            violations.append(f"{prefix}.note: non-empty note required when status != 'active'")
        if not isinstance(note, str):
            violations.append(f"{prefix}.note: must be a string")

    for image_name, count in sorted(active_count.items()):
        if count > 1:
            violations.append(f"image {image_name!r}: {count} active entries (at most 1 allowed)")

    return violations


def check_append_only(old_doc: dict[str, object], new_doc: dict[str, object]) -> list[str]:
    """Return violations of the append-only contract between two registry states.

    Rows are never deleted; ``image``/``env_digest``/``tag``/``git_sha``/
    ``signed_at`` of an existing row are immutable; ``status`` may only follow
    :data:`_ALLOWED_TRANSITIONS` (never back to ``active``). ``note`` may be
    amended (it is descriptive; :func:`check_registry` still requires it
    non-empty on non-active rows).
    """
    violations: list[str] = []

    def _keyed(doc: dict[str, object]) -> dict[tuple[str, str], dict[str, object]]:
        entries = doc.get("entries")
        keyed: dict[tuple[str, str], dict[str, object]] = {}
        if isinstance(entries, list):
            for entry in entries:
                if isinstance(entry, dict):
                    keyed[(str(entry.get("image")), str(entry.get("env_digest")))] = entry
        return keyed

    old_entries = _keyed(old_doc)
    new_entries = _keyed(new_doc)

    for key, old_entry in old_entries.items():
        image, digest = key
        new_entry = new_entries.get(key)
        if new_entry is None:
            violations.append(f"entry deleted (append-only): image={image} env_digest={digest}")
            continue
        for field in ("tag", "git_sha", "signed_at"):
            if old_entry.get(field) != new_entry.get(field):
                violations.append(
                    f"immutable field {field!r} changed on image={image} env_digest={digest}: "
                    f"{old_entry.get(field)!r} -> {new_entry.get(field)!r}"
                )
        old_status = str(old_entry.get("status"))
        new_status = str(new_entry.get("status"))
        allowed = _ALLOWED_TRANSITIONS.get(old_status, frozenset())
        if new_status not in allowed:
            violations.append(
                f"illegal status transition {old_status!r} -> {new_status!r} on "
                f"image={image} env_digest={digest}"
            )

    return violations


def load_registry(path: Path) -> dict[str, object]:
    """Parse + validate the registry at ``path`` (fail-closed).

    A missing file, malformed JSON, a non-object document, or any
    :func:`check_registry` violation raises :class:`EnvDigestRegistryError`
    listing the problem(s) — malformed is an error, never a silent ``None``.
    """
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise EnvDigestRegistryError(f"cannot read registry {path}: {exc}") from exc
    try:
        doc = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise EnvDigestRegistryError(f"malformed JSON in registry {path}: {exc}") from exc
    if not isinstance(doc, dict):
        raise EnvDigestRegistryError(f"registry {path} must be a JSON object")
    violations = check_registry(doc)
    if violations:
        raise EnvDigestRegistryError(f"invalid registry {path}: " + "; ".join(violations))
    return doc


def find_active_digest(doc: dict[str, object], image: str) -> str | None:
    """The unique active entry's ``env_digest`` for ``image``, or ``None``.

    ``None`` is the pre-bootstrap record-and-warn state (CLAR-CP-06-02); a
    validated registry can hold at most one active entry per image.
    """
    entries = doc.get("entries")
    if not isinstance(entries, list):
        return None
    for entry in entries:
        if (
            isinstance(entry, dict)
            and entry.get("image") == image
            and entry.get("status") == "active"
        ):
            digest = entry.get("env_digest")
            return str(digest) if digest is not None else None
    return None


def active_digest(doc: dict[str, object], image: str) -> str:
    """The unique active entry's ``env_digest`` for ``image``; raises if absent."""
    digest = find_active_digest(doc, image)
    if digest is None:
        raise EnvDigestRegistryError(f"no active env_digest entry for image {image!r}")
    return digest


def active_map(doc: dict[str, object]) -> dict[str, str]:
    """Map of ``image -> active env_digest`` (images with no active entry omitted)."""
    result: dict[str, str] = {}
    for image in VALID_IMAGES:
        digest = find_active_digest(doc, image)
        if digest is not None:
            result[image] = digest
    return result


def register(
    path: Path,
    *,
    image: str,
    env_digest: str,
    tag: str,
    git_sha: str,
    signed_at: str,
) -> None:
    """Roll ``image`` over to ``env_digest``: supersede the current active row
    (note = ``"superseded by <tag>"``), append the new active row, re-validate,
    and rewrite ``path`` (indent=2 + trailing newline).

    Idempotent when ``env_digest`` is already the active digest for ``image``.
    Never deletes rows. Any post-condition violation (e.g. re-registering a
    ``void`` digest -> duplicate) raises :class:`EnvDigestRegistryError`.
    """
    doc = load_registry(path)
    if find_active_digest(doc, image) == env_digest:
        return  # idempotent re-register

    entries = doc.get("entries")
    if not isinstance(entries, list):  # pragma: no cover — load_registry validated
        raise EnvDigestRegistryError(f"registry {path}: entries must be a list")
    for entry in entries:
        if (
            isinstance(entry, dict)
            and entry.get("image") == image
            and entry.get("status") == "active"
        ):
            entry["status"] = "superseded"
            entry["note"] = f"superseded by {tag}"
    entries.append(
        {
            "image": image,
            "env_digest": env_digest,
            "tag": tag,
            "git_sha": git_sha,
            "signed_at": signed_at,
            "status": "active",
            "note": "",
        }
    )
    violations = check_registry(doc)
    if violations:
        raise EnvDigestRegistryError(
            f"register({image!r}, {env_digest!r}) would invalidate the registry: "
            + "; ".join(violations)
        )
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    """CLI: ``check <path>`` (exit 1, print each violation) and
    ``register --path --image --digest --tag --git-sha [--signed-at]``."""
    parser = argparse.ArgumentParser(prog="env_digest_registry")
    sub = parser.add_subparsers(dest="command", required=True)

    check_p = sub.add_parser("check", help="validate a registry file")
    check_p.add_argument("path", nargs="?", default=str(_DEFAULT_REGISTRY_FILE))

    reg_p = sub.add_parser("register", help="roll an image over to a new active digest")
    reg_p.add_argument("--path", default=str(_DEFAULT_REGISTRY_FILE))
    reg_p.add_argument("--image", required=True, choices=VALID_IMAGES)
    reg_p.add_argument("--digest", required=True)
    reg_p.add_argument("--tag", required=True)
    reg_p.add_argument("--git-sha", required=True)
    reg_p.add_argument("--signed-at", default=None)

    args = parser.parse_args(argv)

    if args.command == "check":
        registry_path = Path(args.path)
        try:
            doc = json.loads(registry_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"ERROR (CLAR-DEPLOY-22): cannot parse {registry_path}: {exc}", file=sys.stderr)
            return 1
        if not isinstance(doc, dict):
            print(f"ERROR (CLAR-DEPLOY-22): {registry_path} is not a JSON object", file=sys.stderr)
            return 1
        violations = check_registry(doc)
        if violations:
            print(f"ERROR (CLAR-DEPLOY-22): invalid registry {registry_path}:", file=sys.stderr)
            for violation in violations:
                print(f"  - {violation}", file=sys.stderr)
            return 1
        return 0

    # register
    signed_at = args.signed_at
    if signed_at is None:
        from datetime import datetime, timezone

        signed_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")  # noqa: UP017
    try:
        register(
            Path(args.path),
            image=args.image,
            env_digest=args.digest,
            tag=args.tag,
            git_sha=args.git_sha,
            signed_at=signed_at,
        )
    except EnvDigestRegistryError as exc:
        print(f"ERROR (CLAR-DEPLOY-22): {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
