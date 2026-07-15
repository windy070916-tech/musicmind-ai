from dataclasses import dataclass

import requests


SPOTIFY_API_BASE_URL = "https://api.spotify.com/v1"


@dataclass(frozen=True)
class SpotifyUserProfile:
    display_name: str | None
    user_id: str
    country: str | None
    product: str | None


class SpotifyClient:
    def __init__(self, access_token: str):
        self._access_token = access_token

    def get_current_user_profile(self) -> SpotifyUserProfile:
        response = requests.get(
            f"{SPOTIFY_API_BASE_URL}/me",
            headers={"Authorization": f"Bearer {self._access_token}"},
            timeout=20,
        )
        response.raise_for_status()
        profile_data = response.json()

        return SpotifyUserProfile(
            display_name=profile_data.get("display_name"),
            user_id=profile_data["id"],
            country=profile_data.get("country"),
            product=profile_data.get("product"),
        )
