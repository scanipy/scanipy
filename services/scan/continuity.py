"""Pure R07 continuity proposals; no persistence, authentication or absence proof.

Contract: docs/bhmea/OCCURRENCE-DECISION-CONTRACT.md sections 5-6 and
docs/bhmea/CONTINUITY-PURE-MODULE.md. INV-1/2/3/5 remain independent guards.
The production registry is EMPTY. Strong v2 metadata alone is not approval.
Inventory seals and human/operator authority must come from trusted adapters;
hashes bind supplied content but do not prove completeness or authenticity.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from dataclasses import asdict, dataclass
from typing import Literal

from analysis.artifact_identity import GRAPH_V2, SLICE_V2, ArtifactIdentity

POLICY_NAMESPACE = "scanipy-continuity-policy/1"
_SHA256 = re.compile(r"sha256:[0-9a-f]{64}\Z")
_REVISION = re.compile(r"[0-9a-f]{40}\Z")
_VERDICTS = frozenset({"unreviewed", "confirmed", "false_positive"})
_SUPPRESSIONS = frozenset({"active", "inactive"})


def _text(value: str, field: str) -> None:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > 2048
        or any(ord(character) < 32 for character in value)
    ):
        raise ValueError(f"{field} must be nonempty bounded text without control characters")


def _digest(value: str, field: str) -> None:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise ValueError(f"{field} must be sha256:<64 lowercase hex>")


def _revision(value: int) -> None:
    if type(value) is not int or value < 0:
        raise ValueError("revision must be a nonnegative integer")


def _references(values: tuple[str, ...], *, required: bool = False) -> None:
    if not isinstance(values, tuple) or (required and not values) or len(values) > 64:
        raise ValueError("evidence/references must be a bounded immutable tuple")
    for value in values:
        _text(value, "reference")
    if len(set(values)) != len(values):
        raise ValueError("duplicate evidence/reference")


def _hash(namespace: str, value: object) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(namespace.encode("ascii") + b"\n" + encoded).hexdigest()


@dataclass(frozen=True)
class CohortKey:
    """Close this entire cohort BEFORE considering identity or processing state."""

    org_id: str
    codebase_id: str
    repository_id: str
    lineage_id: str
    origin: str
    engine: str
    detector_id: str
    vulnerability_class: str
    language: str
    rule_semantic_digest: str
    s_version: str

    def __post_init__(self) -> None:
        for name, value in asdict(self).items():
            _text(value, name)
        _digest(self.rule_semantic_digest, "rule_semantic_digest")
        if self.origin not in {"deterministic-core", "oracle-passthrough"}:
            raise ValueError("unknown finding origin")


@dataclass(frozen=True)
class IdentityBinding:
    """Observed full analysis binding, not legacy image-only env_digest."""

    identity_policy_digest: str
    model_profile: str
    normalization_profile: str
    budget_policy: str
    observed_full_environment_manifest_digest: str
    analysis_code_revision: str
    analysis_code_content_digest: str

    def __post_init__(self) -> None:
        for name, value in asdict(self).items():
            _text(value, name)
            if "*" in value:
                raise ValueError("identity compatibility has no wildcard")
        for value in (
            self.identity_policy_digest,
            self.observed_full_environment_manifest_digest,
            self.analysis_code_content_digest,
        ):
            _digest(value, "identity binding digest")
        if not _REVISION.fullmatch(self.analysis_code_revision):
            raise ValueError("analysis_code_revision must be 40 lowercase hex")


@dataclass(frozen=True)
class IdentityObservation:
    artifact: ArtifactIdentity
    evidence_refs: tuple[str, ...] = ()
    failure_reason: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.artifact, ArtifactIdentity):
            raise ValueError("identity observation requires an R09 artifact descriptor")
        _references(self.evidence_refs, required=self.artifact.status in {"completed", "failed"})
        if self.failure_reason is not None:
            _text(self.failure_reason, "identity failure reason")
        if self.artifact.status == "failed" and self.failure_reason is None:
            raise ValueError("failed identity requires its actual failure reason")
        if self.artifact.status == "completed" and self.failure_reason is not None:
            raise ValueError("completed identity cannot carry a failure reason")


@dataclass(frozen=True)
class OccurrenceView:
    occurrence_id: str
    scan_id: str
    capture_id: str
    source_tree_digest: str
    cohort: CohortKey
    raw_result_digest: str
    scan_local_sink_binding: str
    duplicate_ambiguity: bool
    graph: IdentityObservation
    sliced: IdentityObservation
    binding: IdentityBinding | None

    def __post_init__(self) -> None:
        for value in (
            self.occurrence_id,
            self.scan_id,
            self.capture_id,
            self.scan_local_sink_binding,
        ):
            _text(value, "occurrence identifier")
        _digest(self.source_tree_digest, "source_tree_digest")
        _digest(self.raw_result_digest, "raw_result_digest")
        if not isinstance(self.cohort, CohortKey):
            raise ValueError("occurrence requires an explicit cohort")
        if type(self.duplicate_ambiguity) is not bool:
            raise ValueError("duplicate ambiguity must be explicit boolean")
        if not isinstance(self.graph, IdentityObservation) or not isinstance(
            self.sliced, IdentityObservation
        ):
            raise ValueError("both independent identity observations are required")
        if self.binding is not None and not isinstance(self.binding, IdentityBinding):
            raise ValueError("binding must be explicit observed identity binding or None")


def occurrence_digest(occurrence: OccurrenceView) -> str:
    return _hash("scanipy-continuity-occurrence-view/1", asdict(occurrence))


@dataclass(frozen=True)
class DetectionInventory:
    scan_id: str
    capture_id: str
    source_tree_digest: str
    cohort: CohortKey
    detection_state: str
    sealed: bool
    sealed_occurrence_ids: tuple[str, ...]
    occurrences: tuple[OccurrenceView, ...]
    evidence_refs: tuple[str, ...]
    content_digest: str

    def __post_init__(self) -> None:
        for value in (self.scan_id, self.capture_id):
            _text(value, "inventory identifier")
        _digest(self.source_tree_digest, "inventory source tree")
        _digest(self.content_digest, "inventory digest")
        if not isinstance(self.cohort, CohortKey):
            raise ValueError("inventory requires an explicit cohort")
        if self.detection_state not in {"pending", "running", "completed", "failed"}:
            raise ValueError("unknown detection state")
        if type(self.sealed) is not bool:
            raise ValueError("inventory sealed flag must be explicit boolean")
        _references(self.evidence_refs, required=self.sealed)
        if not isinstance(self.occurrences, tuple) or not isinstance(
            self.sealed_occurrence_ids, tuple
        ):
            raise ValueError("inventory must contain immutable tuples")
        for occurrence_id in self.sealed_occurrence_ids:
            _text(occurrence_id, "sealed occurrence id")
        ids: list[str] = []
        for occurrence in self.occurrences:
            if not isinstance(occurrence, OccurrenceView):
                raise ValueError("inventory contains an invalid occurrence")
            if (
                occurrence.scan_id != self.scan_id
                or occurrence.capture_id != self.capture_id
                or occurrence.source_tree_digest != self.source_tree_digest
                or occurrence.cohort != self.cohort
            ):
                raise ValueError("occurrence is outside inventory scope/capture")
            ids.append(occurrence.occurrence_id)
        if len(set(ids)) != len(ids) or len(set(self.sealed_occurrence_ids)) != len(
            self.sealed_occurrence_ids
        ):
            raise ValueError("duplicate occurrence inventory entry")
        if set(ids) != set(self.sealed_occurrence_ids):
            raise ValueError("exact occurrence inventory mismatch")
        if self.content_digest != inventory_digest(
            scan_id=self.scan_id,
            capture_id=self.capture_id,
            source_tree_digest=self.source_tree_digest,
            cohort=self.cohort,
            detection_state=self.detection_state,
            sealed=self.sealed,
            sealed_occurrence_ids=self.sealed_occurrence_ids,
            occurrences=self.occurrences,
            evidence_refs=self.evidence_refs,
        ):
            raise ValueError("inventory content digest mismatch")


def inventory_digest(
    *,
    scan_id: str,
    capture_id: str,
    source_tree_digest: str,
    cohort: CohortKey,
    detection_state: str,
    sealed: bool,
    sealed_occurrence_ids: tuple[str, ...],
    occurrences: tuple[OccurrenceView, ...],
    evidence_refs: tuple[str, ...],
) -> str:
    """Bind all supplied records independent of adapter row order; not a seal proof."""
    payload = {
        "scan_id": scan_id,
        "capture_id": capture_id,
        "source_tree_digest": source_tree_digest,
        "cohort": asdict(cohort),
        "detection_state": detection_state,
        "sealed": sealed,
        "sealed_occurrence_ids": sorted(sealed_occurrence_ids),
        "occurrences": [
            asdict(occurrence)
            for occurrence in sorted(occurrences, key=lambda item: item.occurrence_id)
        ],
        "evidence_refs": sorted(evidence_refs),
    }
    return _hash("scanipy-continuity-inventory/1", payload)


@dataclass(frozen=True)
class CompatibilityProfile:
    engine: str
    detector_id: str
    vulnerability_class: str
    language: str
    rule_semantic_digest: str
    s_version: str
    binding: IdentityBinding
    graph_namespace: str = GRAPH_V2
    slice_namespace: str = SLICE_V2

    def __post_init__(self) -> None:
        for value in (
            self.engine,
            self.detector_id,
            self.vulnerability_class,
            self.language,
            self.s_version,
        ):
            _text(value, "policy compatibility profile")
            if "*" in value:
                raise ValueError("policy profiles have no wildcard")
        if self.engine not in {"ifds", "ide"}:
            raise ValueError("only deterministic-core engines can receive continuity policy")
        _digest(self.rule_semantic_digest, "policy rule semantics")
        if not isinstance(self.binding, IdentityBinding):
            raise ValueError("policy profile requires an exact full identity binding")
        if self.graph_namespace != GRAPH_V2 or self.slice_namespace != SLICE_V2:
            raise ValueError("unsupported continuity namespace; explicit implementation required")


@dataclass(frozen=True)
class PolicyDefinition:
    profiles: tuple[CompatibilityProfile, ...]
    evidence_refs: tuple[str, ...]
    review_revision_ref: str
    namespace: str = POLICY_NAMESPACE

    def __post_init__(self) -> None:
        if self.namespace != POLICY_NAMESPACE:
            raise ValueError("unsupported matching policy namespace")
        if not isinstance(self.profiles, tuple) or not self.profiles:
            raise ValueError("policy requires nonempty immutable exact profiles")
        if any(not isinstance(profile, CompatibilityProfile) for profile in self.profiles):
            raise ValueError("invalid policy profile")
        if len(set(self.profiles)) != len(self.profiles):
            raise ValueError("duplicate policy profile")
        _references(self.evidence_refs, required=True)
        _text(self.review_revision_ref, "review revision reference")

    @property
    def digest(self) -> str:
        # Array order is reviewed content: changing it creates a new policy digest.
        return _hash(POLICY_NAMESPACE, asdict(self))


@dataclass(frozen=True)
class PolicyEntry:
    definition: PolicyDefinition
    content_digest: str
    state: Literal["active", "revoked"]
    activation_event_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.definition, PolicyDefinition):
            raise ValueError("registry requires a policy definition")
        if self.content_digest != self.definition.digest:
            raise ValueError("registry policy content digest mismatch")
        if self.state not in {"active", "revoked"}:
            raise ValueError("unknown policy state")
        _text(self.activation_event_id, "activation event id")


@dataclass(frozen=True)
class PolicyRegistrySnapshot:
    revision: int = 0
    entries: tuple[PolicyEntry, ...] = ()
    used_activation_event_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _revision(self.revision)
        if not isinstance(self.entries, tuple) or any(
            not isinstance(entry, PolicyEntry) for entry in self.entries
        ):
            raise ValueError("registry entries must be immutable typed records")
        if len({entry.content_digest for entry in self.entries}) != len(self.entries):
            raise ValueError("ambiguous duplicate registry policy")
        if len({entry.activation_event_id for entry in self.entries}) != len(self.entries):
            raise ValueError("activation event id must identify one policy activation")
        if not isinstance(self.used_activation_event_ids, tuple):
            raise ValueError("activation history must be an immutable tuple")
        for event_id in self.used_activation_event_ids:
            _text(event_id, "historical activation event id")
        if len(set(self.used_activation_event_ids)) != len(self.used_activation_event_ids):
            raise ValueError("duplicate historical activation event id")
        if not {entry.activation_event_id for entry in self.entries} <= set(
            self.used_activation_event_ids
        ):
            raise ValueError("registry activation is missing from retained activation history")

    def active(self, digest: str) -> PolicyEntry | None:
        return next(
            (
                entry
                for entry in self.entries
                if entry.content_digest == digest and entry.state == "active"
            ),
            None,
        )


# No default policy is authorized by tests, v2 names, or a client approval flag.
PRODUCTION_POLICY_REGISTRY = PolicyRegistrySnapshot()


def validate_registry_transition(
    previous: PolicyRegistrySnapshot, current: PolicyRegistrySnapshot
) -> None:
    """Validate a proposed authority event; the caller must commit under CAS.

    Keeping revoked entries prevents removal/re-addition from laundering an old
    activation. Actual append-only event history and operator auth are external.
    """
    if current.revision != previous.revision + 1:
        raise ValueError("registry transition requires exactly the next revision")
    old = {entry.content_digest: entry for entry in previous.entries}
    new = {entry.content_digest: entry for entry in current.entries}
    if not old.keys() <= new.keys():
        raise ValueError("registry retains revoked policies; removal is forbidden")
    old_activation_ids = set(previous.used_activation_event_ids)
    new_activation_ids = set(current.used_activation_event_ids)
    if not old_activation_ids <= new_activation_ids:
        raise ValueError("registry must retain every historical activation event id")
    introduced: set[str] = set()
    for digest, entry in new.items():
        prior = old.get(digest)
        if prior is None:
            if entry.activation_event_id in old_activation_ids:
                raise ValueError("new policy requires a fresh activation event")
            introduced.add(entry.activation_event_id)
        elif prior.state == "revoked" and entry.state == "active":
            if entry.activation_event_id in old_activation_ids:
                raise ValueError("reactivation requires a fresh activation event")
            introduced.add(entry.activation_event_id)
        elif entry.activation_event_id != prior.activation_event_id:
            raise ValueError("activation event can change only on explicit reactivation")
    if new_activation_ids - old_activation_ids != introduced:
        raise ValueError("activation history additions must match actual activation events")


@dataclass(frozen=True)
class DimensionDecision:
    value: str
    event_id: str
    revision: int
    references: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.value not in _VERDICTS | _SUPPRESSIONS:
            raise ValueError("unknown human decision value")
        _text(self.event_id, "human decision event id")
        _revision(self.revision)
        _references(self.references)


@dataclass(frozen=True)
class DecisionSnapshot:
    target_scope: Literal["occurrence", "entity"]
    target_id: str
    cohort: CohortKey
    revision: int
    verdict: DimensionDecision | None = None
    suppression: DimensionDecision | None = None

    def __post_init__(self) -> None:
        if self.target_scope not in {"occurrence", "entity"}:
            raise ValueError("unknown human decision scope")
        _text(self.target_id, "decision target id")
        if not isinstance(self.cohort, CohortKey):
            raise ValueError("decision requires a scoped cohort")
        _revision(self.revision)
        for decision, allowed in ((self.verdict, _VERDICTS), (self.suppression, _SUPPRESSIONS)):
            if decision is not None and (
                not isinstance(decision, DimensionDecision)
                or decision.value not in allowed
                or decision.revision > self.revision
            ):
                raise ValueError("decision dimension/value/revision mismatch")


@dataclass(frozen=True)
class EntitySnapshot:
    entity_id: str
    cohort: CohortKey
    lifecycle: Literal["open", "resolved", "reappeared", "uncertain"]
    revision: int
    decisions: DecisionSnapshot

    def __post_init__(self) -> None:
        _text(self.entity_id, "entity id")
        _revision(self.revision)
        if self.lifecycle not in {"open", "resolved", "reappeared", "uncertain"}:
            raise ValueError("unknown entity lifecycle")
        if (
            not isinstance(self.decisions, DecisionSnapshot)
            or self.decisions.target_scope != "entity"
            or self.decisions.target_id != self.entity_id
            or self.decisions.cohort != self.cohort
        ):
            raise ValueError("entity decision target/scope mismatch")


@dataclass(frozen=True)
class PredecessorEntity:
    occurrence_id: str
    entity: EntitySnapshot

    def __post_init__(self) -> None:
        _text(self.occurrence_id, "predecessor occurrence id")
        if not isinstance(self.entity, EntitySnapshot):
            raise ValueError("predecessor requires scoped entity snapshot")


@dataclass(frozen=True)
class LineageSnapshot:
    cohort: CohortKey
    predecessor_scan_id: str
    current_scan_id: str
    revision: int

    def __post_init__(self) -> None:
        if not isinstance(self.cohort, CohortKey):
            raise ValueError("lineage requires scoped cohort")
        _text(self.predecessor_scan_id, "predecessor scan")
        _text(self.current_scan_id, "current scan")
        if self.predecessor_scan_id == self.current_scan_id:
            raise ValueError("continuity requires distinct predecessor/current scans")
        _revision(self.revision)


@dataclass(frozen=True)
class GuardRevisions:
    cohort: CohortKey
    predecessor_scan_id: str
    current_scan_id: str
    lineage_revision: int
    registry_revision: int
    policy_digest: str
    activation_event_id: str
    entity_id: str
    entity_revision: int
    decision_revision: int
    predecessor_inventory_digest: str
    current_inventory_digest: str

    def __post_init__(self) -> None:
        if not isinstance(self.cohort, CohortKey):
            raise ValueError("guards require a scoped cohort")
        for revision_value in (
            self.lineage_revision,
            self.registry_revision,
            self.entity_revision,
            self.decision_revision,
        ):
            _revision(revision_value)
        for value in (
            self.predecessor_scan_id,
            self.current_scan_id,
            self.activation_event_id,
            self.entity_id,
        ):
            _text(value, "guard identifier")
        if self.predecessor_scan_id == self.current_scan_id:
            raise ValueError("guards require distinct predecessor/current scans")
        for value in (
            self.policy_digest,
            self.predecessor_inventory_digest,
            self.current_inventory_digest,
        ):
            _digest(value, "guard digest")


def guards_match(expected: GuardRevisions, current: GuardRevisions) -> bool:
    """Pure precondition comparison, NOT database locking/CAS or authorization."""
    return (
        isinstance(expected, GuardRevisions)
        and isinstance(current, GuardRevisions)
        and expected == current
    )


@dataclass(frozen=True)
class LinkProposal:
    predecessor_occurrence_id: str
    current_occurrence_id: str
    entity_id: str
    current_occurrence_digest: str
    profile: CompatibilityProfile
    slice_digest: str
    predecessor_graph_digest: str
    current_graph_digest: str
    inherit_entity_decisions: bool
    guards: GuardRevisions


@dataclass(frozen=True)
class OccurrenceDisposition:
    occurrence_id: str
    status: Literal["linked", "new_identity", "blocked"]
    reason: str
    link: LinkProposal | None = None


@dataclass(frozen=True)
class ContinuityPlan:
    dispositions: tuple[OccurrenceDisposition, ...]
    retained_predecessor_ids: tuple[str, ...]
    group_block_reason: str | None = None


def _profile(occurrence: OccurrenceView) -> CompatibilityProfile | None:
    graph, sliced = occurrence.graph.artifact, occurrence.sliced.artifact
    cohort = occurrence.cohort
    if (
        cohort.origin != "deterministic-core"
        or cohort.engine not in {"ifds", "ide"}
        or graph.status != "completed"
        or sliced.status != "completed"
        or graph.fingerprint_class != "strong"
        or sliced.fingerprint_class != "strong"
        or graph.namespace != GRAPH_V2
        or sliced.namespace != SLICE_V2
        or occurrence.binding is None
        or occurrence.duplicate_ambiguity
    ):
        return None
    return CompatibilityProfile(
        cohort.engine,
        cohort.detector_id,
        cohort.vulnerability_class,
        cohort.language,
        cohort.rule_semantic_digest,
        cohort.s_version,
        occurrence.binding,
    )


def plan_continuity(
    before: DetectionInventory,
    after: DetectionInventory,
    *,
    policy_digest: str,
    registry: PolicyRegistrySnapshot = PRODUCTION_POLICY_REGISTRY,
    lineage: LineageSnapshot,
    predecessor_entities: tuple[PredecessorEntity, ...] = (),
) -> ContinuityPlan:
    """One disposition per current occurrence; never resolve or silently drop any.

    Scope, inventory closure and every potential competitor precede matching.
    Exact equal slice + profile is necessary; graph digest equality is not.
    The persistence adapter must authenticate inputs and atomically check guards.
    """
    _digest(policy_digest, "matching policy digest")
    if (
        before.cohort != after.cohort
        or lineage.cohort != after.cohort
        or lineage.predecessor_scan_id != before.scan_id
        or lineage.current_scan_id != after.scan_id
    ):
        raise ValueError("comparison scope or explicit lineage mismatch")
    previous = tuple(sorted(before.occurrences, key=lambda item: item.occurrence_id))
    current = tuple(sorted(after.occurrences, key=lambda item: item.occurrence_id))
    previous_ids = {item.occurrence_id for item in previous}
    if previous_ids & {item.occurrence_id for item in current}:
        raise ValueError("occurrence ids must distinguish separate scans")
    if not isinstance(predecessor_entities, tuple):
        raise ValueError("predecessor entity associations must be an immutable tuple")
    associations: dict[str, EntitySnapshot] = {}
    for association in predecessor_entities:
        if (
            not isinstance(association, PredecessorEntity)
            or association.occurrence_id not in previous_ids
            or association.entity.cohort != before.cohort
            or association.occurrence_id in associations
        ):
            raise ValueError("invalid/duplicate/cross-scope predecessor entity association")
        associations[association.occurrence_id] = association.entity
    # Two predecessor occurrences already linked to one entity are not a unique
    # history, even if they currently carry different slices. Do not split it.
    duplicate_entity = len({item.entity_id for item in associations.values()}) != len(associations)

    def blocked(reason: str) -> ContinuityPlan:
        return ContinuityPlan(
            tuple(OccurrenceDisposition(item.occurrence_id, "blocked", reason) for item in current),
            tuple(sorted(previous_ids)),
            reason,
        )

    if not before.sealed or not after.sealed:
        return blocked("unsealed_detection_inventory")
    if before.detection_state != "completed" or after.detection_state != "completed":
        return blocked("detection_incomplete")
    entry = registry.active(policy_digest)
    if entry is None:
        return blocked("matching_policy_inactive_or_unaccepted")
    if duplicate_entity:
        return blocked("ambiguous_predecessor_entity")
    for group in (previous, current):
        if any(
            count > 1 for count in Counter(item.scan_local_sink_binding for item in group).values()
        ):
            return blocked("multiple_occurrences_at_one_sink")
    profiles: dict[str, CompatibilityProfile] = {}
    for item in previous + current:
        profile = _profile(item)
        if profile is None or profile not in entry.definition.profiles:
            return blocked("ineligible_or_unsupported_potential_competitor")
        profiles[item.occurrence_id] = profile

    def key(item: OccurrenceView) -> tuple[CompatibilityProfile, str | None]:
        return profiles[item.occurrence_id], item.sliced.artifact.digest

    before_keys = Counter(key(item) for item in previous)
    after_keys = Counter(key(item) for item in current)
    used: set[str] = set()
    dispositions: list[OccurrenceDisposition] = []
    for item in current:
        identity = key(item)
        if before_keys[identity] > 1 or after_keys[identity] > 1:
            dispositions.append(
                OccurrenceDisposition(item.occurrence_id, "blocked", "ambiguous_equal_slice")
            )
            continue
        predecessor = next((old for old in previous if key(old) == identity), None)
        if predecessor is None:
            dispositions.append(
                OccurrenceDisposition(
                    item.occurrence_id, "new_identity", "no_equal_eligible_predecessor"
                )
            )
            continue
        entity = associations.get(predecessor.occurrence_id)
        if entity is None:
            dispositions.append(
                OccurrenceDisposition(
                    item.occurrence_id, "blocked", "predecessor_entity_unavailable"
                )
            )
            continue
        # _profile established completed descriptors; these assertions narrow
        # types only and do not replace a trust/authentication boundary.
        assert item.sliced.artifact.digest is not None
        assert item.graph.artifact.digest is not None
        assert predecessor.graph.artifact.digest is not None
        guards = GuardRevisions(
            after.cohort,
            before.scan_id,
            after.scan_id,
            lineage.revision,
            registry.revision,
            policy_digest,
            entry.activation_event_id,
            entity.entity_id,
            entity.revision,
            entity.decisions.revision,
            before.content_digest,
            after.content_digest,
        )
        link = LinkProposal(
            predecessor.occurrence_id,
            item.occurrence_id,
            entity.entity_id,
            occurrence_digest(item),
            profiles[item.occurrence_id],
            item.sliced.artifact.digest,
            predecessor.graph.artifact.digest,
            item.graph.artifact.digest,
            entity.lifecycle == "open",
            guards,
        )
        used.add(predecessor.occurrence_id)
        dispositions.append(
            OccurrenceDisposition(item.occurrence_id, "linked", "unique_eligible_identity", link)
        )
    return ContinuityPlan(tuple(dispositions), tuple(sorted(previous_ids - used)))


@dataclass(frozen=True)
class EffectiveDimension:
    value: str
    source: Literal["default", "occurrence", "entity"]
    event_id: str | None = None
    references: tuple[str, ...] = ()


@dataclass(frozen=True)
class EffectiveDecisions:
    verdict: EffectiveDimension
    suppression: EffectiveDimension
    inheritance_active: bool
    inheritance_block_reason: str | None


def effective_decisions(
    occurrence: OccurrenceView,
    *,
    link: LinkProposal | None = None,
    entity: EntitySnapshot | None = None,
    registry: PolicyRegistrySnapshot = PRODUCTION_POLICY_REGISTRY,
    direct: DecisionSnapshot | None = None,
) -> EffectiveDecisions:
    """Resolve current entity authority then independent occurrence overrides.

    A stored proposal is not self-authenticating: load only committed, authorized
    links. Never pass a client-constructed registry/decision/link here as authority.
    Occurrence-only decisions are never an input to plan_continuity.
    """
    if direct is not None and (
        direct.target_scope != "occurrence"
        or direct.target_id != occurrence.occurrence_id
        or direct.cohort != occurrence.cohort
    ):
        raise ValueError("direct decision belongs to another occurrence/scope")
    reason: str | None = "no_authorized_link"
    inherited: DecisionSnapshot | None = None
    if link is not None:
        entry = registry.active(link.guards.policy_digest)
        if (
            link.current_occurrence_id != occurrence.occurrence_id
            or link.current_occurrence_digest != occurrence_digest(occurrence)
            or link.guards.cohort != occurrence.cohort
            or link.guards.current_scan_id != occurrence.scan_id
            or link.guards.entity_id != link.entity_id
        ):
            reason = "link_occurrence_scope_or_content_mismatch"
        elif entry is None or entry.activation_event_id != link.guards.activation_event_id:
            reason = "policy_revoked_or_reactivation_needs_adjudication"
        elif registry.revision < link.guards.registry_revision:
            reason = "stale_registry_snapshot"
        elif (
            link.profile not in entry.definition.profiles
            or _profile(occurrence) != link.profile
            or occurrence.sliced.artifact.digest != link.slice_digest
            or occurrence.graph.artifact.digest != link.current_graph_digest
        ):
            reason = "link_identity_policy_mismatch"
        elif (
            entity is None
            or entity.entity_id != link.entity_id
            or entity.cohort != occurrence.cohort
        ):
            reason = "entity_scope_or_identity_mismatch"
        elif (
            entity.revision < link.guards.entity_revision
            or entity.decisions.revision < link.guards.decision_revision
        ):
            reason = "stale_entity_or_decision_snapshot"
        elif not link.inherit_entity_decisions or entity.lifecycle != "open":
            reason = "entity_requires_fresh_human_review"
        else:
            inherited = entity.decisions
            reason = None

    def dimension(name: str, default: str) -> EffectiveDimension:
        # None means no direct override. Explicit unreviewed/inactive means a
        # human clear and MUST shadow inherited confirmed/active values.
        for source, decisions in (("occurrence", direct), ("entity", inherited)):
            if decisions is not None:
                value = decisions.verdict if name == "verdict" else decisions.suppression
                if value is not None:
                    if source == "occurrence":
                        return EffectiveDimension(
                            value.value, "occurrence", value.event_id, value.references
                        )
                    return EffectiveDimension(
                        value.value, "entity", value.event_id, value.references
                    )
        return EffectiveDimension(default, "default")

    return EffectiveDecisions(
        dimension("verdict", "unreviewed"),
        dimension("suppression", "inactive"),
        inherited is not None,
        reason,
    )
