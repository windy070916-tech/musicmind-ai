"""Deterministic long-term calculations over bounded Listening Memory."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from music_ai.memory.models import DailyMemorySnapshot, ListeningMemory, timezone_for_name
from music_ai.temporal.long_term_models import (
    ArtistBreadthEvidence,
    ArtistConsistencyEvidence,
    ArtistIdentity,
    ListeningConcentrationEvidence,
    LongTermListeningEvidence,
)


_MIN_LISTENING_DAYS = 10
_MIN_CLOSED_LISTENING_DAYS = 7
_MIN_CONSISTENCY_APPEARANCE_DAYS = 3
_MIN_CONSISTENCY_CLOSED_DAYS = 3
_MIN_CONCENTRATION_ARTISTS = 10
_UNKNOWN_ARTIST = "unknown artist"


@dataclass(frozen=True, slots=True)
class _WindowStats:
    snapshots: tuple[DailyMemorySnapshot, ...]
    gap_dates: tuple[date, ...]
    recorded_day_count: int
    listening_day_count: int
    closed_day_count: int
    closed_listening_day_count: int
    total_duration_ms: int
    total_attributed_artist_duration_ms: int
    artist_duration_ms: dict[ArtistIdentity, int]
    artist_day_count: dict[ArtistIdentity, int]
    closed_artist_day_count: dict[ArtistIdentity, int]
    artist_names: dict[ArtistIdentity, tuple[str, ...]]
    contains_open_day: bool


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
        current = _window_stats(memory.snapshots, start_date, end_date)
        prefix = _window_stats(
            memory.snapshots,
            start_date,
            end_date - timedelta(days=1),
            allow_empty=True,
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
            contains_open_day=current.contains_open_day,
            total_estimated_listening_duration_ms=current.total_duration_ms,
            artist_consistency=_artist_consistency(current, prefix),
            listening_concentration=_listening_concentration(current, prefix),
            artist_breadth=_artist_breadth(current, prefix),
        )


def _window_stats(
    snapshots: tuple[DailyMemorySnapshot, ...],
    start_date: date,
    end_date: date,
    *,
    allow_empty: bool = False,
) -> _WindowStats:
    if start_date > end_date or (start_date == end_date and not allow_empty):
        raise ValueError("Analysis windows must be non-empty [start, end) ranges.")

    selected = tuple(
        snapshot
        for snapshot in snapshots
        if start_date <= snapshot.local_date < end_date
    )
    recorded_dates = {snapshot.local_date for snapshot in selected}
    gap_dates = tuple(
        candidate
        for candidate in _dates(start_date, end_date)
        if candidate not in recorded_dates
    )
    artist_duration_ms: defaultdict[ArtistIdentity, int] = defaultdict(int)
    artist_day_count: defaultdict[ArtistIdentity, int] = defaultdict(int)
    closed_artist_day_count: defaultdict[ArtistIdentity, int] = defaultdict(int)
    names: defaultdict[ArtistIdentity, set[str]] = defaultdict(set)
    listening_day_count = 0
    closed_listening_day_count = 0
    total_duration_ms = 0

    for snapshot in selected:
        profile = snapshot.profile
        day_duration = max(0, profile.total_estimated_listening_duration_ms)
        total_duration_ms += day_duration
        if day_duration > 0:
            listening_day_count += 1
            if snapshot.is_closed:
                closed_listening_day_count += 1

        present_today: set[ArtistIdentity] = set()
        for artist in profile.top_artists:
            duration = max(0, artist.estimated_listening_duration_ms)
            if duration <= 0:
                continue
            display_name = artist.name.strip()
            if not _usable_artist_name(display_name):
                continue
            identity = _artist_identity(artist.spotify_artist_id, display_name)
            if identity is None:
                continue
            names[identity].add(display_name)
            artist_duration_ms[identity] += duration
            present_today.add(identity)

        for identity in present_today:
            artist_day_count[identity] += 1
            if snapshot.is_closed:
                closed_artist_day_count[identity] += 1

    return _WindowStats(
        snapshots=selected,
        gap_dates=gap_dates,
        recorded_day_count=len(selected),
        listening_day_count=listening_day_count,
        closed_day_count=sum(snapshot.is_closed for snapshot in selected),
        closed_listening_day_count=closed_listening_day_count,
        total_duration_ms=total_duration_ms,
        total_attributed_artist_duration_ms=sum(artist_duration_ms.values()),
        artist_duration_ms=dict(artist_duration_ms),
        artist_day_count=dict(artist_day_count),
        closed_artist_day_count=dict(closed_artist_day_count),
        artist_names={
            identity: tuple(sorted(values)) for identity, values in names.items()
        },
        contains_open_day=any(not snapshot.is_closed for snapshot in selected),
    )


def _artist_consistency(
    current: _WindowStats, prefix: _WindowStats
) -> tuple[ArtistConsistencyEvidence, ...]:
    records: list[ArtistConsistencyEvidence] = []
    for identity in current.artist_duration_ms:
        names = current.artist_names.get(identity, ())
        if not names:
            continue
        appearance_days = current.artist_day_count.get(identity, 0)
        closed_days = current.closed_artist_day_count.get(identity, 0)
        prefix_appearance_days = prefix.artist_day_count.get(identity, 0)
        prefix_closed_days = prefix.closed_artist_day_count.get(identity, 0)
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
                artist_name=min(names),
                appearance_day_count=appearance_days,
                listening_day_count=current.listening_day_count,
                closed_supporting_day_count=closed_days,
                aggregate_duration_ms=current.artist_duration_ms[identity],
                appearance_share=_share(
                    appearance_days, current.listening_day_count
                ),
                duration_share=_share(
                    current.artist_duration_ms[identity], current.total_duration_ms
                ),
                evidence_sufficient=current_sufficient,
                prefix_appearance_day_count=prefix_appearance_days,
                prefix_listening_day_count=prefix.listening_day_count,
                prefix_closed_supporting_day_count=prefix_closed_days,
                prefix_aggregate_duration_ms=prefix.artist_duration_ms.get(identity, 0),
                prefix_appearance_share=_share(
                    prefix_appearance_days, prefix.listening_day_count
                ),
                prefix_duration_share=_share(
                    prefix.artist_duration_ms.get(identity, 0),
                    prefix.total_duration_ms,
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
    current: _WindowStats, prefix: _WindowStats
) -> ListeningConcentrationEvidence:
    current_shares = _top_duration_shares(current)
    prefix_shares = _top_duration_shares(prefix)
    current_sufficient = _concentration_sufficient(current)
    prefix_sufficient = _concentration_sufficient(prefix)
    return ListeningConcentrationEvidence(
        distinct_artist_count=len(current.artist_duration_ms),
        top_one_duration_share=current_shares[0],
        top_five_duration_share=current_shares[1],
        total_attributed_artist_duration_ms=(
            current.total_attributed_artist_duration_ms
        ),
        total_estimated_listening_duration_ms=current.total_duration_ms,
        listening_day_count=current.listening_day_count,
        closed_listening_day_count=current.closed_listening_day_count,
        evidence_sufficient=current_sufficient,
        prefix_distinct_artist_count=len(prefix.artist_duration_ms),
        prefix_top_one_duration_share=prefix_shares[0],
        prefix_top_five_duration_share=prefix_shares[1],
        prefix_total_attributed_artist_duration_ms=(
            prefix.total_attributed_artist_duration_ms
        ),
        prefix_total_estimated_listening_duration_ms=prefix.total_duration_ms,
        prefix_listening_day_count=prefix.listening_day_count,
        prefix_closed_listening_day_count=prefix.closed_listening_day_count,
        prefix_evidence_sufficient=prefix_sufficient,
        structural_transition=current_sufficient and not prefix_sufficient,
    )


def _artist_breadth(
    current: _WindowStats, prefix: _WindowStats
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


def _top_duration_shares(stats: _WindowStats) -> tuple[float, float]:
    durations = sorted(
        stats.artist_duration_ms.items(),
        key=lambda item: (-item[1], item[0]),
    )
    return (
        _share(sum(value for _, value in durations[:1]), stats.total_duration_ms),
        _share(sum(value for _, value in durations[:5]), stats.total_duration_ms),
    )


def _breadth_counts(stats: _WindowStats) -> tuple[int, int, int, int]:
    counts = tuple(stats.artist_day_count.values())
    return (
        len(counts),
        sum(value == 1 for value in counts),
        sum(value > 1 for value in counts),
        sum(counts),
    )


def _consistency_sufficient(
    stats: _WindowStats, appearance_days: int, closed_supporting_days: int
) -> bool:
    return (
        stats.listening_day_count >= _MIN_LISTENING_DAYS
        and stats.closed_listening_day_count >= _MIN_CLOSED_LISTENING_DAYS
        and stats.total_duration_ms > 0
        and appearance_days >= _MIN_CONSISTENCY_APPEARANCE_DAYS
        and closed_supporting_days >= _MIN_CONSISTENCY_CLOSED_DAYS
    )


def _concentration_sufficient(stats: _WindowStats) -> bool:
    return (
        stats.listening_day_count >= _MIN_LISTENING_DAYS
        and stats.closed_listening_day_count >= _MIN_CLOSED_LISTENING_DAYS
        and stats.total_duration_ms > 0
        and stats.total_attributed_artist_duration_ms > 0
        and len(stats.artist_duration_ms) >= _MIN_CONCENTRATION_ARTISTS
    )


def _breadth_sufficient(stats: _WindowStats) -> bool:
    return (
        stats.listening_day_count >= _MIN_LISTENING_DAYS
        and stats.closed_listening_day_count >= _MIN_CLOSED_LISTENING_DAYS
        and stats.total_duration_ms > 0
    )


def _artist_identity(
    spotify_artist_id: str | None, artist_name: str
) -> ArtistIdentity | None:
    clean_id = spotify_artist_id.strip() if spotify_artist_id else ""
    if clean_id:
        return ("spotify", clean_id)
    clean_name = artist_name.strip()
    if not _usable_artist_name(clean_name):
        return None
    return ("legacy", clean_name.casefold())


def _usable_artist_name(value: str) -> bool:
    return bool(value) and value.casefold() != _UNKNOWN_ARTIST


def _share(value: int, total: int) -> float:
    return value / total if total > 0 else 0.0


def _ratio(value: int, denominator: int) -> float:
    return value / denominator if denominator > 0 else 0.0


def _dates(start_date: date, end_date: date) -> tuple[date, ...]:
    values: list[date] = []
    current = start_date
    while current < end_date:
        values.append(current)
        current += timedelta(days=1)
    return tuple(values)


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
