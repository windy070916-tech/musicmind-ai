from config import load_spotify_settings
from music_ai.spotify.auth import SpotifyAuth
from music_ai.spotify.client import SpotifyClient


def main() -> None:
    settings = load_spotify_settings()

    auth = SpotifyAuth(settings)
    token = auth.authenticate()

    client = SpotifyClient(token.access_token)
    profile = client.get_current_user_profile()

    print("Spotify Login Success")
    print(f"Display Name: {profile.display_name or 'N/A'}")
    print(f"User ID: {profile.user_id}")
    print(f"Country: {profile.country or 'N/A'}")
    print(f"Product: {_format_product(profile.product)}")


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
