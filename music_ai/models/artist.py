"""Artist domain model used by MusicMind metadata persistence."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Artist:
    """A Spotify artist and its optional catalog genres."""

    spotify_id: str
    name: str
    genres: tuple[str, ...] = ()
