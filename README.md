# MusicMind AI

MusicMind uses Spotify as a data provider. Sprint 3 authenticates with Spotify,
imports saved tracks into SQLite, and keeps the app's core data as MusicMind domain models.

## What It Does

After authenticating your Spotify account, the app downloads every saved track and prints:

- Spotify Login Success
- Imported song count
- Database update confirmation

## Requirements

- Python 3.11+
- Spotify Developer app credentials

## Setup

1. Create or open your app in the Spotify Developer Dashboard.
2. Add this redirect URI to the app settings:

```text
http://127.0.0.1:8888/callback
```

3. Create a `.env` file in the project root:

```env
SPOTIPY_CLIENT_ID=your_client_id
SPOTIPY_CLIENT_SECRET=your_client_secret
SPOTIPY_REDIRECT_URI=http://127.0.0.1:8888/callback
```

4. Install dependencies:

```bash
pip install -r requirements.txt
```

5. Run the app:

```bash
python main.py
```

The app opens Spotify authorization in your browser. After login, Spotify redirects
back to the local callback server, then the app imports your saved tracks into
`music_ai/database/musicmind.db`.

## Project Structure

```text
music_ai/
    database/
        database.py
        schema.sql
    models/
        song.py
        saved_track.py
    parser/
        spotify_parser.py
    repository/
        song_repository.py
        saved_track_repository.py
    spotify/
        auth.py
        client.py
config.py
main.py
requirements.txt
README.md
.gitignore
```

## Scope

This sprint intentionally does not include analytics, GPT integration, Streamlit,
playback tracking, or any Spotipy dependency.
