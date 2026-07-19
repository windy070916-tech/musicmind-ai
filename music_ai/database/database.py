"""SQLite connection management for MusicMind."""

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path


DEFAULT_DATABASE_PATH = Path(__file__).with_name("musicmind.db")
SCHEMA_PATH = Path(__file__).with_name("schema.sql")


class Database:
    """Manage MusicMind's SQLite database and transactions."""

    def __init__(self, database_path: str | Path = DEFAULT_DATABASE_PATH) -> None:
        """Create a database manager for the given SQLite file."""
        self._database_path = Path(database_path)

    def initialize(self) -> None:
        """Create or update the database tables for the current schema."""
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        schema = SCHEMA_PATH.read_text(encoding="utf-8")

        with self.connection() as connection:
            connection.executescript(schema)
            self._allow_nullable_song_popularity(connection)

    @contextmanager
    def connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Yield a database connection and commit or roll back its transaction."""
        connection = sqlite3.connect(self._database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")

        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _allow_nullable_song_popularity(self, connection: sqlite3.Connection) -> None:
        """Rebuild old songs tables where popularity was created as NOT NULL."""
        columns = connection.execute("PRAGMA table_info(songs)").fetchall()
        popularity_column = next(
            (column for column in columns if column["name"] == "popularity"),
            None,
        )
        if popularity_column is None or popularity_column["notnull"] == 0:
            return

        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute(
            """
            CREATE TABLE songs_new (
                spotify_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                artists TEXT NOT NULL,
                album TEXT NOT NULL,
                duration_ms INTEGER NOT NULL,
                explicit INTEGER NOT NULL,
                popularity INTEGER
            )
            """
        )
        connection.execute(
            """
            INSERT INTO songs_new (
                spotify_id, name, artists, album, duration_ms, explicit, popularity
            )
            SELECT
                spotify_id, name, artists, album, duration_ms, explicit, popularity
            FROM songs
            """
        )
        connection.execute("DROP TABLE songs")
        connection.execute("ALTER TABLE songs_new RENAME TO songs")
        connection.execute("PRAGMA foreign_keys = ON")
