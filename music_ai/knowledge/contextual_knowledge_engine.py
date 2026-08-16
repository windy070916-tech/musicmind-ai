"""Canonical Knowledge qualification for contextual playback-event evidence."""

from fractions import Fraction

from music_ai.analytics.contextual_models import (
    ArtistContextualEvidence,
    ContextualListeningEvidence,
    ContextualWindowEvidence,
    LocalClockSegment,
    SegmentEventEvidence,
)
from music_ai.knowledge.models import (
    FactCategory,
    FactSource,
    FactTimeHorizon,
    ImportanceLevel,
    InsightType,
    KnowledgeFact,
)


# Reuse Sprint 3E's conservative minimum for a structurally useful 30-day
# window. Raw-event history has no Memory-style closed-day dimension.
MIN_CONTEXTUAL_LISTENING_DAYS = 10

# A contextual pattern must recur on multiple local dates, and a six-event
# floor avoids calling three isolated events a stable distribution pattern.
MIN_PATTERN_SEGMENT_LISTENING_DAYS = 3
MIN_PATTERN_SEGMENT_EVENTS = 6
MIN_PATTERN_SEGMENT_SHARE = Fraction(2, 5)

# Affinity is deliberately stricter than raw popularity: the artist/segment
# share must exceed the user's baseline both absolutely and proportionally.
MIN_AFFINITY_ARTIST_EVENTS = 8
MIN_AFFINITY_ARTIST_LISTENING_DAYS = 3
MIN_AFFINITY_ARTIST_SEGMENT_EVENTS = 4
MIN_AFFINITY_ARTIST_SEGMENT_LISTENING_DAYS = 3
MIN_AFFINITY_OVERALL_SEGMENT_EVENTS = 6
MIN_AFFINITY_OVERALL_SEGMENT_LISTENING_DAYS = 3
MIN_AFFINITY_SHARE_POINT_LIFT = Fraction(1, 5)
MIN_AFFINITY_RELATIVE_LIFT = Fraction(3, 2)

# Reuse Sprint 3E's 15-percentage-point directional-change scale, with the
# same recurrence/event floors as a standalone time-of-day pattern.
MIN_TIME_EVOLUTION_SHARE_POINT_CHANGE = Fraction(15, 100)
MIN_TIME_EVOLUTION_SEGMENT_EVENTS = 6
MIN_TIME_EVOLUTION_SEGMENT_LISTENING_DAYS = 3

OBSERVED_LOCAL_HISTORY = "observed_local_history"
RAW_HISTORY_COMPLETENESS_UNKNOWN = "unknown"


class ContextualKnowledgeEngine:
    """Qualify locale-neutral contextual observations for Signal Projection."""

    def __init__(self, evidence: ContextualListeningEvidence) -> None:
        if not isinstance(evidence, ContextualListeningEvidence):
            raise TypeError("evidence must be ContextualListeningEvidence.")
        self._evidence = evidence

    def generate_facts(self) -> tuple[KnowledgeFact, ...]:
        """Return pattern, affinity, and evolution facts in fixed family order."""
        facts: list[KnowledgeFact] = []
        pattern = _qualifying_pattern(self._evidence.current_window)
        if pattern is not None:
            facts.append(_pattern_fact(self._evidence, pattern))

        facts.extend(_affinity_facts(self._evidence))

        evolution = _qualifying_evolution(self._evidence)
        if evolution is not None:
            segment, previous, current = evolution
            facts.append(_evolution_fact(self._evidence, segment, previous, current))
        return tuple(facts)


def _qualifying_pattern(
    window: ContextualWindowEvidence,
) -> SegmentEventEvidence | None:
    if window.listening_day_count < MIN_CONTEXTUAL_LISTENING_DAYS:
        return None
    candidates = tuple(
        item
        for item in window.segments
        if item.listening_day_count >= MIN_PATTERN_SEGMENT_LISTENING_DAYS
        and item.event_count >= MIN_PATTERN_SEGMENT_EVENTS
        and _share(item.event_count, window.event_count) >= MIN_PATTERN_SEGMENT_SHARE
    )
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda item: (
            -_share(item.event_count, window.event_count),
            -item.listening_day_count,
            -item.event_count,
            _segment_index(item.segment),
        ),
    )


def _affinity_facts(
    evidence: ContextualListeningEvidence,
) -> tuple[KnowledgeFact, ...]:
    window = evidence.current_window
    if window.listening_day_count < MIN_CONTEXTUAL_LISTENING_DAYS:
        return ()
    candidates: list[
        tuple[Fraction, Fraction, ArtistContextualEvidence, SegmentEventEvidence]
    ] = []
    for artist in window.artists:
        if (
            artist.event_count < MIN_AFFINITY_ARTIST_EVENTS
            or artist.listening_day_count < MIN_AFFINITY_ARTIST_LISTENING_DAYS
        ):
            continue
        artist_candidates: list[
            tuple[Fraction, Fraction, SegmentEventEvidence]
        ] = []
        for artist_segment, overall_segment in zip(
            artist.segments, window.segments, strict=True
        ):
            if not _affinity_support_qualifies(artist_segment, overall_segment):
                continue
            artist_share = _share(artist_segment.event_count, artist.event_count)
            overall_share = _share(overall_segment.event_count, window.event_count)
            lift = artist_share - overall_share
            relative_lift = artist_share / overall_share
            if (
                lift >= MIN_AFFINITY_SHARE_POINT_LIFT
                and relative_lift >= MIN_AFFINITY_RELATIVE_LIFT
            ):
                artist_candidates.append((lift, relative_lift, artist_segment))
        if artist_candidates:
            lift, relative_lift, segment = min(
                artist_candidates,
                key=lambda item: (
                    -item[0],
                    -item[1],
                    -item[2].listening_day_count,
                    -item[2].event_count,
                    _segment_index(item[2].segment),
                ),
            )
            candidates.append((lift, relative_lift, artist, segment))

    ordered = sorted(
        candidates,
        key=lambda item: (
            -item[0],
            -item[1],
            -item[3].listening_day_count,
            -item[3].event_count,
            item[2].identity,
            _segment_index(item[3].segment),
        ),
    )
    return tuple(
        _affinity_fact(evidence, artist, segment, lift, relative_lift)
        for lift, relative_lift, artist, segment in ordered
    )


def _affinity_support_qualifies(
    artist_segment: SegmentEventEvidence, overall_segment: SegmentEventEvidence
) -> bool:
    return (
        artist_segment.event_count >= MIN_AFFINITY_ARTIST_SEGMENT_EVENTS
        and artist_segment.listening_day_count
        >= MIN_AFFINITY_ARTIST_SEGMENT_LISTENING_DAYS
        and overall_segment.event_count >= MIN_AFFINITY_OVERALL_SEGMENT_EVENTS
        and overall_segment.listening_day_count
        >= MIN_AFFINITY_OVERALL_SEGMENT_LISTENING_DAYS
    )


def _qualifying_evolution(
    evidence: ContextualListeningEvidence,
) -> tuple[LocalClockSegment, SegmentEventEvidence, SegmentEventEvidence] | None:
    previous_window = evidence.previous_window
    current_window = evidence.current_window
    if (
        previous_window.listening_day_count < MIN_CONTEXTUAL_LISTENING_DAYS
        or current_window.listening_day_count < MIN_CONTEXTUAL_LISTENING_DAYS
    ):
        return None
    candidates: list[
        tuple[Fraction, LocalClockSegment, SegmentEventEvidence, SegmentEventEvidence]
    ] = []
    for previous, current in zip(
        previous_window.segments, current_window.segments, strict=True
    ):
        previous_share = _share(previous.event_count, previous_window.event_count)
        current_share = _share(current.event_count, current_window.event_count)
        change = current_share - previous_share
        stronger_support = current if change > 0 else previous
        if (
            abs(change) >= MIN_TIME_EVOLUTION_SHARE_POINT_CHANGE
            and stronger_support.event_count >= MIN_TIME_EVOLUTION_SEGMENT_EVENTS
            and stronger_support.listening_day_count
            >= MIN_TIME_EVOLUTION_SEGMENT_LISTENING_DAYS
        ):
            candidates.append((abs(change), current.segment, previous, current))
    if not candidates:
        return None
    _, segment, previous, current = min(
        candidates,
        key=lambda item: (
            -item[0],
            -max(item[2].listening_day_count, item[3].listening_day_count),
            -max(item[2].event_count, item[3].event_count),
            _segment_index(item[1]),
        ),
    )
    return segment, previous, current


def _pattern_fact(
    evidence: ContextualListeningEvidence, segment: SegmentEventEvidence
) -> KnowledgeFact:
    window = evidence.current_window
    segment_share = _share(segment.event_count, window.event_count)
    return KnowledgeFact(
        category=FactCategory.LISTENING_TIME_OF_DAY_PATTERN,
        importance=ImportanceLevel.MEDIUM,
        title="Observed playback-event time pattern",
        description=(
            f"The {segment.segment.value} local-clock segment contained "
            f"{float(segment_share):.0%} of observed playback events in the current "
            f"30-day period, recurring across {segment.listening_day_count} listening days."
        ),
        metadata={
            **_current_window_metadata(evidence),
            "subject_key": "listening:all_events",
            "concept_key": "listening_time_of_day_pattern",
            "segment": segment.segment.value,
            "event_count": window.event_count,
            "listening_day_count": window.listening_day_count,
            "segment_event_count": segment.event_count,
            "segment_listening_day_count": segment.listening_day_count,
            "segment_event_share": float(segment_share),
        },
        tags=("contextual", "observed_events", "time_of_day"),
        source=FactSource.CONTEXTUAL_LISTENING_EVIDENCE,
        date_range=(window.start_date.isoformat(), window.end_date.isoformat()),
        insight_type=InsightType.BEHAVIOR,
        time_horizon=FactTimeHorizon.LONG_TERM,
    )


def _affinity_fact(
    evidence: ContextualListeningEvidence,
    artist: ArtistContextualEvidence,
    artist_segment: SegmentEventEvidence,
    lift: Fraction,
    relative_lift: Fraction,
) -> KnowledgeFact:
    window = evidence.current_window
    overall_segment = window.segments[_segment_index(artist_segment.segment)]
    artist_share = _share(artist_segment.event_count, artist.event_count)
    overall_share = _share(overall_segment.event_count, window.event_count)
    return KnowledgeFact(
        category=FactCategory.ARTIST_TIME_OF_DAY_AFFINITY,
        importance=ImportanceLevel.MEDIUM,
        title="Artist event-time overrepresentation",
        description=(
            f"The {artist_segment.segment.value} local-clock segment contained "
            f"{float(artist_share):.0%} of {artist.artist_name}'s observed playback "
            f"events, compared with {float(overall_share):.0%} of all observed events."
        ),
        metadata={
            **_current_window_metadata(evidence),
            "subject_key": f"{artist.identity[0]}:{artist.identity[1]}",
            "concept_key": "artist_time_of_day_affinity",
            "segment": artist_segment.segment.value,
            "artist_identity": artist.identity,
            "spotify_artist_id": artist.spotify_artist_id,
            "artist_name": artist.artist_name,
            "artist_event_count": artist.event_count,
            "artist_listening_day_count": artist.listening_day_count,
            "artist_segment_event_count": artist_segment.event_count,
            "artist_segment_listening_day_count": (
                artist_segment.listening_day_count
            ),
            "artist_segment_share": float(artist_share),
            "overall_event_count": window.event_count,
            "overall_listening_day_count": window.listening_day_count,
            "overall_segment_event_count": overall_segment.event_count,
            "overall_segment_listening_day_count": (
                overall_segment.listening_day_count
            ),
            "overall_segment_share": float(overall_share),
            "share_point_lift": float(lift),
            "relative_lift": float(relative_lift),
        },
        tags=("contextual", "observed_events", "artist_time_affinity"),
        source=FactSource.CONTEXTUAL_LISTENING_EVIDENCE,
        date_range=(window.start_date.isoformat(), window.end_date.isoformat()),
        insight_type=InsightType.BEHAVIOR,
        time_horizon=FactTimeHorizon.LONG_TERM,
    )


def _evolution_fact(
    evidence: ContextualListeningEvidence,
    segment: LocalClockSegment,
    previous: SegmentEventEvidence,
    current: SegmentEventEvidence,
) -> KnowledgeFact:
    previous_window = evidence.previous_window
    current_window = evidence.current_window
    previous_share = _share(previous.event_count, previous_window.event_count)
    current_share = _share(current.event_count, current_window.event_count)
    signed_change = current_share - previous_share
    direction = "increase" if signed_change > 0 else "decrease"
    verb = "increased" if direction == "increase" else "decreased"
    return KnowledgeFact(
        category=FactCategory.LISTENING_TIME_OF_DAY_EVOLUTION,
        importance=ImportanceLevel.MEDIUM,
        title=f"Observed playback-event time share {verb}",
        description=(
            f"The share of observed playback events in the {segment.value} "
            f"local-clock segment {verb} from {float(previous_share):.0%} in the "
            f"previous 30-day period to {float(current_share):.0%} in the current period."
        ),
        metadata={
            **_history_metadata(evidence),
            "subject_key": "listening:all_events",
            "concept_key": "listening_time_of_day_evolution",
            "direction": direction,
            "segment": segment.value,
            "previous_start_date": previous_window.start_date.isoformat(),
            "previous_end_date": previous_window.end_date.isoformat(),
            "current_start_date": current_window.start_date.isoformat(),
            "current_end_date": current_window.end_date.isoformat(),
            "previous_event_count": previous_window.event_count,
            "current_event_count": current_window.event_count,
            "previous_listening_day_count": previous_window.listening_day_count,
            "current_listening_day_count": current_window.listening_day_count,
            "previous_segment_event_count": previous.event_count,
            "current_segment_event_count": current.event_count,
            "previous_segment_listening_day_count": previous.listening_day_count,
            "current_segment_listening_day_count": current.listening_day_count,
            "previous_segment_event_share": float(previous_share),
            "current_segment_event_share": float(current_share),
            "signed_share_change": float(signed_change),
            "absolute_share_change": float(abs(signed_change)),
        },
        tags=("contextual", "observed_events", "time_of_day_evolution"),
        source=FactSource.CONTEXTUAL_LISTENING_EVIDENCE,
        date_range=(
            previous_window.start_date.isoformat(),
            current_window.end_date.isoformat(),
        ),
        insight_type=InsightType.BEHAVIOR,
        time_horizon=FactTimeHorizon.LONG_TERM,
    )


def _current_window_metadata(
    evidence: ContextualListeningEvidence,
) -> dict[str, object]:
    window = evidence.current_window
    return {
        **_history_metadata(evidence),
        "window_start_date": window.start_date.isoformat(),
        "window_end_date": window.end_date.isoformat(),
    }


def _history_metadata(evidence: ContextualListeningEvidence) -> dict[str, object]:
    return {
        "timezone_name": evidence.timezone_name,
        "as_of": evidence.as_of.isoformat(),
        "history_scope": OBSERVED_LOCAL_HISTORY,
        "raw_history_completeness": RAW_HISTORY_COMPLETENESS_UNKNOWN,
    }


def _share(numerator: int, denominator: int) -> Fraction:
    return Fraction(numerator, denominator) if denominator > 0 else Fraction(0, 1)


def _segment_index(segment: LocalClockSegment) -> int:
    return tuple(LocalClockSegment).index(segment)
