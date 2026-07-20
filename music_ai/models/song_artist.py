"""Association between a MusicMind song and one credited artist."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SongArtist:
    """Preserve the order of artists credited on a Spotify track."""

    song_id: str
    artist_id: str
    credit_position: int
