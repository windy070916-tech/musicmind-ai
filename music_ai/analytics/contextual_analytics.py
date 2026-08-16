"""Read-only contextual analytics over retained raw playback events."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
import json
import sqlite3
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from music_ai.analytics.contextual_models import (
    ArtistContextualEvidence,
    ArtistIdentity,
    ContextualListeningEvidence,
    ContextualWindowEvidence,
    LocalClockSegment,
    SegmentEventEvidence,
    segment_for_hour,
)
from music_ai.database.database import Database


_CONTEXTUAL_WINDOW_DAYS = 30
_UNKNOWN_ARTIST = "unknown artist"


@dataclass(frozen=True, slots=True)
class _ObservedEvent:
    local_date: date
    segment: LocalClockSegment
    artist_identity: ArtistIdentity | None
    spotify_artist_id: str | None
    artist_name: str | None


class ContextualListeningAnalytics:
    """Measure event-count-only listening context from retained SQLite history."""

    def __init__(self, database: Database) -> None:
        self._database = database

    def analyze(
        self, *, timezone_name: str, as_of: datetime
    ) -> ContextualListeningEvidence:
        """Return adjacent ``[D-60,D-30)`` and ``[D-30,D)`` raw-event evidence.

        ``D`` is the local date containing ``as_of``. The open local day is
        excluded. Only each row's recorded event timestamp is measured; track
        duration and Memory coverage play no role in this calculation.
        """
        zone = _timezone(timezone_name)
        if (
            not isinstance(as_of, datetime)
            or as_of.tzinfo is None
            or as_of.utcoffset() is None
        ):
            raise ValueError("as_of must be timezone-aware.")

        current_end = as_of.astimezone(zone).date()
        current_start = current_end - timedelta(days=_CONTEXTUAL_WINDOW_DAYS)
        previous_start = current_start - timedelta(days=_CONTEXTUAL_WINDOW_DAYS)
        query_start = datetime.combine(previous_start, time.min, zone)
        query_end = datetime.combine(current_end, time.min, zone)
        rows = self._load_rows(query_start, query_end)
        events = tuple(_observed_event(row, zone) for row in rows)

        return ContextualListeningEvidence(
            timezone_name=timezone_name,
            as_of=as_of,
            previous_window=_build_window(events, previous_start, current_start),
            current_window=_build_window(events, current_start, current_end),
        )

    def _load_rows(
        self, start_datetime: datetime, end_datetime: datetime
    ) -> tuple[sqlite3.Row, ...]:
        start_utc = start_datetime.astimezone(timezone.utc).isoformat()
        end_utc = end_datetime.astimezone(timezone.utc).isoformat()
        with self._database.connection() as connection:
            rows = connection.execute(
                """
                SELECT
                    play_history.id,
                    play_history.played_at,
                    songs.artists AS legacy_artists,
                    (
                        SELECT song_artists.artist_id
                        FROM song_artists
                        WHERE song_artists.song_id = songs.spotify_id
                        ORDER BY song_artists.credit_position, song_artists.artist_id
                        LIMIT 1
                    ) AS primary_artist_id,
                    (
                        SELECT artists.name
                        FROM song_artists
                        JOIN artists ON artists.spotify_id = song_artists.artist_id
                        WHERE song_artists.song_id = songs.spotify_id
                        ORDER BY song_artists.credit_position, song_artists.artist_id
                        LIMIT 1
                    ) AS primary_artist_name
                FROM play_history
                JOIN songs ON songs.spotify_id = play_history.song_id
                WHERE julianday(play_history.played_at) >= julianday(?)
                  AND julianday(play_history.played_at) < julianday(?)
                ORDER BY julianday(play_history.played_at), play_history.id
                """,
                (start_utc, end_utc),
            ).fetchall()
        return tuple(rows)


def _observed_event(row: sqlite3.Row, zone: ZoneInfo) -> _ObservedEvent:
    recorded_at = datetime.fromisoformat(str(row["played_at"]))
    if recorded_at.tzinfo is None or recorded_at.utcoffset() is None:
        raise ValueError("Stored playback event timestamps must be timezone-aware.")
    local_timestamp = recorded_at.astimezone(zone)
    identity, spotify_id, artist_name = _primary_artist(row)
    return _ObservedEvent(
        local_date=local_timestamp.date(),
        segment=segment_for_hour(local_timestamp.hour),
        artist_identity=identity,
        spotify_artist_id=spotify_id,
        artist_name=artist_name,
    )


def _primary_artist(
    row: sqlite3.Row,
) -> tuple[ArtistIdentity | None, str | None, str | None]:
    spotify_id = _optional_text(row["primary_artist_id"])
    normalized_name = _optional_text(row["primary_artist_name"])
    legacy_name = _legacy_primary_artist(row["legacy_artists"])
    display_name = normalized_name or legacy_name
    if display_name is None or display_name.casefold() == _UNKNOWN_ARTIST:
        return None, None, None
    if spotify_id is not None:
        return ("spotify", spotify_id), spotify_id, display_name
    return ("legacy", display_name.casefold()), None, display_name


def _legacy_primary_artist(value: object) -> str | None:
    try:
        artists = json.loads(str(value))
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("Stored song artists must be valid JSON.") from exc
    if not isinstance(artists, list):
        raise ValueError("Stored song artists must be a JSON list.")
    for artist in artists:
        usable = _optional_text(artist)
        if usable is not None:
            return usable
    return None


def _build_window(
    events: tuple[_ObservedEvent, ...], start_date: date, end_date: date
) -> ContextualWindowEvidence:
    selected = tuple(
        event for event in events if start_date <= event.local_date < end_date
    )
    total_event_count = len(selected)
    listening_days = {event.local_date for event in selected}
    segment_counts: defaultdict[LocalClockSegment, int] = defaultdict(int)
    segment_days: defaultdict[LocalClockSegment, set[date]] = defaultdict(set)
    artist_counts: defaultdict[ArtistIdentity, int] = defaultdict(int)
    artist_days: defaultdict[ArtistIdentity, set[date]] = defaultdict(set)
    artist_segment_counts: defaultdict[
        ArtistIdentity, defaultdict[LocalClockSegment, int]
    ] = defaultdict(lambda: defaultdict(int))
    artist_segment_days: defaultdict[
        ArtistIdentity, defaultdict[LocalClockSegment, set[date]]
    ] = defaultdict(lambda: defaultdict(set))
    artist_names: defaultdict[ArtistIdentity, set[str]] = defaultdict(set)
    spotify_ids: dict[ArtistIdentity, str | None] = {}

    for event in selected:
        segment_counts[event.segment] += 1
        segment_days[event.segment].add(event.local_date)
        identity = event.artist_identity
        if identity is None or event.artist_name is None:
            continue
        artist_counts[identity] += 1
        artist_days[identity].add(event.local_date)
        artist_segment_counts[identity][event.segment] += 1
        artist_segment_days[identity][event.segment].add(event.local_date)
        artist_names[identity].add(event.artist_name)
        spotify_ids[identity] = event.spotify_artist_id

    segments = _segments(segment_counts, segment_days, denominator=total_event_count)
    artists = tuple(
        ArtistContextualEvidence(
            identity=identity,
            spotify_artist_id=spotify_ids[identity],
            artist_name=min(artist_names[identity]),
            event_count=artist_counts[identity],
            listening_day_count=len(artist_days[identity]),
            segments=_segments(
                artist_segment_counts[identity],
                artist_segment_days[identity],
                denominator=artist_counts[identity],
            ),
        )
        for identity in sorted(artist_counts)
    )
    return ContextualWindowEvidence(
        start_date=start_date,
        end_date=end_date,
        event_count=total_event_count,
        listening_day_count=len(listening_days),
        segments=segments,
        artists=artists,
    )


def _segments(
    counts: dict[LocalClockSegment, int],
    days: dict[LocalClockSegment, set[date]],
    *,
    denominator: int,
) -> tuple[SegmentEventEvidence, ...]:
    return tuple(
        SegmentEventEvidence(
            segment=segment,
            event_count=counts.get(segment, 0),
            listening_day_count=len(days.get(segment, set())),
            event_share=(counts.get(segment, 0) / denominator) if denominator else 0.0,
        )
        for segment in LocalClockSegment
    )


def _timezone(timezone_name: str) -> ZoneInfo:
    if not isinstance(timezone_name, str) or not timezone_name.strip():
        raise ValueError("timezone_name must be non-empty text.")
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"Unknown timezone: {timezone_name}") from exc


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
