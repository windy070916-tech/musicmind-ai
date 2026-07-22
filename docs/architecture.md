# MusicMind Architecture

MusicMind is organized as a one-way pipeline. Each layer receives data from the
layer before it and exposes a narrower, more reusable contract to the layer after it.

```text
Spotify
    |
    v
Repository
    |
    v
Analytics
    |
    v
Knowledge
    |\
    | \ Narrative <--- DailyListeningProfile
    |       |
    |       v
    |   Presentation
    |
    v
Report Generator --> LLM Provider
```

## Spotify

The Spotify layer handles authentication and API access. It knows how to request
recent playback data and user information from Spotify, but it does not decide how
MusicMind should store, analyze, or present that data.

## Repository

Repositories persist and retrieve domain models from SQLite. They own database
reads and writes, map rows to domain objects, and keep SQL details away from
analytics and presentation code.

## Analytics

Analytics reads repository-backed data and calculates listening statistics, such as
total listening time, playback count, top songs, and top artists. It produces
`ListeningSummary` objects and does not interpret those values as user-facing
insights.

## Knowledge

Knowledge converts analytics results into reusable `KnowledgeFact` objects. It does
not query Spotify, access the database, or calculate analytics. It interprets
already-computed summaries into daily facts, trend facts, and insight facts.

## Narrative

Narrative combines a `DailyListeningProfile` with already-interpreted
`KnowledgeFact` objects into the stable `DailyNarrative` product contract. It owns
composition and deterministic ordering, not analytics, interpretation, rendering,
or AI generation.

## Presentation

Presentation renders `DailyNarrative` as the deterministic `MusicMind Daily`. It
formats existing values and descriptions without accessing Spotify, SQLite,
repositories, Analytics, KnowledgeEngine, or LLM providers.

## Report Generator

The report generator converts structured knowledge facts into a provider-neutral
prompt, validates the returned `DailyBrief` schema, and renders it as Markdown. It
depends on facts, not on Spotify, repositories, databases, or analytics. The same
brief object can later be rendered by a web or mobile presentation adapter.

The AI report remains separate from the deterministic Narrative presentation path.

## LLM Provider

LLM providers are adapters for external text-generation services. They implement a
shared interface so report generation can stay independent of provider-specific
HTTP details.

## Design Rule

Business data should move forward through the pipeline. A later layer should not
reach backward into Spotify, repositories, or the database to recreate work that an
earlier layer already performed.
