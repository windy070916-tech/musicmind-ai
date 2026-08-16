"""Typed raw-event evidence for contextual listening analytics."""

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from math import isclose
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


ArtistIdentity = tuple[str, str]


class LocalClockSegment(StrEnum):
    """Frozen Sprint 4A half-open six-hour local-clock segments."""

    MIDNIGHT_TO_SIX = "00:00-06:00"
    SIX_TO_NOON = "06:00-12:00"
    NOON_TO_SIX = "12:00-18:00"
    SIX_TO_MIDNIGHT = "18:00-24:00"


@dataclass(frozen=True, slots=True)
class SegmentEventEvidence:
    """Observed playback-event support for one local-clock segment."""

    segment: LocalClockSegment
    event_count: int
    listening_day_count: int
    event_share: float

    def __post_init__(self) -> None:
        _require_non_negative_counts(self.event_count, self.listening_day_count)
        _require_share(self.event_share)


@dataclass(frozen=True, slots=True)
class ArtistContextualEvidence:
    """Primary-artist event distribution inside one contextual window."""

    identity: ArtistIdentity
    spotify_artist_id: str | None
    artist_name: str
    event_count: int
    listening_day_count: int
    segments: tuple[SegmentEventEvidence, ...]

    def __post_init__(self) -> None:
        _validate_identity(self.identity, self.spotify_artist_id, self.artist_name)
        _require_non_negative_counts(self.event_count, self.listening_day_count)
        if self.event_count <= 0 or self.listening_day_count <= 0:
            raise ValueError("Artist contextual support must be positive.")
        if self.listening_day_count > self.event_count:
            raise ValueError("Artist listening days cannot exceed artist events.")
        object.__setattr__(self, "segments", tuple(self.segments))
        _validate_segments(
            self.segments,
            total_event_count=self.event_count,
            total_listening_day_count=self.listening_day_count,
        )


@dataclass(frozen=True, slots=True)
class ContextualWindowEvidence:
    """Observed event distributions for exactly 30 local calendar dates."""

    start_date: date
    end_date: date
    event_count: int
    listening_day_count: int
    segments: tuple[SegmentEventEvidence, ...]
    artists: tuple[ArtistContextualEvidence, ...]

    def __post_init__(self) -> None:
        _require_date(self.start_date, "start_date")
        _require_date(self.end_date, "end_date")
        if (self.end_date - self.start_date).days != 30:
            raise ValueError("Contextual windows must contain exactly 30 dates.")
        _require_non_negative_counts(self.event_count, self.listening_day_count)
        if self.listening_day_count > 30:
            raise ValueError("Window listening days cannot exceed 30.")
        if self.listening_day_count > self.event_count:
            raise ValueError("Window listening days cannot exceed window events.")
        object.__setattr__(self, "segments", tuple(self.segments))
        object.__setattr__(self, "artists", tuple(self.artists))
        _validate_segments(
            self.segments,
            total_event_count=self.event_count,
            total_listening_day_count=self.listening_day_count,
        )
        if any(not isinstance(item, ArtistContextualEvidence) for item in self.artists):
            raise TypeError("artists must contain ArtistContextualEvidence values.")
        identities = tuple(item.identity for item in self.artists)
        if identities != tuple(sorted(identities)) or len(identities) != len(
            set(identities)
        ):
            raise ValueError("Contextual artists must be unique and identity-ordered.")
        if any(item.event_count > self.event_count for item in self.artists):
            raise ValueError("Artist events cannot exceed total window events.")
        if sum(item.event_count for item in self.artists) > self.event_count:
            raise ValueError("Attributed artist events cannot exceed window events.")
        if any(
            item.listening_day_count > self.listening_day_count for item in self.artists
        ):
            raise ValueError("Artist listening days cannot exceed window listening days.")


@dataclass(frozen=True, slots=True)
class ContextualListeningEvidence:
    """Adjacent raw-history windows used by Sprint 4A contextual Knowledge."""

    timezone_name: str
    as_of: datetime
    previous_window: ContextualWindowEvidence
    current_window: ContextualWindowEvidence

    def __post_init__(self) -> None:
        if not isinstance(self.timezone_name, str) or not self.timezone_name.strip():
            raise ValueError("timezone_name must be non-empty text.")
        if self.as_of.tzinfo is None or self.as_of.utcoffset() is None:
            raise ValueError("as_of must be timezone-aware.")
        if not isinstance(self.previous_window, ContextualWindowEvidence) or not isinstance(
            self.current_window, ContextualWindowEvidence
        ):
            raise TypeError("Contextual windows must be ContextualWindowEvidence values.")
        if self.previous_window.end_date != self.current_window.start_date:
            raise ValueError("Contextual windows must be adjacent and non-overlapping.")
        try:
            zone = ZoneInfo(self.timezone_name)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"Unknown timezone: {self.timezone_name}") from exc
        if self.current_window.end_date != self.as_of.astimezone(zone).date():
            raise ValueError(
                "Current contextual window must end at the open local date."
            )


def segment_for_hour(hour: int) -> LocalClockSegment:
    """Return the frozen half-open segment containing one local clock hour."""
    if isinstance(hour, bool) or not isinstance(hour, int) or not 0 <= hour <= 23:
        raise ValueError("hour must be an integer from 0 through 23.")
    if hour < 6:
        return LocalClockSegment.MIDNIGHT_TO_SIX
    if hour < 12:
        return LocalClockSegment.SIX_TO_NOON
    if hour < 18:
        return LocalClockSegment.NOON_TO_SIX
    return LocalClockSegment.SIX_TO_MIDNIGHT


def _validate_segments(
    segments: tuple[SegmentEventEvidence, ...],
    *,
    total_event_count: int,
    total_listening_day_count: int,
) -> None:
    expected = tuple(LocalClockSegment)
    if any(not isinstance(item, SegmentEventEvidence) for item in segments):
        raise TypeError("segments must contain SegmentEventEvidence values.")
    if tuple(item.segment for item in segments) != expected:
        raise ValueError("segments must contain all four clock segments in fixed order.")
    if sum(item.event_count for item in segments) != total_event_count:
        raise ValueError("Segment event counts must equal the total event count.")
    if any(item.listening_day_count > total_listening_day_count for item in segments):
        raise ValueError("Segment listening days cannot exceed total listening days.")
    if any(item.listening_day_count > item.event_count for item in segments):
        raise ValueError("Segment listening days cannot exceed segment events.")
    expected_shares = tuple(
        (item.event_count / total_event_count) if total_event_count else 0.0
        for item in segments
    )
    if any(
        not isclose(item.event_share, expected_share, rel_tol=0.0, abs_tol=1e-12)
        for item, expected_share in zip(segments, expected_shares, strict=True)
    ):
        raise ValueError("Segment event shares must match their event counts.")


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
    if identity[0] == "spotify" and spotify_artist_id != identity[1]:
        raise ValueError("Spotify identity must match spotify_artist_id.")
    if identity[0] == "legacy" and spotify_artist_id is not None:
        raise ValueError("Legacy identity cannot include spotify_artist_id.")


def _require_non_negative_counts(*values: int) -> None:
    if any(
        isinstance(value, bool) or not isinstance(value, int) or value < 0
        for value in values
    ):
        raise ValueError("Contextual counts must be non-negative integers.")


def _require_share(value: float) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("event_share must be numeric.")
    if not 0.0 <= float(value) <= 1.0:
        raise ValueError("event_share must be between zero and one.")


def _require_date(value: date, field_name: str) -> None:
    if not isinstance(value, date) or isinstance(value, datetime):
        raise ValueError(f"{field_name} must be a date.")
