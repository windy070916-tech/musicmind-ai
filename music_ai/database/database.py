"""SQLite connection management for MusicMind."""

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path


DEFAULT_DATABASE_PATH = Path(__file__).with_name("musicmind.db")
SCHEMA_PATH = Path(__file__).with_name("schema.sql")


class Database:
    """Manage MusicMind's SQLite database and transactions."""

    def __init__(self, database_path: str | Path = DEFAULT_DATABASE_PATH):
        """Create a database manager for the given SQLite file."""
        self._database_path = Path(database_path)

    def initialize(self) -> None:
        """Create the database tables when they do not already exist."""
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        schema = SCHEMA_PATH.read_text(encoding="utf-8")

        with self.connection() as connection:
            connection.executescript(schema)

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
