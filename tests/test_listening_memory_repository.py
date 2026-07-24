"""SQLite integration tests for listening-memory persistence."""

from datetime import date, datetime, timezone
import json

import pytest

from music_ai.analytics import DailyListeningProfile
from music_ai.database.database import Database
from music_ai.memory import DailyMemorySnapshot, UnsupportedSnapshotVersionError
from music_ai.memory.models import local_day_utc_boundaries, timezone_for_name
from music_ai.repository.listening_memory_repository import (
    InvalidMemorySnapshotError,
    ListeningMemoryRepository,
)


def _database(tmp_path) -> Database:
    database = Database(tmp_path / "memory.db")
    database.initialize()
    return database


def _snapshot(
    local_date: date,
    *,
    timezone_name: str = "Asia/Shanghai",
    duration_ms: int = 100,
    generated_hour: int = 12,
    is_closed: bool = False,
    version: int = 1,
) -> DailyMemorySnapshot:
    start, end = local_day_utc_boundaries(
        local_date, timezone_for_name(timezone_name)
    )
    count = 1 if duration_ms else 0
    profile = DailyListeningProfile(
        start_datetime=start,
        end_datetime=end,
        total_estimated_listening_duration_ms=duration_ms,
        playback_count=count,
        unique_track_count=count,
        unique_track_ratio=float(count),
        top_track_share=0.0,
        genre_covered_duration_ms=0,
        genre_coverage=0.0,
        top_tracks=(),
        top_artists=(),
        top_albums=(),
        top_genres=(),
    )
    return DailyMemorySnapshot(
        local_date=local_date,
        timezone_name=timezone_name,
        profile=profile,
        generated_at=datetime(
            2026, 7, local_date.day, generated_hour, tzinfo=timezone.utc
        ),
        is_closed=is_closed,
        snapshot_version=version,
    )


def test_database_initialization_adds_memory_table_and_range_index(tmp_path) -> None:
    database = _database(tmp_path)

    with database.connection() as connection:
        tables = {
            str(row["name"])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        indexes = {
            str(row["name"])
            for row in connection.execute(
                "PRAGMA index_list(listening_memory_snapshots)"
            ).fetchall()
        }

    assert "listening_memory_snapshots" in tables
    assert "idx_listening_memory_range" in indexes


def test_store_load_and_open_day_upsert_are_deterministic(tmp_path) -> None:
    database = _database(tmp_path)
    repository = ListeningMemoryRepository(database)
    local_date = date(2026, 7, 22)
    original = _snapshot(local_date, duration_ms=100, generated_hour=10)
    replacement = _snapshot(
        local_date, duration_ms=200, generated_hour=11, is_closed=False
    )

    repository.store_snapshot(original)
    repository.store_snapshot(replacement)

    assert repository.load_snapshot(local_date, "Asia/Shanghai") == replacement
    with database.connection() as connection:
        count = connection.execute(
            "SELECT COUNT(*) AS count FROM listening_memory_snapshots"
        ).fetchone()
        row = connection.execute(
            "SELECT period_start_utc, period_end_utc, generated_at_utc "
            "FROM listening_memory_snapshots"
        ).fetchone()
    assert int(count["count"]) == 1
    assert row["period_start_utc"] == "2026-07-21T16:00:00+00:00"
    assert row["period_end_utc"] == "2026-07-22T16:00:00+00:00"
    assert row["generated_at_utc"] == "2026-07-22T11:00:00+00:00"


def test_missing_timezone_and_version_loads_remain_isolated(tmp_path) -> None:
    repository = ListeningMemoryRepository(_database(tmp_path))
    snapshot = _snapshot(date(2026, 7, 22))
    repository.store_snapshot(snapshot)

    assert repository.load_snapshot(date(2026, 7, 21), "Asia/Shanghai") is None
    assert repository.load_snapshot(date(2026, 7, 22), "Asia/Tokyo") is None
    assert repository.load_snapshot(date(2026, 7, 22), "Asia/Shanghai", 2) is None


def test_bounded_range_is_ordered_exclusive_sparse_and_side_effect_free(
    tmp_path,
) -> None:
    database = _database(tmp_path)
    repository = ListeningMemoryRepository(database)
    repository.store_snapshot(_snapshot(date(2026, 7, 22)))
    repository.store_snapshot(_snapshot(date(2026, 7, 20)))
    repository.store_snapshot(
        _snapshot(date(2026, 7, 21), timezone_name="Asia/Tokyo")
    )

    snapshots = repository.load_range(
        date(2026, 7, 20), date(2026, 7, 22), "Asia/Shanghai"
    )

    assert [snapshot.local_date for snapshot in snapshots] == [date(2026, 7, 20)]
    with database.connection() as connection:
        count = connection.execute(
            "SELECT COUNT(*) AS count FROM listening_memory_snapshots"
        ).fetchone()
    assert int(count["count"]) == 3


def test_delete_range_is_exclusive_idempotent_and_preserves_raw_history(
    tmp_path,
) -> None:
    database = _database(tmp_path)
    repository = ListeningMemoryRepository(database)
    for day in (20, 21, 22):
        repository.store_snapshot(_snapshot(date(2026, 7, day)))

    with database.connection() as connection:
        connection.execute(
            """
            INSERT INTO songs (
                spotify_id, name, artists, album, duration_ms, explicit, popularity
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("track", "Track", json.dumps(["Artist"]), "Album", 100, 0, None),
        )
        connection.execute(
            """
            INSERT INTO play_history (
                song_id, played_at, played_duration_ms, source
            ) VALUES (?, ?, ?, ?)
            """,
            ("track", "2026-07-20T00:00:00+00:00", None, "test"),
        )

    repository.delete_range(
        date(2026, 7, 20), date(2026, 7, 22), "Asia/Shanghai"
    )
    repository.delete_range(
        date(2026, 7, 20), date(2026, 7, 22), "Asia/Shanghai"
    )

    assert [
        snapshot.local_date
        for snapshot in repository.load_range(
            date(2026, 7, 20), date(2026, 7, 23), "Asia/Shanghai"
        )
    ] == [date(2026, 7, 22)]
    with database.connection() as connection:
        raw_count = connection.execute(
            "SELECT COUNT(*) AS count FROM play_history"
        ).fetchone()
    assert int(raw_count["count"]) == 1


def test_corrupted_payload_and_column_mismatch_raise_clear_cache_errors(
    tmp_path,
) -> None:
    database = _database(tmp_path)
    repository = ListeningMemoryRepository(database)
    snapshot = _snapshot(date(2026, 7, 22))
    repository.store_snapshot(snapshot)

    with database.connection() as connection:
        connection.execute(
            "UPDATE listening_memory_snapshots SET profile_payload = ?",
            ("{invalid",),
        )
    with pytest.raises(InvalidMemorySnapshotError, match="payload"):
        repository.load_snapshot(date(2026, 7, 22), "Asia/Shanghai")

    repository.store_snapshot(snapshot)
    with database.connection() as connection:
        connection.execute(
            "UPDATE listening_memory_snapshots SET generated_at_utc = ?",
            ("2020-01-01T00:00:00+00:00",),
        )
    with pytest.raises(InvalidMemorySnapshotError, match="columns"):
        repository.load_snapshot(date(2026, 7, 22), "Asia/Shanghai")


def test_failed_unsupported_store_does_not_replace_valid_snapshot(tmp_path) -> None:
    repository = ListeningMemoryRepository(_database(tmp_path))
    valid = _snapshot(date(2026, 7, 22))
    repository.store_snapshot(valid)

    with pytest.raises(UnsupportedSnapshotVersionError):
        repository.store_snapshot(_snapshot(date(2026, 7, 22), version=2))

    assert repository.load_snapshot(date(2026, 7, 22), "Asia/Shanghai") == valid
