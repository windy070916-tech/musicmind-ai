# MusicMind Architecture

MusicMind uses a directed, layered data flow. Each layer receives an explicit
upstream contract and exposes a narrower contract to its consumers. Deterministic
presentation and the optional AI report are parallel downstream paths.

```text
Spotify
    |
    v
Parser
    |
    v
Repository
    |
    v
SQLite raw records
    |
    v
Analytics
    |\
    | \----> Memory <--------> SQLite derived snapshots
    |             |
    |             v
    |      Temporal Analytics
    |       /             \
    |  Recent Evidence  Long-term Evidence
    |       \             /
    v             v
Knowledge <-------+
    | \
    |  \----> Report Generator ----> LLM Provider
    |
    v
Narrative <---- DailyListeningProfile
    |
    v
Presentation
```

## Spotify

The Spotify layer handles authentication and API access. It knows how to request
recent playback data and user information from Spotify, but it does not decide how
MusicMind should store, analyze, or present that data.

## Parser

Parsers convert Spotify payloads into MusicMind domain models. They normalize the
external payload shape without performing persistence, longitudinal calculations,
knowledge interpretation, or presentation.

## Repository

Most persistence operations use repositories, which persist and retrieve domain
models from SQLite and map rows to domain objects. `ListeningAnalytics` is the
current exception: it reads SQLite through the `Database` abstraction directly for
bounded analytical queries.

## Analytics

Analytics calculates bounded listening statistics such as total listening time,
playback count, top songs, and top artists. `ListeningAnalytics` currently executes
its analytical SQL through `Database`; downstream Memory consumers, Temporal,
Knowledge, Narrative, Presentation, and AI do not reach backward into raw storage.
Analytics produces `ListeningSummary` and `DailyListeningProfile` values without
interpreting them as user-facing insights.

## Memory

Memory persists versioned, immutable daily `DailyListeningProfile` snapshots for
explicit local-calendar dates. Raw `play_history` remains authoritative, and every
Memory snapshot is safe to delete and rebuild. Snapshot identity includes the
configured IANA timezone and an explicit contract version.

Runtime finalizes the previous local date before refreshing the current date after
synchronization. Bounded reads are side-effect free and preserve missing dates as
gaps; other historical generation occurs only through an explicit bounded rebuild.
Memory does not calculate Analytics, interpret behavior, produce prose, or call
Spotify or an LLM.

## Temporal Analytics

Temporal Analytics calculates deterministic longitudinal evidence from an explicit
bounded `ListeningMemory`. The caller supplies non-overlapping, half-open recent and
comparison windows. Temporal Analytics has no built-in seven-day, weekly, or monthly
period and does not capture, load, rebuild, or persist Memory.

Recent analysis produces `RecentListeningEvidence` for artist continuity and artist
emergence. The independent long-term implementation produces
`LongTermListeningEvidence` for artist consistency, listening concentration, and
artist breadth. Both preserve coverage gaps and open-day state. These are
calculations, not user-facing conclusions. The application—not either analytics
class—owns the runtime periods, including the explicit 30-day long-term policy.

## Knowledge

Knowledge converts analytics results into reusable `KnowledgeFact` objects. It does
not query Spotify, access the database, or calculate analytics. It interprets
already-computed summaries into daily, trend, and insight facts. Separately,
`RecentKnowledgeEngine` and `LongTermKnowledgeEngine` interpret their completed,
separate Temporal Evidence contracts; neither reads Memory or re-aggregates profiles.

## Narrative

Narrative combines a `DailyListeningProfile` with already-interpreted
`KnowledgeFact` objects into the stable `DailyNarrative` product contract. It owns
composition, deterministic ordering, bounded recent and long-term observation
selection, and subject-plus-concept deduplication—not analytics, interpretation,
rendering, or AI generation.

## Presentation

Presentation renders `DailyNarrative` as the deterministic `MusicMind Daily`. It
formats existing values and descriptions without accessing Spotify, SQLite,
repositories, Analytics, Temporal Analytics, Knowledge engines, or LLM providers.
The optional `Recently` and `Over Time` sections simply render observations already
selected by Narrative.

## Report Generator

The report generator converts structured knowledge facts into a provider-neutral
prompt, validates the returned `DailyBrief` schema, and renders it as Markdown. It
depends on facts, not on Spotify, repositories, databases, or analytics. The same
brief object can later be rendered by a web or mobile presentation adapter.

The AI report remains separate from the deterministic Narrative presentation path.
The runtime does not add recent or long-term facts to the AI prompt, preserving the
existing provider and prompt behavior.

## LLM Provider

LLM providers are adapters for external text-generation services. They implement a
shared interface so report generation can stay independent of provider-specific
HTTP details.

## Design Rule

Business data should move forward through the pipeline. A later layer should not
reach backward into Spotify, repositories, or the database to recreate work that an
earlier layer already performed. In particular:

- Memory stores evidence but does not interpret it.
- Temporal Analytics compares bounded Memory but does not decide what is meaningful
  enough to tell the user.
- Knowledge interprets supplied evidence but does not calculate periods.
- Narrative selects product content but does not reinterpret evidence.
- Presentation formats selected content but does not filter or rank it.
