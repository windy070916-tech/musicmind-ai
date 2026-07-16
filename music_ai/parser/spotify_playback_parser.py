"""Convert Spotify recently played data into MusicMind domain models."""

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from music_ai.models.play_history import PlayHistory
from music_ai.models.song import Song
from music_ai.parser.spotify_parser import parse_song


def parse_playback_item(
    playback_data: Mapping[str, Any],
) -> tuple[Song, PlayHistory] | None:
    """Create the song and playback-history models for one Spotify playback item.

    Local or unavailable Spotify tracks cannot be persisted as catalog songs, so
    the corresponding playback item is skipped.
    """
    play_history = parse_play_history(playback_data)
    if play_history is None:
        return None

    track_data = _track_data(playback_data)
    return parse_song(track_data), play_history


def parse_play_history(playback_data: Mapping[str, Any]) -> PlayHistory | None:
    """Create a :class:`PlayHistory` from a Spotify recently played item."""
    track_data = _track_data(playback_data)
    if track_data is None or track_data.get("is_local") is True:
        return None

    return PlayHistory(
        id=None,
        song_id=_required_string(track_data, "id", "Spotify playback track"),
        played_at=_parse_played_at(
            _required_string(playback_data, "played_at", "Spotify playback item")
        ),
        played_duration_ms=None,
        source="spotify",
    )


def _track_data(playback_data: Mapping[str, Any]) -> Mapping[str, Any] | None:
    """Return the track object from a Spotify playback item."""
    if "track" not in playback_data:
        raise ValueError("Spotify playback item is missing its 'track' value.")

    track_data = playback_data["track"]
    if track_data is None:
        return None
    if not isinstance(track_data, Mapping):
        raise ValueError("Spotify playback item is missing a valid 'track' object.")

    return track_data


def _required_string(data: Mapping[str, Any], key: str, context: str) -> str:
    """Return a required non-empty string from a Spotify response."""
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{context} is missing a valid '{key}' value.")
    return value


def _parse_played_at(value: str) -> datetime:
    """Parse the ISO 8601 playback timestamp returned by Spotify."""
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("Spotify playback item has an invalid 'played_at' value.") from error
