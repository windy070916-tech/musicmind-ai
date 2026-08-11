"""Deterministic comparison of adjacent long-term listening windows."""

from datetime import date, datetime, timezone

from music_ai.memory.models import ListeningMemory, timezone_for_name
from music_ai.temporal.long_term_evolution_models import (
    ArtistBreadthEvolutionEvidence,
    ArtistShareEvolutionCandidate,
    ConcentrationEvolutionEvidence,
    EvolutionWindowEvidence,
    LongTermEvolutionEvidence,
)
from music_ai.temporal.window_statistics import (
    ArtistWindowAggregate,
    ListeningWindowStatistics,
    calculate_listening_window_statistics,
)


_EVOLUTION_WINDOW_DAYS = 30
_MIN_LISTENING_DAYS = 10
_MIN_CLOSED_LISTENING_DAYS = 7


class LongTermEvolutionAnalytics:
    """Calculate locale-neutral evolution Evidence without product thresholds."""

    def analyze(
        self,
        memory: ListeningMemory,
        previous_start_date: date,
        previous_end_date: date,
        current_start_date: date,
        current_end_date: date,
        timezone_name: str | None = None,
        as_of: datetime | None = None,
    ) -> LongTermEvolutionEvidence:
        """Compare two explicit adjacent rolling 30-calendar-day windows."""
        resolved_timezone, resolved_as_of = _validate_inputs(
            memory,
            previous_start_date,
            previous_end_date,
            current_start_date,
            current_end_date,
            timezone_name,
            as_of,
        )
        previous = calculate_listening_window_statistics(
            memory.snapshots, previous_start_date, previous_end_date
        )
        current = calculate_listening_window_statistics(
            memory.snapshots, current_start_date, current_end_date
        )
        previous_window = _window_evidence(previous)
        current_window = _window_evidence(current)
        artist_share_calculable = (
            previous.total_attributed_artist_duration_ms > 0
            and current.total_attributed_artist_duration_ms > 0
        )
        return LongTermEvolutionEvidence(
            timezone_name=resolved_timezone,
            as_of=resolved_as_of,
            previous_window=previous_window,
            current_window=current_window,
            comparison_evidence_sufficient=(
                previous_window.structurally_sufficient
                and current_window.structurally_sufficient
            ),
            artist_share_calculable=artist_share_calculable,
            artist_share_candidates=_artist_share_candidates(previous, current),
            concentration=_concentration_evidence(previous, current),
            breadth=_breadth_evidence(previous, current),
        )


def _window_evidence(stats: ListeningWindowStatistics) -> EvolutionWindowEvidence:
    return EvolutionWindowEvidence(
        start_date=stats.start_date,
        end_date=stats.end_date,
        recorded_day_count=stats.recorded_day_count,
        listening_day_count=stats.listening_day_count,
        closed_day_count=stats.closed_day_count,
        closed_listening_day_count=stats.closed_listening_day_count,
        gap_dates=stats.gap_dates,
        contains_open_snapshot=stats.contains_open_snapshot,
        total_estimated_listening_duration_ms=(
            stats.total_estimated_listening_duration_ms
        ),
        total_attributed_artist_duration_ms=(
            stats.total_attributed_artist_duration_ms
        ),
        structurally_sufficient=(
            stats.listening_day_count >= _MIN_LISTENING_DAYS
            and stats.closed_listening_day_count >= _MIN_CLOSED_LISTENING_DAYS
        ),
    )


def _artist_share_candidates(
    previous: ListeningWindowStatistics,
    current: ListeningWindowStatistics,
) -> tuple[ArtistShareEvolutionCandidate, ...]:
    previous_by_identity = {artist.identity: artist for artist in previous.artists}
    current_by_identity = {artist.identity: artist for artist in current.artists}
    candidates: list[ArtistShareEvolutionCandidate] = []
    for identity in sorted(previous_by_identity.keys() | current_by_identity.keys()):
        previous_artist = previous_by_identity.get(identity)
        current_artist = current_by_identity.get(identity)
        source_artist = current_artist or previous_artist
        if source_artist is None:  # pragma: no cover - protected by the identity union
            continue
        previous_duration = (
            previous_artist.duration_ms if previous_artist is not None else 0
        )
        current_duration = current_artist.duration_ms if current_artist is not None else 0
        previous_share = _optional_ratio(
            previous_duration, previous.total_attributed_artist_duration_ms
        )
        current_share = _optional_ratio(
            current_duration, current.total_attributed_artist_duration_ms
        )
        signed_change = _optional_change(previous_share, current_share)
        candidates.append(
            ArtistShareEvolutionCandidate(
                identity=identity,
                spotify_artist_id=source_artist.spotify_artist_id,
                artist_name=source_artist.artist_name,
                previous_duration_ms=previous_duration,
                current_duration_ms=current_duration,
                previous_attributed_duration_ms=(
                    previous.total_attributed_artist_duration_ms
                ),
                current_attributed_duration_ms=(
                    current.total_attributed_artist_duration_ms
                ),
                previous_share=previous_share,
                current_share=current_share,
                signed_share_change=signed_change,
                absolute_share_change=(
                    abs(signed_change) if signed_change is not None else None
                ),
            )
        )
    return tuple(candidates)


def _concentration_evidence(
    previous: ListeningWindowStatistics,
    current: ListeningWindowStatistics,
) -> ConcentrationEvolutionEvidence:
    previous_top_five = _top_five_duration(previous.artists)
    current_top_five = _top_five_duration(current.artists)
    previous_share = _optional_ratio(
        previous_top_five, previous.total_attributed_artist_duration_ms
    )
    current_share = _optional_ratio(
        current_top_five, current.total_attributed_artist_duration_ms
    )
    signed_change = _optional_change(previous_share, current_share)
    return ConcentrationEvolutionEvidence(
        previous_top_five_duration_ms=previous_top_five,
        current_top_five_duration_ms=current_top_five,
        previous_attributed_duration_ms=(
            previous.total_attributed_artist_duration_ms
        ),
        current_attributed_duration_ms=current.total_attributed_artist_duration_ms,
        previous_share=previous_share,
        current_share=current_share,
        signed_share_change=signed_change,
        absolute_share_change=(
            abs(signed_change) if signed_change is not None else None
        ),
        is_calculable=previous_share is not None and current_share is not None,
    )


def _breadth_evidence(
    previous: ListeningWindowStatistics,
    current: ListeningWindowStatistics,
) -> ArtistBreadthEvolutionEvidence:
    previous_value = _optional_ratio(
        previous.artist_day_appearance_count, previous.listening_day_count
    )
    current_value = _optional_ratio(
        current.artist_day_appearance_count, current.listening_day_count
    )
    signed_change = _optional_change(previous_value, current_value)
    is_calculable = (
        previous_value is not None
        and current_value is not None
        and previous_value > 0
    )
    relative_change = (
        (current_value - previous_value) / previous_value
        if is_calculable
        else None
    )
    return ArtistBreadthEvolutionEvidence(
        previous_artist_day_count=previous.artist_day_appearance_count,
        current_artist_day_count=current.artist_day_appearance_count,
        previous_listening_day_count=previous.listening_day_count,
        current_listening_day_count=current.listening_day_count,
        previous_artists_per_listening_day=previous_value,
        current_artists_per_listening_day=current_value,
        signed_change=signed_change,
        absolute_change=abs(signed_change) if signed_change is not None else None,
        relative_change=relative_change,
        absolute_relative_change=(
            abs(relative_change) if relative_change is not None else None
        ),
        is_calculable=is_calculable,
    )


def _top_five_duration(artists: tuple[ArtistWindowAggregate, ...]) -> int:
    ranked = sorted(
        artists,
        key=lambda artist: (-artist.duration_ms, artist.identity),
    )
    return sum(artist.duration_ms for artist in ranked[:5])


def _optional_ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator > 0 else None


def _optional_change(previous: float | None, current: float | None) -> float | None:
    if previous is None or current is None:
        return None
    return current - previous


def _validate_inputs(
    memory: ListeningMemory,
    previous_start_date: date,
    previous_end_date: date,
    current_start_date: date,
    current_end_date: date,
    timezone_name: str | None,
    as_of: datetime | None,
) -> tuple[str, datetime]:
    if not isinstance(memory, ListeningMemory):
        raise TypeError("memory must be a ListeningMemory.")
    for field_name, value in (
        ("previous_start_date", previous_start_date),
        ("previous_end_date", previous_end_date),
        ("current_start_date", current_start_date),
        ("current_end_date", current_end_date),
    ):
        if not isinstance(value, date) or isinstance(value, datetime):
            raise ValueError(f"{field_name} must be a date.")
    if (previous_end_date - previous_start_date).days != _EVOLUTION_WINDOW_DAYS:
        raise ValueError("Previous evolution window must contain exactly 30 dates.")
    if (current_end_date - current_start_date).days != _EVOLUTION_WINDOW_DAYS:
        raise ValueError("Current evolution window must contain exactly 30 dates.")
    if previous_end_date != current_start_date:
        raise ValueError("Evolution windows must be adjacent and non-overlapping.")
    if (
        previous_start_date < memory.start_date
        or current_end_date > memory.end_date
    ):
        raise ValueError("Evolution windows must be contained in ListeningMemory.")

    if timezone_name is not None:
        timezone_for_name(timezone_name)
        if timezone_name != memory.timezone_name:
            raise ValueError("Analysis timezone must match ListeningMemory.")
    resolved_timezone = timezone_name or memory.timezone_name
    resolved_as_of = as_of or memory.as_of
    _require_aware(resolved_as_of)
    if as_of is not None and as_of.astimezone(timezone.utc) != memory.as_of.astimezone(
        timezone.utc
    ):
        raise ValueError("Analysis as_of must identify the ListeningMemory instant.")
    local_date = resolved_as_of.astimezone(
        timezone_for_name(resolved_timezone)
    ).date()
    if current_end_date != local_date:
        raise ValueError("Current evolution window must end at local date D.")
    return resolved_timezone, resolved_as_of


def _require_aware(value: datetime) -> None:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError("as_of must be timezone-aware.")
