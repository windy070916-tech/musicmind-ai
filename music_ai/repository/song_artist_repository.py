"""Repository for normalized song-to-artist credits."""

from music_ai.database.database import Database
from music_ai.models.song_artist import SongArtist


class SongArtistRepository:
    """Persist the artists credited on each MusicMind song."""

    def __init__(self, database: Database) -> None:
        self._database = database

    def save_all(self, song_artists: list[SongArtist]) -> None:
        """Insert song credits without creating duplicates during repeated syncs."""
        with self._database.connection() as connection:
            connection.executemany(
                """
                INSERT INTO song_artists (song_id, artist_id, credit_position)
                VALUES (?, ?, ?)
                ON CONFLICT(song_id, artist_id) DO UPDATE SET
                    credit_position = excluded.credit_position
                """,
                [
                    (song_artist.song_id, song_artist.artist_id, song_artist.credit_position)
                    for song_artist in song_artists
                ],
            )

    def find_for_song(self, song_id: str) -> list[SongArtist]:
        """Return ordered artist credits for one song."""
        with self._database.connection() as connection:
            rows = connection.execute(
                """
                SELECT song_id, artist_id, credit_position
                FROM song_artists
                WHERE song_id = ?
                ORDER BY credit_position
                """,
                (song_id,),
            ).fetchall()

        return [
            SongArtist(
                song_id=str(row["song_id"]),
                artist_id=str(row["artist_id"]),
                credit_position=int(row["credit_position"]),
            )
            for row in rows
        ]
