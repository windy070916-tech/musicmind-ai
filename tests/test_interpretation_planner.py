"""Deterministic tests for Sprint 4A interpretation planning."""

from datetime import date
from itertools import permutations

import pytest

from music_ai.planning import (
    InterpretationPlan,
    InterpretationPlanner,
    InterpretationRole,
    PlanItem,
    SignalRelationship,
)
from music_ai.signal.models import (
    ClaimScope,
    EvidenceMaturity,
    KnowledgeEvidenceRef,
    ObservationWindow,
    ReferenceValue,
    Signal,
    SignalCaveat,
    SignalHorizon,
    SignalState,
    SignalType,
    SupportDimension,
    WindowLabel,
    role_eligibility_for_maturity,
)
from music_ai.visible_content.models import (
    VisibleContentManifest,
    VisibleContentReference,
    VisibleSection,
)


_WINDOW = ObservationWindow(
    WindowLabel.CURRENT,
    date(2026, 7, 15),
    date(2026, 8, 14),
)


def _signal(
    signal_id: str,
    signal_type: SignalType,
    state: SignalState,
    maturity: EvidenceMaturity = EvidenceMaturity.SUPPORTED,
    *,
    subject: str | None = None,
    segment: str | None = None,
    evidence_id: str | None = None,
    supporting_days: int = 6,
) -> Signal:
    references = (
        (ReferenceValue("segment", segment),) if segment is not None else ()
    )
    return Signal(
        signal_id=signal_id,
        signal_type=signal_type,
        state=state,
        subject_key=subject,
        subject_label="Artist" if subject else None,
        horizon=SignalHorizon.ADJACENT_30_DAY_WINDOWS,
        windows=(_WINDOW,),
        maturity=maturity,
        supporting_dimensions=(
            SupportDimension("segment_listening_day_count", supporting_days),
        ),
        reference_values=references,
        claim_scopes=(ClaimScope.BOUNDED_MOVEMENT_CLASSIFICATION,),
        caveats=(SignalCaveat.OBSERVED_LOCAL_HISTORY_ONLY,),
        evidence_refs=(
            KnowledgeEvidenceRef(
                evidence_id or f"kf_{signal_id}",
                "test_category",
                ("2026-07-15", "2026-08-14"),
            ),
        ),
        role_eligibility=role_eligibility_for_maturity(maturity),
    )


def _roles(plan: InterpretationPlan) -> tuple[InterpretationRole, ...]:
    return tuple(item.role for item in plan.items)


def test_evidence_gate_assigns_preliminary_to_watch_only() -> None:
    planner = InterpretationPlanner()
    preliminary = _signal(
        "watch",
        SignalType.EXPLORATION_INTENSITY,
        SignalState.BROAD_ARTIST_MIX,
        EvidenceMaturity.PRELIMINARY,
    )

    plan = planner.plan((preliminary,))

    assert _roles(plan) == (InterpretationRole.WATCH,)
    assert plan.selected_signal_ids == ("watch",)


def test_supported_and_strong_fill_primary_then_secondary_with_one_per_role() -> None:
    planner = InterpretationPlanner()
    contextual = _signal(
        "contextual",
        SignalType.LISTENING_TIME_OF_DAY_PATTERN,
        SignalState.OBSERVED_EVENTS_CONCENTRATED_IN_SEGMENT,
        EvidenceMaturity.SUPPORTED,
        segment="evening",
    )
    lifecycle = _signal(
        "lifecycle",
        SignalType.ARTIST_PREFERENCE_FORMATION,
        SignalState.REPEATED_PRESENCE,
        EvidenceMaturity.STRONG,
        subject="artist:one",
    )

    plan = planner.plan((lifecycle, contextual))

    assert _roles(plan) == (
        InterpretationRole.PRIMARY,
        InterpretationRole.SECONDARY,
    )
    assert plan.items[0].signal_ids == ("contextual",)
    assert len({item.role for item in plan.items}) == len(plan.items)


def test_plan_contract_rejects_secondary_without_primary_and_duplicate_roles() -> None:
    secondary = PlanItem(
        "plan-secondary",
        InterpretationRole.SECONDARY,
        ("signal-one",),
        SignalRelationship.UNRELATED,
        "signal:test",
    )
    watch = PlanItem(
        "plan-watch",
        InterpretationRole.WATCH,
        ("signal-two",),
        SignalRelationship.UNRELATED,
        "signal:test-two",
    )
    primary_again = PlanItem(
        "plan-primary-two",
        InterpretationRole.PRIMARY,
        ("signal-three",),
        SignalRelationship.UNRELATED,
        "signal:test-three",
    )

    with pytest.raises(ValueError, match="without Primary"):
        InterpretationPlan((secondary,))
    with pytest.raises(ValueError, match="ordered"):
        InterpretationPlan((watch, primary_again))


def test_plan_contract_rejects_more_than_one_signal_for_unrelated_item() -> None:
    with pytest.raises(ValueError, match="exactly one"):
        PlanItem(
            "plan",
            InterpretationRole.PRIMARY,
            ("one", "two"),
            SignalRelationship.UNRELATED,
            "signal:test",
        )


def test_registered_reinforcement_contrast_and_contextual_support() -> None:
    planner = InterpretationPlanner()
    preference = _signal(
        "preference",
        SignalType.ARTIST_PREFERENCE_FORMATION,
        SignalState.REPEATED_PRESENCE,
        subject="artist:one",
    )
    sustained = _signal(
        "sustained",
        SignalType.TEMPORARY_SPIKE_VS_SUSTAINED_GROWTH,
        SignalState.SUSTAINED_GROWTH,
        subject="artist:one",
    )
    conflicting = _signal(
        "conflicting",
        SignalType.TEMPORARY_SPIKE_VS_SUSTAINED_GROWTH,
        SignalState.CONFLICTING_HORIZONS,
        subject="artist:one",
    )
    affinity = _signal(
        "affinity",
        SignalType.ARTIST_TIME_OF_DAY_AFFINITY,
        SignalState.ARTIST_OVERREPRESENTED_IN_SEGMENT,
        subject="artist:one",
        segment="evening",
    )

    assert (
        planner.relationship_for(preference, sustained)
        is SignalRelationship.REINFORCEMENT
    )
    assert (
        planner.relationship_for(preference, conflicting)
        is SignalRelationship.CONTRAST
    )
    assert (
        planner.relationship_for(preference, affinity)
        is SignalRelationship.CONTEXTUAL_SUPPORT
    )


def test_unrelated_or_unsupported_signals_are_never_force_combined() -> None:
    planner = InterpretationPlanner()
    preference = _signal(
        "preference",
        SignalType.ARTIST_PREFERENCE_FORMATION,
        SignalState.REPEATED_PRESENCE,
        subject="artist:one",
    )
    different_artist_affinity = _signal(
        "affinity",
        SignalType.ARTIST_TIME_OF_DAY_AFFINITY,
        SignalState.ARTIST_OVERREPRESENTED_IN_SEGMENT,
        subject="artist:two",
        segment="evening",
    )
    exploration = _signal(
        "exploration",
        SignalType.EXPLORATION_INTENSITY,
        SignalState.BROADER_ARTIST_MIX,
    )

    assert (
        planner.relationship_for(preference, different_artist_affinity)
        is SignalRelationship.UNRELATED
    )
    assert (
        planner.relationship_for(exploration, different_artist_affinity)
        is SignalRelationship.UNRELATED
    )
    plan = planner.plan((preference, different_artist_affinity, exploration))
    assert all(item.relationship is SignalRelationship.UNRELATED for item in plan.items)


def test_relationship_value_precedes_stronger_single_contextual_signal() -> None:
    planner = InterpretationPlanner()
    preference = _signal(
        "preference",
        SignalType.ARTIST_PREFERENCE_FORMATION,
        SignalState.REPEATED_PRESENCE,
        subject="artist:one",
    )
    affinity = _signal(
        "affinity",
        SignalType.ARTIST_TIME_OF_DAY_AFFINITY,
        SignalState.ARTIST_OVERREPRESENTED_IN_SEGMENT,
        subject="artist:one",
        segment="evening",
    )
    strong_pattern = _signal(
        "pattern",
        SignalType.LISTENING_TIME_OF_DAY_PATTERN,
        SignalState.OBSERVED_EVENTS_CONCENTRATED_IN_SEGMENT,
        EvidenceMaturity.STRONG,
        segment="morning",
    )

    plan = planner.plan((strong_pattern, affinity, preference))

    assert plan.items[0].relationship is SignalRelationship.CONTEXTUAL_SUPPORT
    assert set(plan.items[0].signal_ids) == {"preference", "affinity"}
    assert plan.items[1].signal_ids == ("pattern",)


def test_maturity_then_named_support_break_same_tier_ties() -> None:
    planner = InterpretationPlanner()
    supported = _signal(
        "supported",
        SignalType.LISTENING_TIME_OF_DAY_PATTERN,
        SignalState.OBSERVED_EVENTS_CONCENTRATED_IN_SEGMENT,
        EvidenceMaturity.SUPPORTED,
        segment="morning",
        supporting_days=12,
    )
    strong_lower_support = _signal(
        "strong",
        SignalType.LISTENING_TIME_OF_DAY_PATTERN,
        SignalState.OBSERVED_EVENTS_CONCENTRATED_IN_SEGMENT,
        EvidenceMaturity.STRONG,
        segment="evening",
        supporting_days=8,
    )
    strong_higher_support = _signal(
        "strong-more",
        SignalType.LISTENING_TIME_OF_DAY_PATTERN,
        SignalState.OBSERVED_EVENTS_CONCENTRATED_IN_SEGMENT,
        EvidenceMaturity.STRONG,
        segment="afternoon",
        supporting_days=10,
    )

    plan = planner.plan((supported, strong_lower_support, strong_higher_support))

    assert plan.items[0].signal_ids == ("strong-more",)
    assert plan.items[1].signal_ids == ("strong",)


def test_visible_pure_observation_is_suppressed_before_planning() -> None:
    planner = InterpretationPlanner()
    exploration = _signal(
        "exploration",
        SignalType.EXPLORATION_INTENSITY,
        SignalState.BROADER_ARTIST_MIX,
        evidence_id="kf_visible",
    )
    manifest = VisibleContentManifest(
        (
            VisibleContentReference(
                "visible:breadth",
                VisibleSection.LONG_TERM,
                "artist_breadth",
                evidence_id="kf_visible",
            ),
        )
    )

    assert planner.plan((exploration,), manifest).items == ()


def test_semantically_visible_signal_is_suppressed_without_inventing_category() -> None:
    planner = InterpretationPlanner()
    preference = _signal(
        "preference",
        SignalType.ARTIST_PREFERENCE_FORMATION,
        SignalState.REPEATED_PRESENCE,
        subject="artist:one",
    )
    manifest = VisibleContentManifest(
        (
            VisibleContentReference(
                "visible:preference",
                VisibleSection.RECENT,
                str(preference.signal_type),
                subject_key=preference.subject_key,
                direction=str(preference.state),
                category="artist_continuity",
                horizon=str(preference.horizon),
            ),
        )
    )

    assert planner.plan((preference,), manifest).items == ()


def test_visible_evidence_can_support_a_new_relationship_interpretation() -> None:
    planner = InterpretationPlanner()
    preference = _signal(
        "preference",
        SignalType.ARTIST_PREFERENCE_FORMATION,
        SignalState.REPEATED_PRESENCE,
        subject="artist:one",
        evidence_id="kf_preference",
    )
    affinity = _signal(
        "affinity",
        SignalType.ARTIST_TIME_OF_DAY_AFFINITY,
        SignalState.ARTIST_OVERREPRESENTED_IN_SEGMENT,
        subject="artist:one",
        segment="evening",
        evidence_id="kf_affinity",
    )
    manifest = VisibleContentManifest(
        (
            VisibleContentReference(
                "visible:preference",
                VisibleSection.RECENT,
                "artist_presence",
                evidence_id="kf_preference",
            ),
            VisibleContentReference(
                "visible:affinity",
                VisibleSection.HIGHLIGHTS,
                "artist_time_affinity",
                evidence_id="kf_affinity",
            ),
        )
    )

    plan = planner.plan((preference, affinity), manifest)

    assert len(plan.items) == 1
    assert plan.items[0].relationship is SignalRelationship.CONTEXTUAL_SUPPORT


def test_planning_is_permutation_independent_and_has_no_history_input() -> None:
    planner = InterpretationPlanner()
    signals = (
        _signal(
            "preference",
            SignalType.ARTIST_PREFERENCE_FORMATION,
            SignalState.REPEATED_PRESENCE,
            subject="artist:one",
        ),
        _signal(
            "affinity",
            SignalType.ARTIST_TIME_OF_DAY_AFFINITY,
            SignalState.ARTIST_OVERREPRESENTED_IN_SEGMENT,
            subject="artist:one",
            segment="evening",
        ),
        _signal(
            "watch",
            SignalType.EXPLORATION_INTENSITY,
            SignalState.BROAD_ARTIST_MIX,
            EvidenceMaturity.PRELIMINARY,
        ),
    )
    expected = planner.plan(signals)

    assert all(planner.plan(order) == expected for order in permutations(signals))
    assert planner.plan(signals) == expected


def test_duplicate_signal_ids_are_rejected_instead_of_silently_ranked() -> None:
    planner = InterpretationPlanner()
    one = _signal(
        "duplicate",
        SignalType.EXPLORATION_INTENSITY,
        SignalState.BROAD_ARTIST_MIX,
    )
    two = _signal(
        "duplicate",
        SignalType.LISTENING_TIME_OF_DAY_PATTERN,
        SignalState.OBSERVED_EVENTS_CONCENTRATED_IN_SEGMENT,
        segment="evening",
    )

    with pytest.raises(ValueError, match="unique"):
        planner.plan((one, two))
