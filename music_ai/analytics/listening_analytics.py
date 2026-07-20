"""Reusable listening analytics calculated from MusicMind's SQLite data."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import sqlite3

from music_ai.analytics.listening_profile import (
    DailyListeningProfile,
    RankedAlbum,
    RankedArtist,
    RankedGenre,
    RankedTrack,
)
from music_ai.database.database import Database


@dataclass(frozen=True)
class TopSong:
    """A song ranked by total estimated listening duration."""

    name: str
    artist: str
    listening_time_ms: int


@dataclass(frozen=True)
class TopArtist:
    """An artist ranked by total estimated listening duration."""

    name: str
    listening_time_ms: int


@dataclass(frozen=True)
class ListeningSummary:
    """Listening metrics and estimated-duration rankings for a time range.

    Its existing ``listening_time_ms`` fields use persisted playback duration
    when available and catalog track duration as a fallback.
    """

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

    def get_daily_listening_profile(
        self, start_datetime: datetime, end_datetime: datetime
    ) -> DailyListeningProfile:
        """Return deterministic listening-profile analytics for ``[start, end)``.

        The profile only reads persisted SQLite data. Durations are estimates:
        a playback duration is preferred and the catalog track duration is the
        fallback when a playback duration was not recorded.
        """
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
                    songs.album,
                    songs.album_id,
                    COALESCE(play_history.played_duration_ms, songs.duration_ms)
                        AS resolved_duration_ms,
                    (
                        SELECT song_artists.artist_id
                        FROM song_artists
                        WHERE song_artists.song_id = songs.spotify_id
                        ORDER BY song_artists.credit_position, song_artists.artist_id
                        LIMIT 1
                    ) AS primary_artist_id,
                    (
                        SELECT artists.name
                        FROM song_artists
                        JOIN artists ON artists.spotify_id = song_artists.artist_id
                        WHERE song_artists.song_id = songs.spotify_id
                        ORDER BY song_artists.credit_position, song_artists.artist_id
                        LIMIT 1
                    ) AS primary_artist_name
                FROM play_history
                JOIN songs ON songs.spotify_id = play_history.song_id
                WHERE play_history.played_at >= ? AND play_history.played_at < ?
                """,
                (start, end),
            ).fetchall()
            genres_by_artist_id = _load_genres_by_artist_id(connection, rows)

        return _build_daily_profile(
            start_datetime=start_datetime.astimezone(timezone.utc),
            end_datetime=end_datetime.astimezone(timezone.utc),
            rows=rows,
            genres_by_artist_id=genres_by_artist_id,
        )


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


def _load_genres_by_artist_id(
    connection: sqlite3.Connection, rows: list[sqlite3.Row]
) -> dict[str, tuple[str, ...]]:
    """Load persisted genre metadata for the profile's normalized artists."""
    artist_ids = sorted(
        {
            str(row["primary_artist_id"])
            for row in rows
            if row["primary_artist_id"] is not None
        }
    )
    if not artist_ids:
        return {}

    placeholders = ", ".join("?" for _ in artist_ids)
    genre_rows = connection.execute(
        f"""
        SELECT artist_id, genre
        FROM artist_genres
        WHERE artist_id IN ({placeholders})
        ORDER BY artist_id, genre
        """,
        artist_ids,
    ).fetchall()
    genres_by_artist_id: dict[str, list[str]] = defaultdict(list)
    for row in genre_rows:
        genres_by_artist_id[str(row["artist_id"])].append(str(row["genre"]))
    return {artist_id: tuple(genres) for artist_id, genres in genres_by_artist_id.items()}


def _build_daily_profile(
    start_datetime: datetime,
    end_datetime: datetime,
    rows: list[sqlite3.Row],
    genres_by_artist_id: dict[str, tuple[str, ...]],
) -> DailyListeningProfile:
    """Aggregate filtered playback rows into immutable profile results."""
    tracks: dict[str, _RankedAggregate] = {}
    artists: dict[tuple[str, str], _RankedAggregate] = {}
    albums: dict[tuple[str, ...], _RankedAggregate] = {}
    genres: dict[str, int] = defaultdict(int)
    total_duration = 0
    genre_covered_duration = 0

    for row in rows:
        duration = max(_as_int(row["resolved_duration_ms"]), 0)
        total_duration += duration

        track_id = str(row["spotify_id"])
        artist_names = _profile_artist_names(row["artists"])
        track = tracks.setdefault(
            track_id,
            _RankedAggregate(
                name=str(row["name"]),
                spotify_id=track_id,
                artist_names=artist_names,
                album_name=_display_album_name(row["album"]),
                spotify_album_id=_optional_text(row["album_id"]),
            ),
        )
        track.add(duration)

        primary_artist_id, primary_artist_name = _resolve_primary_artist(row, artist_names)
        artist_key = (
            ("spotify", primary_artist_id)
            if primary_artist_id is not None
            else ("legacy", primary_artist_name.casefold())
        )
        artist = artists.setdefault(
            artist_key,
            _RankedAggregate(name=primary_artist_name, spotify_id=primary_artist_id),
        )
        artist.update_display_name(primary_artist_name)
        artist.add(duration)

        album_name = _display_album_name(row["album"])
        album_id = _optional_text(row["album_id"])
        album_key = (
            ("spotify", album_id)
            if album_id is not None
            else ("legacy", album_name.casefold(), primary_artist_name.casefold())
        )
        album = albums.setdefault(
            album_key,
            _RankedAggregate(name=album_name, spotify_id=album_id),
        )
        album.update_display_name(album_name)
        album.add(duration)

        usable_genres = _usable_genres(genres_by_artist_id.get(primary_artist_id or "", ()))
        if usable_genres:
            genre_covered_duration += duration
            _allocate_genre_duration(genres, usable_genres, duration)

    ranked_tracks = _ranked_tracks(tracks, total_duration)
    ranked_artists = _ranked_artists(artists, total_duration)
    ranked_albums = _ranked_albums(albums, total_duration)
    ranked_genres = _ranked_genres(genres, total_duration)
    playback_count = len(rows)

    return DailyListeningProfile(
        start_datetime=start_datetime,
        end_datetime=end_datetime,
        total_estimated_listening_duration_ms=total_duration,
        playback_count=playback_count,
        unique_track_count=len(tracks),
        unique_track_ratio=(len(tracks) / playback_count) if playback_count else 0.0,
        top_track_share=ranked_tracks[0].share if ranked_tracks else 0.0,
        genre_covered_duration_ms=genre_covered_duration,
        genre_coverage=(genre_covered_duration / total_duration) if total_duration else 0.0,
        top_tracks=ranked_tracks,
        top_artists=ranked_artists,
        top_albums=ranked_albums,
        top_genres=ranked_genres,
    )


@dataclass
class _RankedAggregate:
    """Mutable internal accumulator; public profile results stay immutable."""

    name: str
    spotify_id: str | None
    artist_names: tuple[str, ...] = ()
    album_name: str = ""
    spotify_album_id: str | None = None
    play_count: int = 0
    duration_ms: int = 0

    def add(self, duration_ms: int) -> None:
        """Include one playback in this aggregate."""
        self.play_count += 1
        self.duration_ms += duration_ms

    def update_display_name(self, candidate: str) -> None:
        """Keep the lexicographically smallest non-blank display name."""
        usable_candidate = _optional_text(candidate)
        usable_current = _optional_text(self.name)
        if usable_candidate is None:
            return
        if usable_current is None or usable_candidate < usable_current:
            self.name = usable_candidate


def _ranked_tracks(
    tracks: dict[str, _RankedAggregate], total_duration: int
) -> tuple[RankedTrack, ...]:
    """Build deterministically ordered track profile results."""
    ranked = sorted(
        tracks.values(),
        key=lambda item: (
            -item.duration_ms,
            -item.play_count,
            item.name,
            ", ".join(item.artist_names),
            item.spotify_id or "",
        ),
    )
    return tuple(
        RankedTrack(
            spotify_track_id=item.spotify_id or "",
            name=item.name,
            artist_names=item.artist_names,
            album_name=item.album_name,
            spotify_album_id=item.spotify_album_id,
            play_count=item.play_count,
            estimated_listening_duration_ms=item.duration_ms,
            share=_share(item.duration_ms, total_duration),
        )
        for item in ranked
    )


def _ranked_artists(
    artists: dict[tuple[str, str], _RankedAggregate], total_duration: int
) -> tuple[RankedArtist, ...]:
    """Build deterministically ordered primary-artist profile results."""
    ranked = sorted(
        artists.items(),
        key=lambda pair: (
            -pair[1].duration_ms,
            -pair[1].play_count,
            pair[1].name,
            pair[1].spotify_id or "",
            pair[0],
        ),
    )
    return tuple(
        RankedArtist(
            spotify_artist_id=aggregate.spotify_id,
            name=aggregate.name,
            play_count=aggregate.play_count,
            estimated_listening_duration_ms=aggregate.duration_ms,
            share=_share(aggregate.duration_ms, total_duration),
        )
        for _, aggregate in ranked
    )


def _ranked_albums(
    albums: dict[tuple[str, ...], _RankedAggregate], total_duration: int
) -> tuple[RankedAlbum, ...]:
    """Build deterministically ordered album profile results."""
    ranked = sorted(
        albums.items(),
        key=lambda item: (
            -item[1].duration_ms,
            -item[1].play_count,
            item[1].name,
            item[1].spotify_id or "",
            item[0],
        ),
    )
    return tuple(
        RankedAlbum(
            spotify_album_id=aggregate.spotify_id,
            name=aggregate.name,
            play_count=aggregate.play_count,
            estimated_listening_duration_ms=aggregate.duration_ms,
            share=_share(aggregate.duration_ms, total_duration),
        )
        for _, aggregate in ranked
    )


def _ranked_genres(
    genres: dict[str, int], total_duration: int
) -> tuple[RankedGenre, ...]:
    """Build deterministically ordered genre profile results."""
    return tuple(
        RankedGenre(
            genre=genre,
            estimated_listening_duration_ms=duration,
            share=_share(duration, total_duration),
        )
        for genre, duration in sorted(genres.items(), key=lambda item: (-item[1], item[0]))
    )


def _resolve_primary_artist(
    row: sqlite3.Row, legacy_artist_names: tuple[str, ...]
) -> tuple[str | None, str]:
    """Apply the profile's normalized, legacy, then unknown artist priority."""
    artist_id = _optional_text(row["primary_artist_id"])
    normalized_name = _optional_text(row["primary_artist_name"])
    if artist_id is not None:
        if normalized_name is not None:
            return artist_id, normalized_name
        if legacy_artist_names:
            return artist_id, legacy_artist_names[0]
        return artist_id, "Unknown artist"
    if legacy_artist_names:
        return None, legacy_artist_names[0]
    return None, "Unknown artist"


def _profile_artist_names(value: str) -> tuple[str, ...]:
    """Deserialize usable legacy artist names for profile display and fallback."""
    try:
        artists = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return ()
    if not isinstance(artists, list):
        return ()
    return tuple(
        name.strip() for name in artists if isinstance(name, str) and name.strip()
    )


def _usable_genres(genres: tuple[str, ...]) -> tuple[str, ...]:
    """Return deduplicated alphabetically ordered persisted genres."""
    return tuple(sorted({genre.strip() for genre in genres if genre.strip()}))


def _allocate_genre_duration(
    genre_durations: dict[str, int], genres: tuple[str, ...], duration: int
) -> None:
    """Split integer duration across genres without inflating or losing time."""
    base, remainder = divmod(duration, len(genres))
    for position, genre in enumerate(genres):
        genre_durations[genre] += base + (1 if position < remainder else 0)


def _display_album_name(value: object) -> str:
    """Return the public album fallback used for incomplete historical metadata."""
    return _optional_text(value) or "Unknown album"


def _optional_text(value: object) -> str | None:
    """Return non-blank text or ``None``."""
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _as_int(value: object) -> int:
    """Convert persisted numeric values defensively for new profile analytics."""
    return int(value) if value is not None else 0


def _share(value: int, total: int) -> float:
    """Return a 0-1 share while handling an empty or zero-duration profile."""
    return value / total if total else 0.0
