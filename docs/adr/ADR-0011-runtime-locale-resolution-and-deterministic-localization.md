# ADR-0011: Runtime Locale Resolution and Deterministic Localization

- Status: Accepted
- Date: 2026-08-05
- Decision owners: MusicMind maintainers
- Target release: MusicMind v0.7.0 Sprint 3D
- Related ADRs: ADR-0010
- Supersedes: None

## Context

MusicMind currently produces English-only user-facing output across several
independent paths:

- application runtime and synchronization messages;
- deterministic `MusicMind Daily` Markdown;
- `KnowledgeFact.title` and `KnowledgeFact.description`;
- recent and long-term observations;
- empty states, section headings, counts, units, and durations;
- AI Report prompt instructions;
- AI Report Markdown headings;
- selected Spotify authorization messages.

Sprint 3D introduces complete Simplified Chinese and English output support.

The supported locales are:

- `zh-CN`
- `en-US`

The application default is:

- `zh-CN`

One locale applies to the entire application run. The deterministic report and AI
Report must not independently resolve or request different languages.

Localization must preserve the architectural boundaries established by previous
sprints:

- Analytics calculates bounded statistics.
- Listening Memory stores versioned daily evidence.
- Temporal Analytics calculates recent and long-term evidence.
- Knowledge interprets completed evidence.
- Narrative selects, orders, limits, and deduplicates facts.
- Presentation renders selected content.
- ReportGenerator creates the AI prompt.
- LLM provider adapters only transport requests and responses.

Locale is runtime product configuration. It is not listening evidence and must not
be persisted in the database, Memory, snapshots, Temporal Evidence, Knowledge
metadata, or Narrative metadata.

The current `KnowledgeFact` contract includes required English `title` and
`description` fields. Existing tests, renderers, callers, and AI prompts depend on
those fields. Replacing them in Sprint 3D would create unnecessary compatibility
risk.

Narrative currently uses canonical fact fields as final deterministic tie-breakers.
Localizing facts before Narrative composition could therefore change which facts
are selected or how they are ordered between locales.

The current AI Report accepts only the existing daily, trend, and insight facts.
Recent and long-term facts are intentionally excluded. Sprint 3D changes the AI
Report language only and must not become AI Report v2.

## Decision

### 1. Supported locales

MusicMind supports exactly:

```text
zh-CN
en-US
```

The default locale is:

```text
zh-CN
```

Unsupported locales are rejected explicitly.

No locale negotiation, operating-system locale detection, or partial language tags
are introduced in Sprint 3D.

### 2. Runtime locale resolution

Locale is resolved exactly once per application run.

Resolution priority is:

```text
CLI argument
    ↓
MUSICMIND_LOCALE environment variable
    ↓
interactive terminal selection
    ↓
non-interactive default zh-CN
```

Supported CLI forms are:

```bash
python main.py --locale zh-CN
python main.py --locale en-US
```

Supported environment values are:

```env
MUSICMIND_LOCALE=zh-CN
MUSICMIND_LOCALE=en-US
```

A valid CLI value takes precedence over the environment variable. When a valid CLI
value is present, lower-priority environment configuration is ignored, including a
conflicting or invalid environment value.

An explicitly supplied invalid CLI value fails immediately.

When no CLI value exists, an explicitly present invalid or empty
`MUSICMIND_LOCALE` value fails immediately.

Explicit invalid values must not silently fall back to another locale.

The error format is:

```text
Unsupported locale: fr-FR
Supported locales: zh-CN, en-US
```

### 3. Interactive selection

When neither CLI nor environment configuration exists and standard input is an
interactive terminal, MusicMind asks once:

```text
请选择报告语言 / Choose report language:

1. 中文
2. English

请输入 1 或 2，直接回车默认中文：
```

Selection behavior is:

```text
1           → zh-CN
2           → en-US
empty input → zh-CN
```

Invalid interactive input prompts again with a fixed bilingual message:

```text
请输入 1 或 2 / Please enter 1 or 2.
```

The selector uses fixed pre-locale bilingual messages. It does not depend on an
already resolved locale or the normal localization catalog.

When standard input is not interactive, MusicMind does not attempt to read from it
and defaults to `zh-CN`.

End-of-input during the interactive prompt also defaults to `zh-CN`.

The deterministic report and AI Report do not ask separately. The resolved locale
controls both outputs for the whole run.

### 4. Application bootstrap order

The application entrypoint owns startup sequencing.

The required order is:

```text
1. Load .env once.
2. Parse script arguments.
3. Resolve SupportedLocale.
4. Validate localization catalogs.
5. Load and validate remaining application settings.
6. Authenticate with Spotify.
7. Initialize database and repositories.
8. Continue the existing MusicMind runtime.
```

Invalid locale configuration and invalid localization catalogs must fail before:

- Spotify authentication;
- network requests;
- database initialization;
- synchronization;
- Analytics;
- Memory processing.

The locale resolver does not locate or load `.env` files itself.

The application entrypoint loads `.env` once and passes the prepared environment
mapping into locale resolution.

`config.py` must not become a second locale resolver.

Programmatic calls to `main()` must not automatically consume unrelated global
`sys.argv` values. The `__main__` entry path passes the intended argument sequence
explicitly.

### 5. Locale contract ownership

`SupportedLocale` belongs to the Localization boundary.

It should be represented as a validated string enum equivalent to:

```python
class SupportedLocale(StrEnum):
    ZH_CN = "zh-CN"
    EN_US = "en-US"
```

Raw locale strings should exist only at external boundaries such as CLI and
environment input.

Application components receive a validated `SupportedLocale`.

Locale must not be independently resolved by:

- Knowledge engines;
- Narrative;
- deterministic renderers;
- ReportGenerator;
- AI Markdown rendering;
- Spotify authentication;
- provider adapters.

### 6. Fact message identity belongs to Knowledge

A semantic message identifier is added to the Knowledge contract.

The identifier records which already-selected Knowledge wording branch a fact
represents, for example:

```text
daily.listening_time
daily.playback_count
daily.top_artist
daily.top_song

trend.listening_time.zero_baseline
trend.listening_time.increased
trend.listening_time.decreased
trend.playback.more
trend.playback.fewer
trend.top_artist.changed
trend.top_song.changed

insight.focused_listening
insight.heavy.zero_baseline
insight.heavy
insight.light
insight.stable_top_artist

recent.artist_continuity
recent.artist_emergence

long_term.artist_consistency
long_term.listening_concentration
long_term.artist_breadth
```

This contract is conceptually named:

```text
FactMessageKey
```

`FactMessageKey` belongs to the Knowledge layer because it describes a semantic
interpretation branch, not a selected language or translation implementation.

It should be defined in either:

```text
music_ai/knowledge/models.py
```

or a dedicated Knowledge contract module such as:

```text
music_ai/knowledge/message_keys.py
```

Knowledge may not import Localization to construct facts.

The dependency direction is:

```text
Knowledge contracts
        ↓
Localization
```

It must not become:

```text
Knowledge
        ↓
Localization implementation
```

### 7. Additive KnowledgeFact migration

`KnowledgeFact.title` and `KnowledgeFact.description` remain required canonical
English fields.

An optional final field is added conceptually as:

```python
message_key: FactMessageKey | None = None
```

The exact public field name may follow repository conventions, but it must represent
the semantic fact-message branch.

All built-in MusicMind Knowledge engines must assign a valid message key to every
fact they create.

This includes:

- daily facts;
- trend facts;
- insight facts;
- recent facts;
- long-term facts.

`message_key=None` remains allowed only for backward compatibility with:

- existing direct callers;
- legacy tests during migration;
- external or custom facts not created by built-in MusicMind engines.

Locale must not be added to `KnowledgeFact.metadata`.

A separate `message_params` dictionary is not introduced. Existing immutable
metadata already contains the dynamic values needed for localization, and a second
parameter mapping would duplicate semantic data.

Adding the message key must not change:

- `FactCategory`;
- `ImportanceLevel`;
- `FactSource`;
- `FactTimeHorizon`;
- `InsightType`;
- `subject_key`;
- `concept_key`;
- date ranges;
- metadata values;
- fact-generation thresholds;
- fact-generation eligibility.

### 8. Canonical English is the single English fact source

Sprint 3D must not create a second complete English fact-template catalog.

For `en-US`, localized fact rendering uses the existing canonical fields:

```python
fact.title
fact.description
```

For `zh-CN`, localized fact rendering uses:

```text
FactMessageKey
+
immutable fact metadata
+
Chinese fact templates and formatters
```

This prevents English prose from being duplicated across:

- Knowledge engines; and
- an `en-US` fact catalog.

The required behavior is conceptually:

```python
if locale is SupportedLocale.EN_US:
    return LocalizedFact(
        title=fact.title,
        description=fact.description,
    )

if locale is SupportedLocale.ZH_CN:
    return localize_fact_from_key(
        fact.message_key,
        fact.metadata,
    )
```

For a custom or legacy fact with `message_key=None`:

```text
en-US → use canonical title and description
zh-CN → raise an explicit LocalizationError
```

MusicMind must not silently insert untranslated English facts into a Chinese
report.

### 9. Dedicated Localization boundary

Localization is implemented as a dedicated boundary, preferably under:

```text
music_ai/localization/
```

Likely responsibilities include:

```text
models.py
    SupportedLocale
    localization-specific errors

resolver.py
    CLI/environment/TTY locale resolution

catalog.py
    static UI, runtime, heading, and Chinese fact templates

formatters.py
    locale-aware counts, durations, percentages, and separators

fact_localizer.py
    KnowledgeFact → localized title and description
```

Exact file division may follow existing repository conventions.

The Localization boundary may depend on Knowledge contracts.

Knowledge, Analytics, Memory, Temporal Analytics, and Narrative must not depend on
Localization.

A general-purpose internationalization framework, runtime translation service,
database translation catalog, locale negotiation library, or persistent preference
model is not introduced.

### 10. Localization occurs after Narrative composition

Narrative remains locale-neutral.

Narrative continues to own:

- fact selection;
- deterministic ordering;
- recent observation limits;
- long-term observation limits;
- cross-horizon deduplication;
- `subject_key + concept_key` behavior;
- product priority rules.

Narrative must not own:

- translation templates;
- language selection;
- duration formatting;
- count formatting;
- AI output-language instructions.

Knowledge facts remain canonical during Narrative processing.

Localization is applied only after Narrative has completed:

```text
selection
ordering
limits
deduplication
```

This ensures that the same semantic input produces the same selected facts and the
same ordering in both `zh-CN` and `en-US`.

Sprint 3D does not replace the current Narrative tie-breakers or product priority
rules.

### 11. Static localization catalogs

Static immutable catalogs own user-interface wording such as:

- deterministic report titles;
- section headings;
- empty states;
- unavailable-data text;
- runtime status messages;
- AI Markdown headings;
- CLI help text where applicable.

Both `zh-CN` and `en-US` UI catalogs must contain the same required key set.

Chinese fact templates are keyed by `FactMessageKey`.

English fact wording continues to come from canonical `KnowledgeFact.title` and
`KnowledgeFact.description`, not a duplicate English fact catalog.

Dynamic values supplied by Spotify are treated as opaque text and interpolated
unchanged:

- artist names;
- track names;
- album names;
- Spotify-provided genre values.

No runtime machine translation is used.

### 12. Explicit catalog validation

Catalog completeness is validated through an explicit function equivalent to:

```python
validate_localization_catalogs()
```

The application entrypoint invokes this function after locale resolution and before
Spotify authentication.

Catalog validation must not depend solely on module import side effects.

The validation must confirm at least:

- `zh-CN` and `en-US` UI catalogs have identical required keys;
- every required UI message exists;
- every built-in `FactMessageKey` has a Chinese title and description template;
- formatter and template registrations are internally consistent.

Tests must also call catalog validation directly.

A missing translation is a configuration or build error.

MusicMind must not silently fall back from a missing Chinese translation to English.

### 13. Deterministic report localization

The deterministic Markdown renderer receives a validated locale.

The application always passes the resolved locale explicitly.

For direct API backward compatibility, renderer functions may use a keyword-only
`en-US` default.

Recommended section headings are:

| en-US | zh-CN |
|---|---|
| MusicMind Daily | MusicMind 每日听歌报告 |
| Listening Overview | 今日听歌概览 |
| Top Artists | 热门艺术家 |
| Top Tracks | 热门歌曲 |
| Genre Overview | 流派概览 |
| Recently | 最近变化 |
| Over Time | 长期观察 |
| Highlights | 重点发现 |

Recommended empty states include:

| en-US | zh-CN |
|---|---|
| Listening data is unavailable. | 暂无听歌数据。 |
| No listening activity was recorded today. | 今天没有记录到听歌活动。 |
| Unknown artist | 未知艺术家 |

The renderer continues to own Markdown structure.

Catalog templates own:

- wording;
- word order;
- punctuation.

Formatters own:

- duration units;
- count units;
- English singular and plural forms;
- Chinese classifiers;
- percentages;
- locale-specific separators.

### 14. Chinese formatting standard

Chinese user-facing units do not contain spaces between numbers and units.

Required examples are:

```text
1小时32分钟
12次
3首
20位艺术家
16个听歌日
70%
```

Recommended metric formatting is:

```text
预计听歌时长：1小时32分钟
播放次数：12次
不同歌曲：3首
```

Recommended ranked-row formatting is:

```text
1. Artist A — 预计1小时12分钟 · 播放5次 · 45%
```

Chinese sentence punctuation should use natural Simplified Chinese punctuation,
including full-width `：` and Chinese sentence marks where appropriate.

Multiple Chinese display names should use `、` when a Chinese list separator is
needed.

Dynamic source names themselves remain unchanged.

For `en-US`, deterministic output should remain byte-for-byte compatible wherever
the existing output is deterministic, including:

- headings;
- section order;
- empty states;
- compact `h` and `m` durations;
- singular and plural units;
- punctuation;
- separators.

### 15. Knowledge fact localization

Chinese fact wording must remain bounded by the existing evidence.

Localization may express only the semantic conclusion already selected by Knowledge.

It must not introduce new claims about:

- personality;
- identity;
- mood;
- motivation;
- causes;
- permanent taste;
- loyalty;
- favorite status beyond the existing evidence.

For example, the category currently named `STABLE_FAVORITE` must not be translated
into wording implying emotional loyalty or a permanent favorite.

A suitable Chinese title is equivalent to:

```text
榜首保持不变
```

rather than:

```text
稳定最爱
```

Long-term descriptions must continue to describe the local recorded period rather
than complete Spotify account history.

Localization must not recalculate thresholds, evidence sufficiency, or fact
eligibility.

### 16. AI Report localization

Sprint 3D changes the current AI Report language only.

The AI input scope remains unchanged.

ReportGenerator continues to receive only the facts currently passed to the AI path,
including the existing:

- daily facts;
- trend facts;
- insight facts.

It must not receive:

- recent facts;
- long-term facts;
- Listening Memory;
- Temporal Evidence;
- raw playback history;
- SQLite rows.

ReportGenerator receives the validated locale.

It continues formatting canonical English fact content for the prompt and appends a
locale-specific output-language instruction.

For `zh-CN`, the instruction must be equivalent to:

```text
Write every user-visible JSON string value in natural Simplified Chinese.
Keep artist, track, album, and genre names exactly as supplied.
```

For `en-US`, the instruction must be equivalent to:

```text
Write every user-visible JSON string value in English.
Keep artist, track, album, and genre names exactly as supplied.
```

The existing safety instructions remain in force.

The provider adapters remain language-neutral and unchanged.

Locale-specific prompt composition belongs to ReportGenerator or a shared prompt
composition boundary, not to OpenAI or DeepSeek adapters.

### 17. DailyBrief remains language-neutral

The existing `DailyBrief` schema remains unchanged.

Internal fields such as:

```text
greeting
listening_summary
trend
insight
recommendation
closing
```

are protocol identifiers and remain in English.

Their string values may contain either Simplified Chinese or English.

Sprint 3D must not introduce a separate Chinese `DailyBrief` model.

### 18. AI Markdown localization

The AI Markdown renderer receives the validated locale and localizes deterministic
headings.

For direct API compatibility, it may use a keyword-only `en-US` default.

Recommended Chinese headings are:

```markdown
# MusicMind AI 每日报告

## 👋 问候

## 🎵 听歌概览

## 📈 最近趋势

## 🧠 重点发现

## 💡 温和建议

## ✨ 结束语
```

The existing section order and emojis may remain unchanged.

AI-generated body content is rendered as returned after existing schema validation.

### 19. Wrong-language AI output

The current AI validation checks structure and non-empty strings, not language
identity.

Sprint 3D uses a clear prompt instruction but does not add:

- heuristic language detection;
- language-based retry logic;
- automatic translation;
- a second provider request;
- provider-specific language handling.

A structurally valid response is accepted even if the provider imperfectly follows
the requested language.

This is a documented probabilistic limitation of the current AI contract.

Hard language enforcement may be considered in a later sprint.

### 20. Runtime and Spotify authorization messages

Main application runtime and synchronization messages are localized using the
resolved locale.

The locale selector and explicit locale errors are mandatory Sprint 3D behavior.

Spotify authentication must not resolve locale itself and must not depend directly
on the localization catalog.

Where Spotify authorization exposes user-facing terminal or browser copy, localized
messages may be injected from the application boundary through a small
language-neutral message contract.

Authentication internals must not import the locale resolver.

A localization change must not redesign Spotify authentication or provider
transport behavior.

### 21. Compatibility defaults

Application runtime paths must explicitly pass the resolved locale.

For backward compatibility, direct lower-level APIs may default to `en-US`,
including:

- deterministic Markdown rendering;
- AI Markdown rendering;
- ReportGenerator construction or generation.

These defaults are compatibility mechanisms, not secondary locale resolution.

Lower-level components must not inspect environment variables or prompt the user.

The application-level default remains `zh-CN` by authoritative product decision.

### 22. Persistence and evidence isolation

Locale must not be stored in or added to:

- SQLite schemas;
- playback history;
- repositories;
- Listening Memory;
- daily snapshots;
- snapshot serialization;
- snapshot version;
- Temporal Evidence;
- `KnowledgeFact.metadata`;
- Narrative metadata;
- `DailyBrief`.

Sprint 3D requires no:

- database migration;
- snapshot-version change;
- Memory rebuild;
- historical data rebuild;
- new persistent table;
- Temporal calculation change;
- Analytics calculation change.

The same semantic evidence and facts must be renderable in either supported locale.

## Target architecture

```text
Application Entry
    |
    |-- load .env once
    |
    v
LocaleResolver
    |-- CLI
    |-- prepared environment mapping
    |-- fixed bilingual interactive prompt
    |-- non-TTY default
    v
SupportedLocale
    |
    |-- explicit catalog validation
    |
    +------------------------------------------+
    |                                          |
    v                                          v
Localized runtime messages               Remaining startup
                                               |
                                               v
                                      Spotify / SQLite
                                               |
                                               v
                                           Analytics
                                               |
                         +---------------------+------------------+
                         |                                        |
                         v                                        v
              DailyListeningProfile                       Listening Memory
                                                                  |
                                                                  v
                                                      Temporal Analytics
                                                                  |
                                                                  v
                                                          Temporal Evidence
                                                                  |
                                                                  v
                                                               Knowledge
                                                                  |
                                                                  v
                                                       KnowledgeFact
                                                canonical English title
                                                canonical English description
                                                FactMessageKey
                                                semantic metadata
                                                                  |
                                                                  v
                                                              Narrative
                                              selection / ordering / limits
                                                     deduplication
                                                                  |
                                                                  v
                                                   Deterministic Renderer
                                                   /                  \
                                                  /                    \
                                      en-US canonical prose       zh-CN fact localizer
                                                  \                    /
                                                   \                  /
                                                    MusicMind Daily

Daily + Trend + Insight facts only
                |
                v
          ReportGenerator
   canonical English facts + locale instruction
                |
                v
       Language-neutral LLMProvider
                |
                v
            DailyBrief
                |
                v
       Localized AI Markdown Renderer
                |
                v
       MusicMind AI Report
```

Locale must not enter:

```text
Database
Playback history
Memory
Temporal Evidence
Analytics calculations
Knowledge calculations
Narrative selection
DailyBrief schema
LLM provider adapters
```

## Consequences

### Positive consequences

- MusicMind can produce complete `zh-CN` and `en-US` reports.
- One locale consistently controls deterministic and AI output.
- Locale resolution is deterministic and testable.
- Invalid explicit configuration fails before network or database work.
- Existing English fact contracts remain compatible.
- English fact prose has one source of truth.
- Narrative selection remains identical across locales.
- Localization does not enter Memory or Temporal Evidence.
- Chinese wording is centrally managed and deterministic.
- Provider adapters remain independent of language policy.
- The architecture can support another locale later without repository-wide
  conditional branches.
- No persistent migration or historical rebuild is required.

### Negative consequences

- `KnowledgeFact` temporarily contains canonical English prose plus a semantic
  message identifier.
- Chinese fact localization depends on metadata completeness.
- Built-in fact engines must consistently assign message keys.
- Custom facts without message keys cannot be rendered in Chinese.
- Static catalogs and formatters add new maintenance responsibilities.
- AI language compliance remains best-effort.
- English and Chinese wording are produced through different paths:
  canonical fields for English and catalog templates for Chinese.

These costs are accepted because they minimize Sprint 3D migration risk while
preserving current architectural behavior.

## Rejected alternatives

### Locale-aware Knowledge engines

Rejected because it would make Knowledge presentation-aware, duplicate engine tests
per locale, and prevent one fact from being reused across languages.

### Presentation parsing English descriptions

Rejected because Presentation would need to parse or recognize free-form English
prose and could accidentally reinterpret Knowledge decisions.

### Localization before Narrative

Rejected because localized titles and descriptions could change Narrative
tie-breaking, selection, and ordering.

### Duplicate English fact catalog

Rejected because it would create two English sources of truth and require tests to
prevent prose drift.

### Scattered locale conditionals

Rejected because branches across `main.py`, Knowledge, renderers, prompts, Spotify,
and providers would increase coupling and incomplete-translation risk.

### Locale inside metadata

Rejected because runtime language is not listening evidence and should not affect
fact identity, deduplication, persistence, or downstream semantics.

### Provider-specific locale handling

Rejected because provider adapters should only transport prompts and responses.

### Separate Chinese DailyBrief schema

Rejected because the existing schema already supports Unicode strings and its field
names are internal protocol identifiers.

### Runtime machine translation

Rejected because output would become nondeterministic, require external services,
and weaken catalog completeness guarantees.

### Silent English fallback

Rejected because it would create mixed-language Chinese reports and hide missing
translations.

### Persistent locale preference

Rejected because account-level settings, database-backed preferences, and user
synchronization are outside Sprint 3D.

### AI Report v2

Rejected for Sprint 3D because changing the AI fact scope, prompt shape, or semantic
input model is a separate product and architecture change.

## Implementation constraints

Sprint 3D must not modify the behavior of:

- database schemas;
- repositories;
- Listening Memory;
- Memory serialization;
- snapshot versions;
- recent Temporal Analytics;
- long-term Temporal Analytics;
- Temporal Evidence contracts;
- product thresholds;
- recent and long-term fact eligibility;
- Narrative selection;
- Narrative ordering;
- observation limits;
- cross-horizon deduplication;
- `DailyBrief`;
- LLM provider interfaces;
- OpenAI or DeepSeek HTTP transport;
- AI fact scope.

All built-in facts must receive a semantic message key.

Localization must occur only after Narrative composition for deterministic output.

The AI path must continue receiving only its existing fact collection.

## Testing requirements

Implementation must include focused tests for the following.

### Locale resolution

- CLI `zh-CN`.
- CLI `en-US`.
- CLI overrides conflicting environment configuration.
- Valid CLI ignores invalid lower-priority environment configuration.
- Valid environment configuration bypasses interactive input.
- Invalid CLI fails clearly.
- Invalid environment value fails clearly.
- Empty environment value fails clearly.
- Interactive `1` selects `zh-CN`.
- Interactive `2` selects `en-US`.
- Interactive empty input selects `zh-CN`.
- Invalid interactive input retries.
- EOF selects `zh-CN`.
- Non-interactive execution selects `zh-CN` without reading stdin.
- Locale resolves before Spotify authentication.
- Programmatic calls do not consume unrelated global arguments.

### Catalog validation

- `zh-CN` and `en-US` UI catalogs have identical required key sets.
- Every required UI message exists.
- Every built-in `FactMessageKey` has a Chinese template.
- Missing catalog entries are detected explicitly.
- No runtime translation or network dependency exists.
- Catalog validation occurs before authentication.

### Knowledge contracts

- Every built-in fact branch assigns the expected message key.
- Existing canonical English title and description remain unchanged.
- Message keys do not alter fact metadata.
- Message keys do not alter product thresholds.
- Message keys do not alter fact eligibility.
- Legacy or custom facts may still use `message_key=None`.

### Fact localization

- Daily facts localize correctly.
- Trend branches localize correctly.
- Insight branches localize correctly.
- Recent facts localize correctly.
- Long-term facts localize correctly.
- Dynamic artist and track names remain unchanged.
- English facts use canonical title and description.
- Chinese localization fails clearly when a message key is missing.
- Original facts and metadata remain immutable.

### Deterministic report

- Existing complete English snapshots continue passing.
- One complete Chinese report snapshot is added.
- Chinese unavailable-data output.
- Chinese zero-activity output.
- English unavailable-data output remains unchanged.
- English zero-activity output remains unchanged.
- Chinese durations contain no spaces around units.
- Chinese count classifiers are correct.
- English singular and plural behavior remains correct.
- Dynamic artist, track, album, and genre names are preserved.
- The same `DailyNarrative` selects the same facts in both locales.
- Section ordering remains unchanged.
- Recent and long-term observation limits remain unchanged.

### AI Report

- `zh-CN` adds an explicit Simplified Chinese instruction.
- `en-US` adds or preserves an explicit English instruction.
- Canonical English facts remain the AI fact input.
- Recent facts remain excluded.
- Long-term facts remain excluded.
- `DailyBrief` remains unchanged.
- Chinese AI Markdown headings render correctly.
- English AI Markdown headings remain compatible.
- Provider adapters remain unchanged.
- Tests make no real network calls.

### Regression

- Full Memory suite passes.
- Full Temporal suite passes.
- Knowledge threshold tests pass.
- Narrative selection tests pass.
- Cross-horizon deduplication tests pass.
- Full existing test suite passes.

## Documentation requirements

Sprint 3D implementation should update:

- `README.md`
  - supported locales;
  - default locale;
  - CLI examples;
  - `MUSICMIND_LOCALE`;
  - interactive selection behavior.

- `docs/architecture.md`
  - Localization boundary;
  - resolve-once dependency flow;
  - locale isolation from evidence layers.

- `docs/knowledge.md`
  - canonical English compatibility fields;
  - semantic fact-message keys;
  - Knowledge remaining locale-neutral.

- `docs/narrative.md`
  - Narrative remaining locale-neutral;
  - localization occurring after selection and ordering.

- AI documentation
  - locale-specific language instruction;
  - unchanged AI fact scope;
  - unchanged `DailyBrief`;
  - provider neutrality.

- A localization guide such as `docs/localization.md`
  - catalogs;
  - formatters;
  - Chinese typography;
  - dynamic-name policy;
  - catalog validation;
  - missing-translation behavior.

## Explicit non-goals

Sprint 3D does not include:

- a third locale;
- operating-system locale detection;
- locale negotiation;
- runtime machine translation;
- database-backed translation catalogs;
- writing locale to SQLite;
- writing locale to Memory;
- writing locale to Evidence;
- snapshot migration;
- historical rebuilds;
- different locales per report section;
- simultaneous full bilingual reports;
- AI Report v2;
- Recent facts entering AI;
- Long-term facts entering AI;
- Long-term Listening Evolution;
- language-detection heuristics;
- AI retry based on output language;
- Web UI language selection;
- user-account preference synchronization;
- personalized writing styles;
- provider-specific locale branches.

## Follow-up work

Possible future work includes:

- AI Report v2 with structured temporal context;
- hard AI language-compliance validation;
- additional supported locales;
- user-persisted language preferences;
- web or mobile locale selectors;
- migration away from canonical English fact prose if a future semantic fact contract
  fully replaces presentation strings.

These are separate product decisions and are not implied by Sprint 3D.

## Implementation

Sprint 3D implements this decision with `music_ai.knowledge.message_keys` and the
`music_ai.localization` package. The application entrypoint performs dotenv loading,
locale resolution, explicit catalog validation, and downstream injection in the
decided order. Deterministic fact localization occurs inside Presentation after
Narrative composition; ReportGenerator uses canonical English facts plus the locale
instruction; OAuth receives only an immutable prelocalized user-message bundle.
