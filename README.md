# MusicMind AI

MusicMind imports Spotify listening data, turns analytics into reusable knowledge,
then uses a configurable LLM provider to write a daily Markdown report.

## What It Does

After authenticating your Spotify account, the app downloads recently played tracks and
prints:

- Spotify Login Success
- Imported playback-record count
- Database update confirmation
- Daily listening facts generated from analytics
- Daily listening trends and an AI-generated report

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
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=your_deepseek_api_key
```

Set `LLM_PROVIDER=openai` and provide `OPENAI_API_KEY` to use OpenAI instead.
Optional `DEEPSEEK_MODEL` and `OPENAI_MODEL` variables override the adapter defaults.

4. Install dependencies:

```bash
pip install -r requirements.txt
```

5. Run the app:

```bash
python main.py
```

The app opens Spotify authorization in your browser. After login, Spotify redirects
back to the local callback server, then the app imports playback history into
`music_ai/database/musicmind.db`.

## Project Structure

```text
docs/
    architecture.md
    knowledge.md
music_ai/
    database/
        database.py
        schema.sql
    analytics/
        listening_analytics.py
    knowledge/
        models.py
        knowledge_engine.py
    ai/
        base.py
        prompts.py
        report_generator.py
        providers/
            deepseek.py
            openai.py
    models/
        play_history.py
        song.py
        saved_track.py
    parser/
        spotify_playback_parser.py
        spotify_parser.py
    repository/
        play_history_repository.py
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

The Knowledge layer interprets already-calculated analytics into reusable dataclass
facts. The AI layer turns those facts into reports through a configured provider; it
does not access Spotify, databases, repositories, or analytics.

See `docs/architecture.md` and `docs/knowledge.md` for layer boundaries and
Knowledge-layer extension guidance.

This sprint intentionally does not include recommendations, an AI DJ, dashboards,
streaming, conversation memory, or scheduling.
