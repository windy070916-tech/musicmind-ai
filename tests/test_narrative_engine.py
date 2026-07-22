"""Unit tests for the presentation-independent Narrative foundation."""

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from music_ai.analytics import DailyListeningProfile
from music_ai.knowledge import (
    FactCategory,
    ImportanceLevel,
    InsightType,
    KnowledgeFact,
)
from music_ai.narrative import DailyNarrative, NarrativeEngine


def _profile() -> DailyListeningProfile:
    return DailyListeningProfile(
        start_datetime=datetime(2026, 7, 21, tzinfo=timezone.utc),
        end_datetime=datetime(2026, 7, 22, tzinfo=timezone.utc),
        total_estimated_listening_duration_ms=180_000,
        playback_count=1,
        unique_track_count=1,
        unique_track_ratio=1.0,
        top_track_share=1.0,
        genre_covered_duration_ms=0,
        genre_coverage=0.0,
        top_tracks=(),
        top_artists=(),
        top_albums=(),
        top_genres=(),
    )


def _fact(
    category: FactCategory,
    title: str,
    importance: ImportanceLevel,
) -> KnowledgeFact:
    return KnowledgeFact(
        category=category,
        importance=importance,
        title=title,
        description=f"{title} description.",
        insight_type=InsightType.DAILY_LISTENING,
    )


def test_daily_narrative_creation_preserves_structured_inputs() -> None:
    profile = _profile()
    fact = _fact(FactCategory.TOP_ARTIST, "Top Artist", ImportanceLevel.HIGH)

    narrative = DailyNarrative(
        headline="Daily Listening",
        listening_profile=profile,
        highlights=(fact,),
        metadata={"context": "daily"},
    )

    assert narrative.listening_profile is profile
    assert narrative.highlights == (fact,)
    assert narrative.metadata["context"] == "daily"


def test_daily_narrative_is_immutable() -> None:
    narrative = DailyNarrative(
        headline="Daily Listening",
        listening_profile=None,
        highlights=(),
        metadata={"context": "daily"},
    )

    with pytest.raises(FrozenInstanceError):
        narrative.headline = "Changed"  # type: ignore[misc]
    with pytest.raises(TypeError):
        narrative.metadata["context"] = "changed"  # type: ignore[index]


def test_narrative_engine_composes_profile_and_facts() -> None:
    profile = _profile()
    fact = _fact(FactCategory.PLAYBACK_COUNT, "Playback Count", ImportanceLevel.MEDIUM)

    narrative = NarrativeEngine(profile, [fact]).compose()

    assert narrative.headline == "Daily Listening"
    assert narrative.listening_profile is profile
    assert narrative.highlights == (fact,)
    assert narrative.metadata == {}


def test_narrative_composition_is_deterministic_and_does_not_mutate_inputs() -> None:
    low = _fact(FactCategory.LISTENING_TIME, "Listening Time", ImportanceLevel.LOW)
    high = _fact(FactCategory.TOP_SONG, "Top Song", ImportanceLevel.HIGH)
    facts = [low, high]
    engine = NarrativeEngine(_profile(), facts)
    facts.reverse()

    first = engine.compose()
    second = NarrativeEngine(_profile(), [high, low]).compose()

    assert first.highlights == (high, low)
    assert second.highlights == first.highlights


def test_narrative_composition_uses_stable_fact_attributes_to_break_priority_ties() -> None:
    playback = _fact(
        FactCategory.PLAYBACK_COUNT,
        "Playback Count",
        ImportanceLevel.MEDIUM,
    )
    listening = _fact(
        FactCategory.LISTENING_TIME,
        "Listening Time",
        ImportanceLevel.MEDIUM,
    )

    first = NarrativeEngine(facts=[playback, listening]).compose()
    second = NarrativeEngine(facts=[listening, playback]).compose()

    assert first.highlights == (listening, playback)
    assert second.highlights == first.highlights


def test_narrative_engine_handles_empty_inputs() -> None:
    narrative = NarrativeEngine().compose()

    assert narrative == DailyNarrative(
        headline="Daily Listening",
        listening_profile=None,
        highlights=(),
        metadata={},
    )
