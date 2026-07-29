# MusicMind AI

MusicMind imports Spotify listening data and builds deterministic daily and recent
listening intelligence. Analytics produces statistics, Listening Memory preserves
versioned daily evidence, Temporal Analytics compares caller-selected periods,
Knowledge interprets evidence, and Narrative composes the deterministic product
output. A configurable LLM report remains a separate enhancement path.

## What It Does

After authenticating your Spotify account, the app downloads recently played tracks,
refreshes the current local-day Memory snapshot, and prints:

- Spotify Login Success
- Imported playback-record count
- Database update confirmation
- A deterministic `MusicMind Daily` with the current profile and supported recent
  observations
- A separate AI-generated Daily Brief

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
MUSICMIND_TIMEZONE=Asia/Shanghai
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=your_deepseek_api_key
```

Set `LLM_PROVIDER=openai` and provide `OPENAI_API_KEY` to use OpenAI instead.
Optional `DEEPSEEK_MODEL` and `OPENAI_MODEL` variables override the adapter defaults.
`MUSICMIND_TIMEZONE` is required and must be an IANA timezone name. It defines
MusicMind's stable local-calendar day for Analytics and Listening Memory.

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
    memory.md
    narrative.md
    temporal.md
music_ai/
    database/
        database.py
        schema.sql
    analytics/
        listening_analytics.py
        listening_profile.py
    memory/
        models.py
        serializer.py
        engine.py
    temporal/
        models.py
        analytics.py
    knowledge/
        models.py
        knowledge_engine.py
        recent_knowledge_engine.py
    narrative/
        models.py
        engine.py
    presentation/
        narrative_markdown_renderer.py
    ai/
        base.py
        daily_brief.py
        markdown_renderer.py
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
        listening_memory_repository.py
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

Raw playback history remains authoritative. Analytics calculates deterministic
daily profiles, while Listening Memory stores rebuildable daily snapshots. Temporal
Analytics reads explicit bounded Memory ranges and produces immutable evidence for
artist continuity and artist emergence. It owns no default period, persistence
lifecycle, prose, or product-meaning thresholds.

Knowledge interprets analytics and temporal evidence into reusable dataclass facts.
Narrative then selects and organizes those facts for deterministic Presentation.
The AI layer turns the existing non-recent fact collection into a separate report
through a configured provider; it does not access Spotify, databases, repositories,
Analytics, Memory, or Temporal Analytics.

See `docs/architecture.md`, `docs/memory.md`, `docs/temporal.md`,
`docs/knowledge.md`, and `docs/narrative.md` for layer boundaries and extension
guidance.

This sprint intentionally does not include a recommendation engine, an AI DJ,
dashboards, streaming, conversation memory, long-term preference classification, or
scheduling.
