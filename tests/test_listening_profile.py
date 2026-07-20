"""Regression tests for deterministic daily listening-profile analytics."""

from datetime import datetime, timedelta, timezone
import json

import pytest

from music_ai.analytics import ListeningAnalytics
from music_ai.analytics.listening_analytics import _build_daily_profile
from music_ai.database.database import Database


START = datetime(2026, 7, 19, tzinfo=timezone.utc)
END = datetime(2026, 7, 20, tzinfo=timezone.utc)


def _database(tmp_path) -> Database:
    database = Database(tmp_path / "musicmind.db")
    database.initialize()
    return database


def _song(
    database: Database,
    spotify_id: str,
    *,
    name: str | None = None,
    artists: tuple[str, ...] = ("Legacy Artist",),
    album: str = "Album",
    album_id: str | None = None,
    duration_ms: int = 100,
) -> None:
    with database.connection() as connection:
        connection.execute(
            """
            INSERT INTO songs (
                spotify_id, name, artists, album, album_id, duration_ms, explicit, popularity
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (spotify_id, name or spotify_id, json.dumps(artists), album, album_id, duration_ms, 0, None),
        )


def _play(
    database: Database,
    song_id: str,
    *,
    played_at: datetime = START + timedelta(hours=1),
    duration_ms: int | None = None,
) -> None:
    with database.connection() as connection:
        connection.execute(
            """
            INSERT INTO play_history (song_id, played_at, played_duration_ms, source)
            VALUES (?, ?, ?, ?)
            """,
            (song_id, played_at.isoformat(), duration_ms, "test"),
        )


def _artist(
    database: Database, artist_id: str, name: str, genres: tuple[str, ...] = ()
) -> None:
    with database.connection() as connection:
        connection.execute("INSERT INTO artists (spotify_id, name) VALUES (?, ?)", (artist_id, name))
        connection.executemany(
            "INSERT INTO artist_genres (artist_id, genre) VALUES (?, ?)",
            [(artist_id, genre) for genre in genres],
        )


def _credit(database: Database, song_id: str, artist_id: str, position: int) -> None:
    with database.connection() as connection:
        connection.execute(
            "INSERT INTO song_artists (song_id, artist_id, credit_position) VALUES (?, ?, ?)",
            (song_id, artist_id, position),
        )


def _profile(database: Database, start: datetime = START, end: datetime = END):
    return ListeningAnalytics(database).get_daily_listening_profile(start, end)


def test_empty_profile_has_zero_metrics_and_immutable_collections(tmp_path) -> None:
    profile = _profile(_database(tmp_path))

    assert profile.playback_count == 0
    assert profile.total_estimated_listening_duration_ms == 0
    assert profile.unique_track_ratio == profile.top_track_share == profile.genre_coverage == 0.0
    assert profile.top_tracks == profile.top_artists == profile.top_albums == profile.top_genres == ()


def test_profile_uses_playback_duration_then_catalog_estimate_and_metrics(tmp_path) -> None:
    database = _database(tmp_path)
    _song(database, "track-a", name="Track A", duration_ms=100)
    _play(database, "track-a", duration_ms=60)
    _play(database, "track-a", played_at=START + timedelta(hours=2))

    profile = _profile(database)

    assert profile.total_estimated_listening_duration_ms == 160
    assert profile.playback_count == profile.top_tracks[0].play_count == 2
    assert profile.unique_track_count == 1
    assert profile.unique_track_ratio == 0.5
    assert profile.top_track_share == 1.0
    assert profile.top_tracks[0].estimated_listening_duration_ms == 160


def test_track_ranking_uses_all_declared_tie_breakers(tmp_path) -> None:
    database = _database(tmp_path)
    _song(database, "id-b", name="Same", artists=("B",), duration_ms=100)
    _song(database, "id-a", name="Same", artists=("A",), duration_ms=100)
    _song(database, "id-c", name="Earlier", artists=("Z",), duration_ms=100)
    _play(database, "id-b", played_at=START + timedelta(hours=1))
    _play(database, "id-a", played_at=START + timedelta(hours=2))
    _play(database, "id-c", played_at=START + timedelta(hours=3))

    assert [track.spotify_track_id for track in _profile(database).top_tracks] == [
        "id-c",
        "id-a",
        "id-b",
    ]


def test_normalized_primary_artist_wins_and_conserves_artist_duration(tmp_path) -> None:
    database = _database(tmp_path)
    _song(database, "track", artists=("Legacy First", "Featured"), duration_ms=101)
    _artist(database, "featured", "Featured", ("pop",))
    _artist(database, "primary", "Primary", ("rock",))
    _credit(database, "track", "featured", 1)
    _credit(database, "track", "primary", 0)
    _play(database, "track")

    profile = _profile(database)

    assert [(artist.spotify_artist_id, artist.name) for artist in profile.top_artists] == [
        ("primary", "Primary")
    ]
    assert sum(artist.estimated_listening_duration_ms for artist in profile.top_artists) == 101
    assert [(genre.genre, genre.estimated_listening_duration_ms) for genre in profile.top_genres] == [
        ("rock", 101)
    ]


def test_primary_artist_uses_legacy_then_unknown_fallback(tmp_path) -> None:
    database = _database(tmp_path)
    _song(database, "legacy", artists=("", "Legacy Artist"), duration_ms=10)
    _song(database, "unknown", artists=(), duration_ms=10)
    _play(database, "legacy")
    _play(database, "unknown", played_at=START + timedelta(hours=2))

    assert [(artist.spotify_artist_id, artist.name) for artist in _profile(database).top_artists] == [
        (None, "Legacy Artist"),
        (None, "Unknown artist"),
    ]


def test_album_identity_groups_by_id_and_falls_back_to_album_and_primary_artist(tmp_path) -> None:
    database = _database(tmp_path)
    _song(database, "one", album="Different title", album_id="album-id", duration_ms=10)
    _song(database, "two", album="Another title", album_id="album-id", duration_ms=10)
    _song(database, "three", album="Legacy Album", artists=("A",), duration_ms=10)
    _song(database, "four", album="Legacy Album", artists=("B",), duration_ms=10)
    _song(database, "five", album=" ", duration_ms=10)
    for hour, song_id in enumerate(("one", "two", "three", "four", "five"), start=1):
        _play(database, song_id, played_at=START + timedelta(hours=hour))

    albums = _profile(database).top_albums
    assert [(album.spotify_album_id, album.name, album.play_count) for album in albums] == [
        ("album-id", "Another title", 2),
        (None, "Legacy Album", 1),
        (None, "Legacy Album", 1),
        (None, "Unknown album", 1),
    ]


def test_genres_are_deduplicated_sorted_and_receive_exact_integer_remainder(tmp_path) -> None:
    database = _database(tmp_path)
    _song(database, "track", duration_ms=5)
    _artist(database, "artist", "Artist", ("z", "a", " z ", "m"))
    _credit(database, "track", "artist", 0)
    _play(database, "track")

    profile = _profile(database)

    assert [(genre.genre, genre.estimated_listening_duration_ms) for genre in profile.top_genres] == [
        ("a", 2),
        ("m", 2),
        ("z", 1),
    ]
    assert sum(genre.estimated_listening_duration_ms for genre in profile.top_genres) == 5
    assert profile.genre_covered_duration_ms == 5
    assert profile.genre_coverage == 1.0


def test_missing_genres_and_missing_artist_ids_are_uncovered(tmp_path) -> None:
    database = _database(tmp_path)
    _song(database, "legacy", duration_ms=50)
    _song(database, "metadata", duration_ms=50)
    _artist(database, "artist", "Artist")
    _credit(database, "metadata", "artist", 0)
    _play(database, "legacy")
    _play(database, "metadata", played_at=START + timedelta(hours=2))

    profile = _profile(database)

    assert profile.genre_covered_duration_ms == 0
    assert profile.genre_coverage == 0.0
    assert profile.top_genres == ()


def test_negative_and_zero_durations_are_clamped_without_invalid_shares(tmp_path) -> None:
    database = _database(tmp_path)
    _song(database, "negative", duration_ms=-5)
    _song(database, "zero", duration_ms=0)
    _play(database, "negative")
    _play(database, "zero", played_at=START + timedelta(hours=2), duration_ms=-3)

    profile = _profile(database)

    assert profile.total_estimated_listening_duration_ms == 0
    assert profile.top_track_share == 0.0
    assert [track.share for track in profile.top_tracks] == [0.0, 0.0]


def test_profile_uses_inclusive_start_exclusive_end_and_converts_utc(tmp_path) -> None:
    database = _database(tmp_path)
    _song(database, "track", duration_ms=10)
    _play(database, "track", played_at=START)
    _play(database, "track", played_at=END)

    china_start = START.astimezone(timezone(timedelta(hours=8)))
    china_end = END.astimezone(timezone(timedelta(hours=8)))
    profile = _profile(database, china_start, china_end)

    assert profile.playback_count == 1
    assert profile.start_datetime == START
    assert profile.end_datetime == END


def test_profile_requires_aware_datetimes_and_creates_played_at_index(tmp_path) -> None:
    database = _database(tmp_path)

    with pytest.raises(ValueError, match="timezone-aware"):
        _profile(database, datetime(2026, 7, 19), END)

    with database.connection() as connection:
        indexes = {
            str(row["name"])
            for row in connection.execute("PRAGMA index_list(play_history)").fetchall()
        }
    assert "idx_play_history_played_at" in indexes


def _profile_row(
    *,
    track_id: str,
    artist_names: tuple[str, ...],
    primary_artist_id: str | None,
    primary_artist_name: str | None,
    album_name: str,
    album_id: str | None,
    duration_ms: int,
) -> dict[str, object]:
    """Create one aggregation row with independently varying persisted metadata."""
    return {
        "spotify_id": track_id,
        "name": track_id,
        "artists": json.dumps(artist_names),
        "album": album_name,
        "album_id": album_id,
        "resolved_duration_ms": duration_ms,
        "primary_artist_id": primary_artist_id,
        "primary_artist_name": primary_artist_name,
    }


def _profile_from_rows(rows: list[dict[str, object]]):
    return _build_daily_profile(START, END, rows, {})


def test_spotify_artist_identity_ignores_name_variations_and_is_order_independent() -> None:
    rows = [
        _profile_row(
            track_id="one",
            artist_names=("Zulu Artist",),
            primary_artist_id="artist-id",
            primary_artist_name="Zulu Artist",
            album_name="Album",
            album_id=None,
            duration_ms=40,
        ),
        _profile_row(
            track_id="two",
            artist_names=("Alpha Artist",),
            primary_artist_id="artist-id",
            primary_artist_name="Alpha Artist",
            album_name="Album",
            album_id=None,
            duration_ms=60,
        ),
    ]

    profile = _profile_from_rows(rows)
    reversed_profile = _profile_from_rows(list(reversed(rows)))

    assert len(profile.top_artists) == 1
    assert profile.top_artists[0].spotify_artist_id == "artist-id"
    assert profile.top_artists[0].name == "Alpha Artist"
    assert profile.top_artists[0].play_count == 2
    assert profile.top_artists[0].estimated_listening_duration_ms == 100
    assert sum(artist.estimated_listening_duration_ms for artist in profile.top_artists) == 100
    assert reversed_profile.top_artists == profile.top_artists


def test_spotify_album_display_name_is_order_independent() -> None:
    rows = [
        _profile_row(
            track_id="one",
            artist_names=("Artist",),
            primary_artist_id="artist-id",
            primary_artist_name="Artist",
            album_name="Zulu Album",
            album_id="album-id",
            duration_ms=40,
        ),
        _profile_row(
            track_id="two",
            artist_names=("Artist",),
            primary_artist_id="artist-id",
            primary_artist_name="Artist",
            album_name="Alpha Album",
            album_id="album-id",
            duration_ms=60,
        ),
    ]

    profile = _profile_from_rows(rows)
    reversed_profile = _profile_from_rows(list(reversed(rows)))

    assert len(profile.top_albums) == 1
    assert profile.top_albums[0].spotify_album_id == "album-id"
    assert profile.top_albums[0].name == "Alpha Album"
    assert profile.top_albums[0].play_count == 2
    assert profile.top_albums[0].estimated_listening_duration_ms == 100
    assert reversed_profile.top_albums == profile.top_albums


def test_legacy_artist_name_identity_and_album_primary_artist_identity_remain_distinct() -> None:
    rows = [
        _profile_row(
            track_id="one",
            artist_names=("Same Artist",),
            primary_artist_id=None,
            primary_artist_name=None,
            album_name="Shared Album",
            album_id=None,
            duration_ms=10,
        ),
        _profile_row(
            track_id="two",
            artist_names=("same artist",),
            primary_artist_id=None,
            primary_artist_name=None,
            album_name="Shared Album",
            album_id=None,
            duration_ms=20,
        ),
        _profile_row(
            track_id="three",
            artist_names=("Other Artist",),
            primary_artist_id=None,
            primary_artist_name=None,
            album_name="Shared Album",
            album_id=None,
            duration_ms=30,
        ),
    ]

    profile = _profile_from_rows(rows)

    assert [(artist.name, artist.play_count, artist.estimated_listening_duration_ms) for artist in profile.top_artists] == [
        ("Same Artist", 2, 30),
        ("Other Artist", 1, 30),
    ]
    assert [(album.name, album.play_count) for album in profile.top_albums] == [
        ("Shared Album", 2),
        ("Shared Album", 1),
    ]
