"""Contract tests for immutable listening-memory models."""

from dataclasses import FrozenInstanceError
from datetime import date, datetime, timezone

import pytest

from music_ai.analytics import DailyListeningProfile
from music_ai.memory.models import (
    CURRENT_SNAPSHOT_VERSION,
    DailyMemorySnapshot,
    ListeningMemory,
    local_day_utc_boundaries,
    timezone_for_name,
)


def _profile(local_date: date, timezone_name: str) -> DailyListeningProfile:
    start, end = local_day_utc_boundaries(
        local_date, timezone_for_name(timezone_name)
    )
    return DailyListeningProfile(
        start_datetime=start,
        end_datetime=end,
        total_estimated_listening_duration_ms=0,
        playback_count=0,
        unique_track_count=0,
        unique_track_ratio=0.0,
        top_track_share=0.0,
        genre_covered_duration_ms=0,
        genre_coverage=0.0,
        top_tracks=(),
        top_artists=(),
        top_albums=(),
        top_genres=(),
    )


def _snapshot(
    local_date: date,
    timezone_name: str = "Asia/Shanghai",
    *,
    version: int = CURRENT_SNAPSHOT_VERSION,
) -> DailyMemorySnapshot:
    return DailyMemorySnapshot(
        local_date=local_date,
        timezone_name=timezone_name,
        profile=_profile(local_date, timezone_name),
        generated_at=datetime(2026, 7, 24, 8, tzinfo=timezone.utc),
        is_closed=True,
        snapshot_version=version,
    )


def test_daily_snapshot_is_frozen_slotted_and_validates_timezone_and_version() -> None:
    snapshot = _snapshot(date(2026, 7, 22))

    assert not hasattr(snapshot, "__dict__")
    with pytest.raises(FrozenInstanceError):
        snapshot.is_closed = False  # type: ignore[misc]
    with pytest.raises(ValueError, match="IANA"):
        _snapshot(date(2026, 7, 22), "Invalid/Timezone")
    with pytest.raises(ValueError, match="positive"):
        _snapshot(date(2026, 7, 22), version=0)


def test_daily_snapshot_requires_aware_times_and_exact_profile_period() -> None:
    local_date = date(2026, 7, 22)
    with pytest.raises(ValueError, match="generated_at"):
        DailyMemorySnapshot(
            local_date,
            "UTC",
            _profile(local_date, "UTC"),
            datetime(2026, 7, 22),
            False,
            CURRENT_SNAPSHOT_VERSION,
        )

    wrong_profile = _profile(date(2026, 7, 23), "UTC")
    with pytest.raises(ValueError, match="exact local-calendar day"):
        DailyMemorySnapshot(
            local_date,
            "UTC",
            wrong_profile,
            datetime(2026, 7, 24, tzinfo=timezone.utc),
            True,
            CURRENT_SNAPSHOT_VERSION,
        )


def test_local_day_boundaries_preserve_dst_transition_length() -> None:
    zone = timezone_for_name("America/New_York")
    spring_start, spring_end = local_day_utc_boundaries(date(2026, 3, 8), zone)
    fall_start, fall_end = local_day_utc_boundaries(date(2026, 11, 1), zone)

    assert (spring_end - spring_start).total_seconds() == 23 * 60 * 60
    assert (fall_end - fall_start).total_seconds() == 25 * 60 * 60
    assert _snapshot(date(2026, 3, 8), "America/New_York").profile.end_datetime == (
        spring_end
    )


def test_listening_memory_allows_ordered_gaps_and_empty_exclusive_range() -> None:
    snapshots = (
        _snapshot(date(2026, 7, 20)),
        _snapshot(date(2026, 7, 22)),
    )
    memory = ListeningMemory(
        start_date=date(2026, 7, 20),
        end_date=date(2026, 7, 23),
        timezone_name="Asia/Shanghai",
        snapshots=snapshots,
        as_of=datetime(2026, 7, 24, tzinfo=timezone.utc),
    )
    empty = ListeningMemory(
        start_date=date(2026, 7, 24),
        end_date=date(2026, 7, 24),
        timezone_name="Asia/Shanghai",
        snapshots=(),
        as_of=datetime(2026, 7, 24, tzinfo=timezone.utc),
    )

    assert [snapshot.local_date for snapshot in memory.snapshots] == [
        date(2026, 7, 20),
        date(2026, 7, 22),
    ]
    assert empty.snapshots == ()
    assert not hasattr(memory, "__dict__")


@pytest.mark.parametrize(
    "snapshots,match",
    [
        (
            (_snapshot(date(2026, 7, 21)), _snapshot(date(2026, 7, 20))),
            "ordered",
        ),
        (
            (_snapshot(date(2026, 7, 20)), _snapshot(date(2026, 7, 20))),
            "duplicates",
        ),
        (
            (
                _snapshot(date(2026, 7, 20)),
                _snapshot(date(2026, 7, 21), "Asia/Tokyo"),
            ),
            "timezone",
        ),
        (
            (
                _snapshot(date(2026, 7, 20)),
                _snapshot(date(2026, 7, 21), version=2),
            ),
            "versions",
        ),
    ],
)
def test_listening_memory_rejects_invalid_snapshot_collections(
    snapshots: tuple[DailyMemorySnapshot, ...], match: str
) -> None:
    with pytest.raises(ValueError, match=match):
        ListeningMemory(
            start_date=date(2026, 7, 20),
            end_date=date(2026, 7, 23),
            timezone_name="Asia/Shanghai",
            snapshots=snapshots,
            as_of=datetime(2026, 7, 24, tzinfo=timezone.utc),
        )


def test_listening_memory_rejects_out_of_range_and_naive_as_of() -> None:
    with pytest.raises(ValueError, match="inside"):
        ListeningMemory(
            date(2026, 7, 20),
            date(2026, 7, 21),
            "Asia/Shanghai",
            (_snapshot(date(2026, 7, 21)),),
            datetime(2026, 7, 24, tzinfo=timezone.utc),
        )
    with pytest.raises(ValueError, match="as_of"):
        ListeningMemory(
            date(2026, 7, 20),
            date(2026, 7, 20),
            "Asia/Shanghai",
            (),
            datetime(2026, 7, 24),
        )
