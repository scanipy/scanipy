"""CMP-DEPLOY-01 — deterministic object-store key scheme + in-memory store.

Implementation contract: ``docs/components/DOC-CMP-DEPLOY-01.md`` §3.1 (storage),
§5 (INV-2 anchor), §9 (AC-DEPLOY-01b). Substrate decision: ``CLAR-DEPLOY-02``
(``docs/cross-cutting/DOC-DEPLOY-DECISIONS.md``) + ``CLAR-DEPLOY-16`` layer-1
(S3 prefix isolation). Artifact set: ``DOC-CMP-SNAP-01.md`` §4.2 (the five
persisted snapshot artifacts named by ``AC-SNAP-01a``).

The chosen object store is Amazon S3 (CLAR-DEPLOY-02). S3 is not natively
content-addressable, but the key scheme

    orgs/{org_id}/codebases/{codebase_id}/snapshots/{commit_sha}/{env_digest}/{artifact_type}

delivers content-addressability *transitively*: ``commit_sha`` is Git's content
hash over the source tree and ``env_digest`` is the worker image digest
(``AC-SNAP-05b``), so the path is byte-for-byte reproducible from
``(source, Env)`` and carries ``env_digest`` in the path itself (INV-2). This
module is the substrate primitive that proves the scheme — :class:`SnapshotKeyBuilder`
mints the keys deterministically and :class:`InMemoryObjectStore` is an offline
S3 stand-in with the CLAR-DEPLOY-16 prefix-isolation backstop enforced.

This module emits no findings, so the four provenance fields (INV-1/2/5) are not
threaded *here*; it provides the physical key path into which ``CMP-SNAP-01``
writes ``env_digest`` (DOC-CMP-DEPLOY-01 §8 — "physical anchors").
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable

# The five persisted snapshot artifacts (DOC-CMP-SNAP-01 §4.2, from AC-SNAP-01a),
# mapped to their deterministic ``{artifact_type}`` key suffix. Insertion order is
# the SDD enumeration order; the mapping is the source of truth for both the key
# builder and the AC-DEPLOY-01b cross-test.
SNAPSHOT_ARTIFACT_SUFFIXES: dict[str, str] = {
    "cpg_tarball": "cpg.tar.zst",
    "reverse_symbol_index": "reverse_symbol_index.json.zst",
    "dynamic_call_graph": "dyn_call_graph.json.zst",
    "delta_graph": "delta_graph.json.zst",
    "precondition_status": "precondition_status.json",
}

# The artifact-type keys, frozen as a tuple for stable iteration order.
SNAPSHOT_ARTIFACT_TYPES: tuple[str, ...] = tuple(SNAPSHOT_ARTIFACT_SUFFIXES)

ArtifactType = Literal[
    "cpg_tarball",
    "reverse_symbol_index",
    "dynamic_call_graph",
    "delta_graph",
    "precondition_status",
]


class ObjectStoreError(Exception):
    """Base class for object-store substrate errors (fail-closed posture)."""


class PathTraversalError(ObjectStoreError):
    """A key component contained a path-traversal / separator payload.

    The CLAR-DEPLOY-16 layer-1 backstop: a request parameter (``org_id``,
    ``codebase_id``, ``commit_sha``, ``env_digest``) carrying ``..``, a ``/``, or
    an encoded variant must never resolve a key outside the requesting org's
    ``orgs/{org_id}/...`` prefix. Mints fail-closed rather than normalising.
    """


class CrossTenantAccessError(ObjectStoreError):
    """A read/write resolved to a key outside the requesting org's prefix.

    Even a well-formed key that does not begin with ``orgs/{org_id}/`` is denied
    on access (defence in depth behind :class:`PathTraversalError`).
    """


# Characters / sequences that must never appear in a key component. ``/`` would
# let a component span path segments; ``..`` is the classic traversal token;
# control / encoded separators are rejected to defeat ``%2e%2e`` style payloads.
_FORBIDDEN_SUBSTRINGS: tuple[str, ...] = (
    "/",
    "\\",
    "..",
    "%2e",
    "%2f",
    "%5c",
    "\x00",
)


def _validate_component(name: str, value: str) -> str:
    """Reject any key component that could escape the org prefix (CLAR-DEPLOY-16).

    Fail-closed: an empty value or any forbidden substring raises
    :class:`PathTraversalError`. Case-folded so ``%2E`` is caught as ``%2e``.
    """
    if value == "":
        raise PathTraversalError(f"empty {name!r} key component is not permitted")
    folded = value.casefold()
    for token in _FORBIDDEN_SUBSTRINGS:
        if token in folded:
            raise PathTraversalError(
                f"{name!r} component {value!r} contains forbidden sequence {token!r} "
                "(CLAR-DEPLOY-16 layer-1 path-traversal guard)"
            )
    return value


@dataclass(frozen=True)
class SnapshotKeyBuilder:
    """Mints the deterministic S3 key scheme of ``CLAR-DEPLOY-02``.

    Every component is traversal-validated at construction, so an instance can
    only ever produce keys inside its own ``orgs/{org_id}/...`` prefix. The class
    is frozen and carries no I/O — it is pure, hence the produced keys are
    byte-for-byte reproducible from the inputs (AC-DEPLOY-01b determinism).
    """

    org_id: str
    codebase_id: str
    commit_sha: str
    env_digest: str

    def __post_init__(self) -> None:
        _validate_component("org_id", self.org_id)
        _validate_component("codebase_id", self.codebase_id)
        _validate_component("commit_sha", self.commit_sha)
        _validate_component("env_digest", self.env_digest)

    @property
    def prefix(self) -> str:
        """The org-scoped key prefix every artifact for this snapshot lives under."""
        return (
            f"orgs/{self.org_id}/codebases/{self.codebase_id}"
            f"/snapshots/{self.commit_sha}/{self.env_digest}/"
        )

    def artifact_key(self, artifact_type: ArtifactType) -> str:
        """Return the full deterministic key for one of the five SNAP-01 artifacts.

        ``orgs/{org_id}/codebases/{codebase_id}/snapshots/{commit_sha}/``
        ``{env_digest}/{artifact_type_suffix}`` (CLAR-DEPLOY-02).
        """
        suffix = SNAPSHOT_ARTIFACT_SUFFIXES.get(artifact_type)
        if suffix is None:
            raise ObjectStoreError(
                f"unknown artifact_type {artifact_type!r}; "
                f"expected one of {SNAPSHOT_ARTIFACT_TYPES}"
            )
        return f"{self.prefix}{suffix}"

    def all_artifact_keys(self) -> dict[str, str]:
        """All five artifact keys, in SDD enumeration order (AC-SNAP-01a)."""
        return {
            artifact_type: self.artifact_key(artifact_type)  # type: ignore[arg-type]
            for artifact_type in SNAPSHOT_ARTIFACT_TYPES
        }


@runtime_checkable
class ObjectStore(Protocol):
    """Structural subset of the S3 surface the snapshot persistence layer uses.

    Production wires this to a boto3 S3 client scoped by a per-scan IAM session
    policy (CLAR-DEPLOY-16 layer-1); tests wire :class:`InMemoryObjectStore`.
    """

    def put(self, org_id: str, key: str, body: bytes) -> None: ...

    def get(self, org_id: str, key: str) -> bytes: ...


@dataclass
class InMemoryObjectStore:
    """Deterministic offline S3 stand-in with prefix-isolation enforced.

    Every ``put`` / ``get`` re-checks that the resolved key begins with the
    requesting org's ``orgs/{org_id}/`` prefix *and* that the key is itself
    traversal-clean — so a forged or traversal-bearing key cannot reach another
    org's objects (CLAR-DEPLOY-16, AC-DEPLOY-05b modelled offline). No real AWS.
    """

    _objects: dict[str, bytes]

    def __init__(self) -> None:
        self._objects = {}

    def _guard(self, org_id: str, key: str) -> str:
        _validate_component("org_id", org_id)
        # The key may legitimately contain ``/`` segment separators, so it is not
        # run through _validate_component; instead each segment is checked for the
        # traversal tokens and the org prefix is enforced.
        folded = key.casefold()
        for token in ("..", "%2e", "%5c", "\\", "\x00"):
            if token in folded:
                raise PathTraversalError(
                    f"key {key!r} contains forbidden traversal sequence {token!r}"
                )
        expected_prefix = f"orgs/{org_id}/"
        if not key.startswith(expected_prefix):
            raise CrossTenantAccessError(
                f"key {key!r} does not resolve under the requesting org prefix "
                f"{expected_prefix!r} (CLAR-DEPLOY-16)"
            )
        return key

    def put(self, org_id: str, key: str, body: bytes) -> None:
        self._objects[self._guard(org_id, key)] = body

    def get(self, org_id: str, key: str) -> bytes:
        resolved = self._guard(org_id, key)
        if resolved not in self._objects:
            raise ObjectStoreError(f"no object at key {resolved!r}")
        return self._objects[resolved]


__all__ = [
    "SNAPSHOT_ARTIFACT_SUFFIXES",
    "SNAPSHOT_ARTIFACT_TYPES",
    "ArtifactType",
    "CrossTenantAccessError",
    "InMemoryObjectStore",
    "ObjectStore",
    "ObjectStoreError",
    "PathTraversalError",
    "SnapshotKeyBuilder",
]
