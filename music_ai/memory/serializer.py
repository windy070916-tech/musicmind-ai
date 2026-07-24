"""Explicit JSON serialization for versioned listening-memory snapshots."""

from collections.abc import Mapping
from datetime import date, datetime, timezone
import json
import math

from music_ai.analytics.listening_profile import (
    DailyListeningProfile,
    RankedAlbum,
    RankedArtist,
    RankedGenre,
    RankedTrack,
)
from music_ai.memory.models import (
    CURRENT_SNAPSHOT_VERSION,
    DailyMemorySnapshot,
)


class MemorySerializationError(ValueError):
    """A persisted Memory payload is malformed or violates its contract."""


class UnsupportedSnapshotVersionError(MemorySerializationError):
    """A Memory payload uses a snapshot version this release cannot read."""


def serialize_snapshot(snapshot: DailyMemorySnapshot) -> str:
    """Serialize one validated snapshot using the explicit version-one JSON contract."""
    _require_supported_version(snapshot.snapshot_version)
    profile = snapshot.profile
    payload = {
        "generated_at": _utc_isoformat(snapshot.generated_at),
        "is_closed": snapshot.is_closed,
        "local_date": snapshot.local_date.isoformat(),
        "profile": {
            "end_datetime": _utc_isoformat(profile.end_datetime),
            "genre_coverage": profile.genre_coverage,
            "genre_covered_duration_ms": profile.genre_covered_duration_ms,
            "playback_count": profile.playback_count,
            "start_datetime": _utc_isoformat(profile.start_datetime),
            "top_albums": [
                {
                    "estimated_listening_duration_ms": album.estimated_listening_duration_ms,
                    "name": album.name,
                    "play_count": album.play_count,
                    "share": album.share,
                    "spotify_album_id": album.spotify_album_id,
                }
                for album in profile.top_albums
            ],
            "top_artists": [
                {
                    "estimated_listening_duration_ms": artist.estimated_listening_duration_ms,
                    "name": artist.name,
                    "play_count": artist.play_count,
                    "share": artist.share,
                    "spotify_artist_id": artist.spotify_artist_id,
                }
                for artist in profile.top_artists
            ],
            "top_genres": [
                {
                    "estimated_listening_duration_ms": genre.estimated_listening_duration_ms,
                    "genre": genre.genre,
                    "share": genre.share,
                }
                for genre in profile.top_genres
            ],
            "top_track_share": profile.top_track_share,
            "top_tracks": [
                {
                    "album_name": track.album_name,
                    "artist_names": list(track.artist_names),
                    "estimated_listening_duration_ms": track.estimated_listening_duration_ms,
                    "name": track.name,
                    "play_count": track.play_count,
                    "share": track.share,
                    "spotify_album_id": track.spotify_album_id,
                    "spotify_track_id": track.spotify_track_id,
                }
                for track in profile.top_tracks
            ],
            "total_estimated_listening_duration_ms": (
                profile.total_estimated_listening_duration_ms
            ),
            "unique_track_count": profile.unique_track_count,
            "unique_track_ratio": profile.unique_track_ratio,
        },
        "snapshot_version": snapshot.snapshot_version,
        "timezone_name": snapshot.timezone_name,
    }
    try:
        return json.dumps(
            payload,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError) as error:
        raise MemorySerializationError(
            "Memory snapshot contains a value that cannot be serialized."
        ) from error


def deserialize_snapshot(payload: str) -> DailyMemorySnapshot:
    """Deserialize and validate one versioned Memory snapshot payload."""
    if not isinstance(payload, str):
        raise MemorySerializationError("Memory snapshot payload must be JSON text.")
    try:
        raw = json.loads(payload)
    except json.JSONDecodeError as error:
        raise MemorySerializationError("Memory snapshot payload is malformed JSON.") from error

    root = _mapping(raw, "snapshot")
    version = _integer(_required(root, "snapshot_version"), "snapshot_version", minimum=1)
    _require_supported_version(version)
    profile_payload = _mapping(_required(root, "profile"), "profile")

    try:
        profile = DailyListeningProfile(
            start_datetime=_datetime(
                _required(profile_payload, "start_datetime"),
                "profile.start_datetime",
            ),
            end_datetime=_datetime(
                _required(profile_payload, "end_datetime"),
                "profile.end_datetime",
            ),
            total_estimated_listening_duration_ms=_integer(
                _required(
                    profile_payload, "total_estimated_listening_duration_ms"
                ),
                "profile.total_estimated_listening_duration_ms",
                minimum=0,
            ),
            playback_count=_integer(
                _required(profile_payload, "playback_count"),
                "profile.playback_count",
                minimum=0,
            ),
            unique_track_count=_integer(
                _required(profile_payload, "unique_track_count"),
                "profile.unique_track_count",
                minimum=0,
            ),
            unique_track_ratio=_share(
                _required(profile_payload, "unique_track_ratio"),
                "profile.unique_track_ratio",
            ),
            top_track_share=_share(
                _required(profile_payload, "top_track_share"),
                "profile.top_track_share",
            ),
            genre_covered_duration_ms=_integer(
                _required(profile_payload, "genre_covered_duration_ms"),
                "profile.genre_covered_duration_ms",
                minimum=0,
            ),
            genre_coverage=_share(
                _required(profile_payload, "genre_coverage"),
                "profile.genre_coverage",
            ),
            top_tracks=_tracks(_required(profile_payload, "top_tracks")),
            top_artists=_artists(_required(profile_payload, "top_artists")),
            top_albums=_albums(_required(profile_payload, "top_albums")),
            top_genres=_genres(_required(profile_payload, "top_genres")),
        )
        return DailyMemorySnapshot(
            local_date=_date(_required(root, "local_date"), "local_date"),
            timezone_name=_text(
                _required(root, "timezone_name"), "timezone_name"
            ),
            profile=profile,
            generated_at=_datetime(
                _required(root, "generated_at"), "generated_at"
            ),
            is_closed=_boolean(_required(root, "is_closed"), "is_closed"),
            snapshot_version=version,
        )
    except ValueError as error:
        if isinstance(error, MemorySerializationError):
            raise
        raise MemorySerializationError(
            "Memory snapshot payload violates the model contract."
        ) from error


def _tracks(value: object) -> tuple[RankedTrack, ...]:
    items = _list(value, "profile.top_tracks")
    tracks: list[RankedTrack] = []
    for index, value_item in enumerate(items):
        field = f"profile.top_tracks[{index}]"
        item = _mapping(value_item, field)
        artist_values = _list(_required(item, "artist_names"), f"{field}.artist_names")
        tracks.append(
            RankedTrack(
                spotify_track_id=_text(
                    _required(item, "spotify_track_id"),
                    f"{field}.spotify_track_id",
                    allow_empty=True,
                ),
                name=_text(_required(item, "name"), f"{field}.name"),
                artist_names=tuple(
                    _text(artist, f"{field}.artist_names[{artist_index}]")
                    for artist_index, artist in enumerate(artist_values)
                ),
                album_name=_text(
                    _required(item, "album_name"), f"{field}.album_name"
                ),
                spotify_album_id=_optional_text(
                    _required(item, "spotify_album_id"),
                    f"{field}.spotify_album_id",
                ),
                play_count=_integer(
                    _required(item, "play_count"),
                    f"{field}.play_count",
                    minimum=0,
                ),
                estimated_listening_duration_ms=_integer(
                    _required(item, "estimated_listening_duration_ms"),
                    f"{field}.estimated_listening_duration_ms",
                    minimum=0,
                ),
                share=_share(_required(item, "share"), f"{field}.share"),
            )
        )
    return tuple(tracks)


def _artists(value: object) -> tuple[RankedArtist, ...]:
    items = _list(value, "profile.top_artists")
    artists: list[RankedArtist] = []
    for index, value_item in enumerate(items):
        field = f"profile.top_artists[{index}]"
        item = _mapping(value_item, field)
        artists.append(
            RankedArtist(
                spotify_artist_id=_optional_text(
                    _required(item, "spotify_artist_id"),
                    f"{field}.spotify_artist_id",
                ),
                name=_text(_required(item, "name"), f"{field}.name"),
                play_count=_integer(
                    _required(item, "play_count"),
                    f"{field}.play_count",
                    minimum=0,
                ),
                estimated_listening_duration_ms=_integer(
                    _required(item, "estimated_listening_duration_ms"),
                    f"{field}.estimated_listening_duration_ms",
                    minimum=0,
                ),
                share=_share(_required(item, "share"), f"{field}.share"),
            )
        )
    return tuple(artists)


def _albums(value: object) -> tuple[RankedAlbum, ...]:
    items = _list(value, "profile.top_albums")
    albums: list[RankedAlbum] = []
    for index, value_item in enumerate(items):
        field = f"profile.top_albums[{index}]"
        item = _mapping(value_item, field)
        albums.append(
            RankedAlbum(
                spotify_album_id=_optional_text(
                    _required(item, "spotify_album_id"),
                    f"{field}.spotify_album_id",
                ),
                name=_text(_required(item, "name"), f"{field}.name"),
                play_count=_integer(
                    _required(item, "play_count"),
                    f"{field}.play_count",
                    minimum=0,
                ),
                estimated_listening_duration_ms=_integer(
                    _required(item, "estimated_listening_duration_ms"),
                    f"{field}.estimated_listening_duration_ms",
                    minimum=0,
                ),
                share=_share(_required(item, "share"), f"{field}.share"),
            )
        )
    return tuple(albums)


def _genres(value: object) -> tuple[RankedGenre, ...]:
    items = _list(value, "profile.top_genres")
    genres: list[RankedGenre] = []
    for index, value_item in enumerate(items):
        field = f"profile.top_genres[{index}]"
        item = _mapping(value_item, field)
        genres.append(
            RankedGenre(
                genre=_text(_required(item, "genre"), f"{field}.genre"),
                estimated_listening_duration_ms=_integer(
                    _required(item, "estimated_listening_duration_ms"),
                    f"{field}.estimated_listening_duration_ms",
                    minimum=0,
                ),
                share=_share(_required(item, "share"), f"{field}.share"),
            )
        )
    return tuple(genres)


def _required(mapping: Mapping[str, object], key: str) -> object:
    if key not in mapping:
        raise MemorySerializationError(
            f"Memory snapshot payload is missing required key: {key}."
        )
    return mapping[key]


def _mapping(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, dict) or not all(
        isinstance(key, str) for key in value
    ):
        raise MemorySerializationError(f"{field} must be a JSON object.")
    return value


def _list(value: object, field: str) -> list[object]:
    if not isinstance(value, list):
        raise MemorySerializationError(f"{field} must be a JSON array.")
    return value


def _text(value: object, field: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value):
        raise MemorySerializationError(f"{field} must be text.")
    return value


def _optional_text(value: object, field: str) -> str | None:
    if value is None:
        return None
    return _text(value, field)


def _integer(value: object, field: str, *, minimum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise MemorySerializationError(
            f"{field} must be an integer greater than or equal to {minimum}."
        )
    return value


def _share(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MemorySerializationError(f"{field} must be a number.")
    result = float(value)
    if not math.isfinite(result) or not 0.0 <= result <= 1.0:
        raise MemorySerializationError(f"{field} must be between 0 and 1.")
    return result


def _boolean(value: object, field: str) -> bool:
    if not isinstance(value, bool):
        raise MemorySerializationError(f"{field} must be a boolean.")
    return value


def _date(value: object, field: str) -> date:
    text = _text(value, field)
    try:
        return date.fromisoformat(text)
    except ValueError as error:
        raise MemorySerializationError(f"{field} must be an ISO-8601 date.") from error


def _datetime(value: object, field: str) -> datetime:
    text = _text(value, field)
    try:
        result = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as error:
        raise MemorySerializationError(
            f"{field} must be an ISO-8601 datetime."
        ) from error
    if result.tzinfo is None or result.utcoffset() is None:
        raise MemorySerializationError(f"{field} must be timezone-aware.")
    return result


def _utc_isoformat(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise MemorySerializationError("Snapshot timestamps must be timezone-aware.")
    return value.astimezone(timezone.utc).isoformat()


def _require_supported_version(version: int) -> None:
    if version != CURRENT_SNAPSHOT_VERSION:
        raise UnsupportedSnapshotVersionError(
            f"Unsupported Memory snapshot version: {version}."
        )
