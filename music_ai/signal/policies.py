"""Named deterministic qualification and maturity policies for Signals."""

from collections.abc import Iterable

from music_ai.signal.models import EvidenceMaturity, SignalState

# Lifecycle uses only closed canonical evidence. Daily facts are eligible only when
# an upstream contract explicitly marks them as closed historical observations.
DAILY_LIFECYCLE_REQUIRES_EXPLICIT_CLOSED_MARKER = True

PREFERENCE_LOCALLY_EMERGING_MATURITY = EvidenceMaturity.PRELIMINARY
PREFERENCE_CLOSED_STABLE_ONLY_MATURITY = EvidenceMaturity.PRELIMINARY
PREFERENCE_REPEATED_CONTINUITY_MATURITY = EvidenceMaturity.SUPPORTED
PREFERENCE_SINGLE_LONG_HORIZON_MATURITY = EvidenceMaturity.SUPPORTED
PREFERENCE_CORROBORATED_LONG_HORIZON_MATURITY = EvidenceMaturity.STRONG

MOVEMENT_SHORT_WINDOW_ONLY_MATURITY = EvidenceMaturity.PRELIMINARY
MOVEMENT_LONG_GROWTH_MATURITY = EvidenceMaturity.SUPPORTED
MOVEMENT_CONFLICTING_HORIZONS_MATURITY = EvidenceMaturity.SUPPORTED
MOVEMENT_CORROBORATED_GROWTH_MATURITY = EvidenceMaturity.STRONG

EXPLORATION_SINGLE_OBSERVATION_MATURITY = EvidenceMaturity.SUPPORTED
EXPLORATION_CORROBORATED_MATURITY = EvidenceMaturity.STRONG

CORE_EXPLORATION_COMPOSITE_MATURITY = EvidenceMaturity.STRONG

# Contextual Knowledge already establishes factual recurrence/overrepresentation.
# Signal maturity uses stricter repeated-day bands so minimum qualifying evidence is
# Watch-only while better repeated support may enter Primary/Secondary planning.
TIME_PATTERN_SUPPORTED_SEGMENT_DAYS = 5
TIME_PATTERN_STRONG_SEGMENT_DAYS = 8

ARTIST_TIME_AFFINITY_SUPPORTED_SEGMENT_DAYS = 5
ARTIST_TIME_AFFINITY_STRONG_SEGMENT_DAYS = 8

TIME_EVOLUTION_SUPPORTED_HIGH_SHARE_SEGMENT_DAYS = 5
TIME_EVOLUTION_STRONG_HIGH_SHARE_SEGMENT_DAYS = 8

# This is the sole Sprint 4A core/exploration composite rule. Other direction pairs
# remain separate evidence rather than acquiring semantics not frozen by ADR-0013.
CORE_EXPLORATION_DIRECTION_RULES = {
    ("increase", "increase"): "wider_mix_with_concentrated_core",
}


def daily_lifecycle_evidence_is_eligible(
    *, is_closed_day: object, contains_open_day: object
) -> bool:
    """Apply the explicit closed marker policy to Daily-derived evidence."""
    if contains_open_day is True:
        return False
    if not DAILY_LIFECYCLE_REQUIRES_EXPLICIT_CLOSED_MARKER:
        return True
    return is_closed_day is True and contains_open_day is False


def preference_maturity(
    state: SignalState, evidence_categories: Iterable[str]
) -> EvidenceMaturity:
    """Return lifecycle maturity from qualified, closed Knowledge categories."""
    categories = frozenset(evidence_categories)
    if state is SignalState.LOCALLY_EMERGING:
        return PREFERENCE_LOCALLY_EMERGING_MATURITY
    if state is SignalState.REPEATED_PRESENCE:
        if categories == {"stable_favorite"}:
            return PREFERENCE_CLOSED_STABLE_ONLY_MATURITY
        return PREFERENCE_REPEATED_CONTINUITY_MATURITY
    if state is SignalState.SUSTAINED_GROWTH:
        corroborating = {
            "artist_emergence",
            "artist_continuity",
            "artist_consistency",
        }
        if categories & corroborating:
            return PREFERENCE_CORROBORATED_LONG_HORIZON_MATURITY
        return PREFERENCE_SINGLE_LONG_HORIZON_MATURITY
    if state is SignalState.ESTABLISHED_CORE_PRESENCE:
        if len(categories) > 1:
            return PREFERENCE_CORROBORATED_LONG_HORIZON_MATURITY
        return PREFERENCE_SINGLE_LONG_HORIZON_MATURITY
    raise ValueError(f"Unsupported preference lifecycle state: {state!r}.")


def movement_maturity(
    state: SignalState,
    *,
    has_recent_movement: bool,
    has_long_horizon_movement: bool,
) -> EvidenceMaturity:
    """Return movement maturity without asking the provider to classify support."""
    if state is SignalState.SHORT_WINDOW_MOVEMENT:
        if not has_recent_movement or has_long_horizon_movement:
            raise ValueError("Short-window movement requires recent evidence only.")
        return MOVEMENT_SHORT_WINDOW_ONLY_MATURITY
    if state is SignalState.CONFLICTING_HORIZONS:
        if not has_recent_movement or not has_long_horizon_movement:
            raise ValueError("Conflicting horizons require both horizons.")
        return MOVEMENT_CONFLICTING_HORIZONS_MATURITY
    if state is SignalState.SUSTAINED_GROWTH:
        if not has_long_horizon_movement:
            raise ValueError("Sustained growth requires long-horizon evidence.")
        if has_recent_movement:
            return MOVEMENT_CORROBORATED_GROWTH_MATURITY
        return MOVEMENT_LONG_GROWTH_MATURITY
    raise ValueError(f"Unsupported movement state: {state!r}.")


def exploration_maturity(*, has_compatible_state_evidence: bool) -> EvidenceMaturity:
    """Strengthen evolution only when compatible state evidence corroborates it."""
    if has_compatible_state_evidence:
        return EXPLORATION_CORROBORATED_MATURITY
    return EXPLORATION_SINGLE_OBSERVATION_MATURITY


def time_pattern_maturity(segment_listening_day_count: int) -> EvidenceMaturity:
    """Map qualified time-pattern recurrence to its family-specific maturity."""
    return _repeated_day_maturity(
        segment_listening_day_count,
        supported=TIME_PATTERN_SUPPORTED_SEGMENT_DAYS,
        strong=TIME_PATTERN_STRONG_SEGMENT_DAYS,
    )


def artist_time_affinity_maturity(
    artist_segment_listening_day_count: int,
) -> EvidenceMaturity:
    """Map qualified artist-segment recurrence to affinity maturity."""
    return _repeated_day_maturity(
        artist_segment_listening_day_count,
        supported=ARTIST_TIME_AFFINITY_SUPPORTED_SEGMENT_DAYS,
        strong=ARTIST_TIME_AFFINITY_STRONG_SEGMENT_DAYS,
    )


def time_evolution_maturity(
    high_share_segment_listening_day_count: int,
) -> EvidenceMaturity:
    """Map recurrence on the higher-share side to evolution maturity."""
    return _repeated_day_maturity(
        high_share_segment_listening_day_count,
        supported=TIME_EVOLUTION_SUPPORTED_HIGH_SHARE_SEGMENT_DAYS,
        strong=TIME_EVOLUTION_STRONG_HIGH_SHARE_SEGMENT_DAYS,
    )


def _repeated_day_maturity(
    day_count: int, *, supported: int, strong: int
) -> EvidenceMaturity:
    if isinstance(day_count, bool) or not isinstance(day_count, int) or day_count < 0:
        raise ValueError("Repeated listening-day support must be a non-negative integer.")
    if day_count >= strong:
        return EvidenceMaturity.STRONG
    if day_count >= supported:
        return EvidenceMaturity.SUPPORTED
    return EvidenceMaturity.PRELIMINARY
