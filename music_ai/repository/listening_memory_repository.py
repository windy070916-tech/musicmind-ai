"""SQLite persistence for versioned listening-memory snapshots."""

from datetime import date, datetime, timezone
import sqlite3

from music_ai.database.database import Database
from music_ai.memory.models import (
    CURRENT_SNAPSHOT_VERSION,
    DailyMemorySnapshot,
    timezone_for_name,
)
from music_ai.memory.serializer import (
    MemorySerializationError,
    deserialize_snapshot,
    serialize_snapshot,
)


class InvalidMemorySnapshotError(RuntimeError):
    """Persisted derived Memory data is corrupted or internally inconsistent."""


class ListeningMemoryRepository:
    """Store and retrieve disposable daily listening-memory snapshots."""

    def __init__(self, database: Database) -> None:
        self._database = database

    def store_snapshot(self, snapshot: DailyMemorySnapshot) -> None:
        """Atomically insert or replace one snapshot with matching identity."""
        payload = serialize_snapshot(snapshot)
        with self._database.connection() as connection:
            connection.execute(
                """
                INSERT INTO listening_memory_snapshots (
                    local_date,
                    timezone_name,
                    period_start_utc,
                    period_end_utc,
                    snapshot_version,
                    generated_at_utc,
                    is_closed,
                    profile_payload
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(local_date, timezone_name, snapshot_version)
                DO UPDATE SET
                    period_start_utc = excluded.period_start_utc,
                    period_end_utc = excluded.period_end_utc,
                    generated_at_utc = excluded.generated_at_utc,
                    is_closed = excluded.is_closed,
                    profile_payload = excluded.profile_payload
                """,
                (
                    snapshot.local_date.isoformat(),
                    snapshot.timezone_name,
                    _utc_isoformat(snapshot.profile.start_datetime),
                    _utc_isoformat(snapshot.profile.end_datetime),
                    snapshot.snapshot_version,
                    _utc_isoformat(snapshot.generated_at),
                    int(snapshot.is_closed),
                    payload,
                ),
            )

    def load_snapshot(
        self,
        local_date: date,
        timezone_name: str,
        snapshot_version: int = CURRENT_SNAPSHOT_VERSION,
    ) -> DailyMemorySnapshot | None:
        """Return one validated snapshot or ``None`` when unavailable."""
        _validate_date(local_date, "local_date")
        timezone_for_name(timezone_name)
        if snapshot_version != CURRENT_SNAPSHOT_VERSION:
            return None

        with self._database.connection() as connection:
            row = connection.execute(
                """
                SELECT
                    local_date,
                    timezone_name,
                    period_start_utc,
                    period_end_utc,
                    snapshot_version,
                    generated_at_utc,
                    is_closed,
                    profile_payload
                FROM listening_memory_snapshots
                WHERE local_date = ?
                  AND timezone_name = ?
                  AND snapshot_version = ?
                """,
                (local_date.isoformat(), timezone_name, snapshot_version),
            ).fetchone()
        return _snapshot_from_row(row) if row is not None else None

    def load_range(
        self,
        start_date: date,
        end_date: date,
        timezone_name: str,
        snapshot_version: int = CURRENT_SNAPSHOT_VERSION,
    ) -> tuple[DailyMemorySnapshot, ...]:
        """Load existing snapshots in ``[start_date, end_date)`` without filling gaps."""
        _validate_range(start_date, end_date)
        timezone_for_name(timezone_name)
        if snapshot_version != CURRENT_SNAPSHOT_VERSION:
            return ()

        with self._database.connection() as connection:
            rows = connection.execute(
                """
                SELECT
                    local_date,
                    timezone_name,
                    period_start_utc,
                    period_end_utc,
                    snapshot_version,
                    generated_at_utc,
                    is_closed,
                    profile_payload
                FROM listening_memory_snapshots
                WHERE local_date >= ?
                  AND local_date < ?
                  AND timezone_name = ?
                  AND snapshot_version = ?
                ORDER BY local_date
                """,
                (
                    start_date.isoformat(),
                    end_date.isoformat(),
                    timezone_name,
                    snapshot_version,
                ),
            ).fetchall()
        return tuple(_snapshot_from_row(row) for row in rows)

    def delete_range(
        self,
        start_date: date,
        end_date: date,
        timezone_name: str,
        snapshot_version: int = CURRENT_SNAPSHOT_VERSION,
    ) -> None:
        """Idempotently delete derived snapshots in ``[start_date, end_date)``."""
        _validate_range(start_date, end_date)
        timezone_for_name(timezone_name)
        if snapshot_version != CURRENT_SNAPSHOT_VERSION:
            return

        with self._database.connection() as connection:
            connection.execute(
                """
                DELETE FROM listening_memory_snapshots
                WHERE local_date >= ?
                  AND local_date < ?
                  AND timezone_name = ?
                  AND snapshot_version = ?
                """,
                (
                    start_date.isoformat(),
                    end_date.isoformat(),
                    timezone_name,
                    snapshot_version,
                ),
            )


def _snapshot_from_row(row: sqlite3.Row) -> DailyMemorySnapshot:
    try:
        snapshot = deserialize_snapshot(str(row["profile_payload"]))
    except MemorySerializationError as error:
        raise InvalidMemorySnapshotError(
            "Stored listening-memory payload is invalid."
        ) from error

    expected = {
        "local_date": snapshot.local_date.isoformat(),
        "timezone_name": snapshot.timezone_name,
        "period_start_utc": _utc_isoformat(snapshot.profile.start_datetime),
        "period_end_utc": _utc_isoformat(snapshot.profile.end_datetime),
        "snapshot_version": snapshot.snapshot_version,
        "generated_at_utc": _utc_isoformat(snapshot.generated_at),
        "is_closed": int(snapshot.is_closed),
    }
    actual = {
        "local_date": str(row["local_date"]),
        "timezone_name": str(row["timezone_name"]),
        "period_start_utc": str(row["period_start_utc"]),
        "period_end_utc": str(row["period_end_utc"]),
        "snapshot_version": int(row["snapshot_version"]),
        "generated_at_utc": str(row["generated_at_utc"]),
        "is_closed": int(row["is_closed"]),
    }
    if actual != expected:
        raise InvalidMemorySnapshotError(
            "Stored listening-memory columns do not match the snapshot payload."
        )
    return snapshot


def _utc_isoformat(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Memory timestamps must be timezone-aware.")
    return value.astimezone(timezone.utc).isoformat()


def _validate_range(start_date: date, end_date: date) -> None:
    _validate_date(start_date, "start_date")
    _validate_date(end_date, "end_date")
    if start_date > end_date:
        raise ValueError("start_date must be earlier than or equal to end_date.")


def _validate_date(value: date, field_name: str) -> None:
    if not isinstance(value, date) or isinstance(value, datetime):
        raise ValueError(f"{field_name} must be a date.")
