from collections.abc import Callable, Sequence
from datetime import datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from config import load_musicmind_timezone, load_spotify_settings
from music_ai.ai.report_generator import ReportGenerator
from music_ai.analytics.listening_analytics import ListeningAnalytics, ListeningSummary
from music_ai.analytics.listening_profile import DailyListeningProfile
from music_ai.database.database import Database
from music_ai.knowledge.knowledge_engine import KnowledgeEngine
from music_ai.knowledge.models import KnowledgeFact
from music_ai.knowledge.recent_knowledge_engine import RecentKnowledgeEngine
from music_ai.memory.engine import MemoryEngine
from music_ai.models.artist import Artist
from music_ai.models.play_history import PlayHistory
from music_ai.models.song import Song
from music_ai.models.song_artist import SongArtist
from music_ai.narrative.engine import NarrativeEngine
from music_ai.parser.spotify_parser import parse_artist_metadata
from music_ai.parser.spotify_playback_parser import parse_playback_item
from music_ai.repository.artist_repository import ArtistRepository
from music_ai.repository.listening_memory_repository import (
    ListeningMemoryRepository,
)
from music_ai.repository.play_history_repository import PlayHistoryRepository
from music_ai.repository.song_repository import SongRepository
from music_ai.repository.song_artist_repository import SongArtistRepository
from music_ai.presentation.narrative_markdown_renderer import render_daily_narrative
from music_ai.spotify.auth import SpotifyAuth
from music_ai.spotify.client import SpotifyClient
from music_ai.temporal.analytics import TemporalListeningAnalytics


_RECENT_WINDOW_DAYS = 7
_COMPARISON_WINDOW_DAYS = 7


def main() -> None:
    """Import the authenticated user's Spotify playback history into MusicMind."""
    settings = load_spotify_settings()
    timezone_name = load_musicmind_timezone()
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
    analytics_time = datetime.now(timezone.utc)
    previous_summary, current_summary, current_profile = _daily_listening_summaries(
        database,
        timezone_name,
        analytics_time,
    )
    memory_engine = _capture_current_memory(
        database, timezone_name, analytics_time
    )
    recent_facts = _recent_listening_facts(
        memory_engine,
        timezone_name,
        analytics_time,
    )
    knowledge_engine = KnowledgeEngine(current_summary, previous_summary)
    daily_facts = knowledge_engine.generate_daily_facts()
    trend_facts = knowledge_engine.generate_trend_facts()
    insight_facts = knowledge_engine.generate_insight_facts()
    facts = daily_facts + trend_facts + insight_facts
    _print_daily_outputs(
        current_profile,
        facts,
        recent_facts=recent_facts,
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
    timezone_name: str,
    now: datetime | None = None,
) -> tuple[ListeningSummary, ListeningSummary, DailyListeningProfile]:
    """Calculate daily summaries and profile from one shared local time range."""
    zone = ZoneInfo(timezone_name)
    current_time = now or datetime.now(timezone.utc)
    if current_time.tzinfo is None or current_time.utcoffset() is None:
        raise ValueError("Daily analytics time must be timezone-aware.")
    local_date = current_time.astimezone(zone).date()
    start_of_today = datetime.combine(local_date, time.min, tzinfo=zone)
    end_of_today = datetime.combine(
        local_date + timedelta(days=1), time.min, tzinfo=zone
    )
    start_of_yesterday = datetime.combine(
        local_date - timedelta(days=1), time.min, tzinfo=zone
    )
    analytics = ListeningAnalytics(database)
    previous_summary = analytics.get_listening_summary(
        start_of_yesterday, start_of_today
    )
    current_summary = analytics.get_listening_summary(start_of_today, end_of_today)
    current_profile = analytics.get_daily_listening_profile(
        start_of_today, end_of_today
    )
    return previous_summary, current_summary, current_profile


def _capture_current_memory(
    database: Database, timezone_name: str, generated_at: datetime
) -> MemoryEngine:
    """Persist only the current local-calendar profile after synchronization."""
    engine = MemoryEngine(
        ListeningAnalytics(database),
        ListeningMemoryRepository(database),
        timezone_name,
        clock=lambda: generated_at,
    )
    engine.capture_current_day()
    return engine


def _recent_listening_facts(
    memory_engine: MemoryEngine,
    timezone_name: str,
    as_of: datetime,
) -> list[KnowledgeFact]:
    """Build recent facts from explicit application-owned calendar windows."""
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("Recent analysis time must be timezone-aware.")
    local_date = as_of.astimezone(ZoneInfo(timezone_name)).date()
    recent_end_date = local_date + timedelta(days=1)
    recent_start_date = recent_end_date - timedelta(
        days=_RECENT_WINDOW_DAYS
    )
    comparison_end_date = recent_start_date
    comparison_start_date = comparison_end_date - timedelta(
        days=_COMPARISON_WINDOW_DAYS
    )
    memory = memory_engine.load_range(
        comparison_start_date,
        recent_end_date,
    )
    evidence = TemporalListeningAnalytics().analyze(
        memory,
        recent_start_date=recent_start_date,
        recent_end_date=recent_end_date,
        comparison_start_date=comparison_start_date,
        comparison_end_date=comparison_end_date,
        timezone_name=timezone_name,
        as_of=as_of,
    )
    return RecentKnowledgeEngine(evidence).generate_facts()


def _print_daily_outputs(
    listening_profile: DailyListeningProfile,
    facts: list[KnowledgeFact],
    report_generator_factory: Callable[[], ReportGenerator] = ReportGenerator,
    *,
    recent_facts: Sequence[KnowledgeFact] = (),
) -> None:
    """Print deterministic Narrative output before generating the existing AI report."""
    narrative = NarrativeEngine(
        listening_profile, (*facts, *recent_facts)
    ).compose()
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
