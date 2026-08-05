"""Tests for Knowledge interpretation of deterministic recent evidence."""

from dataclasses import replace
from datetime import date, datetime, timezone
import json

import pytest

from music_ai.knowledge import (
    FactCategory,
    FactSource,
    FactTimeHorizon,
    ImportanceLevel,
    InsightType,
    KnowledgeFact,
    FactMessageKey,
    RecentKnowledgeEngine,
)
from music_ai.temporal import (
    ArtistContinuityEvidence,
    ArtistEmergenceEvidence,
    RecentListeningEvidence,
)


_COMPARISON_START = date(2026, 7, 1)
_COMPARISON_END = date(2026, 7, 4)
_RECENT_START = date(2026, 7, 4)
_RECENT_END = date(2026, 7, 8)
_RECENT_GAPS = (date(2026, 7, 6),)
_AS_OF = datetime(2026, 7, 8, 12, tzinfo=timezone.utc)


def _continuity(**overrides: object) -> ArtistContinuityEvidence:
    fields: dict[str, object] = {
        "spotify_artist_id": "artist-a",
        "artist_name": "Artist A",
        "window_start_date": _RECENT_START,
        "window_end_date": _RECENT_END,
        "recorded_day_count": 3,
        "listening_day_count": 3,
        "qualifying_day_count": 3,
        "closed_qualifying_day_count": 2,
        "qualifying_day_share": 1.0,
        "gap_dates": _RECENT_GAPS,
        "contains_open_day": True,
        "evidence_sufficient": True,
        "continuity_transition": True,
    }
    fields.update(overrides)
    return ArtistContinuityEvidence(**fields)  # type: ignore[arg-type]


def _emergence(**overrides: object) -> ArtistEmergenceEvidence:
    fields: dict[str, object] = {
        "spotify_artist_id": "artist-b",
        "artist_name": "Artist B",
        "recent_start_date": _RECENT_START,
        "recent_end_date": _RECENT_END,
        "comparison_start_date": _COMPARISON_START,
        "comparison_end_date": _COMPARISON_END,
        "recent_recorded_day_count": 3,
        "comparison_recorded_day_count": 3,
        "recent_listening_day_count": 2,
        "comparison_listening_day_count": 2,
        "recent_closed_listening_day_count": 1,
        "comparison_closed_listening_day_count": 2,
        "recent_artist_day_count": 2,
        "comparison_artist_day_count": 1,
        "recent_closed_artist_day_count": 1,
        "comparison_closed_artist_day_count": 1,
        "recent_artist_duration_ms": 400,
        "comparison_artist_duration_ms": 100,
        "recent_total_duration_ms": 1_000,
        "comparison_total_duration_ms": 1_000,
        "recent_duration_share": 0.4,
        "comparison_duration_share": 0.1,
        "duration_share_change": 0.3,
        "recent_gap_dates": _RECENT_GAPS,
        "comparison_gap_dates": (),
        "contains_open_day": True,
        "evidence_sufficient": True,
        "emergence_transition": True,
    }
    fields.update(overrides)
    return ArtistEmergenceEvidence(**fields)  # type: ignore[arg-type]


def _recent_evidence(
    *,
    continuity: tuple[ArtistContinuityEvidence, ...] = (),
    emergence: tuple[ArtistEmergenceEvidence, ...] = (),
) -> RecentListeningEvidence:
    return RecentListeningEvidence(
        timezone_name="UTC",
        as_of=_AS_OF,
        recent_start_date=_RECENT_START,
        recent_end_date=_RECENT_END,
        comparison_start_date=_COMPARISON_START,
        comparison_end_date=_COMPARISON_END,
        recent_gap_dates=_RECENT_GAPS,
        comparison_gap_dates=(),
        contains_open_day=True,
        continuity=continuity,
        emergence=emergence,
    )


def test_continuity_evidence_is_interpreted_as_a_recent_knowledge_fact() -> None:
    fact = RecentKnowledgeEngine(
        _recent_evidence(continuity=(_continuity(),))
    ).generate_facts()[0]

    assert fact.category is FactCategory.ARTIST_CONTINUITY
    assert fact.importance is ImportanceLevel.MEDIUM
    assert fact.title == "Artist Continuity"
    assert (
        fact.description
        == "Artist A was your top artist on 3 of 3 recent listening days."
    )
    assert fact.source is FactSource.RECENT_LISTENING_EVIDENCE
    assert fact.insight_type is InsightType.BEHAVIOR
    assert fact.time_horizon is FactTimeHorizon.RECENT
    assert fact.date_range == ("2026-07-04", "2026-07-08")
    assert fact.metadata["subject_key"] == "spotify:artist-a"
    assert fact.metadata["gap_dates"] == ("2026-07-06",)
    assert fact.message_key is FactMessageKey.RECENT_ARTIST_CONTINUITY
    assert fact.metadata["contains_open_day"] is True


def test_emergence_evidence_is_interpreted_as_a_recent_knowledge_fact() -> None:
    fact = RecentKnowledgeEngine(
        _recent_evidence(emergence=(_emergence(),))
    ).generate_facts()[0]

    assert fact.category is FactCategory.ARTIST_EMERGENCE
    assert fact.importance is ImportanceLevel.HIGH
    assert fact.title == "Artist Emergence"
    assert (
        fact.description
        == "Artist B grew from 10% to 40% of your listening time."
    )
    assert fact.source is FactSource.RECENT_LISTENING_EVIDENCE
    assert fact.insight_type is InsightType.BEHAVIOR
    assert fact.time_horizon is FactTimeHorizon.RECENT
    assert fact.date_range == ("2026-07-01", "2026-07-08")
    assert fact.metadata["subject_key"] == "spotify:artist-b"
    assert fact.metadata["recent_duration_share"] == pytest.approx(0.4)
    assert fact.metadata["comparison_duration_share"] == pytest.approx(0.1)
    assert fact.metadata["duration_share_change"] == pytest.approx(0.3)
    assert fact.metadata["recent_gap_dates"] == ("2026-07-06",)
    assert fact.message_key is FactMessageKey.RECENT_ARTIST_EMERGENCE


def test_legacy_artist_fact_uses_normalized_name_as_subject_identity() -> None:
    fact = RecentKnowledgeEngine(
        _recent_evidence(
            continuity=(
                _continuity(
                    spotify_artist_id=None,
                    artist_name="  ARTIST A  ",
                ),
            )
        )
    ).generate_facts()[0]

    assert fact.metadata["subject_key"] == "legacy:artist a"
    assert fact.metadata["spotify_artist_id"] is None


def test_knowledge_returns_silence_without_temporal_evidence() -> None:
    assert RecentKnowledgeEngine(_recent_evidence()).generate_facts() == []


def test_knowledge_suppresses_insufficient_repeated_or_weak_continuity() -> None:
    evidence = _recent_evidence(
        continuity=(
            _continuity(evidence_sufficient=False),
            _continuity(
                spotify_artist_id="artist-b",
                artist_name="Artist B",
                continuity_transition=False,
            ),
            _continuity(
                spotify_artist_id="artist-c",
                artist_name="Artist C",
                qualifying_day_share=0.49,
            ),
        )
    )

    assert RecentKnowledgeEngine(evidence).generate_facts() == []


def test_knowledge_suppresses_insufficient_nontransitioning_or_weak_emergence() -> None:
    evidence = _recent_evidence(
        emergence=(
            _emergence(evidence_sufficient=False),
            _emergence(
                spotify_artist_id="artist-c",
                artist_name="Artist C",
                emergence_transition=False,
            ),
            _emergence(
                spotify_artist_id="artist-d",
                artist_name="Artist D",
                recent_duration_share=0.24,
                comparison_duration_share=0.04,
                duration_share_change=0.2,
            ),
            _emergence(
                spotify_artist_id="artist-e",
                artist_name="Artist E",
                recent_duration_share=0.4,
                comparison_duration_share=0.26,
                duration_share_change=0.14,
            ),
        )
    )

    assert RecentKnowledgeEngine(evidence).generate_facts() == []


def test_knowledge_relies_on_temporal_sufficiency_instead_of_reaggregating() -> None:
    high_shares_but_insufficient = _emergence(
        evidence_sufficient=False,
        recent_duration_share=0.8,
        comparison_duration_share=0.1,
        duration_share_change=0.7,
    )

    facts = RecentKnowledgeEngine(
        _recent_evidence(emergence=(high_shares_but_insufficient,))
    ).generate_facts()

    assert facts == []


def test_recent_knowledge_engine_accepts_only_recent_listening_evidence() -> None:
    with pytest.raises(TypeError, match="RecentListeningEvidence"):
        RecentKnowledgeEngine(object())  # type: ignore[arg-type]


def test_fact_time_horizon_is_json_serializable_and_additive() -> None:
    existing_fact = KnowledgeFact(
        category=FactCategory.LISTENING_TIME,
        importance=ImportanceLevel.MEDIUM,
        title="Listening Time",
        description="You listened today.",
        insight_type=InsightType.DAILY_LISTENING,
    )

    assert [horizon.value for horizon in FactTimeHorizon] == [
        "daily",
        "recent",
        "long_term",
    ]
    assert existing_fact.time_horizon is FactTimeHorizon.DAILY
    assert (
        json.dumps(
            {
                "category": existing_fact.category,
                "time_horizon": FactTimeHorizon.RECENT,
            },
            sort_keys=True,
        )
        == '{"category": "listening_time", "time_horizon": "recent"}'
    )


def test_recent_evidence_collection_snapshots_input_sequences() -> None:
    continuity_values = [_continuity()]
    evidence = _recent_evidence(continuity=tuple(continuity_values))
    continuity_values.clear()

    assert len(evidence.continuity) == 1
    assert replace(evidence.continuity[0]) == evidence.continuity[0]
