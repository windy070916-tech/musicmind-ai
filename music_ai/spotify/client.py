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

    def saved_tracks(self, limit: int = 20, offset: int = 0) -> list[dict[str, Any]]:
        """Return one page of the authenticated user's saved tracks."""
        if not 1 <= limit <= 50:
            raise ValueError("limit must be between 1 and 50.")
        if offset < 0:
            raise ValueError("offset must be greater than or equal to 0.")

        response_data = self._request(
            "GET",
            "/me/tracks",
            params={"limit": limit, "offset": offset},
        )
        return response_data.get("items", [])

    def recent_tracks(self, limit: int = 20) -> list[dict[str, Any]]:
        """Return the authenticated user's recently played Spotify tracks."""
        if not 1 <= limit <= 50:
            raise ValueError("limit must be between 1 and 50.")

        response_data = self._request(
            "GET",
            "/me/player/recently-played",
            params={"limit": limit},
        )
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
