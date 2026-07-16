CREATE TABLE IF NOT EXISTS songs (
    spotify_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    artists TEXT NOT NULL,
    album TEXT NOT NULL,
    duration_ms INTEGER NOT NULL,
    explicit INTEGER NOT NULL,
    popularity INTEGER
);

CREATE TABLE IF NOT EXISTS saved_tracks (
    song_id TEXT NOT NULL,
    added_at TEXT NOT NULL,
    PRIMARY KEY (song_id, added_at),
    FOREIGN KEY (song_id) REFERENCES songs(spotify_id)
);

CREATE TABLE IF NOT EXISTS play_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    song_id TEXT NOT NULL,
    played_at TEXT NOT NULL,
    played_duration_ms INTEGER,
    source TEXT NOT NULL,
    UNIQUE (song_id, played_at),
    FOREIGN KEY (song_id) REFERENCES songs(spotify_id)
);
