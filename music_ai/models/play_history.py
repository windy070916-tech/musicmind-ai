"""Playback history domain model."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class PlayHistory:
    """A recorded playback event for a MusicMind song."""

    id: int | None
    song_id: str
    played_at: datetime
    played_duration_ms: int | None
    source: str
