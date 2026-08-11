"""Narrative and presentation tests for the deterministic Over Time thread."""

from dataclasses import FrozenInstanceError
from itertools import permutations

import pytest

from music_ai.knowledge import (
    FactCategory,
    FactTimeHorizon,
    ImportanceLevel,
    KnowledgeFact,
)
from music_ai.narrative import (
    DailyNarrative,
    LongTermListeningThread,
    NarrativeEngine,
    RecentListeningThread,
)
from music_ai.presentation import render_daily_narrative


def _fact(
    category: FactCategory,
    description: str,
    *,
    subject: str | None = "listening:all_artists",
    concept: str | None = None,
    horizon: FactTimeHorizon = FactTimeHorizon.LONG_TERM,
    importance: ImportanceLevel = ImportanceLevel.MEDIUM,
    direction: object | None = None,
) -> KnowledgeFact:
    resolved_concept = concept or category.value
    metadata: dict[str, object] = {}
    if subject is not None:
        metadata["subject_key"] = subject
    if resolved_concept:
        metadata["concept_key"] = resolved_concept
    if direction is not None:
        metadata["direction"] = direction
    return KnowledgeFact(
        category=category,
        importance=importance,
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


def test_evolution_priority_applies_before_importance_and_two_item_limit() -> None:
    artist_share = _fact(
        FactCategory.ARTIST_DURATION_SHARE_EVOLUTION,
        "Artist share evolution",
        subject="spotify:a",
        concept="artist_duration_share",
        importance=ImportanceLevel.LOW,
        direction="increase",
    )
    breadth = _fact(
        FactCategory.ARTIST_BREADTH_EVOLUTION,
        "Breadth evolution",
        concept="artist_breadth",
        importance=ImportanceLevel.HIGH,
        direction="increase",
    )
    concentration = _fact(
        FactCategory.LISTENING_CONCENTRATION_EVOLUTION,
        "Concentration evolution",
        concept="listening_concentration",
        importance=ImportanceLevel.HIGH,
        direction="increase",
    )

    narrative = NarrativeEngine(
        facts=(concentration, breadth, artist_share)
    ).compose()

    assert narrative.long_term_thread == LongTermListeningThread(
        (artist_share, breadth)
    )
    assert concentration not in narrative.long_term_thread.observations


@pytest.mark.parametrize(
    ("evolution_category", "state_category", "concept"),
    [
        (
            FactCategory.ARTIST_BREADTH_EVOLUTION,
            FactCategory.ARTIST_BREADTH,
            "artist_breadth",
        ),
        (
            FactCategory.LISTENING_CONCENTRATION_EVOLUTION,
            FactCategory.LISTENING_CONCENTRATION,
            "listening_concentration",
        ),
    ],
)
def test_evolution_suppresses_only_matching_long_term_state_before_limit(
    evolution_category: FactCategory,
    state_category: FactCategory,
    concept: str,
) -> None:
    evolution = _fact(
        evolution_category,
        "Evolution",
        concept=concept,
        direction="increase",
    )
    matching_state = _fact(state_category, "Matching state", concept=concept)
    different_subject_state = _fact(
        state_category,
        "Different subject state",
        subject="listening:other_artists",
        concept=concept,
    )

    narrative = NarrativeEngine(
        facts=(matching_state, different_subject_state, evolution)
    ).compose()

    assert narrative.long_term_thread == LongTermListeningThread(
        (evolution, different_subject_state)
    )
    assert matching_state not in narrative.long_term_thread.observations


def test_artist_share_evolution_does_not_suppress_artist_consistency() -> None:
    artist_share = _fact(
        FactCategory.ARTIST_DURATION_SHARE_EVOLUTION,
        "Artist share evolution",
        subject="spotify:a",
        concept="artist_duration_share",
        direction="increase",
    )
    consistency = _fact(
        FactCategory.ARTIST_CONSISTENCY,
        "Artist consistency",
        subject="spotify:a",
        concept="artist_consistency",
    )

    narrative = NarrativeEngine(facts=(consistency, artist_share)).compose()

    assert narrative.long_term_thread == LongTermListeningThread(
        (artist_share, consistency)
    )


def test_state_suppression_with_missing_identity_is_conservative() -> None:
    incomplete_evolution = _fact(
        FactCategory.ARTIST_BREADTH_EVOLUTION,
        "Incomplete breadth evolution",
        subject=None,
        concept="artist_breadth",
        direction="increase",
    )
    state = _fact(
        FactCategory.ARTIST_BREADTH,
        "Breadth state",
        concept="artist_breadth",
    )

    narrative = NarrativeEngine(facts=(state, incomplete_evolution)).compose()

    assert narrative.long_term_thread == LongTermListeningThread(
        (incomplete_evolution, state)
    )


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


@pytest.mark.parametrize(
    ("direction", "long_term_subject", "is_retained"),
    [
        ("increase", "spotify:a", False),
        ("decrease", "spotify:a", True),
        ("sideways", "spotify:a", True),
        (None, "spotify:a", True),
        ("increase", "spotify:b", True),
        ("increase", None, True),
    ],
)
def test_recent_emergence_deduplicates_only_same_subject_share_increase(
    direction: object | None,
    long_term_subject: str | None,
    is_retained: bool,
) -> None:
    recent = _fact(
        FactCategory.ARTIST_EMERGENCE,
        "Recent emergence",
        subject="spotify:a",
        concept="artist_emergence",
        horizon=FactTimeHorizon.RECENT,
    )
    artist_share = _fact(
        FactCategory.ARTIST_DURATION_SHARE_EVOLUTION,
        "Artist share evolution",
        subject=long_term_subject,
        concept="artist_duration_share",
        direction=direction,
    )

    narrative = NarrativeEngine(facts=(artist_share, recent)).compose()

    assert narrative.recent_thread == RecentListeningThread((recent,))
    if is_retained:
        assert narrative.long_term_thread == LongTermListeningThread(
            (artist_share,)
        )
    else:
        assert narrative.long_term_thread is None


def test_recent_emergence_retains_unrelated_same_artist_long_term_fact() -> None:
    recent = _fact(
        FactCategory.ARTIST_EMERGENCE,
        "Recent emergence",
        subject="spotify:a",
        concept="artist_emergence",
        horizon=FactTimeHorizon.RECENT,
    )
    consistency = _fact(
        FactCategory.ARTIST_CONSISTENCY,
        "Artist consistency",
        subject="spotify:a",
        concept="artist_consistency",
    )

    narrative = NarrativeEngine(facts=(consistency, recent)).compose()

    assert narrative.long_term_thread == LongTermListeningThread((consistency,))


def test_long_term_order_is_independent_of_input_order_and_uses_subject_key() -> None:
    first = _fact(
        FactCategory.ARTIST_CONSISTENCY,
        "Second lexical description",
        subject="spotify:a",
        concept="artist_consistency",
    )
    second = _fact(
        FactCategory.ARTIST_CONSISTENCY,
        "First lexical description",
        subject="spotify:b",
        concept="artist_consistency",
    )
    third = _fact(
        FactCategory.ARTIST_CONSISTENCY,
        "Third description",
        subject="spotify:c",
        concept="artist_consistency",
    )

    for ordered_facts in permutations((first, second, third)):
        narrative = NarrativeEngine(facts=ordered_facts).compose()
        assert narrative.long_term_thread == LongTermListeningThread(
            (first, second)
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
