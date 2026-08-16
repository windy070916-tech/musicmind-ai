# ADR-0013: Listening Interpretation Layer

- Status: Accepted
- Date: 2026-08-14
- Decision owners: MusicMind maintainers
- Target release: MusicMind Sprint 4A
- Related ADRs: ADR-0010, ADR-0011, ADR-0012
- Supersedes: None

## Context

MusicMind currently produces two separate daily outputs:

1. a deterministic listening report; and
2. a MusicMind AI report.

The deterministic report already explains what happened through listening duration,
playback count, distinct tracks, top artists, top tracks, daily comparisons, Recent
observations, Sprint 3C long-term state, and Sprint 3E long-term evolution.

The current AI path receives only:

```text
daily_facts + trend_facts + insight_facts
```

Each fact is flattened to text equivalent to:

```text
[category] title: description
```

The AI does not receive Recent facts, Sprint 3C state facts, Sprint 3E evolution
facts, the listening profile, genre evidence, structured fact metadata, supporting
day counts, evidence maturity, windows, gaps, Narrative selections, or information
about deterministic content already visible to the user.

The current provider response requires six fields:

```text
greeting
listening_summary
trend
insight
recommendation
closing
```

Because every field is required, the AI report tends toward a second summary of
visible deterministic facts and may require filler when no additional
interpretation is justified.

Sprint 4A changes the product role of MusicMind AI to:

```text
Listening Interpreter + Curator
```

with a small amount of Music Companion personality expressed through restrained,
natural language. It is not a second statistical report, a generic summarizer, a
mandatory advice engine, or a system that rewrites visible facts.

The governing product principle is:

```text
Deterministic MusicMind tells WHAT happened.
MusicMind AI explains WHAT MAY MATTER and WHY.
```

An already-visible value may be repeated only when it supports a genuinely new
interpretation. Pure restatement must be prevented deterministically before the
provider is invoked rather than left only to prompt wording.

## Decision drivers

- Observable measurements and qualification must remain deterministic and
  testable.
- The LLM must not inspect raw listening history or independently discover facts.
- Existing Knowledge qualification must remain the authoritative factual truth;
  Sprint 4A must not create a parallel truth system.
- AI-oriented interpretation needs a distinct typed domain rather than additional
  user-visible fact categories or arbitrary metadata conventions.
- Relationships, evidence maturity, role eligibility, grouping, and priority must
  be determined before provider invocation.
- AI input must be materially smaller than the available deterministic evidence
  while retaining enough context for calibrated interpretation.
- The visible brief must be dynamic and must not force greeting, closing, advice,
  recommendation, emoji, or filler.
- Within-run repetition must be suppressed against the deterministic concepts
  actually shown to the user.
- Exact cross-run novelty semantics must remain deferred to Product Discovery
  Round 5.
- Contextual time patterns must use retained event timestamps honestly without
  claiming verified listening intervals or complete Spotify history.
- Sprint 4A must not require a Memory migration, database migration, automatic
  backfill, or new persistence lifecycle.
- Existing deterministic Narrative, Localization, Presentation, Recent, Sprint 3C,
  and Sprint 3E behavior must remain compatible.
- Provider adapters must remain transport-oriented and independent of Signal and
  product policy.

## Decision

Sprint 4A adopts:

```text
Knowledge Evidence Projection
    +
Deterministic Interpretation Planner
    +
Dynamic Typed AI Brief
```

Within this ADR, **Knowledge Evidence Projection** is the selected architecture
family and **Signal Projection** is its interpretation-domain responsibility. The
terms do not describe two independent qualification paths.

The end-to-end responsibility flow is:

```text
Raw listening data
    -> deterministic Analytics
    -> Knowledge qualification
    -> structured interpretation Signals
    -> deterministic interpretation planning
    -> LLM prose realization
    -> validated dynamic AI brief
```

### Responsibility boundaries

Ownership is frozen as follows.

**Analytics** measures observable data. It owns source-window aggregation,
arithmetic, identities required for its measurements, and raw evidence production.
It does not create AI interpretations.

**Knowledge** decides whether a canonical factual observation is valid. Existing
Knowledge qualification, thresholds, fact identities, and evidence meanings remain
authoritative.

**Signal Projection** decides whether one or more already-valid Knowledge
observations support an interpretation candidate. It may form compatible
cross-horizon compositions, bounded lifecycle states, or deterministic composite
Signal semantics. It does not independently recalculate whether a Knowledge
observation is true.

**Interpretation Planner** alone assigns narrative relationships between
already-qualified Signals. It groups interpretation candidates, ranks them,
suppresses within-run restatement, and assigns Primary, Secondary, and Watch
roles. It does not qualify composite Signal semantics or recalculate Knowledge
observations.

**The LLM** realizes planner-approved meaning as natural-language prose. It does
not decide truth, qualification, maturity, relationships, sufficiency, role, or
priority.

**The response validator** validates the typed response against the approved plan.
**The renderer** presents the validated response. It owns visible layout, not
interpretation selection or Signal relationships.

### Signal domain

A Signal is a separate interpretation-oriented domain object.

It is neither an ordinary user-visible `KnowledgeFact` nor an independent parallel
analytics system. It is a deterministic projection over qualified Knowledge
evidence.

A Signal may represent:

- one qualified factual observation;
- a compatible cross-horizon composition;
- a bounded lifecycle state;
- deterministic composite semantics formed from compatible Knowledge evidence; or
- contextual evidence suitable for AI interpretation.

Knowledge remains authoritative for canonical factual qualification. Signal
Projection is authoritative only for interpretation eligibility and composition.

Signal Projection qualifies composite Signal semantics from compatible Knowledge
evidence; the Interpretation Planner alone assigns narrative relationships between
already-qualified Signals.

Signal identity must be stable within a deterministic run and its interpretation
plan so request and response references can be validated. This ADR does not define
a persistent cross-run Signal identity or novelty key.

### Evidence contract

The conceptual Signal contract contains only the structured meaning required for
interpretation planning and controlled provider projection:

- stable Signal identity;
- Signal type;
- approved state or direction;
- stable subject identity when applicable;
- opaque display subject label when applicable;
- observation horizon;
- compact window references;
- deterministic evidence maturity;
- selected supporting dimensions;
- a small set of reference values useful for interpretation;
- approved claim scope;
- required caveats;
- references to contributing Knowledge evidence; and
- role eligibility.

Exact Python type and file names are not fixed by this ADR.

Evidence is separated into three layers.

#### Qualification-only evidence

Qualification-only evidence includes exact threshold arithmetic, complete
numerators and denominators, full candidate sets, rejected candidates,
deterministic tie-break information, and complete raw statistics. It remains
inside deterministic code and is not automatically sent to the provider.

#### LLM-useful evidence

LLM-useful evidence includes the approved state or direction, subject, horizon,
maturity, the small set of support dimensions material to that maturity, selected
reference values, planner-approved narrative relationship, required caveats, and
claim scope.

#### Audit and debug evidence

Audit and debug evidence includes complete provenance, internal calculation
identifiers, exact boundaries, rejected-relationship reasons, and internal ordering
information. It remains available to deterministic tests and diagnostics but is
not provider input by default.

The provider receives a deliberate typed projection of selected Signals, not a
dump of an internal Signal, Analytics Evidence, Temporal model, or
`KnowledgeFact` collection.

### Evidence strength

Evidence strength is deterministic product maturity, not statistical model
confidence. It must not reuse `KnowledgeFact.confidence = 1.0` as statistical
certainty.

Sprint 4A uses three maturity states:

```text
preliminary
supported
strong
```

Their meanings are:

- **preliminary**: repeated evidence exists, but it is not mature enough for a
  Primary or Secondary interpretation; it may qualify for Watch;
- **supported**: evidence is sufficiently established for a Primary or Secondary
  interpretation; and
- **strong**: evidence has stronger support, potentially through more repeated
  observations, stronger support dimensions, or compatible evidence across
  horizons.

Maturity is derived deterministically from observable support. Each Signal family
may require its own qualification rules. This ADR does not establish a single
universal numeric threshold table.

The provider receives the maturity category and only the small set of support
dimensions required to understand it. The provider cannot upgrade or downgrade
maturity.

### Core Signal semantics

Sprint 4A architecture supports seven core Signal families plus Evidence Strength
as a shared property:

1. Artist Preference Formation;
2. Temporary Spike vs Sustained Growth;
3. Exploration Intensity;
4. Core vs Exploration Balance;
5. Listening Time-of-Day Pattern;
6. Artist × Time-of-Day Affinity;
7. Time Pattern Evolution; and
8. Evidence Strength as a shared property.

Exact numeric qualification thresholds remain Signal-family domain rules rather
than universal architecture constants.

#### Artist Preference Formation

Preference formation uses the bounded lifecycle vocabulary:

```text
locally emerging
    -> repeated presence
    -> sustained growth
    -> established core presence
```

These states describe locally observed listening behavior. They do not prove
first-ever discovery, permanent preference, psychological attachment, or complete
user history.

Compatible evidence may include Recent continuity and emergence, long-term artist
consistency, appearance days, current-window artist share, artist-share evolution,
closed-day historical top-artist and stable-favorite observations, and related
deterministic facts.

Current open-day Daily facts may be used as visible report context where
appropriate, but they must not contribute to qualification, lifecycle advancement,
or evidence maturity of long-horizon Artist Preference Formation Signals. In
particular, current-day top artist, current-day stable-favorite behavior, and
current open-day profile evidence cannot independently move an artist through the
bounded lifecycle states. Long-horizon lifecycle qualification uses closed
historical evidence under the frozen Sprint 4A window semantics. Legitimate Daily-
derived evidence from closed historical days remains eligible after canonical
Knowledge qualification.

Cross-horizon composition belongs to Signal Projection. The provider receives the
qualified bounded lifecycle interpretation rather than a loose collection of facts
from which it could invent a lifecycle.

User-facing wording may describe an artist beginning to appear in recent listening,
repeatedly entering rotation, continuing to grow, or becoming a relatively stable
recent core artist. It must not claim that the listener discovered the artist for
the first time unless a future source can genuinely prove that statement.

#### Temporary Spike vs Sustained Growth

Analytics and Knowledge continue to establish daily movement, Recent behavior,
long-term state, long-term evolution, and support-day information.

Signal Projection deterministically distinguishes bounded interpretations such as:

- short-window movement without longer-horizon support;
- repeated movement supported across compatible horizons;
- conflicting horizons; and
- insufficiently mature movement.

The provider does not perform this classification. A single-day top-artist change
cannot become a preference-shift claim merely because it forms a plausible story.

#### Exploration Intensity

Sprint 4A exploration semantics are conservative and locally bounded. They may
describe:

- an artist mix becoming broader or narrower;
- changes in artist distribution;
- changes in distinct-artist structure;
- changes in one-time versus repeated artist appearances;
- bounded track diversity when explicitly supported; and
- an artist appearing in the current comparison window but not the explicit prior
  comparison window.

These observations do not automatically mean genuinely new artists, first-ever
exposure, or globally unfamiliar music. Window-relative evidence must use
window-relative language. Incomplete local history must not silently acquire
complete user-history semantics.

#### Core vs Exploration Balance

Core-versus-exploration composite Signal semantics are qualified deterministically
before provider invocation. Independent breadth and concentration observations
must not be sent to the LLM with an invitation to invent their relationship.

For example:

```text
artist breadth increases
    +
top-five concentration increases
```

may support:

```text
wider outer artist mix while listening remains concentrated around a core
```

only when both observations independently qualify, their windows are compatible,
their directions match the registered composite qualification rule, and their
evidence is sufficient.

Analytics calculates the components. Knowledge qualifies them. Signal Projection
qualifies one composite Signal. This is not a Planner relationship between two
already-qualified Signals. The Planner may rank the qualified composite Signal and
may relate it to other qualified Signals only through its finite narrative
relationship vocabulary. The LLM only phrases the approved plan.

### Interpretation Planner

Sprint 4A introduces a deterministic Interpretation Planner separate from the
existing Narrative engine.

Narrative continues to own deterministic user-visible report selection. It is not
extended into an AI planning engine.

The Planner owns:

- narrative relationship validation between already-qualified Signals;
- deterministic grouping;
- interpretation-candidate ranking;
- Primary, Secondary, and Watch role assignment;
- within-run duplicate suppression; and
- stable deterministic tie-breaking.

The Planner relationship vocabulary is finite:

```text
reinforcement
contrast
contextual support
unrelated
```

No generic graph framework is introduced. Signals may be connected only when they
reinforce the same interpretation, form an explicitly supported contrast, or add
evidence-backed context. Unrelated Signals are not combined merely to make a more
compelling story.

These are narrative relationships between already-qualified Signals. They are
distinct from the deterministic composition of one Signal from compatible
Knowledge evidence, which remains owned by Signal Projection.

Role eligibility is:

- Primary: `supported` or `strong` only;
- Secondary: `supported` or `strong` only; and
- Watch: `preliminary` only.

After the Evidence Gate is satisfied, interpretation value takes priority over
maturity alone. Planner priority is:

1. cross-Signal relationships that produce genuinely new understanding;
2. contextual hidden patterns difficult to infer from the visible report;
3. lifecycle or sustained-behavior interpretations; and
4. single-observation interpretations.

Within a comparable interpretation-value tier, the Planner uses evidence maturity,
support dimensions, and deterministic stable tie-breaking. This ADR does not set
numeric ranking weights or the exact same-tier family tie-break order.

Valid plan shapes are:

```text
no items
Watch only
Primary
Primary + Secondary
Primary + Watch
Primary + Secondary + Watch
```

Invalid plan shapes are:

```text
Secondary only
Secondary + Watch without Primary
```

A plan contains at most one Primary, one Secondary, and one Watch. Secondary is
semantically subordinate to Primary. Watch may exist independently when only
preliminary evidence is available.

### Visible Content Manifest

Within-run anti-repetition uses a locale-neutral Visible Content Manifest.

The manifest must represent deterministic concepts that are actually going to be
shown to the user. It must not be constructed from Narrative alone if final
presentation adds, filters, or limits other deterministic content.

A locale-neutral deterministic report-composition boundary owns the manifest. It
combines Narrative output with the profile and other deterministic report content
after all display selection and limits are known but before localization and
rendering. The same composition is the source for final deterministic Presentation,
and runtime passes its manifest to the Planner. Narrative alone does not own the
manifest, and rendered Presentation text is not used to construct it.

The manifest covers, where present:

- the Today summary;
- top artists;
- top tracks;
- ordinary Highlights;
- Recent observations;
- Sprint 3C long-term state;
- Sprint 3E long-term evolution; and
- other deterministic profile or report content included in final presentation.

It contains only the minimal locale-neutral semantic references needed for
duplicate detection, such as concept, subject, direction, category, or equivalent
identifiers. It is not rendered Chinese or English Markdown.

The Planner uses the manifest to remove interpretations that would only restate
visible content. A visible value may still be supplied as evidence when it is
necessary to explain a genuinely new interpretation.

This manifest addresses within-run duplication only. It is not a cross-run report
history or novelty store.

### Contextual Listening / Time-of-Day

Sprint 4A contextual listening uses dedicated read-only analytics over retained raw
SQLite play history.

The database is accessible only to contextual Analytics. Signal Projection, the
Planner, the AI Report Generator, and providers must never query the database
directly.

Sprint 4A does not extend Memory v1, create contextual snapshots, change the Memory
serializer, add a database migration, or require automatic historical backfill.

#### Contextual windows

Let `D` be the current local calendar date in the configured MusicMind timezone.
Contextual comparison uses:

```text
Previous: [D - 60 days, D - 30 days)
Current:  [D - 30 days, D)
```

Both windows contain exactly 30 local calendar dates. The open local day `D` is
excluded from contextual listening patterns, preference-formation long-term
Signals, time-pattern evolution, and related long-horizon Sprint 4A Signals. The
ordinary Daily Report may continue to use the current day.

Current open-day Daily facts and profile evidence may provide visible report
context, but they cannot qualify, advance, or increase the evidence maturity of a
long-horizon Artist Preference Formation Signal. That lifecycle uses closed
historical evidence within the frozen windows.

Sprint 4A adds no 7-day or 14-day contextual horizon.

#### Local-clock segments

Every retained playback event belongs to exactly one half-open six-hour segment in
the configured timezone:

```text
00:00–06:00
06:00–12:00
12:00–18:00
18:00–24:00
```

Conceptual user-facing labels may be localized as overnight, morning, afternoon,
and evening, or equivalent Chinese terms. These are local-clock segments, not
inferred sleep, lifestyle, mood, or activity phases.

Timezone conversion uses the configured MusicMind timezone. Existing DST
correctness expectations continue to apply.

#### Measurement semantics

Observed playback-event count is the only core Sprint 4A time-of-day measure.

The system may describe more observed playback events occurring in one segment. It
must not translate that into a claim about most listening time occurring in that
segment.

Raw records provide one event timestamp, not a verified listening interval.
Spotify imports may lack actual listened duration, and catalog track duration does
not prove how much was heard or which clock segment contained that duration.

An event belongs to the segment containing its single recorded timestamp and is
not split across boundaries. Estimated duration is not used for Sprint 4A
contextual time claims.

#### Raw-history completeness

Contextual analytics operate on observed local listening history, not guaranteed
complete Spotify history. Current recently-played ingestion does not prove complete
lifetime or continuous coverage.

Memory coverage is not evidence of raw-event completeness. Missing Memory dates
are not contextual raw-history gaps. Unknown or limited completeness remains a
deterministic caveat in relevant Signals even when that caveat does not need to be
repeated mechanically in every sentence.

The claim scope must prevent absolute preference and habitual claims. A bounded
statement about disproportionate occurrence among recently observed playback
events is permitted when qualified; claims that a user always listens to or
prefers an artist at a particular time are not.

#### Artist × Time-of-Day Affinity

Artist affinity requires comparison between the artist's segment distribution and
the user's overall playback-event segment distribution. Raw artist counts alone do
not qualify affinity.

Canonical evidence includes:

- artist time-segment distribution;
- user overall time-segment distribution;
- relative overrepresentation;
- repeated occurrence across multiple distinct listening days; and
- sufficient artist and segment support.

Analytics calculates these distributions. Knowledge qualifies the factual
observation. Signal Projection decides whether it supports an interpretation. The
LLM does not determine statistical or behavioral sufficiency.

Exact affinity thresholds remain Signal-family domain rules.

#### Time Pattern Evolution

Time-pattern evolution compares the same adjacent Previous and Current contextual
windows. Contextual Analytics uses raw event timestamps directly.

Raw-history evidence sufficiency remains separate from Memory sufficiency. Memory
snapshot coverage cannot establish raw-event coverage, and Memory gaps cannot be
substituted for contextual-history evidence.

### AI request contract

The AI Report Generator consumes a strict provider-neutral typed interpretation
request serialized to JSON. It no longer accepts raw `KnowledgeFact` collections
or repository-facing values as its evidence contract.

The request contains only:

- selected interpretation plan items;
- Signals referenced by those plan items;
- compact Visible Content Manifest references where required;
- target locale;
- deterministic evidence maturity;
- selected support dimensions;
- a small set of reference values;
- approved claim scopes;
- required caveats; and
- global prohibited-claim policy.

The request does not contain:

- raw playback rows;
- repositories or database handles;
- Memory snapshots;
- complete Temporal models;
- complete `KnowledgeFact` dumps;
- rejected Signals or rejected candidates;
- arbitrary Analytics metadata; or
- rendered deterministic report text.

Only evidence approved by deterministic layers reaches the provider.

### Dynamic AI response contract

Sprint 4A replaces the fixed six-field `DailyBrief` architecture with a typed
dynamic response conceptually shaped as:

```text
items: [
    {
        plan_item_id,
        role,
        text
    }
]
```

Exact implementation type names are not fixed here.

Structural invariants are:

- zero to three returned items;
- at most one Primary;
- at most one Secondary;
- at most one Watch;
- every item references a known planner-approved item;
- returned role equals the planned role;
- plan references are unique;
- prose is non-empty and bounded;
- provider output is data, not raw Markdown;
- roles absent from the plan require no filler; and
- the provider cannot create a role not supplied by the Planner.

The response type can represent zero items for the internal no-Signal outcome, but
runtime does not invoke the provider for an empty plan. A provider response to an
invoked non-empty plan therefore contains one to three items and must realize every
planned item.

If the provider omits an item present in the plan, the response is invalid. The
provider does not gain selection authority by silently dropping planned content.

The user-visible result is one `MusicMind AI` area containing at most three short
paragraphs. Primary appears as the main paragraph. Secondary, when present, is a
second short paragraph. Watch, when present, may be a final short observation
about what is worth continuing to observe; it is not advice or prediction.

Primary, Secondary, and Watch need not be literal visible headings. Exact sentence
and character limits remain implementation parameters.

The brief has no mandatory greeting, closing, advice, recommendation, emoji, or
filler.

### AI epistemic boundary

The direct-paraphrase-only boundary of the current AI report is too restrictive for
the interpreter role. Sprint 4A permits the LLM to realize:

- synthesis of planner-approved Signals;
- explanation of planner-approved relationships;
- evidence-backed comparisons;
- calibrated tentative language based on deterministic maturity; and
- explanations that evidence is not mature enough for a stronger conclusion.

Calibrated concepts may include:

```text
currently looks more like
appears to be becoming more stable
is not yet strong enough to conclude
```

The following remain prohibited:

- discovering new factual patterns;
- changing evidence maturity;
- unsupported causal claims;
- mood or psychological-state inference;
- personality, stress, motivation, or life-circumstance inference;
- genre guessing from names;
- first-ever discovery claims without proof;
- permanent-preference claims;
- future predictions; and
- unapproved cross-Signal relationships.

The provider contract combines global prohibited claims, per-plan-item approved
claim scope, deterministic maturity, and explicit caveats. The LLM decides
language, not truth or sufficiency.

### Semantic validation

Sprint 4A requires proportionate structural and reference validation, not a
second-model factuality system.

Validation covers:

- strict JSON structure;
- allowed top-level fields;
- known plan references;
- valid and matching role references;
- duplicate prevention;
- non-empty bounded prose;
- optional-role rules; and
- opaque entity preservation where reasonably testable.

A secondary LLM validator is not required. Deterministic tests must prove that
unsupported Signals, relationships, roles, rejected candidates, and raw data do
not reach the provider.

### Localization

Deterministic localization remains:

```text
canonical facts
    -> locale-neutral deterministic selection
    -> code-controlled localization
```

Signal and plan contracts remain locale-neutral. The request names the target
locale, and the provider generates prose directly in that locale. Artist, track,
album, and future source-backed genre names remain opaque source values. Code owns
any local AI headings, status labels, and rendering structure.

Sprint 4A does not introduce an English-generation-then-translation subsystem. The
localized deterministic Markdown report is never sent to the provider.

### Failure and degradation

No meaningful Signal and AI-generation failure are different states.

If no Signal qualifies for Primary, Secondary, or Watch:

- the provider is not called;
- no artificial AI interpretation is generated;
- deterministic report delivery continues; and
- Presentation displays a lightweight deterministic user-visible status that no new
  interpretable Signal qualified.

If only a Watch Signal qualifies, a Watch-only plan is valid and the provider may
be called.

If provider transport fails, JSON is invalid, response structure is invalid, or
planned content is missing:

- deterministic report delivery is preserved;
- the AI response is rejected;
- the runtime exposes a controlled nonfatal AI-generation failure state;
- Presentation displays a lightweight user-visible AI-generation failure status;
  and
- no deterministic-summary fallback recreates the old duplication problem.

No-Signal and AI-generation failure states remain distinguishable from the user's
perspective. Neither state may silently produce an absent AI area that makes the
two outcomes indistinguishable. Exact localized status wording remains an
implementation and Localization parameter. Provider fallback is not required for
Sprint 4A.

### Dependency direction

The conceptual dependency direction is:

```text
Spotify
    -> Database
        -> Daily Analytics
            -> Memory
                -> Temporal Analytics

Database
    -> Contextual Timestamp Analytics

Daily Analytics ---------+
Temporal Analytics ------+--> Knowledge
Contextual Analytics ----+

Knowledge
    +-> Narrative
    |     -> deterministic visible selection
    |     -> locale-neutral report composition / Visible Content Manifest
    |     -> Localization / Presentation
    |
    +-> Signal Projection
          -> Interpretation Planner
              -> AI Report Generator
                  -> Provider
                      -> Response Validator
                          -> validated dynamic AI brief
                              -> AI rendering
```

Locale-neutral Visible Content Manifest semantics also flow from final
deterministic content toward the Planner.

Required dependency constraints are:

- Signal may depend on Knowledge contracts but not directly on Database, Spotify,
  Memory, Localization, Presentation, or Provider;
- the Planner may depend on Signal contracts and neutral visible-content contracts
  but must not query Analytics, Temporal history, repositories, or providers;
- the AI Report Generator consumes only the typed interpretation request and must
  not receive repositories, Memory, raw Temporal data, or raw `KnowledgeFact`
  collections;
- Provider adapters remain transport-oriented and contain no Signal, relationship,
  ranking, or product policy;
- the Response Validator may depend on the typed plan and response contracts but
  not on raw evidence, infrastructure, or provider product policy;
- Narrative remains independent of AI planning policy; and
- Presentation does not rank Signals or determine Signal relationships.

Static dependency tests must enforce these boundaries.

### Future extension points

#### Genre Intelligence

Genre Intelligence is not Sprint 4A Core implementation scope. Future source-backed
genre work follows:

```text
deterministic genre Analytics
    -> canonical Knowledge observations
    -> Signal Projection
    -> Interpretation Planner
    -> AI
```

Potential future families include Genre Shift, Genre Emergence, and Genre ×
Time-of-Day. The provider must never infer genre from artist or track names.

#### Saved Library Intelligence

Saved-library infrastructure exists but is inactive in normal runtime. Future
saved-library intelligence follows:

```text
saved-library deterministic Analytics
    -> Knowledge
    -> Signal Projection
    -> Interpretation Planner
    -> AI
```

Potential future families include Saved Music Shift, Save → Repeat, and Saved vs
Played. The LLM never inspects saved-track rows directly. Sprint 4A does not add
saved-library runtime synchronization.

### Novelty deferral

Cross-run novelty matters, but its exact behavior is intentionally deferred to
Product Discovery Round 5.

Sprint 4A implements only within-run duplicate suppression against the visible
deterministic report. Cross-run novelty is not a Sprint 4A acceptance criterion,
and Sprint 4A does not persist prior AI reports, prior interpretations, prior
Narrative selections, or semantic report history.

The future seam is:

```text
Qualified Signals
    -> optional future novelty / ranking policy
    -> Interpretation Planner
```

This ADR does not define a novelty database schema, serializer, retention period,
novelty key, user-identity model, migration strategy, prior-insight store, or
Boolean `novel` property. The Planner behaves deterministically when no future
novelty input is present.

## Consequences

### Positive

- MusicMind AI becomes an interpretation layer rather than a second deterministic
  report.
- Existing deterministic Knowledge remains authoritative.
- AI receives richer but smaller structured evidence.
- Signal qualification and maturity, Planner relationships, plan roles, and
  tie-breaking are independently testable.
- The LLM cannot determine evidence sufficiency or invent cross-Signal grouping.
- Within-run report duplication can be suppressed before provider invocation.
- The dynamic response produces no forced greeting, closing, advice, or filler.
- Contextual time patterns become possible without Memory or database migration.
- Deterministic report delivery can remain independent of AI availability.
- Future Signal families share one extension path through Knowledge, Signal
  Projection, and the Planner.
- Genre, saved-library, and Round 5 novelty work can extend the architecture without
  exposing raw data to the provider.

### Negative / Costs

- Signal Projection and Interpretation Planner add new domain boundaries and more
  stages to runtime orchestration.
- Projection contracts must validate existing category-specific Knowledge metadata
  before treating it as interpretation evidence.
- Signal-family qualification and composition rules require substantial
  deterministic test coverage.
- The locale-neutral Visible Content Manifest must accurately reflect final
  deterministic presentation, including content not selected by Narrative alone.
- Contextual Analytics relies on retained raw history whose completeness is not
  guaranteed.
- The current provider request, fixed `DailyBrief`, AI renderer, prompt, and related
  tests will require replacement during implementation.
- Distinct user-visible no-Signal and AI-generation failure statuses add explicit
  product and runtime states.
- Cross-run repetition remains unresolved until Product Discovery Round 5.

## Alternatives considered

### KnowledgeFact-Centric Interpretation

This alternative would make Sprint 4A Signals ordinary `KnowledgeFact` values and
extend existing Knowledge and Narrative behavior to cover AI interpretation.

It was rejected because it would push user-visible factual observations,
AI-specific interpretation eligibility, evidence maturity, claim policy, and
future novelty concerns into one broad model. It would encourage loosely typed
metadata conventions, risk overloading Narrative with a second selection purpose,
and couple future AI behavior too strongly to general Knowledge and Localization.

### Independent Parallel Signal Pipeline

This alternative would create separate Signal Analytics and qualification directly
from raw Analytics or Temporal Evidence, alongside existing Knowledge engines.

It was rejected because it would create a parallel truth system and duplicate
current qualification logic. KnowledgeFacts and AI Signals could drift in
identity, thresholds, window definitions, evidence sufficiency, and product
meaning. It also has the largest regression surface.

### Selected Evidence-Projection Architecture

Knowledge Evidence Projection plus a deterministic Planner is selected because it
reuses existing deterministic Knowledge truth while giving AI interpretation a
separate typed domain. It avoids parallel qualification, keeps Narrative focused,
grounds the LLM in approved meaning, supports contextual raw-event Analytics
without Memory migration, and leaves clean extension seams for Genre, Saved
Library, and deferred novelty behavior.

## Scope

### Sprint 4A MUST

Sprint 4A includes:

- a separate Signal domain projected from qualified Knowledge evidence;
- the seven frozen core Signal families plus the shared Evidence Strength property;
- bounded artist lifecycle and exploration semantics;
- exclusion of current open-day Daily facts and profile evidence from long-horizon
  preference qualification, lifecycle advancement, and evidence maturity;
- deterministic spike-versus-sustained classification;
- deterministic composite Signal semantics, including core-versus-exploration
  composition;
- read-only raw-history contextual Analytics;
- the frozen 30-day adjacent contextual windows;
- the four frozen local-clock segments;
- observed-event-count-only contextual claims;
- repeated-listening-day support for contextual patterns;
- artist-time affinity relative to the user's overall time distribution;
- deterministic evidence maturity;
- a separate deterministic Interpretation Planner;
- the finite Planner relationship vocabulary;
- Evidence Gate and interpretation-value priority rules;
- one-Primary, one-Secondary, one-Watch structural enforcement;
- the locale-neutral Visible Content Manifest;
- within-run duplicate suppression;
- a typed provider-neutral AI request;
- a typed dynamic AI response;
- structural and reference validation;
- target-locale AI prose with opaque entity preservation;
- a lightweight user-visible no-Signal status;
- a lightweight user-visible AI-generation failure status;
- nonfatal, user-visible distinction between those outcomes;
- static dependency enforcement; and
- compatibility coverage for Recent, Sprint 3C, and Sprint 3E.

### Optional / Stretch

Optional work may include richer deterministic audit diagnostics or additional
structural validation that does not introduce a second-model validator. Provider
fallback is optional only if it is independently trivial and does not move product
policy into provider adapters.

Optional work must not change the frozen evidence ownership, time measurement,
role, failure-isolation, or dependency boundaries.

### Future / Out of Scope

The following are outside Sprint 4A:

- cross-run AI novelty or history persistence;
- Genre Shift implementation;
- Genre Emergence implementation;
- Genre × Time-of-Day implementation;
- saved-library synchronization or intelligence;
- recommendation-engine or music-recommendation behavior;
- user accounts or a multi-user system;
- Memory v2;
- Memory snapshot schema or serializer changes;
- database migration;
- mandatory historical backfill;
- full Spotify-history ingestion redesign;
- recently-played pagination redesign;
- audio-feature pipelines;
- mood, energy, or valence analysis;
- nontrivial provider-fallback architecture;
- Rich CLI redesign;
- general UI redesign;
- persistence of interpretation plans;
- persistence of AI responses; and
- estimated-duration contextual time evidence.

## Testing and acceptance implications

Core acceptance uses deterministic fixtures and fake providers. Live provider calls
are not required.

### Deterministic Signal tests

Tests must cover:

- qualification for every Sprint 4A Signal family;
- deterministic maturity derivation;
- maturity independence from `KnowledgeFact.confidence`;
- bounded preference-formation lifecycle states;
- rejection of current open-day Daily facts and profile evidence as lifecycle
  qualification, advancement, or maturity evidence;
- rejection of first-ever claims based only on local history;
- short-window movement versus sustained behavior;
- conflicting horizons;
- bounded exploration semantics;
- window-relative appearance versus genuine newness;
- deterministic core-versus-exploration composition;
- separation of composite Signal qualification from Planner-level narrative
  relationships;
- rejection of incompatible composite qualification inputs; and
- stable deterministic ordering.

### Contextual Analytics tests

Tests must cover:

- local-timezone assignment;
- exact `00:00`, `06:00`, `12:00`, and `18:00` boundaries;
- DST transitions;
- exclusion of the current open day;
- event-count-only semantics;
- absence of estimated-duration occupancy claims;
- repeated listening-day support;
- conservative raw-history incompleteness handling;
- artist-time affinity relative to the user's overall event distribution;
- adjacent contextual-window comparison; and
- the prohibition on treating Memory gaps as raw-history completeness evidence.

### Planner tests

Tests must cover:

- Evidence Gate behavior;
- interpretation-value priority;
- the finite Planner relationship vocabulary;
- rejection of unsupported combinations;
- the one-Primary, one-Secondary, and one-Watch limits;
- rejection of Secondary without Primary;
- validity of Watch-only plans;
- within-run Visible Content Manifest deduplication;
- use of visible values only when needed as interpretation evidence;
- deterministic tie-breaking; and
- unchanged ranking behavior when no future novelty input exists.

### AI request and response tests

Tests must cover:

- exact typed serialization;
- inclusion of only selected and planned Signals;
- exclusion of raw playback rows, Memory snapshots, rejected Signals, and complete
  `KnowledgeFact` dumps;
- locale propagation;
- claim scope and caveats;
- optional-role and Watch-only behavior;
- rejection of unknown plan identifiers;
- rejection of duplicate roles or references;
- rejection of role mismatches;
- rejection of empty prose and invalid JSON; and
- the prohibition on raw provider Markdown.

### Runtime tests

Tests must cover:

- independent deterministic report delivery;
- no provider call when no Signal qualifies;
- a lightweight user-visible status when no Signal qualifies;
- AI access only to Planner-approved input;
- preservation of deterministic output after AI failure;
- a lightweight user-visible status when AI generation fails;
- user-visible distinction between no-Signal and AI-generation failure states;
- unchanged Recent, Sprint 3C, and Sprint 3E behavior; and
- consistent runtime timezone and `as_of` use.

### Static dependency tests

Tests must prove that:

- AI cannot import Database, Spotify, Memory, or Temporal infrastructure;
- Signal cannot import infrastructure, Localization, Presentation, or Provider;
- the Planner cannot import raw Analytics or repositories;
- Provider adapters cannot import Signal, Planner, Knowledge product policy, or
  ranking logic; and
- Presentation cannot own Signal ranking or relationships.

## Acceptance invariants

1. Knowledge remains the sole authority for canonical factual qualification.
2. Signal Projection qualifies interpretation candidates and composite Signal
   semantics from compatible Knowledge evidence without becoming a second
   Analytics or Knowledge engine.
3. The LLM receives no raw listening history, Memory snapshot, repository, raw
   Temporal model, rejected Signal, or complete `KnowledgeFact` collection.
4. Evidence maturity is one of `preliminary`, `supported`, or `strong` and is
   derived deterministically.
5. `KnowledgeFact.confidence` is not treated as statistical certainty.
6. Only `supported` or `strong` Signals may be Primary or Secondary.
7. Only `preliminary` Signals may be Watch.
8. No plan contains more than one item of each role.
9. Secondary never exists without Primary; Watch-only remains valid.
10. Planner-level narrative relationships are limited to reinforcement, contrast,
    contextual support, and unrelated.
11. The Planner alone assigns narrative relationships between already-qualified
    Signals and decides grouping, ranking, and roles; it does not qualify composite
    Signal semantics or recalculate Knowledge observations.
12. The Visible Content Manifest represents final deterministic concepts actually
    shown, is locale-neutral, and contains no rendered report text.
13. Pure within-run restatement is suppressed before provider invocation.
14. Contextual windows are `[D - 60 days, D - 30 days)` and
    `[D - 30 days, D)`, excluding the open local day `D`.
15. Contextual segments are the four half-open six-hour local-clock intervals.
16. Contextual claims use observed event count, not estimated duration or inferred
    listening occupancy.
17. Artist-time affinity is relative to the user's overall event-time distribution
    and requires repeated listening-day support.
18. Memory coverage is not treated as raw-history completeness evidence.
19. AI response items reference Planner-approved identifiers and roles exactly.
20. The user-visible AI area has no required greeting, closing, advice,
    recommendation, emoji, or filler.
21. No-Signal and AI-generation failure outcomes each produce a distinct,
    lightweight user-visible status and remain nonfatal to deterministic report
    delivery.
22. Deterministic localization remains post-selection and code-controlled.
23. Cross-run novelty remains absent when the optional future policy is not
    present.
24. Sprint 4A changes no database schema, Memory version, Memory serializer, or
    historical-backfill lifecycle.
25. Current open-day Daily facts and profile evidence may remain visible report
    context but do not qualify, advance, or increase the maturity of long-horizon
    Artist Preference Formation Signals.

## Compatibility

ADR-0010 remains authoritative for Memory as stored evidence rather than stored
conclusions and for the Memory-to-Temporal-to-Knowledge direction. Sprint 4A does
not alter Memory snapshot version 1 or existing long-term state semantics.

ADR-0010's exclusion of long-term facts from the then-current AI report is refined
for Sprint 4A: long-term Knowledge observations may contribute only through
qualified Signal Projection and the Planner, never through direct fact dumping.

ADR-0011 remains authoritative for supported locale ownership, canonical English
facts, opaque source-name preservation, deterministic post-Narrative localization,
and provider-neutral transport. This ADR replaces the fixed six-field AI brief and
its mandatory-section product shape; it does not change deterministic localization.
The prior canonical fact-line AI input is replaced by the typed interpretation
request.

ADR-0012 remains authoritative for the `[D - 60 days, D + 1 day)` Memory read,
Recent windows, Sprint 3C state and prefix, Sprint 3E adjacent-window evolution,
identity, denominators, thresholds, Narrative priority, and deterministic fact
localization. Sprint 4A reuses the adjacent 30-day calendar geometry for contextual
Analytics but does not treat Memory evidence or gaps as raw-event completeness.
ADR-0012's requirement that `ReportGenerator` receive only `ai_facts` is refined:
the Sprint 4A AI Report Generator receives only the typed interpretation request,
and Recent, state, or evolution evidence can reach it only through selected Signals
and a Planner-approved plan.

Existing Recent, Sprint 3C, Sprint 3E, deterministic Narrative, and deterministic
Presentation behavior remain compatible. The AI request and response contracts are
intentionally replaced during Sprint 4A implementation.

Sprint 4A requires:

```text
no database migration
no Memory version change
no mandatory backfill
no AI history persistence
no Narrative history persistence
```

## Unresolved implementation parameters

The following remain implementation or Signal-family domain-rule parameters:

- exact numeric qualification thresholds for each Signal;
- exact support counts that map each Signal family to `preliminary`, `supported`,
  or `strong`;
- exact artist-time affinity cutoff;
- exact same-tier tie-break order among otherwise equivalent Signal families;
- exact provider prose length limits;
- exact Python class, module, and file names;
- exact localized no-Signal and AI-generation failure status wording; and
- all future Round 5 novelty and history behavior.

These unresolved parameters do not reopen the frozen four time segments, adjacent
30-day windows, open-day exclusion, event-count-only semantics, three maturity
states, bounded lifecycle and exploration vocabulary, affinity baseline,
interpretation-value priority, role eligibility, plan shapes, Visible Content
Manifest behavior, or novelty deferral.

## References

- ADR-0010: Long-term Listening Analytics.
- ADR-0011: Runtime Locale Resolution and Deterministic Localization.
- ADR-0012: Long-term Listening Evolution.
- Sprint 4A Product Discovery decisions.
- Sprint 4A Architecture Discovery Pass A current-state report.
- Sprint 4A Architecture Discovery Pass B recommendation.
- Architecture Review of Pass B.
- Sprint 4A Signal Semantics Freeze.
