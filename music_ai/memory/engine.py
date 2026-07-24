"""Lifecycle coordination for deterministic listening-memory snapshots."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, timedelta, timezone
from typing import TYPE_CHECKING

from music_ai.analytics.listening_analytics import ListeningAnalytics
from music_ai.memory.models import (
    CURRENT_SNAPSHOT_VERSION,
    DailyMemorySnapshot,
    ListeningMemory,
    local_day_utc_boundaries,
    timezone_for_name,
)

if TYPE_CHECKING:
    from music_ai.repository.listening_memory_repository import (
        ListeningMemoryRepository,
    )


class MemoryEngine:
    """Capture, load, and explicitly rebuild versioned Analytics snapshots."""

    def __init__(
        self,
        analytics: ListeningAnalytics,
        repository: ListeningMemoryRepository,
        timezone_name: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._analytics = analytics
        self._repository = repository
        self._timezone_name = timezone_name
        self._zone = timezone_for_name(timezone_name)
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def capture_date(self, local_date: date) -> DailyMemorySnapshot:
        """Calculate and upsert one explicit local-calendar date."""
        return self._capture_date(local_date, self._now_utc())

    def capture_current_day(self) -> DailyMemorySnapshot:
        """Refresh the current date in the configured canonical timezone."""
        generated_at = self._now_utc()
        local_date = generated_at.astimezone(self._zone).date()
        return self._capture_date(local_date, generated_at)

    def load_range(self, start_date: date, end_date: date) -> ListeningMemory:
        """Read a bounded, sparse Memory range without calculating or writing."""
        _validate_range(start_date, end_date)
        snapshots = self._repository.load_range(
            start_date,
            end_date,
            self._timezone_name,
            CURRENT_SNAPSHOT_VERSION,
        )
        return ListeningMemory(
            start_date=start_date,
            end_date=end_date,
            timezone_name=self._timezone_name,
            snapshots=snapshots,
            as_of=self._now_utc(),
        )

    def rebuild_range(self, start_date: date, end_date: date) -> ListeningMemory:
        """Explicitly replace every current-version date in a bounded range."""
        _validate_range(start_date, end_date)
        snapshots: list[DailyMemorySnapshot] = []
        current_date = start_date
        while current_date < end_date:
            snapshots.append(self.capture_date(current_date))
            current_date += timedelta(days=1)
        return ListeningMemory(
            start_date=start_date,
            end_date=end_date,
            timezone_name=self._timezone_name,
            snapshots=tuple(snapshots),
            as_of=self._now_utc(),
        )

    def _capture_date(
        self, local_date: date, generated_at: datetime
    ) -> DailyMemorySnapshot:
        _validate_date(local_date, "local_date")
        start_datetime, end_datetime = local_day_utc_boundaries(
            local_date, self._zone
        )
        profile = self._analytics.get_daily_listening_profile(
            start_datetime, end_datetime
        )
        snapshot = DailyMemorySnapshot(
            local_date=local_date,
            timezone_name=self._timezone_name,
            profile=profile,
            generated_at=generated_at,
            is_closed=generated_at >= end_datetime,
            snapshot_version=CURRENT_SNAPSHOT_VERSION,
        )
        self._repository.store_snapshot(snapshot)
        return snapshot

    def _now_utc(self) -> datetime:
        current = self._clock()
        if (
            not isinstance(current, datetime)
            or current.tzinfo is None
            or current.utcoffset() is None
        ):
            raise ValueError("MemoryEngine clock must return an aware datetime.")
        return current.astimezone(timezone.utc)


def _validate_range(start_date: date, end_date: date) -> None:
    _validate_date(start_date, "start_date")
    _validate_date(end_date, "end_date")
    if start_date > end_date:
        raise ValueError("start_date must be earlier than or equal to end_date.")


def _validate_date(value: date, field_name: str) -> None:
    if not isinstance(value, date) or isinstance(value, datetime):
        raise ValueError(f"{field_name} must be a date.")
