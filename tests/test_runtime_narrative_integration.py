"""Isolated tests for Narrative and AI runtime coexistence."""

from datetime import datetime, timezone

import main
from music_ai.analytics import DailyListeningProfile, ListeningSummary
from music_ai.knowledge import (
    FactCategory,
    ImportanceLevel,
    InsightType,
    KnowledgeFact,
)


def _profile() -> DailyListeningProfile:
    return DailyListeningProfile(
        start_datetime=datetime(2026, 7, 21, tzinfo=timezone.utc),
        end_datetime=datetime(2026, 7, 22, tzinfo=timezone.utc),
        total_estimated_listening_duration_ms=60_000,
        playback_count=1,
        unique_track_count=1,
        unique_track_ratio=1.0,
        top_track_share=0.0,
        genre_covered_duration_ms=0,
        genre_coverage=0.0,
        top_tracks=(),
        top_artists=(),
        top_albums=(),
        top_genres=(),
    )


def _fact() -> KnowledgeFact:
    return KnowledgeFact(
        category=FactCategory.PLAYBACK_COUNT_CHANGE,
        importance=ImportanceLevel.MEDIUM,
        title="Playback Count Changed",
        description="You played one more track than yesterday.",
        insight_type=InsightType.TREND,
    )


def test_daily_outputs_print_narrative_before_constructing_and_calling_ai(monkeypatch) -> None:
    events: list[object] = []
    facts = [_fact()]

    class FakeReportGenerator:
        def generate_daily_report(self, received_facts):
            events.append(("generate_ai", received_facts))
            return "AI report"

    def factory():
        events.append("construct_ai")
        return FakeReportGenerator()

    monkeypatch.setattr(main, "_print_daily_narrative", lambda report: events.append(("daily", report)))
    monkeypatch.setattr(main, "_print_ai_report", lambda report: events.append(("ai", report)))
    monkeypatch.setattr(main, "_print_daily_facts", lambda _facts: events.append("raw_daily"))
    monkeypatch.setattr(main, "_print_daily_trends", lambda _facts: events.append("raw_trends"))
    monkeypatch.setattr(main, "_print_insight_facts", lambda _facts: events.append("raw_insights"))

    main._print_daily_outputs(_profile(), facts, factory)

    assert events[0][0] == "daily"
    assert events[1] == "construct_ai"
    assert events[2] == ("generate_ai", facts)
    assert events[3] == ("ai", "AI report")
    assert "raw_daily" not in events
    assert "raw_trends" not in events
    assert "raw_insights" not in events


def test_daily_summary_and_profile_share_exact_current_boundaries(monkeypatch) -> None:
    calls: list[tuple[str, datetime, datetime]] = []
    empty_summary = ListeningSummary(0, 0, (), ())
    profile = _profile()

    class FakeListeningAnalytics:
        def __init__(self, _database) -> None:
            pass

        def get_listening_summary(self, start: datetime, end: datetime) -> ListeningSummary:
            calls.append(("summary", start, end))
            return empty_summary

        def get_daily_listening_profile(
            self, start: datetime, end: datetime
        ) -> DailyListeningProfile:
            calls.append(("profile", start, end))
            return profile

    monkeypatch.setattr(main, "ListeningAnalytics", FakeListeningAnalytics)
    now = datetime(2026, 7, 22, 15, 30, tzinfo=timezone.utc)

    previous, current, current_profile = main._daily_listening_summaries(
        object(), "UTC", now
    )

    assert previous is empty_summary
    assert current is empty_summary
    assert current_profile is profile
    assert calls[1][1:] == calls[2][1:]
    assert calls[1][1] == datetime(2026, 7, 22, tzinfo=timezone.utc)
    assert calls[1][2] == datetime(2026, 7, 23, tzinfo=timezone.utc)
