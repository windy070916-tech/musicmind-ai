"""Developer tool for inspecting the local MusicMind database status."""

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from music_ai.database.database import DEFAULT_DATABASE_PATH, Database


def main() -> None:
    """Display basic SQLite database statistics."""
    database = Database()
    database.initialize()

    print("Database Statistics")
    print()
    print(f"Songs: {_count_songs(database)}")
    print(f"Saved Tracks: {_count_saved_tracks(database)}")
    print(f"SQLite file size: {_database_size_bytes()} bytes")


def _count_songs(database: Database) -> int:
    """Return the number of stored songs."""
    with database.connection() as connection:
        row = connection.execute("SELECT COUNT(*) AS count FROM songs").fetchone()

    return int(row["count"])


def _count_saved_tracks(database: Database) -> int:
    """Return the number of stored saved-track records."""
    with database.connection() as connection:
        row = connection.execute("SELECT COUNT(*) AS count FROM saved_tracks").fetchone()

    return int(row["count"])


def _database_size_bytes() -> int:
    """Return the SQLite database file size in bytes."""
    if not DEFAULT_DATABASE_PATH.exists():
        return 0

    return DEFAULT_DATABASE_PATH.stat().st_size


if __name__ == "__main__":
    main()
