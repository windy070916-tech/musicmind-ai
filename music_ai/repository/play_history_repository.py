"""Repository for persisting MusicMind playback history."""

from datetime import datetime
import sqlite3

from music_ai.database.database import Database
from music_ai.models.play_history import PlayHistory


class PlayHistoryRepository:
    """Store and retrieve :class:`PlayHistory` domain models."""

    def __init__(self, database: Database):
        """Create a playback-history repository backed by the supplied database."""
        self._database = database

    def save(self, play_history: PlayHistory) -> None:
        """Insert a playback-history record when it has not already been recorded."""
        with self._database.connection() as connection:
            self._save(connection, play_history)

    def find_all(self) -> list[PlayHistory]:
        """Return every stored playback-history record."""
        with self._database.connection() as connection:
            rows = connection.execute(
                """
                SELECT id, song_id, played_at, played_duration_ms, source
                FROM play_history
                ORDER BY played_at DESC
                """
            ).fetchall()

        return [_play_history_from_row(row) for row in rows]

    def count(self) -> int:
        """Return the number of stored playback-history records."""
        with self._database.connection() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS count FROM play_history"
            ).fetchone()

        return int(row["count"])

    def delete_all(self) -> None:
        """Delete all stored playback-history records."""
        with self._database.connection() as connection:
            connection.execute("DELETE FROM play_history")

    def _save(
        self, connection: sqlite3.Connection, play_history: PlayHistory
    ) -> None:
        """Persist a playback-history record using an existing transaction."""
        if play_history.id is None:
            connection.execute(
                """
                INSERT OR IGNORE INTO play_history (
                    song_id, played_at, played_duration_ms, source
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    play_history.song_id,
                    play_history.played_at.isoformat(),
                    play_history.played_duration_ms,
                    play_history.source,
                ),
            )
            return

        connection.execute(
            """
            INSERT OR IGNORE INTO play_history (
                id, song_id, played_at, played_duration_ms, source
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                play_history.id,
                play_history.song_id,
                play_history.played_at.isoformat(),
                play_history.played_duration_ms,
                play_history.source,
            ),
        )


def _play_history_from_row(row: sqlite3.Row) -> PlayHistory:
    """Build a playback-history domain model from one SQLite row."""
    return PlayHistory(
        id=row["id"],
        song_id=row["song_id"],
        played_at=datetime.fromisoformat(row["played_at"]),
        played_duration_ms=row["played_duration_ms"],
        source=row["source"],
    )
