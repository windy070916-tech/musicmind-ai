import pytest

from music_ai.analytics.listening_analytics import (
    ListeningSummary,
    TopArtist,
    TopSong,
)
from music_ai.knowledge import (
    FactCategory,
    FactMessageKey,
    ImportanceLevel,
    InsightType,
)
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
    assert [fact.message_key for fact in facts] == [
        FactMessageKey.DAILY_LISTENING_TIME,
        FactMessageKey.DAILY_PLAYBACK_COUNT,
        FactMessageKey.DAILY_TOP_ARTIST,
        FactMessageKey.DAILY_TOP_SONG,
    ]


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
    assert dict(facts[3].metadata) == {
        "previous_value": "Runaway",
        "current_value": "Stronger",
        "previous_artist": "Kanye West",
        "current_artist": "Kanye West",
    }
    assert all(fact.insight_type == InsightType.TREND for fact in facts)
    assert [fact.message_key for fact in facts] == [
        FactMessageKey.TREND_LISTENING_TIME_INCREASED,
        FactMessageKey.TREND_PLAYBACK_MORE,
        FactMessageKey.TREND_TOP_ARTIST_CHANGED,
        FactMessageKey.TREND_TOP_SONG_CHANGED,
    ]


def test_generate_trend_facts_requires_previous_summary() -> None:
    with pytest.raises(ValueError, match="previous_summary"):
        KnowledgeEngine(_summary(total_ms=1_000, count=1)).generate_trend_facts()


def test_same_top_song_name_with_different_artist_remains_an_eligible_change() -> None:
    facts = KnowledgeEngine(
        _summary(
            total_ms=9_000_000,
            count=28,
            song="Intro",
            song_artist="Artist B",
        ),
        _summary(
            total_ms=6_000_000,
            count=21,
            song="Intro",
            song_artist="Artist A",
        ),
    ).generate_trend_facts()
    top_song_change = next(
        fact for fact in facts if fact.category is FactCategory.TOP_SONG_CHANGE
    )

    assert top_song_change.description == (
        "Today's top song changed from Intro to Intro."
    )
    assert dict(top_song_change.metadata) == {
        "previous_value": "Intro",
        "current_value": "Intro",
        "previous_artist": "Artist A",
        "current_artist": "Artist B",
    }
    assert top_song_change.message_key is FactMessageKey.TREND_TOP_SONG_CHANGED


def test_directional_fact_branches_assign_distinct_semantic_message_keys() -> None:
    decreased = KnowledgeEngine(
        _summary(total_ms=3_000_000, count=5),
        _summary(total_ms=6_000_000, count=8),
    )
    decreased_trends = decreased.generate_trend_facts()
    assert [fact.message_key for fact in decreased_trends[:2]] == [
        FactMessageKey.TREND_LISTENING_TIME_DECREASED,
        FactMessageKey.TREND_PLAYBACK_FEWER,
    ]
    decreased_insights = decreased.generate_insight_facts()
    assert FactMessageKey.INSIGHT_LIGHT in {
        fact.message_key for fact in decreased_insights
    }

    zero_baseline = KnowledgeEngine(
        _summary(total_ms=3_000_000, count=5),
        _summary(total_ms=0, count=0),
    )
    zero_trends = zero_baseline.generate_trend_facts()
    assert [fact.message_key for fact in zero_trends[:2]] == [
        FactMessageKey.TREND_LISTENING_TIME_ZERO_BASELINE,
        FactMessageKey.TREND_PLAYBACK_MORE,
    ]
    zero_insights = zero_baseline.generate_insight_facts()
    assert FactMessageKey.INSIGHT_HEAVY_ZERO_BASELINE in {
        fact.message_key for fact in zero_insights
    }


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
    assert [fact.message_key for fact in facts] == [
        FactMessageKey.INSIGHT_FOCUSED_LISTENING,
        FactMessageKey.INSIGHT_HEAVY,
        FactMessageKey.INSIGHT_STABLE_TOP_ARTIST,
    ]
