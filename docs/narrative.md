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
collections and separates recent facts from ordinary highlights.

## Output

`DailyNarrative` is the immutable, renderer-facing contract containing a headline,
an optional `listening_profile`, ordered knowledge highlights, an optional
`recent_thread`, and immutable extension metadata. The explicit profile name
distinguishes the complete analytics result from the smaller existing
`ListeningSummary` contract.

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

Non-recent facts remain in `highlights` and retain their deterministic importance
ordering. Recent facts are excluded from generic highlights so the same observation
is not rendered twice.

MusicMind now renders this contract as the deterministic `MusicMind Daily` before
calling the separate AI report path. The renderer formats only the existing profile
and selected fact descriptions. When a thread exists, Presentation prints a
`Recently` section in the order supplied by Narrative; it does not filter, rank, or
deduplicate those observations.

The AI Daily Brief remains an independent optional interpretation path. Its legacy
Knowledge facts are based on `ListeningSummary`, while profile artist rankings use
primary-artist attribution, so the two outputs may temporarily differ for
collaborative tracks.
