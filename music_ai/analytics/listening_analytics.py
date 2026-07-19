"""Reusable listening analytics calculated from MusicMind's SQLite data."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import sqlite3

from music_ai.database.database import Database


@dataclass(frozen=True)
class TopSong:
    """A song ranked by total listening duration."""

    name: str
    artist: str
    listening_time_ms: int


@dataclass(frozen=True)
class TopArtist:
    """An artist ranked by total listening duration."""

    name: str
    listening_time_ms: int


@dataclass(frozen=True)
class ListeningSummary:
    """Listening metrics and duration-based rankings for a time range."""

    total_listening_time_ms: int
    playback_count: int
    top_songs: tuple[TopSong, ...]
    top_artists: tuple[TopArtist, ...]


class ListeningAnalytics:
    """Calculate read-only listening analytics from the MusicMind database."""

    def __init__(self, database: Database) -> None:
        """Create an analytics engine that reads from the supplied database."""
        self._database = database

    def get_listening_summary(
        self, start_datetime: datetime, end_datetime: datetime
    ) -> ListeningSummary:
        """Return duration-based listening analytics for ``[start_datetime, end_datetime)``."""
        start = _to_utc_isoformat(start_datetime)
        end = _to_utc_isoformat(end_datetime)
        if start >= end:
            raise ValueError("start_datetime must be earlier than end_datetime.")

        with self._database.connection() as connection:
            rows = connection.execute(
                """
                SELECT
                    songs.spotify_id,
                    songs.name,
                    songs.artists,
                    COALESCE(play_history.played_duration_ms, songs.duration_ms)
                        AS listening_time_ms
                FROM play_history
                JOIN songs ON songs.spotify_id = play_history.song_id
                WHERE play_history.played_at >= ? AND play_history.played_at < ?
                """,
                (start, end),
            ).fetchall()

        return _build_summary(rows)


def _to_utc_isoformat(value: datetime) -> str:
    """Convert an aware datetime to its UTC ISO-8601 representation."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Analytics time ranges must use timezone-aware datetimes.")
    return value.astimezone(timezone.utc).isoformat()


def _build_summary(rows: list[sqlite3.Row]) -> ListeningSummary:
    """Aggregate database rows into one listening summary."""
    song_durations: dict[tuple[str, str, str], int] = defaultdict(int)
    artist_durations: dict[str, int] = defaultdict(int)
    total_listening_time_ms = 0

    for row in rows:
        duration = int(row["listening_time_ms"])
        song_name = str(row["name"])
        artist_names = _artist_names(row["artists"])
        artist_label = ", ".join(artist_names)

        total_listening_time_ms += duration
        song_durations[(str(row["spotify_id"]), song_name, artist_label)] += duration
        for artist_name in artist_names:
            artist_durations[artist_name] += duration

    top_songs = tuple(
        TopSong(name=name, artist=artist, listening_time_ms=duration)
        for _, name, artist, duration in _rank_songs(song_durations)
    )
    top_artists = tuple(
        TopArtist(name=name, listening_time_ms=duration)
        for name, duration in _rank_artists(artist_durations)
    )

    return ListeningSummary(
        total_listening_time_ms=total_listening_time_ms,
        playback_count=len(rows),
        top_songs=top_songs,
        top_artists=top_artists,
    )


def _artist_names(value: str) -> tuple[str, ...]:
    """Deserialize the artist list stored by the song repository."""
    artists = json.loads(value)
    if not isinstance(artists, list) or not all(isinstance(artist, str) for artist in artists):
        raise ValueError("Stored song artists must be a JSON list of strings.")
    return tuple(artists)


def _rank_songs(
    durations: dict[tuple[str, str, str], int],
) -> list[tuple[str, str, str, int]]:
    """Return songs ordered by duration, then stable display values."""
    return sorted(
        (
            (spotify_id, name, artist, duration)
            for (spotify_id, name, artist), duration in durations.items()
        ),
        key=lambda item: (-item[3], item[1], item[2], item[0]),
    )


def _rank_artists(durations: dict[str, int]) -> list[tuple[str, int]]:
    """Return artists ordered by duration, then name."""
    return sorted(durations.items(), key=lambda item: (-item[1], item[0]))
