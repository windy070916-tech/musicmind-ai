"""Unit tests for deterministic bounded Temporal Analytics."""

from dataclasses import FrozenInstanceError
from datetime import date, datetime, timezone

import pytest

from music_ai.analytics import DailyListeningProfile, RankedArtist
from music_ai.memory import (
    CURRENT_SNAPSHOT_VERSION,
    DailyMemorySnapshot,
    ListeningMemory,
)
from music_ai.memory.models import local_day_utc_boundaries, timezone_for_name
from music_ai.temporal import (
    ArtistContinuityEvidence,
    TemporalListeningAnalytics,
)


_TIMEZONE_NAME = "UTC"
_AS_OF = datetime(2026, 7, 20, 12, tzinfo=timezone.utc)


def _profile(
    local_date: date,
    artists: tuple[tuple[str | None, str, int], ...] = (),
    *,
    total_duration_ms: int | None = None,
) -> DailyListeningProfile:
    start, end = local_day_utc_boundaries(
        local_date, timezone_for_name(_TIMEZONE_NAME)
    )
    resolved_total = (
        sum(duration_ms for _, _, duration_ms in artists)
        if total_duration_ms is None
        else total_duration_ms
    )
    ranked_artists = tuple(
        RankedArtist(
            spotify_artist_id=spotify_artist_id,
            name=name,
            play_count=1,
            estimated_listening_duration_ms=duration_ms,
            share=(duration_ms / resolved_total if resolved_total else 0.0),
        )
        for spotify_artist_id, name, duration_ms in artists
    )
    return DailyListeningProfile(
        start_datetime=start,
        end_datetime=end,
        total_estimated_listening_duration_ms=resolved_total,
        playback_count=1 if resolved_total else 0,
        unique_track_count=1 if resolved_total else 0,
        unique_track_ratio=1.0 if resolved_total else 0.0,
        top_track_share=1.0 if resolved_total else 0.0,
        genre_covered_duration_ms=0,
        genre_coverage=0.0,
        top_tracks=(),
        top_artists=ranked_artists,
        top_albums=(),
        top_genres=(),
    )


def _snapshot(
    local_date: date,
    artists: tuple[tuple[str | None, str, int], ...] = (),
    *,
    total_duration_ms: int | None = None,
    is_closed: bool = True,
) -> DailyMemorySnapshot:
    return DailyMemorySnapshot(
        local_date=local_date,
        timezone_name=_TIMEZONE_NAME,
        profile=_profile(
            local_date,
            artists,
            total_duration_ms=total_duration_ms,
        ),
        generated_at=_AS_OF,
        is_closed=is_closed,
        snapshot_version=CURRENT_SNAPSHOT_VERSION,
    )


def _memory(
    start_date: date,
    end_date: date,
    snapshots: tuple[DailyMemorySnapshot, ...],
) -> ListeningMemory:
    return ListeningMemory(
        start_date=start_date,
        end_date=end_date,
        timezone_name=_TIMEZONE_NAME,
        snapshots=snapshots,
        as_of=_AS_OF,
    )


def _analyze(
    memory: ListeningMemory,
    *,
    comparison_start: date,
    recent_start: date,
    recent_end: date,
):
    return TemporalListeningAnalytics().analyze(
        memory,
        comparison_start_date=comparison_start,
        comparison_end_date=recent_start,
        recent_start_date=recent_start,
        recent_end_date=recent_end,
        timezone_name=_TIMEZONE_NAME,
        as_of=_AS_OF,
    )


def _emergence_for_id(evidence, spotify_artist_id: str):
    return next(
        item
        for item in evidence.emergence
        if item.spotify_artist_id == spotify_artist_id
    )


def test_analysis_uses_only_caller_supplied_half_open_windows() -> None:
    snapshots = (
        _snapshot(date(2026, 7, 3), (("artist-a", "Artist A", 9_999),)),
        _snapshot(
            date(2026, 7, 4),
            (("artist-a", "Artist A", 20), ("artist-b", "Artist B", 80)),
        ),
        _snapshot(
            date(2026, 7, 5),
            (("artist-a", "Artist A", 20), ("artist-b", "Artist B", 80)),
        ),
        _snapshot(
            date(2026, 7, 6),
            (("artist-a", "Artist A", 20), ("artist-b", "Artist B", 80)),
        ),
        _snapshot(
            date(2026, 7, 7),
            (("artist-a", "Artist A", 70), ("artist-b", "Artist B", 30)),
        ),
        _snapshot(
            date(2026, 7, 8),
            (("artist-a", "Artist A", 70), ("artist-b", "Artist B", 30)),
        ),
        _snapshot(
            date(2026, 7, 9),
            (("artist-a", "Artist A", 70), ("artist-b", "Artist B", 30)),
        ),
        _snapshot(date(2026, 7, 10), (("artist-a", "Artist A", 8_888),)),
    )
    memory = _memory(date(2026, 7, 1), date(2026, 7, 12), snapshots)
    original_snapshots = memory.snapshots

    evidence = _analyze(
        memory,
        comparison_start=date(2026, 7, 4),
        recent_start=date(2026, 7, 7),
        recent_end=date(2026, 7, 10),
    )
    artist = _emergence_for_id(evidence, "artist-a")

    assert artist.comparison_recorded_day_count == 3
    assert artist.recent_recorded_day_count == 3
    assert artist.comparison_artist_duration_ms == 60
    assert artist.recent_artist_duration_ms == 210
    assert artist.comparison_total_duration_ms == 300
    assert artist.recent_total_duration_ms == 300
    assert artist.comparison_duration_share == pytest.approx(0.2)
    assert artist.recent_duration_share == pytest.approx(0.7)
    assert memory.snapshots is original_snapshots


def test_temporal_analytics_owns_no_implicit_analysis_windows() -> None:
    memory = _memory(date(2026, 7, 1), date(2026, 7, 7), ())

    with pytest.raises(TypeError, match="recent_start_date"):
        TemporalListeningAnalytics().analyze(memory)


@pytest.mark.parametrize(
    "overrides,match",
    [
        ({"recent_end_date": date(2026, 7, 4)}, "recent window"),
        ({"comparison_end_date": date(2026, 7, 8)}, "overlap"),
        ({"comparison_start_date": date(2026, 6, 30)}, "contained"),
        ({"recent_end_date": date(2026, 7, 12)}, "contained"),
        ({"timezone_name": "Asia/Shanghai"}, "timezone"),
        ({"as_of": datetime(2026, 7, 10, 12)}, "timezone-aware"),
    ],
)
def test_analysis_rejects_invalid_or_unbounded_window_context(
    overrides: dict[str, object],
    match: str,
) -> None:
    memory = _memory(date(2026, 7, 1), date(2026, 7, 11), ())
    arguments: dict[str, object] = {
        "comparison_start_date": date(2026, 7, 1),
        "comparison_end_date": date(2026, 7, 4),
        "recent_start_date": date(2026, 7, 4),
        "recent_end_date": date(2026, 7, 7),
        "timezone_name": _TIMEZONE_NAME,
        "as_of": _AS_OF,
    }
    arguments.update(overrides)

    with pytest.raises(ValueError, match=match):
        TemporalListeningAnalytics().analyze(
            memory, **arguments  # type: ignore[arg-type]
        )


def test_missing_snapshot_is_a_gap_but_recorded_zero_listening_day_is_not() -> None:
    snapshots = (
        _snapshot(date(2026, 7, 1), (("comparison", "Comparison", 100),)),
        _snapshot(date(2026, 7, 3), total_duration_ms=0),
        _snapshot(date(2026, 7, 4), (("artist-a", "Artist A", 100),)),
        _snapshot(date(2026, 7, 6), total_duration_ms=0),
    )
    evidence = _analyze(
        _memory(date(2026, 7, 1), date(2026, 7, 7), snapshots),
        comparison_start=date(2026, 7, 1),
        recent_start=date(2026, 7, 4),
        recent_end=date(2026, 7, 7),
    )
    artist = _emergence_for_id(evidence, "artist-a")

    assert evidence.comparison_gap_dates == (date(2026, 7, 2),)
    assert evidence.recent_gap_dates == (date(2026, 7, 5),)
    assert artist.recent_recorded_day_count == 2
    assert artist.recent_listening_day_count == 1
    assert artist.recent_gap_dates == (date(2026, 7, 5),)


def test_artist_continuity_becomes_sufficient_on_third_rank_one_day() -> None:
    recent_snapshots = tuple(
        _snapshot(day, (("artist-a", "Artist A", 100),))
        for day in (
            date(2026, 7, 4),
            date(2026, 7, 5),
            date(2026, 7, 6),
        )
    )
    evidence = _analyze(
        _memory(date(2026, 7, 1), date(2026, 7, 7), recent_snapshots),
        comparison_start=date(2026, 7, 1),
        recent_start=date(2026, 7, 4),
        recent_end=date(2026, 7, 7),
    )

    continuity = evidence.continuity[0]
    assert continuity.spotify_artist_id == "artist-a"
    assert continuity.listening_day_count == 3
    assert continuity.qualifying_day_count == 3
    assert continuity.closed_qualifying_day_count == 3
    assert continuity.qualifying_day_share == 1.0
    assert continuity.evidence_sufficient is True
    assert continuity.continuity_transition is True


def test_continuity_supported_before_final_day_is_not_a_new_transition() -> None:
    recent_snapshots = tuple(
        _snapshot(day, (("artist-a", "Artist A", 100),))
        for day in (
            date(2026, 7, 4),
            date(2026, 7, 5),
            date(2026, 7, 6),
            date(2026, 7, 7),
        )
    )
    evidence = _analyze(
        _memory(date(2026, 7, 1), date(2026, 7, 8), recent_snapshots),
        comparison_start=date(2026, 7, 1),
        recent_start=date(2026, 7, 4),
        recent_end=date(2026, 7, 8),
    )

    continuity = evidence.continuity[0]
    assert continuity.evidence_sufficient is True
    assert continuity.qualifying_day_count == 4
    assert continuity.continuity_transition is False


def test_open_day_is_preserved_but_cannot_support_a_conclusion_by_itself() -> None:
    snapshots = (
        _snapshot(date(2026, 7, 1), (("comparison", "Comparison", 100),)),
        _snapshot(date(2026, 7, 2), (("comparison", "Comparison", 100),)),
        _snapshot(date(2026, 7, 4), total_duration_ms=0),
        _snapshot(date(2026, 7, 5), total_duration_ms=0),
        _snapshot(
            date(2026, 7, 6),
            (("artist-a", "Artist A", 100),),
            is_closed=False,
        ),
    )
    evidence = _analyze(
        _memory(date(2026, 7, 1), date(2026, 7, 7), snapshots),
        comparison_start=date(2026, 7, 1),
        recent_start=date(2026, 7, 4),
        recent_end=date(2026, 7, 7),
    )
    continuity = evidence.continuity[0]
    emergence = _emergence_for_id(evidence, "artist-a")

    assert evidence.contains_open_day is True
    assert continuity.contains_open_day is True
    assert continuity.closed_qualifying_day_count == 0
    assert continuity.evidence_sufficient is False
    assert continuity.continuity_transition is False
    assert emergence.contains_open_day is True
    assert emergence.recent_artist_day_count == 1
    assert emergence.evidence_sufficient is False
    assert emergence.emergence_transition is False


def test_open_current_day_can_complete_continuity_supported_by_closed_days() -> None:
    snapshots = (
        _snapshot(date(2026, 7, 4), (("artist-a", "Artist A", 100),)),
        _snapshot(date(2026, 7, 5), (("artist-a", "Artist A", 100),)),
        _snapshot(
            date(2026, 7, 6),
            (("artist-a", "Artist A", 100),),
            is_closed=False,
        ),
    )
    evidence = _analyze(
        _memory(date(2026, 7, 1), date(2026, 7, 7), snapshots),
        comparison_start=date(2026, 7, 1),
        recent_start=date(2026, 7, 4),
        recent_end=date(2026, 7, 7),
    )
    continuity = evidence.continuity[0]

    assert continuity.contains_open_day is True
    assert continuity.closed_qualifying_day_count == 2
    assert continuity.qualifying_day_count == 3
    assert continuity.evidence_sufficient is True
    assert continuity.continuity_transition is True


def test_all_open_snapshots_cannot_support_recent_conclusions() -> None:
    snapshots = tuple(
        _snapshot(
            day,
            (("artist-a", "Artist A", 100),),
            is_closed=False,
        )
        for day in (
            date(2026, 7, 1),
            date(2026, 7, 2),
            date(2026, 7, 4),
            date(2026, 7, 5),
            date(2026, 7, 6),
        )
    )
    evidence = _analyze(
        _memory(date(2026, 7, 1), date(2026, 7, 7), snapshots),
        comparison_start=date(2026, 7, 1),
        recent_start=date(2026, 7, 4),
        recent_end=date(2026, 7, 7),
    )
    continuity = evidence.continuity[0]
    emergence = _emergence_for_id(evidence, "artist-a")

    assert continuity.qualifying_day_count == 3
    assert continuity.closed_qualifying_day_count == 0
    assert continuity.evidence_sufficient is False
    assert continuity.continuity_transition is False
    assert emergence.recent_closed_artist_day_count == 0
    assert emergence.comparison_closed_listening_day_count == 0
    assert emergence.evidence_sufficient is False
    assert emergence.emergence_transition is False


def test_open_current_day_can_support_emergence_with_closed_evidence() -> None:
    snapshots = (
        _snapshot(
            date(2026, 7, 1),
            (("artist-a", "Artist A", 10), ("other", "Other", 90)),
        ),
        _snapshot(
            date(2026, 7, 2),
            (("artist-a", "Artist A", 10), ("other", "Other", 90)),
        ),
        _snapshot(date(2026, 7, 4), (("artist-a", "Artist A", 100),)),
        _snapshot(
            date(2026, 7, 5),
            (("artist-a", "Artist A", 100),),
            is_closed=False,
        ),
    )
    evidence = _analyze(
        _memory(date(2026, 7, 1), date(2026, 7, 7), snapshots),
        comparison_start=date(2026, 7, 1),
        recent_start=date(2026, 7, 4),
        recent_end=date(2026, 7, 7),
    )
    emergence = _emergence_for_id(evidence, "artist-a")

    assert emergence.contains_open_day is True
    assert emergence.recent_artist_day_count == 2
    assert emergence.recent_closed_artist_day_count == 1
    assert emergence.comparison_closed_listening_day_count == 2
    assert emergence.evidence_sufficient is True
    assert emergence.emergence_transition is True


def test_spotify_identity_combines_name_variants_and_selects_stable_name() -> None:
    names_by_day = (
        (date(2026, 7, 4), "Zulu Artist"),
        (date(2026, 7, 5), "Alpha Artist"),
        (date(2026, 7, 6), "Middle Artist"),
    )
    snapshots = tuple(
        _snapshot(day, (("spotify-a", name, 100),))
        for day, name in names_by_day
    )
    reverse_assignments = tuple(
        _snapshot(day, (("spotify-a", name, 100),))
        for (day, _), (_, name) in zip(
            names_by_day, reversed(names_by_day), strict=True
        )
    )

    first = _analyze(
        _memory(date(2026, 7, 1), date(2026, 7, 7), snapshots),
        comparison_start=date(2026, 7, 1),
        recent_start=date(2026, 7, 4),
        recent_end=date(2026, 7, 7),
    )
    second = _analyze(
        _memory(
            date(2026, 7, 1),
            date(2026, 7, 7),
            reverse_assignments,
        ),
        comparison_start=date(2026, 7, 1),
        recent_start=date(2026, 7, 4),
        recent_end=date(2026, 7, 7),
    )

    assert len(first.continuity) == 1
    assert first.continuity[0].spotify_artist_id == "spotify-a"
    assert first.continuity[0].artist_name == "Alpha Artist"
    assert second.continuity[0].artist_name == first.continuity[0].artist_name


def test_legacy_identity_uses_normalized_name_without_bridging_spotify_id() -> None:
    snapshots = (
        _snapshot(
            date(2026, 7, 4),
            (
                (None, "Legacy Artist", 60),
                ("spotify-a", "Legacy Artist", 40),
            ),
        ),
        _snapshot(
            date(2026, 7, 5),
            (
                (None, " legacy artist ", 60),
                ("spotify-a", "Legacy Artist", 40),
            ),
        ),
        _snapshot(
            date(2026, 7, 6),
            (
                (None, "LEGACY ARTIST", 60),
                ("spotify-a", "Legacy Artist", 40),
            ),
        ),
    )
    evidence = _analyze(
        _memory(date(2026, 7, 1), date(2026, 7, 7), snapshots),
        comparison_start=date(2026, 7, 1),
        recent_start=date(2026, 7, 4),
        recent_end=date(2026, 7, 7),
    )

    legacy = next(
        item for item in evidence.emergence if item.spotify_artist_id is None
    )
    spotify = _emergence_for_id(evidence, "spotify-a")

    assert legacy.artist_name == "LEGACY ARTIST"
    assert legacy.recent_artist_day_count == 3
    assert legacy.recent_artist_duration_ms == 180
    assert spotify.recent_artist_duration_ms == 120


@pytest.mark.parametrize(
    "spotify_artist_id,name",
    [(None, "Unknown artist"), (None, " UNKNOWN ARTIST "), ("id", "Unknown artist")],
)
def test_unknown_artist_placeholders_do_not_produce_temporal_evidence(
    spotify_artist_id: str | None,
    name: str,
) -> None:
    snapshots = tuple(
        _snapshot(day, ((spotify_artist_id, name, 100),))
        for day in (
            date(2026, 7, 4),
            date(2026, 7, 5),
            date(2026, 7, 6),
        )
    )

    evidence = _analyze(
        _memory(date(2026, 7, 1), date(2026, 7, 7), snapshots),
        comparison_start=date(2026, 7, 1),
        recent_start=date(2026, 7, 4),
        recent_end=date(2026, 7, 7),
    )

    assert evidence.continuity == ()
    assert evidence.emergence == ()


def test_emergence_uses_aggregate_duration_shares_not_average_daily_shares() -> None:
    snapshots = (
        _snapshot(
            date(2026, 7, 1),
            (("artist-a", "Artist A", 10), ("other", "Other", 90)),
        ),
        _snapshot(
            date(2026, 7, 2),
            (("artist-a", "Artist A", 90), ("other", "Other", 810)),
        ),
        _snapshot(
            date(2026, 7, 4),
            (("artist-a", "Artist A", 90), ("other", "Other", 10)),
        ),
        _snapshot(
            date(2026, 7, 5),
            (("artist-a", "Artist A", 10), ("other", "Other", 890)),
        ),
    )
    evidence = _analyze(
        _memory(date(2026, 7, 1), date(2026, 7, 7), snapshots),
        comparison_start=date(2026, 7, 1),
        recent_start=date(2026, 7, 4),
        recent_end=date(2026, 7, 7),
    )
    artist = _emergence_for_id(evidence, "artist-a")

    assert artist.comparison_artist_duration_ms == 100
    assert artist.comparison_total_duration_ms == 1_000
    assert artist.recent_artist_duration_ms == 100
    assert artist.recent_total_duration_ms == 1_000
    assert artist.comparison_duration_share == pytest.approx(0.1)
    assert artist.recent_duration_share == pytest.approx(0.1)
    assert artist.duration_share_change == pytest.approx(0.0)
    assert artist.emergence_transition is False


def test_zero_comparison_duration_has_no_fabricated_share_or_emergence() -> None:
    snapshots = (
        _snapshot(date(2026, 7, 1), total_duration_ms=0),
        _snapshot(date(2026, 7, 2), total_duration_ms=0),
        _snapshot(date(2026, 7, 4), (("artist-a", "Artist A", 100),)),
        _snapshot(date(2026, 7, 5), (("artist-a", "Artist A", 100),)),
    )
    evidence = _analyze(
        _memory(date(2026, 7, 1), date(2026, 7, 7), snapshots),
        comparison_start=date(2026, 7, 1),
        recent_start=date(2026, 7, 4),
        recent_end=date(2026, 7, 7),
    )
    artist = _emergence_for_id(evidence, "artist-a")

    assert artist.comparison_total_duration_ms == 0
    assert artist.comparison_duration_share is None
    assert artist.duration_share_change is None
    assert artist.evidence_sufficient is False
    assert artist.emergence_transition is False


def test_temporal_evidence_is_immutable_and_slotted() -> None:
    snapshots = tuple(
        _snapshot(day, (("artist-a", "Artist A", 100),))
        for day in (
            date(2026, 7, 4),
            date(2026, 7, 5),
            date(2026, 7, 6),
        )
    )
    evidence = _analyze(
        _memory(date(2026, 7, 1), date(2026, 7, 7), snapshots),
        comparison_start=date(2026, 7, 1),
        recent_start=date(2026, 7, 4),
        recent_end=date(2026, 7, 7),
    )
    continuity: ArtistContinuityEvidence = evidence.continuity[0]

    assert not hasattr(evidence, "__dict__")
    assert not hasattr(continuity, "__dict__")
    with pytest.raises(FrozenInstanceError):
        continuity.artist_name = "Changed"  # type: ignore[misc]
