# Narrative Layer

Narrative is MusicMind's deterministic composition boundary between structured
Analytics and Knowledge results and presentation renderers.

## Responsibility

Narrative organizes existing information into a stable product-facing contract. It
does not calculate listening statistics, interpret behavior, generate AI text, or
apply output formatting.

## Inputs

- `DailyListeningProfile` supplies deterministic metrics and ranked listening data.
- `KnowledgeFact` collections supply already-interpreted facts and insights.

Narrative treats both inputs as read-only. `NarrativeEngine` snapshots fact
collections and separates recent and long-term facts from ordinary highlights.

## Output

`DailyNarrative` is the immutable, renderer-facing contract containing a headline,
an optional `listening_profile`, ordered knowledge highlights, an optional
`recent_thread`, an optional `long_term_thread`, and immutable extension metadata.
The explicit profile name distinguishes the complete analytics result from the
smaller existing `ListeningSummary` contract.

`RecentListeningThread` is a presentation-independent collection containing at most
two `FactTimeHorizon.RECENT` observations. `NarrativeEngine` selects it
deterministically:

1. Artist emergence precedes artist continuity.
2. Importance and stable fact attributes break ties.
3. Facts with the same non-empty `metadata["subject_key"]` are deduplicated, keeping
   the first selected observation.
4. Selection stops after two observations.
5. No qualifying recent fact produces `recent_thread=None`.

This is product composition, not interpretation. Narrative does not recalculate
shares, inspect Memory, apply evidence thresholds, or keep presentation history.
Its novelty behavior comes from the transition evidence already interpreted by
Knowledge.

Ordinary facts remain in `highlights` and retain their deterministic importance
ordering. Recent and long-term facts are excluded for their dedicated threads.

`LongTermListeningThread` contains at most two `FactTimeHorizon.LONG_TERM`
observations. Sprint 3C state facts and Sprint 3E evolution facts remain separate in
runtime and join only in Narrative's fact-sequence input. Narrative processes them
in this order:

1. Select `Recently` with the existing behavior.
2. Remove explicit Recent/long-term semantic duplicates.
3. Suppress matching Sprint 3C state facts.
4. Apply explicit long-term category priority and stable tie-breakers.
5. Retain at most two `Over Time` observations.

The long-term category priority is artist-share evolution, artist-breadth evolution,
listening-concentration evolution, artist consistency, artist breadth, listening
concentration, then other long-term categories. Ties resolve by importance
descending, stable category value, `subject_key`, `concept_key`, canonical title,
and canonical description. Input order, enum declaration order, and Presentation do
not affect the result.

Before the two-item limit, breadth evolution suppresses breadth state only when both
facts have the same valid all-artists subject and breadth concept. Concentration
evolution applies the equivalent matching-concept rule. Artist-share evolution does
not suppress artist consistency. Missing semantic identity causes conservative
retention.

Existing exact cross-horizon and same-horizon deduplication by equal, non-empty
`subject_key` plus `concept_key` remains. Sprint 3E adds one explicit cross-concept
relationship: selected Recent `ARTIST_EMERGENCE` suppresses long-term
`ARTIST_DURATION_SHARE_EVOLUTION` only for the same valid subject when evolution
direction is `increase`; concept-key equality is not required. Share decreases,
different artists, unrelated concepts, missing identity, and missing or invalid
direction remain. No qualifying long-term fact produces `long_term_thread=None`.

After Narrative, one locale-neutral visible-report composition applies final display
limits and produces both the deterministic `MusicMind Daily` content and its
semantic Visible Content Manifest. When a thread exists, Presentation prints a
`Recently` section in Narrative order. The optional `Over Time` section follows and
also preserves Narrative order. Presentation does not rank Signals or determine AI
relationships.

Narrative remains locale-neutral. It continues sorting and selecting canonical
`KnowledgeFact` values, including its existing title/description tie-breakers. The
deterministic renderer receives the resolved locale only after composition and
localizes selected fact descriptions at render time. Consequently `zh-CN` and
`en-US` use the same observations, order, limits, and cross-horizon deduplication.
Locale is not stored in `DailyNarrative`, either thread contract, or Narrative
metadata.

The separate AI interpretation path projects qualified Knowledge evidence into
Signals, then uses the deterministic Planner and Visible Content Manifest to suppress
pure within-run restatement. Narrative does not import Signal or Planner policy and
does not assign Primary, Secondary, or Watch roles. Its visible Recent observations
remain the existing open-inclusive selection; the separate closed Recent facts used
for Signal qualification never enter Narrative.
