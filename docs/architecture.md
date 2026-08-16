# MusicMind Architecture

MusicMind uses a directed, layered data flow. Each layer receives an explicit
upstream contract and exposes a narrower contract to its consumers. Deterministic
presentation and AI interpretation share qualified Knowledge evidence, then follow
separate selection paths.

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
    | \
    |  \----> Contextual Timestamp Analytics
    v
Daily Analytics ----> Memory <--------> SQLite derived snapshots
    |                    |
    |                    v
    |              Temporal Analytics
    |             /        |         \
    |        Recent    Long-term   Long-term
    |        Evidence     State    Evolution
    |             \        |         /
    +---------------> Knowledge <----- Contextual Evidence
                           | \
                           |  \----> Signal Projection
                           |              |
                           v              v
                       Narrative      Interpretation Planner
                           |              ^
                           v              |
                 Visible Report Composition
                      |             |
                      |             +----> Visible Content Manifest
                      v
              Localization / Presentation

Interpretation Planner
    -> Typed AI Request
    -> Report Generator
    -> LLM Provider
    -> Response Validation
    -> Dynamic AI Rendering
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
playback count, top songs, and top artists. `ListeningAnalytics` executes its
analytical SQL through `Database`. `ContextualListeningAnalytics` is the other
intentional raw-storage boundary: it reads retained playback-event timestamps for
the adjacent Previous `[D-60,D-30)` and Current `[D-30,D)` windows, excluding open
local day `D`.

Contextual evidence uses observed event counts only. Each recorded instant belongs
to exactly one local-clock segment: `00:00-06:00`, `06:00-12:00`, `12:00-18:00`, or
`18:00-24:00`. Track duration is not used to infer time occupancy, Memory gaps are
not treated as raw-history gaps, and retained events are described as observed local
history rather than complete Spotify history. Downstream Knowledge, Signal,
Planner, Narrative, Presentation, and AI layers do not query raw storage.

## Memory

Memory persists versioned, immutable daily `DailyListeningProfile` snapshots for
explicit local-calendar dates. Raw `play_history` remains authoritative, and every
Memory snapshot is safe to delete and rebuild. Snapshot identity includes the
configured IANA timezone and an explicit contract version.

Runtime finalizes the previous local date before refreshing the current date after
synchronization. It then performs one sparse `[D-60,D+1)` longitudinal read for the
unchanged visible Recent `[D-6,D+1)` path, the interpretation-only closed Recent
`[D-7,D)` versus `[D-14,D-7)` path, Sprint 3C state/prefix, and Sprint 3E evolution.
Bounded reads are
side-effect free and preserve missing dates as gaps; their generic containment bounds
are not repository-call provenance. Other historical generation occurs only through
an explicit bounded rebuild. Memory does not calculate Analytics, interpret
behavior, produce prose, or call Spotify or an LLM.

## Temporal Analytics

Temporal Analytics calculates deterministic longitudinal evidence from an explicit
bounded `ListeningMemory`. The caller supplies every half-open window explicitly;
Visible Recent uses its existing non-overlapping current/comparison windows. The
same Temporal engine separately derives closed Recent Signal evidence over
`[D-7,D)` versus `[D-14,D-7)` from the same in-memory value; state uses one window
plus its derived prefix, and evolution uses adjacent Previous/Current windows. Temporal
Analytics has no built-in seven-day, weekly, or monthly period and does not capture,
load, rebuild, or persist Memory.

Recent analysis produces `RecentListeningEvidence` for artist continuity and artist
emergence. The visible and closed Signal-only passes remain distinct Knowledge
inputs; closed-pass failure is isolated to the interpretation status and cannot
suppress deterministic output. Sprint 3C's independent state implementation produces
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

`ContextualKnowledgeEngine` separately qualifies canonical time-of-day pattern,
artist-by-time overrepresentation, and time-pattern evolution observations from
Contextual Analytics evidence. These locale-neutral facts support Signal Projection
and are not automatically added to the visible deterministic Narrative.

## Signal Projection

Signal Projection converts already-qualified Knowledge observations into immutable,
interpretation-oriented Signals. It owns bounded lifecycle composition,
spike-versus-sustained classification, exploration semantics, core-versus-exploration
composites, and deterministic evidence maturity. It does not query Analytics,
Temporal, Memory, repositories, or SQLite, and it does not re-qualify the factual
thresholds already owned by Knowledge.

Evidence maturity is `preliminary`, `supported`, or `strong`; it is product maturity,
not statistical probability and not `KnowledgeFact.confidence`. Signals retain
Knowledge evidence references, approved claim scopes, required caveats, compact
support dimensions, and role eligibility. Current open-day Daily evidence and the
open-inclusive visible Recent facts cannot advance long-horizon artist-preference
lifecycle or maturity; only the separate closed Recent facts enter Signal Projection.
Sprint 3E evolution facts retain combined open-snapshot provenance, and any such
fact remains visible-compatible but is ineligible for lifecycle or movement Signals.

## Narrative

Narrative combines a `DailyListeningProfile` with already-interpreted
`KnowledgeFact` objects into the stable `DailyNarrative` product contract. It owns
composition, deterministic ordering, bounded recent and long-term observation
selection, state suppression, and semantic deduplication—not analytics,
interpretation, rendering, or AI generation. Evolution facts have explicit priority;
matching breadth or concentration evolution can suppress its Sprint 3C state fact,
and same-artist Recent emergence can suppress only a long-term artist-share increase.

## Visible Report Composition and Manifest

After Narrative selection, one locale-neutral `VisibleReportComposition` applies the
final deterministic display limits. Both deterministic Presentation and the
`VisibleContentManifest` consume that same immutable composition. The manifest holds
semantic concept, subject, direction, category, horizon, and evidence references—not
localized or rendered prose—so Planner anti-restatement cannot drift from what was
actually shown.

## Interpretation Planner

The deterministic Planner consumes qualified Signals and the Visible Content
Manifest. It alone relates Signals using `reinforcement`, `contrast`,
`contextual_support`, or `unrelated`; groups and ranks candidates; suppresses pure
within-run restatement; and assigns at most one Primary, one Secondary, and one Watch.
Only `supported` or `strong` Signals are Primary/Secondary eligible, while
`preliminary` Signals are Watch-only. Secondary never exists without Primary, and a
Watch-only plan is valid. No cross-run novelty or history participates in planning.

## Presentation

Presentation renders `VisibleReportComposition` as the deterministic `MusicMind
Daily`. It formats existing values and descriptions without accessing Spotify,
SQLite, repositories, Temporal history, Signal policy, Planner ranking, or LLM
providers. The optional `Recently` and `Over Time` sections render observations
already selected by Narrative and final report composition.

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

Locale may enter runtime copy, deterministic Presentation, typed AI request
projection, and ReportGenerator prompt composition. It must not enter SQLite,
repositories, Analytics, Memory, Temporal Evidence, Knowledge calculations, Signal
qualification, Narrative contracts, Planner decisions, or provider adapters. See
`docs/localization.md`.

## Report Generator

The report generator accepts only a typed `InterpretationRequest` projected from a
non-empty Planner result. The deliberate provider projection contains selected plan
items and Signals, target locale, maturity, compact support and reference values,
claim scopes, caveats, relevant semantic visible-content references, and global
prohibited claims. It contains no raw playback rows, Memory snapshots, repositories,
Temporal objects, rejected Signals, complete KnowledgeFact collections, or rendered
deterministic Markdown.

The provider returns strict JSON containing one to three plain-text items tied to
the exact planned identifiers and roles. Structural and reference validation rejects
unknown or omitted plan items, duplicate identifiers or roles, role mismatches,
unexpected fields, empty or oversized text, and provider Markdown. The renderer
then presents the validated items as at most three short paragraphs, with no forced
greeting, closing, advice, recommendation, emoji, or filler.

An empty plan skips the provider and shows a localized no-Signal status. Transport,
JSON, or validation failure preserves the deterministic report and shows a distinct
localized AI-generation-failure status. No deterministic-summary fallback recreates
the previous duplicate-report behavior.

## LLM Provider

LLM providers are adapters for external text-generation services. They implement a
shared interface so report generation can stay independent of provider-specific
HTTP details. They contain no Signal qualification, Planner relationships, ranking,
or Knowledge product policy.

## Persistence Boundary

Sprint 4A adds no database schema, Memory version, Memory serializer, contextual
snapshot, mandatory backfill, AI-report persistence, or interpretation-plan
persistence. Cross-run novelty and semantic report history remain deferred to Round
5; only within-run restatement suppression exists.

## Design Rule

Business data should move forward through the pipeline. A later layer should not
reach backward into Spotify, repositories, or the database to recreate work that an
earlier layer already performed. In particular:

- Memory stores evidence but does not interpret it.
- Temporal Analytics compares bounded Memory but does not decide what is meaningful
  enough to tell the user.
- Contextual Analytics measures retained raw events but does not interpret them.
- Knowledge qualifies supplied evidence but does not perform AI composition.
- Signal Projection creates interpretation candidates but does not assign narrative
  relationships or roles.
- The Planner relates and ranks qualified Signals but does not recalculate evidence.
- Narrative selects product content but does not reinterpret evidence.
- Visible report composition creates both final deterministic content and its
  locale-neutral manifest.
- Presentation formats selected content but does not rank Signals or decide
  relationships.
- The LLM phrases the approved plan but does not decide truth, maturity,
  sufficiency, grouping, priority, or role.
