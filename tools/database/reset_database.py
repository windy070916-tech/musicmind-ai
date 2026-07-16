"""Developer tool for recreating the local MusicMind SQLite database."""

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from music_ai.database.database import DEFAULT_DATABASE_PATH, Database


def main() -> None:
    """Delete and recreate the local SQLite database after confirmation."""
    print("WARNING")
    print()
    print("This will delete the local database.")

    if not _confirmed():
        print("Reset cancelled.")
        return

    if DEFAULT_DATABASE_PATH.exists():
        DEFAULT_DATABASE_PATH.unlink()

    Database().initialize()
    print("Database recreated successfully.")


def _confirmed() -> bool:
    """Return whether the user confirmed the destructive maintenance action."""
    answer = input("Continue? (Y/N) ")
    return answer.strip().upper() == "Y"


if __name__ == "__main__":
    main()
