from datetime import datetime, timezone
import json

import pytest

from music_ai.analytics.listening_analytics import ListeningAnalytics
from music_ai.database.database import Database


def test_listening_summary_aggregates_duration_rankings(tmp_path) -> None:
    database = Database(tmp_path / "musicmind.db")
    database.initialize()

    with database.connection() as connection:
        connection.execute(
            """
            INSERT INTO songs (
                spotify_id, name, artists, album, duration_ms, explicit, popularity
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("song-a", "Song A", json.dumps(("Kanye West",)), "Album", 240_000, 0, 80),
        )
        connection.execute(
            """
            INSERT INTO songs (
                spotify_id, name, artists, album, duration_ms, explicit, popularity
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "song-b",
                "Song B",
                json.dumps(("Kanye West", "Jay-Z")),
                "Album",
                300_000,
                0,
                75,
            ),
        )
        connection.execute(
            """
            INSERT INTO play_history (
                song_id, played_at, played_duration_ms, source
            ) VALUES (?, ?, ?, ?)
            """,
            ("song-a", "2026-07-19T01:00:00+00:00", 120_000, "test"),
        )
        connection.execute(
            """
            INSERT INTO play_history (
                song_id, played_at, played_duration_ms, source
            ) VALUES (?, ?, ?, ?)
            """,
            ("song-b", "2026-07-19T02:00:00+00:00", None, "test"),
        )

    summary = ListeningAnalytics(database).get_listening_summary(
        datetime(2026, 7, 19, tzinfo=timezone.utc),
        datetime(2026, 7, 20, tzinfo=timezone.utc),
    )

    assert summary.total_listening_time_ms == 420_000
    assert summary.playback_count == 2
    assert [song.name for song in summary.top_songs] == ["Song B", "Song A"]
    assert summary.top_artists[0].name == "Kanye West"
    assert summary.top_artists[0].listening_time_ms == 420_000
    assert summary.top_artists[1].name == "Jay-Z"
    assert summary.top_artists[1].listening_time_ms == 300_000


def test_listening_summary_requires_aware_datetimes(tmp_path) -> None:
    database = Database(tmp_path / "musicmind.db")
    database.initialize()

    with pytest.raises(ValueError, match="timezone-aware"):
        ListeningAnalytics(database).get_listening_summary(
            datetime(2026, 7, 19),
            datetime(2026, 7, 20),
        )
