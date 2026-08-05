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

## Deterministic and AI boundaries

Narrative completes selection, ordering, limits, and deduplication before any fact
localization. The same `DailyNarrative` can therefore render in either locale without
changing its semantic contents.

The AI path continues receiving canonical English daily, trend, and existing insight
facts only. Recent facts, long-term facts, Memory, Temporal Evidence, playback rows,
and SQLite data remain excluded. ReportGenerator appends a locale-specific language
instruction to the unchanged safety prompt. `DailyBrief`, its JSON field names, and
provider adapters remain unchanged. The AI Markdown renderer localizes headings but
does not rewrite generated body strings.

AI language compliance is best-effort under the existing provider contract. A
structurally valid brief is accepted without language detection, retry, or automatic
translation.

## Persistence

Locale is runtime configuration and is never written to SQLite, playback history,
Memory, snapshots, Temporal Evidence, KnowledgeFact metadata, Narrative metadata, or
DailyBrief. Adding localization requires no database migration, snapshot-version
change, Memory rebuild, or historical-data rebuild.
