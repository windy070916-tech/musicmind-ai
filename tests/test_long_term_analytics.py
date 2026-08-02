"""Focused tests for deterministic long-term Temporal Analytics."""

from dataclasses import FrozenInstanceError
from datetime import date, datetime, timedelta, timezone

import pytest

from music_ai.analytics import DailyListeningProfile, RankedArtist
from music_ai.memory import CURRENT_SNAPSHOT_VERSION, DailyMemorySnapshot, ListeningMemory
from music_ai.temporal import LongTermListeningAnalytics


_AS_OF = datetime(2026, 7, 31, 12, tzinfo=timezone.utc)


def _snapshot(
    local_date: date,
    artists: tuple[tuple[str | None, str, int], ...] = (),
    *,
    closed: bool = True,
    total_duration_ms: int | None = None,
) -> DailyMemorySnapshot:
    total = (
        sum(duration for _, _, duration in artists)
        if total_duration_ms is None
        else total_duration_ms
    )
    ranked = tuple(
        RankedArtist(
            spotify_artist_id=artist_id,
            name=name,
            play_count=1,
            estimated_listening_duration_ms=duration,
            share=(duration / total if total > 0 else 0.0),
        )
        for artist_id, name, duration in artists
    )
    start = datetime.combine(local_date, datetime.min.time(), tzinfo=timezone.utc)
    profile = DailyListeningProfile(
        start_datetime=start,
        end_datetime=start + timedelta(days=1),
        total_estimated_listening_duration_ms=total,
        playback_count=int(total > 0),
        unique_track_count=int(total > 0),
        unique_track_ratio=float(total > 0),
        top_track_share=float(total > 0),
        genre_covered_duration_ms=0,
        genre_coverage=0.0,
        top_tracks=(),
        top_artists=ranked,
        top_albums=(),
        top_genres=(),
    )
    return DailyMemorySnapshot(
        local_date=local_date,
        timezone_name="UTC",
        profile=profile,
        generated_at=_AS_OF,
        is_closed=closed,
        snapshot_version=CURRENT_SNAPSHOT_VERSION,
    )


def _memory(
    start_date: date,
    end_date: date,
    snapshots: tuple[DailyMemorySnapshot, ...],
) -> ListeningMemory:
    return ListeningMemory(
        start_date=start_date,
        end_date=end_date,
        timezone_name="UTC",
        snapshots=snapshots,
        as_of=_AS_OF,
    )


def test_explicit_half_open_window_preserves_gaps_and_zero_listening_days() -> None:
    start = date(2026, 7, 1)
    snapshots = (
        _snapshot(start, (("a", "Artist A", 100),)),
        _snapshot(start + timedelta(days=2)),
        _snapshot(start + timedelta(days=3), (("b", "Artist B", 200),)),
        _snapshot(start + timedelta(days=4), (("outside", "Outside", 300),)),
    )
    evidence = LongTermListeningAnalytics().analyze(
        _memory(start, start + timedelta(days=5), snapshots),
        start_date=start,
        end_date=start + timedelta(days=4),
    )

    assert evidence.recorded_day_count == 3
    assert evidence.listening_day_count == 2
    assert evidence.closed_day_count == 3
    assert evidence.gap_dates == (start + timedelta(days=1),)
    assert evidence.total_estimated_listening_duration_ms == 300
    assert {item.artist_name for item in evidence.artist_consistency} == {
        "Artist A",
        "Artist B",
    }


@pytest.mark.parametrize(
    ("start_date", "end_date", "message"),
    (
        (date(2026, 7, 1), date(2026, 7, 1), "non-empty"),
        (date(2026, 6, 30), date(2026, 7, 2), "contained"),
        (date(2026, 7, 1), date(2026, 7, 4), "contained"),
    ),
)
def test_invalid_or_uncontained_windows_are_rejected(
    start_date: date, end_date: date, message: str
) -> None:
    memory = _memory(date(2026, 7, 1), date(2026, 7, 3), ())
    with pytest.raises(ValueError, match=message):
        LongTermListeningAnalytics().analyze(
            memory, start_date=start_date, end_date=end_date
        )


def test_timezone_mismatch_naive_as_of_and_wrong_memory_are_rejected() -> None:
    memory = _memory(date(2026, 7, 1), date(2026, 7, 3), ())
    analytics = LongTermListeningAnalytics()
    with pytest.raises(ValueError, match="match ListeningMemory"):
        analytics.analyze(
            memory,
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 2),
            timezone_name="Asia/Shanghai",
        )
    with pytest.raises(ValueError, match="timezone-aware"):
        analytics.analyze(
            memory,
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 2),
            as_of=datetime(2026, 7, 2),
        )
    with pytest.raises(TypeError, match="ListeningMemory"):
        analytics.analyze(  # type: ignore[arg-type]
            object(), start_date=date(2026, 7, 1), end_date=date(2026, 7, 2)
        )


def test_artist_identity_is_id_first_normalized_and_has_stable_display_name() -> None:
    start = date(2026, 7, 1)
    snapshots = (
        _snapshot(
            start,
            (
                ("spotify-a", "Zulu Name", 10),
                (None, " Legacy Artist ", 20),
                (None, "Unknown artist", 30),
                (None, " ", 40),
            ),
        ),
        _snapshot(
            start + timedelta(days=1),
            (
                ("spotify-a", "Alpha Name", 10),
                (None, "legacy artist", 20),
            ),
        ),
    )
    evidence = LongTermListeningAnalytics().analyze(
        _memory(start, start + timedelta(days=2), snapshots),
        start_date=start,
        end_date=start + timedelta(days=2),
    )

    by_identity = {item.identity: item for item in evidence.artist_consistency}
    assert set(by_identity) == {
        ("spotify", "spotify-a"),
        ("legacy", "legacy artist"),
    }
    assert by_identity[("spotify", "spotify-a")].artist_name == "Alpha Name"
    assert by_identity[("legacy", "legacy artist")].appearance_day_count == 2


def test_spotify_backed_unusable_names_are_excluded_before_aggregation() -> None:
    start = date(2026, 7, 1)
    snapshot = _snapshot(
        start,
        (
            ("spotify-valid", "Valid Artist", 100),
            (None, " Legacy Artist ", 50),
            ("spotify-unknown", "Unknown artist", 100),
            ("spotify-uppercase", "UNKNOWN ARTIST", 100),
            ("spotify-blank", "", 100),
            ("spotify-whitespace", "   ", 100),
        ),
    )
    evidence = LongTermListeningAnalytics().analyze(
        _memory(start, start + timedelta(days=1), (snapshot,)),
        start_date=start,
        end_date=start + timedelta(days=1),
    )

    consistency = {item.identity: item for item in evidence.artist_consistency}
    assert set(consistency) == {
        ("spotify", "spotify-valid"),
        ("legacy", "legacy artist"),
    }
    assert consistency[("spotify", "spotify-valid")].appearance_day_count == 1
    assert consistency[("legacy", "legacy artist")].appearance_day_count == 1

    concentration = evidence.listening_concentration
    assert concentration.distinct_artist_count == 2
    assert concentration.total_attributed_artist_duration_ms == 150
    assert concentration.total_estimated_listening_duration_ms == 550
    assert concentration.top_one_duration_share == pytest.approx(100 / 550)
    assert concentration.top_five_duration_share == pytest.approx(150 / 550)

    breadth = evidence.artist_breadth
    assert breadth.unique_artist_count == 2
    assert breadth.single_day_artist_count == 2
    assert breadth.repeated_artist_count == 0
    assert breadth.artist_day_appearance_count == 2
    assert breadth.artists_per_listening_day == pytest.approx(2.0)
    assert evidence.total_estimated_listening_duration_ms == 550


def test_all_metrics_prefix_values_structural_transitions_and_ordering() -> None:
    start = date(2026, 7, 1)
    snapshots = []
    for index in range(10):
        artists: list[tuple[str | None, str, int]] = [
            ("a", "Artist A", 50),
            (f"unique-{index}", f"Unique {index}", 20),
        ]
        if index < 5:
            artists.append(("b", "Artist B", 30))
        snapshots.append(
            _snapshot(
                start + timedelta(days=index),
                tuple(reversed(artists)) if index % 2 else tuple(artists),
                closed=index < 7,
            )
        )
    evidence = LongTermListeningAnalytics().analyze(
        _memory(start, start + timedelta(days=10), tuple(snapshots)),
        start_date=start,
        end_date=start + timedelta(days=10),
    )

    consistency = evidence.artist_consistency
    assert [item.artist_name for item in consistency[:2]] == ["Artist A", "Artist B"]
    assert consistency[0].appearance_day_count == 10
    assert consistency[0].appearance_share == pytest.approx(1.0)
    assert consistency[0].aggregate_duration_ms == 500
    assert consistency[0].duration_share == pytest.approx(500 / 850)
    assert consistency[0].prefix_appearance_day_count == 9
    assert consistency[0].prefix_listening_day_count == 9
    assert consistency[0].evidence_sufficient is True
    assert consistency[0].prefix_evidence_sufficient is False
    assert consistency[0].structural_transition is True

    concentration = evidence.listening_concentration
    assert concentration.distinct_artist_count == 12
    assert concentration.top_one_duration_share == pytest.approx(500 / 850)
    assert concentration.top_five_duration_share == pytest.approx(710 / 850)
    assert concentration.total_attributed_artist_duration_ms == 850
    assert concentration.listening_day_count == 10
    assert concentration.closed_listening_day_count == 7
    assert concentration.evidence_sufficient is True
    assert concentration.prefix_evidence_sufficient is False
    assert concentration.structural_transition is True

    breadth = evidence.artist_breadth
    assert breadth.unique_artist_count == 12
    assert breadth.single_day_artist_count == 10
    assert breadth.repeated_artist_count == 2
    assert breadth.artist_day_appearance_count == 25
    assert breadth.artists_per_listening_day == pytest.approx(2.5)
    assert breadth.prefix_unique_artist_count == 11
    assert breadth.prefix_artist_day_appearance_count == 23
    assert breadth.evidence_sufficient is True
    assert breadth.prefix_evidence_sufficient is False
    assert breadth.structural_transition is True
    assert evidence.contains_open_day is True


def test_open_snapshots_participate_but_cannot_independently_support_conclusions() -> None:
    start = date(2026, 7, 1)
    snapshots = tuple(
        _snapshot(
            start + timedelta(days=index),
            ((f"artist-{index}", f"Artist {index}", 100),),
            closed=False,
        )
        for index in range(10)
    )
    evidence = LongTermListeningAnalytics().analyze(
        _memory(start, start + timedelta(days=10), snapshots),
        start_date=start,
        end_date=start + timedelta(days=10),
    )

    assert evidence.listening_day_count == 10
    assert evidence.closed_day_count == 0
    assert evidence.contains_open_day is True
    assert evidence.listening_concentration.evidence_sufficient is False
    assert evidence.artist_breadth.evidence_sufficient is False
    assert all(not item.evidence_sufficient for item in evidence.artist_consistency)


def test_long_term_evidence_is_frozen_and_snapshots_collections() -> None:
    start = date(2026, 7, 1)
    evidence = LongTermListeningAnalytics().analyze(
        _memory(start, start + timedelta(days=1), (_snapshot(start),)),
        start_date=start,
        end_date=start + timedelta(days=1),
    )

    assert isinstance(evidence.artist_consistency, tuple)
    assert isinstance(evidence.gap_dates, tuple)
    with pytest.raises(FrozenInstanceError):
        evidence.recorded_day_count = 2  # type: ignore[misc]
