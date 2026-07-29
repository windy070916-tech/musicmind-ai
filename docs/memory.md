# Listening Memory

Listening Memory is MusicMind's deterministic, rebuildable history of daily
Analytics results. Raw `play_history` remains the canonical source of truth;
Memory snapshots are disposable derived data.

## Snapshot identity

Each immutable `DailyMemorySnapshot` is identified by:

- one explicit local-calendar date;
- one configured IANA timezone;
- one snapshot contract version.

The snapshot preserves the complete `DailyListeningProfile`, its exact UTC
`[start, end)` boundaries, generation time, and whether the local day had closed
when captured. The current snapshot version is explicit and persisted with every
record.

## Lifecycle

`MemoryEngine.capture_current_day()` refreshes only the current configured local
date after raw synchronization succeeds. Repeated capture replaces the same
date/timezone/version row.

Range reads are side-effect free. They return only stored snapshots, leave missing
dates visible as gaps, and never call Analytics. Historical dates are generated
only through an explicit bounded `rebuild_range()` operation.

Malformed or unsupported snapshots are invalid derived cache data. They may be
replaced through capture or rebuilding without changing raw playback history.

## Temporal consumption

Temporal Analytics consumes a caller-bounded `ListeningMemory` as read-only
evidence. It compares explicit half-open local-date windows contained within that
Memory and preserves absent snapshot dates as gaps in its output.

This does not give Memory interpretation responsibilities. Memory does not choose
recent or comparison periods, calculate continuity or emergence, or decide whether
evidence is meaningful. It also does not call Temporal Analytics: the application
loads the required range and passes it downstream. Temporal analysis has no capture,
rebuild, upsert, or other Memory lifecycle side effects.

## Scope

Memory stores Analytics snapshots; it does not calculate rankings, interpret
preferences, compose Narrative, render output, or call Spotify or an LLM.

It currently contains no favorite, streak, rediscovery, session, or preference
classification. It represents listening recorded by MusicMind and is not a
guarantee of complete Spotify account history.
