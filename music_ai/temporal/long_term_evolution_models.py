"""Immutable Evidence contracts for adjacent-window listening evolution."""

from dataclasses import dataclass
from datetime import date, datetime
from math import isclose, isfinite

from music_ai.memory.models import timezone_for_name
from music_ai.temporal.long_term_models import ArtistIdentity


_MIN_LISTENING_DAYS = 10
_MIN_CLOSED_LISTENING_DAYS = 7
_UNKNOWN_ARTIST = "unknown artist"


@dataclass(frozen=True, slots=True)
class EvolutionWindowEvidence:
    """Locale-neutral evidence for one evolution comparison window."""

    start_date: date
    end_date: date
    recorded_day_count: int
    listening_day_count: int
    closed_day_count: int
    closed_listening_day_count: int
    gap_dates: tuple[date, ...]
    contains_open_snapshot: bool
    total_estimated_listening_duration_ms: int
    total_attributed_artist_duration_ms: int
    structurally_sufficient: bool

    def __post_init__(self) -> None:
        _validate_window(self.start_date, self.end_date)
        _validate_counts(
            self.recorded_day_count,
            self.listening_day_count,
            self.closed_day_count,
            self.closed_listening_day_count,
            self.total_estimated_listening_duration_ms,
            self.total_attributed_artist_duration_ms,
        )
        object.__setattr__(self, "gap_dates", tuple(self.gap_dates))
        _validate_gap_dates(self.gap_dates, self.start_date, self.end_date)
        _require_bool(self.contains_open_snapshot, "contains_open_snapshot")
        _require_bool(self.structurally_sufficient, "structurally_sufficient")
        if self.recorded_day_count + len(self.gap_dates) != (
            self.end_date - self.start_date
        ).days:
            raise ValueError(
                "Recorded days and gap dates must cover the complete window."
            )
        if self.listening_day_count > self.recorded_day_count:
            raise ValueError("listening_day_count cannot exceed recorded_day_count.")
        if self.closed_day_count > self.recorded_day_count:
            raise ValueError("closed_day_count cannot exceed recorded_day_count.")
        if self.closed_listening_day_count > self.listening_day_count:
            raise ValueError(
                "closed_listening_day_count cannot exceed listening_day_count."
            )
        if self.closed_listening_day_count > self.closed_day_count:
            raise ValueError(
                "closed_listening_day_count cannot exceed closed_day_count."
            )
        if self.contains_open_snapshot != (
            self.closed_day_count < self.recorded_day_count
        ):
            raise ValueError(
                "contains_open_snapshot must match recorded and closed day counts."
            )
        if (
            self.total_attributed_artist_duration_ms
            > self.total_estimated_listening_duration_ms
        ):
            raise ValueError(
                "Attributed artist duration cannot exceed total listening duration."
            )
        expected_sufficiency = (
            self.listening_day_count >= _MIN_LISTENING_DAYS
            and self.closed_listening_day_count >= _MIN_CLOSED_LISTENING_DAYS
        )
        if self.structurally_sufficient != expected_sufficiency:
            raise ValueError(
                "structurally_sufficient must match the 10/7 day-count rule."
            )


@dataclass(frozen=True, slots=True)
class ArtistShareEvolutionCandidate:
    """Raw cross-window share evidence for one stable artist identity."""

    identity: ArtistIdentity
    spotify_artist_id: str | None
    artist_name: str
    previous_duration_ms: int
    current_duration_ms: int
    previous_attributed_duration_ms: int
    current_attributed_duration_ms: int
    previous_share: float | None
    current_share: float | None
    signed_share_change: float | None
    absolute_share_change: float | None

    def __post_init__(self) -> None:
        _validate_identity(self.identity, self.spotify_artist_id, self.artist_name)
        _validate_counts(
            self.previous_duration_ms,
            self.current_duration_ms,
            self.previous_attributed_duration_ms,
            self.current_attributed_duration_ms,
        )
        if self.previous_duration_ms > self.previous_attributed_duration_ms:
            raise ValueError(
                "previous_duration_ms cannot exceed its attributed duration."
            )
        if self.current_duration_ms > self.current_attributed_duration_ms:
            raise ValueError(
                "current_duration_ms cannot exceed its attributed duration."
            )
        _validate_optional_ratio_from_counts(
            self.previous_share,
            self.previous_duration_ms,
            self.previous_attributed_duration_ms,
            "previous_share",
        )
        _validate_optional_ratio_from_counts(
            self.current_share,
            self.current_duration_ms,
            self.current_attributed_duration_ms,
            "current_share",
        )
        _validate_change_fields(
            self.previous_share,
            self.current_share,
            self.signed_share_change,
            self.absolute_share_change,
            "share",
        )


@dataclass(frozen=True, slots=True)
class ConcentrationEvolutionEvidence:
    """Top-five attributable-duration concentration comparison Evidence."""

    previous_top_five_duration_ms: int
    current_top_five_duration_ms: int
    previous_attributed_duration_ms: int
    current_attributed_duration_ms: int
    previous_share: float | None
    current_share: float | None
    signed_share_change: float | None
    absolute_share_change: float | None
    is_calculable: bool

    def __post_init__(self) -> None:
        _validate_counts(
            self.previous_top_five_duration_ms,
            self.current_top_five_duration_ms,
            self.previous_attributed_duration_ms,
            self.current_attributed_duration_ms,
        )
        if self.previous_top_five_duration_ms > self.previous_attributed_duration_ms:
            raise ValueError(
                "Previous top-five duration cannot exceed attributed duration."
            )
        if self.current_top_five_duration_ms > self.current_attributed_duration_ms:
            raise ValueError(
                "Current top-five duration cannot exceed attributed duration."
            )
        _validate_optional_ratio_from_counts(
            self.previous_share,
            self.previous_top_five_duration_ms,
            self.previous_attributed_duration_ms,
            "previous_share",
        )
        _validate_optional_ratio_from_counts(
            self.current_share,
            self.current_top_five_duration_ms,
            self.current_attributed_duration_ms,
            "current_share",
        )
        _validate_change_fields(
            self.previous_share,
            self.current_share,
            self.signed_share_change,
            self.absolute_share_change,
            "share",
        )
        _require_bool(self.is_calculable, "is_calculable")
        expected = self.previous_share is not None and self.current_share is not None
        if self.is_calculable != expected:
            raise ValueError(
                "is_calculable must match concentration denominator availability."
            )


@dataclass(frozen=True, slots=True)
class ArtistBreadthEvolutionEvidence:
    """Artists-per-listening-day comparison Evidence."""

    previous_artist_day_count: int
    current_artist_day_count: int
    previous_listening_day_count: int
    current_listening_day_count: int
    previous_artists_per_listening_day: float | None
    current_artists_per_listening_day: float | None
    signed_change: float | None
    absolute_change: float | None
    relative_change: float | None
    absolute_relative_change: float | None
    is_calculable: bool

    def __post_init__(self) -> None:
        _validate_counts(
            self.previous_artist_day_count,
            self.current_artist_day_count,
            self.previous_listening_day_count,
            self.current_listening_day_count,
        )
        _validate_optional_non_negative_ratio_from_counts(
            self.previous_artists_per_listening_day,
            self.previous_artist_day_count,
            self.previous_listening_day_count,
            "previous_artists_per_listening_day",
        )
        _validate_optional_non_negative_ratio_from_counts(
            self.current_artists_per_listening_day,
            self.current_artist_day_count,
            self.current_listening_day_count,
            "current_artists_per_listening_day",
        )
        _validate_change_fields(
            self.previous_artists_per_listening_day,
            self.current_artists_per_listening_day,
            self.signed_change,
            self.absolute_change,
            "breadth",
        )
        _require_bool(self.is_calculable, "is_calculable")
        expected_calculable = (
            self.previous_artists_per_listening_day is not None
            and self.current_artists_per_listening_day is not None
            and self.previous_artists_per_listening_day > 0
        )
        if self.is_calculable != expected_calculable:
            raise ValueError(
                "is_calculable must match breadth ratio and baseline availability."
            )
        if not expected_calculable:
            if self.relative_change is not None or self.absolute_relative_change is not None:
                raise ValueError(
                    "Relative breadth changes must be undefined when non-calculable."
                )
            return
        _require_finite_number(self.relative_change, "relative_change")
        _require_finite_number(
            self.absolute_relative_change, "absolute_relative_change"
        )
        if self.absolute_relative_change < 0:
            raise ValueError("absolute_relative_change must be non-negative.")
        expected_relative = (
            self.current_artists_per_listening_day
            - self.previous_artists_per_listening_day
        ) / self.previous_artists_per_listening_day
        if not _numbers_equal(self.relative_change, expected_relative):
            raise ValueError("relative_change must match the exact breadth ratios.")
        if not _numbers_equal(
            self.absolute_relative_change, abs(expected_relative)
        ):
            raise ValueError(
                "absolute_relative_change must be the magnitude of relative_change."
            )


@dataclass(frozen=True, slots=True)
class LongTermEvolutionEvidence:
    """Completed Temporal Evidence for one adjacent-window comparison."""

    timezone_name: str
    as_of: datetime
    previous_window: EvolutionWindowEvidence
    current_window: EvolutionWindowEvidence
    comparison_evidence_sufficient: bool
    artist_share_calculable: bool
    artist_share_candidates: tuple[ArtistShareEvolutionCandidate, ...]
    concentration: ConcentrationEvolutionEvidence
    breadth: ArtistBreadthEvolutionEvidence

    def __post_init__(self) -> None:
        zone = timezone_for_name(self.timezone_name)
        _require_aware(self.as_of, "as_of")
        if not isinstance(self.previous_window, EvolutionWindowEvidence):
            raise ValueError("previous_window must be EvolutionWindowEvidence.")
        if not isinstance(self.current_window, EvolutionWindowEvidence):
            raise ValueError("current_window must be EvolutionWindowEvidence.")
        if (self.previous_window.end_date - self.previous_window.start_date).days != 30:
            raise ValueError("Previous evolution window must contain exactly 30 dates.")
        if (self.current_window.end_date - self.current_window.start_date).days != 30:
            raise ValueError("Current evolution window must contain exactly 30 dates.")
        if self.previous_window.end_date != self.current_window.start_date:
            raise ValueError("Evolution windows must be adjacent and non-overlapping.")
        if self.current_window.end_date != self.as_of.astimezone(zone).date():
            raise ValueError("Current evolution window must end at local date D.")
        _require_bool(
            self.comparison_evidence_sufficient,
            "comparison_evidence_sufficient",
        )
        expected_sufficiency = (
            self.previous_window.structurally_sufficient
            and self.current_window.structurally_sufficient
        )
        if self.comparison_evidence_sufficient != expected_sufficiency:
            raise ValueError(
                "comparison_evidence_sufficient must require both sufficient windows."
            )
        _require_bool(self.artist_share_calculable, "artist_share_calculable")
        expected_share_calculable = (
            self.previous_window.total_attributed_artist_duration_ms > 0
            and self.current_window.total_attributed_artist_duration_ms > 0
        )
        if self.artist_share_calculable != expected_share_calculable:
            raise ValueError(
                "artist_share_calculable must match both attributable totals."
            )
        object.__setattr__(
            self, "artist_share_candidates", tuple(self.artist_share_candidates)
        )
        if any(
            not isinstance(item, ArtistShareEvolutionCandidate)
            for item in self.artist_share_candidates
        ):
            raise ValueError(
                "artist_share_candidates must contain ArtistShareEvolutionCandidate values."
            )
        identities = tuple(item.identity for item in self.artist_share_candidates)
        if identities != tuple(sorted(identities)) or len(set(identities)) != len(
            identities
        ):
            raise ValueError("Artist-share candidates must be unique and identity-ordered.")
        for candidate in self.artist_share_candidates:
            if (
                candidate.previous_attributed_duration_ms
                != self.previous_window.total_attributed_artist_duration_ms
                or candidate.current_attributed_duration_ms
                != self.current_window.total_attributed_artist_duration_ms
            ):
                raise ValueError(
                    "Artist-share candidates must use the comparison window totals."
                )
        if not isinstance(self.concentration, ConcentrationEvolutionEvidence):
            raise ValueError("concentration must be ConcentrationEvolutionEvidence.")
        if not isinstance(self.breadth, ArtistBreadthEvolutionEvidence):
            raise ValueError("breadth must be ArtistBreadthEvolutionEvidence.")
        if (
            self.concentration.previous_attributed_duration_ms
            != self.previous_window.total_attributed_artist_duration_ms
            or self.concentration.current_attributed_duration_ms
            != self.current_window.total_attributed_artist_duration_ms
        ):
            raise ValueError(
                "Concentration must use the comparison window attributable totals."
            )
        if (
            self.breadth.previous_listening_day_count
            != self.previous_window.listening_day_count
            or self.breadth.current_listening_day_count
            != self.current_window.listening_day_count
        ):
            raise ValueError("Breadth must use the comparison window listening days.")


def _validate_optional_ratio_from_counts(
    value: float | None, numerator: int, denominator: int, field_name: str
) -> None:
    if denominator == 0:
        if value is not None:
            raise ValueError(f"{field_name} must be undefined for a zero denominator.")
        return
    _require_ratio(value, field_name)
    if not _numbers_equal(value, numerator / denominator):
        raise ValueError(f"{field_name} must match its numerator and denominator.")


def _validate_optional_non_negative_ratio_from_counts(
    value: float | None, numerator: int, denominator: int, field_name: str
) -> None:
    if denominator == 0:
        if value is not None:
            raise ValueError(f"{field_name} must be undefined for a zero denominator.")
        return
    _require_finite_number(value, field_name)
    if value < 0:
        raise ValueError(f"{field_name} must be non-negative.")
    if not _numbers_equal(value, numerator / denominator):
        raise ValueError(f"{field_name} must match its numerator and denominator.")


def _validate_change_fields(
    previous: float | None,
    current: float | None,
    signed: float | None,
    absolute: float | None,
    label: str,
) -> None:
    if previous is None or current is None:
        if signed is not None or absolute is not None:
            raise ValueError(f"{label} changes must be undefined without both ratios.")
        return
    _require_finite_number(signed, f"signed_{label}_change")
    _require_finite_number(absolute, f"absolute_{label}_change")
    if absolute < 0:
        raise ValueError(f"absolute_{label}_change must be non-negative.")
    expected = current - previous
    if not _numbers_equal(signed, expected):
        raise ValueError(f"signed_{label}_change must match Current minus Previous.")
    if not _numbers_equal(absolute, abs(expected)):
        raise ValueError(f"absolute_{label}_change must be the signed magnitude.")


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
    if artist_name.strip().casefold() == _UNKNOWN_ARTIST:
        raise ValueError("artist_name must not use the unknown-artist sentinel.")
    if identity[0] == "spotify":
        if spotify_artist_id != identity[1]:
            raise ValueError("Spotify identity must match spotify_artist_id.")
    elif spotify_artist_id is not None:
        raise ValueError("Legacy identity cannot include spotify_artist_id.")


def _validate_window(start_date: date, end_date: date) -> None:
    _require_date(start_date, "start_date")
    _require_date(end_date, "end_date")
    if start_date >= end_date:
        raise ValueError("Evolution windows must be non-empty [start, end) ranges.")


def _validate_counts(*values: int) -> None:
    if any(
        isinstance(value, bool) or not isinstance(value, int) or value < 0
        for value in values
    ):
        raise ValueError("Evidence counts must be non-negative integers.")


def _validate_gap_dates(
    gap_dates: tuple[date, ...], start_date: date, end_date: date
) -> None:
    previous: date | None = None
    for gap_date in gap_dates:
        _require_date(gap_date, "gap date")
        if not start_date <= gap_date < end_date:
            raise ValueError("Gap dates must fall inside the evolution window.")
        if previous is not None and gap_date <= previous:
            raise ValueError("Gap dates must be ordered without duplicates.")
        previous = gap_date


def _require_ratio(value: float | None, field_name: str) -> None:
    _require_finite_number(value, field_name)
    if not 0 <= value <= 1:
        raise ValueError(f"{field_name} must be between 0 and 1.")


def _require_finite_number(value: float | None, field_name: str) -> None:
    if (
        value is None
        or isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not isfinite(value)
    ):
        raise ValueError(f"{field_name} must be a finite number.")


def _numbers_equal(left: float | None, right: float) -> bool:
    return left is not None and isclose(left, right, rel_tol=0.0, abs_tol=1e-12)


def _require_bool(value: bool, field_name: str) -> None:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be a boolean.")


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
