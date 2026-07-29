"""Configuration and isolated runtime tests for current-day Memory capture."""

from datetime import date, datetime, timezone

import pytest

import config
import main
from music_ai.analytics import DailyListeningProfile, ListeningSummary


def _profile() -> DailyListeningProfile:
    return DailyListeningProfile(
        start_datetime=datetime(2026, 7, 23, 16, tzinfo=timezone.utc),
        end_datetime=datetime(2026, 7, 24, 16, tzinfo=timezone.utc),
        total_estimated_listening_duration_ms=0,
        playback_count=0,
        unique_track_count=0,
        unique_track_ratio=0.0,
        top_track_share=0.0,
        genre_covered_duration_ms=0,
        genre_coverage=0.0,
        top_tracks=(),
        top_artists=(),
        top_albums=(),
        top_genres=(),
    )


def test_musicmind_timezone_configuration_is_explicit_and_validated(
    monkeypatch,
) -> None:
    monkeypatch.setattr(config, "load_dotenv", lambda: None)
    monkeypatch.delenv("MUSICMIND_TIMEZONE", raising=False)
    with pytest.raises(RuntimeError, match="MUSICMIND_TIMEZONE"):
        config.load_musicmind_timezone()

    monkeypatch.setenv("MUSICMIND_TIMEZONE", "Invalid/Zone")
    with pytest.raises(RuntimeError, match="IANA"):
        config.load_musicmind_timezone()

    monkeypatch.setenv("MUSICMIND_TIMEZONE", "Asia/Shanghai")
    assert config.load_musicmind_timezone() == "Asia/Shanghai"


def test_capture_current_memory_delegates_once_without_historical_rebuild(
    monkeypatch,
) -> None:
    calls = []
    analytics = object()
    repository = object()

    class FakeEngine:
        def __init__(self, received_analytics, received_repository, zone, clock):
            calls.append(
                ("init", received_analytics, received_repository, zone, clock())
            )

        def capture_current_day(self):
            calls.append("capture_current")

        def rebuild_range(self, *_args):
            raise AssertionError("Runtime must not rebuild history.")

    monkeypatch.setattr(main, "ListeningAnalytics", lambda _database: analytics)
    monkeypatch.setattr(
        main, "ListeningMemoryRepository", lambda _database: repository
    )
    monkeypatch.setattr(main, "MemoryEngine", FakeEngine)
    generated_at = datetime(2026, 7, 24, 8, tzinfo=timezone.utc)

    main._capture_current_memory(object(), "Asia/Shanghai", generated_at)

    assert calls == [
        ("init", analytics, repository, "Asia/Shanghai", generated_at),
        "capture_current",
    ]


def test_main_captures_memory_after_raw_persistence_without_changing_facts(
    monkeypatch,
) -> None:
    events = []
    empty_summary = ListeningSummary(0, 0, (), ())
    profile = _profile()

    class FakeAuth:
        def __init__(self, _settings):
            events.append("auth_init")

        def authenticate(self):
            events.append("authenticate")
            return object()

    class FakeClient:
        def __init__(self, _token):
            pass

        def current_user(self):
            events.append("current_user")

    class FakeDatabase:
        def initialize(self):
            events.append("database_initialize")

    class FakePlayHistoryRepository:
        def __init__(self, _database):
            self.records = []

        def latest_played_at(self):
            return None

        def count(self):
            return len(self.records)

        def save(self, record):
            events.append("raw_playback_saved")
            self.records.append(record)

    monkeypatch.setattr(main, "load_spotify_settings", lambda: object())
    monkeypatch.setattr(
        main, "load_musicmind_timezone", lambda: "Asia/Shanghai"
    )
    monkeypatch.setattr(main, "SpotifyAuth", FakeAuth)
    monkeypatch.setattr(main, "SpotifyClient", FakeClient)
    monkeypatch.setattr(main, "Database", FakeDatabase)
    monkeypatch.setattr(
        main, "PlayHistoryRepository", FakePlayHistoryRepository
    )
    monkeypatch.setattr(main, "_download_recent_tracks", lambda *_args: [{}])
    monkeypatch.setattr(
        main, "_parse_recent_tracks", lambda _items: ([], [object()])
    )
    monkeypatch.setattr(
        main,
        "_persist_song_metadata",
        lambda *_args: events.append("metadata_persisted"),
    )
    monkeypatch.setattr(
        main,
        "_enrich_artist_metadata",
        lambda *_args: events.append("metadata_enriched"),
    )

    def summaries(_database, timezone_name, now):
        assert timezone_name == "Asia/Shanghai"
        assert now.tzinfo is not None
        events.append("daily_analytics")
        return empty_summary, empty_summary, profile

    captured = []
    monkeypatch.setattr(main, "_daily_listening_summaries", summaries)

    def capture_memory(_database, timezone_name, _now):
        events.append("memory_captured")
        captured.append(timezone_name)
        return object()

    monkeypatch.setattr(
        main,
        "_capture_current_memory",
        capture_memory,
    )

    def recent_facts(_engine, timezone_name, _now):
        events.append("recent_analysis")
        captured.append(timezone_name)
        return []

    monkeypatch.setattr(
        main,
        "_recent_listening_facts",
        recent_facts,
    )

    def output(received_profile, facts, *, recent_facts):
        events.append("product_output")
        assert received_profile is profile
        assert recent_facts == []
        captured.append(tuple(facts))

    monkeypatch.setattr(main, "_print_daily_outputs", output)

    main.main()

    assert events.index("metadata_persisted") < events.index("memory_captured")
    assert events.index("metadata_enriched") < events.index("memory_captured")
    assert events.index("raw_playback_saved") < events.index("memory_captured")
    assert events.index("daily_analytics") < events.index("memory_captured")
    assert events.index("memory_captured") < events.index("recent_analysis")
    assert events.index("memory_captured") < events.index("product_output")
    assert events.count("memory_captured") == 1
    assert captured[0] == "Asia/Shanghai"
    assert captured[1] == "Asia/Shanghai"
    assert [fact.category for fact in captured[2]] == [
        "listening_time",
        "playback_count",
    ]


def test_invalid_timezone_fails_before_spotify_authentication(monkeypatch) -> None:
    monkeypatch.setattr(main, "load_spotify_settings", lambda: object())
    monkeypatch.setattr(
        main,
        "load_musicmind_timezone",
        lambda: (_ for _ in ()).throw(RuntimeError("invalid timezone")),
    )

    class UnexpectedAuth:
        def __init__(self, _settings):
            raise AssertionError("Spotify auth must not start.")

    monkeypatch.setattr(main, "SpotifyAuth", UnexpectedAuth)

    with pytest.raises(RuntimeError, match="invalid timezone"):
        main.main()
