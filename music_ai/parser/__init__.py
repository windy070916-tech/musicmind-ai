"""Adapters that convert provider data into MusicMind domain models."""

from music_ai.parser.spotify_parser import parse_saved_track, parse_song

__all__ = ["parse_saved_track", "parse_song"]
