"""Narrative composition and presentation tests for Recent Listening Thread."""

from dataclasses import FrozenInstanceError

import pytest

from music_ai.knowledge import (
    FactCategory,
    FactTimeHorizon,
    ImportanceLevel,
    InsightType,
    KnowledgeFact,
)
from music_ai.narrative import (
    DailyNarrative,
    NarrativeEngine,
    RecentListeningThread,
)
from music_ai.presentation import render_daily_narrative


def _recent_fact(
    category: FactCategory,
    artist_name: str,
    *,
    importance: ImportanceLevel | None = None,
) -> KnowledgeFact:
    resolved_importance = importance or (
        ImportanceLevel.HIGH
        if category is FactCategory.ARTIST_EMERGENCE
        else ImportanceLevel.MEDIUM
    )
    action = (
        "became more prominent"
        if category is FactCategory.ARTIST_EMERGENCE
        else "led your recent listening"
    )
    return KnowledgeFact(
        category=category,
        importance=resolved_importance,
        title=category.value.replace("_", " ").title(),
        description=f"{artist_name} {action}.",
        metadata={"subject_key": f"legacy:{artist_name.casefold()}"},
        insight_type=InsightType.BEHAVIOR,
        time_horizon=FactTimeHorizon.RECENT,
    )


def _daily_fact() -> KnowledgeFact:
    return KnowledgeFact(
        category=FactCategory.LISTENING_TIME_CHANGE,
        importance=ImportanceLevel.MEDIUM,
        title="Listening Time Increased",
        description="Listening time increased compared with yesterday.",
        insight_type=InsightType.TREND,
    )


def test_recent_thread_contract_accepts_zero_one_or_two_observations() -> None:
    first = _recent_fact(FactCategory.ARTIST_EMERGENCE, "Artist A")
    second = _recent_fact(FactCategory.ARTIST_CONTINUITY, "Artist B")

    assert RecentListeningThread().observations == ()
    assert RecentListeningThread((first,)).observations == (first,)
    assert RecentListeningThread((first, second)).observations == (first, second)


def test_recent_thread_contract_is_immutable_and_rejects_invalid_contents() -> None:
    fact = _recent_fact(FactCategory.ARTIST_EMERGENCE, "Artist A")
    thread = RecentListeningThread((fact,))

    with pytest.raises(FrozenInstanceError):
        thread.observations = ()  # type: ignore[misc]
    with pytest.raises(ValueError, match="more than two"):
        RecentListeningThread((fact, fact, fact))
    with pytest.raises(ValueError, match="recent horizon"):
        RecentListeningThread((_daily_fact(),))
    with pytest.raises(ValueError, match="KnowledgeFact"):
        RecentListeningThread(("not a fact",))  # type: ignore[arg-type]


def test_narrative_omits_recent_thread_when_no_recent_fact_exists() -> None:
    daily = _daily_fact()

    narrative = NarrativeEngine(facts=(daily,)).compose()

    assert narrative.recent_thread is None
    assert narrative.highlights == (daily,)


def test_narrative_composes_one_recent_observation_separately_from_highlights() -> None:
    daily = _daily_fact()
    recent = _recent_fact(FactCategory.ARTIST_CONTINUITY, "Artist A")

    narrative = NarrativeEngine(facts=(recent, daily)).compose()

    assert narrative.recent_thread == RecentListeningThread((recent,))
    assert narrative.highlights == (daily,)


def test_narrative_orders_emergence_before_continuity_deterministically() -> None:
    continuity = _recent_fact(FactCategory.ARTIST_CONTINUITY, "Artist B")
    emergence = _recent_fact(FactCategory.ARTIST_EMERGENCE, "Artist A")

    first = NarrativeEngine(facts=(continuity, emergence)).compose()
    second = NarrativeEngine(facts=(emergence, continuity)).compose()

    expected = RecentListeningThread((emergence, continuity))
    assert first.recent_thread == expected
    assert second.recent_thread == expected


def test_narrative_deduplicates_artist_subjects_and_limits_thread_to_two() -> None:
    artist_a_continuity = _recent_fact(
        FactCategory.ARTIST_CONTINUITY, "Artist A"
    )
    artist_a_emergence = _recent_fact(
        FactCategory.ARTIST_EMERGENCE, "Artist A"
    )
    artist_b = _recent_fact(FactCategory.ARTIST_CONTINUITY, "Artist B")
    artist_c = _recent_fact(FactCategory.ARTIST_CONTINUITY, "Artist C")

    narrative = NarrativeEngine(
        facts=(
            artist_c,
            artist_a_continuity,
            artist_b,
            artist_a_emergence,
        )
    ).compose()

    assert narrative.recent_thread == RecentListeningThread(
        (artist_a_emergence, artist_b)
    )
    assert artist_a_continuity not in narrative.recent_thread.observations
    assert artist_c not in narrative.recent_thread.observations


def test_daily_narrative_addition_preserves_old_positional_construction() -> None:
    daily = _daily_fact()

    narrative = DailyNarrative(
        "Daily Listening",
        None,
        (daily,),
        {"legacy_constructor": True},
    )

    assert narrative.highlights == (daily,)
    assert narrative.metadata["legacy_constructor"] is True
    assert narrative.recent_thread is None


def test_renderer_renders_recent_observations_in_contract_order() -> None:
    continuity = _recent_fact(FactCategory.ARTIST_CONTINUITY, "Artist B")
    emergence = _recent_fact(FactCategory.ARTIST_EMERGENCE, "Artist A")
    narrative = DailyNarrative(
        headline="Daily Listening",
        listening_profile=None,
        recent_thread=RecentListeningThread((continuity, emergence)),
    )

    markdown = render_daily_narrative(narrative)

    assert markdown == """# MusicMind Daily

## Listening Overview

Listening data is unavailable.

## Recently

- Artist B led your recent listening.
- Artist A became more prominent."""
    assert markdown.index(continuity.description) < markdown.index(
        emergence.description
    )


def test_renderer_omits_recently_for_absent_or_empty_thread() -> None:
    absent = render_daily_narrative(
        DailyNarrative("Daily Listening", None)
    )
    empty = render_daily_narrative(
        DailyNarrative(
            "Daily Listening",
            None,
            recent_thread=RecentListeningThread(),
        )
    )

    expected = """# MusicMind Daily

## Listening Overview

Listening data is unavailable."""
    assert absent == expected
    assert empty == expected
    assert "## Recently" not in absent
    assert "## Recently" not in empty


def test_existing_daily_output_is_unchanged_without_recent_thread() -> None:
    daily = _daily_fact()

    markdown = render_daily_narrative(
        DailyNarrative(
            headline="Daily Listening",
            listening_profile=None,
            highlights=(daily,),
        )
    )

    assert markdown == """# MusicMind Daily

## Listening Overview

Listening data is unavailable.

## Highlights

- Listening time increased compared with yesterday."""
