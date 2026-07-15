"""Convert Spotify Web API responses into MusicMind domain models."""

import json
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from music_ai.models.saved_track import SavedTrack
from music_ai.models.song import Song


def parse_song(track_data: Mapping[str, Any]) -> Song:
    """Create a :class:`Song` from a Spotify track response."""
    album_data = _mapping_value(track_data, "album")
    artist_data = track_data.get("artists")

    if not isinstance(artist_data, list):
        raise ValueError("Spotify track is missing its artists list.")

    artists = tuple(
        _required_string(artist, "name", "Spotify track artist")
        for artist in artist_data
        if isinstance(artist, Mapping)
    )
    if not artists:
        raise ValueError("Spotify track must contain at least one artist.")

    return Song(
        spotify_id=_required_string(track_data, "id", "Spotify track"),
        name=_required_string(track_data, "name", "Spotify track"),
        artists=artists,
        album=_required_string(album_data, "name", "Spotify album"),
        duration_ms=_required_integer(track_data, "duration_ms", "Spotify track"),
        explicit=_required_boolean(track_data, "explicit", "Spotify track"),
        popularity=_required_integer(track_data, "popularity", "Spotify track"),
    )


def parse_saved_track(saved_track_data: Mapping[str, Any]) -> SavedTrack | None:
    """Create a :class:`SavedTrack` from a Spotify saved-track response.

    Spotify can leave saved-library entries behind for tracks that no longer
    resolve to a usable catalog track. Those entries are skipped instead of
    being imported as malformed MusicMind songs.
    """
    if "track" not in saved_track_data:
        raise ValueError("Spotify saved track is missing its 'track' value.")

    track_data = saved_track_data["track"]
    if track_data is None:
        return None
    if not isinstance(track_data, Mapping):
        raise ValueError("Spotify saved track is missing a valid 'track' object.")
    if track_data.get("is_local") is True:
        return None

    added_at = _parse_datetime(
        _required_string(saved_track_data, "added_at", "Spotify saved track")
    )

    _print_invalid_popularity_payload(saved_track_data, track_data)
    return SavedTrack(song=parse_song(track_data), added_at=added_at)


def _mapping_value(data: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    """Return a required mapping value from an API response."""
    value = data.get(key)
    if not isinstance(value, Mapping):
        raise ValueError(f"Spotify response is missing a valid '{key}' object.")
    return value


def _required_string(data: Mapping[str, Any], key: str, context: str) -> str:
    """Return a required non-empty string from an API response."""
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{context} is missing a valid '{key}' value.")
    return value


def _required_integer(data: Mapping[str, Any], key: str, context: str) -> int:
    """Return a required integer from an API response."""
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{context} is missing a valid '{key}' value.")
    return value


def _print_invalid_popularity_payload(
    saved_track_data: Mapping[str, Any], track_data: Mapping[str, Any]
) -> None:
    """Print the complete saved-track response before popularity validation fails.

    This temporary diagnostic preserves the parser's fail-fast validation while
    exposing the exact Spotify payload that lacks a valid track popularity.
    """
    popularity = track_data.get("popularity")
    if isinstance(popularity, int) and not isinstance(popularity, bool):
        return

    print("Invalid Spotify saved-track payload (missing valid popularity):")
    print(json.dumps(saved_track_data, indent=2))


def _required_boolean(data: Mapping[str, Any], key: str, context: str) -> bool:
    """Return a required boolean from an API response."""
    value = data.get(key)
    if not isinstance(value, bool):
        raise ValueError(f"{context} is missing a valid '{key}' value.")
    return value


def _parse_datetime(value: str) -> datetime:
    """Parse an ISO 8601 timestamp returned by Spotify."""
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("Spotify saved track has an invalid 'added_at' value.") from error
