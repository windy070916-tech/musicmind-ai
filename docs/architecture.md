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
    |             Temporal Analytics
    |          /          |          \
    |     Recent      Long-term    Long-term
    |     Evidence  State Evidence Evolution Evidence
    |          \          |          /
    v                      v
Knowledge <----------------+
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
synchronization. It then performs one sparse `[D-60,D+1)` longitudinal read for all
Recent, Sprint 3C state/prefix, and Sprint 3E evolution paths. Bounded reads are
side-effect free and preserve missing dates as gaps; their generic containment bounds
are not repository-call provenance. Other historical generation occurs only through
an explicit bounded rebuild. Memory does not calculate Analytics, interpret
behavior, produce prose, or call Spotify or an LLM.

## Temporal Analytics

Temporal Analytics calculates deterministic longitudinal evidence from an explicit
bounded `ListeningMemory`. The caller supplies every half-open window explicitly;
Recent uses non-overlapping current/comparison windows, state uses one window plus
its derived prefix, and evolution uses adjacent Previous/Current windows. Temporal
Analytics has no built-in seven-day, weekly, or monthly period and does not capture,
load, rebuild, or persist Memory.

Recent analysis produces `RecentListeningEvidence` for artist continuity and artist
emergence. Sprint 3C's independent state implementation produces
`LongTermListeningEvidence` for artist consistency, listening concentration, and
artist breadth, including its overlapping prefix novelty calculation. Sprint 3E's
`LongTermEvolutionEvidence` compares adjacent, non-overlapping Previous
`[D-60,D-30)` and Current `[D-30,D)` windows. Shared locale-neutral window
statistics keep common aggregation deterministic without changing Sprint 3C's
public evidence or denominator semantics.

All three paths preserve coverage gaps and open-day state. Evolution uses
primary-artist attributable duration for artist share and concentration; blank and
unknown artists remain outside that denominator. Previous and Current independently
need ten listening days and seven closed listening days for structural sufficiency.
These are calculations, not user-facing conclusions. The application—not a
Temporal class—owns every runtime period and the single repository-read boundary.

## Knowledge

Knowledge converts analytics results into reusable `KnowledgeFact` objects. It does
not query Spotify, access the database, or calculate analytics. It interprets
already-computed summaries into daily, trend, and insight facts. Separately,
`RecentKnowledgeEngine`, `LongTermKnowledgeEngine`, and
`LongTermEvolutionKnowledgeEngine` interpret their completed, separate Temporal
Evidence contracts; none reads Memory or re-aggregates profiles. Temporal owns
structural sufficiency and calculability. Knowledge owns exact product thresholds,
directional evolution facts, and the qualifying artist selection.

## Narrative

Narrative combines a `DailyListeningProfile` with already-interpreted
`KnowledgeFact` objects into the stable `DailyNarrative` product contract. It owns
composition, deterministic ordering, bounded recent and long-term observation
selection, state suppression, and semantic deduplication—not analytics,
interpretation, rendering, or AI generation. Evolution facts have explicit priority;
matching breadth or concentration evolution can suppress its Sprint 3C state fact,
and same-artist Recent emergence can suppress only a long-term artist-share increase.

## Presentation

Presentation renders `DailyNarrative` as the deterministic `MusicMind Daily`. It
formats existing values and descriptions without accessing Spotify, SQLite,
repositories, Analytics, Temporal Analytics, Knowledge engines, or LLM providers.
The optional `Recently` and `Over Time` sections simply render observations already
selected by Narrative.

## Localization

The application loads `.env`, resolves one `SupportedLocale`, and validates all
static catalogs before Spotify authentication or database initialization. Resolution
is CLI `--locale`, then `MUSICMIND_LOCALE`, then the fixed bilingual terminal
selector, then the non-interactive `zh-CN` default.

Localization depends on Knowledge contracts, never the reverse. Built-in facts keep
their canonical English `title` and `description` and add a semantic
`FactMessageKey`. Narrative selects and orders those canonical facts without locale.
Only the deterministic renderer localizes the already-composed observations, using
the message key, immutable metadata, Chinese templates, and focused formatters.
Sprint 3E adds six direction-specific evolution messages. Breadth values render to
one decimal place using decimal round-half-up; artist names remain opaque source
text.

Locale may enter runtime copy, deterministic Presentation, ReportGenerator prompt
composition, and AI Markdown headings. It must not enter SQLite, repositories,
Analytics, Memory, Temporal Evidence, Knowledge calculations, Narrative contracts,
`DailyBrief`, or provider adapters. See `docs/localization.md`.

## Report Generator

The report generator converts structured knowledge facts into a provider-neutral
prompt, validates the returned `DailyBrief` schema, and renders it as Markdown. It
depends on facts, not on Spotify, repositories, databases, or analytics. The same
brief object can later be rendered by a web or mobile presentation adapter.

The AI report remains separate from the deterministic Narrative presentation path.
The runtime passes only daily, trend, and existing insight `ai_facts` to the AI
prompt. Recent facts, Sprint 3C state facts, and Sprint 3E evolution facts are all
excluded, preserving existing ReportGenerator, provider, and prompt behavior.

Sprint 3D passes the resolved locale to ReportGenerator only to append an explicit
output-language instruction. Its fact input remains canonical English and retains
the existing daily, trend, and insight scope. `DailyBrief`, its English protocol
field names, schema validation, and provider adapters remain language-neutral.

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
