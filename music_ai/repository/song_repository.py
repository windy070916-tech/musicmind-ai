"""Repository for persisting MusicMind songs."""

import json
import sqlite3

from music_ai.database.database import Database
from music_ai.models.song import Song


class SongRepository:
    """Store and retrieve :class:`Song` domain models."""

    def __init__(self, database: Database) -> None:
        """Create a song repository backed by the supplied database."""
        self._database = database

    def save(self, song: Song) -> None:
        """Insert a song or update its stored attributes."""
        with self._database.connection() as connection:
            self._save(connection, song)

    def save_all(self, songs: list[Song]) -> None:
        """Insert or update multiple songs in one transaction."""
        with self._database.connection() as connection:
            for song in songs:
                self._save(connection, song)

    def find_by_id(self, spotify_id: str) -> Song | None:
        """Return a song by Spotify identifier, if it exists."""
        with self._database.connection() as connection:
            row = connection.execute(
                "SELECT spotify_id, name, artists, album, duration_ms, explicit, popularity "
                "FROM songs WHERE spotify_id = ?",
                (spotify_id,),
            ).fetchone()

        return _song_from_row(row) if row is not None else None

    def find_all(self) -> list[Song]:
        """Return every stored song."""
        with self._database.connection() as connection:
            rows = connection.execute(
                "SELECT spotify_id, name, artists, album, duration_ms, explicit, popularity "
                "FROM songs ORDER BY name"
            ).fetchall()

        return [_song_from_row(row) for row in rows]

    def _save(self, connection: sqlite3.Connection, song: Song) -> None:
        """Persist a song using an existing transaction."""
        connection.execute(
            """
            INSERT INTO songs (
                spotify_id, name, artists, album, duration_ms, explicit, popularity
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(spotify_id) DO UPDATE SET
                name = excluded.name,
                artists = excluded.artists,
                album = excluded.album,
                duration_ms = excluded.duration_ms,
                explicit = excluded.explicit,
                popularity = excluded.popularity
            """,
            (
                song.spotify_id,
                song.name,
                json.dumps(song.artists),
                song.album,
                song.duration_ms,
                int(song.explicit),
                song.popularity,
            ),
        )


def _song_from_row(row: sqlite3.Row) -> Song:
    """Build a song domain model from one SQLite row."""
    return Song(
        spotify_id=row["spotify_id"],
        name=row["name"],
        artists=tuple(json.loads(row["artists"])),
        album=row["album"],
        duration_ms=row["duration_ms"],
        explicit=bool(row["explicit"]),
        popularity=row["popularity"],
    )
