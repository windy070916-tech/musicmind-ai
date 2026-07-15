from typing import Any

from config import load_spotify_settings
from music_ai.database.database import Database
from music_ai.models.saved_track import SavedTrack
from music_ai.parser.spotify_parser import parse_saved_track
from music_ai.repository.saved_track_repository import SavedTrackRepository
from music_ai.repository.song_repository import SongRepository
from music_ai.spotify.auth import SpotifyAuth
from music_ai.spotify.client import SpotifyClient


def main() -> None:
    """Import the authenticated user's saved Spotify tracks into MusicMind."""
    settings = load_spotify_settings()
    auth = SpotifyAuth(settings)
    token = auth.authenticate()

    client = SpotifyClient(token)
    client.current_user()

    print("Spotify Login Success")
    print("Downloading saved tracks...")
    saved_tracks, skipped_tracks = _parse_saved_tracks(_download_saved_tracks(client))

    database = Database()
    database.initialize()
    SongRepository(database).save_all([saved_track.song for saved_track in saved_tracks])
    SavedTrackRepository(database).save_all(saved_tracks)

    print(f"Imported {len(saved_tracks)} songs.")
    if skipped_tracks:
        print(f"Skipped {skipped_tracks} unavailable or local tracks.")
    print("Database updated successfully.")


def _download_saved_tracks(client: SpotifyClient) -> list[dict[str, Any]]:
    """Download every page of the current user's saved tracks."""
    tracks: list[dict[str, Any]] = []
    page_size = 50
    offset = 0

    while True:
        page = client.saved_tracks(limit=page_size, offset=offset)
        tracks.extend(page)

        if len(page) < page_size:
            return tracks

        offset += len(page)


def _parse_saved_tracks(items: list[dict[str, Any]]) -> tuple[list[SavedTrack], int]:
    """Convert Spotify saved-track JSON into importable MusicMind objects."""
    saved_tracks: list[SavedTrack] = []
    skipped_tracks = 0

    for item in items:
        saved_track = parse_saved_track(item)
        if saved_track is None:
            skipped_tracks += 1
            continue
        saved_tracks.append(saved_track)

    return saved_tracks, skipped_tracks


if __name__ == "__main__":
    main()
