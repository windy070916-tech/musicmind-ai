"""Deterministic longitudinal calculations over bounded Listening Memory."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from music_ai.memory.models import (
    DailyMemorySnapshot,
    ListeningMemory,
    timezone_for_name,
)
from music_ai.temporal.models import (
    ArtistContinuityEvidence,
    ArtistEmergenceEvidence,
    RecentListeningEvidence,
)


_MIN_CONTINUITY_LISTENING_DAYS = 3
_MIN_CONTINUITY_QUALIFYING_DAYS = 3
_MIN_COMPARISON_LISTENING_DAYS = 2
_MIN_RECENT_LISTENING_DAYS = 2
_MIN_RECENT_ARTIST_DAYS = 2
_UNKNOWN_ARTIST = "unknown artist"

_ArtistKey = tuple[str, str]


@dataclass(frozen=True, slots=True)
class _WindowStats:
    """Internal aggregate for one explicit window."""

    snapshots: tuple[DailyMemorySnapshot, ...]
    gap_dates: tuple[date, ...]
    recorded_day_count: int
    listening_day_count: int
    closed_listening_day_count: int
    total_duration_ms: int
    artist_duration_ms: dict[_ArtistKey, int]
    artist_day_count: dict[_ArtistKey, int]
    closed_artist_day_count: dict[_ArtistKey, int]
    top_artist_day_count: dict[_ArtistKey, int]
    closed_top_artist_day_count: dict[_ArtistKey, int]
    artist_names: dict[_ArtistKey, tuple[str, ...]]
    contains_open_day: bool


class TemporalListeningAnalytics:
    """Calculate recent evidence without interpreting or persisting it.

    The caller always supplies both half-open local-date windows. The class owns
    no default period and performs no Memory lifecycle operations.
    """

    def analyze(
        self,
        memory: ListeningMemory,
        *,
        recent_start_date: date,
        recent_end_date: date,
        comparison_start_date: date,
        comparison_end_date: date,
        timezone_name: str | None = None,
        as_of: datetime | None = None,
    ) -> RecentListeningEvidence:
        """Return immutable evidence for two caller-bounded windows."""
        _validate_inputs(
            memory,
            recent_start_date=recent_start_date,
            recent_end_date=recent_end_date,
            comparison_start_date=comparison_start_date,
            comparison_end_date=comparison_end_date,
            timezone_name=timezone_name,
            as_of=as_of,
        )
        evidence_timezone = timezone_name or memory.timezone_name
        evidence_as_of = as_of or memory.as_of

        comparison = _window_stats(
            memory.snapshots, comparison_start_date, comparison_end_date
        )
        recent = _window_stats(
            memory.snapshots, recent_start_date, recent_end_date
        )
        prior_recent = _window_stats(
            memory.snapshots,
            recent_start_date,
            recent_end_date - timedelta(days=1),
            allow_empty=True,
        )

        continuity = _continuity_evidence(
            recent,
            prior_recent,
            recent_start_date,
            recent_end_date,
        )
        emergence = _emergence_evidence(
            recent,
            comparison,
            recent_start_date,
            recent_end_date,
            comparison_start_date,
            comparison_end_date,
        )
        return RecentListeningEvidence(
            timezone_name=evidence_timezone,
            as_of=evidence_as_of,
            recent_start_date=recent_start_date,
            recent_end_date=recent_end_date,
            comparison_start_date=comparison_start_date,
            comparison_end_date=comparison_end_date,
            recent_gap_dates=recent.gap_dates,
            comparison_gap_dates=comparison.gap_dates,
            contains_open_day=(
                recent.contains_open_day or comparison.contains_open_day
            ),
            continuity=continuity,
            emergence=emergence,
        )


# A concise alias keeps the domain name available without introducing another
# implementation or abstraction.
TemporalAnalytics = TemporalListeningAnalytics


def _window_stats(
    snapshots: tuple[DailyMemorySnapshot, ...],
    start_date: date,
    end_date: date,
    *,
    allow_empty: bool = False,
) -> _WindowStats:
    """Aggregate stored evidence inside one exact half-open window."""
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

    artist_duration_ms: defaultdict[_ArtistKey, int] = defaultdict(int)
    artist_day_count: defaultdict[_ArtistKey, int] = defaultdict(int)
    closed_artist_day_count: defaultdict[_ArtistKey, int] = defaultdict(int)
    top_artist_day_count: defaultdict[_ArtistKey, int] = defaultdict(int)
    closed_top_artist_day_count: defaultdict[_ArtistKey, int] = defaultdict(int)
    names: defaultdict[_ArtistKey, set[str]] = defaultdict(set)
    listening_day_count = 0
    closed_listening_day_count = 0
    total_duration_ms = 0

    for snapshot in selected:
        profile = snapshot.profile
        day_duration = max(0, profile.total_estimated_listening_duration_ms)
        total_duration_ms += day_duration
        usable_day = day_duration > 0
        if usable_day:
            listening_day_count += 1
            if snapshot.is_closed:
                closed_listening_day_count += 1

        present_today: set[_ArtistKey] = set()
        for artist in profile.top_artists:
            identity = _artist_identity(
                artist.spotify_artist_id,
                artist.name,
            )
            if identity is None:
                continue
            display_name = artist.name.strip()
            if _usable_artist_name(display_name):
                names[identity].add(display_name)
            artist_duration_ms[identity] += max(
                0, artist.estimated_listening_duration_ms
            )
            present_today.add(identity)

        for identity in present_today:
            artist_day_count[identity] += 1
            if snapshot.is_closed:
                closed_artist_day_count[identity] += 1

        if usable_day and profile.top_artists:
            top_artist = profile.top_artists[0]
            top_identity = _artist_identity(
                top_artist.spotify_artist_id,
                top_artist.name,
            )
            if top_identity is not None:
                top_name = top_artist.name.strip()
                if _usable_artist_name(top_name):
                    names[top_identity].add(top_name)
                top_artist_day_count[top_identity] += 1
                if snapshot.is_closed:
                    closed_top_artist_day_count[top_identity] += 1

    return _WindowStats(
        snapshots=selected,
        gap_dates=gap_dates,
        recorded_day_count=len(selected),
        listening_day_count=listening_day_count,
        closed_listening_day_count=closed_listening_day_count,
        total_duration_ms=total_duration_ms,
        artist_duration_ms=dict(artist_duration_ms),
        artist_day_count=dict(artist_day_count),
        closed_artist_day_count=dict(closed_artist_day_count),
        top_artist_day_count=dict(top_artist_day_count),
        closed_top_artist_day_count=dict(closed_top_artist_day_count),
        artist_names={
            identity: tuple(sorted(values))
            for identity, values in names.items()
        },
        contains_open_day=any(not snapshot.is_closed for snapshot in selected),
    )


def _continuity_evidence(
    recent: _WindowStats,
    prior_recent: _WindowStats,
    start_date: date,
    end_date: date,
) -> tuple[ArtistContinuityEvidence, ...]:
    """Build evidence records for artists that led at least one usable day."""
    records: list[ArtistContinuityEvidence] = []
    for identity in sorted(recent.top_artist_day_count):
        if not _has_display_name(identity, recent):
            continue
        qualifying_days = recent.top_artist_day_count[identity]
        prior_qualifying_days = prior_recent.top_artist_day_count.get(
            identity, 0
        )
        evidence_sufficient = _continuity_is_sufficient(
            recent.listening_day_count,
            qualifying_days,
            recent.closed_top_artist_day_count.get(identity, 0),
        )
        prior_sufficient = _continuity_is_sufficient(
            prior_recent.listening_day_count,
            prior_qualifying_days,
            prior_recent.closed_top_artist_day_count.get(identity, 0),
        )
        records.append(
            ArtistContinuityEvidence(
                spotify_artist_id=_spotify_id(identity),
                artist_name=_display_name(identity, recent),
                window_start_date=start_date,
                window_end_date=end_date,
                recorded_day_count=recent.recorded_day_count,
                listening_day_count=recent.listening_day_count,
                qualifying_day_count=qualifying_days,
                closed_qualifying_day_count=(
                    recent.closed_top_artist_day_count.get(identity, 0)
                ),
                qualifying_day_share=(
                    qualifying_days / recent.listening_day_count
                    if recent.listening_day_count
                    else 0.0
                ),
                gap_dates=recent.gap_dates,
                contains_open_day=recent.contains_open_day,
                evidence_sufficient=evidence_sufficient,
                continuity_transition=(
                    evidence_sufficient and not prior_sufficient
                ),
            )
        )
    return tuple(records)


def _emergence_evidence(
    recent: _WindowStats,
    comparison: _WindowStats,
    recent_start_date: date,
    recent_end_date: date,
    comparison_start_date: date,
    comparison_end_date: date,
) -> tuple[ArtistEmergenceEvidence, ...]:
    """Build aggregate-duration prominence comparisons for recent artists."""
    records: list[ArtistEmergenceEvidence] = []
    for identity in sorted(recent.artist_duration_ms):
        if not _has_display_name(identity, recent, comparison):
            continue
        recent_artist_duration = recent.artist_duration_ms[identity]
        comparison_artist_duration = comparison.artist_duration_ms.get(
            identity, 0
        )
        recent_share = _duration_share(
            recent_artist_duration, recent.total_duration_ms
        )
        comparison_share = _duration_share(
            comparison_artist_duration, comparison.total_duration_ms
        )
        change = (
            recent_share - comparison_share
            if recent_share is not None and comparison_share is not None
            else None
        )
        evidence_sufficient = (
            recent.listening_day_count >= _MIN_RECENT_LISTENING_DAYS
            and comparison.listening_day_count
            >= _MIN_COMPARISON_LISTENING_DAYS
            and recent.artist_day_count.get(identity, 0)
            >= _MIN_RECENT_ARTIST_DAYS
            and recent.closed_artist_day_count.get(identity, 0) >= 1
            and comparison.closed_listening_day_count >= 1
            and recent.total_duration_ms > 0
            and comparison.total_duration_ms > 0
        )
        records.append(
            ArtistEmergenceEvidence(
                spotify_artist_id=_spotify_id(identity),
                artist_name=_display_name(identity, recent, comparison),
                recent_start_date=recent_start_date,
                recent_end_date=recent_end_date,
                comparison_start_date=comparison_start_date,
                comparison_end_date=comparison_end_date,
                recent_recorded_day_count=recent.recorded_day_count,
                comparison_recorded_day_count=comparison.recorded_day_count,
                recent_listening_day_count=recent.listening_day_count,
                comparison_listening_day_count=comparison.listening_day_count,
                recent_closed_listening_day_count=(
                    recent.closed_listening_day_count
                ),
                comparison_closed_listening_day_count=(
                    comparison.closed_listening_day_count
                ),
                recent_artist_day_count=recent.artist_day_count.get(identity, 0),
                comparison_artist_day_count=comparison.artist_day_count.get(
                    identity, 0
                ),
                recent_closed_artist_day_count=(
                    recent.closed_artist_day_count.get(identity, 0)
                ),
                comparison_closed_artist_day_count=(
                    comparison.closed_artist_day_count.get(identity, 0)
                ),
                recent_artist_duration_ms=recent_artist_duration,
                comparison_artist_duration_ms=comparison_artist_duration,
                recent_total_duration_ms=recent.total_duration_ms,
                comparison_total_duration_ms=comparison.total_duration_ms,
                recent_duration_share=recent_share,
                comparison_duration_share=comparison_share,
                duration_share_change=change,
                recent_gap_dates=recent.gap_dates,
                comparison_gap_dates=comparison.gap_dates,
                contains_open_day=(
                    recent.contains_open_day
                    or comparison.contains_open_day
                ),
                evidence_sufficient=evidence_sufficient,
                emergence_transition=(
                    evidence_sufficient
                    and change is not None
                    and change > 0
                ),
            )
        )
    return tuple(records)


def _continuity_is_sufficient(
    listening_day_count: int,
    qualifying_day_count: int,
    closed_qualifying_day_count: int,
) -> bool:
    """Return structural sufficiency without applying product wording."""
    return (
        listening_day_count >= _MIN_CONTINUITY_LISTENING_DAYS
        and qualifying_day_count >= _MIN_CONTINUITY_QUALIFYING_DAYS
        and closed_qualifying_day_count >= 1
    )


def _duration_share(duration_ms: int, total_duration_ms: int) -> float | None:
    if total_duration_ms <= 0:
        return None
    return duration_ms / total_duration_ms


def _artist_identity(
    spotify_artist_id: str | None, artist_name: str
) -> _ArtistKey | None:
    """Return an ID-first identity without bridging legacy and Spotify data."""
    clean_id = spotify_artist_id.strip() if spotify_artist_id else ""
    if clean_id:
        return ("spotify", clean_id)
    clean_name = artist_name.strip()
    if not _usable_artist_name(clean_name):
        return None
    return ("legacy", clean_name.casefold())


def _spotify_id(identity: _ArtistKey) -> str | None:
    return identity[1] if identity[0] == "spotify" else None


def _display_name(
    identity: _ArtistKey,
    primary: _WindowStats,
    fallback: _WindowStats | None = None,
) -> str:
    """Select a stable display value independent of snapshot encounter order."""
    values = primary.artist_names.get(identity, ())
    if not values and fallback is not None:
        values = fallback.artist_names.get(identity, ())
    if values:
        return min(values)
    raise ValueError("Longitudinal artist evidence requires a usable display name.")


def _has_display_name(
    identity: _ArtistKey,
    primary: _WindowStats,
    fallback: _WindowStats | None = None,
) -> bool:
    return bool(
        primary.artist_names.get(identity)
        or (
            fallback is not None
            and fallback.artist_names.get(identity)
        )
    )


def _usable_artist_name(value: str) -> bool:
    return bool(value) and value.casefold() != _UNKNOWN_ARTIST


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
    recent_start_date: date,
    recent_end_date: date,
    comparison_start_date: date,
    comparison_end_date: date,
    timezone_name: str | None,
    as_of: datetime | None,
) -> None:
    if not isinstance(memory, ListeningMemory):
        raise TypeError("memory must be a ListeningMemory.")
    for field_name, value in (
        ("recent_start_date", recent_start_date),
        ("recent_end_date", recent_end_date),
        ("comparison_start_date", comparison_start_date),
        ("comparison_end_date", comparison_end_date),
    ):
        if not isinstance(value, date) or isinstance(value, datetime):
            raise ValueError(f"{field_name} must be a date.")
    if recent_start_date >= recent_end_date:
        raise ValueError("The recent window must be non-empty.")
    if comparison_start_date >= comparison_end_date:
        raise ValueError("The comparison window must be non-empty.")
    if comparison_end_date > recent_start_date:
        raise ValueError("Comparison and recent windows must not overlap.")
    if (
        comparison_start_date < memory.start_date
        or comparison_end_date > memory.end_date
        or recent_start_date < memory.start_date
        or recent_end_date > memory.end_date
    ):
        raise ValueError("Analysis windows must be contained in ListeningMemory.")
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
