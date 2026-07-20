"""Immutable deterministic results for daily listening-profile analytics."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class RankedTrack:
    """One track ranked within a listening profile."""

    spotify_track_id: str
    name: str
    artist_names: tuple[str, ...]
    album_name: str
    spotify_album_id: str | None
    play_count: int
    estimated_listening_duration_ms: int
    share: float


@dataclass(frozen=True)
class RankedArtist:
    """One primary artist ranked within a listening profile."""

    spotify_artist_id: str | None
    name: str
    play_count: int
    estimated_listening_duration_ms: int
    share: float


@dataclass(frozen=True)
class RankedAlbum:
    """One album ranked within a listening profile."""

    spotify_album_id: str | None
    name: str
    play_count: int
    estimated_listening_duration_ms: int
    share: float


@dataclass(frozen=True)
class RankedGenre:
    """One primary-artist genre ranked within a listening profile."""

    genre: str
    estimated_listening_duration_ms: int
    share: float


@dataclass(frozen=True)
class DailyListeningProfile:
    """Reusable deterministic listening statistics for one time range.

    All duration values are estimates: each playback uses its persisted played
    duration when available, otherwise the track's catalog duration.
    """

    start_datetime: datetime
    end_datetime: datetime
    total_estimated_listening_duration_ms: int
    playback_count: int
    unique_track_count: int
    unique_track_ratio: float
    top_track_share: float
    genre_covered_duration_ms: int
    genre_coverage: float
    top_tracks: tuple[RankedTrack, ...]
    top_artists: tuple[RankedArtist, ...]
    top_albums: tuple[RankedAlbum, ...]
    top_genres: tuple[RankedGenre, ...]
