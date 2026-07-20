CREATE TABLE IF NOT EXISTS songs (
    spotify_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    artists TEXT NOT NULL,
    album TEXT NOT NULL,
    album_id TEXT,
    duration_ms INTEGER NOT NULL,
    explicit INTEGER NOT NULL,
    popularity INTEGER
);

CREATE TABLE IF NOT EXISTS artists (
    spotify_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    metadata_refreshed_at TEXT
);

CREATE TABLE IF NOT EXISTS song_artists (
    song_id TEXT NOT NULL,
    artist_id TEXT NOT NULL,
    credit_position INTEGER NOT NULL,
    PRIMARY KEY (song_id, artist_id),
    FOREIGN KEY (song_id) REFERENCES songs(spotify_id),
    FOREIGN KEY (artist_id) REFERENCES artists(spotify_id)
);

CREATE INDEX IF NOT EXISTS idx_song_artists_artist_id ON song_artists(artist_id);

CREATE TABLE IF NOT EXISTS artist_genres (
    artist_id TEXT NOT NULL,
    genre TEXT NOT NULL,
    PRIMARY KEY (artist_id, genre),
    FOREIGN KEY (artist_id) REFERENCES artists(spotify_id)
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
