"""Unit tests for Memory lifecycle coordination."""

from datetime import date, datetime, timezone

import pytest

from music_ai.analytics import DailyListeningProfile
from music_ai.memory import CURRENT_SNAPSHOT_VERSION, MemoryEngine


class FakeAnalytics:
    def __init__(self) -> None:
        self.calls: list[tuple[datetime, datetime]] = []

    def get_daily_listening_profile(
        self, start_datetime: datetime, end_datetime: datetime
    ) -> DailyListeningProfile:
        self.calls.append((start_datetime, end_datetime))
        return DailyListeningProfile(
            start_datetime=start_datetime.astimezone(timezone.utc),
            end_datetime=end_datetime.astimezone(timezone.utc),
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


class FakeRepository:
    def __init__(self) -> None:
        self.snapshots = {}
        self.stores = []
        self.loads = []

    def store_snapshot(self, snapshot) -> None:
        self.stores.append(snapshot)
        self.snapshots[
            (snapshot.local_date, snapshot.timezone_name, snapshot.snapshot_version)
        ] = snapshot

    def load_range(self, start_date, end_date, timezone_name, snapshot_version):
        self.loads.append(
            (start_date, end_date, timezone_name, snapshot_version)
        )
        return tuple(
            snapshot
            for key, snapshot in sorted(self.snapshots.items())
            if start_date <= key[0] < end_date
            and key[1] == timezone_name
            and key[2] == snapshot_version
        )


def _engine(
    *,
    now: datetime = datetime(2026, 7, 24, 8, tzinfo=timezone.utc),
    timezone_name: str = "Asia/Shanghai",
) -> tuple[MemoryEngine, FakeAnalytics, FakeRepository]:
    analytics = FakeAnalytics()
    repository = FakeRepository()
    engine = MemoryEngine(
        analytics,  # type: ignore[arg-type]
        repository,  # type: ignore[arg-type]
        timezone_name,
        clock=lambda: now,
    )
    return engine, analytics, repository


def test_capture_date_calls_analytics_with_exact_normal_day_and_stores_profile() -> None:
    engine, analytics, repository = _engine()

    snapshot = engine.capture_date(date(2026, 7, 24))

    assert analytics.calls == [
        (
            datetime(2026, 7, 23, 16, tzinfo=timezone.utc),
            datetime(2026, 7, 24, 16, tzinfo=timezone.utc),
        )
    ]
    assert snapshot.profile.start_datetime == analytics.calls[0][0]
    assert snapshot.profile.end_datetime == analytics.calls[0][1]
    assert snapshot.is_closed is False
    assert snapshot.snapshot_version == CURRENT_SNAPSHOT_VERSION
    assert repository.stores == [snapshot]


def test_capture_date_handles_dst_and_marks_historical_date_closed() -> None:
    engine, analytics, _ = _engine(
        now=datetime(2026, 3, 10, tzinfo=timezone.utc),
        timezone_name="America/New_York",
    )

    snapshot = engine.capture_date(date(2026, 3, 8))

    start, end = analytics.calls[0]
    assert (end - start).total_seconds() == 23 * 60 * 60
    assert snapshot.is_closed is True


def test_capture_current_day_uses_canonical_timezone_and_is_idempotent() -> None:
    engine, analytics, repository = _engine(
        now=datetime(2026, 7, 24, 16, 30, tzinfo=timezone.utc)
    )

    first = engine.capture_current_day()
    second = engine.capture_current_day()

    assert first.local_date == second.local_date == date(2026, 7, 25)
    assert len(analytics.calls) == 2
    assert len(repository.snapshots) == 1
    assert len(repository.stores) == 2


def test_load_range_is_sparse_side_effect_free_and_does_not_call_analytics() -> None:
    engine, analytics, repository = _engine()
    engine.capture_date(date(2026, 7, 20))
    engine.capture_date(date(2026, 7, 22))
    analytics.calls.clear()
    repository.stores.clear()

    memory = engine.load_range(date(2026, 7, 20), date(2026, 7, 23))

    assert [snapshot.local_date for snapshot in memory.snapshots] == [
        date(2026, 7, 20),
        date(2026, 7, 22),
    ]
    assert analytics.calls == []
    assert repository.stores == []
    assert repository.loads == [
        (
            date(2026, 7, 20),
            date(2026, 7, 23),
            "Asia/Shanghai",
            CURRENT_SNAPSHOT_VERSION,
        )
    ]


def test_rebuild_range_captures_exact_requested_dates_only() -> None:
    engine, analytics, repository = _engine()

    memory = engine.rebuild_range(date(2026, 7, 20), date(2026, 7, 23))

    assert [snapshot.local_date for snapshot in memory.snapshots] == [
        date(2026, 7, 20),
        date(2026, 7, 21),
        date(2026, 7, 22),
    ]
    assert len(analytics.calls) == len(repository.stores) == 3
    assert all(
        snapshot.snapshot_version == CURRENT_SNAPSHOT_VERSION
        for snapshot in memory.snapshots
    )


def test_empty_rebuild_and_invalid_ranges_are_deterministic() -> None:
    engine, analytics, repository = _engine()

    memory = engine.rebuild_range(date(2026, 7, 20), date(2026, 7, 20))

    assert memory.snapshots == ()
    assert analytics.calls == repository.stores == []
    with pytest.raises(ValueError, match="earlier"):
        engine.load_range(date(2026, 7, 21), date(2026, 7, 20))
    with pytest.raises(ValueError, match="earlier"):
        engine.rebuild_range(date(2026, 7, 21), date(2026, 7, 20))


def test_engine_rejects_invalid_timezone_and_naive_clock() -> None:
    with pytest.raises(ValueError, match="IANA"):
        _engine(timezone_name="Not/AZone")

    analytics = FakeAnalytics()
    repository = FakeRepository()
    engine = MemoryEngine(
        analytics,  # type: ignore[arg-type]
        repository,  # type: ignore[arg-type]
        "UTC",
        clock=lambda: datetime(2026, 7, 24),
    )
    with pytest.raises(ValueError, match="aware"):
        engine.capture_current_day()
