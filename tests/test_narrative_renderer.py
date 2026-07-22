"""Tests for deterministic DailyNarrative Markdown presentation."""

from datetime import datetime, timezone

from music_ai.analytics import (
    DailyListeningProfile,
    RankedArtist,
    RankedGenre,
    RankedTrack,
)
from music_ai.knowledge import (
    FactCategory,
    ImportanceLevel,
    InsightType,
    KnowledgeFact,
)
from music_ai.narrative import DailyNarrative
from music_ai.presentation import render_daily_narrative


def _fact(
    category: FactCategory,
    description: str,
    insight_type: InsightType,
) -> KnowledgeFact:
    return KnowledgeFact(
        category=category,
        importance=ImportanceLevel.HIGH,
        title=category.value,
        description=description,
        insight_type=insight_type,
    )


def _profile(
    *,
    playback_count: int = 2,
    artists: tuple[RankedArtist, ...] = (),
    tracks: tuple[RankedTrack, ...] = (),
    genres: tuple[RankedGenre, ...] = (),
) -> DailyListeningProfile:
    return DailyListeningProfile(
        start_datetime=datetime(2026, 7, 21, tzinfo=timezone.utc),
        end_datetime=datetime(2026, 7, 22, tzinfo=timezone.utc),
        total_estimated_listening_duration_ms=9_060_000 if playback_count else 0,
        playback_count=playback_count,
        unique_track_count=1 if playback_count else 0,
        unique_track_ratio=0.5 if playback_count else 0.0,
        top_track_share=0.6 if tracks else 0.0,
        genre_covered_duration_ms=4_530_000 if genres else 0,
        genre_coverage=0.5 if genres else 0.0,
        top_tracks=tracks,
        top_artists=artists,
        top_albums=(),
        top_genres=genres,
    )


def test_populated_narrative_has_stable_exact_markdown() -> None:
    narrative = DailyNarrative(
        headline="Daily Listening",
        listening_profile=_profile(
            playback_count=2,
            artists=(
                RankedArtist("artist-1", "Artist One", 2, 4_530_000, 0.5),
            ),
            tracks=(
                RankedTrack(
                    "track-1",
                    "Track One",
                    ("Artist One", "Artist Two"),
                    "Album",
                    "album-1",
                    1,
                    3_600_000,
                    0.4,
                ),
            ),
            genres=(RankedGenre("hip hop", 4_530_000, 0.5),),
        ),
        highlights=(
            _fact(
                FactCategory.LISTENING_TIME_CHANGE,
                "Listening time increased by 20% compared with yesterday.",
                InsightType.TREND,
            ),
        ),
        metadata={"must_not_render": "hidden"},
    )

    markdown = render_daily_narrative(narrative)

    assert markdown == """# MusicMind Daily

## Listening Overview

- Estimated listening duration: 2h 31m
- Playback count: 2 plays
- Unique tracks: 1 track

## Top Artists

1. Artist One — estimated 1h 15m · 2 plays · 50%

## Top Tracks

1. Track One — Artist One, Artist Two — estimated 1h · 1 play · 40%

## Genre Overview

1. hip hop — estimated 1h 15m · 50%

## Highlights

- Listening time increased by 20% compared with yesterday."""
    assert "must_not_render" not in markdown


def test_missing_and_zero_playback_profiles_render_required_empty_states() -> None:
    missing = render_daily_narrative(
        DailyNarrative("Daily Listening", None)
    )
    empty = render_daily_narrative(
        DailyNarrative("Daily Listening", _profile(playback_count=0))
    )

    assert missing == """# MusicMind Daily

## Listening Overview

Listening data is unavailable."""
    assert empty == """# MusicMind Daily

## Listening Overview

No listening activity was recorded today."""
    assert "## Top Artists" not in empty
    assert "## Top Tracks" not in empty
    assert "## Genre Overview" not in empty


def test_renderer_applies_limits_without_reranking_and_filters_daily_facts() -> None:
    artists = tuple(
        RankedArtist(f"artist-{index}", f"Artist {index}", index, 60_000, 0.1)
        for index in range(1, 5)
    )
    tracks = tuple(
        RankedTrack(
            f"track-{index}",
            f"Track {index}",
            (f"Artist {index}",),
            "Album",
            None,
            index,
            60_000,
            0.1,
        )
        for index in range(1, 7)
    )
    genres = tuple(
        RankedGenre(f"genre {index}", 60_000, 0.1) for index in range(1, 5)
    )
    daily = _fact(
        FactCategory.LISTENING_TIME,
        "Duplicate daily listening time.",
        InsightType.DAILY_LISTENING,
    )
    highlights = tuple(
        _fact(
            FactCategory.LISTENING_TIME_CHANGE,
            f"Eligible highlight {index}.",
            InsightType.TREND,
        )
        for index in range(1, 5)
    )

    markdown = render_daily_narrative(
        DailyNarrative(
            "Daily Listening",
            _profile(artists=artists, tracks=tracks, genres=genres),
            (daily, *highlights),
        )
    )
    artist_section = markdown.split("## Top Artists\n\n", 1)[1].split("\n\n##", 1)[0]

    assert "Artist 1" in markdown and "Artist 3" in markdown
    assert "4. Artist 4" not in artist_section
    assert "Track 1" in markdown and "Track 5" in markdown
    assert "Track 6" not in markdown
    assert "genre 1" in markdown and "genre 3" in markdown
    assert "genre 4" not in markdown
    assert "Eligible highlight 1." in markdown
    assert "Eligible highlight 3." in markdown
    assert "Eligible highlight 4." not in markdown
    assert "Duplicate daily listening time." not in markdown


def test_partial_narrative_omits_empty_sections_and_preserves_inputs() -> None:
    unknown_track = RankedTrack(
        "track-1",
        "Unknown Track",
        (),
        "Unknown album",
        None,
        1,
        60_000,
        1.0,
    )
    profile = _profile(playback_count=1, tracks=(unknown_track,))
    fact = _fact(
        FactCategory.PLAYBACK_COUNT_CHANGE,
        "You played one more track than yesterday.",
        InsightType.TREND,
    )
    narrative = DailyNarrative("A factual day", profile, (fact,))
    original_tracks = profile.top_tracks
    original_highlights = narrative.highlights

    markdown = render_daily_narrative(narrative)

    assert "A factual day" in markdown
    assert "Unknown Track — Unknown artist" in markdown
    assert "- Playback count: 1 play" in markdown
    assert "## Top Artists" not in markdown
    assert "## Genre Overview" not in markdown
    assert profile.top_tracks == original_tracks
    assert narrative.highlights == original_highlights
