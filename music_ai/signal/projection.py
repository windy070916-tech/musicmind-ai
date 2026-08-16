"""Project qualified Knowledge evidence into deterministic interpretation Signals."""

from collections import defaultdict
from collections.abc import Iterable, Sequence
from datetime import date
from enum import Enum
from hashlib import sha256
import json
from math import isfinite

from music_ai.knowledge.evidence_reference import knowledge_evidence_id
from music_ai.knowledge.models import KnowledgeFact
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
from music_ai.signal.policies import (
    CORE_EXPLORATION_COMPOSITE_MATURITY,
    CORE_EXPLORATION_DIRECTION_RULES,
    artist_time_affinity_maturity,
    daily_lifecycle_evidence_is_eligible,
    exploration_maturity,
    movement_maturity,
    preference_maturity,
    time_evolution_maturity,
    time_pattern_maturity,
)


_ARTIST_EMERGENCE = "artist_emergence"
_ARTIST_CONTINUITY = "artist_continuity"
_ARTIST_CONSISTENCY = "artist_consistency"
_ARTIST_SHARE_EVOLUTION = "artist_duration_share_evolution"
_STABLE_FAVORITE = "stable_favorite"
_ARTIST_BREADTH = "artist_breadth"
_ARTIST_BREADTH_EVOLUTION = "artist_breadth_evolution"
_CONCENTRATION_EVOLUTION = "listening_concentration_evolution"
_TIME_PATTERN = "listening_time_of_day_pattern"
_ARTIST_TIME_AFFINITY = "artist_time_of_day_affinity"
_TIME_EVOLUTION = "listening_time_of_day_evolution"

_LIFECYCLE_RANK = {
    SignalState.LOCALLY_EMERGING: 1,
    SignalState.REPEATED_PRESENCE: 2,
    SignalState.SUSTAINED_GROWTH: 3,
    SignalState.ESTABLISHED_CORE_PRESENCE: 4,
}

_LIFECYCLE_CAVEATS = (
    SignalCaveat.OBSERVED_LOCAL_HISTORY_ONLY,
    SignalCaveat.NOT_FIRST_EVER_DISCOVERY,
    SignalCaveat.NOT_PERMANENT_PREFERENCE,
    SignalCaveat.NO_CAUSAL_OR_PSYCHOLOGICAL_INFERENCE,
    SignalCaveat.CURRENT_OPEN_DAY_EXCLUDED,
)
_CONTEXT_CAVEATS = (
    SignalCaveat.OBSERVED_LOCAL_HISTORY_ONLY,
    SignalCaveat.EVENT_COUNT_NOT_LISTENING_TIME,
    SignalCaveat.NO_ALWAYS_OR_HABIT_CLAIM,
    SignalCaveat.NO_CAUSAL_OR_PSYCHOLOGICAL_INFERENCE,
    SignalCaveat.CURRENT_OPEN_DAY_EXCLUDED,
)


class SignalProjector:
    """Compose already-qualified Knowledge observations into Signals.

    The projector trusts Knowledge qualification.  It does not repeat analytic
    thresholds for share, lift, or evidence sufficiency; it only applies the
    interpretation-domain lifecycle, compatibility, composition, and maturity
    policies declared by Sprint 4A.
    """

    def project(self, facts: Iterable[KnowledgeFact]) -> tuple[Signal, ...]:
        """Return a stable, permutation-independent collection of Signals."""
        resolved = tuple(facts)
        if any(not isinstance(fact, KnowledgeFact) for fact in resolved):
            raise TypeError("facts must contain only KnowledgeFact values.")
        ordered = tuple(sorted(resolved, key=knowledge_evidence_id))

        signals = [
            *self._preference_signals(ordered),
            *self._movement_signals(ordered),
            *self._exploration_signals(ordered),
            *self._core_exploration_signals(ordered),
            *self._time_pattern_signals(ordered),
            *self._artist_time_affinity_signals(ordered),
            *self._time_evolution_signals(ordered),
        ]
        unique = {signal.signal_id: signal for signal in signals}
        return tuple(
            sorted(
                unique.values(),
                key=lambda signal: (
                    signal.signal_type.value,
                    signal.subject_key or "",
                    signal.state.value,
                    signal.signal_id,
                ),
            )
        )

    def _preference_signals(
        self, facts: tuple[KnowledgeFact, ...]
    ) -> tuple[Signal, ...]:
        grouped = _group_closed_artist_evidence(facts)
        signals: list[Signal] = []
        for subject_key, candidates in sorted(grouped.items()):
            states: list[tuple[SignalState, KnowledgeFact]] = []
            for fact in candidates:
                category = _category(fact)
                if category == _ARTIST_EMERGENCE:
                    states.append((SignalState.LOCALLY_EMERGING, fact))
                elif category in {_ARTIST_CONTINUITY, _STABLE_FAVORITE}:
                    states.append((SignalState.REPEATED_PRESENCE, fact))
                elif (
                    category == _ARTIST_SHARE_EVOLUTION
                    and _direction(fact) == "increase"
                ):
                    states.append((SignalState.SUSTAINED_GROWTH, fact))
                elif category == _ARTIST_CONSISTENCY:
                    states.append((SignalState.ESTABLISHED_CORE_PRESENCE, fact))
            if not states:
                continue
            state = max(states, key=lambda item: _LIFECYCLE_RANK[item[0]])[0]
            supporting = tuple(
                fact
                for candidate_state, fact in states
                if _LIFECYCLE_RANK[candidate_state] <= _LIFECYCLE_RANK[state]
            )
            maturity = preference_maturity(
                state, (_category(fact) for fact in supporting)
            )
            signals.append(
                _build_signal(
                    signal_type=SignalType.ARTIST_PREFERENCE_FORMATION,
                    state=state,
                    subject_key=subject_key,
                    subject_label=_artist_label(supporting),
                    horizon=_combined_horizon(supporting),
                    facts=supporting,
                    maturity=maturity,
                    supporting_dimensions=_artist_support_dimensions(supporting),
                    reference_values=_artist_reference_values(supporting),
                    claim_scopes=(ClaimScope.BOUNDED_ARTIST_LIFECYCLE,),
                    caveats=_LIFECYCLE_CAVEATS,
                )
            )
        return tuple(signals)

    def _movement_signals(
        self, facts: tuple[KnowledgeFact, ...]
    ) -> tuple[Signal, ...]:
        grouped = _group_closed_artist_evidence(facts)
        signals: list[Signal] = []
        for subject_key, candidates in sorted(grouped.items()):
            emergence = tuple(
                fact for fact in candidates if _category(fact) == _ARTIST_EMERGENCE
            )
            increases = tuple(
                fact
                for fact in candidates
                if _category(fact) == _ARTIST_SHARE_EVOLUTION
                and _direction(fact) == "increase"
            )
            decreases = tuple(
                fact
                for fact in candidates
                if _category(fact) == _ARTIST_SHARE_EVOLUTION
                and _direction(fact) == "decrease"
            )
            if emergence and increases:
                state = SignalState.SUSTAINED_GROWTH
                supporting = (*emergence, *increases)
            elif emergence and decreases:
                state = SignalState.CONFLICTING_HORIZONS
                supporting = (*emergence, *decreases)
            elif increases:
                state = SignalState.SUSTAINED_GROWTH
                supporting = increases
            elif emergence:
                # A qualified Recent movement is repeated evidence, but without a
                # compatible longer horizon it remains Watch-only rather than being
                # labelled a sustained preference shift.
                state = SignalState.SHORT_WINDOW_MOVEMENT
                supporting = emergence
            else:
                continue
            maturity = movement_maturity(
                state,
                has_recent_movement=bool(emergence),
                has_long_horizon_movement=bool(increases or decreases),
            )
            signals.append(
                _build_signal(
                    signal_type=(
                        SignalType.TEMPORARY_SPIKE_VS_SUSTAINED_GROWTH
                    ),
                    state=state,
                    subject_key=subject_key,
                    subject_label=_artist_label(supporting),
                    horizon=_combined_horizon(supporting),
                    facts=supporting,
                    maturity=maturity,
                    supporting_dimensions=_artist_support_dimensions(supporting),
                    reference_values=_artist_reference_values(supporting),
                    claim_scopes=(ClaimScope.BOUNDED_MOVEMENT_CLASSIFICATION,),
                    caveats=_LIFECYCLE_CAVEATS,
                )
            )
        return tuple(signals)

    def _exploration_signals(
        self, facts: tuple[KnowledgeFact, ...]
    ) -> tuple[Signal, ...]:
        breadth_state = tuple(
            fact for fact in facts if _category(fact) == _ARTIST_BREADTH
        )
        evolution = tuple(
            fact for fact in facts if _category(fact) == _ARTIST_BREADTH_EVOLUTION
        )
        signals: list[Signal] = []
        for fact in evolution:
            direction = _direction(fact)
            if direction not in {"increase", "decrease"}:
                continue
            compatible_state = tuple(
                state_fact
                for state_fact in breadth_state
                if _state_matches_evolution_current_window(state_fact, fact)
            )
            supporting = (fact, *compatible_state)
            maturity = exploration_maturity(
                has_compatible_state_evidence=bool(compatible_state)
            )
            signals.append(
                _build_signal(
                    signal_type=SignalType.EXPLORATION_INTENSITY,
                    state=(
                        SignalState.BROADER_ARTIST_MIX
                        if direction == "increase"
                        else SignalState.NARROWER_ARTIST_MIX
                    ),
                    subject_key="listening:all_artists",
                    subject_label=None,
                    horizon=SignalHorizon.ADJACENT_30_DAY_WINDOWS,
                    facts=supporting,
                    maturity=maturity,
                    supporting_dimensions=_exploration_dimensions(supporting),
                    reference_values=_exploration_references(supporting),
                    claim_scopes=(ClaimScope.WINDOW_RELATIVE_EXPLORATION,),
                    caveats=(
                        SignalCaveat.OBSERVED_LOCAL_HISTORY_ONLY,
                        SignalCaveat.NOT_FIRST_EVER_DISCOVERY,
                        SignalCaveat.NO_CAUSAL_OR_PSYCHOLOGICAL_INFERENCE,
                        SignalCaveat.CURRENT_OPEN_DAY_EXCLUDED,
                    ),
                )
            )
        if not evolution:
            for fact in breadth_state:
                signals.append(
                    _build_signal(
                        signal_type=SignalType.EXPLORATION_INTENSITY,
                        state=SignalState.BROAD_ARTIST_MIX,
                        subject_key="listening:all_artists",
                        subject_label=None,
                        horizon=SignalHorizon.LONG_TERM,
                        facts=(fact,),
                        maturity=exploration_maturity(
                            has_compatible_state_evidence=False
                        ),
                        supporting_dimensions=_exploration_dimensions((fact,)),
                        reference_values=_exploration_references((fact,)),
                        claim_scopes=(ClaimScope.WINDOW_RELATIVE_EXPLORATION,),
                        caveats=(
                            SignalCaveat.OBSERVED_LOCAL_HISTORY_ONLY,
                            SignalCaveat.NOT_FIRST_EVER_DISCOVERY,
                            SignalCaveat.NO_CAUSAL_OR_PSYCHOLOGICAL_INFERENCE,
                            SignalCaveat.CURRENT_OPEN_DAY_EXCLUDED,
                        ),
                    )
                )
        return tuple(signals)

    def _core_exploration_signals(
        self, facts: tuple[KnowledgeFact, ...]
    ) -> tuple[Signal, ...]:
        breadth = tuple(
            fact for fact in facts if _category(fact) == _ARTIST_BREADTH_EVOLUTION
        )
        concentration = tuple(
            fact for fact in facts if _category(fact) == _CONCENTRATION_EVOLUTION
        )
        signals: list[Signal] = []
        for breadth_fact in breadth:
            for concentration_fact in concentration:
                directions = (
                    _direction(breadth_fact),
                    _direction(concentration_fact),
                )
                state_value = CORE_EXPLORATION_DIRECTION_RULES.get(directions)
                if state_value is None or not _same_evolution_windows(
                    breadth_fact, concentration_fact
                ):
                    continue
                signals.append(
                    _build_signal(
                        signal_type=SignalType.CORE_VS_EXPLORATION_BALANCE,
                        state=SignalState(state_value),
                        subject_key="listening:all_artists",
                        subject_label=None,
                        horizon=SignalHorizon.ADJACENT_30_DAY_WINDOWS,
                        facts=(breadth_fact, concentration_fact),
                        maturity=CORE_EXPLORATION_COMPOSITE_MATURITY,
                        supporting_dimensions=_core_exploration_dimensions(
                            breadth_fact, concentration_fact
                        ),
                        reference_values=_core_exploration_references(
                            breadth_fact, concentration_fact
                        ),
                        claim_scopes=(ClaimScope.CORE_EXPLORATION_COMPOSITION,),
                        caveats=(
                            SignalCaveat.OBSERVED_LOCAL_HISTORY_ONLY,
                            SignalCaveat.NO_CAUSAL_OR_PSYCHOLOGICAL_INFERENCE,
                            SignalCaveat.CURRENT_OPEN_DAY_EXCLUDED,
                        ),
                    )
                )
        return tuple(signals)

    def _time_pattern_signals(
        self, facts: tuple[KnowledgeFact, ...]
    ) -> tuple[Signal, ...]:
        signals: list[Signal] = []
        for fact in facts:
            if _category(fact) != _TIME_PATTERN:
                continue
            segment_days = _required_int(
                fact, "segment_listening_day_count", minimum=1
            )
            maturity = time_pattern_maturity(segment_days)
            signals.append(
                _build_signal(
                    signal_type=SignalType.LISTENING_TIME_OF_DAY_PATTERN,
                    state=SignalState.OBSERVED_EVENTS_CONCENTRATED_IN_SEGMENT,
                    subject_key=_subject_key(fact) or "listening:all_events",
                    subject_label=None,
                    horizon=SignalHorizon.LONG_TERM,
                    facts=(fact,),
                    maturity=maturity,
                    supporting_dimensions=_named_dimensions(
                        fact,
                        (
                            "event_count",
                            "listening_day_count",
                            "segment_event_count",
                            "segment_listening_day_count",
                        ),
                    ),
                    reference_values=_named_references(
                        fact, ("segment", "segment_event_share")
                    ),
                    claim_scopes=(ClaimScope.OBSERVED_EVENT_DISTRIBUTION,),
                    caveats=_CONTEXT_CAVEATS,
                )
            )
        return tuple(signals)

    def _artist_time_affinity_signals(
        self, facts: tuple[KnowledgeFact, ...]
    ) -> tuple[Signal, ...]:
        signals: list[Signal] = []
        for fact in facts:
            if _category(fact) != _ARTIST_TIME_AFFINITY:
                continue
            segment_days = _required_int(
                fact, "artist_segment_listening_day_count", minimum=1
            )
            maturity = artist_time_affinity_maturity(segment_days)
            signals.append(
                _build_signal(
                    signal_type=SignalType.ARTIST_TIME_OF_DAY_AFFINITY,
                    state=SignalState.ARTIST_OVERREPRESENTED_IN_SEGMENT,
                    subject_key=_subject_key(fact) or _artist_identity_key(fact),
                    subject_label=_required_str(fact, "artist_name"),
                    horizon=SignalHorizon.LONG_TERM,
                    facts=(fact,),
                    maturity=maturity,
                    supporting_dimensions=_named_dimensions(
                        fact,
                        (
                            "artist_event_count",
                            "artist_listening_day_count",
                            "artist_segment_event_count",
                            "artist_segment_listening_day_count",
                            "overall_event_count",
                            "overall_listening_day_count",
                            "overall_segment_event_count",
                            "overall_segment_listening_day_count",
                        ),
                    ),
                    reference_values=_named_references(
                        fact,
                        (
                            "segment",
                            "artist_segment_share",
                            "overall_segment_share",
                            "share_point_lift",
                            "relative_lift",
                        ),
                    ),
                    claim_scopes=(
                        ClaimScope.OBSERVED_ARTIST_TIME_ASSOCIATION,
                    ),
                    caveats=_CONTEXT_CAVEATS,
                )
            )
        return tuple(signals)

    def _time_evolution_signals(
        self, facts: tuple[KnowledgeFact, ...]
    ) -> tuple[Signal, ...]:
        signals: list[Signal] = []
        for fact in facts:
            if _category(fact) != _TIME_EVOLUTION:
                continue
            direction = _direction(fact)
            if direction not in {"increase", "decrease"}:
                raise ValueError(
                    "Time-pattern evolution Knowledge fact requires increase/decrease."
                )
            previous_days = _required_int(
                fact, "previous_segment_listening_day_count", minimum=0
            )
            current_days = _required_int(
                fact, "current_segment_listening_day_count", minimum=0
            )
            higher_share_days = (
                current_days if direction == "increase" else previous_days
            )
            maturity = time_evolution_maturity(higher_share_days)
            signals.append(
                _build_signal(
                    signal_type=SignalType.TIME_PATTERN_EVOLUTION,
                    state=(
                        SignalState.SEGMENT_SHARE_INCREASED
                        if direction == "increase"
                        else SignalState.SEGMENT_SHARE_DECREASED
                    ),
                    subject_key=_subject_key(fact) or "listening:all_events",
                    subject_label=None,
                    horizon=SignalHorizon.ADJACENT_30_DAY_WINDOWS,
                    facts=(fact,),
                    maturity=maturity,
                    supporting_dimensions=_named_dimensions(
                        fact,
                        (
                            "previous_event_count",
                            "current_event_count",
                            "previous_listening_day_count",
                            "current_listening_day_count",
                            "previous_segment_event_count",
                            "current_segment_event_count",
                            "previous_segment_listening_day_count",
                            "current_segment_listening_day_count",
                        ),
                    ),
                    reference_values=_named_references(
                        fact,
                        (
                            "segment",
                            "previous_segment_event_share",
                            "current_segment_event_share",
                            "signed_share_change",
                        ),
                    ),
                    claim_scopes=(
                        ClaimScope.OBSERVED_TIME_DISTRIBUTION_CHANGE,
                    ),
                    caveats=_CONTEXT_CAVEATS,
                )
            )
        return tuple(signals)


def knowledge_evidence_ref(fact: KnowledgeFact) -> KnowledgeEvidenceRef:
    """Project a canonical Knowledge fact into a traceable Signal reference."""
    if not isinstance(fact, KnowledgeFact):
        raise TypeError("fact must be KnowledgeFact.")
    return KnowledgeEvidenceRef(
        evidence_id=knowledge_evidence_id(fact),
        category=_category(fact),
        date_range=fact.date_range,
    )


def _build_signal(
    *,
    signal_type: SignalType,
    state: SignalState,
    subject_key: str | None,
    subject_label: str | None,
    horizon: SignalHorizon,
    facts: Sequence[KnowledgeFact],
    maturity: EvidenceMaturity,
    supporting_dimensions: tuple[SupportDimension, ...],
    reference_values: tuple[ReferenceValue, ...],
    claim_scopes: tuple[ClaimScope, ...],
    caveats: tuple[SignalCaveat, ...],
) -> Signal:
    evidence_refs = tuple(
        sorted(
            (knowledge_evidence_ref(fact) for fact in facts),
            key=lambda reference: reference.evidence_id,
        )
    )
    windows = _windows_for_facts(facts)
    signal_id = _signal_id(
        signal_type,
        state,
        subject_key,
        windows,
        evidence_refs,
    )
    return Signal(
        signal_id=signal_id,
        signal_type=signal_type,
        state=state,
        subject_key=subject_key,
        subject_label=subject_label,
        horizon=horizon,
        windows=windows,
        maturity=maturity,
        supporting_dimensions=tuple(
            sorted(supporting_dimensions, key=lambda item: item.name)
        ),
        reference_values=tuple(
            sorted(reference_values, key=lambda item: item.name)
        ),
        claim_scopes=claim_scopes,
        caveats=caveats,
        evidence_refs=evidence_refs,
        role_eligibility=role_eligibility_for_maturity(maturity),
    )


def _signal_id(
    signal_type: SignalType,
    state: SignalState,
    subject_key: str | None,
    windows: tuple[ObservationWindow, ...],
    evidence_refs: tuple[KnowledgeEvidenceRef, ...],
) -> str:
    payload = {
        "signal_type": signal_type.value,
        "state": state.value,
        "subject_key": subject_key,
        "windows": [
            {
                "label": window.label.value,
                "start_date": window.start_date.isoformat(),
                "end_date": window.end_date.isoformat(),
            }
            for window in windows
        ],
        "evidence_ids": [reference.evidence_id for reference in evidence_refs],
    }
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return f"sig_{sha256(encoded).hexdigest()[:20]}"


def _group_closed_artist_evidence(
    facts: Sequence[KnowledgeFact],
) -> dict[str, tuple[KnowledgeFact, ...]]:
    categories = {
        _ARTIST_EMERGENCE,
        _ARTIST_CONTINUITY,
        _ARTIST_CONSISTENCY,
        _ARTIST_SHARE_EVOLUTION,
        _STABLE_FAVORITE,
    }
    grouped: dict[str, list[KnowledgeFact]] = defaultdict(list)
    for fact in facts:
        if _category(fact) not in categories or not _closed_lifecycle_fact(fact):
            continue
        subject_key = _subject_key(fact)
        if subject_key is None:
            artist_name = _optional_str(fact, "artist_name")
            if artist_name is None:
                continue
            subject_key = f"legacy:{artist_name.strip().casefold()}"
        grouped[subject_key].append(fact)
    return {
        key: tuple(sorted(values, key=knowledge_evidence_id))
        for key, values in grouped.items()
    }


def _closed_lifecycle_fact(fact: KnowledgeFact) -> bool:
    metadata = fact.metadata
    if metadata.get("contains_open_day") is True:
        return False
    if metadata.get("contains_open_snapshot") is True:
        return False
    horizon = _enum_text(fact.time_horizon)
    if horizon == "daily":
        return daily_lifecycle_evidence_is_eligible(
            is_closed_day=metadata.get("is_closed_day"),
            contains_open_day=metadata.get("contains_open_day"),
        )
    return True


def _combined_horizon(facts: Sequence[KnowledgeFact]) -> SignalHorizon:
    horizons = {_enum_text(fact.time_horizon) for fact in facts}
    if len(horizons) > 1:
        return SignalHorizon.CROSS_HORIZON
    if horizons == {"recent"}:
        return SignalHorizon.RECENT
    return SignalHorizon.LONG_TERM


def _artist_label(facts: Sequence[KnowledgeFact]) -> str:
    labels = sorted(
        {
            label
            for fact in facts
            if (label := _optional_str(fact, "artist_name")) is not None
        },
        key=lambda value: (value.casefold(), value),
    )
    if not labels:
        raise ValueError("Artist interpretation evidence requires artist_name.")
    return labels[0]


def _artist_support_dimensions(
    facts: Sequence[KnowledgeFact],
) -> tuple[SupportDimension, ...]:
    keys = (
        "qualifying_day_count",
        "listening_day_count",
        "recent_closed_listening_day_count",
        "comparison_closed_listening_day_count",
        "recent_closed_artist_day_count",
        "appearance_day_count",
        "closed_supporting_day_count",
    )
    return _prefixed_dimensions(facts, keys)


def _artist_reference_values(
    facts: Sequence[KnowledgeFact],
) -> tuple[ReferenceValue, ...]:
    keys = (
        "qualifying_day_share",
        "recent_duration_share",
        "comparison_duration_share",
        "duration_share_change",
        "appearance_share",
        "duration_share",
        "previous_value",
        "current_value",
        "signed_share_change",
    )
    return _prefixed_references(facts, keys)


def _exploration_dimensions(
    facts: Sequence[KnowledgeFact],
) -> tuple[SupportDimension, ...]:
    return _prefixed_dimensions(
        facts,
        (
            "previous_artist_day_count",
            "current_artist_day_count",
            "previous_listening_day_count",
            "current_listening_day_count",
            "unique_artist_count",
            "single_day_artist_count",
            "repeated_artist_count",
            "closed_listening_day_count",
        ),
    )


def _exploration_references(
    facts: Sequence[KnowledgeFact],
) -> tuple[ReferenceValue, ...]:
    return _prefixed_references(
        facts,
        (
            "direction",
            "previous_value",
            "current_value",
            "signed_change",
            "relative_change",
            "artists_per_listening_day",
        ),
    )


def _core_exploration_dimensions(
    breadth: KnowledgeFact, concentration: KnowledgeFact
) -> tuple[SupportDimension, ...]:
    return _prefixed_dimensions(
        (breadth, concentration),
        (
            "previous_artist_day_count",
            "current_artist_day_count",
            "previous_listening_day_count",
            "current_listening_day_count",
            "previous_top_five_duration_ms",
            "current_top_five_duration_ms",
            "previous_attributed_duration_ms",
            "current_attributed_duration_ms",
        ),
    )


def _core_exploration_references(
    breadth: KnowledgeFact, concentration: KnowledgeFact
) -> tuple[ReferenceValue, ...]:
    return _prefixed_references(
        (breadth, concentration),
        (
            "direction",
            "previous_value",
            "current_value",
            "signed_change",
            "signed_share_change",
        ),
    )


def _prefixed_dimensions(
    facts: Sequence[KnowledgeFact], keys: Sequence[str]
) -> tuple[SupportDimension, ...]:
    dimensions: list[SupportDimension] = []
    for fact in facts:
        prefix = str(fact.metadata.get("concept_key") or _category(fact))
        for key in keys:
            if key in fact.metadata:
                dimensions.append(
                    SupportDimension(
                        name=f"{prefix}.{key}",
                        value=_scalar(fact.metadata[key], key),
                    )
                )
    return _deduplicate_named(dimensions)


def _prefixed_references(
    facts: Sequence[KnowledgeFact], keys: Sequence[str]
) -> tuple[ReferenceValue, ...]:
    references: list[ReferenceValue] = []
    for fact in facts:
        prefix = str(fact.metadata.get("concept_key") or _category(fact))
        for key in keys:
            if key in fact.metadata:
                references.append(
                    ReferenceValue(
                        name=f"{prefix}.{key}",
                        value=_scalar(fact.metadata[key], key),
                    )
                )
    return _deduplicate_named(references)


def _named_dimensions(
    fact: KnowledgeFact, keys: Sequence[str]
) -> tuple[SupportDimension, ...]:
    return tuple(
        SupportDimension(key, _scalar(_required_metadata(fact, key), key))
        for key in keys
    )


def _named_references(
    fact: KnowledgeFact, keys: Sequence[str]
) -> tuple[ReferenceValue, ...]:
    return tuple(
        ReferenceValue(key, _scalar(_required_metadata(fact, key), key))
        for key in keys
    )


def _deduplicate_named(values: Sequence[object]) -> tuple:
    by_name: dict[str, object] = {}
    for value in values:
        existing = by_name.get(value.name)
        if existing is not None and existing.value != value.value:
            # Multiple canonical observations with the same concept/key need a
            # fact-specific prefix to remain a compact, unambiguous contract.
            raise ValueError(
                f"Conflicting projected values for {value.name!r}."
            )
        by_name[value.name] = value
    return tuple(by_name[name] for name in sorted(by_name))


def _windows_for_facts(
    facts: Sequence[KnowledgeFact],
) -> tuple[ObservationWindow, ...]:
    windows: set[ObservationWindow] = set()
    for fact in facts:
        metadata = fact.metadata
        if all(
            key in metadata
            for key in (
                "previous_start_date",
                "previous_end_date",
                "current_start_date",
                "current_end_date",
            )
        ):
            windows.add(
                _metadata_window(fact, WindowLabel.PREVIOUS, "previous")
            )
            windows.add(_metadata_window(fact, WindowLabel.CURRENT, "current"))
            continue
        if "window_start_date" in metadata and "window_end_date" in metadata:
            windows.add(
                ObservationWindow(
                    WindowLabel.CURRENT,
                    _metadata_date(fact, "window_start_date"),
                    _metadata_date(fact, "window_end_date"),
                )
            )
            continue
        if fact.date_range is None:
            raise ValueError(
                f"{_category(fact)} evidence requires a compact date window."
            )
        label = (
            WindowLabel.RECENT
            if _enum_text(fact.time_horizon) == "recent"
            else WindowLabel.LONG_TERM
        )
        windows.add(
            ObservationWindow(
                label,
                _parse_date(fact.date_range[0], "date_range start"),
                _parse_date(fact.date_range[1], "date_range end"),
            )
        )
    return tuple(
        sorted(
            windows,
            key=lambda window: (
                window.start_date,
                window.end_date,
                window.label.value,
            ),
        )
    )


def _metadata_window(
    fact: KnowledgeFact, label: WindowLabel, prefix: str
) -> ObservationWindow:
    return ObservationWindow(
        label,
        _metadata_date(fact, f"{prefix}_start_date"),
        _metadata_date(fact, f"{prefix}_end_date"),
    )


def _same_evolution_windows(left: KnowledgeFact, right: KnowledgeFact) -> bool:
    keys = (
        "previous_start_date",
        "previous_end_date",
        "current_start_date",
        "current_end_date",
    )
    return all(
        key in left.metadata
        and key in right.metadata
        and left.metadata[key] == right.metadata[key]
        for key in keys
    )


def _state_matches_evolution_current_window(
    state: KnowledgeFact, evolution: KnowledgeFact
) -> bool:
    return (
        state.date_range is not None
        and state.date_range
        == (
            evolution.metadata.get("current_start_date"),
            evolution.metadata.get("current_end_date"),
        )
    )


def _subject_key(fact: KnowledgeFact) -> str | None:
    value = fact.metadata.get("subject_key")
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Knowledge subject_key must be a non-empty string.")
    return value


def _artist_identity_key(fact: KnowledgeFact) -> str:
    identity = _required_metadata(fact, "artist_identity")
    if (
        not isinstance(identity, (tuple, list))
        or len(identity) != 2
        or not all(isinstance(value, str) and value for value in identity)
    ):
        raise ValueError("artist_identity must contain two non-empty strings.")
    return f"{identity[0]}:{identity[1]}"


def _direction(fact: KnowledgeFact) -> str | None:
    value = fact.metadata.get("direction")
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ValueError("Knowledge direction must be a non-empty string.")
    return value


def _category(fact: KnowledgeFact) -> str:
    value = _enum_text(fact.category)
    if not isinstance(value, str) or not value:
        raise ValueError("Knowledge category must be a non-empty string.")
    return value


def _enum_text(value: object) -> object:
    return value.value if isinstance(value, Enum) else value


def _optional_str(fact: KnowledgeFact, key: str) -> str | None:
    value = fact.metadata.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Knowledge {key} must be a non-empty string.")
    return value


def _required_str(fact: KnowledgeFact, key: str) -> str:
    value = _optional_str(fact, key)
    if value is None:
        raise ValueError(f"Knowledge {key} is required.")
    return value


def _required_int(fact: KnowledgeFact, key: str, *, minimum: int) -> int:
    value = _required_metadata(fact, key)
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"Knowledge {key} must be an integer >= {minimum}.")
    return value


def _required_metadata(fact: KnowledgeFact, key: str) -> object:
    if key not in fact.metadata:
        raise ValueError(f"Knowledge {_category(fact)} requires metadata {key!r}.")
    return fact.metadata[key]


def _scalar(value: object, key: str) -> str | int | float | bool:
    if isinstance(value, Enum):
        value = value.value
    if not isinstance(value, (str, int, float, bool)):
        raise TypeError(f"Knowledge {key} must be a provider-safe scalar.")
    if isinstance(value, str) and not value.strip():
        raise ValueError(f"Knowledge {key} must not be empty.")
    if isinstance(value, float) and not isfinite(value):
        raise ValueError(f"Knowledge {key} must be finite.")
    return value


def _metadata_date(fact: KnowledgeFact, key: str) -> date:
    return _parse_date(_required_metadata(fact, key), key)


def _parse_date(value: object, label: str) -> date:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(f"Knowledge {label} must be an ISO date.") from exc
    raise TypeError(f"Knowledge {label} must be a date or ISO date string.")
