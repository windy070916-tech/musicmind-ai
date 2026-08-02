# Temporal Analytics

Temporal Analytics is MusicMind's deterministic calculation boundary for
longitudinal listening evidence. Recent and long-term analysis share this domain but
use independent implementations and contracts. Both consume immutable daily
snapshots and return typed evidence rather than user-facing conclusions.

## Long-term listening analytics

`LongTermListeningAnalytics.analyze()` receives one explicit half-open local-date
window and returns immutable `LongTermListeningEvidence`. It owns no implicit 30-day,
monthly, or yearly period. The runtime supplies a 30-calendar-day window ending at
the current local date, thereby excluding the current open local day.

The evidence records timezone, `as_of`, exact dates, recorded and listening days,
closed coverage, gaps, open-day state, total estimated duration, and separate
contracts for:

- artist consistency: appearance days, appearance share, closed support, aggregate
  duration, and duration share;
- listening concentration: deterministic top-one and top-five artist duration
  shares; and
- artist breadth: unique, single-day, and repeated artist counts plus artist-day
  appearances per listening day.

Each concept includes current `[start_date, end_date)` metrics and prefix
`[start_date, end_date - 1 day)` metrics. Analytics calculates structural
sufficiency and structural transitions. Knowledge applies the product thresholds
and emits a fact only when the product threshold is newly crossed.

Long-term structural support requires at least ten listening days and seven closed
listening days. Concept-specific support additionally requires repeated artist days
for consistency and ten usable artists for concentration. Open snapshots may
participate descriptively, but cannot independently support a strong conclusion.

The artist identity, gap, zero-listening-day, and deterministic display-name rules
below apply equally to recent and long-term evidence.

## Recent inputs and windows

`TemporalListeningAnalytics.analyze()` receives one bounded `ListeningMemory` plus
explicit recent and comparison windows. Every window uses local dates and half-open
semantics:

```text
[start_date, end_date)
```

Both windows must be non-empty, non-overlapping, and fully contained in the supplied
Memory range. An optional timezone must match the Memory timezone, and an optional
`as_of` value must be timezone-aware.

Temporal Analytics deliberately owns no default period. It does not assume 7, 14,
or 30 days, and it does not define “week” or “month.” The application currently
chooses adjacent seven-calendar-day windows for the Daily runtime; another caller
can choose a different explicit bounded comparison without changing Temporal
Analytics.

## Recent output contract

`RecentListeningEvidence` records the shared timezone, `as_of` time, exact windows,
gap dates, open-day presence, and immutable collections of:

- `ArtistContinuityEvidence`
- `ArtistEmergenceEvidence`

These models expose calculated values and coverage so downstream interpretation is
traceable. They are evidence contracts, not `KnowledgeFact` values and not
presentation models.

## Artist continuity

Continuity evaluates the rank-one artist already present in each daily
`DailyListeningProfile`:

- A listening day has positive total estimated listening duration.
- A qualifying day is a listening day on which the artist is ranked first.
- The qualifying-day share is qualifying days divided by listening days.
- Structural evidence is sufficient after at least three listening days and three
  qualifying days, including at least one closed qualifying day.
- `continuity_transition` is true only when the full recent window is structurally
  sufficient but that same window without its final calendar date was not.

The evidence also records total snapshot coverage, missing dates, open-day presence,
and how many qualifying days are closed. Temporal Analytics does not turn these
values into prose.

## Artist emergence

Emergence compares an artist's share of total estimated listening duration in the
recent window with its share in the comparison window:

```text
artist duration share = artist estimated duration / window estimated duration
duration share change = recent share - comparison share
```

Structural evidence requires:

- at least two listening days in the recent window;
- at least two listening days in the comparison window;
- the artist to appear on at least two recent listening days; and
- at least one closed recent artist day and one closed comparison listening day;
  and
- positive duration denominators in both windows.

`emergence_transition` records a structurally supported positive share change.
It means movement from the explicit comparison window to the explicit recent
window—not that MusicMind remembered whether it displayed the observation on a
previous run. Knowledge separately decides whether that change is meaningful enough
to say.

## Gaps and open days

A missing snapshot remains an explicit gap date. A stored day with no listening is a
recorded day, not a gap. Gaps are never silently converted into zero-listening
evidence.

Open snapshots may participate in calculations, and the evidence reports their
presence. A current open day cannot create a supported observation by itself:
structural sufficiency requires repeated evidence plus closed support. A mixed
closed/open window may qualify, while evidence supported entirely by open snapshots
remains insufficient. Continuity and emergence both expose closed-support counts so
downstream consumers can audit coverage without querying Memory.

## Artist identity

Artist aggregation is ID-first:

- With a Spotify artist ID: `("spotify", spotify_artist_id)`.
- Without an ID: `("legacy", normalized_artist_name)`.

The display name does not participate in Spotify-backed identity. Legacy names use
trimmed, case-insensitive normalization, and legacy identities are not bridged to
Spotify identities. Blank and “unknown artist” names cannot create evidence.

When multiple usable display names exist for one identity in the primary evidence
window, Temporal Analytics picks the case-sensitive lexicographically smallest
value. This keeps evidence stable regardless of snapshot encounter order.

## Threshold ownership

Thresholds are intentionally split by responsibility:

- Temporal Analytics owns structural sufficiency: enough listening days, artist
  days, duration denominators, and calculated transitions.
- Knowledge owns product meaning: continuity must cover at least half of recent
  listening days; emergence must reach at least 25% recent share and increase by at
  least 15 percentage points. Long-term Knowledge owns the artist consistency,
  top-five concentration, and artist breadth product thresholds.
- Narrative only selects already-interpreted facts.
- Presentation only formats the selected observations.

This separation lets evidence remain reusable without moving calculations into
Knowledge or product policy into Analytics.

Both transition flags are derived solely from the supplied windows. There is no
persisted “already shown” state: emergence expresses comparison-to-recent movement,
while continuity expresses the point where adding the recent window's final
calendar day first satisfies structural repetition.

## Lifecycle boundary

Temporal Analytics is read-only and has no persistence lifecycle effects. It never:

- captures or rebuilds a Memory snapshot;
- loads from or writes to a repository;
- selects a default time period;
- queries raw playback history;
- generates prose or `KnowledgeFact` objects;
- composes Narrative or renders output; or
- calls Spotify or an LLM.

The application is responsible for loading the required Memory range, choosing
explicit windows, and passing the resulting evidence to `RecentKnowledgeEngine` or
`LongTermKnowledgeEngine`.
