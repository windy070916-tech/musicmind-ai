from dataclasses import dataclass
from os import getenv
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import load_dotenv


@dataclass(frozen=True)
class SpotifySettings:
    client_id: str
    client_secret: str
    redirect_uri: str


def load_spotify_settings() -> SpotifySettings:
    load_dotenv()

    client_id = getenv("SPOTIPY_CLIENT_ID")
    client_secret = getenv("SPOTIPY_CLIENT_SECRET")
    redirect_uri = getenv("SPOTIPY_REDIRECT_URI")

    missing = [
        name
        for name, value in {
            "SPOTIPY_CLIENT_ID": client_id,
            "SPOTIPY_CLIENT_SECRET": client_secret,
            "SPOTIPY_REDIRECT_URI": redirect_uri,
        }.items()
        if not value
    ]

    if missing:
        missing_vars = ", ".join(missing)
        raise RuntimeError(f"Missing required environment variable(s): {missing_vars}")

    return SpotifySettings(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
    )


def load_musicmind_timezone() -> str:
    """Return the configured canonical IANA timezone name."""
    load_dotenv()
    timezone_name = getenv("MUSICMIND_TIMEZONE")
    if not timezone_name:
        raise RuntimeError(
            "Missing required environment variable: MUSICMIND_TIMEZONE"
        )

    try:
        ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as error:
        raise RuntimeError(
            "MUSICMIND_TIMEZONE must be a valid IANA timezone name."
        ) from error
    return timezone_name
