from datetime import datetime, timedelta, timezone
import sqlite3

import requests

from main import _enrich_artist_metadata, _persist_song_metadata
from music_ai.database.database import Database
from music_ai.models.artist import Artist
from music_ai.models.song import Song
from music_ai.models.song_artist import SongArtist
from music_ai.parser.spotify_parser import parse_artist_metadata, parse_song
from music_ai.repository.artist_repository import ArtistRepository
from music_ai.repository.song_artist_repository import SongArtistRepository
from music_ai.repository.song_repository import SongRepository
from music_ai.spotify.auth import SpotifyToken
from music_ai.spotify.client import SpotifyClient


def test_parser_preserves_multiple_artist_and_album_identifiers() -> None:
    song = parse_song(
        {
            "id": "song-1",
            "name": "Collaboration",
            "artists": [
                {"id": "artist-a", "name": "Artist A"},
                {"id": "artist-b", "name": "Artist B"},
            ],
            "album": {"id": "album-1", "name": "Album"},
            "duration_ms": 180_000,
            "explicit": False,
            "popularity": 42,
        }
    )

    assert song.artists == ("Artist A", "Artist B")
    assert song.artist_ids == ("artist-a", "artist-b")
    assert song.album_id == "album-1"


def test_artist_repository_caches_empty_genres_and_song_credits(tmp_path) -> None:
    database = Database(tmp_path / "musicmind.db")
    database.initialize()
    song = Song(
        spotify_id="song-1",
        name="Song",
        artists=("Artist A", "Artist B"),
        album="Album",
        duration_ms=180_000,
        explicit=False,
        popularity=None,
        artist_ids=("artist-a", "artist-b"),
        album_id="album-1",
    )
    SongRepository(database).save(song)

    artist_repository = ArtistRepository(database)
    artist_repository.save_all(
        [Artist("artist-a", "Artist A"), Artist("artist-b", "Artist B")]
    )
    SongArtistRepository(database).save_all(
        [
            SongArtist("song-1", "artist-a", 0),
            SongArtist("song-1", "artist-b", 1),
        ]
    )
    refreshed_at = datetime(2026, 7, 20, tzinfo=timezone.utc)
    artist_repository.save_metadata(Artist("artist-a", "Artist A", ("rap", "hip hop")), refreshed_at)
    artist_repository.save_metadata(Artist("artist-b", "Artist B"), refreshed_at)

    assert artist_repository.find_by_id("artist-a") == Artist(
        "artist-a", "Artist A", ("hip hop", "rap")
    )
    assert artist_repository.find_by_id("artist-b") == Artist("artist-b", "Artist B")
    assert artist_repository.requiring_metadata(
        ["artist-a", "artist-b"], refreshed_at - timedelta(days=1)
    ) == []
    assert SongArtistRepository(database).find_for_song("song-1") == [
        SongArtist("song-1", "artist-a", 0),
        SongArtist("song-1", "artist-b", 1),
    ]


def test_duplicate_metadata_persistence_does_not_duplicate_rows(tmp_path) -> None:
    database = Database(tmp_path / "musicmind.db")
    database.initialize()
    SongRepository(database).save(
        Song(
            spotify_id="song-1",
            name="Song",
            artists=("Artist A",),
            album="Album",
            duration_ms=180_000,
            explicit=False,
            popularity=None,
            artist_ids=("artist-a",),
        )
    )
    artist_repository = ArtistRepository(database)
    artist_repository.save_all([Artist("artist-a", "Artist A")])
    song_artist_repository = SongArtistRepository(database)
    credit = SongArtist("song-1", "artist-a", 0)
    song_artist_repository.save_all([credit])
    song_artist_repository.save_all([credit])

    refreshed_at = datetime(2026, 7, 20, tzinfo=timezone.utc)
    artist_repository.save_metadata(Artist("artist-a", "Artist A", ("rap", "rap")), refreshed_at)
    artist_repository.save_metadata(Artist("artist-a", "Artist A", ("rap",)), refreshed_at)

    with database.connection() as connection:
        credit_count = connection.execute("SELECT COUNT(*) AS count FROM song_artists").fetchone()
        genre_count = connection.execute("SELECT COUNT(*) AS count FROM artist_genres").fetchone()

    assert int(credit_count["count"]) == 1
    assert int(genre_count["count"]) == 1


def test_existing_database_migrates_without_losing_listening_history(tmp_path) -> None:
    database_path = tmp_path / "legacy.db"
    with sqlite3.connect(database_path) as connection:
        connection.executescript(
            """
            CREATE TABLE songs (
                spotify_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                artists TEXT NOT NULL,
                album TEXT NOT NULL,
                duration_ms INTEGER NOT NULL,
                explicit INTEGER NOT NULL,
                popularity INTEGER
            );
            CREATE TABLE play_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                song_id TEXT NOT NULL,
                played_at TEXT NOT NULL,
                played_duration_ms INTEGER,
                source TEXT NOT NULL,
                UNIQUE (song_id, played_at)
            );
            INSERT INTO songs VALUES ('song-1', 'Song', '["Artist"]', 'Album', 180000, 0, 5);
            INSERT INTO play_history (song_id, played_at, played_duration_ms, source)
            VALUES ('song-1', '2026-07-20T00:00:00+00:00', NULL, 'spotify');
            """
        )

    database = Database(database_path)
    database.initialize()

    with database.connection() as connection:
        song_columns = {
            str(row["name"])
            for row in connection.execute("PRAGMA table_info(songs)").fetchall()
        }
        history_count = connection.execute("SELECT COUNT(*) AS count FROM play_history").fetchone()
        table_names = {
            str(row["name"])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }

    assert "album_id" in song_columns
    assert int(history_count["count"]) == 1
    assert {"artists", "song_artists", "artist_genres"} <= table_names


def test_artist_metadata_parser_and_client_failures_are_non_blocking(monkeypatch) -> None:
    assert parse_artist_metadata({"id": "artist-a", "name": "Artist A"}) == Artist(
        "artist-a", "Artist A"
    )
    assert parse_artist_metadata({"id": "artist-a"}) is None

    client = SpotifyClient(SpotifyToken("token", "Bearer", 3600))

    def fail_request(*_args, **_kwargs):
        raise requests.ConnectionError("offline")

    monkeypatch.setattr(client, "_request", fail_request)

    assert client.artists(["artist-a", "artist-a"]) == []


def test_artist_client_deduplicates_identifiers_before_one_batch_request(monkeypatch) -> None:
    client = SpotifyClient(SpotifyToken("token", "Bearer", 3600))
    captured_params: list[dict[str, str] | None] = []

    def fake_request(_method, _endpoint, params=None):
        captured_params.append(params)
        return {"artists": [{"id": "artist-a", "name": "Artist A", "genres": []}]}

    monkeypatch.setattr(client, "_request", fake_request)

    assert client.artists(["artist-a", "artist-b", "artist-a"]) == [
        {"id": "artist-a", "name": "Artist A", "genres": []}
    ]
    assert captured_params == [{"ids": "artist-a,artist-b"}]


def test_metadata_synchronization_persists_and_then_reuses_artist_cache(tmp_path) -> None:
    class FakeArtistClient:
        def __init__(self) -> None:
            self.calls: list[list[str]] = []

        def artists(self, spotify_ids: list[str]) -> list[dict[str, object]]:
            self.calls.append(spotify_ids)
            return [
                {"id": "artist-a", "name": "Artist A", "genres": ["rap", "hip hop"]},
                {"id": "artist-b", "name": "Artist B", "genres": []},
            ]

    database = Database(tmp_path / "musicmind.db")
    database.initialize()
    songs = [
        Song(
            spotify_id="song-1",
            name="Song",
            artists=("Artist A", "Artist B"),
            album="Album",
            duration_ms=180_000,
            explicit=False,
            popularity=None,
            artist_ids=("artist-a", "artist-b"),
            album_id="album-1",
        )
    ]
    client = FakeArtistClient()

    _persist_song_metadata(database, songs)
    _enrich_artist_metadata(client, database, songs)
    _enrich_artist_metadata(client, database, songs)

    assert client.calls == [["artist-a", "artist-b"]]
    assert ArtistRepository(database).find_by_id("artist-a") == Artist(
        "artist-a", "Artist A", ("hip hop", "rap")
    )
    assert ArtistRepository(database).find_by_id("artist-b") == Artist("artist-b", "Artist B")
