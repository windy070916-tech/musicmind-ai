"""Immutable evidence contracts for long-term listening analytics."""

from dataclasses import dataclass
from datetime import date, datetime

from music_ai.memory.models import timezone_for_name


ArtistIdentity = tuple[str, str]


@dataclass(frozen=True, slots=True)
class ArtistConsistencyEvidence:
    """Deterministic evidence for one artist's appearances across a window."""

    identity: ArtistIdentity
    spotify_artist_id: str | None
    artist_name: str
    appearance_day_count: int
    listening_day_count: int
    closed_supporting_day_count: int
    aggregate_duration_ms: int
    appearance_share: float
    duration_share: float
    evidence_sufficient: bool
    prefix_appearance_day_count: int
    prefix_listening_day_count: int
    prefix_closed_supporting_day_count: int
    prefix_aggregate_duration_ms: int
    prefix_appearance_share: float
    prefix_duration_share: float
    prefix_evidence_sufficient: bool
    structural_transition: bool

    def __post_init__(self) -> None:
        _validate_identity(self.identity, self.spotify_artist_id, self.artist_name)
        _validate_counts(
            self.appearance_day_count,
            self.listening_day_count,
            self.closed_supporting_day_count,
            self.aggregate_duration_ms,
            self.prefix_appearance_day_count,
            self.prefix_listening_day_count,
            self.prefix_closed_supporting_day_count,
            self.prefix_aggregate_duration_ms,
        )
        if self.appearance_day_count > self.listening_day_count:
            raise ValueError("appearance_day_count cannot exceed listening_day_count.")
        if self.closed_supporting_day_count > self.appearance_day_count:
            raise ValueError(
                "closed_supporting_day_count cannot exceed appearance_day_count."
            )
        if self.prefix_appearance_day_count > self.prefix_listening_day_count:
            raise ValueError(
                "prefix_appearance_day_count cannot exceed prefix listening days."
            )
        if self.prefix_closed_supporting_day_count > self.prefix_appearance_day_count:
            raise ValueError(
                "prefix closed support cannot exceed prefix appearance days."
            )
        _validate_shares(
            self.appearance_share,
            self.duration_share,
            self.prefix_appearance_share,
            self.prefix_duration_share,
        )
        _validate_bools(
            self.evidence_sufficient,
            self.prefix_evidence_sufficient,
            self.structural_transition,
        )


@dataclass(frozen=True, slots=True)
class ListeningConcentrationEvidence:
    """Calculated artist-duration concentration without a product label."""

    distinct_artist_count: int
    top_one_duration_share: float
    top_five_duration_share: float
    total_attributed_artist_duration_ms: int
    total_estimated_listening_duration_ms: int
    listening_day_count: int
    closed_listening_day_count: int
    evidence_sufficient: bool
    prefix_distinct_artist_count: int
    prefix_top_one_duration_share: float
    prefix_top_five_duration_share: float
    prefix_total_attributed_artist_duration_ms: int
    prefix_total_estimated_listening_duration_ms: int
    prefix_listening_day_count: int
    prefix_closed_listening_day_count: int
    prefix_evidence_sufficient: bool
    structural_transition: bool

    def __post_init__(self) -> None:
        _validate_counts(
            self.distinct_artist_count,
            self.total_attributed_artist_duration_ms,
            self.total_estimated_listening_duration_ms,
            self.listening_day_count,
            self.closed_listening_day_count,
            self.prefix_distinct_artist_count,
            self.prefix_total_attributed_artist_duration_ms,
            self.prefix_total_estimated_listening_duration_ms,
            self.prefix_listening_day_count,
            self.prefix_closed_listening_day_count,
        )
        if self.closed_listening_day_count > self.listening_day_count:
            raise ValueError("Closed listening days cannot exceed listening days.")
        if self.prefix_closed_listening_day_count > self.prefix_listening_day_count:
            raise ValueError(
                "Prefix closed listening days cannot exceed prefix listening days."
            )
        _validate_shares(
            self.top_one_duration_share,
            self.top_five_duration_share,
            self.prefix_top_one_duration_share,
            self.prefix_top_five_duration_share,
        )
        if self.top_one_duration_share > self.top_five_duration_share:
            raise ValueError("Top-one share cannot exceed top-five share.")
        if self.prefix_top_one_duration_share > self.prefix_top_five_duration_share:
            raise ValueError("Prefix top-one share cannot exceed prefix top-five share.")
        _validate_bools(
            self.evidence_sufficient,
            self.prefix_evidence_sufficient,
            self.structural_transition,
        )


@dataclass(frozen=True, slots=True)
class ArtistBreadthEvidence:
    """Calculated artist breadth across recorded listening days."""

    unique_artist_count: int
    single_day_artist_count: int
    repeated_artist_count: int
    artist_day_appearance_count: int
    artists_per_listening_day: float
    listening_day_count: int
    closed_listening_day_count: int
    evidence_sufficient: bool
    prefix_unique_artist_count: int
    prefix_single_day_artist_count: int
    prefix_repeated_artist_count: int
    prefix_artist_day_appearance_count: int
    prefix_artists_per_listening_day: float
    prefix_listening_day_count: int
    prefix_closed_listening_day_count: int
    prefix_evidence_sufficient: bool
    structural_transition: bool

    def __post_init__(self) -> None:
        _validate_counts(
            self.unique_artist_count,
            self.single_day_artist_count,
            self.repeated_artist_count,
            self.artist_day_appearance_count,
            self.listening_day_count,
            self.closed_listening_day_count,
            self.prefix_unique_artist_count,
            self.prefix_single_day_artist_count,
            self.prefix_repeated_artist_count,
            self.prefix_artist_day_appearance_count,
            self.prefix_listening_day_count,
            self.prefix_closed_listening_day_count,
        )
        if self.single_day_artist_count + self.repeated_artist_count != self.unique_artist_count:
            raise ValueError("Breadth artist counts must partition unique artists.")
        if (
            self.prefix_single_day_artist_count + self.prefix_repeated_artist_count
            != self.prefix_unique_artist_count
        ):
            raise ValueError("Prefix breadth counts must partition unique artists.")
        if self.closed_listening_day_count > self.listening_day_count:
            raise ValueError("Closed listening days cannot exceed listening days.")
        if self.prefix_closed_listening_day_count > self.prefix_listening_day_count:
            raise ValueError(
                "Prefix closed listening days cannot exceed prefix listening days."
            )
        _validate_non_negative_number(
            self.artists_per_listening_day, "artists_per_listening_day"
        )
        _validate_non_negative_number(
            self.prefix_artists_per_listening_day,
            "prefix_artists_per_listening_day",
        )
        _validate_bools(
            self.evidence_sufficient,
            self.prefix_evidence_sufficient,
            self.structural_transition,
        )


@dataclass(frozen=True, slots=True)
class LongTermListeningEvidence:
    """One completed long-term analysis of an explicit Memory window."""

    timezone_name: str
    as_of: datetime
    start_date: date
    end_date: date
    recorded_day_count: int
    listening_day_count: int
    closed_day_count: int
    gap_dates: tuple[date, ...]
    contains_open_day: bool
    total_estimated_listening_duration_ms: int
    artist_consistency: tuple[ArtistConsistencyEvidence, ...]
    listening_concentration: ListeningConcentrationEvidence
    artist_breadth: ArtistBreadthEvidence

    def __post_init__(self) -> None:
        timezone_for_name(self.timezone_name)
        _require_aware(self.as_of, "as_of")
        _validate_window(self.start_date, self.end_date)
        _validate_counts(
            self.recorded_day_count,
            self.listening_day_count,
            self.closed_day_count,
            self.total_estimated_listening_duration_ms,
        )
        if self.listening_day_count > self.recorded_day_count:
            raise ValueError("listening_day_count cannot exceed recorded_day_count.")
        if self.closed_day_count > self.recorded_day_count:
            raise ValueError("closed_day_count cannot exceed recorded_day_count.")
        object.__setattr__(self, "gap_dates", tuple(self.gap_dates))
        object.__setattr__(self, "artist_consistency", tuple(self.artist_consistency))
        _validate_gap_dates(self.gap_dates, self.start_date, self.end_date)
        _validate_bools(self.contains_open_day)
        window_day_count = (self.end_date - self.start_date).days
        if self.recorded_day_count + len(self.gap_dates) != window_day_count:
            raise ValueError(
                "Recorded days and gap dates must cover the complete analysis window."
            )
        expected_contains_open_day = self.closed_day_count < self.recorded_day_count
        if self.contains_open_day != expected_contains_open_day:
            raise ValueError(
                "contains_open_day must match recorded and closed day counts."
            )
        if not isinstance(self.listening_concentration, ListeningConcentrationEvidence):
            raise ValueError(
                "listening_concentration must be ListeningConcentrationEvidence."
            )
        if not isinstance(self.artist_breadth, ArtistBreadthEvidence):
            raise ValueError("artist_breadth must be ArtistBreadthEvidence.")
        if any(
            not isinstance(item, ArtistConsistencyEvidence)
            for item in self.artist_consistency
        ):
            raise ValueError(
                "artist_consistency must contain ArtistConsistencyEvidence values."
            )
        if any(
            item.listening_day_count != self.listening_day_count
            for item in self.artist_consistency
        ):
            raise ValueError(
                "Artist consistency must use the shared listening-day count."
            )
        if (
            self.listening_concentration.listening_day_count
            != self.listening_day_count
            or self.artist_breadth.listening_day_count
            != self.listening_day_count
        ):
            raise ValueError(
                "Long-term concept evidence must use the shared listening-day count."
            )
        if (
            self.listening_concentration.closed_listening_day_count
            != self.artist_breadth.closed_listening_day_count
        ):
            raise ValueError(
                "Concentration and breadth must use the same closed listening-day count."
            )
        if (
            self.listening_concentration.closed_listening_day_count
            > self.closed_day_count
        ):
            raise ValueError(
                "Closed listening-day count cannot exceed the shared closed-day count."
            )
        if (
            self.listening_concentration.total_estimated_listening_duration_ms
            != self.total_estimated_listening_duration_ms
        ):
            raise ValueError(
                "Concentration evidence must use the shared listening duration."
            )


def _validate_identity(
    identity: ArtistIdentity, spotify_artist_id: str | None, artist_name: str
) -> None:
    if (
        not isinstance(identity, tuple)
        or len(identity) != 2
        or identity[0] not in {"spotify", "legacy"}
        or not isinstance(identity[1], str)
        or not identity[1]
    ):
        raise ValueError("identity must be a usable Spotify or legacy artist key.")
    if not isinstance(artist_name, str) or not artist_name.strip():
        raise ValueError("artist_name must be non-empty text.")
    if identity[0] == "spotify":
        if spotify_artist_id != identity[1]:
            raise ValueError("Spotify identity must match spotify_artist_id.")
    elif spotify_artist_id is not None:
        raise ValueError("Legacy identity cannot include spotify_artist_id.")


def _validate_window(start_date: date, end_date: date) -> None:
    _require_date(start_date, "start_date")
    _require_date(end_date, "end_date")
    if start_date >= end_date:
        raise ValueError("Analysis windows must be non-empty [start, end) ranges.")


def _validate_counts(*values: int) -> None:
    if any(
        isinstance(value, bool) or not isinstance(value, int) or value < 0
        for value in values
    ):
        raise ValueError("Evidence counts must be non-negative integers.")


def _validate_shares(*values: float) -> None:
    for value in values:
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not 0.0 <= value <= 1.0
        ):
            raise ValueError("Evidence shares must be between 0 and 1.")


def _validate_non_negative_number(value: float, field_name: str) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or value < 0
    ):
        raise ValueError(f"{field_name} must be a non-negative number.")


def _validate_bools(*values: bool) -> None:
    if any(not isinstance(value, bool) for value in values):
        raise ValueError("Evidence state values must be boolean.")


def _validate_gap_dates(
    gap_dates: tuple[date, ...], start_date: date, end_date: date
) -> None:
    previous: date | None = None
    for gap_date in gap_dates:
        _require_date(gap_date, "gap date")
        if not start_date <= gap_date < end_date:
            raise ValueError("Gap dates must fall inside the analysis window.")
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
