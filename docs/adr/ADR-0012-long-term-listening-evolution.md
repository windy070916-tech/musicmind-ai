# ADR-0012: Long-term Listening Evolution

- Status: Accepted
- Date: 2026-08-06
- Decision owners: MusicMind maintainers
- Target release: MusicMind v0.7.0 Sprint 3E
- Related ADRs: ADR-0010, ADR-0011
- Supersedes: None

## Context

MusicMind currently derives deterministic recent observations and Sprint 3C
long-term state observations from sparse, versioned daily Listening Memory
snapshots. Sprint 3C answers questions about the state of one rolling 30-day
period. Its prefix window supports novelty detection within that same period. It
does not compare the current period with a preceding, non-overlapping period.

Sprint 3E adds deterministic comparison between two adjacent rolling windows:

```text
Previous: [D - 60 days, D - 30 days)
Current:  [D - 30 days, D)
```

`D` is the current local calendar date in `MUSICMIND_TIMEZONE`. Each window
contains exactly 30 calendar dates. Both are half-open, both exclude the open local
day `D`, and neither is a natural-month period. A missing snapshot remains a gap;
it is not interpreted as a zero-listening day.

Sprint 3E introduces exactly three evolution concepts:

1. artist attributable-duration-share evolution;
2. top-five attributable-listening concentration evolution;
3. artists-per-listening-day breadth evolution.

These concepts describe changes in locally recorded behavior. They do not infer a
listener's identity, personality, emotion, motivation, loyalty, permanent taste,
or future behavior.

State, prefix novelty, and adjacent-window evolution have different meanings.
Sprint 3C state describes one current 30-day window. Sprint 3C prefix novelty asks
whether a fact newly qualifies when the last date is added to that window. Sprint
3E evolution compares the current window with the separate 30-day window that
immediately precedes it. The three meanings must remain separate in Temporal
Evidence and Knowledge interpretation.

## Decision drivers

- Evolution must be deterministic, rebuildable, and based on existing sparse
  Listening Memory evidence.
- One bounded repository read must serve Recent, Sprint 3C state, Sprint 3C prefix,
  and Sprint 3E evolution paths.
- Existing Sprint 3C public Evidence, denominators, thresholds, and prefix behavior
  must remain compatible.
- Temporal must expose raw evidence without applying product significance
  thresholds or selecting user-visible facts.
- Artist attribution and cross-window identity must be explicit and deterministic.
- Threshold boundaries and one-decimal display rounding must not depend on binary
  floating-point accidents.
- Narrative must retain ownership of selection, suppression, priority, and
  cross-horizon semantic deduplication.
- Localization must remain downstream of Narrative, and the current AI Daily Brief
  scope must remain unchanged.
- No database, Memory schema, snapshot, serialization, persistence, or backfill
  change is justified for rebuildable comparison results.

## Decision

Sprint 3E adds a shared Temporal window-statistics boundary, a separate evolution
Evidence and Analytics boundary, and a separate Knowledge interpreter. Runtime
loads one sparse range and passes the resulting `ListeningMemory` to all temporal
paths. Evolution facts join Sprint 3C state facts only at the locale-neutral
Narrative boundary and can appear only under the existing `Over Time` section.

The dependency direction remains:

```text
Memory
    -> Temporal
    -> Knowledge
    -> Narrative
    -> Presentation / Localization
```

Temporal must not import Knowledge, Narrative, Presentation, or Localization.
Knowledge must not import Localization or Presentation. Narrative must not import
Localization. Presentation must not perform fact selection, ranking, suppression,
or semantic deduplication.

## Runtime windows

Runtime must resolve `D` once from the run's existing timezone and as-of context.
It must perform exactly one half-open longitudinal Memory range read:

```text
MemoryEngine.load_range(D - 60 days, D + 1 day)
```

The returned sparse `ListeningMemory` serves all temporal paths:

```text
Recent current:       [D - 6 days,  D + 1 day)
Recent comparison:    [D - 13 days, D - 6 days)
Sprint 3C state:      [D - 30 days, D)
Sprint 3C prefix:     [D - 30 days, D - 1 day)
Sprint 3E Previous:   [D - 60 days, D - 30 days)
Sprint 3E Current:    [D - 30 days, D)
```

`D` may be present in the Recent current window under existing Recent semantics. It
must not be present in Sprint 3C state, Sprint 3C prefix, or either Sprint 3E
evolution window. Sprint 3E requires no history before `D - 60 days`.

For `D = 2026-08-06`, the exact ranges are:

```text
Repository read: [2026-06-07, 2026-08-07)
Previous:        [2026-06-07, 2026-07-07)
Current:         [2026-07-07, 2026-08-06)
```

The longitudinal repository range-read call count must be one. Existing snapshot
finalization and current-day capture writes are separate lifecycle operations and
remain unchanged. Repository half-open range behavior and sparse return semantics
remain unchanged.

## Sparse Memory ownership

Runtime owns correctness of the repository call boundaries. `ListeningMemory`
already carries caller-declared half-open `start_date` and `end_date` containment
bounds and remains sparse within them. Those generic bounds permit Temporal to
validate that an analysis window is contained in Memory, but they are not
independently verifiable repository-call provenance: they do not prove which
runtime operation created the value, that the required broader repository call
occurred, or why an expected snapshot is absent.

`LongTermEvolutionAnalytics` must validate containment and the geometry of its
explicit Previous and Current windows, but it must not claim to prove the runtime
repository call or complete persisted-history coverage. Within those explicit
windows, every absent snapshot is a gap. Runtime integration verification, rather
than new Memory metadata, must prove the repository call count and boundaries.

Requested-range coverage or provenance metadata must not be added to
`ListeningMemory`. Sprint 3E adds no Memory schema, repository persistence,
serializer, or snapshot-version change.

## Shared Temporal window statistics

Temporal owns an immutable, locale-neutral, product-threshold-free aggregate
conceptually named `ListeningWindowStatistics`. It provides reusable raw window
statistics to both existing `LongTermListeningAnalytics` and new
`LongTermEvolutionAnalytics`.

The window statistics contain evidence equivalent to:

- half-open `start_date` and `end_date`;
- recorded-day count;
- listening-day count;
- closed-day count;
- closed-listening-day count;
- unique, sorted gap dates;
- whether an open snapshot is present;
- total estimated listening duration;
- total attributable primary-artist duration;
- artist-day appearance count;
- deterministic per-artist aggregates.

Each artist aggregate, conceptually named `ArtistWindowAggregate`, contains
evidence equivalent to:

- stable artist identity;
- Spotify artist ID when available;
- deterministic source display name;
- aggregate duration;
- appearance-day count;
- closed-supporting-day count.

The statistics contract must preserve these invariants:

- its interval is `[start_date, end_date)` and `start_date` precedes `end_date`;
- all counts and durations are non-negative;
- gap dates are unique, sorted, and contained in the interval;
- recorded-day count plus gap count equals the number of calendar dates in the
  interval;
- closed-listening-day count does not exceed either listening-day count or
  closed-day count;
- artist identities are unique and artist aggregates are ordered by stable
  identity;
- every included per-window artist aggregate has strictly positive duration;
- the sum of artist durations equals total attributable artist duration;
- the sum of per-artist appearance-day counts equals artist-day appearance count;
- each closed-supporting-day count does not exceed its artist's appearance-day
  count;
- total attributable artist duration does not exceed total estimated listening
  duration;
- blank and MusicMind unknown-artist values are excluded from artist aggregates;
- one playback is attributed to one primary artist, so multi-artist duration is
  not duplicated.

Artist entries with zero or negative attributed duration do not create artist
aggregates. Within one calendar date, a usable identity contributes at most one
appearance day and, when the snapshot is closed, at most one closed-supporting day,
regardless of how many source entries refer to that identity.

A recorded zero-listening day remains recorded and is not a gap. A closed
zero-listening day contributes to closed-day count but not to listening-day or
closed-listening-day count. Missing snapshots inside the explicit interval remain
gaps.

The contract contains no locale, user-visible prose, Knowledge threshold, selected
fact, or persistence concern. It is not part of Memory serialization. It must not
claim knowledge of the repository range that produced its `ListeningMemory`.

`LongTermListeningAnalytics` may consume this shared contract only if its Sprint 3C
public Evidence types, values, ordering, total-listening-duration denominators,
concept sufficiency, structural behavior, prefix behavior, Knowledge thresholds,
and canonical facts remain unchanged.

`ListeningWindowStatistics` represents only non-empty intervals and retains the
`start_date < end_date` invariant. Existing Sprint 3C callers may analyze a
one-calendar-day state window, whose prefix is the empty interval `[start, start)`.
That released edge case must remain supported through a private Temporal
empty-prefix compatibility value used only to derive existing zero-valued prefix
Evidence. It is not a `ListeningWindowStatistics`, must not escape through a new
public contract, and must not weaken the shared statistics invariant.

## Evolution Analytics and Evidence

Temporal owns a dedicated stateless, locale-neutral boundary conceptually named
`LongTermEvolutionAnalytics`. It consumes one `ListeningMemory`, explicit Previous
and Current boundaries, and the run's existing timezone and as-of context. It
emits one immutable aggregate conceptually named `LongTermEvolutionEvidence`.

The analysis date `D` is derived mechanically as the local calendar date of the
validated aware `as_of` instant in the validated `timezone_name`. The Memory
timezone must equal that timezone. Memory's `as_of` value is authoritative for the
loaded value; an explicitly supplied analysis `as_of` must identify the same
instant.

The Analytics boundary must validate that:

- Previous contains exactly 30 calendar dates;
- Current contains exactly 30 calendar dates;
- Previous end equals Current start;
- the windows are adjacent and do not overlap;
- Current ends at local date `D`;
- `D` is excluded from both windows.

It must accept sparse Memory and interpret missing snapshots within either explicit
window as gaps. It must not validate or claim repository-read coverage. It must not
reuse Sprint 3C prefix as Previous, apply Knowledge thresholds, rank candidates by
product significance, select facts, create user-visible text, or persist results.

Sprint 3C prefix remains the overlapping 29-day interval
`[D - 30 days, D - 1 day)`. Sprint 3E Previous remains the non-overlapping adjacent
interval `[D - 60 days, D - 30 days)`. One must never substitute for the other.

### Window Evidence

Each comparison window exposes immutable evidence conceptually named
`EvolutionWindowEvidence`, containing values equivalent to:

- start and exclusive end dates;
- recorded-day count;
- listening-day count;
- closed-day count;
- closed-listening-day count;
- gap dates;
- open-snapshot presence;
- total estimated listening duration;
- total attributable artist duration;
- structural-sufficiency status.

### Artist-share candidates

Temporal must expose every usable artist identity in the union of Previous and
Current. Each `ArtistShareEvolutionCandidate` contains evidence equivalent to:

- stable identity, optional Spotify ID, and deterministic display name;
- Previous and Current artist durations;
- Previous and Current total attributable artist durations;
- Previous and Current shares;
- signed share change and absolute share change.

An artist absent from one otherwise calculable window has duration and share zero
in that window. If either window has zero attributable artist duration, the
artist-share comparison is not calculable and no artist-share fact may be produced.
The identity-ordered union and its raw durations and totals remain available, but
each per-window share is undefined only when that window's own denominator is zero.
Signed and absolute share change are undefined when either per-window share is
undefined. A concrete Evidence contract must represent undefined ratios and
changes as optional values, not fabricate zero ratios.

Raw integer numerators and denominators are authoritative. Ratio values may also be
exposed as locale-neutral metadata, but product threshold decisions must use the
authoritative evidence. Temporal must order the complete candidate collection only
by stable identity. It must not sort by display name or change magnitude, apply the
15-percentage-point or 20-percent thresholds, or choose a winning artist.

### Concentration Evidence

`ConcentrationEvolutionEvidence` contains values equivalent to:

- Previous and Current top-five attributable durations;
- Previous and Current total attributable durations;
- Previous and Current concentration shares;
- signed share change and absolute share change;
- calculability status.

For each window, the numerator is the sum of the largest
`min(5, usable artist count)` artist durations. The denominator is total
attributable artist duration. With fewer than five usable artists and a positive
denominator, all usable artists form the numerator and concentration is `1.0`.
Each per-window concentration ratio is undefined only when that window's own
attributable denominator is zero. The comparison is non-calculable, and signed and
absolute changes are undefined, when either per-window ratio is undefined. Ratios
outside `[0, 1]`, negative evidence, and other mathematically invalid states must
fail explicitly; they must not be silently clamped.

### Breadth Evidence

Breadth is defined for each window as:

```text
artists per listening day
    = artist-day appearance count / listening-day count
```

`ArtistBreadthEvolutionEvidence` contains values equivalent to:

- Previous and Current artist-day appearance counts;
- Previous and Current listening-day counts;
- Previous and Current artists per listening day;
- signed change and absolute change;
- signed relative change and absolute relative change;
- calculability status.

Relative change is:

```text
(Current breadth - Previous breadth) / Previous breadth
```

Zero listening days makes that window's breadth ratio undefined. Previous breadth
equal to zero in a window with a defined breadth ratio makes relative change
undefined and breadth evolution non-calculable. Previous breadth greater than zero
and defined Current breadth equal to zero remains calculable with relative change
`-1`. Temporal applies no `0.5` or `20%` product threshold.

### Aggregate comparison Evidence

`LongTermEvolutionEvidence` contains the run's timezone name and as-of context,
Previous and Current window Evidence, comparison structural sufficiency,
artist-share calculability, all identity-ordered artist-share candidates,
concentration Evidence, and breadth Evidence.

Comparison structural sufficiency must not be redefined by the calculability of an
individual concept.

## Attribution and artist identity

Sprint 3E defines total attributable artist duration as:

```text
the sum of durations assigned to every usable primary-artist identity
```

Artist share is artist attributable duration divided by total attributable artist
duration. Top-five concentration is the sum of the five largest attributable
primary-artist durations, or all usable durations when fewer than five artists
exist, divided by total attributable artist duration.

Existing primary-artist attribution is unchanged:

- one playback contributes to exactly one primary artist;
- multi-artist duration is neither split nor duplicated;
- canonical credit selection is unchanged;
- blank artist values and the MusicMind unknown-artist sentinel are excluded;
- excluded artist duration remains in total estimated playback duration but does
  not enter the attributable denominator.

This denominator applies only to Sprint 3E artist-share and concentration
evolution. Sprint 3C state artist share and concentration retain their existing
total-listening-duration denominator.

Cross-window artist identity is:

```text
Spotify-backed: ("spotify", spotify_artist_id)
Legacy:         ("legacy", stripped_casefold_name)
```

Legacy normalization applies `strip()` followed by `casefold()`. Spotify identity
uses the existing non-blank Spotify ID after surrounding-whitespace cleaning. The
same Spotify ID matches across windows. Different Spotify IDs remain distinct even
when display names match. Legacy identities match only by their normalized legacy
name. Spotify-backed and legacy identities must not bridge automatically,
including when their display names match. Blank and unknown artist values are
excluded even when another identity field is present.

Legacy same-name collision is an accepted compatibility limitation. Spotify and
legacy records for the same real-world artist intentionally remain distinct when
the evidence does not provide a shared stable identifier.

Display names remain opaque source text after the existing artist-name usability
and surrounding-whitespace cleaning. When an identity appears in Current, its
Current deterministic source display name wins. Otherwise its Previous
deterministic source display name is used. Existing deterministic within-window
selection remains the lexicographically smallest usable source name after
surrounding-whitespace cleaning. The selected display string must then be preserved
without additional normalization, synthesis, or translation, and it must not be
used as the primary identity tie-breaker.

## Sufficiency, calculability, and product significance

Each evolution window is structurally sufficient only when both conditions hold:

```text
listening-day count >= 10
closed-listening-day count >= 7
```

Comparison Evidence is structurally sufficient only when Previous and Current
independently satisfy both conditions. One sufficient window cannot substitute for
the other. Gaps remain gaps, and recorded zero-listening days remain recorded
zero-listening days.

Structural sufficiency is owned by Temporal and describes the shape of available
evidence. Concept calculability is also owned by Temporal and describes whether a
metric can be calculated mathematically. Product significance is owned by
Knowledge and describes whether calculable, structurally sufficient evidence meets
product thresholds.

Zero attributable duration is a calculability issue for artist share and
concentration. Previous breadth equal to zero is a calculability issue for relative
breadth evolution. Neither condition changes comparison structural sufficiency.
Existing Sprint 3C concept-specific `evidence_sufficient` behavior remains
unchanged.

If comparison Evidence is structurally insufficient,
`LongTermEvolutionKnowledgeEngine` must return an empty fact tuple. Thresholds must
not be reduced because a window is sparse.

## Exact arithmetic and display rounding

Knowledge owns these significance thresholds:

```text
Artist share:
    absolute share change >= 0.15
    and max(Previous share, Current share) >= 0.20

Concentration:
    absolute share change >= 0.15

Breadth:
    absolute artists-per-listening-day change >= 0.5
    and absolute relative change >= 0.20
```

Both artist-share conditions and both breadth conditions are required. Zero change
never qualifies. At most one artist-share fact may be emitted.

Qualification must use original integer numerators and denominators before display
rounding. Implementations must use exact rational comparison, integer cross
multiplication, or an equivalent deterministic method. Formatted percentages,
one-decimal display values, rounded floats, and binary floating-point equality must
not decide threshold boundaries.

Knowledge must choose the artist-share fact in this order:

1. filter every candidate by both product thresholds;
2. select the greatest exact absolute change among qualifying candidates;
3. resolve an exact tie by stable artist identity ascending.

A larger unqualified candidate must not block a smaller qualifying candidate.

Artists-per-listening-day display values must use exactly one decimal place and
decimal round-half-up semantics. The display value must be derived
deterministically from the exact ratio using an explicit rounding mode equivalent
to `ROUND_HALF_UP`, never from an already rounded binary float.

Required examples are:

```text
1    -> 1.0
1.64 -> 1.6
1.65 -> 1.7
2.25 -> 2.3
```

This display rule applies to canonical English breadth facts and `zh-CN`
localization. Display rounding occurs only after qualification and must not affect
eligibility.

## Knowledge contracts

Knowledge owns a separate locale-neutral interpreter conceptually named
`LongTermEvolutionKnowledgeEngine`. It consumes completed
`LongTermEvolutionEvidence` and returns an immutable tuple of `KnowledgeFact`
values. Existing `LongTermKnowledgeEngine` remains dedicated to Sprint 3C state
and prefix novelty.

The fixed concept output order is:

1. artist attributable-duration-share evolution;
2. artist breadth evolution;
3. listening concentration evolution.

If comparison Evidence is structurally insufficient, no evolution facts are
returned. If no calculable concept meets its thresholds, the result is also empty.

### Semantic vocabulary

Sprint 3E adds these concept-level categories and stable values:

```text
ARTIST_DURATION_SHARE_EVOLUTION = "artist_duration_share_evolution"
ARTIST_BREADTH_EVOLUTION = "artist_breadth_evolution"
LISTENING_CONCENTRATION_EVOLUTION = "listening_concentration_evolution"
```

It adds one source and stable value:

```text
LONG_TERM_EVOLUTION_EVIDENCE = "long_term_evolution_evidence"
```

It adds six direction-specific `FactMessageKey` values following ADR-0011's
dotted-value convention:

```text
LONG_TERM_ARTIST_SHARE_EVOLUTION_INCREASED
    = "long_term.artist_share_evolution.increased"
LONG_TERM_ARTIST_SHARE_EVOLUTION_DECREASED
    = "long_term.artist_share_evolution.decreased"
LONG_TERM_ARTIST_BREADTH_EVOLUTION_INCREASED
    = "long_term.artist_breadth_evolution.increased"
LONG_TERM_ARTIST_BREADTH_EVOLUTION_DECREASED
    = "long_term.artist_breadth_evolution.decreased"
LONG_TERM_LISTENING_CONCENTRATION_EVOLUTION_INCREASED
    = "long_term.listening_concentration_evolution.increased"
LONG_TERM_LISTENING_CONCENTRATION_EVOLUTION_DECREASED
    = "long_term.listening_concentration_evolution.decreased"
```

Direction-level `FactCategory` values must not be created, and Sprint 3C state
categories must not be reused for evolution. All evolution facts use
`FactTimeHorizon.LONG_TERM`, `InsightType.BEHAVIOR`, and
`FactSource.LONG_TERM_EVOLUTION_EVIDENCE`.

Importance is fixed as:

- artist share: `HIGH`;
- breadth: `MEDIUM`;
- concentration: `MEDIUM`.

This follows the existing long-term product convention in which an artist-specific
observation has higher importance than aggregate breadth and concentration. The
explicit category priority remains authoritative before importance in Narrative.

These enum additions are semantic runtime vocabulary only. They are not persisted
in Memory or the database. `KnowledgeFact` remains immutable, and `message_key`
remains excluded from value equality.

### Fact identity and date range

Artist-share evolution uses:

```text
subject_key: spotify:{spotify_artist_id}
             or legacy:{normalized_name}
concept_key: artist_duration_share
```

Breadth uses:

```text
subject_key: listening:all_artists
concept_key: artist_breadth
```

Concentration uses:

```text
subject_key: listening:all_artists
concept_key: listening_concentration
```

Controlled direction metadata is `increase` or `decrease`, derived from signed
Evidence. Evolution facts use the existing Knowledge date-range representation of
two ISO-8601 date strings. The first value is Previous start and the second is
Current exclusive end. Sprint 3E must not introduce a new date-range type.

### Minimal metadata

Evolution facts must not copy complete Temporal Evidence. Full gap lists,
structural audit counts, unrelated concept Evidence, and duplicated window state
remain in Temporal.

In the current `KnowledgeFact` contract, the `subject_key` and `concept_key`
identities defined above remain metadata. In addition to those identity keys, every
evolution fact contains only these common metadata keys:

```text
direction
previous_start_date
previous_end_date
current_start_date
current_end_date
previous_value
current_value
```

The four metadata date values are also ISO-8601 `YYYY-MM-DD` strings and preserve
half-open semantics. Artist-share and concentration values are raw ratios in
`[0, 1]`; breadth values are non-negative raw artists-per-listening-day values.
They must not be preformatted localized strings.

Artist-share facts additionally contain exactly these concept-specific keys:

```text
artist_identity
artist_name
previous_duration_ms
current_duration_ms
previous_attributed_duration_ms
current_attributed_duration_ms
signed_share_change
absolute_share_change
```

Concentration facts additionally contain exactly these concept-specific keys:

```text
previous_top_five_duration_ms
current_top_five_duration_ms
previous_attributed_duration_ms
current_attributed_duration_ms
signed_share_change
absolute_share_change
```

Breadth facts additionally contain exactly these concept-specific keys:

```text
previous_artist_day_count
current_artist_day_count
previous_listening_day_count
current_listening_day_count
signed_change
absolute_change
relative_change
absolute_relative_change
```

Metadata remains immutable and participates in normal `KnowledgeFact` value
equality. It must contain no gap dates, complete window Evidence, unrelated concept
Evidence, locale, or localized prose.

### Canonical English facts

Knowledge owns canonical English facts without importing Localization. Artist names
are interpolated unchanged. Percentages follow the existing deterministic canonical
English convention and render ratios as whole percentages with no decimal places.
Breadth values use exactly one decimal place with the round-half-up rule defined
above.

In the description shapes below, `previous_percentage` and `current_percentage`
are formatted derivatives of the raw `previous_value` and `current_value` metadata
ratios. They are notation for canonical Knowledge-owned formatting, not additional
metadata keys.

Artist-share titles are `Artist share increased` and `Artist share decreased`.
Their exact description shapes are:

```text
The share of attributable artist listening for {artist_name} increased from
{previous_percentage} in the previous 30-day period to {current_percentage} in the
current 30-day period.

The share of attributable artist listening for {artist_name} decreased from
{previous_percentage} in the previous 30-day period to {current_percentage} in the
current 30-day period.
```

Breadth titles are `Artist breadth increased` and `Artist breadth decreased`.
Their exact description shapes are:

```text
Artists per listening day increased from {previous_value} in the previous 30-day
period to {current_value} in the current 30-day period.

Artists per listening day decreased from {previous_value} in the previous 30-day
period to {current_value} in the current 30-day period.
```

Concentration titles are `Listening concentration increased` and
`Listening concentration decreased`. Their exact description shapes are:

```text
The top five artists' share of attributable artist listening increased from
{previous_percentage} in the previous 30-day period to {current_percentage} in the
current 30-day period.

The top five artists' share of attributable artist listening decreased from
{previous_percentage} in the previous 30-day period to {current_percentage} in the
current 30-day period.
```

Wording must remain factual and neutral. It must not claim preference, personality,
emotion, motivation, loyalty, cause, or prediction.

## Narrative priority, suppression, and deduplication

Evolution facts and Sprint 3C state facts remain separate collections until the
Narrative boundary. `Over Time` remains limited to two observations and no new
report section is added.

Narrative must process facts in this order:

1. select `Recently` using existing behavior;
2. remove explicit Recent/Long-term semantic duplicates;
3. suppress matching long-term state facts;
4. apply explicit long-term category priority;
5. apply stable tie-breakers;
6. retain at most two `Over Time` observations.

The long-term category priority is:

1. `ARTIST_DURATION_SHARE_EVOLUTION`;
2. `ARTIST_BREADTH_EVOLUTION`;
3. `LISTENING_CONCENTRATION_EVOLUTION`;
4. `ARTIST_CONSISTENCY`;
5. `ARTIST_BREADTH`;
6. `LISTENING_CONCENTRATION`;
7. other long-term categories.

Within this priority, deterministic ties are resolved by:

1. importance descending;
2. stable category value;
3. `subject_key`, using an empty value when absent;
4. `concept_key`, using an empty value when absent;
5. canonical title;
6. canonical description.

Ordering must not depend on input order, enum declaration order, accidental lexical
ordering alone, or Presentation behavior.

### Explicit state suppression

Before the two-observation limit:

- `ARTIST_BREADTH_EVOLUTION` suppresses `ARTIST_BREADTH` only when subject and
  concept identify the same all-artists breadth concept;
- `LISTENING_CONCENTRATION_EVOLUTION` suppresses
  `LISTENING_CONCENTRATION` only when subject and concept identify the same
  all-artists concentration concept.

Artist duration-share evolution must not suppress `ARTIST_CONSISTENCY`; artist
share change and repeated top-artist appearance are distinct concepts. Sprint 3E
must not introduce generic evolution-suppresses-state behavior. Missing semantic
identity causes conservative retention, followed by deterministic ordering.

### Explicit cross-horizon relationship

ADR-0010's existing exact cross-horizon deduplication by valid, equal
`subject_key` and `concept_key` remains unchanged. Recent selection continues to
deduplicate by valid `subject_key` alone. Existing Long-term same-horizon exact-pair
deduplication also remains unchanged. This ADR explicitly refines Long-term
ordering by adding the tie-breakers defined above; it does not otherwise redefine
same-horizon semantic identity.

Sprint 3E adds exactly one additional cross-concept Recent/Long-term semantic
relationship. Under this added relationship, a Recent fact and a Long-term fact are
duplicates only when all conditions hold:

- Recent category is `ARTIST_EMERGENCE`;
- Long-term category is `ARTIST_DURATION_SHARE_EVOLUTION`;
- both `subject_key` values are valid and equal;
- Long-term direction metadata is `increase`.

When the relationship holds, Narrative retains `Recently` and removes the
Long-term share increase before `Over Time` selection. Equal `concept_key` values
are not required because the categories define this explicit product relationship.

Long-term share decreases, different artists, artist consistency, unrelated
same-artist concepts, breadth, concentration, and facts sharing only display text
must not be deduplicated by this added relationship. Missing subject identity or
missing or invalid direction prevents this added relationship and causes
conservative retention unless the facts independently satisfy the existing exact
identity rule.

## Localization and formatting

ADR-0011 remains authoritative: English uses canonical `KnowledgeFact` title and
description, while Simplified Chinese is generated after Narrative selection from
`FactMessageKey` plus immutable metadata. Knowledge and Narrative remain
locale-neutral.

The Chinese catalog must add these six direction-specific title and description
templates:

### Artist share increased

```text
Title: 艺人占比上升
Description: 与前一个30天周期相比，{artist_name}在可归因艺人听歌时长中的占比
             从{previous_value}上升到{current_value}。
```

### Artist share decreased

```text
Title: 艺人占比下降
Description: 与前一个30天周期相比，{artist_name}在可归因艺人听歌时长中的占比
             从{previous_value}下降到{current_value}。
```

### Artist breadth increased

```text
Title: 艺人广度增加
Description: 与前一个30天周期相比，平均每个听歌日涉及的艺人数
             从{previous_value}增加到{current_value}。
```

### Artist breadth decreased

```text
Title: 艺人广度减少
Description: 与前一个30天周期相比，平均每个听歌日涉及的艺人数
             从{previous_value}减少到{current_value}。
```

### Listening concentration increased

```text
Title: 听歌集中度上升
Description: 与前一个30天周期相比，排名前五的艺人在可归因艺人听歌时长中的占比
             从{previous_value}上升到{current_value}。
```

### Listening concentration decreased

```text
Title: 听歌集中度下降
Description: 与前一个30天周期相比，排名前五的艺人在可归因艺人听歌时长中的占比
             从{previous_value}下降到{current_value}。
```

The line breaks and indentation above are documentation formatting only; rendered
descriptions are continuous sentences and contain no literal code markers.

Artist names remain opaque and unchanged. Chinese percentages contain no space
before `%`. Localization owns a formatter conceptually named
`format_artists_per_listening_day`. It must accept only finite, non-negative
numeric values, reject booleans, negative values, `NaN`, and positive or negative
infinity, and always render one decimal place using the exact round-half-up rule in
this ADR. Its `en-US` and `zh-CN` output must be deterministic and follow the
respective locale's existing punctuation conventions. It applies no product
threshold.

Ratio formatters must receive values in `[0, 1]`. Whole percentages and
percentage-point changes must not be passed as ratios. Relative breadth change is
threshold and audit metadata and is not displayed in the main sentence.

Catalog validation must cover every new message key and its exact required
metadata. Missing templates or metadata must fail explicitly. Machine translation
and silent Chinese-to-English fallback remain prohibited. No new UI heading is
added, and Presentation remains selection-free.

## Runtime fact flow and AI isolation

Runtime must retain four semantically separate collections:

```text
ai_facts
recent_facts
long_term_state_facts
long_term_evolution_facts
```

`ai_facts` remains exactly the concatenation of daily, daily-trend, and daily-
insight facts. Runtime retains the four collections separately and concatenates
them only when constructing Narrative's existing single fact-sequence input so
Narrative can select Recent and long-term deterministic observations.

`ReportGenerator` receives only `ai_facts`. Recent facts, Sprint 3C state facts, and
Sprint 3E evolution facts must remain absent from the AI Daily Brief, AI prompts,
and provider requests. This isolation is owned by the runtime call boundary; no
filtering belongs in `ReportGenerator` or provider adapters.

Runtime verification must capture the `ReportGenerator` input and prove that
Recent, Sprint 3C state, and Sprint 3E evolution facts are absent.

Sprint 3E must not change `DailyBrief`, AI prompt files, `ReportGenerator` behavior,
provider interfaces, provider adapters, or Spotify OAuth.

## Persistence and unchanged contracts

Evolution Evidence and evolution Knowledge facts are rebuildable runtime results.
Sprint 3E adds no:

- database schema or migration;
- `DailyMemorySnapshot` or `ListeningMemory` schema change;
- Memory serializer change;
- snapshot-version change from version 1;
- evolution-result or display-history persistence;
- automatic historical backfill;
- locale persistence.

Repository half-open range semantics, sparse gaps, Recent Evidence semantics,
Sprint 3C public state Evidence, Sprint 3C total-listening-duration denominators,
Sprint 3C prefix novelty, `KnowledgeFact` immutability, `message_key` equality
behavior, `DailyBrief`, AI prompts, `ReportGenerator`, provider contracts and
adapters, and OAuth remain unchanged.

Evolution appears only in the existing deterministic `Over Time` section. Sprint
3E does not add charts, dashboards, natural-month reports, scheduled reports,
genre, track, song, or album evolution, recommendations, predictions, Web MVP,
AI Report v2, or historical backfill.

## Data flow and ownership boundaries

The target runtime flow is:

```text
Runtime resolves D and timezone
    |
    |-- one Memory read [D - 60, D + 1)
    v
Sparse ListeningMemory
    |
    |-- Recent Temporal Analytics
    |-- Sprint 3C LongTermListeningAnalytics
    |-- Sprint 3E LongTermEvolutionAnalytics
    v
Locale-neutral Temporal Evidence
    |
    |-- Recent Knowledge
    |-- Sprint 3C LongTermKnowledgeEngine
    |-- Sprint 3E LongTermEvolutionKnowledgeEngine
    v
Canonical KnowledgeFact collections
    |
    v
Narrative selection / deduplication / suppression / limits
    |
    v
Presentation and post-Narrative Localization

Daily + trend + insight KnowledgeFact values only
    |
    v
ReportGenerator -> language-neutral provider -> DailyBrief
```

Memory stores evidence. Temporal aggregates and compares evidence. Knowledge
applies product meaning and exact thresholds. Narrative owns deterministic product
selection. Presentation and Localization render already selected facts. The AI
path remains a separate runtime projection of daily, trend, and insight facts.

## Consequences

### Positive consequences

- State, prefix novelty, and adjacent-window evolution remain semantically
  separate.
- One bounded sparse Memory read serves all temporal paths.
- Shared window statistics eliminate duplicate aggregation semantics without
  changing Sprint 3C public behavior.
- Attributable-duration denominators and primary-artist identity are explicit.
- Structural sufficiency, mathematical calculability, and product significance have
  distinct owners.
- Exact comparisons make threshold boundaries deterministic.
- Narrative retains priority, suppression, deduplication, and observation-limit
  ownership.
- Localization and AI scope remain within the boundaries established by ADR-0011.
- Future Web MVP or AI Report v2 work can consume clear locale-neutral contracts
  without being implied by Sprint 3E.
- No data migration, persistence, or historical rebuild is required.

### Costs and limitations

- Runtime reads up to 61 calendar slots instead of 31.
- Temporal gains shared statistics and several comparison Evidence contracts.
- Knowledge gains three categories, one source, and six message keys.
- Narrative gains explicit state-suppression and cross-horizon relationship maps.
- Exact rational threshold comparison and decimal half-up formatting are more
  complex than rounded float comparison.
- Legacy normalized-name identities can collide.
- Spotify-backed and legacy records for the same real artist intentionally remain
  separate without a shared stable identifier.
- Sprint 3C and Sprint 3E ratios intentionally use different denominators.

## Alternatives considered

### Multiple repository reads

Rejected because all temporal paths can consume one bounded sparse Memory value.
Multiple reads would add orchestration and consistency risk without adding evidence.

### Comparing Sprint 3C state Evidence inside Knowledge

Rejected because Knowledge would need to reconstruct raw comparison mathematics
from product-oriented state Evidence and would blur the Temporal-to-Knowledge
boundary.

### Folding evolution into the Sprint 3C state and prefix engine

Rejected because current state, prefix novelty, and adjacent-window evolution have
different windows, sufficiency rules, denominators, and product meanings.

### Reusing Sprint 3C prefix as Previous

Rejected because the prefix is an overlapping 29-day interval within Current, not
the adjacent non-overlapping 30-day Previous interval.

### Applying product thresholds in Temporal

Rejected because Temporal owns evidence shape and calculability while Knowledge
owns product significance.

### Temporal selecting the largest raw artist candidate

Rejected because qualification must occur before winner selection. A larger raw
but unqualified change must not hide a smaller qualifying change.

### Sorting Temporal candidates by change magnitude

Rejected because candidate order is an evidence invariant. Temporal must expose the
complete union in stable identity order; Knowledge owns significance ranking.

### Using rounded display values or binary floats for qualification

Rejected because exact threshold boundaries would depend on formatting or binary
representation rather than authoritative numerators and denominators.

### Redefining Sprint 3C ratios with the attributable denominator

Rejected because it would silently change released state facts. Sprint 3C retains
its total-listening-duration denominator.

### Bridging Spotify and legacy identities by display name

Rejected because name equality is ambiguous and could merge distinct artists.

### Reusing Sprint 3C state categories

Rejected because state and evolution are different semantic concepts and require
independent Narrative priority and suppression.

### Direction-level categories

Rejected because direction is controlled fact metadata and a message-key branch,
not a separate product concept.

### One generic localization template with arbitrary direction text

Rejected because six explicit message keys keep catalog validation and wording
branches closed and deterministic.

### Copying full Temporal Evidence into fact metadata

Rejected because Knowledge metadata would become a duplicate Evidence store and
would couple Localization and Narrative to unrelated gap and sufficiency details.

### Deduplicating all facts about one artist

Rejected because emergence, share change, and consistency are distinct product
concepts even when they refer to the same artist.

### Requiring concept-key equality for emergence/share-increase deduplication

Rejected because the explicit categories define the intended cross-horizon
relationship and legitimately use different concept keys.

### Filtering evolution facts inside ReportGenerator or providers

Rejected because runtime owns AI input scope. Downstream filtering would weaken the
call contract and add temporal policy to language-generation or transport layers.

### Persisting evolution, changing schemas, or automatically backfilling

Rejected because evolution results are deterministic and rebuildable from existing
Memory evidence. Persistence would add migration and lifecycle complexity without
being required by Sprint 3E.

## Compatibility and migration

Sprint 3E is additive at the Temporal Evidence, Knowledge vocabulary, Narrative,
Localization, and runtime orchestration boundaries. The broader Memory read is a
runtime range change, not a repository contract or stored-data change.

Existing stored snapshots remain valid at snapshot version 1. Existing sparse
history becomes usable as it accumulates or through the already explicit bounded
Memory rebuild workflow; Sprint 3E does not initiate a rebuild. No schema migration,
serializer migration, result migration, or display-history migration is required.

Existing Sprint 3C public Evidence and fact behavior remain compatible. Existing
Recent behavior remains compatible. English canonical fact fields and
`KnowledgeFact.message_key` equality behavior remain compatible with ADR-0011.
The deterministic report keeps its existing headings and limits. The AI Daily Brief
keeps its existing fact scope and schema.

## Acceptance invariants

1. Runtime performs exactly one half-open `[D - 60 days, D + 1 day)` longitudinal
   Memory range read.
2. Previous and Current each contain exactly 30 calendar dates and are adjacent.
3. The open local day `D` is excluded from both evolution windows.
4. Missing snapshots inside explicit windows remain gaps, not zero-listening days.
5. Evolution Analytics does not claim to verify repository-read coverage.
6. Sprint 3C prefix remains `[D - 30 days, D - 1 day)`.
7. Sprint 3C public state Evidence and denominators remain unchanged.
8. Temporal exposes all artist candidates ordered by stable identity.
9. Knowledge filters for qualification before selecting the greatest qualifying
   artist change and resolves exact ties by identity.
10. Sprint 3E artist share and concentration use attributable artist duration.
11. Blank and unknown artists do not enter the attributable denominator.
12. Spotify-backed and legacy identities do not bridge automatically.
13. Previous and Current independently require at least 10 listening days and 7
    closed-listening days.
14. Structural sufficiency, concept calculability, and product significance remain
    distinct.
15. Exact pre-rounding numerator and denominator Evidence determines threshold
    qualification and tie-breaking.
16. Breadth display uses decimal `ROUND_HALF_UP` to exactly one decimal place.
17. Previous breadth equal to zero makes breadth evolution non-calculable.
18. Evolution facts contain minimal concept-specific metadata, not complete
    Temporal Evidence.
19. Narrative applies evolution priority and suppression before its two-item
    `Over Time` limit.
20. Breadth and concentration evolution suppress only matching state facts.
21. Artist-share evolution does not automatically suppress artist consistency.
22. Recent emergence suppresses the same-subject long-term share increase without
    requiring `concept_key` equality.
23. Chinese localization occurs only after Narrative selection.
24. `ReportGenerator` receives only `ai_facts`.
25. Sprint 3E changes no database schema, Memory schema, snapshot version,
    serializer, persistence, backfill, `DailyBrief`, `ReportGenerator` behavior,
    AI prompt, provider, OAuth, or locale persistence contract.

## Relationship to ADR-0010 and ADR-0011

ADR-0010 remains authoritative for Memory as stored evidence rather than stored
conclusions, the Memory-to-Temporal-to-Knowledge-to-Narrative direction, Sprint 3C
long-term state analysis, prefix novelty semantics, the existing `Over Time`
presentation limit except where this ADR defines explicit priority and suppression,
and exclusion of long-term facts from the current AI report.

ADR-0012 refines ADR-0010 by adding adjacent-window evolution, the broader single-
read runtime range, shared Temporal window statistics, separate evolution Evidence
and Knowledge interpretation, and explicit Narrative evolution priority, state
suppression, and Recent/Long-term semantic deduplication.

ADR-0011 remains authoritative for `SupportedLocale` ownership,
`FactMessageKey` ownership in Knowledge, canonical English facts, post-Narrative
Chinese localization, strict catalog validation, opaque dynamic-name preservation,
and the unchanged AI scope. This ADR adds six semantic message keys and their
formatting requirements without changing those ownership decisions.
