"""Isolated tests for Narrative and AI runtime coexistence."""

from datetime import date, datetime, timezone

import pytest

import main
from music_ai.ai import InterpretationRequest
from music_ai.analytics import DailyListeningProfile, ListeningSummary
from music_ai.knowledge import (
    FactCategory,
    FactSource,
    FactTimeHorizon,
    ImportanceLevel,
    InsightType,
    KnowledgeFact,
    knowledge_evidence_id,
)
from music_ai.memory import ListeningMemory
from music_ai.signal import (
    ClaimScope,
    EvidenceMaturity,
    KnowledgeEvidenceRef,
    ObservationWindow,
    ReferenceValue,
    Signal,
    SignalCaveat,
    SignalHorizon,
    SignalRoleEligibility,
    SignalState,
    SignalType,
    SupportDimension,
    WindowLabel,
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


def _planned_signal(maturity: EvidenceMaturity) -> Signal:
    return Signal(
        signal_id=f"runtime-{maturity}",
        signal_type=SignalType.LISTENING_TIME_OF_DAY_PATTERN,
        state=SignalState.OBSERVED_EVENTS_CONCENTRATED_IN_SEGMENT,
        subject_key="listening:all_events",
        subject_label=None,
        horizon=SignalHorizon.LONG_TERM,
        windows=(
            ObservationWindow(
                WindowLabel.CURRENT,
                date(2026, 7, 15),
                date(2026, 8, 14),
            ),
        ),
        maturity=maturity,
        supporting_dimensions=(SupportDimension("segment_listening_days", 5),),
        reference_values=(ReferenceValue("segment", "18:00-24:00"),),
        claim_scopes=(ClaimScope.OBSERVED_EVENT_DISTRIBUTION,),
        caveats=(SignalCaveat.EVENT_COUNT_NOT_LISTENING_TIME,),
        evidence_refs=(KnowledgeEvidenceRef("runtime-evidence", "context", None),),
        role_eligibility=(
            SignalRoleEligibility.WATCH_ONLY
            if maturity is EvidenceMaturity.PRELIMINARY
            else SignalRoleEligibility.PRIMARY_OR_SECONDARY
        ),
    )


def _projecting(signal: Signal):
    class FakeProjector:
        def project(self, _facts):
            return (signal,)

    return FakeProjector


@pytest.mark.parametrize(
    ("locale", "expected_status"),
    [
        (
            main.SupportedLocale.EN_US,
            "There are no new listening changes worth a separate interpretation today.",
        ),
        (
            main.SupportedLocale.ZH_CN,
            "今天还没有出现值得单独解读的新变化。",
        ),
    ],
)
def test_zero_signals_render_localized_status_without_provider(
    monkeypatch,
    locale,
    expected_status,
) -> None:
    events: list[object] = []
    facts: list[KnowledgeFact] = []

    def factory(locale):
        raise AssertionError("An empty plan must not construct or call a provider.")

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

    main._print_daily_outputs(_profile(), facts, factory, locale=locale)

    assert events[0][0] == "daily"
    assert events[1] == ("ai", expected_status)
    assert "raw_daily" not in events
    assert "raw_trends" not in events
    assert "raw_insights" not in events


def test_recent_facts_render_unchanged_when_no_interpretation_signal_qualifies(
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
        lambda _locale: (_ for _ in ()).throw(
            AssertionError("No provider should be constructed.")
        ),
        recent_facts=(recent_fact,),
    )

    assert "## Recently" in events[0][1]
    assert recent_fact.description in events[0][1]
    assert events[1][0] == "ai"
    assert "worth a separate interpretation" in events[1][1]


def test_closed_recent_signal_seam_excludes_open_visible_evidence_and_reaches_provider(
    monkeypatch,
) -> None:
    events: list[object] = []
    open_visible_fact = KnowledgeFact(
        category=FactCategory.ARTIST_EMERGENCE,
        importance=ImportanceLevel.HIGH,
        title="Visible recent emergence",
        description="Artist One grew in the visible open-inclusive window.",
        metadata={
            "subject_key": "spotify:artist-one",
            "concept_key": "artist_emergence",
            "artist_name": "Artist One",
            "recent_duration_share": 0.40,
            "comparison_duration_share": 0.10,
            "duration_share_change": 0.30,
            "recent_closed_listening_day_count": 4,
            "comparison_closed_listening_day_count": 4,
            "recent_closed_artist_day_count": 3,
            "contains_open_day": True,
        },
        source=FactSource.RECENT_LISTENING_EVIDENCE,
        date_range=("2026-07-24", "2026-08-07"),
        insight_type=InsightType.BEHAVIOR,
        time_horizon=FactTimeHorizon.RECENT,
    )
    closed_signal_fact = KnowledgeFact(
        category=FactCategory.ARTIST_EMERGENCE,
        importance=ImportanceLevel.HIGH,
        title="Closed recent emergence",
        description="Artist One grew in the closed interpretation window.",
        metadata={
            "subject_key": "spotify:artist-one",
            "concept_key": "artist_emergence",
            "artist_name": "Artist One",
            "recent_duration_share": 0.42,
            "comparison_duration_share": 0.10,
            "duration_share_change": 0.32,
            "recent_closed_listening_day_count": 4,
            "comparison_closed_listening_day_count": 4,
            "recent_closed_artist_day_count": 3,
            "contains_open_day": False,
        },
        source=FactSource.RECENT_LISTENING_EVIDENCE,
        date_range=("2026-07-23", "2026-08-06"),
        insight_type=InsightType.BEHAVIOR,
        time_horizon=FactTimeHorizon.RECENT,
    )
    real_projector = main.SignalProjector()
    projected_inputs: list[tuple[KnowledgeFact, ...]] = []
    projected_signals: list[tuple[Signal, ...]] = []

    class RecordingProjector:
        def project(self, facts):
            resolved = tuple(facts)
            projected_inputs.append(resolved)
            signals = real_projector.project(resolved)
            projected_signals.append(signals)
            return signals

    class Generator:
        def generate_report(self, request):
            events.append(("provider", request))
            return "Artist One has a closed recent movement worth watching."

    monkeypatch.setattr(main, "SignalProjector", RecordingProjector)
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
        (),
        lambda _locale: Generator(),
        recent_facts=(open_visible_fact,),
        closed_recent_signal_facts=(closed_signal_fact,),
    )

    visible_report = events[0][1]
    assert open_visible_fact.description in visible_report
    assert closed_signal_fact.description not in visible_report
    assert projected_inputs == [(closed_signal_fact,)]
    assert events[1][0] == "provider"
    closed_evidence_id = knowledge_evidence_id(closed_signal_fact)
    open_evidence_id = knowledge_evidence_id(open_visible_fact)
    assert projected_signals
    assert any(
        reference.evidence_id == closed_evidence_id
        for signal in projected_signals[0]
        for reference in signal.evidence_refs
    )
    assert all(
        reference.evidence_id != open_evidence_id
        for signal in projected_signals[0]
        for reference in signal.evidence_refs
    )
    assert events[2][0] == "ai"


def test_visible_long_term_state_is_suppressed_as_pure_ai_restatement(
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
        date_range=("2026-07-15", "2026-08-14"),
    )

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
        lambda _locale: (_ for _ in ()).throw(
            AssertionError("Pure restatement must not call a provider.")
        ),
        long_term_state_facts=(long_term_fact,),
    )

    assert "## Over Time" in events[0][1]
    assert long_term_fact.description in events[0][1]
    assert events[1][0] == "ai"
    assert "worth a separate interpretation" in events[1][1]


def test_long_term_evolution_reaches_ai_only_through_a_typed_selected_request(
    monkeypatch,
) -> None:
    events: list[object] = []
    daily_facts = [_fact()]
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
            "artist_name": "Artist One",
        },
        insight_type=InsightType.BEHAVIOR,
        time_horizon=FactTimeHorizon.LONG_TERM,
        date_range=("2026-06-15", "2026-08-14"),
    )

    class FakeReportGenerator:
        def generate_report(self, request):
            events.append(("generate_ai", request))
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
        long_term_evolution_facts=(evolution_fact,),
    )

    assert "## Over Time" in events[0][1]
    assert evolution_fact.description in events[0][1]
    assert events[1][0] == "generate_ai"
    assert isinstance(events[1][1], InterpretationRequest)
    assert "Artist One" in events[1][1].to_json()
    assert "You played one more track" not in events[1][1].to_json()
    assert events[2] == ("ai", "AI report")


def test_watch_only_plan_invokes_provider_with_typed_target_locale(
    monkeypatch,
) -> None:
    events: list[object] = []
    signal = _planned_signal(EvidenceMaturity.PRELIMINARY)
    monkeypatch.setattr(main, "SignalProjector", _projecting(signal))
    monkeypatch.setattr(
        main,
        "_print_daily_narrative",
        lambda report: events.append(("daily", report)),
    )
    monkeypatch.setattr(
        main,
        "_print_ai_report",
        lambda report, *, locale: events.append(("ai", locale, report)),
    )

    class Generator:
        def generate_report(self, request):
            assert isinstance(request, InterpretationRequest)
            assert request.target_locale == "zh-CN"
            assert tuple(item.role for item in request.plan_items) == ("watch",)
            events.append("provider")
            return "这个时段分布仍值得观察。"

    main._print_daily_outputs(
        _profile(),
        (),
        lambda locale: Generator(),
        locale=main.SupportedLocale.ZH_CN,
    )

    assert events[0][0] == "daily"
    assert "MusicMind 每日听歌报告" in events[0][1]
    assert events[1] == "provider"
    assert events[2][2] == "这个时段分布仍值得观察。"


@pytest.mark.parametrize("failure", [RuntimeError("transport"), RuntimeError("invalid response")])
def test_provider_or_validation_failure_preserves_deterministic_output_and_shows_failure(
    monkeypatch,
    failure,
) -> None:
    events: list[tuple[str, str]] = []
    monkeypatch.setattr(
        main,
        "SignalProjector",
        _projecting(_planned_signal(EvidenceMaturity.SUPPORTED)),
    )
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

    class FailingGenerator:
        def generate_report(self, _request):
            raise failure

    main._print_daily_outputs(
        _profile(),
        (),
        lambda _locale: FailingGenerator(),
    )

    assert events[0][0] == "daily"
    assert "# MusicMind Daily" in events[0][1]
    assert events[1] == (
        "ai",
        "MusicMind AI could not generate an interpretation this time.",
    )


def test_contextual_interpretation_failure_cannot_suppress_deterministic_report(
    monkeypatch,
) -> None:
    events: list[tuple[str, str]] = []
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
        (),
        lambda _locale: (_ for _ in ()).throw(
            AssertionError("A failed interpretation boundary cannot call a provider.")
        ),
        interpretation_failure=RuntimeError("context unavailable"),
    )

    assert events[0][0] == "daily"
    assert "# MusicMind Daily" in events[0][1]
    assert events[1][0] == "ai"
    assert "could not generate" in events[1][1]


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
    recent_analyzer_calls: list[
        tuple[ListeningMemory, dict[str, object]]
    ] = []
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
    closed_recent_evidence = object()
    state_evidence = object()
    evolution_evidence = object()

    class FakeRecentAnalytics:
        def analyze(self, received_memory, **kwargs):
            recent_analyzer_calls.append((received_memory, kwargs))
            return (
                recent_evidence
                if len(recent_analyzer_calls) == 1
                else closed_recent_evidence
            )

    class FakeStateAnalytics:
        def analyze(self, received_memory, **kwargs):
            analyzer_calls["state"] = (received_memory, kwargs)
            return state_evidence

    class FakeEvolutionAnalytics:
        def analyze(self, received_memory, **kwargs):
            analyzer_calls["evolution"] = (received_memory, kwargs)
            return evolution_evidence

    recent_facts = [_fact()]
    closed_recent_facts = [_fact()]
    state_facts = (_fact(),)
    evolution_facts = (_fact(),)
    facts_by_evidence = {
        recent_evidence: recent_facts,
        closed_recent_evidence: closed_recent_facts,
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

    (
        recent,
        closed_recent,
        state,
        evolution,
        interpretation_failure,
    ) = main._longitudinal_listening_facts(
        FakeMemoryEngine(),  # type: ignore[arg-type]
        "Asia/Shanghai",
        as_of,
    )

    assert calls == [(date(2026, 6, 7), date(2026, 8, 7))]
    assert all(
        received_memory is memory
        for received_memory, _kwargs in (
            *recent_analyzer_calls,
            *analyzer_calls.values(),
        )
    )
    assert recent_analyzer_calls[0] == (
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
    assert recent_analyzer_calls[1] == (
        memory,
        {
            "recent_start_date": date(2026, 7, 30),
            "recent_end_date": date(2026, 8, 6),
            "comparison_start_date": date(2026, 7, 23),
            "comparison_end_date": date(2026, 7, 30),
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
    assert closed_recent is closed_recent_facts
    assert state is state_facts
    assert evolution is evolution_facts
    assert interpretation_failure is None


def test_closed_recent_analysis_failure_preserves_visible_longitudinal_report(
    monkeypatch,
) -> None:
    as_of = datetime(2026, 8, 6, 8, tzinfo=timezone.utc)
    memory = ListeningMemory(
        start_date=date(2026, 6, 7),
        end_date=date(2026, 8, 7),
        timezone_name="Asia/Shanghai",
        snapshots=(),
        as_of=as_of,
    )
    load_calls: list[tuple[date, date]] = []

    class FakeMemoryEngine:
        def load_range(self, start_date, end_date):
            load_calls.append((start_date, end_date))
            return memory

    visible_evidence = object()
    state_evidence = object()
    evolution_evidence = object()
    closed_failure = RuntimeError("closed Recent unavailable")
    recent_calls = 0

    class FakeRecentAnalytics:
        def analyze(self, _memory, **_kwargs):
            nonlocal recent_calls
            recent_calls += 1
            if recent_calls == 2:
                raise closed_failure
            return visible_evidence

    class FakeStateAnalytics:
        def analyze(self, _memory, **_kwargs):
            return state_evidence

    class FakeEvolutionAnalytics:
        def analyze(self, _memory, **_kwargs):
            return evolution_evidence

    visible_recent_fact = KnowledgeFact(
        category=FactCategory.ARTIST_CONTINUITY,
        importance=ImportanceLevel.MEDIUM,
        title="Visible Recent",
        description="Visible Recent remains available.",
        insight_type=InsightType.BEHAVIOR,
        time_horizon=FactTimeHorizon.RECENT,
    )
    state_fact = _fact()
    evolution_fact = _fact()
    facts_by_evidence = {
        visible_evidence: [visible_recent_fact],
        state_evidence: (state_fact,),
        evolution_evidence: (evolution_fact,),
    }

    class FakeKnowledgeEngine:
        def __init__(self, evidence):
            self._facts = facts_by_evidence[evidence]

        def generate_facts(self):
            return self._facts

    monkeypatch.setattr(main, "TemporalListeningAnalytics", FakeRecentAnalytics)
    monkeypatch.setattr(main, "LongTermListeningAnalytics", FakeStateAnalytics)
    monkeypatch.setattr(
        main,
        "LongTermEvolutionAnalytics",
        FakeEvolutionAnalytics,
    )
    monkeypatch.setattr(main, "RecentKnowledgeEngine", FakeKnowledgeEngine)
    monkeypatch.setattr(main, "LongTermKnowledgeEngine", FakeKnowledgeEngine)
    monkeypatch.setattr(
        main,
        "LongTermEvolutionKnowledgeEngine",
        FakeKnowledgeEngine,
    )

    recent, closed, state, evolution, failure = (
        main._longitudinal_listening_facts(
            FakeMemoryEngine(),  # type: ignore[arg-type]
            "Asia/Shanghai",
            as_of,
        )
    )

    assert load_calls == [(date(2026, 6, 7), date(2026, 8, 7))]
    assert recent == [visible_recent_fact]
    assert closed == []
    assert state == (state_fact,)
    assert evolution == (evolution_fact,)
    assert failure is closed_failure

    events: list[tuple[str, str]] = []
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
        (),
        lambda _locale: (_ for _ in ()).throw(
            AssertionError("A failed closed pass cannot call a provider.")
        ),
        recent_facts=recent,
        closed_recent_signal_facts=closed,
        long_term_state_facts=state,
        long_term_evolution_facts=evolution,
        interpretation_failure=failure,
    )

    assert visible_recent_fact.description in events[0][1]
    assert events[1] == (
        "ai",
        "MusicMind AI could not generate an interpretation this time.",
    )


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
