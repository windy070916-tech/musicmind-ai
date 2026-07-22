# Narrative Layer

Narrative is MusicMind's deterministic composition boundary between structured
Analytics and Knowledge results and future presentation renderers.

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

`DailyNarrative` is an immutable, presentation-independent object containing a
headline, an optional `listening_profile`, ordered knowledge highlights, and
immutable extension metadata. The explicit profile name distinguishes the complete
analytics result from the smaller existing `ListeningSummary` contract. Future
terminal, Markdown, web, or mobile renderers can consume this contract without
reaching back into Analytics, Knowledge, repositories, or AI providers.

Sprint 2C introduces this package additively. The existing `main.py`, Daily Brief,
Report Generator, LLM, and renderer execution path do not use Narrative yet.
