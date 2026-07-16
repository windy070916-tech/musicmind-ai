from datetime import datetime, timedelta
from typing import Any

from config import load_spotify_settings
from music_ai.analytics.listening_analytics import ListeningAnalytics, ListeningSummary
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
    _print_listening_summary(_todays_listening_summary(database))


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


def _todays_listening_summary(database: Database) -> ListeningSummary:
    """Calculate a listening summary for the current local calendar day."""
    now = datetime.now().astimezone()
    start_of_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_today = start_of_today + timedelta(days=1)
    return ListeningAnalytics(database).get_listening_summary(start_of_today, end_of_today)


def _print_listening_summary(summary: ListeningSummary) -> None:
    """Print a formatted listening summary returned by the analytics layer."""
    print()
    print("=" * 40)
    print("MusicMind Listening Summary")
    print("=" * 40)
    print(f"Listening Time: {_format_duration(summary.total_listening_time_ms)}")
    print(f"Playback Count: {summary.playback_count}")
    print("Top Songs")
    _print_top_songs(summary)
    print("Top Artists")
    _print_top_artists(summary)
    print("=" * 40)


def _print_top_songs(summary: ListeningSummary) -> None:
    """Print the five songs with the most listening time."""
    if not summary.top_songs:
        print("No listening activity.")
        return

    for position, song in enumerate(summary.top_songs[:5], start=1):
        print(f"{position}. {song.name} - {song.artist} ({_format_duration(song.listening_time_ms)})")


def _print_top_artists(summary: ListeningSummary) -> None:
    """Print the five artists with the most listening time."""
    if not summary.top_artists:
        print("No listening activity.")
        return

    for artist in summary.top_artists[:5]:
        print(f"{artist.name} ({_format_duration(artist.listening_time_ms)})")


def _format_duration(duration_ms: int) -> str:
    """Format a duration in milliseconds for console display."""
    total_minutes = duration_ms // 60_000
    hours, minutes = divmod(total_minutes, 60)
    return f"{hours}h{minutes}m" if hours else f"{minutes}m"


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
