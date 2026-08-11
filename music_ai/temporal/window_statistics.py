"""Shared locale-neutral statistics for explicit listening windows."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from music_ai.memory.models import DailyMemorySnapshot
from music_ai.temporal.long_term_models import ArtistIdentity


_UNKNOWN_ARTIST = "unknown artist"


@dataclass(frozen=True, slots=True)
class ArtistWindowAggregate:
    """Immutable primary-artist statistics for one explicit window."""

    identity: ArtistIdentity
    spotify_artist_id: str | None
    artist_name: str
    duration_ms: int
    appearance_day_count: int
    closed_supporting_day_count: int

    def __post_init__(self) -> None:
        """Validate stable identity and non-negative supporting evidence."""
        _validate_identity(self.identity, self.spotify_artist_id, self.artist_name)
        _validate_counts(
            self.duration_ms,
            self.appearance_day_count,
            self.closed_supporting_day_count,
        )
        if self.duration_ms <= 0:
            raise ValueError("Artist duration_ms must be positive.")
        if self.appearance_day_count <= 0:
            raise ValueError("Artist appearance_day_count must be positive.")
        if self.closed_supporting_day_count > self.appearance_day_count:
            raise ValueError(
                "closed_supporting_day_count cannot exceed appearance_day_count."
            )


@dataclass(frozen=True, slots=True)
class ListeningWindowStatistics:
    """Immutable raw statistics for one non-empty half-open date window."""

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
    artist_day_appearance_count: int
    artists: tuple[ArtistWindowAggregate, ...]

    def __post_init__(self) -> None:
        """Validate the complete immutable statistics contract."""
        _validate_window(self.start_date, self.end_date)
        _validate_counts(
            self.recorded_day_count,
            self.listening_day_count,
            self.closed_day_count,
            self.closed_listening_day_count,
            self.total_estimated_listening_duration_ms,
            self.total_attributed_artist_duration_ms,
            self.artist_day_appearance_count,
        )
        if not isinstance(self.contains_open_snapshot, bool):
            raise ValueError("contains_open_snapshot must be a boolean.")
        object.__setattr__(self, "gap_dates", tuple(self.gap_dates))
        object.__setattr__(self, "artists", tuple(self.artists))
        _validate_gap_dates(self.gap_dates, self.start_date, self.end_date)

        window_day_count = (self.end_date - self.start_date).days
        if self.recorded_day_count + len(self.gap_dates) != window_day_count:
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
        expected_open = self.closed_day_count < self.recorded_day_count
        if self.contains_open_snapshot != expected_open:
            raise ValueError(
                "contains_open_snapshot must match recorded and closed day counts."
            )
        if any(not isinstance(item, ArtistWindowAggregate) for item in self.artists):
            raise ValueError("artists must contain ArtistWindowAggregate values.")
        identities = tuple(item.identity for item in self.artists)
        if identities != tuple(sorted(identities)) or len(set(identities)) != len(
            identities
        ):
            raise ValueError("Artist aggregates must be unique and identity-ordered.")
        if any(
            item.appearance_day_count > self.listening_day_count
            for item in self.artists
        ):
            raise ValueError(
                "Artist appearance days cannot exceed window listening days."
            )
        if (
            sum(item.duration_ms for item in self.artists)
            != self.total_attributed_artist_duration_ms
        ):
            raise ValueError(
                "Artist durations must equal total attributed artist duration."
            )
        if (
            sum(item.appearance_day_count for item in self.artists)
            != self.artist_day_appearance_count
        ):
            raise ValueError(
                "Artist appearance days must equal artist_day_appearance_count."
            )
        if (
            self.total_attributed_artist_duration_ms
            > self.total_estimated_listening_duration_ms
        ):
            raise ValueError(
                "Attributed artist duration cannot exceed total listening duration."
            )


def calculate_listening_window_statistics(
    snapshots: tuple[DailyMemorySnapshot, ...],
    start_date: date,
    end_date: date,
) -> ListeningWindowStatistics:
    """Aggregate snapshots inside exactly one explicit half-open window."""
    _validate_window(start_date, end_date)
    if not isinstance(snapshots, tuple) or any(
        not isinstance(snapshot, DailyMemorySnapshot) for snapshot in snapshots
    ):
        raise TypeError("snapshots must be a tuple of DailyMemorySnapshot values.")

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

    artists = tuple(
        ArtistWindowAggregate(
            identity=identity,
            spotify_artist_id=(identity[1] if identity[0] == "spotify" else None),
            artist_name=min(names[identity]),
            duration_ms=artist_duration_ms[identity],
            appearance_day_count=artist_day_count[identity],
            closed_supporting_day_count=closed_artist_day_count[identity],
        )
        for identity in sorted(artist_duration_ms)
    )
    return ListeningWindowStatistics(
        start_date=start_date,
        end_date=end_date,
        recorded_day_count=len(selected),
        listening_day_count=listening_day_count,
        closed_day_count=sum(snapshot.is_closed for snapshot in selected),
        closed_listening_day_count=closed_listening_day_count,
        gap_dates=gap_dates,
        contains_open_snapshot=any(not snapshot.is_closed for snapshot in selected),
        total_estimated_listening_duration_ms=total_duration_ms,
        total_attributed_artist_duration_ms=sum(artist_duration_ms.values()),
        artist_day_appearance_count=sum(artist_day_count.values()),
        artists=artists,
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
    if not _usable_artist_name(artist_name.strip()):
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
        raise ValueError("Statistics windows must be non-empty [start, end) ranges.")


def _validate_counts(*values: int) -> None:
    if any(
        isinstance(value, bool) or not isinstance(value, int) or value < 0
        for value in values
    ):
        raise ValueError("Statistics counts must be non-negative integers.")


def _validate_gap_dates(
    gap_dates: tuple[date, ...], start_date: date, end_date: date
) -> None:
    previous: date | None = None
    for gap_date in gap_dates:
        _require_date(gap_date, "gap date")
        if not start_date <= gap_date < end_date:
            raise ValueError("Gap dates must fall inside the statistics window.")
        if previous is not None and gap_date <= previous:
            raise ValueError("Gap dates must be ordered without duplicates.")
        previous = gap_date


def _dates(start_date: date, end_date: date) -> tuple[date, ...]:
    values: list[date] = []
    current = start_date
    while current < end_date:
        values.append(current)
        current += timedelta(days=1)
    return tuple(values)


def _require_date(value: date, field_name: str) -> None:
    if not isinstance(value, date) or isinstance(value, datetime):
        raise ValueError(f"{field_name} must be a date.")
