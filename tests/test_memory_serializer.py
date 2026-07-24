"""Regression tests for the explicit Memory JSON storage contract."""

from datetime import date, datetime, timezone
import json

import pytest

from music_ai.analytics import (
    DailyListeningProfile,
    RankedAlbum,
    RankedArtist,
    RankedGenre,
    RankedTrack,
)
from music_ai.memory import (
    CURRENT_SNAPSHOT_VERSION,
    DailyMemorySnapshot,
    MemorySerializationError,
    UnsupportedSnapshotVersionError,
    deserialize_snapshot,
    serialize_snapshot,
)
from music_ai.memory.models import local_day_utc_boundaries, timezone_for_name


LOCAL_DATE = date(2026, 7, 22)
TIMEZONE_NAME = "Asia/Shanghai"


def _snapshot(*, populated: bool = True, version: int = 1) -> DailyMemorySnapshot:
    start, end = local_day_utc_boundaries(
        LOCAL_DATE, timezone_for_name(TIMEZONE_NAME)
    )
    profile = DailyListeningProfile(
        start_datetime=start,
        end_datetime=end,
        total_estimated_listening_duration_ms=300_000 if populated else 0,
        playback_count=2 if populated else 0,
        unique_track_count=2 if populated else 0,
        unique_track_ratio=1.0 if populated else 0.0,
        top_track_share=2 / 3 if populated else 0.0,
        genre_covered_duration_ms=300_000 if populated else 0,
        genre_coverage=1.0 if populated else 0.0,
        top_tracks=(
            RankedTrack(
                spotify_track_id="track-id",
                name="Track",
                artist_names=("Artist A", "Artist B"),
                album_name="Album",
                spotify_album_id=None,
                play_count=1,
                estimated_listening_duration_ms=200_000,
                share=2 / 3,
            ),
            RankedTrack(
                spotify_track_id="track-id-2",
                name="Track 2",
                artist_names=("Artist B",),
                album_name="Album 2",
                spotify_album_id="album-id-2",
                play_count=1,
                estimated_listening_duration_ms=100_000,
                share=1 / 3,
            ),
        )
        if populated
        else (),
        top_artists=(
            RankedArtist(
                spotify_artist_id="artist-id",
                name="Artist A",
                play_count=1,
                estimated_listening_duration_ms=200_000,
                share=2 / 3,
            ),
            RankedArtist(
                spotify_artist_id=None,
                name="Artist B",
                play_count=1,
                estimated_listening_duration_ms=100_000,
                share=1 / 3,
            ),
        )
        if populated
        else (),
        top_albums=(
            RankedAlbum(
                spotify_album_id=None,
                name="Album",
                play_count=1,
                estimated_listening_duration_ms=200_000,
                share=2 / 3,
            ),
            RankedAlbum(
                spotify_album_id="album-id-2",
                name="Album 2",
                play_count=1,
                estimated_listening_duration_ms=100_000,
                share=1 / 3,
            ),
        )
        if populated
        else (),
        top_genres=(
            RankedGenre(
                genre="pop",
                estimated_listening_duration_ms=200_000,
                share=2 / 3,
            ),
            RankedGenre(
                genre="rock",
                estimated_listening_duration_ms=100_000,
                share=1 / 3,
            ),
        )
        if populated
        else (),
    )
    return DailyMemorySnapshot(
        local_date=LOCAL_DATE,
        timezone_name=TIMEZONE_NAME,
        profile=profile,
        generated_at=datetime(2026, 7, 22, 18, 30, tzinfo=timezone.utc),
        is_closed=False,
        snapshot_version=version,
    )


@pytest.mark.parametrize("populated", [True, False])
def test_snapshot_round_trip_preserves_complete_immutable_profile(
    populated: bool,
) -> None:
    snapshot = _snapshot(populated=populated)
    before = snapshot.profile

    payload = serialize_snapshot(snapshot)
    restored = deserialize_snapshot(payload)

    assert restored == snapshot
    assert restored.profile == before
    assert restored.profile.top_tracks == before.top_tracks
    assert restored.profile.top_artists == before.top_artists
    assert restored.profile.top_albums == before.top_albums
    assert restored.profile.top_genres == before.top_genres
    assert [track.spotify_track_id for track in restored.profile.top_tracks] == (
        ["track-id", "track-id-2"] if populated else []
    )
    if populated:
        assert restored.profile.top_tracks[0].spotify_album_id is None
    assert snapshot.profile == before


def test_snapshot_serialization_is_deterministic_and_uses_utc_boundaries() -> None:
    snapshot = _snapshot()
    first = serialize_snapshot(snapshot)
    second = serialize_snapshot(snapshot)
    payload = json.loads(first)

    assert first == second
    assert payload["snapshot_version"] == CURRENT_SNAPSHOT_VERSION
    assert payload["profile"]["start_datetime"] == "2026-07-21T16:00:00+00:00"
    assert payload["profile"]["end_datetime"] == "2026-07-22T16:00:00+00:00"
    assert payload["profile"]["top_tracks"][0]["artist_names"] == [
        "Artist A",
        "Artist B",
    ]


@pytest.mark.parametrize(
    "payload,exception",
    [
        ("{", MemorySerializationError),
        ("[]", MemorySerializationError),
        ("{}", MemorySerializationError),
        (
            json.dumps(
                {
                    "snapshot_version": 99,
                    "profile": {},
                    "local_date": "2026-07-22",
                    "timezone_name": "UTC",
                    "generated_at": "2026-07-22T00:00:00+00:00",
                    "is_closed": True,
                }
            ),
            UnsupportedSnapshotVersionError,
        ),
    ],
)
def test_deserializer_rejects_malformed_missing_and_unsupported_payloads(
    payload: str, exception: type[Exception]
) -> None:
    with pytest.raises(exception):
        deserialize_snapshot(payload)


@pytest.mark.parametrize(
    "path,value",
    [
        (("profile", "playback_count"), "two"),
        (("profile", "top_tracks"), {}),
        (("profile", "top_tracks", 0, "artist_names"), "Artist"),
        (("profile", "top_artists", 0, "share"), 2.0),
        (("is_closed",), 1),
    ],
)
def test_deserializer_rejects_corrupted_nested_types(
    path: tuple[object, ...], value: object
) -> None:
    payload = json.loads(serialize_snapshot(_snapshot()))
    target: object = payload
    for key in path[:-1]:
        target = target[key]  # type: ignore[index]
    target[path[-1]] = value  # type: ignore[index]

    with pytest.raises(MemorySerializationError):
        deserialize_snapshot(json.dumps(payload))


def test_serializer_rejects_unsupported_snapshot_without_mutating_input() -> None:
    snapshot = _snapshot(version=2)
    profile = snapshot.profile

    with pytest.raises(UnsupportedSnapshotVersionError):
        serialize_snapshot(snapshot)

    assert snapshot.profile is profile
