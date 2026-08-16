"""Tests for post-selection report composition and visible semantics."""

from datetime import datetime, timezone

import pytest

from music_ai.analytics import (
    DailyListeningProfile,
    RankedArtist,
    RankedGenre,
    RankedTrack,
)
from music_ai.knowledge import (
    FactCategory,
    FactTimeHorizon,
    ImportanceLevel,
    InsightType,
    KnowledgeFact,
    knowledge_evidence_id,
)
from music_ai.narrative import (
    DailyNarrative,
    LongTermListeningThread,
    RecentListeningThread,
)
from music_ai.visible_content import (
    VisibleContentManifest,
    VisibleContentReference,
    VisibleProfileState,
    VisibleSection,
    compose_visible_report,
)


def _profile(playback_count: int = 3) -> DailyListeningProfile:
    artists = tuple(
        RankedArtist(f"artist-{index}", f"Artist {index}", 2, 60_000, 0.2)
        for index in range(1, 5)
    )
    tracks = tuple(
        RankedTrack(
            f"track-{index}",
            f"Track {index}",
            (f"Artist {index}",),
            "Album",
            None,
            1,
            60_000,
            0.1,
        )
        for index in range(1, 7)
    )
    genres = tuple(
        RankedGenre(f"genre {index}", 60_000, 0.1)
        for index in range(1, 5)
    )
    return DailyListeningProfile(
        start_datetime=datetime(2026, 8, 13, tzinfo=timezone.utc),
        end_datetime=datetime(2026, 8, 14, tzinfo=timezone.utc),
        total_estimated_listening_duration_ms=(180_000 if playback_count else 0),
        playback_count=playback_count,
        unique_track_count=3 if playback_count else 0,
        unique_track_ratio=1.0 if playback_count else 0.0,
        top_track_share=0.4 if playback_count else 0.0,
        genre_covered_duration_ms=120_000 if playback_count else 0,
        genre_coverage=2 / 3 if playback_count else 0.0,
        top_tracks=tracks if playback_count else (),
        top_artists=artists if playback_count else (),
        top_albums=(),
        top_genres=genres if playback_count else (),
    )


def _fact(
    category: FactCategory,
    *,
    horizon: FactTimeHorizon = FactTimeHorizon.DAILY,
    insight_type: InsightType = InsightType.BEHAVIOR,
    subject_key: str = "artist:one",
    concept_key: str = "artist_presence",
    direction: str = "increase",
) -> KnowledgeFact:
    return KnowledgeFact(
        category=category,
        importance=ImportanceLevel.HIGH,
        title="Canonical title",
        description="Canonical description.",
        metadata={
            "subject_key": subject_key,
            "concept_key": concept_key,
            "direction": direction,
        },
        insight_type=insight_type,
        time_horizon=horizon,
        date_range=("2026-07-15", "2026-08-14"),
    )


def test_composition_applies_final_limits_and_manifest_uses_same_selection() -> None:
    recent = _fact(
        FactCategory.ARTIST_EMERGENCE,
        horizon=FactTimeHorizon.RECENT,
    )
    long_term = _fact(
        FactCategory.ARTIST_CONSISTENCY,
        horizon=FactTimeHorizon.LONG_TERM,
        concept_key="artist_consistency",
    )
    daily_duplicate = _fact(
        FactCategory.LISTENING_TIME,
        insight_type=InsightType.DAILY_LISTENING,
    )
    highlights = tuple(
        _fact(
            FactCategory.PLAYBACK_COUNT_CHANGE,
            subject_key=f"listening:{index}",
            concept_key="playback_count_change",
        )
        for index in range(4)
    )
    composition = compose_visible_report(
        DailyNarrative(
            headline="Daily Listening",
            listening_profile=_profile(),
            highlights=(daily_duplicate, *highlights),
            recent_thread=RecentListeningThread((recent,)),
            long_term_thread=LongTermListeningThread((long_term,)),
        )
    )

    assert composition.profile_state is VisibleProfileState.ACTIVE
    assert composition.subtitle is None
    assert len(composition.top_artists) == 3
    assert len(composition.top_tracks) == 5
    assert len(composition.top_genres) == 3
    assert composition.highlights == highlights[:3]
    assert (
        knowledge_evidence_id(daily_duplicate)
        not in composition.manifest.evidence_ids
    )
    assert composition.manifest.evidence_ids == frozenset(
        knowledge_evidence_id(fact)
        for fact in (recent, long_term, *highlights[:3])
    )
    assert all(
        "Canonical description" not in reference.reference_id
        for reference in composition.manifest.references
    )


def test_manifest_covers_today_profile_rankings_and_fact_semantics() -> None:
    recent = _fact(
        FactCategory.ARTIST_EMERGENCE,
        horizon=FactTimeHorizon.RECENT,
    )
    composition = compose_visible_report(
        DailyNarrative(
            "A factual subtitle",
            _profile(),
            recent_thread=RecentListeningThread((recent,)),
        )
    )
    concepts = {reference.concept for reference in composition.manifest.references}

    assert composition.subtitle == "A factual subtitle"
    assert {
        "today_summary",
        "estimated_listening_duration",
        "playback_count",
        "distinct_tracks",
        "top_artist",
        "top_track",
        "top_genre",
        "artist_presence",
    } <= concepts
    assert composition.manifest.contains_semantic(
        concept="artist_presence",
        subject_key="artist:one",
        direction="increase",
        category=FactCategory.ARTIST_EMERGENCE,
        horizon=FactTimeHorizon.RECENT,
    )
    assert composition.manifest.contains_evidence(knowledge_evidence_id(recent))


def test_manifest_subset_matching_treats_unsupplied_dimensions_as_wildcards() -> None:
    reference = VisibleContentReference(
        "visible:semantic",
        VisibleSection.LONG_TERM,
        "artist_preference_formation",
        subject_key="artist:one",
        direction="repeated_presence",
        category="artist_continuity",
        horizon="long_term",
    )
    manifest = VisibleContentManifest((reference,))

    assert manifest.matches_semantic(
        concept="artist_preference_formation",
        subject_key="artist:one",
        direction="repeated_presence",
        horizon="long_term",
    )
    assert not manifest.matches_semantic(
        concept="artist_preference_formation",
        subject_key="artist:two",
    )


def test_missing_and_inactive_profiles_have_exact_distinct_manifest_states() -> None:
    missing = compose_visible_report(DailyNarrative("Daily Listening", None))
    inactive = compose_visible_report(
        DailyNarrative("Daily Listening", _profile(playback_count=0))
    )

    assert missing.profile_state is VisibleProfileState.UNAVAILABLE
    assert inactive.profile_state is VisibleProfileState.NO_ACTIVITY
    assert {item.concept for item in missing.manifest.references} == {
        "today_summary",
        "listening_unavailable",
    }
    assert {item.concept for item in inactive.manifest.references} == {
        "today_summary",
        "no_listening_activity",
    }


def test_manifest_validates_semantic_references_and_unique_identifiers() -> None:
    reference = VisibleContentReference(
        reference_id="visible:test",
        section=VisibleSection.HIGHLIGHTS,
        concept="artist_breadth",
    )

    with pytest.raises(ValueError, match="unique"):
        VisibleContentManifest((reference, reference))
    with pytest.raises(ValueError, match="multiline"):
        VisibleContentReference(
            reference_id="visible:bad",
            section=VisibleSection.HIGHLIGHTS,
            concept="rendered\nMarkdown",
        )
