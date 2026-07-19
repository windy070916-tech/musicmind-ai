import pytest

from music_ai.analytics.listening_analytics import (
    ListeningSummary,
    TopArtist,
    TopSong,
)
from music_ai.knowledge import FactCategory, ImportanceLevel, InsightType
from music_ai.knowledge.knowledge_engine import KnowledgeEngine


def _summary(
    *,
    total_ms: int,
    count: int,
    artist: str = "Kanye West",
    artist_ms: int | None = None,
    song: str = "Stronger",
    song_artist: str = "Kanye West",
    song_ms: int | None = None,
) -> ListeningSummary:
    return ListeningSummary(
        total_listening_time_ms=total_ms,
        playback_count=count,
        top_artists=(
            TopArtist(name=artist, listening_time_ms=artist_ms or total_ms),
        ),
        top_songs=(
            TopSong(
                name=song,
                artist=song_artist,
                listening_time_ms=song_ms or total_ms,
            ),
        ),
    )


def test_generate_daily_facts_returns_structured_facts() -> None:
    facts = KnowledgeEngine(
        _summary(total_ms=9_060_000, count=28)
    ).generate_daily_facts()

    assert [fact.category for fact in facts] == [
        FactCategory.LISTENING_TIME,
        FactCategory.PLAYBACK_COUNT,
        FactCategory.TOP_ARTIST,
        FactCategory.TOP_SONG,
    ]
    assert facts[0].description == "You listened to music for 2 hours and 31 minutes today."
    assert facts[0].importance == ImportanceLevel.MEDIUM
    assert facts[0].insight_type == InsightType.DAILY_LISTENING
    assert facts[1].description == "You played 28 tracks today."
    assert facts[2].description == "Today's top artist is Kanye West."
    assert facts[3].description == "Today's top song is Stronger."


def test_generate_trend_facts_compares_two_summaries() -> None:
    facts = KnowledgeEngine(
        _summary(total_ms=9_000_000, count=28, artist="Kanye West", song="Stronger"),
        _summary(
            total_ms=6_000_000,
            count=21,
            artist="Kendrick Lamar",
            song="Runaway",
        ),
    ).generate_trend_facts()

    assert [fact.category for fact in facts] == [
        FactCategory.LISTENING_TIME_CHANGE,
        FactCategory.PLAYBACK_COUNT_CHANGE,
        FactCategory.TOP_ARTIST_CHANGE,
        FactCategory.TOP_SONG_CHANGE,
    ]
    assert facts[0].description == "Listening time increased by 50% compared with yesterday."
    assert facts[0].metadata["percentage_change"] == 50
    assert facts[1].description == "You played 7 more tracks than yesterday."
    assert facts[2].description == (
        "Today's top artist changed from Kendrick Lamar to Kanye West."
    )
    assert facts[3].description == "Today's top song changed from Runaway to Stronger."
    assert all(fact.insight_type == InsightType.TREND for fact in facts)


def test_generate_trend_facts_requires_previous_summary() -> None:
    with pytest.raises(ValueError, match="previous_summary"):
        KnowledgeEngine(_summary(total_ms=1_000, count=1)).generate_trend_facts()


def test_generate_insight_facts_identifies_behavioral_patterns() -> None:
    facts = KnowledgeEngine(
        _summary(total_ms=8_000_000, count=12, artist_ms=6_000_000),
        _summary(total_ms=4_000_000, count=10, artist="Kanye West"),
    ).generate_insight_facts()

    assert [fact.category for fact in facts] == [
        FactCategory.FOCUSED_LISTENING,
        FactCategory.HEAVY_LISTENING,
        FactCategory.STABLE_FAVORITE,
    ]
    assert facts[0].description == (
        "Most of today's listening time (75%) came from Kanye West."
    )
    assert facts[0].metadata["listening_share"] == 0.75
    assert facts[1].description == "Your listening time was 100% higher than yesterday."
    assert facts[2].description == "Kanye West remained your top artist today."
