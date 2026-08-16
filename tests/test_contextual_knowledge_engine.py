"""Canonical contextual Knowledge qualification tests for Sprint 4A."""

from datetime import date, datetime, timezone

import pytest

from music_ai.analytics import (
    ArtistContextualEvidence,
    ContextualListeningEvidence,
    ContextualWindowEvidence,
    LocalClockSegment,
    SegmentEventEvidence,
)
from music_ai.knowledge import (
    ContextualKnowledgeEngine,
    FactCategory,
    FactSource,
    FactTimeHorizon,
    InsightType,
)


_PREVIOUS_START = date(2026, 6, 15)
_CURRENT_START = date(2026, 7, 15)
_CURRENT_END = date(2026, 8, 14)
_AS_OF = datetime(2026, 8, 14, 12, tzinfo=timezone.utc)


def _segments(
    counts: tuple[int, int, int, int],
    days: tuple[int, int, int, int],
) -> tuple[SegmentEventEvidence, ...]:
    total = sum(counts)
    return tuple(
        SegmentEventEvidence(
            segment=segment,
            event_count=count,
            listening_day_count=day_count,
            event_share=(count / total) if total else 0.0,
        )
        for segment, count, day_count in zip(
            LocalClockSegment, counts, days, strict=True
        )
    )


def _artist(
    identity: tuple[str, str],
    counts: tuple[int, int, int, int],
    days: tuple[int, int, int, int],
    *,
    name: str | None = None,
) -> ArtistContextualEvidence:
    artist_name = name or identity[1].title()
    return ArtistContextualEvidence(
        identity=identity,
        spotify_artist_id=identity[1] if identity[0] == "spotify" else None,
        artist_name=artist_name,
        event_count=sum(counts),
        listening_day_count=max(days),
        segments=_segments(counts, days),
    )


def _window(
    start_date: date,
    end_date: date,
    counts: tuple[int, int, int, int],
    days: tuple[int, int, int, int],
    *,
    listening_days: int = 10,
    artists: tuple[ArtistContextualEvidence, ...] = (),
) -> ContextualWindowEvidence:
    return ContextualWindowEvidence(
        start_date=start_date,
        end_date=end_date,
        event_count=sum(counts),
        listening_day_count=listening_days,
        segments=_segments(counts, days),
        artists=tuple(sorted(artists, key=lambda item: item.identity)),
    )


def _evidence(
    *,
    previous_counts: tuple[int, int, int, int] = (10, 5, 5, 5),
    previous_days: tuple[int, int, int, int] = (5, 3, 3, 3),
    current_counts: tuple[int, int, int, int] = (10, 5, 5, 5),
    current_days: tuple[int, int, int, int] = (5, 3, 3, 3),
    previous_listening_days: int = 10,
    current_listening_days: int = 10,
    artists: tuple[ArtistContextualEvidence, ...] = (),
) -> ContextualListeningEvidence:
    return ContextualListeningEvidence(
        timezone_name="UTC",
        as_of=_AS_OF,
        previous_window=_window(
            _PREVIOUS_START,
            _CURRENT_START,
            previous_counts,
            previous_days,
            listening_days=previous_listening_days,
        ),
        current_window=_window(
            _CURRENT_START,
            _CURRENT_END,
            current_counts,
            current_days,
            listening_days=current_listening_days,
            artists=artists,
        ),
    )


def _facts(evidence: ContextualListeningEvidence, category: FactCategory):
    return tuple(
        fact
        for fact in ContextualKnowledgeEngine(evidence).generate_facts()
        if fact.category is category
    )


def test_pattern_exact_policy_boundary_emits_canonical_observed_event_fact() -> None:
    evidence = _evidence(
        current_counts=(6, 3, 3, 3),
        current_days=(3, 3, 3, 3),
    )

    facts = _facts(evidence, FactCategory.LISTENING_TIME_OF_DAY_PATTERN)

    assert len(facts) == 1
    fact = facts[0]
    assert fact.source is FactSource.CONTEXTUAL_LISTENING_EVIDENCE
    assert fact.time_horizon is FactTimeHorizon.LONG_TERM
    assert fact.insight_type is InsightType.BEHAVIOR
    assert fact.message_key is None
    assert fact.confidence is None
    assert fact.date_range == ("2026-07-15", "2026-08-14")
    assert fact.metadata["segment"] == "00:00-06:00"
    assert fact.metadata["segment_event_count"] == 6
    assert fact.metadata["segment_listening_day_count"] == 3
    assert fact.metadata["segment_event_share"] == pytest.approx(0.4)
    assert fact.metadata["history_scope"] == "observed_local_history"
    assert fact.metadata["raw_history_completeness"] == "unknown"
    assert "observed playback events" in fact.description
    assert "listening time" not in fact.description.casefold()
    assert all("duration" not in key for key in fact.metadata)


@pytest.mark.parametrize(
    ("counts", "days", "listening_days"),
    (
        ((6, 3, 3, 3), (3, 3, 3, 3), 9),
        ((6, 3, 3, 3), (2, 3, 3, 3), 10),
        ((5, 3, 2, 2), (3, 3, 2, 2), 10),
        ((6, 4, 3, 3), (3, 3, 3, 3), 10),
    ),
    ids=("window-days", "segment-days", "segment-events", "segment-share"),
)
def test_pattern_rejects_support_below_each_policy_floor(
    counts, days, listening_days
) -> None:
    evidence = _evidence(
        current_counts=counts,
        current_days=days,
        current_listening_days=listening_days,
    )
    assert _facts(evidence, FactCategory.LISTENING_TIME_OF_DAY_PATTERN) == ()


def test_one_day_cluster_is_not_a_stable_pattern() -> None:
    evidence = _evidence(
        current_counts=(20, 0, 0, 0),
        current_days=(1, 0, 0, 0),
        current_listening_days=1,
    )
    assert _facts(evidence, FactCategory.LISTENING_TIME_OF_DAY_PATTERN) == ()


def test_affinity_compares_artist_distribution_with_user_baseline() -> None:
    artist = _artist(
        ("spotify", "artist-a"),
        (8, 0, 0, 0),
        (4, 0, 0, 0),
        name="Artist A",
    )
    evidence = _evidence(
        current_counts=(20, 20, 20, 20),
        current_days=(6, 6, 6, 6),
        artists=(artist,),
    )

    facts = _facts(evidence, FactCategory.ARTIST_TIME_OF_DAY_AFFINITY)

    assert len(facts) == 1
    fact = facts[0]
    assert fact.metadata["artist_identity"] == ("spotify", "artist-a")
    assert fact.metadata["artist_segment_share"] == 1.0
    assert fact.metadata["overall_segment_share"] == 0.25
    assert fact.metadata["share_point_lift"] == 0.75
    assert fact.metadata["relative_lift"] == 4.0
    assert "compared with 25% of all observed events" in fact.description


def test_popular_artist_following_overall_distribution_is_not_false_affinity() -> None:
    artist = _artist(
        ("spotify", "popular"),
        (0, 0, 0, 8),
        (0, 0, 0, 4),
        name="Popular Artist",
    )
    # The artist has many evening events, but the user's overall evening share
    # is already 80%; raw count alone is not evidence of overrepresentation.
    evidence = _evidence(
        current_counts=(6, 6, 8, 80),
        current_days=(3, 3, 3, 10),
        artists=(artist,),
    )

    assert _facts(evidence, FactCategory.ARTIST_TIME_OF_DAY_AFFINITY) == ()


def test_affinity_requires_repetition_across_distinct_artist_segment_days() -> None:
    artist = _artist(
        ("spotify", "artist-a"),
        (8, 0, 0, 0),
        (1, 0, 0, 0),
        name="Artist A",
    )
    evidence = _evidence(
        current_counts=(20, 20, 20, 20),
        current_days=(6, 6, 6, 6),
        artists=(artist,),
    )
    assert _facts(evidence, FactCategory.ARTIST_TIME_OF_DAY_AFFINITY) == ()


def test_affinity_emits_only_strongest_segment_per_artist_in_stable_order() -> None:
    artist_a = _artist(
        ("spotify", "artist-a"),
        (4, 4, 0, 0),
        (3, 3, 0, 0),
        name="Artist A",
    )
    artist_b = _artist(
        ("spotify", "artist-b"),
        (0, 0, 8, 0),
        (0, 0, 4, 0),
        name="Artist B",
    )
    evidence = _evidence(
        current_counts=(10, 10, 10, 70),
        current_days=(5, 5, 5, 10),
        artists=(artist_b, artist_a),
    )

    facts = _facts(evidence, FactCategory.ARTIST_TIME_OF_DAY_AFFINITY)

    assert tuple(fact.metadata["artist_name"] for fact in facts) == (
        "Artist B",
        "Artist A",
    )
    assert sum(fact.metadata["artist_name"] == "Artist A" for fact in facts) == 1
    assert next(
        fact.metadata["segment"]
        for fact in facts
        if fact.metadata["artist_name"] == "Artist A"
    ) == "00:00-06:00"


def test_time_pattern_evolution_exact_15_point_boundary_qualifies() -> None:
    evidence = _evidence(
        previous_counts=(8, 4, 4, 4),
        previous_days=(4, 3, 3, 3),
        current_counts=(11, 3, 3, 3),
        current_days=(5, 3, 3, 3),
    )

    facts = _facts(evidence, FactCategory.LISTENING_TIME_OF_DAY_EVOLUTION)

    assert len(facts) == 1
    fact = facts[0]
    assert fact.metadata["segment"] == "00:00-06:00"
    assert fact.metadata["direction"] == "increase"
    assert fact.metadata["previous_segment_event_share"] == 0.4
    assert fact.metadata["current_segment_event_share"] == 0.55
    assert fact.metadata["absolute_share_change"] == pytest.approx(0.15)
    assert fact.date_range == ("2026-06-15", "2026-08-14")


def test_evolution_rejects_below_change_and_recurrence_boundaries() -> None:
    below_change = _evidence(
        previous_counts=(8, 4, 4, 4),
        previous_days=(4, 3, 3, 3),
        current_counts=(10, 4, 3, 3),
        current_days=(5, 3, 3, 3),
    )
    one_day = _evidence(
        previous_counts=(8, 4, 4, 4),
        previous_days=(4, 3, 3, 3),
        current_counts=(11, 3, 3, 3),
        current_days=(1, 3, 3, 3),
    )

    assert _facts(below_change, FactCategory.LISTENING_TIME_OF_DAY_EVOLUTION) == ()
    assert _facts(one_day, FactCategory.LISTENING_TIME_OF_DAY_EVOLUTION) == ()


def test_fact_family_and_candidate_order_is_permutation_independent() -> None:
    artist_a = _artist(
        ("spotify", "artist-a"), (8, 0, 0, 0), (4, 0, 0, 0), name="A"
    )
    artist_b = _artist(
        ("spotify", "artist-b"), (0, 8, 0, 0), (0, 4, 0, 0), name="B"
    )
    kwargs = {
        "previous_counts": (20, 20, 20, 20),
        "previous_days": (6, 6, 6, 6),
        "current_counts": (20, 20, 20, 20),
        "current_days": (6, 6, 6, 6),
    }
    forward = ContextualKnowledgeEngine(
        _evidence(artists=(artist_a, artist_b), **kwargs)
    ).generate_facts()
    reverse = ContextualKnowledgeEngine(
        _evidence(artists=(artist_b, artist_a), **kwargs)
    ).generate_facts()

    assert forward == reverse
    assert tuple(fact.category for fact in forward) == (
        FactCategory.ARTIST_TIME_OF_DAY_AFFINITY,
        FactCategory.ARTIST_TIME_OF_DAY_AFFINITY,
    )
