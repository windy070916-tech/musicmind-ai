from typing import Any

import requests

from music_ai.spotify.auth import SpotifyToken


SPOTIFY_API_BASE_URL = "https://api.spotify.com/v1"


class SpotifyClient:
    """Reusable client for Spotify Web API requests."""

    def __init__(self, token: SpotifyToken):
        self._token = token

    def current_user(self) -> dict[str, Any]:
        """Return the authenticated Spotify user's profile."""
        return self._request("GET", "/me")

    def saved_tracks(self, limit: int = 20) -> list[dict[str, Any]]:
        """Return the authenticated user's saved tracks."""
        response_data = self._request("GET", "/me/tracks", params={"limit": limit})
        return response_data.get("items", [])

    def _request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Send one Spotify Web API request and return the decoded JSON response."""
        response = requests.request(
            method=method,
            url=f"{SPOTIFY_API_BASE_URL}{endpoint}",
            headers={"Authorization": f"Bearer {self._token.access_token}"},
            params=params,
            timeout=20,
        )
        response.raise_for_status()
        return response.json()
