from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any

from config import load_spotify_settings
from music_ai.ai.report_generator import ReportGenerator
from music_ai.analytics.listening_analytics import ListeningAnalytics, ListeningSummary
from music_ai.analytics.listening_profile import DailyListeningProfile
from music_ai.database.database import Database
from music_ai.knowledge.knowledge_engine import KnowledgeEngine
from music_ai.knowledge.models import KnowledgeFact
from music_ai.models.artist import Artist
from music_ai.models.play_history import PlayHistory
from music_ai.models.song import Song
from music_ai.models.song_artist import SongArtist
from music_ai.narrative.engine import NarrativeEngine
from music_ai.parser.spotify_parser import parse_artist_metadata
from music_ai.parser.spotify_playback_parser import parse_playback_item
from music_ai.repository.artist_repository import ArtistRepository
from music_ai.repository.play_history_repository import PlayHistoryRepository
from music_ai.repository.song_repository import SongRepository
from music_ai.repository.song_artist_repository import SongArtistRepository
from music_ai.presentation.narrative_markdown_renderer import render_daily_narrative
from music_ai.spotify.auth import SpotifyAuth
from music_ai.spotify.client import SpotifyClient


def main() -> None:
    """Import the authenticated user's Spotify playback history into MusicMind."""
    settings = load_spotify_settings()
    auth = SpotifyAuth(settings)
    token = auth.authenticate()

    client = SpotifyClient(token)
    client.current_user()

    database = Database()
    database.initialize()
    play_history_repository = PlayHistoryRepository(database)
    latest_played_at = play_history_repository.latest_played_at()

    print("Spotify Login Success")
    recent_tracks = _download_recent_tracks(client, latest_played_at)
    songs, play_history = _parse_recent_tracks(recent_tracks)
    _persist_song_metadata(database, songs)
    _enrich_artist_metadata(client, database, songs)

    initial_count = play_history_repository.count()
    for record in play_history:
        play_history_repository.save(record)
    imported_count = play_history_repository.count() - initial_count

    print(f"Imported {imported_count} playback records.")
    print("Database updated successfully.")
    previous_summary, current_summary, current_profile = _daily_listening_summaries(
        database
    )
    knowledge_engine = KnowledgeEngine(current_summary, previous_summary)
    daily_facts = knowledge_engine.generate_daily_facts()
    trend_facts = knowledge_engine.generate_trend_facts()
    insight_facts = knowledge_engine.generate_insight_facts()
    facts = daily_facts + trend_facts + insight_facts
    _print_daily_outputs(
        current_profile,
        facts,
    )


def _download_recent_tracks(
    client: SpotifyClient, latest_played_at: datetime | None
) -> list[dict[str, Any]]:
    """Download recent tracks, optionally only after the latest stored playback."""
    if latest_played_at is None:
        print("First synchronization.")
        print("Downloading recent playback history...")
        return client.recent_tracks(limit=50)

    print("Last synchronized playback:")
    print(latest_played_at.isoformat())
    print("Checking Spotify...")
    tracks = client.recent_tracks(
        limit=50,
        after=_to_unix_timestamp_ms(latest_played_at),
    )
    print(f"Found {len(tracks)} new playback records.")
    return tracks


def _to_unix_timestamp_ms(value: datetime) -> int:
    """Convert a playback timestamp to the millisecond Unix value Spotify expects."""
    return int(value.timestamp() * 1000)


def _daily_listening_summaries(
    database: Database,
    now: datetime | None = None,
) -> tuple[ListeningSummary, ListeningSummary, DailyListeningProfile]:
    """Calculate daily summaries and profile from one shared local time range."""
    now = now or datetime.now().astimezone()
    start_of_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_today = start_of_today + timedelta(days=1)
    start_of_yesterday = start_of_today - timedelta(days=1)
    analytics = ListeningAnalytics(database)
    previous_summary = analytics.get_listening_summary(
        start_of_yesterday, start_of_today
    )
    current_summary = analytics.get_listening_summary(start_of_today, end_of_today)
    current_profile = analytics.get_daily_listening_profile(
        start_of_today, end_of_today
    )
    return previous_summary, current_summary, current_profile


def _print_daily_outputs(
    listening_profile: DailyListeningProfile,
    facts: list[KnowledgeFact],
    report_generator_factory: Callable[[], ReportGenerator] = ReportGenerator,
) -> None:
    """Print deterministic Narrative output before generating the existing AI report."""
    narrative = NarrativeEngine(listening_profile, facts).compose()
    _print_daily_narrative(render_daily_narrative(narrative))
    report_generator = report_generator_factory()
    _print_ai_report(report_generator.generate_daily_report(facts))


def _print_daily_narrative(report: str) -> None:
    """Print the deterministic Markdown report produced from DailyNarrative."""
    print()
    print("=" * 40)
    print(report)
    print("=" * 40)


def _print_daily_facts(facts: list[KnowledgeFact]) -> None:
    """Print presentation-ready facts generated by the knowledge layer."""
    print()
    print("=" * 40)
    print("MusicMind Daily Facts")
    print("=" * 40)
    for fact in facts:
        print(f"• {fact.description}")
    print("=" * 40)


def _print_daily_trends(facts: list[KnowledgeFact]) -> None:
    """Print trend facts generated by the knowledge layer."""
    print()
    print("=" * 40)
    print("MusicMind Daily Trends")
    print("=" * 40)
    if not facts:
        print("• No changes from yesterday.")
    for fact in facts:
        print(f"• {fact.description}")
    print("=" * 40)


def _print_insight_facts(facts: list[KnowledgeFact]) -> None:
    """Print higher-level behavioral facts generated by the knowledge layer."""
    print()
    print("=" * 40)
    print("MusicMind Insight Facts")
    print("=" * 40)
    if not facts:
        print("• No behavioral insights for today.")
    for fact in facts:
        print(f"• {fact.description}")
    print("=" * 40)


def _print_ai_report(report: str) -> None:
    """Print the Markdown report generated by the configured LLM provider."""
    print()
    print("=" * 40)
    print("MusicMind AI Report")
    print("=" * 40)
    print(report)
    print("=" * 40)


def _parse_recent_tracks(
    items: list[dict[str, Any]],
) -> tuple[list[Song], list[PlayHistory]]:
    """Convert Spotify recently played JSON into MusicMind domain models."""
    songs: list[Song] = []
    play_history: list[PlayHistory] = []
    for item in items:
        playback_item = parse_playback_item(item)
        if playback_item is None:
            continue

        song, record = playback_item
        songs.append(song)
        play_history.append(record)

    return songs, play_history


def _persist_song_metadata(database: Database, songs: list[Song]) -> None:
    """Persist songs and their normalized artist credits for later analytics."""
    SongRepository(database).save_all(songs)
    artists = _artists_from_songs(songs)
    ArtistRepository(database).save_all(artists)
    SongArtistRepository(database).save_all(_song_artists_from_songs(songs))


def _enrich_artist_metadata(
    client: SpotifyClient, database: Database, songs: list[Song]
) -> None:
    """Cache optional artist genres without blocking playback synchronization."""
    artist_repository = ArtistRepository(database)
    refresh_before = datetime.now(timezone.utc) - timedelta(days=30)
    stale_artists = artist_repository.requiring_metadata(
        [artist.spotify_id for artist in _artists_from_songs(songs)],
        refresh_before,
    )

    for artist_batch in _batches(stale_artists, 50):
        for artist_data in client.artists([artist.spotify_id for artist in artist_batch]):
            artist = parse_artist_metadata(artist_data)
            if artist is not None:
                artist_repository.save_metadata(artist, datetime.now(timezone.utc))


def _artists_from_songs(songs: list[Song]) -> list[Artist]:
    """Return unique artist references parsed from songs that include Spotify IDs."""
    artists: dict[str, Artist] = {}
    for song in songs:
        for artist_id, artist_name in zip(song.artist_ids, song.artists, strict=True):
            artists[artist_id] = Artist(spotify_id=artist_id, name=artist_name)
    return list(artists.values())


def _song_artists_from_songs(songs: list[Song]) -> list[SongArtist]:
    """Build ordered normalized artist credits from parsed song metadata."""
    return [
        SongArtist(song.spotify_id, artist_id, position)
        for song in songs
        for position, artist_id in enumerate(song.artist_ids)
    ]


def _batches(items: list[Artist], size: int) -> list[list[Artist]]:
    """Split artist metadata requests into Spotify's maximum batch size."""
    return [items[index : index + size] for index in range(0, len(items), size)]


if __name__ == "__main__":
    main()
