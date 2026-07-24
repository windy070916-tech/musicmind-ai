"""Immutable public contracts for deterministic listening memory."""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from music_ai.analytics.listening_profile import DailyListeningProfile


CURRENT_SNAPSHOT_VERSION = 1


@dataclass(frozen=True, slots=True)
class DailyMemorySnapshot:
    """One versioned Analytics snapshot for an explicit local-calendar date."""

    local_date: date
    timezone_name: str
    profile: DailyListeningProfile
    generated_at: datetime
    is_closed: bool
    snapshot_version: int

    def __post_init__(self) -> None:
        """Validate snapshot identity and exact local-day boundaries."""
        if not isinstance(self.local_date, date) or isinstance(
            self.local_date, datetime
        ):
            raise ValueError("local_date must be a date.")
        zone = timezone_for_name(self.timezone_name)
        _require_aware(self.generated_at, "generated_at")
        if isinstance(self.snapshot_version, bool) or not isinstance(
            self.snapshot_version, int
        ):
            raise ValueError("snapshot_version must be a positive integer.")
        if self.snapshot_version <= 0:
            raise ValueError("snapshot_version must be a positive integer.")
        if not isinstance(self.is_closed, bool):
            raise ValueError("is_closed must be a boolean.")
        if not isinstance(self.profile, DailyListeningProfile):
            raise ValueError("profile must be a DailyListeningProfile.")

        _require_aware(self.profile.start_datetime, "profile.start_datetime")
        _require_aware(self.profile.end_datetime, "profile.end_datetime")
        expected_start, expected_end = local_day_utc_boundaries(
            self.local_date, zone
        )
        if (
            self.profile.start_datetime.astimezone(timezone.utc) != expected_start
            or self.profile.end_datetime.astimezone(timezone.utc) != expected_end
        ):
            raise ValueError(
                "Profile period must match the snapshot's exact local-calendar day."
            )
        if self.profile.start_datetime >= self.profile.end_datetime:
            raise ValueError("Profile period must use a non-empty [start, end) range.")


@dataclass(frozen=True, slots=True)
class ListeningMemory:
    """A bounded, possibly sparse collection of daily Memory snapshots."""

    start_date: date
    end_date: date
    timezone_name: str
    snapshots: tuple[DailyMemorySnapshot, ...]
    as_of: datetime

    def __post_init__(self) -> None:
        """Validate range, ordering, timezone, version, and uniqueness rules."""
        _require_date(self.start_date, "start_date")
        _require_date(self.end_date, "end_date")
        if self.start_date > self.end_date:
            raise ValueError("start_date must be earlier than or equal to end_date.")
        timezone_for_name(self.timezone_name)
        _require_aware(self.as_of, "as_of")
        object.__setattr__(self, "snapshots", tuple(self.snapshots))

        previous_date: date | None = None
        snapshot_version: int | None = None
        for snapshot in self.snapshots:
            if not isinstance(snapshot, DailyMemorySnapshot):
                raise ValueError(
                    "snapshots must contain DailyMemorySnapshot values."
                )
            if snapshot.timezone_name != self.timezone_name:
                raise ValueError("All snapshots must use the Memory timezone.")
            if not self.start_date <= snapshot.local_date < self.end_date:
                raise ValueError(
                    "Every snapshot must fall inside [start_date, end_date)."
                )
            if previous_date is not None and snapshot.local_date <= previous_date:
                raise ValueError(
                    "Snapshots must be ordered by local_date without duplicates."
                )
            if snapshot_version is None:
                snapshot_version = snapshot.snapshot_version
            elif snapshot.snapshot_version != snapshot_version:
                raise ValueError("ListeningMemory cannot mix snapshot versions.")
            previous_date = snapshot.local_date


def timezone_for_name(timezone_name: str) -> ZoneInfo:
    """Return a validated IANA timezone."""
    if not isinstance(timezone_name, str) or not timezone_name:
        raise ValueError("timezone_name must be a valid IANA timezone name.")
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as error:
        raise ValueError(
            f"timezone_name is not a valid IANA timezone: {timezone_name!r}"
        ) from error


def local_day_utc_boundaries(
    local_date: date, zone: ZoneInfo
) -> tuple[datetime, datetime]:
    """Return exact UTC boundaries for one local-calendar date."""
    _require_date(local_date, "local_date")
    local_start = datetime.combine(local_date, time.min, tzinfo=zone)
    local_end = datetime.combine(local_date + timedelta(days=1), time.min, tzinfo=zone)
    return (
        local_start.astimezone(timezone.utc),
        local_end.astimezone(timezone.utc),
    )


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
