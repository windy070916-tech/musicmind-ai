"""MusicMind domain models."""

from music_ai.models.artist import Artist
from music_ai.models.play_history import PlayHistory
from music_ai.models.saved_track import SavedTrack
from music_ai.models.song import Song
from music_ai.models.song_artist import SongArtist

__all__ = ["Artist", "PlayHistory", "SavedTrack", "Song", "SongArtist"]
