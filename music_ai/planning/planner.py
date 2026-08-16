"""Deterministic grouping, ranking, and role assignment for Signals."""

from collections.abc import Iterable
from dataclasses import dataclass
from hashlib import sha256
from itertools import combinations

from music_ai.planning.models import (
    InterpretationPlan,
    InterpretationRole,
    PlanItem,
    SignalRelationship,
)
from music_ai.signal.models import (
    EvidenceMaturity,
    Signal,
    SignalRoleEligibility,
    SignalState,
    SignalType,
)
from music_ai.visible_content.models import VisibleContentManifest


# Same-tier family order is deliberately small and explicit. Rich composites and
# contextual associations precede distributions; lifecycle precedes isolated
# movement. Maturity and named support dimensions are compared before this order.
_FAMILY_PRIORITY = {
    SignalType.CORE_VS_EXPLORATION_BALANCE: 0,
    SignalType.ARTIST_TIME_OF_DAY_AFFINITY: 1,
    SignalType.TIME_PATTERN_EVOLUTION: 2,
    SignalType.LISTENING_TIME_OF_DAY_PATTERN: 3,
    SignalType.ARTIST_PREFERENCE_FORMATION: 4,
    SignalType.TEMPORARY_SPIKE_VS_SUSTAINED_GROWTH: 5,
    SignalType.EXPLORATION_INTENSITY: 6,
}

# These are not qualification thresholds or a score. They are the observable
# dimensions consulted, in order, only after interpretation tier and maturity tie.
_SUPPORT_DIMENSION_TIE_BREAK_ORDER = (
    "closed_supporting_day_count",
    "closed_listening_days",
    "closed_days",
    "closed_listening_day_count",
    "recent_closed_listening_day_count",
    "comparison_closed_listening_day_count",
    "supporting_listening_days",
    "supporting_days",
    "qualifying_day_count",
    "repeated_listening_days",
    "segment_listening_days",
    "segment_listening_day_count",
    "artist_segment_listening_days",
    "artist_segment_listening_day_count",
    "appearance_days",
    "appearance_day_count",
    "current_listening_days",
    "current_listening_day_count",
    "current_segment_listening_day_count",
    "previous_listening_days",
    "previous_listening_day_count",
    "previous_segment_listening_day_count",
    "listening_day_count",
    "event_count",
)

_MATURITY_PRIORITY = {
    EvidenceMaturity.STRONG: 0,
    EvidenceMaturity.SUPPORTED: 1,
    EvidenceMaturity.PRELIMINARY: 2,
}

# Lower numbers are higher interpretation value, as frozen by ADR-0013.
_RELATIONSHIP_TIER = 0
_CONTEXTUAL_TIER = 1
_LIFECYCLE_TIER = 2
_SINGLE_OBSERVATION_TIER = 3

_CONTEXTUAL_SIGNAL_TYPES = {
    SignalType.CORE_VS_EXPLORATION_BALANCE,
    SignalType.LISTENING_TIME_OF_DAY_PATTERN,
    SignalType.ARTIST_TIME_OF_DAY_AFFINITY,
    SignalType.TIME_PATTERN_EVOLUTION,
}
_LIFECYCLE_STATES = {
    SignalState.LOCALLY_EMERGING,
    SignalState.REPEATED_PRESENCE,
    SignalState.SUSTAINED_GROWTH,
    SignalState.ESTABLISHED_CORE_PRESENCE,
}
_PURE_OBSERVATION_TYPES = {SignalType.EXPLORATION_INTENSITY}
_PURE_OBSERVATION_STATES = {SignalState.SHORT_WINDOW_MOVEMENT}


@dataclass(frozen=True, slots=True)
class _Candidate:
    signals: tuple[Signal, ...]
    relationship: SignalRelationship
    value_tier: int
    maturity: EvidenceMaturity
    interpretation_key: str

    @property
    def signal_ids(self) -> tuple[str, ...]:
        return tuple(signal.signal_id for signal in self.signals)

    @property
    def evidence_ids(self) -> frozenset[str]:
        return frozenset(
            reference.evidence_id
            for signal in self.signals
            for reference in signal.evidence_refs
        )


class InterpretationPlanner:
    """Plan at most one Primary, Secondary, and Watch deterministically.

    The planner is stateless and accepts no report-history or novelty input. It
    relates only already-qualified Signals and never recalculates their evidence.
    """

    def plan(
        self,
        signals: Iterable[Signal],
        manifest: VisibleContentManifest | None = None,
    ) -> InterpretationPlan:
        """Apply the Evidence Gate, anti-restatement, ranking, and role rules."""
        resolved_manifest = manifest or VisibleContentManifest()
        if not isinstance(resolved_manifest, VisibleContentManifest):
            raise TypeError("manifest must be a VisibleContentManifest or None.")
        resolved_signals = tuple(signals)
        if any(not isinstance(signal, Signal) for signal in resolved_signals):
            raise TypeError("signals must contain only Signal values.")
        signal_ids = [signal.signal_id for signal in resolved_signals]
        if len(signal_ids) != len(set(signal_ids)):
            raise ValueError("Planner input Signal identifiers must be unique.")

        regular = tuple(
            signal
            for signal in resolved_signals
            if signal.maturity
            in {EvidenceMaturity.SUPPORTED, EvidenceMaturity.STRONG}
            and signal.role_eligibility
            is SignalRoleEligibility.PRIMARY_OR_SECONDARY
        )
        watch = tuple(
            signal
            for signal in resolved_signals
            if signal.maturity is EvidenceMaturity.PRELIMINARY
            and signal.role_eligibility is SignalRoleEligibility.WATCH_ONLY
        )

        regular_candidates = self._ranked_candidates(regular, resolved_manifest)
        watch_candidates = self._ranked_candidates(watch, resolved_manifest)

        selected: list[tuple[InterpretationRole, _Candidate]] = []
        used_signal_ids: set[str] = set()
        used_evidence_ids: set[str] = set()
        primary = _first_disjoint(
            regular_candidates,
            used_signal_ids,
            used_evidence_ids,
        )
        if primary is not None:
            selected.append((InterpretationRole.PRIMARY, primary))
            used_signal_ids.update(primary.signal_ids)
            used_evidence_ids.update(primary.evidence_ids)
            secondary = _first_disjoint(
                regular_candidates,
                used_signal_ids,
                used_evidence_ids,
            )
            if secondary is not None:
                selected.append((InterpretationRole.SECONDARY, secondary))
                used_signal_ids.update(secondary.signal_ids)
                used_evidence_ids.update(secondary.evidence_ids)

        watch_item = _first_disjoint(
            watch_candidates,
            used_signal_ids,
            used_evidence_ids,
        )
        if watch_item is not None:
            selected.append((InterpretationRole.WATCH, watch_item))

        return InterpretationPlan(
            tuple(
                _plan_item(role, candidate)
                for role, candidate in selected
            )
        )

    def relationship_for(
        self,
        left: Signal,
        right: Signal,
    ) -> SignalRelationship:
        """Return the one registered finite relationship for two Signals."""
        if not isinstance(left, Signal) or not isinstance(right, Signal):
            raise TypeError("relationship inputs must be Signal values.")
        if left.signal_id == right.signal_id:
            return SignalRelationship.UNRELATED
        left_evidence = {item.evidence_id for item in left.evidence_refs}
        right_evidence = {item.evidence_id for item in right.evidence_refs}
        if not (left_evidence - right_evidence and right_evidence - left_evidence):
            # A relationship must add genuinely independent support from both
            # Signals. Otherwise it is a composition/restatement concern, not a
            # new cross-Signal interpretation.
            return SignalRelationship.UNRELATED

        by_type = {left.signal_type: left, right.signal_type: right}
        types = frozenset(by_type)
        preference_growth = frozenset(
            {
                SignalType.ARTIST_PREFERENCE_FORMATION,
                SignalType.TEMPORARY_SPIKE_VS_SUSTAINED_GROWTH,
            }
        )
        if types == preference_growth:
            preference = by_type[SignalType.ARTIST_PREFERENCE_FORMATION]
            movement = by_type[
                SignalType.TEMPORARY_SPIKE_VS_SUSTAINED_GROWTH
            ]
            if not _same_subject(preference, movement):
                return SignalRelationship.UNRELATED
            if movement.state is SignalState.SUSTAINED_GROWTH:
                return SignalRelationship.REINFORCEMENT
            if movement.state is SignalState.CONFLICTING_HORIZONS:
                return SignalRelationship.CONTRAST
            return SignalRelationship.UNRELATED

        preference_affinity = frozenset(
            {
                SignalType.ARTIST_PREFERENCE_FORMATION,
                SignalType.ARTIST_TIME_OF_DAY_AFFINITY,
            }
        )
        if types == preference_affinity:
            preference = by_type[SignalType.ARTIST_PREFERENCE_FORMATION]
            affinity = by_type[SignalType.ARTIST_TIME_OF_DAY_AFFINITY]
            if _same_subject(preference, affinity):
                return SignalRelationship.CONTEXTUAL_SUPPORT
            return SignalRelationship.UNRELATED

        pattern_evolution = frozenset(
            {
                SignalType.LISTENING_TIME_OF_DAY_PATTERN,
                SignalType.TIME_PATTERN_EVOLUTION,
            }
        )
        if types == pattern_evolution:
            pattern = by_type[SignalType.LISTENING_TIME_OF_DAY_PATTERN]
            evolution = by_type[SignalType.TIME_PATTERN_EVOLUTION]
            if not _same_segment(pattern, evolution):
                return SignalRelationship.UNRELATED
            if evolution.state is SignalState.SEGMENT_SHARE_INCREASED:
                return SignalRelationship.REINFORCEMENT
            if evolution.state is SignalState.SEGMENT_SHARE_DECREASED:
                return SignalRelationship.CONTRAST
            return SignalRelationship.UNRELATED

        pattern_affinity = frozenset(
            {
                SignalType.LISTENING_TIME_OF_DAY_PATTERN,
                SignalType.ARTIST_TIME_OF_DAY_AFFINITY,
            }
        )
        if types == pattern_affinity:
            pattern = by_type[SignalType.LISTENING_TIME_OF_DAY_PATTERN]
            affinity = by_type[SignalType.ARTIST_TIME_OF_DAY_AFFINITY]
            if _same_segment(pattern, affinity):
                return SignalRelationship.CONTEXTUAL_SUPPORT
        return SignalRelationship.UNRELATED

    def _ranked_candidates(
        self,
        signals: tuple[Signal, ...],
        manifest: VisibleContentManifest,
    ) -> tuple[_Candidate, ...]:
        ordered_signals = tuple(sorted(signals, key=lambda signal: signal.signal_id))
        related = []
        for left, right in combinations(ordered_signals, 2):
            relationship = self.relationship_for(left, right)
            if relationship is SignalRelationship.UNRELATED:
                continue
            related.append(
                _Candidate(
                    signals=(left, right),
                    relationship=relationship,
                    value_tier=_RELATIONSHIP_TIER,
                    maturity=_least_maturity(left, right),
                    interpretation_key=f"relationship:{relationship}",
                )
            )
        singles = [
            _Candidate(
                signals=(signal,),
                relationship=SignalRelationship.UNRELATED,
                value_tier=_value_tier(signal),
                maturity=signal.maturity,
                interpretation_key=(
                    f"signal:{signal.signal_type}:{signal.state}"
                ),
            )
            for signal in ordered_signals
            if not _is_pure_restatement(signal, manifest)
        ]
        return tuple(sorted((*related, *singles), key=_candidate_order))


def _is_pure_restatement(
    signal: Signal,
    manifest: VisibleContentManifest,
) -> bool:
    if manifest.matches_semantic(
        concept=str(signal.signal_type),
        subject_key=signal.subject_key,
        direction=str(signal.state),
        horizon=str(signal.horizon),
    ):
        return True
    if (
        signal.signal_type not in _PURE_OBSERVATION_TYPES
        and signal.state not in _PURE_OBSERVATION_STATES
    ):
        return False
    evidence_ids = tuple(ref.evidence_id for ref in signal.evidence_refs)
    return bool(evidence_ids) and all(
        manifest.contains_evidence(evidence_id) for evidence_id in evidence_ids
    )


def _candidate_order(candidate: _Candidate) -> tuple[object, ...]:
    return (
        candidate.value_tier,
        _MATURITY_PRIORITY[candidate.maturity],
        *_support_order(candidate.signals),
        tuple(
            sorted(
                _FAMILY_PRIORITY[signal.signal_type]
                for signal in candidate.signals
            )
        ),
        candidate.signal_ids,
    )


def _support_order(signals: tuple[Signal, ...]) -> tuple[float, ...]:
    per_signal = tuple(_numeric_support(signal) for signal in signals)
    return tuple(
        -min(values[index] for values in per_signal)
        for index in range(len(_SUPPORT_DIMENSION_TIE_BREAK_ORDER))
    )


def _numeric_support(signal: Signal) -> tuple[float, ...]:
    numeric_dimensions = tuple(
        (dimension.name, float(dimension.value))
        for dimension in signal.supporting_dimensions
        if isinstance(dimension.value, (int, float))
        and not isinstance(dimension.value, bool)
    )
    values: list[float] = []
    for policy_name in _SUPPORT_DIMENSION_TIE_BREAK_ORDER:
        matching = tuple(
            value
            for name, value in numeric_dimensions
            if name == policy_name or name.endswith(f".{policy_name}")
        )
        # Multiple cross-horizon observations use their weakest matching support;
        # a rich window cannot hide a thin one during a same-tier tie.
        values.append(min(matching) if matching else 0.0)
    return tuple(values)


def _value_tier(signal: Signal) -> int:
    if signal.signal_type in _CONTEXTUAL_SIGNAL_TYPES:
        return _CONTEXTUAL_TIER
    if (
        signal.signal_type is SignalType.ARTIST_PREFERENCE_FORMATION
        or signal.state in _LIFECYCLE_STATES
    ):
        return _LIFECYCLE_TIER
    return _SINGLE_OBSERVATION_TIER


def _least_maturity(left: Signal, right: Signal) -> EvidenceMaturity:
    return max(
        (left.maturity, right.maturity),
        key=_MATURITY_PRIORITY.__getitem__,
    )


def _same_subject(left: Signal, right: Signal) -> bool:
    return bool(left.subject_key) and left.subject_key == right.subject_key


def _same_segment(left: Signal, right: Signal) -> bool:
    left_segment = _named_value(left, "segment")
    right_segment = _named_value(right, "segment")
    return left_segment is not None and left_segment == right_segment


def _named_value(signal: Signal, name: str) -> object | None:
    return next(
        (
            value.value
            for value in signal.reference_values
            if value.name == name
        ),
        None,
    )


def _first_disjoint(
    candidates: tuple[_Candidate, ...],
    used_signal_ids: set[str],
    used_evidence_ids: set[str],
) -> _Candidate | None:
    return next(
        (
            candidate
            for candidate in candidates
            if used_signal_ids.isdisjoint(candidate.signal_ids)
            and not candidate.evidence_ids.issubset(used_evidence_ids)
        ),
        None,
    )


def _plan_item(role: InterpretationRole, candidate: _Candidate) -> PlanItem:
    payload = "|".join(
        (
            str(role),
            str(candidate.relationship),
            candidate.interpretation_key,
            *candidate.signal_ids,
        )
    )
    plan_item_id = f"plan_{sha256(payload.encode('utf-8')).hexdigest()[:20]}"
    return PlanItem(
        plan_item_id=plan_item_id,
        role=role,
        signal_ids=candidate.signal_ids,
        relationship=candidate.relationship,
        interpretation_key=candidate.interpretation_key,
    )
