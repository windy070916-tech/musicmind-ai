from typing import Any

import requests

from music_ai.spotify.auth import SpotifyToken


SPOTIFY_API_BASE_URL = "https://api.spotify.com/v1"


class SpotifyClient:
    """Reusable client for Spotify Web API requests."""

    def __init__(self, token: SpotifyToken) -> None:
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

    def recent_tracks(
        self, limit: int = 50, after: int | None = None
    ) -> list[dict[str, Any]]:
        """Return the authenticated user's recently played Spotify tracks."""
        if not 1 <= limit <= 50:
            raise ValueError("limit must be between 1 and 50.")
        if after is not None and (
            isinstance(after, bool) or not isinstance(after, int) or after < 0
        ):
            raise ValueError("after must be a non-negative Unix timestamp in milliseconds.")

        params: dict[str, int] = {"limit": limit}
        if after is not None:
            params["after"] = after

        response_data = self._request(
            "GET",
            "/me/player/recently-played",
            params=params,
        )
        return response_data.get("items", [])

    def artists(self, spotify_ids: list[str]) -> list[dict[str, Any]]:
        """Return artist metadata for up to fifty unique Spotify artist identifiers.

        Metadata is optional for synchronization. Network failures and rate limiting
        therefore produce no metadata rather than failing an otherwise valid import.
        """
        unique_ids = list(dict.fromkeys(spotify_ids))
        if not unique_ids:
            return []
        if len(unique_ids) > 50:
            raise ValueError("artists accepts at most 50 unique Spotify artist identifiers.")

        try:
            response_data = self._request(
                "GET",
                "/artists",
                params={"ids": ",".join(unique_ids)},
            )
        except requests.RequestException:
            return []

        artists = response_data.get("artists", [])
        if not isinstance(artists, list):
            return []
        return [artist for artist in artists if isinstance(artist, dict)]

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
