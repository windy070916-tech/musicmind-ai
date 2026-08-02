# ADR-0010: Long-term Listening Analytics

- Status: Accepted
- Release: MusicMind v0.7.0 Sprint 3C

## Context

MusicMind already stores versioned daily `DailyListeningProfile` evidence in
Listening Memory and uses Temporal Analytics to calculate recent longitudinal
evidence. Sprint 3C needs deterministic long-term observations without defining a
user's identity, personality, permanent taste, motivation, or emotional state.

## Decision

Long-term calculations live in the existing `music_ai.temporal` domain as an
independent `LongTermListeningAnalytics` implementation with an independent
`LongTermListeningEvidence` contract. The existing recent implementation and
`RecentListeningEvidence` remain unchanged.

The application supplies an explicit half-open local-date window. Production uses
30 calendar days ending at the current local date, excluding the current open day.
Analytics calculates artist consistency, top-one and top-five listening
concentration, and artist breadth, including current and prefix-window metrics for
deterministic transition evaluation.

`LongTermKnowledgeEngine` consumes completed evidence only, applies product
thresholds, and creates the existing `KnowledgeFact` with
`FactTimeHorizon.LONG_TERM`. `NarrativeEngine` selects at most two facts into an
immutable `LongTermListeningThread`, and Presentation renders them under `Over
Time`. Cross-horizon deduplication requires both stable subject and concept keys.

Memory remains evidence storage only. Its schema, snapshot contract, serializer,
repository contract, and version do not change. Missing snapshots remain gaps and
historical rebuilding remains explicit and bounded. Runtime finalizes the previous
local date before refreshing the current date.

Recent and long-term facts do not enter the Sprint 3C AI report path. Long-term
language describes locally recorded behavior and follows existing primary-artist
attribution; it does not claim complete Spotify history or infer identity.

## Consequences

- Recent and long-term analysis share date, timezone, identity, and evidence
  principles while evolving through separate public contracts.
- Novelty needs no persisted display history because Knowledge compares current and
  prefix evidence thresholds.
- Sparse or insufficient history correctly produces silence.
- The deterministic Narrative path, not the LLM, controls long-term product wording.
- Historical data appears only after ordinary accumulation or an explicit bounded
  `MemoryEngine.rebuild_range()` operation.

## Rejected alternatives

- Raw Analytics would mix SQLite aggregation with Memory-based longitudinal work.
- Memory calculation or result persistence would mix evidence lifecycle with
  algorithm output.
- A new top-level profile domain would duplicate existing Temporal responsibilities.
- Knowledge or Narrative calculation would violate the forward-only evidence flow.
