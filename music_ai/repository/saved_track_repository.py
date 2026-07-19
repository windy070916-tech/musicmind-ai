"""Repository for persisting MusicMind saved tracks."""

from datetime import datetime
import json
import sqlite3

from music_ai.database.database import Database
from music_ai.models.saved_track import SavedTrack
from music_ai.models.song import Song


class SavedTrackRepository:
    """Store and retrieve :class:`SavedTrack` domain models."""

    def __init__(self, database: Database) -> None:
        """Create a saved-track repository backed by the supplied database."""
        self._database = database

    def save(self, saved_track: SavedTrack) -> None:
        """Insert a saved track when it has not already been recorded."""
        with self._database.connection() as connection:
            self._save(connection, saved_track)

    def save_all(self, saved_tracks: list[SavedTrack]) -> None:
        """Insert multiple saved tracks in one transaction without duplicates."""
        with self._database.connection() as connection:
            for saved_track in saved_tracks:
                self._save(connection, saved_track)

    def find_all(self) -> list[SavedTrack]:
        """Return every saved track, ordered by when it was added."""
        with self._database.connection() as connection:
            rows = connection.execute(
                """
                SELECT
                    songs.spotify_id,
                    songs.name,
                    songs.artists,
                    songs.album,
                    songs.duration_ms,
                    songs.explicit,
                    songs.popularity,
                    saved_tracks.added_at
                FROM saved_tracks
                JOIN songs ON songs.spotify_id = saved_tracks.song_id
                ORDER BY saved_tracks.added_at DESC
                """
            ).fetchall()

        return [_saved_track_from_row(row) for row in rows]

    def _save(self, connection: sqlite3.Connection, saved_track: SavedTrack) -> None:
        """Persist a saved track using an existing transaction."""
        connection.execute(
            "INSERT OR IGNORE INTO saved_tracks (song_id, added_at) VALUES (?, ?)",
            (saved_track.song.spotify_id, saved_track.added_at.isoformat()),
        )


def _saved_track_from_row(row: sqlite3.Row) -> SavedTrack:
    """Build a saved-track domain model from one SQLite row."""
    song = Song(
        spotify_id=row["spotify_id"],
        name=row["name"],
        artists=tuple(json.loads(row["artists"])),
        album=row["album"],
        duration_ms=row["duration_ms"],
        explicit=bool(row["explicit"]),
        popularity=row["popularity"],
    )
    return SavedTrack(song=song, added_at=datetime.fromisoformat(row["added_at"]))
