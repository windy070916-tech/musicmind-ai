"""Knowledge interpretation tests for long-term listening evolution."""

from datetime import date, datetime, timezone
from fractions import Fraction
import inspect

import pytest

from music_ai.knowledge import (
    FactCategory,
    FactMessageKey,
    FactSource,
    FactTimeHorizon,
    ImportanceLevel,
    InsightType,
    LongTermEvolutionKnowledgeEngine,
)
from music_ai.knowledge import long_term_evolution_knowledge_engine as engine_module
from music_ai.temporal import (
    ArtistBreadthEvolutionEvidence,
    ArtistShareEvolutionCandidate,
    ConcentrationEvolutionEvidence,
    EvolutionWindowEvidence,
    LongTermEvolutionEvidence,
)


_PREVIOUS_START = date(2026, 6, 7)
_PREVIOUS_END = date(2026, 7, 7)
_CURRENT_START = _PREVIOUS_END
_CURRENT_END = date(2026, 8, 6)
_AS_OF = datetime(2026, 8, 6, 12, tzinfo=timezone.utc)


def _window(
    start_date: date,
    end_date: date,
    *,
    attributed_duration_ms: int = 1_000,
    listening_day_count: int = 10,
    closed_listening_day_count: int = 7,
) -> EvolutionWindowEvidence:
    return EvolutionWindowEvidence(
        start_date=start_date,
        end_date=end_date,
        recorded_day_count=30,
        listening_day_count=listening_day_count,
        closed_day_count=30,
        closed_listening_day_count=closed_listening_day_count,
        gap_dates=(),
        contains_open_snapshot=False,
        total_estimated_listening_duration_ms=max(1_000, attributed_duration_ms),
        total_attributed_artist_duration_ms=attributed_duration_ms,
        structurally_sufficient=(
            listening_day_count >= 10 and closed_listening_day_count >= 7
        ),
    )


def _candidate(
    *,
    identity: tuple[str, str] = ("spotify", "artist-a"),
    artist_name: str = "Artist A",
    previous_duration_ms: int = 200,
    current_duration_ms: int = 350,
    previous_total_ms: int = 1_000,
    current_total_ms: int = 1_000,
) -> ArtistShareEvolutionCandidate:
    previous_share = (
        previous_duration_ms / previous_total_ms if previous_total_ms else None
    )
    current_share = current_duration_ms / current_total_ms if current_total_ms else None
    signed_change = (
        current_share - previous_share
        if previous_share is not None and current_share is not None
        else None
    )
    return ArtistShareEvolutionCandidate(
        identity=identity,
        spotify_artist_id=identity[1] if identity[0] == "spotify" else None,
        artist_name=artist_name,
        previous_duration_ms=previous_duration_ms,
        current_duration_ms=current_duration_ms,
        previous_attributed_duration_ms=previous_total_ms,
        current_attributed_duration_ms=current_total_ms,
        previous_share=previous_share,
        current_share=current_share,
        signed_share_change=signed_change,
        absolute_share_change=(abs(signed_change) if signed_change is not None else None),
    )


def _concentration(
    *,
    previous_top_five_ms: int = 500,
    current_top_five_ms: int = 650,
    previous_total_ms: int = 1_000,
    current_total_ms: int = 1_000,
) -> ConcentrationEvolutionEvidence:
    previous_share = (
        previous_top_five_ms / previous_total_ms if previous_total_ms else None
    )
    current_share = current_top_five_ms / current_total_ms if current_total_ms else None
    signed_change = (
        current_share - previous_share
        if previous_share is not None and current_share is not None
        else None
    )
    return ConcentrationEvolutionEvidence(
        previous_top_five_duration_ms=previous_top_five_ms,
        current_top_five_duration_ms=current_top_five_ms,
        previous_attributed_duration_ms=previous_total_ms,
        current_attributed_duration_ms=current_total_ms,
        previous_share=previous_share,
        current_share=current_share,
        signed_share_change=signed_change,
        absolute_share_change=(abs(signed_change) if signed_change is not None else None),
        is_calculable=previous_total_ms > 0 and current_total_ms > 0,
    )


def _breadth(
    *,
    previous_artist_days: int = 20,
    current_artist_days: int = 25,
    previous_listening_days: int = 10,
    current_listening_days: int = 10,
) -> ArtistBreadthEvolutionEvidence:
    previous_value = (
        previous_artist_days / previous_listening_days
        if previous_listening_days
        else None
    )
    current_value = (
        current_artist_days / current_listening_days
        if current_listening_days
        else None
    )
    signed_change = (
        current_value - previous_value
        if previous_value is not None and current_value is not None
        else None
    )
    relative_change = (
        signed_change / previous_value
        if signed_change is not None and previous_value
        else None
    )
    calculable = (
        previous_value is not None
        and current_value is not None
        and previous_value > 0
    )
    return ArtistBreadthEvolutionEvidence(
        previous_artist_day_count=previous_artist_days,
        current_artist_day_count=current_artist_days,
        previous_listening_day_count=previous_listening_days,
        current_listening_day_count=current_listening_days,
        previous_artists_per_listening_day=previous_value,
        current_artists_per_listening_day=current_value,
        signed_change=signed_change,
        absolute_change=(abs(signed_change) if signed_change is not None else None),
        relative_change=relative_change,
        absolute_relative_change=(
            abs(relative_change) if relative_change is not None else None
        ),
        is_calculable=calculable,
    )


def _evidence(
    *,
    candidates: tuple[ArtistShareEvolutionCandidate, ...] | None = None,
    concentration: ConcentrationEvolutionEvidence | None = None,
    breadth: ArtistBreadthEvolutionEvidence | None = None,
    comparison_sufficient: bool = True,
    previous_total_ms: int = 1_000,
    current_total_ms: int = 1_000,
) -> LongTermEvolutionEvidence:
    previous_listening_days = 10 if comparison_sufficient else 9
    resolved_breadth = breadth or _breadth(
        previous_listening_days=previous_listening_days
    )
    return LongTermEvolutionEvidence(
        timezone_name="UTC",
        as_of=_AS_OF,
        previous_window=_window(
            _PREVIOUS_START,
            _PREVIOUS_END,
            attributed_duration_ms=previous_total_ms,
            listening_day_count=resolved_breadth.previous_listening_day_count,
        ),
        current_window=_window(
            _CURRENT_START,
            _CURRENT_END,
            attributed_duration_ms=current_total_ms,
            listening_day_count=resolved_breadth.current_listening_day_count,
        ),
        comparison_evidence_sufficient=comparison_sufficient,
        artist_share_calculable=previous_total_ms > 0 and current_total_ms > 0,
        artist_share_candidates=(
            candidates if candidates is not None else (_candidate(),)
        ),
        concentration=concentration or _concentration(),
        breadth=resolved_breadth,
    )


def test_all_three_concepts_emit_in_fixed_order_with_exact_contracts() -> None:
    facts = LongTermEvolutionKnowledgeEngine(_evidence()).generate_facts()

    assert tuple(fact.category for fact in facts) == (
        FactCategory.ARTIST_DURATION_SHARE_EVOLUTION,
        FactCategory.ARTIST_BREADTH_EVOLUTION,
        FactCategory.LISTENING_CONCENTRATION_EVOLUTION,
    )
    assert tuple(fact.importance for fact in facts) == (
        ImportanceLevel.HIGH,
        ImportanceLevel.MEDIUM,
        ImportanceLevel.MEDIUM,
    )
    assert all(fact.source is FactSource.LONG_TERM_EVOLUTION_EVIDENCE for fact in facts)
    assert all(fact.time_horizon is FactTimeHorizon.LONG_TERM for fact in facts)
    assert all(fact.insight_type is InsightType.BEHAVIOR for fact in facts)
    assert all(fact.date_range == ("2026-06-07", "2026-08-06") for fact in facts)
    assert tuple(fact.message_key for fact in facts) == (
        FactMessageKey.LONG_TERM_ARTIST_SHARE_EVOLUTION_INCREASED,
        FactMessageKey.LONG_TERM_ARTIST_BREADTH_EVOLUTION_INCREASED,
        FactMessageKey.LONG_TERM_LISTENING_CONCENTRATION_EVOLUTION_INCREASED,
    )
    assert tuple(fact.title for fact in facts) == (
        "Artist share increased",
        "Artist breadth increased",
        "Listening concentration increased",
    )
    assert facts[0].description == (
        "The share of attributable artist listening for Artist A increased from "
        "20% in the previous 30-day period to 35% in the current 30-day period."
    )
    assert facts[1].description == (
        "Artists per listening day increased from 2.0 in the previous 30-day "
        "period to 2.5 in the current 30-day period."
    )
    assert facts[2].description == (
        "The top five artists' share of attributable artist listening increased "
        "from 50% in the previous 30-day period to 65% in the current 30-day period."
    )


def test_decrease_branches_use_direction_specific_titles_and_message_keys() -> None:
    facts = LongTermEvolutionKnowledgeEngine(
        _evidence(
            candidates=(_candidate(previous_duration_ms=350, current_duration_ms=200),),
            concentration=_concentration(
                previous_top_five_ms=650,
                current_top_five_ms=500,
            ),
            breadth=_breadth(previous_artist_days=25, current_artist_days=20),
        )
    ).generate_facts()

    assert tuple(fact.metadata["direction"] for fact in facts) == (
        "decrease",
        "decrease",
        "decrease",
    )
    assert tuple(fact.message_key for fact in facts) == (
        FactMessageKey.LONG_TERM_ARTIST_SHARE_EVOLUTION_DECREASED,
        FactMessageKey.LONG_TERM_ARTIST_BREADTH_EVOLUTION_DECREASED,
        FactMessageKey.LONG_TERM_LISTENING_CONCENTRATION_EVOLUTION_DECREASED,
    )
    assert all("decreased" in fact.description for fact in facts)


def test_structural_insufficiency_and_nonqualifying_concepts_are_silent() -> None:
    assert LongTermEvolutionKnowledgeEngine(
        _evidence(comparison_sufficient=False)
    ).generate_facts() == ()

    evidence = _evidence(
        candidates=(_candidate(current_duration_ms=349),),
        concentration=_concentration(current_top_five_ms=649),
        breadth=_breadth(current_artist_days=24),
    )
    assert LongTermEvolutionKnowledgeEngine(evidence).generate_facts() == ()


@pytest.mark.parametrize(
    "candidate",
    (
        _candidate(previous_duration_ms=200, current_duration_ms=350),
        _candidate(previous_duration_ms=200, current_duration_ms=50),
    ),
    ids=("increase", "decrease"),
)
def test_artist_share_exact_15_point_and_20_percent_boundaries_qualify(
    candidate: ArtistShareEvolutionCandidate,
) -> None:
    facts = LongTermEvolutionKnowledgeEngine(
        _evidence(
            candidates=(candidate,),
            concentration=_concentration(current_top_five_ms=500),
            breadth=_breadth(current_artist_days=20),
        )
    ).generate_facts()
    assert len(facts) == 1
    assert facts[0].category is FactCategory.ARTIST_DURATION_SHARE_EVOLUTION


@pytest.mark.parametrize(
    "candidate",
    (
        _candidate(previous_duration_ms=200, current_duration_ms=349),
        _candidate(previous_duration_ms=199, current_duration_ms=49),
    ),
    ids=("below-change", "below-max-window-share"),
)
def test_artist_share_requires_both_thresholds(
    candidate: ArtistShareEvolutionCandidate,
) -> None:
    facts = LongTermEvolutionKnowledgeEngine(
        _evidence(
            candidates=(candidate,),
            concentration=_concentration(current_top_five_ms=500),
            breadth=_breadth(current_artist_days=20),
        )
    ).generate_facts()
    assert facts == ()


def test_artist_selection_filters_before_ranking_and_breaks_exact_ties_by_identity() -> None:
    larger_unqualified = _candidate(
        identity=("spotify", "artist-a"),
        artist_name="Unqualified",
        previous_duration_ms=190,
        current_duration_ms=0,
    )
    tie_a = _candidate(
        identity=("legacy", "artist a"),
        artist_name="Tie A",
        previous_duration_ms=200,
        current_duration_ms=350,
    )
    tie_b = _candidate(
        identity=("spotify", "artist-b"),
        artist_name="Tie B",
        previous_duration_ms=350,
        current_duration_ms=200,
    )
    candidates = tuple(sorted((larger_unqualified, tie_a, tie_b), key=lambda item: item.identity))
    facts = LongTermEvolutionKnowledgeEngine(
        _evidence(
            candidates=candidates,
            concentration=_concentration(current_top_five_ms=500),
            breadth=_breadth(current_artist_days=20),
        )
    ).generate_facts()

    assert len(facts) == 1
    assert facts[0].metadata["artist_name"] == "Tie A"
    assert facts[0].metadata["subject_key"] == "legacy:artist a"


def test_artist_selection_chooses_the_greatest_qualifying_exact_change() -> None:
    weaker = _candidate(
        identity=("spotify", "artist-a"),
        artist_name="Weaker",
        previous_duration_ms=200,
        current_duration_ms=350,
    )
    stronger = _candidate(
        identity=("spotify", "artist-b"),
        artist_name="Stronger",
        previous_duration_ms=200,
        current_duration_ms=400,
    )
    facts = LongTermEvolutionKnowledgeEngine(
        _evidence(
            candidates=(weaker, stronger),
            concentration=_concentration(current_top_five_ms=500),
            breadth=_breadth(current_artist_days=20),
        )
    ).generate_facts()

    assert len(facts) == 1
    assert facts[0].metadata["artist_name"] == "Stronger"
    assert facts[0].metadata["absolute_share_change"] == pytest.approx(0.2)


def test_exact_rational_evidence_not_binary_float_decides_thresholds() -> None:
    candidate = _candidate(
        previous_duration_ms=20,
        current_duration_ms=29,
        previous_total_ms=60,
        current_total_ms=60,
    )
    facts = LongTermEvolutionKnowledgeEngine(
        _evidence(
            candidates=(candidate,),
            concentration=_concentration(
                previous_top_five_ms=20,
                current_top_five_ms=29,
                previous_total_ms=60,
                current_total_ms=60,
            ),
            breadth=_breadth(current_artist_days=20),
            previous_total_ms=60,
            current_total_ms=60,
        )
    ).generate_facts()

    assert tuple(fact.category for fact in facts) == (
        FactCategory.ARTIST_DURATION_SHARE_EVOLUTION,
        FactCategory.LISTENING_CONCENTRATION_EVOLUTION,
    )
    assert Fraction(29, 60) - Fraction(20, 60) == Fraction(15, 100)


@pytest.mark.parametrize(
    ("breadth", "qualifies"),
    (
        (_breadth(previous_artist_days=20, current_artist_days=25), True),
        (_breadth(previous_artist_days=20, current_artist_days=24), False),
        (_breadth(previous_artist_days=25, current_artist_days=30), True),
        (_breadth(previous_artist_days=26, current_artist_days=31), False),
        (_breadth(previous_artist_days=0, current_artist_days=10), False),
        (_breadth(previous_artist_days=20, current_artist_days=0), True),
    ),
    ids=(
        "both-exact",
        "absolute-below",
        "relative-exact",
        "relative-below",
        "previous-zero",
        "current-zero",
    ),
)
def test_breadth_requires_exact_absolute_and_relative_thresholds(
    breadth: ArtistBreadthEvolutionEvidence,
    qualifies: bool,
) -> None:
    facts = LongTermEvolutionKnowledgeEngine(
        _evidence(
            candidates=(),
            concentration=_concentration(current_top_five_ms=500),
            breadth=breadth,
        )
    ).generate_facts()
    assert bool(facts) is qualifies


@pytest.mark.parametrize(
    ("current_top_five_ms", "qualifies"),
    ((650, True), (649, False), (350, True)),
    ids=("increase-boundary", "below-boundary", "decrease-boundary"),
)
def test_concentration_exact_threshold_and_direction(
    current_top_five_ms: int,
    qualifies: bool,
) -> None:
    facts = LongTermEvolutionKnowledgeEngine(
        _evidence(
            candidates=(),
            concentration=_concentration(current_top_five_ms=current_top_five_ms),
            breadth=_breadth(current_artist_days=20),
        )
    ).generate_facts()
    assert bool(facts) is qualifies


def test_metadata_is_minimal_raw_immutable_and_date_ranges_are_half_open() -> None:
    share, breadth, concentration = LongTermEvolutionKnowledgeEngine(
        _evidence()
    ).generate_facts()
    common = {
        "subject_key",
        "concept_key",
        "direction",
        "previous_start_date",
        "previous_end_date",
        "current_start_date",
        "current_end_date",
        "previous_value",
        "current_value",
    }
    assert set(share.metadata) == common | {
        "artist_identity",
        "artist_name",
        "previous_duration_ms",
        "current_duration_ms",
        "previous_attributed_duration_ms",
        "current_attributed_duration_ms",
        "signed_share_change",
        "absolute_share_change",
    }
    assert set(breadth.metadata) == common | {
        "previous_artist_day_count",
        "current_artist_day_count",
        "previous_listening_day_count",
        "current_listening_day_count",
        "signed_change",
        "absolute_change",
        "relative_change",
        "absolute_relative_change",
    }
    assert set(concentration.metadata) == common | {
        "previous_top_five_duration_ms",
        "current_top_five_duration_ms",
        "previous_attributed_duration_ms",
        "current_attributed_duration_ms",
        "signed_share_change",
        "absolute_share_change",
    }
    assert share.metadata["previous_value"] == 0.2
    assert share.metadata["current_value"] == 0.35
    assert breadth.metadata["previous_value"] == 2.0
    assert breadth.metadata["current_value"] == 2.5
    assert share.metadata["previous_end_date"] == "2026-07-07"
    assert share.metadata["current_end_date"] == "2026-08-06"
    for fact in (share, breadth, concentration):
        assert "gap_dates" not in fact.metadata
        assert "previous_window" not in fact.metadata
        assert "current_window" not in fact.metadata
        with pytest.raises(TypeError):
            fact.metadata["direction"] = "changed"  # type: ignore[index]


def test_canonical_breadth_uses_exact_round_half_up() -> None:
    breadth = _breadth(
        previous_artist_days=33,
        current_artist_days=45,
        previous_listening_days=20,
        current_listening_days=20,
    )
    facts = LongTermEvolutionKnowledgeEngine(
        _evidence(
            candidates=(),
            concentration=_concentration(current_top_five_ms=500),
            breadth=breadth,
        )
    ).generate_facts()
    assert facts[0].description == (
        "Artists per listening day increased from 1.7 in the previous 30-day "
        "period to 2.3 in the current 30-day period."
    )


def test_engine_rejects_wrong_input_and_has_no_localization_dependency() -> None:
    with pytest.raises(TypeError, match="LongTermEvolutionEvidence"):
        LongTermEvolutionKnowledgeEngine(object())  # type: ignore[arg-type]
    assert "music_ai.localization" not in inspect.getsource(engine_module)
