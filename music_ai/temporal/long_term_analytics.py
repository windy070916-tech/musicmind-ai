"""Deterministic long-term calculations over bounded Listening Memory."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from music_ai.memory.models import ListeningMemory, timezone_for_name
from music_ai.temporal.long_term_models import (
    ArtistBreadthEvidence,
    ArtistConsistencyEvidence,
    ListeningConcentrationEvidence,
    LongTermListeningEvidence,
)
from music_ai.temporal.window_statistics import (
    ArtistWindowAggregate,
    ListeningWindowStatistics,
    calculate_listening_window_statistics,
)


_MIN_LISTENING_DAYS = 10
_MIN_CLOSED_LISTENING_DAYS = 7
_MIN_CONSISTENCY_APPEARANCE_DAYS = 3
_MIN_CONSISTENCY_CLOSED_DAYS = 3
_MIN_CONCENTRATION_ARTISTS = 10


@dataclass(frozen=True, slots=True)
class _EmptyPrefixStatistics:
    """Compatibility view for the empty prefix of a valid one-day state window."""

    listening_day_count: int
    closed_listening_day_count: int
    total_estimated_listening_duration_ms: int
    total_attributed_artist_duration_ms: int
    artist_day_appearance_count: int
    artists: tuple[ArtistWindowAggregate, ...]


_EMPTY_PREFIX = _EmptyPrefixStatistics(0, 0, 0, 0, 0, ())
_StateWindowStatistics = ListeningWindowStatistics | _EmptyPrefixStatistics


class LongTermListeningAnalytics:
    """Calculate long-term evidence without interpretation or persistence."""

    def analyze(
        self,
        memory: ListeningMemory,
        *,
        start_date: date,
        end_date: date,
        timezone_name: str | None = None,
        as_of: datetime | None = None,
    ) -> LongTermListeningEvidence:
        """Analyze one explicit half-open local-date window."""
        _validate_inputs(
            memory,
            start_date=start_date,
            end_date=end_date,
            timezone_name=timezone_name,
            as_of=as_of,
        )
        current = calculate_listening_window_statistics(
            memory.snapshots, start_date, end_date
        )
        prefix_end_date = end_date - timedelta(days=1)
        prefix: _StateWindowStatistics = (
            _EMPTY_PREFIX
            if prefix_end_date == start_date
            else calculate_listening_window_statistics(
                memory.snapshots, start_date, prefix_end_date
            )
        )
        return LongTermListeningEvidence(
            timezone_name=timezone_name or memory.timezone_name,
            as_of=as_of or memory.as_of,
            start_date=start_date,
            end_date=end_date,
            recorded_day_count=current.recorded_day_count,
            listening_day_count=current.listening_day_count,
            closed_day_count=current.closed_day_count,
            gap_dates=current.gap_dates,
            contains_open_day=current.contains_open_snapshot,
            total_estimated_listening_duration_ms=(
                current.total_estimated_listening_duration_ms
            ),
            artist_consistency=_artist_consistency(current, prefix),
            listening_concentration=_listening_concentration(current, prefix),
            artist_breadth=_artist_breadth(current, prefix),
        )


def _artist_consistency(
    current: ListeningWindowStatistics, prefix: _StateWindowStatistics
) -> tuple[ArtistConsistencyEvidence, ...]:
    records: list[ArtistConsistencyEvidence] = []
    prefix_artists = {artist.identity: artist for artist in prefix.artists}
    for artist in current.artists:
        identity = artist.identity
        prefix_artist = prefix_artists.get(identity)
        appearance_days = artist.appearance_day_count
        closed_days = artist.closed_supporting_day_count
        prefix_appearance_days = (
            prefix_artist.appearance_day_count if prefix_artist is not None else 0
        )
        prefix_closed_days = (
            prefix_artist.closed_supporting_day_count
            if prefix_artist is not None
            else 0
        )
        current_sufficient = _consistency_sufficient(
            current, appearance_days, closed_days
        )
        prefix_sufficient = _consistency_sufficient(
            prefix, prefix_appearance_days, prefix_closed_days
        )
        records.append(
            ArtistConsistencyEvidence(
                identity=identity,
                spotify_artist_id=(identity[1] if identity[0] == "spotify" else None),
                artist_name=artist.artist_name,
                appearance_day_count=appearance_days,
                listening_day_count=current.listening_day_count,
                closed_supporting_day_count=closed_days,
                aggregate_duration_ms=artist.duration_ms,
                appearance_share=_share(
                    appearance_days, current.listening_day_count
                ),
                duration_share=_share(
                    artist.duration_ms,
                    current.total_estimated_listening_duration_ms,
                ),
                evidence_sufficient=current_sufficient,
                prefix_appearance_day_count=prefix_appearance_days,
                prefix_listening_day_count=prefix.listening_day_count,
                prefix_closed_supporting_day_count=prefix_closed_days,
                prefix_aggregate_duration_ms=(
                    prefix_artist.duration_ms if prefix_artist is not None else 0
                ),
                prefix_appearance_share=_share(
                    prefix_appearance_days, prefix.listening_day_count
                ),
                prefix_duration_share=_share(
                    prefix_artist.duration_ms if prefix_artist is not None else 0,
                    prefix.total_estimated_listening_duration_ms,
                ),
                prefix_evidence_sufficient=prefix_sufficient,
                structural_transition=current_sufficient and not prefix_sufficient,
            )
        )
    return tuple(
        sorted(
            records,
            key=lambda item: (
                -item.appearance_share,
                -item.appearance_day_count,
                -item.duration_share,
                item.identity,
            ),
        )
    )


def _listening_concentration(
    current: ListeningWindowStatistics, prefix: _StateWindowStatistics
) -> ListeningConcentrationEvidence:
    current_shares = _top_duration_shares(current)
    prefix_shares = _top_duration_shares(prefix)
    current_sufficient = _concentration_sufficient(current)
    prefix_sufficient = _concentration_sufficient(prefix)
    return ListeningConcentrationEvidence(
        distinct_artist_count=len(current.artists),
        top_one_duration_share=current_shares[0],
        top_five_duration_share=current_shares[1],
        total_attributed_artist_duration_ms=(
            current.total_attributed_artist_duration_ms
        ),
        total_estimated_listening_duration_ms=(
            current.total_estimated_listening_duration_ms
        ),
        listening_day_count=current.listening_day_count,
        closed_listening_day_count=current.closed_listening_day_count,
        evidence_sufficient=current_sufficient,
        prefix_distinct_artist_count=len(prefix.artists),
        prefix_top_one_duration_share=prefix_shares[0],
        prefix_top_five_duration_share=prefix_shares[1],
        prefix_total_attributed_artist_duration_ms=(
            prefix.total_attributed_artist_duration_ms
        ),
        prefix_total_estimated_listening_duration_ms=(
            prefix.total_estimated_listening_duration_ms
        ),
        prefix_listening_day_count=prefix.listening_day_count,
        prefix_closed_listening_day_count=prefix.closed_listening_day_count,
        prefix_evidence_sufficient=prefix_sufficient,
        structural_transition=current_sufficient and not prefix_sufficient,
    )


def _artist_breadth(
    current: ListeningWindowStatistics, prefix: _StateWindowStatistics
) -> ArtistBreadthEvidence:
    current_counts = _breadth_counts(current)
    prefix_counts = _breadth_counts(prefix)
    current_sufficient = _breadth_sufficient(current)
    prefix_sufficient = _breadth_sufficient(prefix)
    return ArtistBreadthEvidence(
        unique_artist_count=current_counts[0],
        single_day_artist_count=current_counts[1],
        repeated_artist_count=current_counts[2],
        artist_day_appearance_count=current_counts[3],
        artists_per_listening_day=_ratio(
            current_counts[3], current.listening_day_count
        ),
        listening_day_count=current.listening_day_count,
        closed_listening_day_count=current.closed_listening_day_count,
        evidence_sufficient=current_sufficient,
        prefix_unique_artist_count=prefix_counts[0],
        prefix_single_day_artist_count=prefix_counts[1],
        prefix_repeated_artist_count=prefix_counts[2],
        prefix_artist_day_appearance_count=prefix_counts[3],
        prefix_artists_per_listening_day=_ratio(
            prefix_counts[3], prefix.listening_day_count
        ),
        prefix_listening_day_count=prefix.listening_day_count,
        prefix_closed_listening_day_count=prefix.closed_listening_day_count,
        prefix_evidence_sufficient=prefix_sufficient,
        structural_transition=current_sufficient and not prefix_sufficient,
    )


def _top_duration_shares(stats: _StateWindowStatistics) -> tuple[float, float]:
    durations = sorted(
        stats.artists,
        key=lambda item: (-item.duration_ms, item.identity),
    )
    return (
        _share(
            sum(item.duration_ms for item in durations[:1]),
            stats.total_estimated_listening_duration_ms,
        ),
        _share(
            sum(item.duration_ms for item in durations[:5]),
            stats.total_estimated_listening_duration_ms,
        ),
    )


def _breadth_counts(stats: _StateWindowStatistics) -> tuple[int, int, int, int]:
    counts = tuple(artist.appearance_day_count for artist in stats.artists)
    return (
        len(counts),
        sum(value == 1 for value in counts),
        sum(value > 1 for value in counts),
        sum(counts),
    )


def _consistency_sufficient(
    stats: _StateWindowStatistics,
    appearance_days: int,
    closed_supporting_days: int,
) -> bool:
    return (
        stats.listening_day_count >= _MIN_LISTENING_DAYS
        and stats.closed_listening_day_count >= _MIN_CLOSED_LISTENING_DAYS
        and stats.total_estimated_listening_duration_ms > 0
        and appearance_days >= _MIN_CONSISTENCY_APPEARANCE_DAYS
        and closed_supporting_days >= _MIN_CONSISTENCY_CLOSED_DAYS
    )


def _concentration_sufficient(stats: _StateWindowStatistics) -> bool:
    return (
        stats.listening_day_count >= _MIN_LISTENING_DAYS
        and stats.closed_listening_day_count >= _MIN_CLOSED_LISTENING_DAYS
        and stats.total_estimated_listening_duration_ms > 0
        and stats.total_attributed_artist_duration_ms > 0
        and len(stats.artists) >= _MIN_CONCENTRATION_ARTISTS
    )


def _breadth_sufficient(stats: _StateWindowStatistics) -> bool:
    return (
        stats.listening_day_count >= _MIN_LISTENING_DAYS
        and stats.closed_listening_day_count >= _MIN_CLOSED_LISTENING_DAYS
        and stats.total_estimated_listening_duration_ms > 0
    )


def _share(value: int, total: int) -> float:
    return value / total if total > 0 else 0.0


def _ratio(value: int, denominator: int) -> float:
    return value / denominator if denominator > 0 else 0.0


def _validate_inputs(
    memory: ListeningMemory,
    *,
    start_date: date,
    end_date: date,
    timezone_name: str | None,
    as_of: datetime | None,
) -> None:
    if not isinstance(memory, ListeningMemory):
        raise TypeError("memory must be a ListeningMemory.")
    for field_name, value in (("start_date", start_date), ("end_date", end_date)):
        if not isinstance(value, date) or isinstance(value, datetime):
            raise ValueError(f"{field_name} must be a date.")
    if start_date >= end_date:
        raise ValueError("The long-term window must be non-empty.")
    if start_date < memory.start_date or end_date > memory.end_date:
        raise ValueError("The long-term window must be contained in ListeningMemory.")
    if timezone_name is not None:
        timezone_for_name(timezone_name)
        if timezone_name != memory.timezone_name:
            raise ValueError("Analysis timezone must match ListeningMemory.")
    if as_of is not None and (
        not isinstance(as_of, datetime)
        or as_of.tzinfo is None
        or as_of.utcoffset() is None
    ):
        raise ValueError("as_of must be timezone-aware.")
