"""Narrative and presentation tests for the deterministic Over Time thread."""

from dataclasses import FrozenInstanceError

import pytest

from music_ai.knowledge import (
    FactCategory,
    FactTimeHorizon,
    ImportanceLevel,
    KnowledgeFact,
)
from music_ai.narrative import DailyNarrative, LongTermListeningThread, NarrativeEngine
from music_ai.presentation import render_daily_narrative


def _fact(
    category: FactCategory,
    description: str,
    *,
    subject: str = "listening:all_artists",
    concept: str | None = None,
    horizon: FactTimeHorizon = FactTimeHorizon.LONG_TERM,
) -> KnowledgeFact:
    resolved_concept = concept or category.value
    metadata = {"subject_key": subject}
    if resolved_concept:
        metadata["concept_key"] = resolved_concept
    return KnowledgeFact(
        category=category,
        importance=ImportanceLevel.MEDIUM,
        title=category.value,
        description=description,
        metadata=metadata,
        time_horizon=horizon,
    )


def test_long_term_thread_is_immutable_bounded_and_horizon_specific() -> None:
    first = _fact(FactCategory.ARTIST_CONSISTENCY, "Consistency")
    second = _fact(FactCategory.ARTIST_BREADTH, "Breadth")
    thread = LongTermListeningThread((first, second))

    assert thread.observations == (first, second)
    with pytest.raises(FrozenInstanceError):
        thread.observations = ()  # type: ignore[misc]
    with pytest.raises(ValueError, match="more than two"):
        LongTermListeningThread((first, second, first))
    with pytest.raises(ValueError, match="long-term horizon"):
        LongTermListeningThread(
            (
                _fact(
                    FactCategory.ARTIST_CONTINUITY,
                    "Recent",
                    horizon=FactTimeHorizon.RECENT,
                ),
            )
        )


def test_narrative_orders_limits_and_excludes_long_term_facts_from_highlights() -> None:
    consistency = _fact(FactCategory.ARTIST_CONSISTENCY, "Consistency")
    breadth = _fact(FactCategory.ARTIST_BREADTH, "Breadth")
    concentration = _fact(FactCategory.LISTENING_CONCENTRATION, "Concentration")
    daily = _fact(
        FactCategory.LISTENING_TIME_CHANGE,
        "Daily",
        horizon=FactTimeHorizon.DAILY,
    )

    narrative = NarrativeEngine(
        facts=(concentration, daily, breadth, consistency)
    ).compose()

    assert narrative.highlights == (daily,)
    assert narrative.long_term_thread == LongTermListeningThread(
        (consistency, breadth)
    )
    assert concentration not in narrative.long_term_thread.observations


def test_cross_horizon_deduplication_requires_both_subject_and_concept() -> None:
    recent = _fact(
        FactCategory.ARTIST_EMERGENCE,
        "Recent emergence",
        subject="spotify:a",
        concept="artist_emergence",
        horizon=FactTimeHorizon.RECENT,
    )
    exact_duplicate = _fact(
        FactCategory.ARTIST_CONSISTENCY,
        "Duplicate concept",
        subject="spotify:a",
        concept="artist_emergence",
    )
    different_concept = _fact(
        FactCategory.ARTIST_CONSISTENCY,
        "Long-term consistency",
        subject="spotify:a",
        concept="artist_consistency",
    )

    narrative = NarrativeEngine(
        facts=(exact_duplicate, different_concept, recent)
    ).compose()

    assert narrative.recent_thread is not None
    assert narrative.long_term_thread == LongTermListeningThread(
        (different_concept,)
    )


def test_missing_deduplication_keys_do_not_remove_observations() -> None:
    first = KnowledgeFact(
        category=FactCategory.ARTIST_CONSISTENCY,
        importance=ImportanceLevel.MEDIUM,
        title="First",
        description="First",
        metadata={"subject_key": "spotify:a"},
        time_horizon=FactTimeHorizon.LONG_TERM,
    )
    second = KnowledgeFact(
        category=FactCategory.ARTIST_BREADTH,
        importance=ImportanceLevel.MEDIUM,
        title="Second",
        description="Second",
        metadata={"concept_key": "artist_breadth"},
        time_horizon=FactTimeHorizon.LONG_TERM,
    )

    narrative = NarrativeEngine(facts=(second, first)).compose()

    assert narrative.long_term_thread == LongTermListeningThread((first, second))


def test_no_long_term_facts_preserves_compatible_default() -> None:
    assert DailyNarrative("Daily Listening", None).long_term_thread is None
    assert NarrativeEngine().compose().long_term_thread is None
    assert LongTermListeningThread().observations == ()


def test_renderer_appends_over_time_after_recently_in_narrative_order() -> None:
    recent = _fact(
        FactCategory.ARTIST_EMERGENCE,
        "Recent observation.",
        horizon=FactTimeHorizon.RECENT,
    )
    first = _fact(FactCategory.ARTIST_CONSISTENCY, "First over time.")
    second = _fact(FactCategory.ARTIST_BREADTH, "Second over time.")
    narrative = NarrativeEngine(facts=(second, recent, first)).compose()

    rendered = render_daily_narrative(narrative)

    assert "## Recently\n\n- Recent observation." in rendered
    assert "## Over Time\n\n- First over time.\n- Second over time." in rendered
    assert rendered.index("## Recently") < rendered.index("## Over Time")
    assert rendered.index("First over time.") < rendered.index("Second over time.")


def test_renderer_output_is_unchanged_without_long_term_thread() -> None:
    rendered = render_daily_narrative(DailyNarrative("Daily Listening", None))
    assert rendered == """# MusicMind Daily

## Listening Overview

Listening data is unavailable."""
