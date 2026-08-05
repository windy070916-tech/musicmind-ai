# MusicMind AI

MusicMind imports Spotify listening data and builds deterministic daily, recent,
and long-term listening intelligence. Analytics produces statistics, Listening
Memory preserves versioned daily evidence, Temporal Analytics evaluates explicit
bounded periods, Knowledge interprets evidence, and Narrative composes the
deterministic product output. A configurable LLM report remains separate.

## What It Does

After authenticating your Spotify account, the app downloads recently played tracks,
finalizes the previous local-day Memory snapshot, refreshes the current snapshot,
and prints:

- Spotify Login Success
- Imported playback-record count
- Database update confirmation
- A deterministic `MusicMind Daily` with the current profile and supported recent
  and `Over Time` observations
- A separate AI-generated Daily Brief

Both reports use one runtime locale. MusicMind supports Simplified Chinese
(`zh-CN`) and English (`en-US`), with `zh-CN` as the application default.

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
MUSICMIND_LOCALE=zh-CN
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=your_deepseek_api_key
```

Set `LLM_PROVIDER=openai` and provide `OPENAI_API_KEY` to use OpenAI instead.
Optional `DEEPSEEK_MODEL` and `OPENAI_MODEL` variables override the adapter defaults.
`MUSICMIND_TIMEZONE` is required and must be an IANA timezone name. It defines
MusicMind's stable local-calendar day for Analytics and Listening Memory.
`MUSICMIND_LOCALE` is optional; accepted values are exactly `zh-CN` and `en-US`.

4. Install dependencies:

```bash
pip install -r requirements.txt
```

5. Run the app:

```bash
python main.py
```

Choose a locale explicitly with either CLI form:

```bash
python main.py --locale zh-CN
python main.py --locale en-US
```

Or set one of these environment values:

```env
MUSICMIND_LOCALE=zh-CN
MUSICMIND_LOCALE=en-US
```

Resolution is `--locale` > `MUSICMIND_LOCALE` > interactive terminal selection >
non-interactive `zh-CN`. An interactive terminal offers Chinese or English once;
empty input and end-of-input select Chinese. An invalid explicit CLI or environment
value fails before Spotify authentication. The selected locale is resolved once,
controls deterministic and AI output for that run, and is never persisted.

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
        long_term_models.py
        long_term_analytics.py
    knowledge/
        message_keys.py
        models.py
        knowledge_engine.py
        recent_knowledge_engine.py
        long_term_knowledge_engine.py
    narrative/
        models.py
        engine.py
    presentation/
        narrative_markdown_renderer.py
    localization/
        models.py
        resolver.py
        catalog.py
        formatters.py
        fact_localizer.py
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
daily profiles, while Listening Memory stores rebuildable daily snapshots. Recent
and long-term Temporal Analytics use separate immutable evidence contracts. The
long-term contract describes artist consistency, listening concentration, and
artist breadth. Neither analytics path owns default periods, persistence, prose, or
product-meaning thresholds.

Knowledge interprets analytics and temporal evidence into reusable dataclass facts.
Narrative selects recent and long-term observations into separate bounded threads.
The application owns the 30-calendar-day long-term runtime window and excludes the
current open local day. Recent and long-term facts remain outside the separate AI
report path.

See `docs/architecture.md`, `docs/memory.md`, `docs/temporal.md`,
`docs/knowledge.md`, `docs/narrative.md`, and `docs/localization.md` for layer
boundaries and extension guidance.

Long-term observations describe locally recorded evidence using the existing
primary-artist attribution rule. They do not guarantee complete Spotify account
history or define identity, personality, permanent taste, motivation, or emotion.
This sprint intentionally excludes recommendations, dashboards, comparison
profiles, persistent display history, automatic backfill, and scheduling.
