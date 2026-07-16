from datetime import datetime
from typing import Any

from config import load_spotify_settings
from music_ai.database.database import Database
from music_ai.models.play_history import PlayHistory
from music_ai.models.song import Song
from music_ai.parser.spotify_playback_parser import parse_playback_item
from music_ai.repository.play_history_repository import PlayHistoryRepository
from music_ai.repository.song_repository import SongRepository
from music_ai.spotify.auth import SpotifyAuth
from music_ai.spotify.client import SpotifyClient


def main() -> None:
    """Import the authenticated user's Spotify playback history into MusicMind."""
    settings = load_spotify_settings()
    auth = SpotifyAuth(settings)
    token = auth.authenticate()

    client = SpotifyClient(token)
    client.current_user()

    database = Database()
    database.initialize()
    play_history_repository = PlayHistoryRepository(database)
    latest_played_at = play_history_repository.latest_played_at()

    print("Spotify Login Success")
    recent_tracks = _download_recent_tracks(client, latest_played_at)
    songs, play_history = _parse_recent_tracks(recent_tracks)
    SongRepository(database).save_all(songs)

    initial_count = play_history_repository.count()
    for record in play_history:
        play_history_repository.save(record)
    imported_count = play_history_repository.count() - initial_count

    print(f"Imported {imported_count} playback records.")
    print("Database updated successfully.")


def _download_recent_tracks(
    client: SpotifyClient, latest_played_at: datetime | None
) -> list[dict[str, Any]]:
    """Download recent tracks, optionally only after the latest stored playback."""
    if latest_played_at is None:
        print("First synchronization.")
        print("Downloading recent playback history...")
        return client.recent_tracks(limit=50)

    print("Last synchronized playback:")
    print(latest_played_at.isoformat())
    print("Checking Spotify...")
    tracks = client.recent_tracks(
        limit=50,
        after=_to_unix_timestamp_ms(latest_played_at),
    )
    print(f"Found {len(tracks)} new playback records.")
    return tracks


def _to_unix_timestamp_ms(value: datetime) -> int:
    """Convert a playback timestamp to the millisecond Unix value Spotify expects."""
    return int(value.timestamp() * 1000)


def _parse_recent_tracks(
    items: list[dict[str, Any]],
) -> tuple[list[Song], list[PlayHistory]]:
    """Convert Spotify recently played JSON into MusicMind domain models."""
    songs: list[Song] = []
    play_history: list[PlayHistory] = []
    for item in items:
        playback_item = parse_playback_item(item)
        if playback_item is None:
            continue

        song, record = playback_item
        songs.append(song)
        play_history.append(record)

    return songs, play_history


if __name__ == "__main__":
    main()
