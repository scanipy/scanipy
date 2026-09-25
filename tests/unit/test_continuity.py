"""Controlled policy falsifiers, not acceptance of any production normalization."""

from __future__ import annotations

import hashlib
import itertools
import json
from dataclasses import asdict, replace
from types import SimpleNamespace

import pytest

from analysis.artifact_identity import GRAPH_V2, SLICE_V2, ArtifactIdentity
from services.scan.continuity import (
    POLICY_NAMESPACE,
    PRODUCTION_POLICY_REGISTRY,
    CohortKey,
    CompatibilityProfile,
    DecisionSnapshot,
    DetectionInventory,
    DimensionDecision,
    EntityLifecycleEvent,
    EntitySnapshot,
    HumanAuthorization,
    IdentityBinding,
    IdentityObservation,
    LineageSnapshot,
    OccurrenceView,
    PolicyDefinition,
    PolicyEntry,
    PolicyRegistrySnapshot,
    PredecessorEntity,
    ReferenceMetadata,
    effective_decisions,
    guards_match,
    inventory_digest,
    plan_continuity,
    validate_entity_transition,
    validate_registry_transition,
)

pytestmark = pytest.mark.unit


def digest(label):
    return "sha256:" + hashlib.sha256(label.encode()).hexdigest()


def identity(label, namespace, strength="strong"):
    return IdentityObservation(
        ArtifactIdentity("completed", digest(label)[7:], strength, namespace),
        (f"controlled-evidence:{label}",),
    )


def cohort():
    return CohortKey(
        "org",
        "codebase",
        "repository",
        "lineage",
        "deterministic-core",
        "ifds",
        "detector",
        "sql-injection",
        "java",
        digest("rule"),
        "1.2.3",
    )


def binding():
    return IdentityBinding(
        digest("controlled-identity-policy"),
        "controlled-model/1",
        "controlled-normalization/1",
        "controlled-budget/1",
        digest("observed-full-environment"),
        "a" * 40,
        digest("observed-analysis-source"),
    )


def occurrence(side, number=1, *, slice_key="same", scope=None):
    return OccurrenceView(
        f"occurrence-{side}-{number}",
        f"scan-{side}",
        f"capture-{side}",
        digest(f"tree-{side}"),
        scope or cohort(),
        digest(f"raw-{side}-{number}"),
        f"sink-{side}-{number}",
        False,
        identity(f"graph-{side}-{number}", GRAPH_V2),
        identity(slice_key, SLICE_V2),
        binding(),
    )


def inventory(side, occurrences=(), *, scope=None, state="completed", sealed=True, **changes):
    values = {
        "scan_id": f"scan-{side}",
        "capture_id": f"capture-{side}",
        "source_tree_digest": digest(f"tree-{side}"),
        "cohort": scope or cohort(),
        "detection_state": state,
        "sealed": sealed,
        "sealed_occurrence_ids": tuple(item.occurrence_id for item in occurrences),
        "occurrences": tuple(occurrences),
        "evidence_refs": (f"controlled-inventory-evidence:{side}",),
    }
    values.update(changes)
    return DetectionInventory(**values, content_digest=inventory_digest(**values))


def profile(item):
    scope = item.cohort
    return CompatibilityProfile(
        scope.engine,
        scope.detector_id,
        scope.vulnerability_class,
        scope.language,
        scope.rule_semantic_digest,
        scope.s_version,
        item.binding,
    )


def registry_for(*profiles):
    policy = PolicyDefinition(tuple(profiles), ("controlled-evidence:not-production",), "test-only")
    entry = PolicyEntry(policy, policy.digest, "active", "controlled-activation-1")
    return policy, PolicyRegistrySnapshot(1, (entry,), (entry.activation_event_id,))


def entity(item, number=1):
    decisions = DecisionSnapshot(
        "entity",
        f"entity-{number}",
        item.cohort,
        2,
        DimensionDecision("false_positive", "verdict-event", 1, ("inert:review-note",), 0),
        DimensionDecision("active", "suppression-event", 2, authorized_generation=0),
    )
    return EntitySnapshot(f"entity-{number}", item.cohort, "open", 3, decisions, 0)


@pytest.fixture
def sample():
    before = occurrence("before")
    after = occurrence("after")
    policy, registry = registry_for(profile(before))
    previous_entity = entity(before)
    return SimpleNamespace(
        before=before,
        after=after,
        policy=policy,
        registry=registry,
        entity=previous_entity,
        lineage=LineageSnapshot(before.cohort, before.scan_id, after.scan_id, 5),
    )


def plan(sample, *, before=None, after=None, entities=None, registry=None):
    previous = (sample.before,) if before is None else tuple(before)
    current = (sample.after,) if after is None else tuple(after)
    return plan_continuity(
        inventory("before", previous),
        inventory("after", current),
        policy_digest=sample.policy.digest,
        registry=sample.registry if registry is None else registry,
        lineage=sample.lineage,
        predecessor_entities=(PredecessorEntity(sample.before.occurrence_id, sample.entity),)
        if entities is None
        else entities,
    )


def linked(sample):
    result = plan(sample)
    assert result.dispositions[0].status == "linked"
    assert result.dispositions[0].link is not None
    return result.dispositions[0].link


def effective(sample, **changes):
    values = {"link": linked(sample), "entity": sample.entity, "registry": sample.registry}
    values.update(changes)
    return effective_decisions(sample.after, **values)


def test_production_policy_registry_is_empty_even_with_strong_v2(sample):
    assert PRODUCTION_POLICY_REGISTRY == PolicyRegistrySnapshot()
    result = plan(sample, registry=PRODUCTION_POLICY_REGISTRY)
    assert result.group_block_reason == "matching_policy_inactive_or_unaccepted"
    assert result.retained_predecessor_ids == (sample.before.occurrence_id,)
    assert result.dispositions[0].status == "blocked"


def test_whole_graph_and_source_movement_are_not_equality_requirements(sample):
    link = linked(sample)
    assert sample.before.source_tree_digest != sample.after.source_tree_digest
    assert sample.before.scan_local_sink_binding != sample.after.scan_local_sink_binding
    assert link.predecessor_graph_digest != link.current_graph_digest
    assert link.slice_digest == sample.before.sliced.artifact.digest
    result = effective(sample)
    assert result.inheritance_active
    assert (result.verdict.value, result.suppression.value) == ("false_positive", "active")
    assert result.verdict.source == "entity"


@pytest.mark.parametrize(
    "graph_class,slice_class", tuple(itertools.product(("strong", "weak"), repeat=2))
)
def test_four_independent_artifact_classes(sample, graph_class, slice_class):
    changed = replace(
        sample.after,
        graph=identity("new-graph", GRAPH_V2, graph_class),
        sliced=identity("same", SLICE_V2, slice_class),
    )
    result = plan(sample, after=(changed,))
    assert (result.dispositions[0].status == "linked") == (graph_class == slice_class == "strong")


def damaged(item, kind):
    if kind == "weak-graph":
        return replace(item, graph=identity("competitor-graph", GRAPH_V2, "weak"))
    if kind == "weak-slice":
        return replace(item, sliced=identity("competitor-slice", SLICE_V2, "weak"))
    if kind == "missing-binding":
        return replace(item, binding=None)
    if kind == "duplicate-result":
        return replace(item, duplicate_ambiguity=True)
    if kind in {"legacy-graph", "unknown-graph"}:
        return replace(
            item, graph=identity("g", "graph/1" if kind == "legacy-graph" else "graph/99")
        )
    if kind in {"legacy-slice", "unknown-slice"}:
        return replace(
            item, sliced=identity("s", "slice/1" if kind == "legacy-slice" else "slice/99")
        )
    observation = IdentityObservation(
        ArtifactIdentity(kind),
        ("controlled-failure:evidence",) if kind == "failed" else (),
        "actual controlled timeout" if kind == "failed" else None,
    )
    return replace(item, sliced=observation)


@pytest.mark.parametrize("side", ("before", "after"))
@pytest.mark.parametrize(
    "kind",
    (
        "weak-graph",
        "weak-slice",
        "missing-binding",
        "duplicate-result",
        "legacy-graph",
        "unknown-graph",
        "legacy-slice",
        "unknown-slice",
        "failed",
        "pending",
        "running",
        "not-applicable",
        "legacy-ambiguous",
    ),
)
def test_unresolved_competitor_cannot_disappear_before_uniqueness_check(sample, side, kind):
    competitor = damaged(occurrence(side, 2, slice_key="different"), kind)
    result = plan(sample, **{side: (getattr(sample, side), competitor)})
    assert result.group_block_reason == "ineligible_or_unsupported_potential_competitor"
    assert all(item.status == "blocked" for item in result.dispositions)
    assert sample.before.occurrence_id in result.retained_predecessor_ids


@pytest.mark.parametrize("before_count,after_count", tuple(itertools.product(range(3), repeat=2)))
def test_exhaustive_small_equal_slice_multiplicity_and_row_order(sample, before_count, after_count):
    previous = tuple(occurrence("before", n) for n in range(before_count))
    current = tuple(occurrence("after", n) for n in range(after_count))
    associations = tuple(
        PredecessorEntity(item.occurrence_id, entity(item, n)) for n, item in enumerate(previous)
    )
    outcomes = []
    for old_order in itertools.permutations(previous):
        for new_order in itertools.permutations(current):
            result = plan(sample, before=old_order, after=new_order, entities=associations)
            outcomes.append(result)
            assert len(result.dispositions) == after_count
            links = [item for item in result.dispositions if item.status == "linked"]
            assert len(links) == int(before_count == after_count == 1)
            assert len(result.retained_predecessor_ids) == before_count - len(links)
    assert all(result == outcomes[0] for result in outcomes)


def test_distinct_slices_can_match_separately_in_a_closed_cohort(sample):
    previous = (sample.before, occurrence("before", 2, slice_key="second"))
    current = (sample.after, occurrence("after", 2, slice_key="second"))
    associations = tuple(
        PredecessorEntity(item.occurrence_id, entity(item, n)) for n, item in enumerate(previous)
    )
    result = plan(sample, before=previous, after=current, entities=associations)
    assert [item.status for item in result.dispositions] == ["linked", "linked"]
    assert not result.retained_predecessor_ids


@pytest.mark.parametrize("side", ("before", "after"))
def test_multiple_findings_at_one_sink_block_even_different_slices(sample, side):
    competitor = replace(
        occurrence(side, 2, slice_key="different"),
        scan_local_sink_binding=getattr(sample, side).scan_local_sink_binding,
    )
    result = plan(sample, **{side: (getattr(sample, side), competitor)})
    assert result.group_block_reason == "multiple_occurrences_at_one_sink"


def test_one_entity_cannot_silently_split_across_predecessors(sample):
    second = occurrence("before", 2, slice_key="second")
    associations = tuple(
        PredecessorEntity(item.occurrence_id, sample.entity) for item in (sample.before, second)
    )
    result = plan(sample, before=(sample.before, second), entities=associations)
    assert result.group_block_reason == "ambiguous_predecessor_entity"


@pytest.mark.parametrize(
    "field,value",
    (
        ("org_id", "other-org"),
        ("codebase_id", "other-codebase"),
        ("repository_id", "other-repository"),
        ("lineage_id", "other-lineage"),
        ("origin", "oracle-passthrough"),
        ("engine", "ide"),
        ("detector_id", "other-detector"),
        ("vulnerability_class", "xss"),
        ("language", "python"),
        ("rule_semantic_digest", digest("other-rule")),
        ("s_version", "1.2.4"),
    ),
)
def test_every_scope_axis_requires_explicit_separate_cohort(sample, field, value):
    changed_scope = replace(sample.before.cohort, **{field: value})
    previous = replace(sample.before, cohort=changed_scope)
    with pytest.raises(ValueError, match="scope or explicit lineage"):
        plan_continuity(
            inventory("before", (previous,), scope=changed_scope),
            inventory("after", (sample.after,)),
            policy_digest=sample.policy.digest,
            registry=sample.registry,
            lineage=sample.lineage,
        )


@pytest.mark.parametrize(
    "field,value",
    (
        ("identity_policy_digest", digest("other-identity-policy")),
        ("model_profile", "controlled-model/2"),
        ("normalization_profile", "controlled-normalization/2"),
        ("budget_policy", "controlled-budget/2"),
        ("observed_full_environment_manifest_digest", digest("other-full-environment")),
        ("analysis_code_revision", "b" * 40),
        ("analysis_code_content_digest", digest("other-code")),
    ),
)
def test_exact_compatibility_binding_no_implicit_upgrade(sample, field, value):
    changed = replace(sample.after, binding=replace(sample.after.binding, **{field: value}))
    result = plan(sample, after=(changed,))
    assert result.group_block_reason == "ineligible_or_unsupported_potential_competitor"
    policy, registry = registry_for(profile(sample.before), profile(changed))
    sample.policy = policy
    result = plan(sample, after=(changed,), registry=registry)
    assert result.dispositions[0].status == "new_identity"
    assert result.retained_predecessor_ids == (sample.before.occurrence_id,)


def test_oracle_strong_auxiliary_identities_do_not_authorize_inheritance(sample):
    scope = replace(cohort(), origin="oracle-passthrough", engine="external")
    before, after = occurrence("before", scope=scope), occurrence("after", scope=scope)
    result = plan_continuity(
        inventory("before", (before,), scope=scope),
        inventory("after", (after,), scope=scope),
        policy_digest=sample.policy.digest,
        registry=sample.registry,
        lineage=LineageSnapshot(scope, before.scan_id, after.scan_id, 1),
    )
    assert result.group_block_reason == "ineligible_or_unsupported_potential_competitor"
    with pytest.raises(ValueError, match="only deterministic-core"):
        profile(before)


@pytest.mark.parametrize(
    "state,sealed", (("completed", False), ("pending", True), ("running", True), ("failed", True))
)
@pytest.mark.parametrize("side", ("before", "after"))
def test_unsealed_or_failed_detection_never_means_successful_absence(sample, state, sealed, side):
    before = inventory(
        "before",
        (sample.before,),
        state=state if side == "before" else "completed",
        sealed=sealed if side == "before" else True,
    )
    after = inventory(
        "after",
        (sample.after,),
        state=state if side == "after" else "completed",
        sealed=sealed if side == "after" else True,
    )
    result = plan_continuity(
        before,
        after,
        policy_digest=sample.policy.digest,
        registry=sample.registry,
        lineage=sample.lineage,
    )
    assert result.dispositions[0].status == "blocked"
    assert result.retained_predecessor_ids == (sample.before.occurrence_id,)


def test_empty_current_and_changed_identity_retain_history_without_resolution(sample):
    empty = plan(sample, after=())
    assert empty.dispositions == ()
    assert empty.retained_predecessor_ids == (sample.before.occurrence_id,)
    changed = replace(sample.after, sliced=identity("changed", SLICE_V2))
    result = plan(sample, after=(changed,))
    assert result.dispositions[0].status == "new_identity"
    assert result.retained_predecessor_ids == empty.retained_predecessor_ids


def test_missing_predecessor_entity_is_visible_not_silently_created(sample):
    result = plan(sample, entities=())
    assert result.dispositions[0].reason == "predecessor_entity_unavailable"
    assert result.retained_predecessor_ids == (sample.before.occurrence_id,)


@pytest.mark.parametrize(
    "field,value",
    (
        ("scan_id", "other-scan"),
        ("capture_id", "other-capture"),
        ("source_tree_digest", digest("other-tree")),
        ("cohort", replace(cohort(), org_id="other-org")),
    ),
)
def test_inventory_rejects_cross_capture_or_scope_records(sample, field, value):
    with pytest.raises(ValueError, match="outside inventory scope/capture"):
        inventory("after", (replace(sample.after, **{field: value}),))


def test_inventory_rejects_omissions_duplicates_and_changed_content(sample):
    with pytest.raises(ValueError, match="inventory mismatch"):
        inventory("after", (sample.after,), sealed_occurrence_ids=())
    with pytest.raises(ValueError, match="duplicate occurrence"):
        inventory("after", (sample.after, sample.after))
    original = inventory("after", (sample.after,))
    with pytest.raises(ValueError, match="digest mismatch"):
        replace(original, evidence_refs=("tampered-evidence",))
    with pytest.raises(ValueError, match="digest mismatch"):
        replace(original, content_digest=digest("wrong"))
    with pytest.raises(ValueError, match="immutable tuples"):
        replace(original, occurrences=[sample.after])


def test_content_digests_bind_actual_identity_and_evidence_not_row_order(sample):
    second = occurrence("after", 2, slice_key="second")
    left = inventory("after", (sample.after, second))
    right = inventory("after", (second, sample.after))
    assert left.content_digest == right.content_digest
    changed = inventory(
        "after", (replace(sample.after, graph=identity("different", GRAPH_V2)), second)
    )
    assert changed.content_digest != left.content_digest


def test_policy_digest_exact_framing_and_tamper_rejection(sample):
    encoded = json.dumps(
        asdict(sample.policy),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode()
    expected = "sha256:" + hashlib.sha256(POLICY_NAMESPACE.encode() + b"\n" + encoded).hexdigest()
    assert sample.policy.digest == expected
    changed = replace(sample.policy, review_revision_ref="different-review")
    assert changed.digest != sample.policy.digest
    with pytest.raises(ValueError, match="digest mismatch"):
        replace(sample.registry.entries[0], definition=changed)
    with pytest.raises(ValueError, match="duplicate policy"):
        replace(sample.policy, profiles=sample.policy.profiles * 2)
    with pytest.raises(ValueError, match="duplicate registry"):
        replace(sample.registry, entries=sample.registry.entries * 2)
    with pytest.raises(ValueError, match="wildcard"):
        replace(sample.policy.profiles[0], language="*")
    with pytest.raises(ValueError, match="unsupported continuity namespace"):
        replace(sample.policy.profiles[0], slice_namespace="slice/99")


def test_policy_revocation_and_reactivation_require_explicit_link_readjudication(sample):
    original = sample.registry.entries[0]
    revoked = replace(sample.registry, revision=2, entries=(replace(original, state="revoked"),))
    validate_registry_transition(sample.registry, revoked)
    assert not effective(sample, registry=revoked).inheritance_active
    cached_activation = replace(revoked, revision=3, entries=(original,))
    with pytest.raises(ValueError, match="fresh activation"):
        validate_registry_transition(revoked, cached_activation)
    reactivated = PolicyRegistrySnapshot(
        3,
        (replace(original, activation_event_id="new-reviewed-activation"),),
        (*revoked.used_activation_event_ids, "new-reviewed-activation"),
    )
    validate_registry_transition(revoked, reactivated)
    assert not effective(sample, registry=reactivated).inheritance_active
    fresh_link = plan(sample, registry=reactivated).dispositions[0].link
    assert effective(sample, registry=reactivated, link=fresh_link).inheritance_active
    with pytest.raises(ValueError, match="removal is forbidden"):
        validate_registry_transition(revoked, PolicyRegistrySnapshot(3))
    with pytest.raises(ValueError, match="next revision"):
        validate_registry_transition(sample.registry, replace(revoked, revision=4))
    revoked_again = replace(
        reactivated, revision=4, entries=(replace(reactivated.entries[0], state="revoked"),)
    )
    validate_registry_transition(reactivated, revoked_again)
    reuse_ancient_id = replace(revoked_again, revision=5, entries=(original,))
    with pytest.raises(ValueError, match="fresh activation"):
        validate_registry_transition(revoked_again, reuse_ancient_id)
    with pytest.raises(ValueError, match="every historical activation"):
        validate_registry_transition(
            reactivated,
            replace(revoked_again, used_activation_event_ids=("new-reviewed-activation",)),
        )


@pytest.mark.parametrize(
    "dimension,new_value", (("suppression", "inactive"), ("verdict", "unreviewed"))
)
def test_human_revocations_are_current_and_dimension_local(sample, dimension, new_value):
    changed_decisions = replace(
        sample.entity.decisions,
        revision=3,
        **{dimension: DimensionDecision(new_value, "human-revocation", 3, authorized_generation=0)},
    )
    current = replace(sample.entity, revision=4, decisions=changed_decisions)
    result = effective(sample, entity=current)
    assert result.inheritance_active
    assert getattr(result, dimension).value == new_value
    if dimension == "suppression":
        assert result.verdict.value == "false_positive"
    else:
        assert result.suppression.value == "active"


@pytest.mark.parametrize(
    "dimension,value", (("suppression", "inactive"), ("verdict", "unreviewed"))
)
def test_direct_explicit_clear_shadows_only_its_inherited_dimension(sample, dimension, value):
    direct = DecisionSnapshot(
        "occurrence",
        sample.after.occurrence_id,
        sample.after.cohort,
        1,
        **{dimension: DimensionDecision(value, "direct-clear", 1)},
    )
    result = effective(sample, direct=direct)
    assert getattr(result, dimension).source == "occurrence"
    assert getattr(result, dimension).value == value
    other = "verdict" if dimension == "suppression" else "suppression"
    assert getattr(result, other).source == "entity"


def test_false_positive_verdict_never_silently_activates_suppression(sample):
    verdict_only = replace(
        sample.entity, decisions=replace(sample.entity.decisions, suppression=None)
    )
    result = effective(sample, entity=verdict_only)
    assert result.verdict.value == "false_positive"
    assert result.suppression.value == "inactive"


def test_direct_weak_occurrence_decision_is_allowed_but_cannot_carry_forward(sample):
    weak = damaged(sample.after, "weak-slice")
    direct = DecisionSnapshot(
        "occurrence",
        weak.occurrence_id,
        weak.cohort,
        1,
        suppression=DimensionDecision("active", "local-human-suppression", 1),
    )
    result = effective_decisions(weak, direct=direct)
    assert result.suppression.source == "occurrence"
    assert not result.inheritance_active
    assert plan(sample, after=(weak,)).dispositions[0].status == "blocked"
    with pytest.raises(ValueError, match="another occurrence/scope"):
        effective_decisions(sample.before, direct=direct)
    # An occurrence snapshot cannot be smuggled into the entity decision channel.
    with pytest.raises(ValueError, match="entity decision target/scope"):
        replace(sample.entity, decisions=direct)


@pytest.mark.parametrize("lifecycle", ("resolved", "reappeared", "uncertain"))
def test_resolved_reappearance_and_uncertainty_never_reactivate_suppression(sample, lifecycle):
    current = replace(sample.entity, lifecycle=lifecycle)
    assert effective(sample, entity=current).suppression.value == "inactive"
    sample.entity = current
    link = linked(sample)
    assert not link.inherit_entity_decisions
    reopened = replace(current, lifecycle="open", revision=current.revision + 1)
    assert effective(sample, link=link, entity=reopened).suppression.value == "inactive"


@pytest.mark.parametrize(
    "field",
    (
        "cohort",
        "predecessor_scan_id",
        "current_scan_id",
        "lineage_revision",
        "registry_revision",
        "policy_digest",
        "activation_event_id",
        "entity_id",
        "entity_revision",
        "entity_lifecycle_generation",
        "decision_revision",
        "predecessor_inventory_digest",
        "current_inventory_digest",
    ),
)
def test_every_guard_axis_is_compared_without_claiming_database_cas(sample, field):
    guards = linked(sample).guards
    original = getattr(guards, field)
    value = (
        original + 1
        if isinstance(original, int)
        else (
            replace(original, org_id="other-org")
            if isinstance(original, CohortKey)
            else digest("different-guard")
            if "digest" in field
            else original + "-new"
        )
    )
    assert guards_match(guards, guards)
    assert not guards_match(guards, replace(guards, **{field: value}))


def test_stale_snapshots_cannot_apply_a_newer_link(sample):
    assert not effective(sample, registry=replace(sample.registry, revision=0)).inheritance_active
    assert not effective(sample, entity=replace(sample.entity, revision=2)).inheritance_active
    old_decisions = replace(sample.entity.decisions, revision=1, suppression=None)
    assert not effective(
        sample, entity=replace(sample.entity, decisions=old_decisions)
    ).inheritance_active


def test_link_cannot_be_replayed_on_another_scope_or_payload(sample):
    link = linked(sample)
    changed = replace(sample.after, raw_result_digest=digest("other-result"))
    result = effective_decisions(changed, link=link, entity=sample.entity, registry=sample.registry)
    assert not result.inheritance_active
    foreign = replace(
        sample.entity,
        cohort=replace(sample.entity.cohort, org_id="other"),
        decisions=replace(
            sample.entity.decisions, cohort=replace(sample.entity.cohort, org_id="other")
        ),
    )
    assert not effective(sample, entity=foreign).inheritance_active


@pytest.mark.parametrize(
    "factory",
    (
        lambda: IdentityObservation(ArtifactIdentity("failed")),
        lambda: IdentityObservation(
            ArtifactIdentity("completed", digest("g")[7:], "strong", GRAPH_V2)
        ),
        lambda: replace(binding(), observed_full_environment_manifest_digest="image-only"),
        lambda: replace(binding(), normalization_profile="*"),
        lambda: DimensionDecision("fixed", "event", 1),
        lambda: DimensionDecision("active", "event", True),
        lambda: replace(cohort(), org_id="\nmalicious"),
    ),
)
def test_malformed_evidence_decisions_and_bindings_fail_closed(factory):
    with pytest.raises(ValueError):
        factory()


def change_lifecycle(previous, state):
    actions = {
        "resolved": "resolve",
        "reappeared": "reappear",
        "uncertain": "mark_uncertain",
        "open": "open_for_review",
    }
    current = replace(
        previous,
        revision=previous.revision + 1,
        lifecycle=state,
        lifecycle_generation=previous.lifecycle_generation + 1,
    )
    event = EntityLifecycleEvent(
        f"controlled-lifecycle-{current.revision}",
        previous.entity_id,
        previous.cohort,
        actions[state],
        previous.revision,
        previous.lifecycle_generation,
        ("controlled-lifecycle-evidence:not-real-coverage",),
    )
    validate_entity_transition(previous, current, lifecycle_event=event)
    return current, event


def authorize_dimension(previous, dimension, value="confirmed", *, event_id=None):
    revision = previous.decisions.revision + 1
    event_id = event_id or f"controlled-human-{dimension}-{revision}"
    if dimension == "metadata":
        old_refs = previous.decisions.metadata.references if previous.decisions.metadata else ()
        event = ReferenceMetadata(event_id, revision, (*old_refs, f"inert:note-{revision}"))
    else:
        event = DimensionDecision(
            value, event_id, revision, authorized_generation=previous.lifecycle_generation
        )
    authorization = HumanAuthorization(
        previous.entity_id,
        previous.cohort,
        dimension,
        event,
        "controlled-human-event-store:not-auth",
    )
    current = replace(
        previous,
        revision=previous.revision + 1,
        decisions=replace(previous.decisions, revision=revision, **{dimension: event}),
    )
    validate_entity_transition(previous, current, human_authorizations=(authorization,))
    return current, authorization


@pytest.mark.parametrize(
    "states",
    (
        ("resolved", "open"),
        ("resolved", "reappeared", "open"),
        ("uncertain", "open"),
        ("resolved", "reappeared", "uncertain", "open"),
        ("resolved", "open", "resolved", "reappeared", "open"),
    ),
)
def test_originally_open_link_never_revives_after_lifecycle_cycles(sample, states):
    old_link = linked(sample)
    current = sample.entity
    historical_decisions = current.decisions
    for state in states:
        current, _ = change_lifecycle(current, state)
        observed = effective(sample, link=old_link, entity=current)
        assert not observed.inheritance_active
        assert observed.suppression.value == "inactive"
        assert current.decisions == historical_decisions  # History is not erased/restamped.
    assert current.lifecycle == "open"
    assert current.lifecycle_generation == len(states)
    sample.entity = current
    fresh_link = linked(sample)
    assert fresh_link.guards.entity_lifecycle_generation == current.lifecycle_generation
    assert not effective(sample, link=fresh_link).inheritance_active
    reviewed_verdict, _ = authorize_dimension(current, "verdict", "confirmed")
    verdict_only = effective(sample, link=fresh_link, entity=reviewed_verdict)
    assert verdict_only.verdict.value == "confirmed"
    assert verdict_only.verdict.source == "entity"
    assert verdict_only.suppression.value == "inactive"
    assert reviewed_verdict.decisions.suppression == historical_decisions.suppression
    reviewed_both, _ = authorize_dimension(reviewed_verdict, "suppression", "active")
    assert effective(sample, link=fresh_link, entity=reviewed_both).suppression.value == "active"
    assert effective(sample, link=old_link, entity=reviewed_both).suppression.value == "inactive"


def test_reference_metadata_cannot_renew_any_dimension_after_reopen(sample):
    closed, _ = change_lifecycle(sample.entity, "resolved")
    reopened, _ = change_lifecycle(closed, "open")
    with_note, authorization = authorize_dimension(reopened, "metadata")
    assert with_note.decisions.verdict == reopened.decisions.verdict
    assert with_note.decisions.suppression == reopened.decisions.suppression
    sample.entity = with_note
    assert not effective(sample).inheritance_active
    restamped = replace(
        with_note,
        decisions=replace(
            with_note.decisions,
            suppression=replace(
                with_note.decisions.suppression,
                authorized_generation=with_note.lifecycle_generation,
            ),
        ),
    )
    with pytest.raises(ValueError, match="unchanged dimension cannot be restamped"):
        validate_entity_transition(reopened, restamped, human_authorizations=(authorization,))
    # Updating per-authorization references is not a metadata-only authorization either.
    altered = replace(
        with_note,
        decisions=replace(
            with_note.decisions,
            suppression=replace(with_note.decisions.suppression, references=("new",)),
        ),
    )
    with pytest.raises(ValueError, match="unchanged dimension cannot be restamped"):
        validate_entity_transition(reopened, altered, human_authorizations=(authorization,))


def test_explicit_occurrence_override_survives_entity_epoch_barrier_only_locally(sample):
    old_link = linked(sample)
    closed, _ = change_lifecycle(sample.entity, "resolved")
    reopened, _ = change_lifecycle(closed, "open")
    direct = DecisionSnapshot(
        "occurrence",
        sample.after.occurrence_id,
        sample.after.cohort,
        1,
        suppression=DimensionDecision("active", "direct-human", 1),
    )
    result = effective(sample, entity=reopened, link=old_link, direct=direct)
    assert not result.inheritance_active
    assert result.suppression.value == "active" and result.suppression.source == "occurrence"
    with pytest.raises(ValueError, match="another occurrence"):
        effective_decisions(sample.before, direct=direct)


@pytest.mark.parametrize("generation", (0, 2, 3))
def test_lifecycle_generation_cannot_stay_or_jump_on_transition(sample, generation):
    current, event = change_lifecycle(sample.entity, "resolved")
    with pytest.raises(ValueError, match="exactly once"):
        validate_entity_transition(
            sample.entity,
            replace(current, lifecycle_generation=generation),
            lifecycle_event=event,
        )


def test_lifecycle_generation_cannot_rollback_or_advance_on_same_state(sample):
    closed, _ = change_lifecycle(sample.entity, "resolved")
    reopened, event = change_lifecycle(closed, "open")
    with pytest.raises(ValueError, match="exactly once"):
        validate_entity_transition(
            closed, replace(reopened, lifecycle_generation=0), lifecycle_event=event
        )
    reviewed, authorization = authorize_dimension(reopened, "verdict")
    with pytest.raises(ValueError, match="exactly once"):
        validate_entity_transition(
            reopened,
            replace(reviewed, lifecycle_generation=reviewed.lifecycle_generation + 1),
            human_authorizations=(authorization,),
        )


def test_reopen_requires_explicit_matching_typed_lifecycle_event(sample):
    closed, _ = change_lifecycle(sample.entity, "resolved")
    reopened, event = change_lifecycle(closed, "open")
    for invalid in (
        None,
        replace(event, action="reappear"),
        replace(event, previous_revision=0),
        replace(event, previous_generation=0),
        replace(event, entity_id="foreign"),
    ):
        with pytest.raises(ValueError, match="exact typed lifecycle event"):
            validate_entity_transition(closed, reopened, lifecycle_event=invalid)
    with pytest.raises(ValueError, match="invalid lifecycle event"):
        replace(event, action="open")


def test_new_link_does_not_accept_replayed_immutable_preclosure_human_event(sample):
    closed, _ = change_lifecycle(sample.entity, "resolved")
    reopened, _ = change_lifecycle(closed, "open")
    old = sample.entity.decisions.suppression
    with pytest.raises(ValueError, match="unique and not restamp"):
        authorize_dimension(reopened, "suppression", "active", event_id=old.event_id)
    current = replace(
        reopened,
        revision=reopened.revision + 1,
        decisions=replace(
            reopened.decisions,
            revision=reopened.decisions.revision + 1,
            suppression=replace(old, event_id="distinct-but-stale-immutable-event"),
        ),
    )
    stale = HumanAuthorization(
        current.entity_id,
        current.cohort,
        "suppression",
        current.decisions.suppression,
        "controlled-authority",
    )
    with pytest.raises(ValueError, match="new revision"):
        validate_entity_transition(reopened, current, human_authorizations=(stale,))
    current = replace(
        current,
        decisions=replace(
            current.decisions,
            suppression=replace(
                current.decisions.suppression,
                revision=current.decisions.revision,
            ),
        ),
    )
    stale = replace(stale, event=current.decisions.suppression)
    with pytest.raises(ValueError, match="current lifecycle generation"):
        validate_entity_transition(reopened, current, human_authorizations=(stale,))


def test_dimension_cannot_be_deleted_or_changed_without_its_own_authorization(sample):
    reviewed, authorization = authorize_dimension(sample.entity, "verdict")
    for suppression in (None, replace(reviewed.decisions.suppression, value="inactive")):
        with pytest.raises(ValueError, match="unchanged dimension"):
            validate_entity_transition(
                sample.entity,
                replace(reviewed, decisions=replace(reviewed.decisions, suppression=suppression)),
                human_authorizations=(authorization,),
            )
    # An explicit suppression revoke remains a genuine independent action.
    revoked, _ = authorize_dimension(sample.entity, "suppression", "inactive")
    assert effective(sample, entity=revoked).suppression.value == "inactive"


def test_constructor_retains_historical_epochs_but_rejects_future_or_scope_confusion(sample):
    historical = replace(sample.entity, lifecycle_generation=7)
    assert historical.decisions.suppression.authorized_generation == 0
    future = replace(sample.entity.decisions.suppression, authorized_generation=1)
    with pytest.raises(ValueError, match="future/absent"):
        replace(sample.entity, decisions=replace(sample.entity.decisions, suppression=future))
    with pytest.raises(ValueError, match="generation must match decision scope"):
        replace(sample.entity.decisions, suppression=replace(future, authorized_generation=None))
    with pytest.raises(ValueError, match="generation must match decision scope"):
        DecisionSnapshot(
            "occurrence", sample.after.occurrence_id, sample.after.cohort, 2, suppression=future
        )
    with pytest.raises(ValueError, match="dimension/generation"):
        HumanAuthorization(
            sample.entity.entity_id,
            sample.entity.cohort,
            "suppression",
            DimensionDecision("active", "occurrence-event", 3),
            "controlled-authority",
        )


def test_transition_event_ids_dimensions_and_scopes_are_unique(sample):
    reviewed, authorization = authorize_dimension(sample.entity, "verdict")
    with pytest.raises(ValueError, match="duplicate human authorization dimension"):
        validate_entity_transition(
            sample.entity, reviewed, human_authorizations=(authorization, authorization)
        )
    with pytest.raises(ValueError, match="exact target/dimension"):
        validate_entity_transition(
            sample.entity,
            reviewed,
            human_authorizations=(replace(authorization, entity_id="foreign"),),
        )
    closed, lifecycle = change_lifecycle(sample.entity, "resolved")
    event = DimensionDecision(
        "inactive",
        lifecycle.event_id,
        sample.entity.decisions.revision + 1,
        authorized_generation=closed.lifecycle_generation,
    )
    combined = replace(
        closed, decisions=replace(closed.decisions, revision=event.revision, suppression=event)
    )
    human = HumanAuthorization(
        combined.entity_id, combined.cohort, "suppression", event, "controlled-authority"
    )
    with pytest.raises(ValueError, match="unique and not restamp"):
        validate_entity_transition(
            sample.entity, combined, lifecycle_event=lifecycle, human_authorizations=(human,)
        )


def test_current_snapshot_validation_does_not_authenticate_event_store(sample):
    # This is intentionally a controlled authority reference. The pure helper
    # proves structural transition constraints, not a human login or global UUID
    # uniqueness. Production must load immutable events from its authenticated
    # append-only store before invoking this validator and commit under real CAS.
    current, authorization = authorize_dimension(sample.entity, "suppression", "inactive")
    assert authorization.authority_ref == "controlled-human-event-store:not-auth"
    assert (
        validate_entity_transition(sample.entity, current, human_authorizations=(authorization,))
        is None
    )
