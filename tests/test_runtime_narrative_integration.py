"""Isolated tests for Narrative and AI runtime coexistence."""

from datetime import date, datetime, timezone

import main
from music_ai.analytics import DailyListeningProfile, ListeningSummary
from music_ai.knowledge import (
    FactCategory,
    FactTimeHorizon,
    ImportanceLevel,
    InsightType,
    KnowledgeFact,
)
from music_ai.memory import ListeningMemory


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

    def factory(locale):
        assert locale.value == "en-US"
        events.append("construct_ai")
        return FakeReportGenerator()

    monkeypatch.setattr(
        main,
        "_print_daily_narrative",
        lambda report: events.append(("daily", report)),
    )
    monkeypatch.setattr(
        main,
        "_print_ai_report",
        lambda report, *, locale: events.append(("ai", report)),
    )
    monkeypatch.setattr(
        main, "_print_daily_facts", lambda _facts: events.append("raw_daily")
    )
    monkeypatch.setattr(
        main,
        "_print_daily_trends",
        lambda _facts: events.append("raw_trends"),
    )
    monkeypatch.setattr(
        main,
        "_print_insight_facts",
        lambda _facts: events.append("raw_insights"),
    )

    main._print_daily_outputs(_profile(), facts, factory)

    assert events[0][0] == "daily"
    assert events[1] == "construct_ai"
    assert events[2] == ("generate_ai", facts)
    assert events[3] == ("ai", "AI report")
    assert "raw_daily" not in events
    assert "raw_trends" not in events
    assert "raw_insights" not in events


def test_recent_facts_render_but_do_not_change_existing_ai_input(
    monkeypatch,
) -> None:
    events: list[object] = []
    daily_facts = [_fact()]
    recent_fact = KnowledgeFact(
        category=FactCategory.ARTIST_EMERGENCE,
        importance=ImportanceLevel.HIGH,
        title="Artist Emergence",
        description="Artist One grew in your recent listening.",
        insight_type=InsightType.BEHAVIOR,
        time_horizon=FactTimeHorizon.RECENT,
    )

    class FakeReportGenerator:
        def generate_daily_report(self, received_facts):
            events.append(("generate_ai", received_facts))
            return "AI report"

    monkeypatch.setattr(
        main,
        "_print_daily_narrative",
        lambda report: events.append(("daily", report)),
    )
    monkeypatch.setattr(
        main,
        "_print_ai_report",
        lambda report, *, locale: events.append(("ai", report)),
    )

    main._print_daily_outputs(
        _profile(),
        daily_facts,
        lambda _locale: FakeReportGenerator(),
        recent_facts=(recent_fact,),
    )

    assert "## Recently" in events[0][1]
    assert recent_fact.description in events[0][1]
    assert events[1] == ("generate_ai", daily_facts)
    assert events[1][1] is daily_facts
    assert events[2] == ("ai", "AI report")


def test_long_term_state_facts_render_but_do_not_change_existing_ai_input(
    monkeypatch,
) -> None:
    events: list[object] = []
    daily_facts = [_fact()]
    long_term_fact = KnowledgeFact(
        category=FactCategory.ARTIST_BREADTH,
        importance=ImportanceLevel.HIGH,
        title="Artist breadth",
        description="You listened to 20 artists across 16 recorded listening days.",
        metadata={
            "subject_key": "listening:all_artists",
            "concept_key": "artist_breadth",
        },
        insight_type=InsightType.BEHAVIOR,
        time_horizon=FactTimeHorizon.LONG_TERM,
    )

    class FakeReportGenerator:
        def generate_daily_report(self, received_facts):
            events.append(("generate_ai", received_facts))
            return "AI report"

    monkeypatch.setattr(
        main,
        "_print_daily_narrative",
        lambda report: events.append(("daily", report)),
    )
    monkeypatch.setattr(
        main,
        "_print_ai_report",
        lambda report, *, locale: events.append(("ai", report)),
    )

    main._print_daily_outputs(
        _profile(),
        daily_facts,
        lambda _locale: FakeReportGenerator(),
        long_term_state_facts=(long_term_fact,),
    )

    assert "## Over Time" in events[0][1]
    assert long_term_fact.description in events[0][1]
    assert events[1] == ("generate_ai", daily_facts)
    assert events[1][1] is daily_facts
    assert events[2] == ("ai", "AI report")


def test_long_term_evolution_facts_render_but_do_not_change_ai_input(
    monkeypatch,
) -> None:
    events: list[object] = []
    ai_facts = [_fact()]
    evolution_fact = KnowledgeFact(
        category=FactCategory.ARTIST_DURATION_SHARE_EVOLUTION,
        importance=ImportanceLevel.HIGH,
        title="Artist share increased",
        description=(
            "The share of attributable artist listening for Artist One increased "
            "from 20% in the previous 30-day period to 40% in the current "
            "30-day period."
        ),
        metadata={
            "subject_key": "spotify:artist-one",
            "concept_key": "artist_duration_share",
            "direction": "increase",
        },
        insight_type=InsightType.BEHAVIOR,
        time_horizon=FactTimeHorizon.LONG_TERM,
    )

    class FakeReportGenerator:
        def generate_daily_report(self, received_facts):
            events.append(("generate_ai", received_facts))
            return "AI report"

    monkeypatch.setattr(
        main,
        "_print_daily_narrative",
        lambda report: events.append(("daily", report)),
    )
    monkeypatch.setattr(
        main,
        "_print_ai_report",
        lambda report, *, locale: events.append(("ai", report)),
    )

    main._print_daily_outputs(
        _profile(),
        ai_facts,
        lambda _locale: FakeReportGenerator(),
        long_term_evolution_facts=(evolution_fact,),
    )

    assert "## Over Time" in events[0][1]
    assert evolution_fact.description in events[0][1]
    assert events[1] == ("generate_ai", ai_facts)
    assert events[1][1] is ai_facts
    assert events[2] == ("ai", "AI report")


def test_runtime_supplies_explicit_recent_and_comparison_windows() -> None:
    calls: list[tuple[date, date]] = []
    as_of = datetime(2026, 7, 24, 8, tzinfo=timezone.utc)

    class FakeMemoryEngine:
        def load_range(
            self, start_date: date, end_date: date
        ) -> ListeningMemory:
            calls.append((start_date, end_date))
            return ListeningMemory(
                start_date=start_date,
                end_date=end_date,
                timezone_name="Asia/Shanghai",
                snapshots=(),
                as_of=as_of,
            )

    facts = main._recent_listening_facts(
        FakeMemoryEngine(),  # type: ignore[arg-type]
        "Asia/Shanghai",
        as_of,
    )

    assert calls == [(date(2026, 7, 11), date(2026, 7, 25))]
    assert facts == []


def test_runtime_reuses_one_range_for_exact_longitudinal_windows(monkeypatch) -> None:
    calls: list[tuple[date, date]] = []
    analyzer_calls: dict[str, tuple[ListeningMemory, dict[str, object]]] = {}
    as_of = datetime(2026, 8, 6, 8, tzinfo=timezone.utc)
    memory = ListeningMemory(
        start_date=date(2026, 6, 7),
        end_date=date(2026, 8, 7),
        timezone_name="Asia/Shanghai",
        snapshots=(),
        as_of=as_of,
    )

    class FakeMemoryEngine:
        def load_range(
            self, start_date: date, end_date: date
        ) -> ListeningMemory:
            calls.append((start_date, end_date))
            return memory

    recent_evidence = object()
    state_evidence = object()
    evolution_evidence = object()

    class FakeRecentAnalytics:
        def analyze(self, received_memory, **kwargs):
            analyzer_calls["recent"] = (received_memory, kwargs)
            return recent_evidence

    class FakeStateAnalytics:
        def analyze(self, received_memory, **kwargs):
            analyzer_calls["state"] = (received_memory, kwargs)
            return state_evidence

    class FakeEvolutionAnalytics:
        def analyze(self, received_memory, **kwargs):
            analyzer_calls["evolution"] = (received_memory, kwargs)
            return evolution_evidence

    recent_facts = [_fact()]
    state_facts = (_fact(),)
    evolution_facts = (_fact(),)
    facts_by_evidence = {
        recent_evidence: recent_facts,
        state_evidence: state_facts,
        evolution_evidence: evolution_facts,
    }

    class FakeKnowledgeEngine:
        def __init__(self, evidence):
            self._facts = facts_by_evidence[evidence]

        def generate_facts(self):
            return self._facts

    monkeypatch.setattr(main, "TemporalListeningAnalytics", FakeRecentAnalytics)
    monkeypatch.setattr(main, "LongTermListeningAnalytics", FakeStateAnalytics)
    monkeypatch.setattr(main, "LongTermEvolutionAnalytics", FakeEvolutionAnalytics)
    monkeypatch.setattr(main, "RecentKnowledgeEngine", FakeKnowledgeEngine)
    monkeypatch.setattr(main, "LongTermKnowledgeEngine", FakeKnowledgeEngine)
    monkeypatch.setattr(main, "LongTermEvolutionKnowledgeEngine", FakeKnowledgeEngine)

    recent, state, evolution = main._longitudinal_listening_facts(
        FakeMemoryEngine(),  # type: ignore[arg-type]
        "Asia/Shanghai",
        as_of,
    )

    assert calls == [(date(2026, 6, 7), date(2026, 8, 7))]
    assert all(
        received_memory is memory
        for received_memory, _kwargs in analyzer_calls.values()
    )
    assert analyzer_calls["recent"] == (
        memory,
        {
            "recent_start_date": date(2026, 7, 31),
            "recent_end_date": date(2026, 8, 7),
            "comparison_start_date": date(2026, 7, 24),
            "comparison_end_date": date(2026, 7, 31),
            "timezone_name": "Asia/Shanghai",
            "as_of": as_of,
        },
    )
    assert analyzer_calls["state"] == (
        memory,
        {
            "start_date": date(2026, 7, 7),
            "end_date": date(2026, 8, 6),
            "timezone_name": "Asia/Shanghai",
            "as_of": as_of,
        },
    )
    assert analyzer_calls["evolution"] == (
        memory,
        {
            "previous_start_date": date(2026, 6, 7),
            "previous_end_date": date(2026, 7, 7),
            "current_start_date": date(2026, 7, 7),
            "current_end_date": date(2026, 8, 6),
            "timezone_name": "Asia/Shanghai",
            "as_of": as_of,
        },
    )
    assert recent is recent_facts
    assert state is state_facts
    assert evolution is evolution_facts


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
