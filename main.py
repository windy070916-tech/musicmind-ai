from typing import Any

from config import load_spotify_settings
from music_ai.spotify.auth import SpotifyAuth
from music_ai.spotify.client import SpotifyClient


def main() -> None:
    """Authenticate with Spotify and print a small account summary."""
    settings = load_spotify_settings()
    auth = SpotifyAuth(settings)
    token = auth.authenticate()

    client = SpotifyClient(token)
    user = client.current_user()
    tracks = client.saved_tracks()

    _print_user(user)
    _print_saved_tracks(tracks)


def _print_user(user: dict[str, Any]) -> None:
    print("Spotify Login Success")
    print(f"Display Name: {user.get('display_name') or 'N/A'}")
    print(f"User ID: {user['id']}")
    print(f"Country: {user.get('country') or 'N/A'}")
    print(f"Product: {_format_product(user.get('product'))}")


def _print_saved_tracks(tracks: list[dict[str, Any]]) -> None:
    print(f"Saved Tracks: {len(tracks)}")

    for index, item in enumerate(tracks, start=1):
        track = item.get("track") or {}
        track_name = track.get("name") or "Unknown Track"
        artists = track.get("artists") or []
        artist_names = ", ".join(artist.get("name", "Unknown Artist") for artist in artists)
        print(f"{index}. {track_name} - {artist_names or 'Unknown Artist'}")


def _format_product(product: str | None) -> str:
    if not product:
        return "N/A"
    if product == "premium":
        return "Premium"
    if product == "free":
        return "Free"
    return product.title()


if __name__ == "__main__":
    main()
