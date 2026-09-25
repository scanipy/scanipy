"""Versioned, artifact-local identity metadata (BHMEA R09).

The legacy single ``fingerprint_class`` cannot establish both graph and slice
canonicality. Readers never infer either new verdict from it. Processing state
is independent of strength, and native cross-refactor identity is exposed only
for the corrected v2 algorithms with both verdicts strong.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

ANNOTATION: Final = "canonical iff fingerprint_class = strong"
GRAPH_V2: Final = "scanipy-canonical-graph/2"
SLICE_V2: Final = "scanipy-slice-normal-form/2"
STATES: Final = frozenset(
    {"completed", "pending", "running", "failed", "not-applicable", "legacy-ambiguous"}
)
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


@dataclass(frozen=True)
class ArtifactIdentity:
    """A digest and its own verdict; missing evidence never defaults to strong."""

    status: str
    digest: str | None = None
    fingerprint_class: str | None = None
    namespace: str | None = None

    def __post_init__(self) -> None:
        if self.status not in STATES:
            raise ValueError(f"unknown artifact status: {self.status!r}")
        if self.digest is not None and (
            not isinstance(self.digest, str) or not _SHA256.fullmatch(self.digest)
        ):
            raise ValueError("artifact digest must be 64 lowercase hexadecimal characters")
        if self.status == "completed":
            if self.digest is None or self.fingerprint_class not in {"strong", "weak"}:
                raise ValueError("completed artifact requires its digest and independent class")
            if not isinstance(self.namespace, str) or not self.namespace:
                raise ValueError("completed artifact requires its algorithm namespace")
        elif self.fingerprint_class is not None or self.namespace is not None:
            raise ValueError("uncomputed/legacy artifact cannot assert a class or namespace")
        elif self.status != "legacy-ambiguous" and self.digest is not None:
            raise ValueError("uncomputed artifact cannot carry a computed digest")

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "digest": self.digest,
            "fingerprint_class": self.fingerprint_class,
            "namespace": self.namespace,
            "annotation": ANNOTATION,
        }

    @classmethod
    def from_dict(cls, value: object) -> ArtifactIdentity:
        if not isinstance(value, dict) or set(value) != {
            "status",
            "digest",
            "fingerprint_class",
            "namespace",
            "annotation",
        }:
            raise ValueError("invalid artifact descriptor shape")
        if value["annotation"] != ANNOTATION:
            raise ValueError("artifact annotation must retain its exact scoped literal")
        for key in ("status", "digest", "fingerprint_class", "namespace"):
            if value[key] is not None and not isinstance(value[key], str):
                raise ValueError(f"artifact {key} must be a string or null")
        if not isinstance(value["status"], str):
            raise ValueError("artifact status is required")
        return cls(value["status"], value["digest"], value["fingerprint_class"], value["namespace"])


def identities_from_finding(finding: object) -> tuple[ArtifactIdentity, ArtifactIdentity]:
    """Read explicit v2 fields or preserve ambiguous v1 metadata without promotion."""
    version = getattr(finding, "identity_schema_version", 1)
    if type(version) is not int or version not in {1, 2}:
        raise ValueError(f"unsupported identity schema version: {version!r}")
    identities: list[ArtifactIdentity] = []
    for prefix, digest_name in (("cpg_order", "cpg_order_hash"), ("slice", "slice_fingerprint")):
        digest = getattr(finding, digest_name, None) or None
        if isinstance(digest, bytes):
            digest = digest.hex()
        if version == 1:
            identities.append(ArtifactIdentity("legacy-ambiguous", digest))
        else:
            class_name = "cpg_order_class" if prefix == "cpg_order" else "slice_fingerprint_class"
            identities.append(
                ArtifactIdentity(
                    getattr(finding, f"{prefix}_status", "legacy-ambiguous"),
                    digest,
                    getattr(finding, class_name, None),
                    getattr(finding, f"{prefix}_namespace", None),
                )
            )
    return identities[0], identities[1]


def identity_metadata(finding: object) -> dict[str, object]:
    graph, sliced = identities_from_finding(finding)
    return {"schema_version": 2, "cpg_order": graph.to_dict(), "slice": sliced.to_dict()}


def validate_identity_metadata(value: object) -> tuple[ArtifactIdentity, ArtifactIdentity]:
    if not isinstance(value, dict) or set(value) != {"schema_version", "cpg_order", "slice"}:
        raise ValueError("invalid identity metadata shape")
    if type(value["schema_version"]) is not int or value["schema_version"] != 2:
        raise ValueError("unsupported identity metadata version")
    return ArtifactIdentity.from_dict(value["cpg_order"]), ArtifactIdentity.from_dict(
        value["slice"]
    )


def has_strong_v2_artifact_identities(finding: object) -> bool:
    """Necessary identity guard, not a replacement for scope/version/ambiguity checks."""
    try:
        graph, sliced = identities_from_finding(finding)
    except (ValueError, TypeError):
        return False
    return (
        graph.status == sliced.status == "completed"
        and graph.fingerprint_class == sliced.fingerprint_class == "strong"
        and graph.namespace == GRAPH_V2
        and sliced.namespace == SLICE_V2
    )
