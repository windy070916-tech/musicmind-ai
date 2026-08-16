"""Raw-history contextual Analytics tests for Sprint 4A."""

from datetime import datetime, timezone
import inspect
import json

import pytest

from music_ai.analytics import ContextualListeningAnalytics, LocalClockSegment
from music_ai.analytics import contextual_analytics as contextual_module
from music_ai.database.database import Database


def _database(tmp_path, name: str = "musicmind.db") -> Database:
    database = Database(tmp_path / name)
    database.initialize()
    return database


def _insert_events(
    database: Database,
    events: tuple[tuple[str, str, str | None], ...],
) -> None:
    """Insert ``(played_at, artist_name, spotify_artist_id)`` fixtures."""
    with database.connection() as connection:
        for index, (played_at, artist_name, spotify_artist_id) in enumerate(events):
            song_id = f"song-{index}"
            connection.execute(
                """
                INSERT INTO songs (
                    spotify_id, name, artists, album, duration_ms, explicit, popularity
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    song_id,
                    f"Song {index}",
                    json.dumps((artist_name,)),
                    "Album",
                    180_000 + index,
                    0,
                    None,
                ),
            )
            if spotify_artist_id is not None:
                connection.execute(
                    "INSERT OR IGNORE INTO artists (spotify_id, name) VALUES (?, ?)",
                    (spotify_artist_id, artist_name),
                )
                connection.execute(
                    """
                    INSERT INTO song_artists (song_id, artist_id, credit_position)
                    VALUES (?, ?, 0)
                    """,
                    (song_id, spotify_artist_id),
                )
            connection.execute(
                """
                INSERT INTO play_history (
                    song_id, played_at, played_duration_ms, source
                ) VALUES (?, ?, ?, ?)
                """,
                (song_id, played_at, index * 1_000, "test"),
            )


def _counts(evidence) -> tuple[int, ...]:
    return tuple(item.event_count for item in evidence.segments)


def test_exact_adjacent_windows_exclude_open_local_day(tmp_path) -> None:
    database = _database(tmp_path)
    _insert_events(
        database,
        (
            ("2026-06-14T23:59:59+00:00", "Artist", "artist"),
            ("2026-06-15T00:00:00+00:00", "Artist", "artist"),
            ("2026-07-15T00:00:00+00:00", "Artist", "artist"),
            ("2026-08-13T23:59:59+00:00", "Artist", "artist"),
            ("2026-08-14T00:00:00+00:00", "Artist", "artist"),
        ),
    )

    evidence = ContextualListeningAnalytics(database).analyze(
        timezone_name="UTC",
        as_of=datetime(2026, 8, 14, 12, tzinfo=timezone.utc),
    )

    assert (
        evidence.previous_window.start_date.isoformat(),
        evidence.previous_window.end_date.isoformat(),
    ) == ("2026-06-15", "2026-07-15")
    assert (
        evidence.current_window.start_date.isoformat(),
        evidence.current_window.end_date.isoformat(),
    ) == ("2026-07-15", "2026-08-14")
    assert evidence.previous_window.event_count == 1
    assert evidence.current_window.event_count == 2


def test_all_four_half_open_clock_boundaries_are_exact(tmp_path) -> None:
    database = _database(tmp_path)
    _insert_events(
        database,
        tuple(
            (f"2026-08-01T{clock}+00:00", "Artist", "artist")
            for clock in (
                "00:00:00",
                "05:59:59",
                "06:00:00",
                "11:59:59",
                "12:00:00",
                "17:59:59",
                "18:00:00",
                "23:59:59",
            )
        ),
    )

    evidence = ContextualListeningAnalytics(database).analyze(
        timezone_name="UTC",
        as_of=datetime(2026, 8, 14, 12, tzinfo=timezone.utc),
    )

    assert tuple(item.segment for item in evidence.current_window.segments) == tuple(
        LocalClockSegment
    )
    assert _counts(evidence.current_window) == (2, 2, 2, 2)
    assert tuple(item.listening_day_count for item in evidence.current_window.segments) == (
        1,
        1,
        1,
        1,
    )


def test_timezone_conversion_precedes_segment_and_local_date_assignment(tmp_path) -> None:
    database = _database(tmp_path)
    _insert_events(
        database,
        (("2026-07-31T22:00:00+00:00", "Artist", "artist"),),
    )

    evidence = ContextualListeningAnalytics(database).analyze(
        timezone_name="Asia/Shanghai",
        as_of=datetime(2026, 8, 14, 4, tzinfo=timezone.utc),
    )

    assert evidence.current_window.event_count == 1
    assert _counts(evidence.current_window) == (0, 1, 0, 0)


def test_sql_window_bounds_compare_instants_not_iso_text_offsets(tmp_path) -> None:
    database = _database(tmp_path)
    _insert_events(
        database,
        (
            # Current starts at 2026-07-15 00:00 +08:00. This equivalent
            # negative-offset instant belongs exactly on the inclusive boundary.
            ("2026-07-14T11:00:00-05:00", "Artist", "artist"),
            ("2026-07-14T10:59:59-05:00", "Artist", "artist"),
            # Current ends at 2026-08-14 00:00 +08:00. The 23:00 event belongs;
            # the local-midnight event is the excluded open-day boundary.
            ("2026-08-13T23:00:00+08:00", "Artist", "artist"),
            ("2026-08-14T00:00:00+08:00", "Artist", "artist"),
        ),
    )

    current = ContextualListeningAnalytics(database).analyze(
        timezone_name="Asia/Shanghai",
        as_of=datetime(2026, 8, 14, 4, tzinfo=timezone.utc),
    ).current_window

    assert current.event_count == 2
    assert _counts(current) == (1, 0, 0, 1)


def test_dst_spring_forward_uses_actual_local_clocks(tmp_path) -> None:
    database = _database(tmp_path)
    _insert_events(
        database,
        (
            # 00:30 EST and 06:00 EDT on the spring-forward date.
            ("2026-03-08T05:30:00+00:00", "Artist", "artist"),
            ("2026-03-08T10:00:00+00:00", "Artist", "artist"),
        ),
    )

    evidence = ContextualListeningAnalytics(database).analyze(
        timezone_name="America/New_York",
        as_of=datetime(2026, 4, 1, 16, tzinfo=timezone.utc),
    )

    assert _counts(evidence.current_window) == (1, 1, 0, 0)
    assert evidence.current_window.listening_day_count == 1


def test_dst_fall_back_counts_both_recorded_events_without_splitting(tmp_path) -> None:
    database = _database(tmp_path)
    _insert_events(
        database,
        (
            # Both recorded instants resolve to local 01:30, on opposite folds.
            ("2026-11-01T05:30:00+00:00", "Artist", "artist"),
            ("2026-11-01T06:30:00+00:00", "Artist", "artist"),
        ),
    )

    evidence = ContextualListeningAnalytics(database).analyze(
        timezone_name="America/New_York",
        as_of=datetime(2026, 11, 15, 17, tzinfo=timezone.utc),
    )

    assert _counts(evidence.current_window) == (2, 0, 0, 0)
    assert evidence.current_window.segments[0].listening_day_count == 1


def test_contextual_results_ignore_estimated_and_recorded_durations(tmp_path) -> None:
    database = _database(tmp_path)
    _insert_events(
        database,
        (
            ("2026-08-01T05:59:00+00:00", "Artist", "artist"),
            ("2026-08-01T06:01:00+00:00", "Artist", "artist"),
        ),
    )
    analytics = ContextualListeningAnalytics(database)
    as_of = datetime(2026, 8, 14, 12, tzinfo=timezone.utc)
    before = analytics.analyze(timezone_name="UTC", as_of=as_of)

    with database.connection() as connection:
        connection.execute("UPDATE songs SET duration_ms = 99999999")
        connection.execute("UPDATE play_history SET played_duration_ms = NULL")

    after = analytics.analyze(timezone_name="UTC", as_of=as_of)
    assert before == after


def test_primary_artist_distributions_are_id_first_and_window_relative(tmp_path) -> None:
    database = _database(tmp_path)
    _insert_events(
        database,
        (
            ("2026-08-01T01:00:00+00:00", "Artist A", "artist-a"),
            ("2026-08-02T07:00:00+00:00", "Artist A", "artist-a"),
            ("2026-08-02T13:00:00+00:00", "Legacy B", None),
        ),
    )

    current = ContextualListeningAnalytics(database).analyze(
        timezone_name="UTC",
        as_of=datetime(2026, 8, 14, 12, tzinfo=timezone.utc),
    ).current_window

    assert tuple(item.identity for item in current.artists) == (
        ("legacy", "legacy b"),
        ("spotify", "artist-a"),
    )
    spotify_artist = current.artists[1]
    assert spotify_artist.event_count == 2
    assert spotify_artist.listening_day_count == 2
    assert tuple(item.event_count for item in spotify_artist.segments) == (1, 1, 0, 0)


def test_results_are_independent_of_insertion_order(tmp_path) -> None:
    events = (
        ("2026-08-01T01:00:00+00:00", "Artist A", "artist-a"),
        ("2026-08-02T07:00:00+00:00", "Artist B", "artist-b"),
        ("2026-08-03T18:00:00+00:00", "Artist A", "artist-a"),
    )
    forward = _database(tmp_path, "forward.db")
    reverse = _database(tmp_path, "reverse.db")
    _insert_events(forward, events)
    _insert_events(reverse, tuple(reversed(events)))
    as_of = datetime(2026, 8, 14, 12, tzinfo=timezone.utc)

    assert ContextualListeningAnalytics(forward).analyze(
        timezone_name="UTC", as_of=as_of
    ) == ContextualListeningAnalytics(reverse).analyze(
        timezone_name="UTC", as_of=as_of
    )


def test_sparse_raw_history_has_no_memory_gap_or_completeness_inference(tmp_path) -> None:
    database = _database(tmp_path)
    _insert_events(
        database,
        (("2026-08-01T01:00:00+00:00", "Artist", "artist"),),
    )

    window = ContextualListeningAnalytics(database).analyze(
        timezone_name="UTC",
        as_of=datetime(2026, 8, 14, 12, tzinfo=timezone.utc),
    ).current_window

    assert window.listening_day_count == 1
    assert not hasattr(window, "gap_dates")
    source = inspect.getsource(contextual_module)
    assert "music_ai.memory" not in source


@pytest.mark.parametrize(
    ("timezone_name", "as_of", "message"),
    (
        ("Not/A-Timezone", datetime(2026, 8, 14, tzinfo=timezone.utc), "Unknown"),
        ("UTC", datetime(2026, 8, 14), "timezone-aware"),
    ),
)
def test_invalid_runtime_context_is_rejected(
    tmp_path, timezone_name: str, as_of: datetime, message: str
) -> None:
    database = _database(tmp_path)
    with pytest.raises(ValueError, match=message):
        ContextualListeningAnalytics(database).analyze(
            timezone_name=timezone_name, as_of=as_of
        )
