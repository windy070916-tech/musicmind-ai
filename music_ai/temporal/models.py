"""Immutable evidence contracts produced by Temporal Analytics."""

from dataclasses import dataclass
from datetime import date, datetime

from music_ai.memory.models import timezone_for_name


@dataclass(frozen=True, slots=True)
class ArtistContinuityEvidence:
    """Deterministic evidence that one artist repeatedly led a bounded window."""

    spotify_artist_id: str | None
    artist_name: str
    window_start_date: date
    window_end_date: date
    recorded_day_count: int
    listening_day_count: int
    qualifying_day_count: int
    closed_qualifying_day_count: int
    qualifying_day_share: float
    gap_dates: tuple[date, ...]
    contains_open_day: bool
    evidence_sufficient: bool
    continuity_transition: bool

    def __post_init__(self) -> None:
        """Validate bounded counts and immutable gap ordering."""
        _validate_artist(self.spotify_artist_id, self.artist_name)
        _validate_window(self.window_start_date, self.window_end_date)
        _validate_counts(
            self.recorded_day_count,
            self.listening_day_count,
            self.qualifying_day_count,
            self.closed_qualifying_day_count,
        )
        if self.listening_day_count > self.recorded_day_count:
            raise ValueError("listening_day_count cannot exceed recorded_day_count.")
        if self.qualifying_day_count > self.listening_day_count:
            raise ValueError("qualifying_day_count cannot exceed listening_day_count.")
        if self.closed_qualifying_day_count > self.qualifying_day_count:
            raise ValueError(
                "closed_qualifying_day_count cannot exceed qualifying_day_count."
            )
        _validate_share(self.qualifying_day_share, "qualifying_day_share")
        object.__setattr__(self, "gap_dates", tuple(self.gap_dates))
        _validate_gap_dates(
            self.gap_dates, self.window_start_date, self.window_end_date
        )
        _require_bool(self.contains_open_day, "contains_open_day")
        _require_bool(self.evidence_sufficient, "evidence_sufficient")
        _require_bool(self.continuity_transition, "continuity_transition")


@dataclass(frozen=True, slots=True)
class ArtistEmergenceEvidence:
    """Deterministic artist-prominence comparison across two bounded windows."""

    spotify_artist_id: str | None
    artist_name: str
    recent_start_date: date
    recent_end_date: date
    comparison_start_date: date
    comparison_end_date: date
    recent_recorded_day_count: int
    comparison_recorded_day_count: int
    recent_listening_day_count: int
    comparison_listening_day_count: int
    recent_closed_listening_day_count: int
    comparison_closed_listening_day_count: int
    recent_artist_day_count: int
    comparison_artist_day_count: int
    recent_closed_artist_day_count: int
    comparison_closed_artist_day_count: int
    recent_artist_duration_ms: int
    comparison_artist_duration_ms: int
    recent_total_duration_ms: int
    comparison_total_duration_ms: int
    recent_duration_share: float | None
    comparison_duration_share: float | None
    duration_share_change: float | None
    recent_gap_dates: tuple[date, ...]
    comparison_gap_dates: tuple[date, ...]
    contains_open_day: bool
    evidence_sufficient: bool
    emergence_transition: bool

    def __post_init__(self) -> None:
        """Validate identities, windows, coverage, shares, and gap ordering."""
        _validate_artist(self.spotify_artist_id, self.artist_name)
        _validate_window(self.recent_start_date, self.recent_end_date)
        _validate_window(self.comparison_start_date, self.comparison_end_date)
        if self.comparison_end_date > self.recent_start_date:
            raise ValueError("Comparison and recent windows must not overlap.")
        _validate_counts(
            self.recent_recorded_day_count,
            self.comparison_recorded_day_count,
            self.recent_listening_day_count,
            self.comparison_listening_day_count,
            self.recent_closed_listening_day_count,
            self.comparison_closed_listening_day_count,
            self.recent_artist_day_count,
            self.comparison_artist_day_count,
            self.recent_closed_artist_day_count,
            self.comparison_closed_artist_day_count,
            self.recent_artist_duration_ms,
            self.comparison_artist_duration_ms,
            self.recent_total_duration_ms,
            self.comparison_total_duration_ms,
        )
        if self.recent_listening_day_count > self.recent_recorded_day_count:
            raise ValueError(
                "recent_listening_day_count cannot exceed recorded coverage."
            )
        if (
            self.comparison_listening_day_count
            > self.comparison_recorded_day_count
        ):
            raise ValueError(
                "comparison_listening_day_count cannot exceed recorded coverage."
            )
        if self.recent_artist_day_count > self.recent_listening_day_count:
            raise ValueError(
                "recent_artist_day_count cannot exceed recent listening days."
            )
        if (
            self.comparison_artist_day_count
            > self.comparison_listening_day_count
        ):
            raise ValueError(
                "comparison_artist_day_count cannot exceed comparison listening days."
            )
        if (
            self.recent_closed_listening_day_count
            > self.recent_listening_day_count
            or self.comparison_closed_listening_day_count
            > self.comparison_listening_day_count
        ):
            raise ValueError(
                "Closed listening-day counts cannot exceed listening-day counts."
            )
        if (
            self.recent_closed_artist_day_count
            > self.recent_artist_day_count
            or self.comparison_closed_artist_day_count
            > self.comparison_artist_day_count
        ):
            raise ValueError(
                "Closed artist-day counts cannot exceed artist-day counts."
            )
        _validate_optional_share(
            self.recent_duration_share, "recent_duration_share"
        )
        _validate_optional_share(
            self.comparison_duration_share, "comparison_duration_share"
        )
        if self.duration_share_change is not None and (
            isinstance(self.duration_share_change, bool)
            or not isinstance(self.duration_share_change, (int, float))
            or not -1.0 <= self.duration_share_change <= 1.0
        ):
            raise ValueError(
                "duration_share_change must be None or between -1 and 1."
            )
        if self.recent_total_duration_ms == 0:
            if self.recent_duration_share is not None:
                raise ValueError(
                    "recent_duration_share must be None without a duration denominator."
                )
        elif self.recent_duration_share is None:
            raise ValueError(
                "recent_duration_share is required with a duration denominator."
            )
        if self.comparison_total_duration_ms == 0:
            if self.comparison_duration_share is not None:
                raise ValueError(
                    "comparison_duration_share must be None without a "
                    "duration denominator."
                )
        elif self.comparison_duration_share is None:
            raise ValueError(
                "comparison_duration_share is required with a duration denominator."
            )
        if (
            self.recent_duration_share is None
            or self.comparison_duration_share is None
        ):
            if self.duration_share_change is not None:
                raise ValueError(
                    "duration_share_change requires both duration shares."
                )
        elif self.duration_share_change is None:
            raise ValueError(
                "duration_share_change is required when both shares exist."
            )
        object.__setattr__(self, "recent_gap_dates", tuple(self.recent_gap_dates))
        object.__setattr__(
            self, "comparison_gap_dates", tuple(self.comparison_gap_dates)
        )
        _validate_gap_dates(
            self.recent_gap_dates,
            self.recent_start_date,
            self.recent_end_date,
        )
        _validate_gap_dates(
            self.comparison_gap_dates,
            self.comparison_start_date,
            self.comparison_end_date,
        )
        _require_bool(self.contains_open_day, "contains_open_day")
        _require_bool(self.evidence_sufficient, "evidence_sufficient")
        _require_bool(self.emergence_transition, "emergence_transition")


@dataclass(frozen=True, slots=True)
class RecentListeningEvidence:
    """One completed deterministic analysis of explicit recent windows."""

    timezone_name: str
    as_of: datetime
    recent_start_date: date
    recent_end_date: date
    comparison_start_date: date
    comparison_end_date: date
    recent_gap_dates: tuple[date, ...]
    comparison_gap_dates: tuple[date, ...]
    contains_open_day: bool
    continuity: tuple[ArtistContinuityEvidence, ...]
    emergence: tuple[ArtistEmergenceEvidence, ...]

    def __post_init__(self) -> None:
        """Validate shared window context and immutable evidence collections."""
        timezone_for_name(self.timezone_name)
        _require_aware(self.as_of, "as_of")
        _validate_window(self.recent_start_date, self.recent_end_date)
        _validate_window(self.comparison_start_date, self.comparison_end_date)
        if self.comparison_end_date > self.recent_start_date:
            raise ValueError("Comparison and recent windows must not overlap.")
        object.__setattr__(self, "recent_gap_dates", tuple(self.recent_gap_dates))
        object.__setattr__(
            self, "comparison_gap_dates", tuple(self.comparison_gap_dates)
        )
        object.__setattr__(self, "continuity", tuple(self.continuity))
        object.__setattr__(self, "emergence", tuple(self.emergence))
        _validate_gap_dates(
            self.recent_gap_dates,
            self.recent_start_date,
            self.recent_end_date,
        )
        _validate_gap_dates(
            self.comparison_gap_dates,
            self.comparison_start_date,
            self.comparison_end_date,
        )
        _require_bool(self.contains_open_day, "contains_open_day")
        for evidence in self.continuity:
            if (
                evidence.window_start_date != self.recent_start_date
                or evidence.window_end_date != self.recent_end_date
                or evidence.gap_dates != self.recent_gap_dates
            ):
                raise ValueError(
                    "Continuity evidence must use the shared recent window."
                )
        for evidence in self.emergence:
            if (
                evidence.recent_start_date != self.recent_start_date
                or evidence.recent_end_date != self.recent_end_date
                or evidence.comparison_start_date
                != self.comparison_start_date
                or evidence.comparison_end_date != self.comparison_end_date
                or evidence.recent_gap_dates != self.recent_gap_dates
                or evidence.comparison_gap_dates
                != self.comparison_gap_dates
            ):
                raise ValueError(
                    "Emergence evidence must use the shared analysis windows."
                )


def _validate_artist(spotify_artist_id: str | None, artist_name: str) -> None:
    if spotify_artist_id is not None and (
        not isinstance(spotify_artist_id, str) or not spotify_artist_id
    ):
        raise ValueError("spotify_artist_id must be non-empty text or None.")
    if not isinstance(artist_name, str) or not artist_name:
        raise ValueError("artist_name must be non-empty text.")


def _validate_window(start_date: date, end_date: date) -> None:
    _require_date(start_date, "window start")
    _require_date(end_date, "window end")
    if start_date >= end_date:
        raise ValueError("Analysis windows must be non-empty [start, end) ranges.")


def _validate_counts(*values: int) -> None:
    if any(
        isinstance(value, bool) or not isinstance(value, int) or value < 0
        for value in values
    ):
        raise ValueError("Evidence counts must be non-negative integers.")


def _validate_share(value: float, field_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be numeric.")
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{field_name} must be between 0 and 1.")


def _validate_optional_share(value: float | None, field_name: str) -> None:
    if value is not None:
        _validate_share(value, field_name)


def _validate_gap_dates(
    gap_dates: tuple[date, ...], start_date: date, end_date: date
) -> None:
    previous: date | None = None
    for gap_date in gap_dates:
        _require_date(gap_date, "gap date")
        if not start_date <= gap_date < end_date:
            raise ValueError("Gap dates must fall inside their analysis window.")
        if previous is not None and gap_date <= previous:
            raise ValueError("Gap dates must be ordered without duplicates.")
        previous = gap_date


def _require_aware(value: datetime, field_name: str) -> None:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(f"{field_name} must be timezone-aware.")


def _require_date(value: date, field_name: str) -> None:
    if not isinstance(value, date) or isinstance(value, datetime):
        raise ValueError(f"{field_name} must be a date.")


def _require_bool(value: bool, field_name: str) -> None:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be a boolean.")
