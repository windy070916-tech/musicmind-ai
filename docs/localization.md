# Runtime Localization

MusicMind supports exactly `zh-CN` and `en-US`. The application default is
`zh-CN`, and one resolved locale controls runtime copy, the deterministic report,
and the current AI Report for the complete process run.

## Selection

Use either CLI form:

```bash
python main.py --locale zh-CN
python main.py --locale en-US
```

Or configure one exact environment value:

```env
MUSICMIND_LOCALE=zh-CN
MUSICMIND_LOCALE=en-US
```

The precedence is CLI, environment, interactive terminal, then non-interactive
`zh-CN`. The terminal selector accepts `1` for Chinese, `2` for English, and empty
input for Chinese; it retries other answers. EOF selects Chinese. Non-TTY execution
does not read stdin.

Explicit values are trimmed but case-sensitive. Empty values and aliases such as
`zh`, `en`, `zh-cn`, or `EN-US` are invalid. Explicit invalid configuration fails
before Spotify authentication, network requests, or database initialization.

The entrypoint loads `.env` once, resolves locale once, validates catalogs, and then
loads the remaining settings. Renderers and ReportGenerator do not read environment
configuration or prompt independently.

## Contracts and catalogs

`SupportedLocale` is the validated runtime contract. UI catalogs contain identical
`UiMessageKey` sets for both locales. Chinese fact templates contain exactly one
entry for every `FactMessageKey`, including separate directional and zero-baseline
branches. `validate_localization_catalogs()` checks both contracts explicitly at
startup and in tests.

Missing translations are build/configuration errors. MusicMind does not machine
translate, skip an untranslatable fact, or silently fall back to English inside a
Chinese report.

Knowledge remains locale-neutral. Its `title` and `description` are canonical
English and are the `en-US` source of truth. Built-in facts carry a semantic message
key outside metadata. For `zh-CN`, the post-Narrative fact localizer validates the
key's required immutable metadata before using a controlled Chinese renderer.

Sprint 3E adds six direction-specific keys:

- `LONG_TERM_ARTIST_SHARE_EVOLUTION_INCREASED` and
  `LONG_TERM_ARTIST_SHARE_EVOLUTION_DECREASED`;
- `LONG_TERM_ARTIST_BREADTH_EVOLUTION_INCREASED` and
  `LONG_TERM_ARTIST_BREADTH_EVOLUTION_DECREASED`; and
- `LONG_TERM_LISTENING_CONCENTRATION_EVOLUTION_INCREASED` and
  `LONG_TERM_LISTENING_CONCENTRATION_EVOLUTION_DECREASED`.

The corresponding Chinese titles are `艺人占比上升/下降`, `艺人广度增加/减少`, and
`听歌集中度上升/下降`. Descriptions compare the previous 30-day period with the
current 30-day period, preserve opaque artist names unchanged, and use
`可归因艺人听歌时长` for artist share and top-five concentration. Direction is
selected by Knowledge's message key; Localization does not interpret a free-form
direction string or recalculate eligibility.

## Chinese formatting

Chinese numbers and units contain no separating spaces:

```text
1小时32分钟
12次
3首
20位艺术家
16个听歌日
70%
```

Playback events use `次`, songs/tracks use `首`, artist counts use `位`, and day
counts use `天`. Chinese sentences use Simplified Chinese punctuation, and multiple
display names use `、` where Presentation supplies a list separator. English keeps
the previous compact durations, singular/plural units, punctuation, and headings.

Artist, track, album, and Spotify-provided genre names are opaque dynamic values.
Their contents are interpolated unchanged. Only MusicMind's own unknown-artist
fallback is localized.

Evolution ratios are supplied as raw values in `[0,1]` and render as whole
percentages, with no space before `%` in Chinese. Artists-per-listening-day values
always render with exactly one decimal place using decimal `ROUND_HALF_UP`: `1`
becomes `1.0`, `1.65` becomes `1.7`, and `2.25` becomes `2.3`. The formatter accepts
only finite, non-negative numeric values and rejects booleans, negatives, `NaN`, and
infinity. Formatting applies no product threshold and never changes fact selection.

## Deterministic and AI boundaries

Narrative completes selection, ordering, limits, and deduplication before any fact
localization. The same `DailyNarrative` can therefore render in either locale without
changing its semantic contents.

Signal and Planner contracts remain locale-neutral. A typed provider request carries
the target locale plus only Planner-selected Signals, compact support, approved
claim scopes, caveats, and relevant semantic visible-content references. Memory,
Temporal Evidence, playback rows, SQLite data, rejected Signals, full KnowledgeFact
collections, and localized deterministic Markdown remain excluded. The provider
generates the planned short paragraphs directly in the target locale; code owns the
AI area heading and the distinct no-Signal and AI-generation-failure statuses.

AI language compliance is best-effort under the existing provider contract. A
structurally valid brief is accepted without language detection, retry, or automatic
translation.

## Persistence

Locale is runtime configuration and is never written to SQLite, playback history,
Memory, snapshots, Temporal Evidence, KnowledgeFact metadata, Signals, plans,
Narrative metadata, typed interpretation requests, or AI briefs. Adding localization
requires no database migration, snapshot-version change, Memory rebuild, or
historical-data rebuild.

Sprint 3E likewise adds no locale persistence, schema change, serializer change,
snapshot-version change, automatic backfill, or stored localized evolution result.
