"""Developer tool for viewing songs stored in the local MusicMind database."""

import json
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from music_ai.database.database import Database


def main() -> None:
    """Display every song currently stored in SQLite."""
    database = Database()
    database.initialize()
    songs = _load_songs(database)

    print("=================================")
    print("MusicMind Database")
    print("=================================")
    print()
    print(f"Songs: {len(songs)}")
    print()

    for index, song in enumerate(songs, start=1):
        print(f"{index}.")
        print()
        print(song["name"])
        print(_format_artists(song["artists"]))
        print(song["album"])
        print()
        print("-------------------------")


def _load_songs(database: Database) -> list[dict[str, Any]]:
    """Return raw song display fields from the local database."""
    with database.connection() as connection:
        rows = connection.execute("SELECT name, artists, album FROM songs").fetchall()

    return [dict(row) for row in rows]


def _format_artists(raw_artists: str) -> str:
    """Format the stored artist list for console display."""
    artists = json.loads(raw_artists)
    if not isinstance(artists, list):
        return ""

    return ", ".join(str(artist) for artist in artists)


if __name__ == "__main__":
    main()
