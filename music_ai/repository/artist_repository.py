"""Repository for normalized artist metadata and cached genres."""

from datetime import datetime
import sqlite3

from music_ai.database.database import Database
from music_ai.models.artist import Artist


class ArtistRepository:
    """Persist Spotify artists and their optional genre metadata."""

    def __init__(self, database: Database) -> None:
        self._database = database

    def save_all(self, artists: list[Artist]) -> None:
        """Insert artists discovered in track metadata without refreshing genres."""
        with self._database.connection() as connection:
            for artist in artists:
                self._save_reference(connection, artist)

    def save_metadata(self, artist: Artist, refreshed_at: datetime) -> None:
        """Store one artist's current genre metadata, including an empty result."""
        with self._database.connection() as connection:
            self._save_reference(connection, artist)
            connection.execute(
                """
                UPDATE artists
                SET metadata_refreshed_at = ?
                WHERE spotify_id = ?
                """,
                (refreshed_at.isoformat(), artist.spotify_id),
            )
            connection.execute(
                "DELETE FROM artist_genres WHERE artist_id = ?",
                (artist.spotify_id,),
            )
            connection.executemany(
                "INSERT INTO artist_genres (artist_id, genre) VALUES (?, ?)",
                [(artist.spotify_id, genre) for genre in dict.fromkeys(artist.genres)],
            )

    def find_by_id(self, spotify_id: str) -> Artist | None:
        """Return one artist and its cached genres, if stored."""
        with self._database.connection() as connection:
            row = connection.execute(
                "SELECT spotify_id, name FROM artists WHERE spotify_id = ?",
                (spotify_id,),
            ).fetchone()
            if row is None:
                return None
            genres = connection.execute(
                "SELECT genre FROM artist_genres WHERE artist_id = ? ORDER BY genre",
                (spotify_id,),
            ).fetchall()

        return Artist(
            spotify_id=str(row["spotify_id"]),
            name=str(row["name"]),
            genres=tuple(str(genre["genre"]) for genre in genres),
        )

    def requiring_metadata(
        self, spotify_ids: list[str], refreshed_before: datetime
    ) -> list[Artist]:
        """Return cached artists that are missing or stale metadata."""
        unique_ids = list(dict.fromkeys(spotify_ids))
        if not unique_ids:
            return []

        placeholders = ", ".join("?" for _ in unique_ids)
        with self._database.connection() as connection:
            rows = connection.execute(
                f"""
                SELECT spotify_id, name
                FROM artists
                WHERE spotify_id IN ({placeholders})
                  AND (
                    metadata_refreshed_at IS NULL
                    OR metadata_refreshed_at < ?
                  )
                ORDER BY spotify_id
                """,
                (*unique_ids, refreshed_before.isoformat()),
            ).fetchall()

        return [
            Artist(spotify_id=str(row["spotify_id"]), name=str(row["name"]))
            for row in rows
        ]

    def _save_reference(self, connection: sqlite3.Connection, artist: Artist) -> None:
        connection.execute(
            """
            INSERT INTO artists (spotify_id, name) VALUES (?, ?)
            ON CONFLICT(spotify_id) DO UPDATE SET name = excluded.name
            """,
            (artist.spotify_id, artist.name),
        )
