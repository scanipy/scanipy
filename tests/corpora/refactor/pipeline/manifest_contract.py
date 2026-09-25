"""Schema-2 generator hashing/serialization; gates implement this framing independently.

A report gate must not import executable Python from a caller-supplied corpus.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

TREE_DIGEST_ALGORITHM = "sha256-length-prefixed-path-and-content-v1"


def json_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True) + "\n").encode()


def manifest_bytes(value: dict) -> bytes:
    """Readable root, one compact case per line: below the 500 KiB artifact gate.

    Keep all fields and expectations; only whitespace differs from pretty JSON.
    Exact serialized bytes are bound by the lock's case_manifest_sha256.
    """
    fields = []
    for key, item in sorted(value.items()):
        if key == "cases":
            entries = [
                json.dumps(case, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
                for case in item
            ]
            payload = "[\n" + ",\n".join("    " + entry for entry in entries) + "\n  ]"
        else:
            payload = json.dumps(item, sort_keys=True, ensure_ascii=True)
        fields.append("  " + json.dumps(key) + ": " + payload)
    return ("{\n" + ",\n".join(fields) + "\n}\n").encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def tree_digest(root: Path) -> str:
    """Sorted POSIX relative paths, each with uint64be path/content lengths.

    Symlinks are rejected rather than followed, including the root. Empty
    directories are not semantic files and do not contribute. This algorithm
    has unambiguous boundaries even when file contents contain NUL bytes.
    """
    if root.is_symlink() or not root.is_dir():
        raise ValueError(f"not a regular source directory: {root}")
    entries = list(root.rglob("*"))
    if any(path.is_symlink() for path in entries):
        raise ValueError(f"symlinks are forbidden in corpus source trees: {root}")
    if any(not path.is_file() and not path.is_dir() for path in entries):
        raise ValueError(f"non-regular filesystem entry in corpus source tree: {root}")
    digest = hashlib.sha256()
    for path in sorted(
        (p for p in entries if p.is_file()), key=lambda p: p.relative_to(root).as_posix()
    ):
        name = path.relative_to(root).as_posix().encode("utf-8")
        content = path.read_bytes()
        digest.update(len(name).to_bytes(8, "big"))
        digest.update(name)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return "sha256:" + digest.hexdigest()


def canonical_digest(lock: dict[str, object]) -> str:
    stable = {
        key: value
        for key, value in lock.items()
        if key not in {"corpus_digest", "built_at", "built_by"}
    }
    return sha256_bytes(
        json.dumps(stable, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    )


def safe_relative(root: Path, relative: str) -> Path:
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError(f"unsafe corpus-relative path: {relative!r}")
    candidate = root / path
    if not candidate.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"path escapes corpus root: {relative!r}")
    return candidate
