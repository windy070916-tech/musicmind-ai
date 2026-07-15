"""Saved track domain model."""

from dataclasses import dataclass
from datetime import datetime

from music_ai.models.song import Song


@dataclass(frozen=True)
class SavedTrack:
    """A song saved to a user's music library at a particular time."""

    song: Song
    added_at: datetime
