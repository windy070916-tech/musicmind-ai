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

After raw synchronization succeeds, runtime explicitly captures the previous local
date so it has closed-day evidence, then `MemoryEngine.capture_current_day()`
refreshes the current configured local date. Repeated capture replaces the same
date/timezone/version row.

Range reads are side-effect free. They return only stored snapshots, leave missing
dates visible as gaps, and never call Analytics. Historical dates are generated
only through an explicit bounded `rebuild_range()` operation.

Malformed or unsupported snapshots are invalid derived cache data. They may be
replaced through capture or rebuilding without changing raw playback history.

## Explicit historical rebuild

Historical backfill is never automatic. An operator or maintenance entry point must
construct the normal `MemoryEngine` and call its existing bounded API explicitly:

```python
memory = memory_engine.rebuild_range(start_date, end_date)
```

The dates use half-open `[start_date, end_date)` semantics. Raw `play_history`
remains authoritative; missing snapshots remain gaps until such an explicit rebuild.
Rebuilding cannot make locally stored playback complete, and Memory does not
guarantee complete Spotify account history.

## Temporal consumption

Temporal Analytics consumes a caller-bounded `ListeningMemory` as read-only
evidence. It compares explicit half-open local-date windows contained within that
Memory and preserves absent snapshot dates as gaps in its output.

The Daily runtime performs one longitudinal range read over `[D-60,D+1)`. The same
sparse `ListeningMemory` serves the existing Recent current/comparison windows,
Sprint 3C's state and prefix, and Sprint 3E's adjacent Previous and Current windows.
The range read returns only stored snapshots and does not fill gaps. Its declared
bounds support containment validation, but do not prove which repository call
created the value or why a date is absent; runtime integration owns verification of
the one-call boundary.

This does not give Memory interpretation responsibilities. Memory does not choose
Recent, state, prefix, Previous, or Current periods; calculate continuity, state, or
evolution; or decide whether evidence is meaningful. It also does not call Temporal
Analytics: the application loads the required range and passes it downstream.
Temporal analysis has no capture, rebuild, upsert, or other Memory lifecycle side
effects.

## Scope

Memory stores Analytics snapshots; it does not calculate rankings, interpret
preferences, compose Narrative, render output, or call Spotify or an LLM.

Long-term observations describe only locally recorded evidence. Daily artist
duration uses the existing primary-artist attribution rule preserved in each
`DailyListeningProfile`.

It currently contains no favorite, streak, rediscovery, session, or preference
classification. It represents listening recorded by MusicMind and is not a
guarantee of complete Spotify account history.

Sprint 3E adds no Memory fields, requested-range provenance, database schema,
snapshot-version, serializer, persistence, automatic backfill, or rebuild behavior.
Existing stored snapshots remain compatible.
