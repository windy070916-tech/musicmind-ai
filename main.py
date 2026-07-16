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

    print("Spotify Login Success")
    print("Downloading Recently Played...")
    songs, play_history = _parse_recent_tracks(client.recent_tracks(limit=50))

    database = Database()
    database.initialize()
    SongRepository(database).save_all(songs)

    play_history_repository = PlayHistoryRepository(database)
    initial_count = play_history_repository.count()
    for record in play_history:
        play_history_repository.save(record)
    imported_count = play_history_repository.count() - initial_count

    print(f"Imported {imported_count} playback records.")
    print("Database updated successfully.")


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
