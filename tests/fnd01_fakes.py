"""Hermetic builders for CMP-FND-01 (findings normalizer / SARIF emitter) specs.

No I/O, no DB, no upstream component. CMP-CORE-02 (slice_fingerprint /
fingerprint_class) is unbuilt, so these builders supply those as ordinary typed
inputs — exactly the build-ahead contract: the emitter accepts them, never
computes them.

``make_finding`` returns the shipped concrete
:class:`analysis.sarif.canonical_emit._Finding` (a frozen dataclass that
satisfies the :class:`~analysis.sarif.canonical_emit.WorkerFinding` Protocol),
with every required provenance field populated by default. ``make_broken_finding``
clears exactly one required field so the normalizer's fail-fast pre-emit pass can
be exercised (negative control (a)).
"""

from __future__ import annotations

import hashlib
from typing import Any

from analysis.sarif.canonical_emit import _Finding


def _hex(seed: str) -> str:
    """A deterministic 64-char lowercase hex digest from a seed string."""
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


# A pinned, valid environment digest + spec version reused across fixtures so two
# findings differ only where a test intends them to.
ENV_DIGEST = "sha256:" + ("7" * 64)
S_VERSION = "1.4.0"


def make_finding(
    *,
    origin: str = "deterministic-core",
    rule_id: str = "scanipy/path-traversal/extract-all-archive",
    uri: str = "src/extract.py",
    start_line: int = 42,
    cpg_order_hash: str | None = None,
    slice_fingerprint: str | None = None,
    fingerprint_class: str = "strong",
    engine: str | None = None,
    severity: str = "high",
    class_: str = "path-traversal",
    status: str = "open",
    precondition_status: str = "closed-world",
    message: str = "Untrusted archive extraction without path containment.",
    witness_blob_uri: str | None = "s3://scanipy-witness/orgs/x/witness.json.zst",
    spec_provenance: str | None = "global-revalidated",
    **overrides: Any,
) -> _Finding:
    """Build a fully-populated, valid worker finding.

    ``determinism_partition`` defaults to ``origin`` (DOC-SARIF §6: equal at
    emission time). ``engine`` defaults to a partition-consistent value
    (``ifds`` for core, ``semgrep`` for oracle). Hashes default to deterministic
    seeds derived from ``(rule_id, uri, start_line, origin)`` so distinct findings
    get distinct, stable hashes.
    """
    if engine is None:
        engine = "ifds" if origin == "deterministic-core" else "semgrep"
    seed = f"{rule_id}|{uri}|{start_line}|{origin}"
    fields: dict[str, Any] = {
        "origin": origin,
        "determinism_partition": origin,
        "engine": engine,
        "S_version": S_VERSION,
        "env_digest": ENV_DIGEST,
        "cpg_order_hash": cpg_order_hash if cpg_order_hash is not None else _hex("cpg|" + seed),
        "fingerprint_class": fingerprint_class,
        "slice_fingerprint": (
            slice_fingerprint if slice_fingerprint is not None else _hex("slice|" + seed)
        ),
        "rule_id": rule_id,
        "message": message,
        "uri": uri,
        "start_line": start_line,
        "start_col": 13,
        "end_line": start_line,
        "end_col": 27,
        "severity": severity,
        "class_": class_,
        "status": status,
        "precondition_status": precondition_status,
        "witness_blob_uri": witness_blob_uri,
        "spec_provenance": spec_provenance,
    }
    fields.update(overrides)
    return _Finding(**fields)


def make_broken_finding(missing_field: str, **kwargs: Any) -> _Finding:
    """A finding with exactly ``missing_field`` blanked to ``""`` (a null/blank
    provenance field). Feeds negative control (a): the normalizer must REJECT it.
    """
    base = make_finding(**kwargs)
    import dataclasses

    return dataclasses.replace(base, **{missing_field: ""})  # type: ignore[arg-type]
