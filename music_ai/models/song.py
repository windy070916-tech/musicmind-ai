"""Song domain model."""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Song:
    """A song known to MusicMind, independent of any external API."""

    spotify_id: str
    name: str
    artists: tuple[str, ...]
    album: str
    duration_ms: int
    explicit: bool
    popularity: Optional[int]
