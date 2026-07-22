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
collections and orders highlights deterministically using their declared importance
and stable fact attributes.

## Output

`DailyNarrative` is the immutable, renderer-facing contract containing a
headline, an optional `listening_profile`, ordered knowledge highlights, and
immutable extension metadata. The explicit profile name distinguishes the complete
analytics result from the smaller existing `ListeningSummary` contract. Future
terminal, Markdown, web, or mobile renderers can consume this contract without
reaching back into Analytics, Knowledge, repositories, or AI providers.

MusicMind now renders this contract as the deterministic `MusicMind Daily` before
calling the separate AI report path. The renderer formats only the existing profile
and eligible fact descriptions; it does not access Analytics, persistence, Spotify,
or an LLM.

The AI Daily Brief remains an independent optional interpretation path. Its legacy
Knowledge facts are based on `ListeningSummary`, while profile artist rankings use
primary-artist attribution, so the two outputs may temporarily differ for
collaborative tracks.
