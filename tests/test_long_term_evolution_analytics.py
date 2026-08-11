"""Focused tests for adjacent-window long-term evolution Analytics."""

from dataclasses import FrozenInstanceError, replace
from datetime import date, datetime, timedelta, timezone

import pytest

from music_ai.analytics import DailyListeningProfile, RankedArtist
from music_ai.memory import CURRENT_SNAPSHOT_VERSION, DailyMemorySnapshot, ListeningMemory
from music_ai.temporal import LongTermEvolutionAnalytics


_D = date(2026, 8, 6)
_PREVIOUS_START = _D - timedelta(days=60)
_CURRENT_START = _D - timedelta(days=30)
_AS_OF = datetime(2026, 8, 6, 12, tzinfo=timezone.utc)


def _snapshot(
    local_date: date,
    artists: tuple[tuple[str | None, str, int], ...],
    *,
    closed: bool = True,
    total_duration_ms: int | None = None,
) -> DailyMemorySnapshot:
    total = (
        sum(max(0, duration) for _, _, duration in artists)
        if total_duration_ms is None
        else total_duration_ms
    )
    start = datetime.combine(local_date, datetime.min.time(), tzinfo=timezone.utc)
    return DailyMemorySnapshot(
        local_date=local_date,
        timezone_name="UTC",
        profile=DailyListeningProfile(
            start_datetime=start,
            end_datetime=start + timedelta(days=1),
            total_estimated_listening_duration_ms=total,
            playback_count=int(total > 0),
            unique_track_count=int(total > 0),
            unique_track_ratio=float(total > 0),
            top_track_share=0.0,
            genre_covered_duration_ms=0,
            genre_coverage=0.0,
            top_tracks=(),
            top_artists=tuple(
                RankedArtist(artist_id, name, 1, duration, 0.0)
                for artist_id, name, duration in artists
            ),
            top_albums=(),
            top_genres=(),
        ),
        generated_at=_AS_OF,
        is_closed=closed,
        snapshot_version=CURRENT_SNAPSHOT_VERSION,
    )


def _memory(snapshots: tuple[DailyMemorySnapshot, ...]) -> ListeningMemory:
    return ListeningMemory(
        start_date=_PREVIOUS_START,
        end_date=_D + timedelta(days=1),
        timezone_name="UTC",
        snapshots=tuple(sorted(snapshots, key=lambda item: item.local_date)),
        as_of=_AS_OF,
    )


def _analyze(memory: ListeningMemory):
    return LongTermEvolutionAnalytics().analyze(
        memory,
        _PREVIOUS_START,
        _CURRENT_START,
        _CURRENT_START,
        _D,
        "UTC",
        _AS_OF,
    )


def test_sparse_adjacent_windows_emit_complete_identity_ordered_evidence() -> None:
    snapshots: list[DailyMemorySnapshot] = []
    for index in range(10):
        snapshots.append(
            _snapshot(
                _PREVIOUS_START + timedelta(days=index),
                (
                    ("artist-a", "Old A", 60),
                    (None, " Legacy C ", 40),
                    ("unknown", "Unknown artist", 10 if index == 0 else 0),
                ),
                closed=index < 7,
            )
        )
        snapshots.append(
            _snapshot(
                _CURRENT_START + timedelta(days=index),
                (
                    ("artist-a", "New A", 30),
                    ("artist-b", "Artist B", 70),
                ),
                closed=index < 7,
            )
        )

    evidence = _analyze(_memory(tuple(snapshots)))

    assert evidence.previous_window.start_date == _PREVIOUS_START
    assert evidence.previous_window.end_date == _CURRENT_START
    assert evidence.current_window.start_date == _CURRENT_START
    assert evidence.current_window.end_date == _D
    assert evidence.previous_window.recorded_day_count == 10
    assert len(evidence.previous_window.gap_dates) == 20
    assert evidence.previous_window.listening_day_count == 10
    assert evidence.previous_window.closed_listening_day_count == 7
    assert evidence.previous_window.contains_open_snapshot is True
    assert evidence.previous_window.structurally_sufficient is True
    assert evidence.current_window.structurally_sufficient is True
    assert evidence.comparison_evidence_sufficient is True
    assert evidence.artist_share_calculable is True

    assert tuple(item.identity for item in evidence.artist_share_candidates) == (
        ("legacy", "legacy c"),
        ("spotify", "artist-a"),
        ("spotify", "artist-b"),
    )
    legacy, artist_a, artist_b = evidence.artist_share_candidates
    assert legacy.previous_duration_ms == 400
    assert legacy.current_duration_ms == 0
    assert legacy.previous_share == pytest.approx(0.4)
    assert legacy.current_share == 0.0
    assert artist_a.artist_name == "New A"
    assert artist_a.previous_duration_ms == 600
    assert artist_a.current_duration_ms == 300
    assert artist_a.signed_share_change == pytest.approx(-0.3)
    assert artist_b.previous_duration_ms == 0
    assert artist_b.current_duration_ms == 700
    assert artist_b.signed_share_change == pytest.approx(0.7)

    assert evidence.previous_window.total_estimated_listening_duration_ms == 1_010
    assert evidence.previous_window.total_attributed_artist_duration_ms == 1_000
    assert evidence.concentration.previous_top_five_duration_ms == 1_000
    assert evidence.concentration.current_top_five_duration_ms == 1_000
    assert evidence.concentration.previous_share == 1.0
    assert evidence.concentration.current_share == 1.0
    assert evidence.concentration.signed_share_change == 0.0
    assert evidence.breadth.previous_artist_day_count == 20
    assert evidence.breadth.current_artist_day_count == 20
    assert evidence.breadth.previous_artists_per_listening_day == 2.0
    assert evidence.breadth.relative_change == 0.0


@pytest.mark.parametrize(
    ("previous_start", "previous_end", "current_start", "current_end", "message"),
    (
        (
            _PREVIOUS_START + timedelta(days=1),
            _CURRENT_START,
            _CURRENT_START,
            _D,
            "Previous.*30",
        ),
        (
            _PREVIOUS_START - timedelta(days=1),
            _CURRENT_START,
            _CURRENT_START,
            _D,
            "Previous.*30",
        ),
        (
            _PREVIOUS_START,
            _CURRENT_START,
            _CURRENT_START + timedelta(days=1),
            _D + timedelta(days=1),
            "adjacent",
        ),
        (
            _PREVIOUS_START,
            _CURRENT_START,
            _CURRENT_START - timedelta(days=1),
            _D - timedelta(days=1),
            "adjacent",
        ),
        (
            _PREVIOUS_START - timedelta(days=1),
            _CURRENT_START - timedelta(days=1),
            _CURRENT_START - timedelta(days=1),
            _D - timedelta(days=1),
            "contained",
        ),
        (
            _PREVIOUS_START + timedelta(days=2),
            _CURRENT_START + timedelta(days=2),
            _CURRENT_START + timedelta(days=2),
            _D + timedelta(days=2),
            "contained",
        ),
    ),
)
def test_window_geometry_and_memory_containment_are_validated(
    previous_start: date,
    previous_end: date,
    current_start: date,
    current_end: date,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        LongTermEvolutionAnalytics().analyze(
            _memory(()),
            previous_start,
            previous_end,
            current_start,
            current_end,
        )


@pytest.mark.parametrize(
    ("previous_shift", "current_shift", "message"),
    (
        (1, 1, "Current.*30"),
        (-1, -1, "Current.*30"),
    ),
)
def test_current_window_rejects_29_and_31_calendar_dates(
    previous_shift: int,
    current_shift: int,
    message: str,
) -> None:
    shared_boundary = _CURRENT_START + timedelta(days=previous_shift)
    previous_start = shared_boundary - timedelta(days=30)
    current_end = _D + timedelta(days=current_shift - previous_shift)
    with pytest.raises(ValueError, match=message):
        LongTermEvolutionAnalytics().analyze(
            _memory(()),
            previous_start,
            shared_boundary,
            shared_boundary,
            current_end,
        )


@pytest.mark.parametrize("day_shift", (-1, 1))
def test_exact_adjacent_windows_reject_current_end_before_or_after_local_d(
    day_shift: int,
) -> None:
    previous_start = _PREVIOUS_START + timedelta(days=day_shift)
    previous_end = _CURRENT_START + timedelta(days=day_shift)
    current_end = _D + timedelta(days=day_shift)
    memory = ListeningMemory(
        start_date=_PREVIOUS_START - timedelta(days=1),
        end_date=_D + timedelta(days=1),
        timezone_name="UTC",
        snapshots=(),
        as_of=_AS_OF,
    )
    with pytest.raises(ValueError, match="local date D"):
        LongTermEvolutionAnalytics().analyze(
            memory,
            previous_start,
            previous_end,
            previous_end,
            current_end,
        )


def test_current_window_must_end_at_local_d_and_context_must_match_memory() -> None:
    earlier_as_of = _AS_OF - timedelta(days=1)
    with pytest.raises(ValueError, match="ListeningMemory instant"):
        LongTermEvolutionAnalytics().analyze(
            _memory(()),
            _PREVIOUS_START,
            _CURRENT_START,
            _CURRENT_START,
            _D,
            "UTC",
            earlier_as_of,
        )
    with pytest.raises(ValueError, match="match ListeningMemory"):
        LongTermEvolutionAnalytics().analyze(
            _memory(()),
            _PREVIOUS_START,
            _CURRENT_START,
            _CURRENT_START,
            _D,
            "Asia/Shanghai",
            _AS_OF,
        )
    with pytest.raises(ValueError, match="valid IANA"):
        LongTermEvolutionAnalytics().analyze(
            _memory(()),
            _PREVIOUS_START,
            _CURRENT_START,
            _CURRENT_START,
            _D,
            "",
            _AS_OF,
        )

    memory = _memory(())
    object.__setattr__(memory, "as_of", _AS_OF + timedelta(days=1))
    with pytest.raises(ValueError, match="local date D"):
        LongTermEvolutionAnalytics().analyze(
            memory,
            _PREVIOUS_START,
            _CURRENT_START,
            _CURRENT_START,
            _D,
        )


@pytest.mark.parametrize(
    (
        "previous_days",
        "previous_closed",
        "current_days",
        "current_closed",
        "expected_previous",
        "expected_current",
    ),
    (
        (10, 7, 10, 7, True, True),
        (9, 7, 10, 7, False, True),
        (10, 6, 10, 7, False, True),
        (10, 7, 9, 7, True, False),
        (10, 7, 10, 6, True, False),
    ),
)
def test_each_window_independently_owns_the_10_7_structural_rule(
    previous_days: int,
    previous_closed: int,
    current_days: int,
    current_closed: int,
    expected_previous: bool,
    expected_current: bool,
) -> None:
    snapshots = tuple(
        _snapshot(
            start + timedelta(days=index),
            (("artist-a", "Artist A", 100),),
            closed=index < closed_count,
        )
        for start, day_count, closed_count in (
            (_PREVIOUS_START, previous_days, previous_closed),
            (_CURRENT_START, current_days, current_closed),
        )
        for index in range(day_count)
    )

    evidence = _analyze(_memory(snapshots))

    assert evidence.previous_window.structurally_sufficient is expected_previous
    assert evidence.current_window.structurally_sufficient is expected_current
    assert evidence.comparison_evidence_sufficient is (
        expected_previous and expected_current
    )


def test_cross_window_artist_identity_matching_and_non_bridging_are_explicit() -> None:
    evidence = _analyze(
        _memory(
            (
                _snapshot(
                    _PREVIOUS_START,
                    (
                        ("id-a", "Same Name", 40),
                        (None, " Legacy Name ", 30),
                        (None, "Bridge Name", 20),
                    ),
                ),
                _snapshot(
                    _CURRENT_START,
                    (
                        ("id-a", "Renamed A", 10),
                        ("id-b", "Same Name", 30),
                        (None, "legacy name", 20),
                        ("bridge-id", "Bridge Name", 40),
                    ),
                ),
            )
        )
    )

    by_identity = {
        candidate.identity: candidate
        for candidate in evidence.artist_share_candidates
    }
    assert tuple(by_identity) == (
        ("legacy", "bridge name"),
        ("legacy", "legacy name"),
        ("spotify", "bridge-id"),
        ("spotify", "id-a"),
        ("spotify", "id-b"),
    )
    assert by_identity[("spotify", "id-a")].artist_name == "Renamed A"
    assert by_identity[("legacy", "legacy name")].previous_duration_ms == 30
    assert by_identity[("legacy", "legacy name")].current_duration_ms == 20
    assert by_identity[("spotify", "id-b")].previous_duration_ms == 0
    assert by_identity[("legacy", "bridge name")].current_duration_ms == 0
    assert by_identity[("spotify", "bridge-id")].previous_duration_ms == 0


def test_concentration_uses_all_five_and_only_top_five_when_more_exist() -> None:
    previous_artists = tuple(
        (f"previous-{index}", f"Previous {index}", 50)
        for index in range(5)
    )
    current_artists = tuple(
        (f"current-{index}", f"Current {index}", duration)
        for index, duration in enumerate((60, 50, 40, 30, 20, 10))
    )
    concentration = _analyze(
        _memory(
            (
                _snapshot(_PREVIOUS_START, previous_artists),
                _snapshot(_CURRENT_START, current_artists),
            )
        )
    ).concentration

    assert concentration.previous_top_five_duration_ms == 250
    assert concentration.previous_share == 1.0
    assert concentration.current_attributed_duration_ms == 210
    assert concentration.current_top_five_duration_ms == 200
    assert concentration.current_share == pytest.approx(20 / 21)


@pytest.mark.parametrize("zero_previous", (True, False))
def test_one_zero_attributable_denominator_preserves_per_window_optional_ratios(
    zero_previous: bool,
) -> None:
    zero_snapshot = (("unknown", "Unknown artist", 100),)
    usable_snapshot = (("artist-a", "Artist A", 100),)
    previous_artists = zero_snapshot if zero_previous else usable_snapshot
    current_artists = usable_snapshot if zero_previous else zero_snapshot
    evidence = _analyze(
        _memory(
            (
                _snapshot(_PREVIOUS_START, previous_artists),
                _snapshot(_CURRENT_START, current_artists),
            )
        )
    )

    assert evidence.artist_share_calculable is False
    candidate = evidence.artist_share_candidates[0]
    assert candidate.previous_share == (None if zero_previous else 1.0)
    assert candidate.current_share == (1.0 if zero_previous else None)
    assert candidate.signed_share_change is None
    assert evidence.concentration.previous_share == (
        None if zero_previous else 1.0
    )
    assert evidence.concentration.current_share == (
        1.0 if zero_previous else None
    )
    assert evidence.concentration.signed_share_change is None
    assert evidence.concentration.is_calculable is False


def test_zero_attributable_windows_keep_structural_and_calculability_separate() -> None:
    snapshots = tuple(
        _snapshot(
            window_start + timedelta(days=index),
            (("unknown", "Unknown artist", 100),),
            closed=index < 7,
        )
        for window_start in (_PREVIOUS_START, _CURRENT_START)
        for index in range(10)
    )

    evidence = _analyze(_memory(snapshots))

    assert evidence.comparison_evidence_sufficient is True
    assert evidence.artist_share_calculable is False
    assert evidence.artist_share_candidates == ()
    assert evidence.concentration.is_calculable is False
    assert evidence.concentration.previous_share is None
    assert evidence.concentration.signed_share_change is None
    assert evidence.breadth.previous_artists_per_listening_day == 0.0
    assert evidence.breadth.current_artists_per_listening_day == 0.0
    assert evidence.breadth.signed_change == 0.0
    assert evidence.breadth.relative_change is None
    assert evidence.breadth.is_calculable is False


def test_positive_previous_and_zero_current_breadth_has_relative_change_minus_one() -> None:
    snapshots: list[DailyMemorySnapshot] = []
    for index in range(10):
        snapshots.append(
            _snapshot(
                _PREVIOUS_START + timedelta(days=index),
                (("artist-a", "Artist A", 100),),
                closed=index < 7,
            )
        )
        snapshots.append(
            _snapshot(
                _CURRENT_START + timedelta(days=index),
                (("unknown", "Unknown artist", 100),),
                closed=index < 7,
            )
        )

    breadth = _analyze(_memory(tuple(snapshots))).breadth

    assert breadth.previous_artists_per_listening_day == 1.0
    assert breadth.current_artists_per_listening_day == 0.0
    assert breadth.signed_change == -1.0
    assert breadth.relative_change == -1.0
    assert breadth.absolute_relative_change == 1.0
    assert breadth.is_calculable is True


def test_evolution_evidence_and_candidate_collections_are_immutable() -> None:
    snapshots = tuple(
        _snapshot(
            window_start,
            (("artist-a", "Artist A", 100),),
        )
        for window_start in (_PREVIOUS_START, _CURRENT_START)
    )
    evidence = _analyze(_memory(snapshots))

    assert isinstance(evidence.artist_share_candidates, tuple)
    with pytest.raises(FrozenInstanceError):
        evidence.artist_share_calculable = False  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        evidence.artist_share_candidates[0].artist_name = "Changed"  # type: ignore[misc]


def test_concentration_evidence_rejects_invalid_unclamped_ratios() -> None:
    evidence = _analyze(
        _memory(
            tuple(
                _snapshot(
                    window_start,
                    (("artist-a", "Artist A", 100),),
                )
                for window_start in (_PREVIOUS_START, _CURRENT_START)
            )
        )
    )

    with pytest.raises(ValueError, match="between 0 and 1"):
        replace(evidence.concentration, previous_share=1.1)
