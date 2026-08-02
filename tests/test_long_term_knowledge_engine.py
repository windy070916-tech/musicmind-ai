"""Tests for Knowledge interpretation of long-term evidence."""

from dataclasses import FrozenInstanceError, replace
from datetime import date, datetime, timedelta, timezone

import pytest

from music_ai.knowledge import (
    FactCategory,
    FactSource,
    FactTimeHorizon,
    LongTermKnowledgeEngine,
)
from music_ai.temporal import (
    ArtistBreadthEvidence,
    ArtistConsistencyEvidence,
    ListeningConcentrationEvidence,
    LongTermListeningEvidence,
)


def _consistency(**overrides: object) -> ArtistConsistencyEvidence:
    fields: dict[str, object] = {
        "identity": ("spotify", "artist-a"),
        "spotify_artist_id": "artist-a",
        "artist_name": "Artist A",
        "appearance_day_count": 8,
        "listening_day_count": 16,
        "closed_supporting_day_count": 6,
        "aggregate_duration_ms": 8_000,
        "appearance_share": 0.5,
        "duration_share": 0.4,
        "evidence_sufficient": True,
        "prefix_appearance_day_count": 7,
        "prefix_listening_day_count": 15,
        "prefix_closed_supporting_day_count": 5,
        "prefix_aggregate_duration_ms": 7_000,
        "prefix_appearance_share": 7 / 15,
        "prefix_duration_share": 0.38,
        "prefix_evidence_sufficient": True,
        "structural_transition": False,
    }
    fields.update(overrides)
    return ArtistConsistencyEvidence(**fields)  # type: ignore[arg-type]


def _concentration(**overrides: object) -> ListeningConcentrationEvidence:
    fields: dict[str, object] = {
        "distinct_artist_count": 20,
        "top_one_duration_share": 0.30,
        "top_five_duration_share": 0.70,
        "total_attributed_artist_duration_ms": 20_000,
        "total_estimated_listening_duration_ms": 20_000,
        "listening_day_count": 16,
        "closed_listening_day_count": 12,
        "evidence_sufficient": True,
        "prefix_distinct_artist_count": 19,
        "prefix_top_one_duration_share": 0.30,
        "prefix_top_five_duration_share": 0.69,
        "prefix_total_attributed_artist_duration_ms": 19_000,
        "prefix_total_estimated_listening_duration_ms": 19_000,
        "prefix_listening_day_count": 15,
        "prefix_closed_listening_day_count": 11,
        "prefix_evidence_sufficient": True,
        "structural_transition": False,
    }
    fields.update(overrides)
    return ListeningConcentrationEvidence(**fields)  # type: ignore[arg-type]


def _breadth(**overrides: object) -> ArtistBreadthEvidence:
    fields: dict[str, object] = {
        "unique_artist_count": 20,
        "single_day_artist_count": 8,
        "repeated_artist_count": 12,
        "artist_day_appearance_count": 32,
        "artists_per_listening_day": 2.0,
        "listening_day_count": 16,
        "closed_listening_day_count": 12,
        "evidence_sufficient": True,
        "prefix_unique_artist_count": 19,
        "prefix_single_day_artist_count": 7,
        "prefix_repeated_artist_count": 12,
        "prefix_artist_day_appearance_count": 29,
        "prefix_artists_per_listening_day": 29 / 15,
        "prefix_listening_day_count": 15,
        "prefix_closed_listening_day_count": 11,
        "prefix_evidence_sufficient": True,
        "structural_transition": False,
    }
    fields.update(overrides)
    return ArtistBreadthEvidence(**fields)  # type: ignore[arg-type]


def _evidence(
    *,
    consistency: tuple[ArtistConsistencyEvidence, ...] | None = None,
    concentration: ListeningConcentrationEvidence | None = None,
    breadth: ArtistBreadthEvidence | None = None,
) -> LongTermListeningEvidence:
    return LongTermListeningEvidence(
        timezone_name="UTC",
        as_of=datetime(2026, 7, 31, 12, tzinfo=timezone.utc),
        start_date=date(2026, 7, 1),
        end_date=date(2026, 7, 31),
        recorded_day_count=28,
        listening_day_count=16,
        closed_day_count=20,
        gap_dates=(date(2026, 7, 4), date(2026, 7, 9)),
        contains_open_day=True,
        total_estimated_listening_duration_ms=20_000,
        artist_consistency=consistency if consistency is not None else (_consistency(),),
        listening_concentration=concentration or _concentration(),
        artist_breadth=breadth or _breadth(),
    )


def test_exact_thresholds_create_one_fact_per_concept_from_evidence_only() -> None:
    facts = LongTermKnowledgeEngine(_evidence()).generate_facts()

    assert tuple(fact.category for fact in facts) == (
        FactCategory.ARTIST_CONSISTENCY,
        FactCategory.LISTENING_CONCENTRATION,
        FactCategory.ARTIST_BREADTH,
    )
    assert all(fact.time_horizon is FactTimeHorizon.LONG_TERM for fact in facts)
    assert all(
        fact.source is FactSource.LONG_TERM_LISTENING_EVIDENCE for fact in facts
    )
    assert all(fact.date_range == ("2026-07-01", "2026-07-31") for fact in facts)
    assert all(fact.metadata["recorded_day_count"] == 28 for fact in facts)
    assert all(fact.metadata["gap_dates"] == ("2026-07-04", "2026-07-09") for fact in facts)
    assert [fact.metadata["concept_key"] for fact in facts] == [
        "artist_consistency",
        "listening_concentration",
        "artist_breadth",
    ]
    assert facts[0].metadata["subject_key"] == "spotify:artist-a"
    assert facts[1].metadata["subject_key"] == "listening:all_artists"


def test_prefix_product_threshold_prevents_repeated_facts() -> None:
    evidence = _evidence(
        consistency=(
            _consistency(
                prefix_appearance_day_count=8,
                prefix_appearance_share=8 / 15,
                prefix_closed_supporting_day_count=6,
            ),
        ),
        concentration=_concentration(prefix_top_five_duration_share=0.70),
        breadth=_breadth(
            prefix_unique_artist_count=20,
            prefix_single_day_artist_count=8,
            prefix_repeated_artist_count=12,
            prefix_artist_day_appearance_count=30,
            prefix_artists_per_listening_day=2.0,
        ),
    )

    assert LongTermKnowledgeEngine(evidence).generate_facts() == ()


def test_insufficient_or_below_threshold_evidence_is_silent() -> None:
    evidence = _evidence(
        consistency=(_consistency(evidence_sufficient=False),),
        concentration=_concentration(top_five_duration_share=0.69),
        breadth=_breadth(artists_per_listening_day=1.99),
    )

    assert LongTermKnowledgeEngine(evidence).generate_facts() == ()


def test_strongest_new_consistency_artist_is_selected_deterministically() -> None:
    weaker = _consistency(
        identity=("spotify", "artist-b"),
        spotify_artist_id="artist-b",
        artist_name="Artist B",
        appearance_day_count=9,
        appearance_share=0.60,
        duration_share=0.60,
    )
    stronger = _consistency(
        identity=("legacy", "artist c"),
        spotify_artist_id=None,
        artist_name="Artist C",
        appearance_day_count=10,
        appearance_share=0.625,
        duration_share=0.20,
    )
    evidence = _evidence(
        consistency=(weaker, stronger),
        concentration=_concentration(evidence_sufficient=False),
        breadth=_breadth(evidence_sufficient=False),
    )

    facts = LongTermKnowledgeEngine(evidence).generate_facts()

    assert len(facts) == 1
    assert facts[0].description.startswith("Artist C appeared")
    assert facts[0].metadata["subject_key"] == "legacy:artist c"


def test_fact_wording_is_neutral_exact_and_metadata_is_immutable() -> None:
    facts = LongTermKnowledgeEngine(_evidence()).generate_facts()

    assert facts[0].description == (
        "Artist A appeared on 8 of 16 recorded listening days in this period."
    )
    assert facts[1].description == (
        "The top five artists accounted for 70% of recorded listening time "
        "in this period."
    )
    assert facts[2].description == (
        "You listened to 20 artists across 16 recorded listening days; "
        "8 appeared on one day."
    )
    combined = " ".join(fact.description.casefold() for fact in facts)
    for banned in ("favorite", "loyal", "devoted", "adventurous", "personality"):
        assert banned not in combined
    with pytest.raises(TypeError):
        facts[0].metadata["subject_key"] = "changed"  # type: ignore[index]


def test_engine_rejects_non_evidence_input_without_memory_access() -> None:
    with pytest.raises(TypeError, match="LongTermListeningEvidence"):
        LongTermKnowledgeEngine(object())  # type: ignore[arg-type]

    engine = LongTermKnowledgeEngine(
        _evidence(
            consistency=(),
            concentration=_concentration(evidence_sufficient=False),
            breadth=_breadth(evidence_sufficient=False),
        )
    )
    assert not hasattr(engine, "_memory")
    assert engine.generate_facts() == ()


def test_evidence_rejects_incomplete_window_partition() -> None:
    with pytest.raises(ValueError, match="cover the complete analysis window"):
        replace(_evidence(), recorded_day_count=27)


def test_evidence_rejects_inconsistent_open_day_state() -> None:
    with pytest.raises(ValueError, match="contains_open_day"):
        replace(_evidence(), contains_open_day=False)
    with pytest.raises(ValueError, match="contains_open_day"):
        replace(_evidence(), closed_day_count=28, contains_open_day=True)


def test_evidence_rejects_conflicting_or_excessive_closed_listening_days() -> None:
    with pytest.raises(ValueError, match="same closed listening-day count"):
        _evidence(
            concentration=_concentration(closed_listening_day_count=11),
        )
    with pytest.raises(ValueError, match="shared closed-day count"):
        replace(_evidence(), closed_day_count=11)


def test_evidence_accepts_zero_fully_closed_and_partially_open_coverage() -> None:
    valid_partial = _evidence()
    assert valid_partial.contains_open_day is True

    fully_closed = replace(
        valid_partial,
        recorded_day_count=30,
        closed_day_count=30,
        gap_dates=(),
        contains_open_day=False,
    )
    assert fully_closed.closed_day_count == fully_closed.recorded_day_count

    zero_concentration = replace(
        _concentration(),
        distinct_artist_count=0,
        top_one_duration_share=0.0,
        top_five_duration_share=0.0,
        total_attributed_artist_duration_ms=0,
        total_estimated_listening_duration_ms=0,
        listening_day_count=0,
        closed_listening_day_count=0,
        evidence_sufficient=False,
    )
    zero_breadth = replace(
        _breadth(),
        unique_artist_count=0,
        single_day_artist_count=0,
        repeated_artist_count=0,
        artist_day_appearance_count=0,
        artists_per_listening_day=0.0,
        listening_day_count=0,
        closed_listening_day_count=0,
        evidence_sufficient=False,
    )
    zero_recorded = replace(
        valid_partial,
        recorded_day_count=0,
        listening_day_count=0,
        closed_day_count=0,
        gap_dates=tuple(
            valid_partial.start_date + timedelta(days=index)
            for index in range(30)
        ),
        contains_open_day=False,
        total_estimated_listening_duration_ms=0,
        artist_consistency=(),
        listening_concentration=zero_concentration,
        artist_breadth=zero_breadth,
    )
    assert zero_recorded.recorded_day_count == 0
    assert len(zero_recorded.gap_dates) == 30

    with pytest.raises(FrozenInstanceError):
        valid_partial.recorded_day_count = 30  # type: ignore[misc]
