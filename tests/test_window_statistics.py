"""Focused tests for shared immutable Temporal window statistics."""

from dataclasses import FrozenInstanceError, replace
from datetime import date, datetime, timedelta, timezone

import pytest

from music_ai.analytics import DailyListeningProfile, RankedArtist
from music_ai.memory import CURRENT_SNAPSHOT_VERSION, DailyMemorySnapshot
from music_ai.temporal.window_statistics import (
    ArtistWindowAggregate,
    calculate_listening_window_statistics,
)


def _snapshot(
    local_date: date,
    artists: tuple[tuple[str | None, str, int], ...] = (),
    *,
    total_duration_ms: int | None = None,
    closed: bool = True,
) -> DailyMemorySnapshot:
    total = (
        sum(max(0, duration) for _, _, duration in artists)
        if total_duration_ms is None
        else total_duration_ms
    )
    start = datetime.combine(local_date, datetime.min.time(), tzinfo=timezone.utc)
    profile = DailyListeningProfile(
        start_datetime=start,
        end_datetime=start + timedelta(days=1),
        total_estimated_listening_duration_ms=total,
        playback_count=int(total > 0),
        unique_track_count=int(total > 0),
        unique_track_ratio=float(total > 0),
        top_track_share=0.0,
        genre_covered_duration_ms=0,
        genre_coverage=0.0,
        top_tracks=(),
        top_artists=tuple(
            RankedArtist(artist_id, name, 1, duration, 0.0)
            for artist_id, name, duration in artists
        ),
        top_albums=(),
        top_genres=(),
    )
    return DailyMemorySnapshot(
        local_date=local_date,
        timezone_name="UTC",
        profile=profile,
        generated_at=start + timedelta(days=2),
        is_closed=closed,
        snapshot_version=CURRENT_SNAPSHOT_VERSION,
    )


def test_shared_statistics_preserve_sparse_half_open_primary_artist_semantics() -> None:
    start = date(2026, 7, 1)
    snapshots = (
        _snapshot(
            start,
            (
                (" spotify-z ", "Zulu Name", 100),
                ("spotify-z", "Alpha Name", 50),
                (None, " Legacy Artist ", 50),
                ("unknown-id", "Unknown artist", 200),
                ("blank-id", "   ", 50),
                ("ignored", "Ignored", 0),
            ),
            total_duration_ms=500,
        ),
        _snapshot(start + timedelta(days=2)),
        _snapshot(
            start + timedelta(days=3),
            (("spotify-z", "Current Name", 100),),
            closed=False,
        ),
        _snapshot(
            start + timedelta(days=4),
            (("outside", "Outside", 1_000),),
        ),
    )

    stats = calculate_listening_window_statistics(
        snapshots, start, start + timedelta(days=4)
    )

    assert stats.recorded_day_count == 3
    assert stats.listening_day_count == 2
    assert stats.closed_day_count == 2
    assert stats.closed_listening_day_count == 1
    assert stats.gap_dates == (start + timedelta(days=1),)
    assert stats.contains_open_snapshot is True
    assert stats.total_estimated_listening_duration_ms == 600
    assert stats.total_attributed_artist_duration_ms == 300
    assert stats.artist_day_appearance_count == 3
    assert tuple(artist.identity for artist in stats.artists) == (
        ("legacy", "legacy artist"),
        ("spotify", "spotify-z"),
    )
    legacy, spotify = stats.artists
    assert legacy == ArtistWindowAggregate(
        identity=("legacy", "legacy artist"),
        spotify_artist_id=None,
        artist_name="Legacy Artist",
        duration_ms=50,
        appearance_day_count=1,
        closed_supporting_day_count=1,
    )
    assert spotify.artist_name == "Alpha Name"
    assert spotify.duration_ms == 250
    assert spotify.appearance_day_count == 2
    assert spotify.closed_supporting_day_count == 1


def test_shared_statistics_are_deeply_immutable_and_validate_invariants() -> None:
    start = date(2026, 7, 1)
    stats = calculate_listening_window_statistics(
        (_snapshot(start, (("a", "Artist A", 100),)),),
        start,
        start + timedelta(days=1),
    )

    assert isinstance(stats.artists, tuple)
    assert isinstance(stats.gap_dates, tuple)
    with pytest.raises(FrozenInstanceError):
        stats.recorded_day_count = 2  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        stats.artists[0].duration_ms = 200  # type: ignore[misc]
    with pytest.raises(ValueError, match="Attributed artist duration"):
        replace(stats, total_estimated_listening_duration_ms=99)
    with pytest.raises(ValueError, match="identity-ordered"):
        replace(stats, artists=(stats.artists[0], stats.artists[0]))


def test_shared_statistics_reject_empty_windows_and_non_snapshot_collections() -> None:
    start = date(2026, 7, 1)
    with pytest.raises(ValueError, match="non-empty"):
        calculate_listening_window_statistics((), start, start)
    with pytest.raises(TypeError, match="tuple of DailyMemorySnapshot"):
        calculate_listening_window_statistics(  # type: ignore[arg-type]
            (object(),), start, start + timedelta(days=1)
        )
