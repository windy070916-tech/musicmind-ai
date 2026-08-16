"""Deterministic Knowledge-to-Signal projection tests for Sprint 4A."""

from dataclasses import replace
from itertools import permutations

import pytest

from music_ai.planning import InterpretationPlanner, SignalRelationship
from music_ai.knowledge import (
    FactCategory,
    FactSource,
    FactTimeHorizon,
    ImportanceLevel,
    KnowledgeFact,
    knowledge_evidence_id,
)
from music_ai.signal import (
    ClaimScope,
    EvidenceMaturity,
    SignalCaveat,
    SignalProjector,
    SignalRoleEligibility,
    SignalState,
    SignalType,
    knowledge_evidence_ref,
)


_PREVIOUS_START = "2026-06-07"
_PREVIOUS_END = "2026-07-07"
_CURRENT_START = _PREVIOUS_END
_CURRENT_END = "2026-08-06"
_SUBJECT = "spotify:artist-a"


def _fact(
    category: FactCategory,
    metadata: dict[str, object],
    *,
    horizon: FactTimeHorizon = FactTimeHorizon.LONG_TERM,
    date_range: tuple[str, str] = (_CURRENT_START, _CURRENT_END),
    source: FactSource = FactSource.LONG_TERM_LISTENING_EVIDENCE,
    confidence: float | None = 1.0,
) -> KnowledgeFact:
    return KnowledgeFact(
        category=category,
        importance=ImportanceLevel.HIGH,
        title=f"Canonical {category.value}",
        description=f"Qualified {category.value} evidence.",
        metadata=metadata,
        confidence=confidence,
        source=source,
        date_range=date_range,
        time_horizon=horizon,
    )


def _emergence(*, contains_open_day: bool = False) -> KnowledgeFact:
    return _fact(
        FactCategory.ARTIST_EMERGENCE,
        {
            "subject_key": _SUBJECT,
            "concept_key": "artist_emergence",
            "artist_name": "Artist A",
            "recent_duration_share": 0.40,
            "comparison_duration_share": 0.10,
            "duration_share_change": 0.30,
            "recent_closed_listening_day_count": 4,
            "comparison_closed_listening_day_count": 4,
            "recent_closed_artist_day_count": 3,
            "contains_open_day": contains_open_day,
        },
        horizon=FactTimeHorizon.RECENT,
        date_range=("2026-07-23", _CURRENT_END),
        source=FactSource.RECENT_LISTENING_EVIDENCE,
    )


def _continuity() -> KnowledgeFact:
    return _fact(
        FactCategory.ARTIST_CONTINUITY,
        {
            "subject_key": _SUBJECT,
            "concept_key": "artist_continuity",
            "artist_name": "Artist A",
            "qualifying_day_count": 4,
            "listening_day_count": 6,
            "qualifying_day_share": 4 / 6,
            "contains_open_day": False,
        },
        horizon=FactTimeHorizon.RECENT,
        date_range=("2026-07-30", _CURRENT_END),
        source=FactSource.RECENT_LISTENING_EVIDENCE,
    )


def _consistency() -> KnowledgeFact:
    return _fact(
        FactCategory.ARTIST_CONSISTENCY,
        {
            "subject_key": _SUBJECT,
            "concept_key": "artist_consistency",
            "artist_name": "Artist A",
            "appearance_day_count": 12,
            "listening_day_count": 18,
            "appearance_share": 12 / 18,
            "closed_supporting_day_count": 10,
            "duration_share": 0.42,
            "contains_open_day": False,
        },
    )


def _artist_share_evolution(direction: str = "increase") -> KnowledgeFact:
    previous = 0.20 if direction == "increase" else 0.45
    current = 0.45 if direction == "increase" else 0.20
    return _fact(
        FactCategory.ARTIST_DURATION_SHARE_EVOLUTION,
        {
            **_evolution_window_metadata(),
            "subject_key": _SUBJECT,
            "concept_key": "artist_duration_share",
            "direction": direction,
            "artist_name": "Artist A",
            "previous_value": previous,
            "current_value": current,
            "signed_share_change": current - previous,
        },
        source=FactSource.LONG_TERM_EVOLUTION_EVIDENCE,
        date_range=(_PREVIOUS_START, _CURRENT_END),
    )


def _breadth_evolution(
    direction: str = "increase", *, current_start: str = _CURRENT_START
) -> KnowledgeFact:
    previous = 2.0 if direction == "increase" else 2.8
    current = 2.8 if direction == "increase" else 2.0
    metadata = _evolution_window_metadata(current_start=current_start)
    return _fact(
        FactCategory.ARTIST_BREADTH_EVOLUTION,
        {
            **metadata,
            "subject_key": "listening:all_artists",
            "concept_key": "artist_breadth",
            "direction": direction,
            "previous_value": previous,
            "current_value": current,
            "previous_artist_day_count": 20,
            "current_artist_day_count": 28,
            "previous_listening_day_count": 10,
            "current_listening_day_count": 10,
            "signed_change": current - previous,
            "relative_change": (current - previous) / previous,
        },
        source=FactSource.LONG_TERM_EVOLUTION_EVIDENCE,
        date_range=(_PREVIOUS_START, _CURRENT_END),
    )


def _concentration_evolution(
    direction: str = "increase", *, current_start: str = _CURRENT_START
) -> KnowledgeFact:
    previous = 0.50 if direction == "increase" else 0.75
    current = 0.75 if direction == "increase" else 0.50
    return _fact(
        FactCategory.LISTENING_CONCENTRATION_EVOLUTION,
        {
            **_evolution_window_metadata(current_start=current_start),
            "subject_key": "listening:all_artists",
            "concept_key": "listening_concentration",
            "direction": direction,
            "previous_value": previous,
            "current_value": current,
            "previous_top_five_duration_ms": 500,
            "current_top_five_duration_ms": 750,
            "previous_attributed_duration_ms": 1_000,
            "current_attributed_duration_ms": 1_000,
            "signed_share_change": current - previous,
        },
        source=FactSource.LONG_TERM_EVOLUTION_EVIDENCE,
        date_range=(_PREVIOUS_START, _CURRENT_END),
    )


def _breadth_state() -> KnowledgeFact:
    return _fact(
        FactCategory.ARTIST_BREADTH,
        {
            "subject_key": "listening:all_artists",
            "concept_key": "artist_breadth",
            "unique_artist_count": 28,
            "single_day_artist_count": 12,
            "repeated_artist_count": 16,
            "artists_per_listening_day": 2.8,
            "closed_listening_day_count": 10,
            "contains_open_day": False,
        },
    )


def _time_pattern(*, segment_days: int = 5) -> KnowledgeFact:
    return _fact(
        FactCategory.LISTENING_TIME_OF_DAY_PATTERN,
        {
            **_current_context_metadata(),
            "subject_key": "listening:all_events",
            "concept_key": "listening_time_of_day_pattern",
            "segment": "18:00-24:00",
            "event_count": 30,
            "listening_day_count": 12,
            "segment_event_count": 15,
            "segment_listening_day_count": segment_days,
            "segment_event_share": 0.5,
        },
        source=FactSource.CONTEXTUAL_LISTENING_EVIDENCE,
        confidence=None,
    )


def _affinity(*, segment_days: int = 5) -> KnowledgeFact:
    return _fact(
        FactCategory.ARTIST_TIME_OF_DAY_AFFINITY,
        {
            **_current_context_metadata(),
            "subject_key": _SUBJECT,
            "concept_key": "artist_time_of_day_affinity",
            "segment": "18:00-24:00",
            "artist_identity": ("spotify", "artist-a"),
            "artist_name": "Artist A",
            "artist_event_count": 12,
            "artist_listening_day_count": 8,
            "artist_segment_event_count": 8,
            "artist_segment_listening_day_count": segment_days,
            "artist_segment_share": 8 / 12,
            "overall_event_count": 30,
            "overall_listening_day_count": 12,
            "overall_segment_event_count": 12,
            "overall_segment_listening_day_count": 7,
            "overall_segment_share": 0.4,
            "share_point_lift": 8 / 12 - 0.4,
            "relative_lift": (8 / 12) / 0.4,
        },
        source=FactSource.CONTEXTUAL_LISTENING_EVIDENCE,
        confidence=None,
    )


def _time_evolution(
    *, direction: str = "increase", higher_share_days: int = 5
) -> KnowledgeFact:
    previous_share = 0.20 if direction == "increase" else 0.50
    current_share = 0.50 if direction == "increase" else 0.20
    previous_segment_days = 3 if direction == "increase" else higher_share_days
    current_segment_days = higher_share_days if direction == "increase" else 3
    return _fact(
        FactCategory.LISTENING_TIME_OF_DAY_EVOLUTION,
        {
            **_evolution_window_metadata(),
            "history_scope": "observed_local_history",
            "raw_history_completeness": "unknown",
            "subject_key": "listening:all_events",
            "concept_key": "listening_time_of_day_evolution",
            "direction": direction,
            "segment": "18:00-24:00",
            "previous_event_count": 30,
            "current_event_count": 30,
            "previous_listening_day_count": 12,
            "current_listening_day_count": 12,
            "previous_segment_event_count": 6,
            "current_segment_event_count": 15,
            "previous_segment_listening_day_count": previous_segment_days,
            "current_segment_listening_day_count": current_segment_days,
            "previous_segment_event_share": previous_share,
            "current_segment_event_share": current_share,
            "signed_share_change": current_share - previous_share,
            "absolute_share_change": abs(current_share - previous_share),
        },
        source=FactSource.CONTEXTUAL_LISTENING_EVIDENCE,
        date_range=(_PREVIOUS_START, _CURRENT_END),
        confidence=None,
    )


def _evolution_window_metadata(
    *, current_start: str = _CURRENT_START
) -> dict[str, object]:
    return {
        "previous_start_date": _PREVIOUS_START,
        "previous_end_date": _PREVIOUS_END,
        "current_start_date": current_start,
        "current_end_date": _CURRENT_END,
    }


def _current_context_metadata() -> dict[str, object]:
    return {
        "window_start_date": _CURRENT_START,
        "window_end_date": _CURRENT_END,
        "history_scope": "observed_local_history",
        "raw_history_completeness": "unknown",
    }


def _signal(
    signals: tuple, signal_type: SignalType
):
    return next(signal for signal in signals if signal.signal_type is signal_type)


@pytest.mark.parametrize(
    ("facts", "state", "maturity"),
    (
        ((_emergence(),), SignalState.LOCALLY_EMERGING, EvidenceMaturity.PRELIMINARY),
        ((_continuity(),), SignalState.REPEATED_PRESENCE, EvidenceMaturity.SUPPORTED),
        (
            (_artist_share_evolution(),),
            SignalState.SUSTAINED_GROWTH,
            EvidenceMaturity.SUPPORTED,
        ),
        (
            (_consistency(),),
            SignalState.ESTABLISHED_CORE_PRESENCE,
            EvidenceMaturity.SUPPORTED,
        ),
        (
            (_consistency(), _artist_share_evolution()),
            SignalState.ESTABLISHED_CORE_PRESENCE,
            EvidenceMaturity.STRONG,
        ),
    ),
)
def test_preference_lifecycle_is_bounded_and_deterministically_matured(
    facts: tuple[KnowledgeFact, ...],
    state: SignalState,
    maturity: EvidenceMaturity,
) -> None:
    signal = _signal(
        SignalProjector().project(facts),
        SignalType.ARTIST_PREFERENCE_FORMATION,
    )

    assert signal.state is state
    assert signal.maturity is maturity
    assert SignalCaveat.NOT_FIRST_EVER_DISCOVERY in signal.caveats
    assert SignalCaveat.NOT_PERMANENT_PREFERENCE in signal.caveats
    assert signal.role_eligibility is (
        SignalRoleEligibility.WATCH_ONLY
        if maturity is EvidenceMaturity.PRELIMINARY
        else SignalRoleEligibility.PRIMARY_OR_SECONDARY
    )


def test_signal_contract_rejects_arbitrary_claim_scope_or_caveat_strings() -> None:
    signal = _signal(
        SignalProjector().project((_artist_share_evolution(),)),
        SignalType.ARTIST_PREFERENCE_FORMATION,
    )

    with pytest.raises(TypeError, match="ClaimScope"):
        replace(signal, claim_scopes=("recommend_music",))
    with pytest.raises(TypeError, match="SignalCaveat"):
        replace(signal, caveats=("ignore_history_limits",))


def test_current_open_day_and_unmarked_daily_facts_cannot_advance_lifecycle() -> None:
    open_emergence = _emergence(contains_open_day=True)
    current_stable = _fact(
        FactCategory.STABLE_FAVORITE,
        {
            "artist_name": "Artist A",
            "previous_value": "Artist A",
            "current_value": "Artist A",
        },
        horizon=FactTimeHorizon.DAILY,
        date_range=("2026-08-05", "2026-08-07"),
        source=FactSource.LISTENING_SUMMARY_COMPARISON,
    )

    assert SignalProjector().project((open_emergence, current_stable)) == ()


def test_explicitly_closed_historical_daily_evidence_is_watch_only() -> None:
    closed_stable = _fact(
        FactCategory.STABLE_FAVORITE,
        {
            "subject_key": _SUBJECT,
            "artist_name": "Artist A",
            "previous_value": "Artist A",
            "current_value": "Artist A",
            "is_closed_day": True,
            "contains_open_day": False,
        },
        horizon=FactTimeHorizon.DAILY,
        date_range=("2026-08-03", "2026-08-05"),
        source=FactSource.LISTENING_SUMMARY_COMPARISON,
    )

    signal = _signal(
        SignalProjector().project((closed_stable,)),
        SignalType.ARTIST_PREFERENCE_FORMATION,
    )

    assert signal.state is SignalState.REPEATED_PRESENCE
    assert signal.maturity is EvidenceMaturity.PRELIMINARY
    assert signal.role_eligibility is SignalRoleEligibility.WATCH_ONLY


def test_open_recent_evidence_does_not_increase_closed_growth_maturity() -> None:
    signal = _signal(
        SignalProjector().project(
            (_emergence(contains_open_day=True), _artist_share_evolution())
        ),
        SignalType.ARTIST_PREFERENCE_FORMATION,
    )

    assert signal.state is SignalState.SUSTAINED_GROWTH
    assert signal.maturity is EvidenceMaturity.SUPPORTED
    assert len(signal.evidence_refs) == 1


def test_open_snapshot_evolution_cannot_qualify_lifecycle_or_movement() -> None:
    closed = _artist_share_evolution()
    open_evolution = _fact(
        FactCategory.ARTIST_DURATION_SHARE_EVOLUTION,
        {
            **dict(closed.metadata),
            "contains_open_snapshot": True,
        },
        source=FactSource.LONG_TERM_EVOLUTION_EVIDENCE,
        date_range=(_PREVIOUS_START, _CURRENT_END),
    )

    signals = SignalProjector().project((open_evolution,))

    assert all(
        signal.signal_type
        not in {
            SignalType.ARTIST_PREFERENCE_FORMATION,
            SignalType.TEMPORARY_SPIKE_VS_SUSTAINED_GROWTH,
        }
        for signal in signals
    )


def test_short_movement_sustained_growth_and_conflicting_horizons_are_explicit() -> None:
    projector = SignalProjector()

    short = _signal(
        projector.project((_emergence(),)),
        SignalType.TEMPORARY_SPIKE_VS_SUSTAINED_GROWTH,
    )
    sustained = _signal(
        projector.project((_emergence(), _artist_share_evolution())),
        SignalType.TEMPORARY_SPIKE_VS_SUSTAINED_GROWTH,
    )
    conflicting = _signal(
        projector.project(
            (_emergence(), _artist_share_evolution("decrease"))
        ),
        SignalType.TEMPORARY_SPIKE_VS_SUSTAINED_GROWTH,
    )

    assert (short.state, short.maturity) == (
        SignalState.SHORT_WINDOW_MOVEMENT,
        EvidenceMaturity.PRELIMINARY,
    )
    assert (sustained.state, sustained.maturity) == (
        SignalState.SUSTAINED_GROWTH,
        EvidenceMaturity.STRONG,
    )
    assert (conflicting.state, conflicting.maturity) == (
        SignalState.CONFLICTING_HORIZONS,
        EvidenceMaturity.SUPPORTED,
    )


def test_one_share_evolution_fact_cannot_become_a_tautological_relationship_or_two_items() -> None:
    signals = SignalProjector().project((_artist_share_evolution(),))
    preference = _signal(signals, SignalType.ARTIST_PREFERENCE_FORMATION)
    movement = _signal(
        signals,
        SignalType.TEMPORARY_SPIKE_VS_SUSTAINED_GROWTH,
    )
    planner = InterpretationPlanner()

    assert (
        planner.relationship_for(preference, movement)
        is SignalRelationship.UNRELATED
    )
    plan = planner.plan(signals)
    assert len(plan.items) == 1
    assert plan.items[0].relationship is SignalRelationship.UNRELATED


def test_single_daily_top_artist_change_is_not_sustained_behavior() -> None:
    fact = _fact(
        FactCategory.TOP_ARTIST_CHANGE,
        {"previous_value": "Artist B", "current_value": "Artist A"},
        horizon=FactTimeHorizon.DAILY,
        source=FactSource.LISTENING_SUMMARY_COMPARISON,
    )

    assert SignalProjector().project((fact,)) == ()


def test_exploration_is_explicitly_window_relative() -> None:
    signal = _signal(
        SignalProjector().project((_breadth_evolution(),)),
        SignalType.EXPLORATION_INTENSITY,
    )

    assert signal.state is SignalState.BROADER_ARTIST_MIX
    assert signal.maturity is EvidenceMaturity.SUPPORTED
    assert signal.claim_scopes == (ClaimScope.WINDOW_RELATIVE_EXPLORATION,)
    assert SignalCaveat.NOT_FIRST_EVER_DISCOVERY in signal.caveats
    assert "new" not in signal.state.value


def test_compatible_state_evidence_strengthens_exploration() -> None:
    signal = _signal(
        SignalProjector().project((_breadth_evolution(), _breadth_state())),
        SignalType.EXPLORATION_INTENSITY,
    )

    assert signal.maturity is EvidenceMaturity.STRONG
    assert len(signal.evidence_refs) == 2


def test_core_exploration_is_one_composite_signal_not_a_planner_relationship() -> None:
    signals = SignalProjector().project(
        (_breadth_evolution(), _concentration_evolution())
    )
    composite = _signal(signals, SignalType.CORE_VS_EXPLORATION_BALANCE)

    assert composite.state is SignalState.WIDER_MIX_WITH_CONCENTRATED_CORE
    assert composite.maturity is EvidenceMaturity.STRONG
    assert tuple(ref.category for ref in composite.evidence_refs) == (
        FactCategory.ARTIST_BREADTH_EVOLUTION.value,
        FactCategory.LISTENING_CONCENTRATION_EVOLUTION.value,
    ) or tuple(ref.category for ref in composite.evidence_refs) == (
        FactCategory.LISTENING_CONCENTRATION_EVOLUTION.value,
        FactCategory.ARTIST_BREADTH_EVOLUTION.value,
    )
    assert not hasattr(composite, "relationship")


@pytest.mark.parametrize(
    ("breadth", "concentration"),
    (
        (_breadth_evolution(), _concentration_evolution("decrease")),
        (
            _breadth_evolution(),
            _concentration_evolution(current_start="2026-07-08"),
        ),
    ),
)
def test_unregistered_or_incompatible_core_composite_is_rejected(
    breadth: KnowledgeFact, concentration: KnowledgeFact
) -> None:
    signals = SignalProjector().project((breadth, concentration))

    assert not any(
        signal.signal_type is SignalType.CORE_VS_EXPLORATION_BALANCE
        for signal in signals
    )


@pytest.mark.parametrize(
    ("days", "maturity"),
    (
        (3, EvidenceMaturity.PRELIMINARY),
        (5, EvidenceMaturity.SUPPORTED),
        (8, EvidenceMaturity.STRONG),
    ),
)
def test_time_pattern_maturity_uses_repeated_segment_days(
    days: int, maturity: EvidenceMaturity
) -> None:
    signal = _signal(
        SignalProjector().project((_time_pattern(segment_days=days),)),
        SignalType.LISTENING_TIME_OF_DAY_PATTERN,
    )

    assert signal.state is SignalState.OBSERVED_EVENTS_CONCENTRATED_IN_SEGMENT
    assert signal.maturity is maturity
    assert SignalCaveat.EVENT_COUNT_NOT_LISTENING_TIME in signal.caveats


@pytest.mark.parametrize(
    ("days", "maturity"),
    (
        (3, EvidenceMaturity.PRELIMINARY),
        (5, EvidenceMaturity.SUPPORTED),
        (8, EvidenceMaturity.STRONG),
    ),
)
def test_artist_time_affinity_maturity_uses_artist_segment_recurrence(
    days: int, maturity: EvidenceMaturity
) -> None:
    signal = _signal(
        SignalProjector().project((_affinity(segment_days=days),)),
        SignalType.ARTIST_TIME_OF_DAY_AFFINITY,
    )

    assert signal.state is SignalState.ARTIST_OVERREPRESENTED_IN_SEGMENT
    assert signal.maturity is maturity
    assert dict(
        (value.name, value.value) for value in signal.reference_values
    )["overall_segment_share"] == 0.4


@pytest.mark.parametrize(
    ("direction", "state"),
    (
        ("increase", SignalState.SEGMENT_SHARE_INCREASED),
        ("decrease", SignalState.SEGMENT_SHARE_DECREASED),
    ),
)
def test_time_pattern_evolution_projects_same_adjacent_windows(
    direction: str, state: SignalState
) -> None:
    signal = _signal(
        SignalProjector().project(
            (_time_evolution(direction=direction, higher_share_days=5),)
        ),
        SignalType.TIME_PATTERN_EVOLUTION,
    )

    assert signal.state is state
    assert signal.maturity is EvidenceMaturity.SUPPORTED
    assert tuple(window.label.value for window in signal.windows) == (
        "previous",
        "current",
    )


def test_all_seven_signal_families_project_from_canonical_evidence() -> None:
    signals = SignalProjector().project(
        (
            _emergence(),
            _artist_share_evolution(),
            _breadth_evolution(),
            _concentration_evolution(),
            _time_pattern(),
            _affinity(),
            _time_evolution(),
        )
    )

    assert {signal.signal_type for signal in signals} == set(SignalType)


def test_maturity_and_identity_are_independent_of_knowledge_confidence_and_prose() -> None:
    fact = _time_pattern(segment_days=5)
    changed = replace(
        fact,
        confidence=0.01,
        title="Different canonical display title",
        description="Different visible wording.",
    )

    original_signal = _signal(
        SignalProjector().project((fact,)),
        SignalType.LISTENING_TIME_OF_DAY_PATTERN,
    )
    changed_signal = _signal(
        SignalProjector().project((changed,)),
        SignalType.LISTENING_TIME_OF_DAY_PATTERN,
    )

    assert knowledge_evidence_id(fact) == knowledge_evidence_id(changed)
    assert knowledge_evidence_ref(fact) == knowledge_evidence_ref(changed)
    assert original_signal == changed_signal
    assert original_signal.maturity is EvidenceMaturity.SUPPORTED


def test_projection_order_and_ids_are_permutation_independent() -> None:
    facts = (_emergence(), _artist_share_evolution(), _time_pattern())
    projected = {
        SignalProjector().project(order)
        for order in permutations(facts)
    }

    assert len(projected) == 1
    signals = next(iter(projected))
    assert tuple(signal.signal_id for signal in signals) == tuple(
        signal.signal_id
        for signal in sorted(
            signals,
            key=lambda signal: (
                signal.signal_type.value,
                signal.subject_key or "",
                signal.state.value,
                signal.signal_id,
            ),
        )
    )


def test_contextual_projection_requires_provider_safe_canonical_metadata() -> None:
    malformed = replace(
        _time_pattern(),
        metadata={
            **dict(_time_pattern().metadata),
            "segment_event_share": (1, 2),
        },
    )

    with pytest.raises(TypeError, match="provider-safe scalar"):
        SignalProjector().project((malformed,))
