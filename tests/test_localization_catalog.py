from dataclasses import replace

import pytest

from music_ai.knowledge import (
    FactCategory,
    FactMessageKey,
    ImportanceLevel,
    KnowledgeFact,
)
from music_ai.localization import (
    LocalizationError,
    MissingTranslationError,
    SupportedLocale,
    localize_fact,
    validate_localization_catalogs,
)
from music_ai.localization.catalog import (
    ChineseFactTemplate,
    _UI_CATALOGS,
    _UI_PLACEHOLDER_CONTRACT,
)
from music_ai.localization.formatters import (
    format_artist_count,
    format_compact_duration,
    format_listening_day_count,
    format_percentage,
    format_playback_count,
    format_prose_duration,
    format_track_count,
    join_display_names,
)
from music_ai.localization.models import UiMessageKey


_FACT_METADATA = {
    FactMessageKey.DAILY_LISTENING_TIME: {"total_listening_time_ms": 5_520_000},
    FactMessageKey.DAILY_PLAYBACK_COUNT: {"playback_count": 28},
    FactMessageKey.DAILY_TOP_ARTIST: {"artist_name": "Artist A"},
    FactMessageKey.DAILY_TOP_SONG: {"song_name": "Track A"},
    FactMessageKey.TREND_LISTENING_TIME_ZERO_BASELINE: {"current_value": 4_800_000},
    FactMessageKey.TREND_LISTENING_TIME_INCREASED: {"percentage_change": 50},
    FactMessageKey.TREND_LISTENING_TIME_DECREASED: {"percentage_change": -25},
    FactMessageKey.TREND_PLAYBACK_MORE: {"change": 7},
    FactMessageKey.TREND_PLAYBACK_FEWER: {"change": -7},
    FactMessageKey.TREND_TOP_ARTIST_CHANGED: {
        "previous_value": "Artist A",
        "current_value": "Artist B",
    },
    FactMessageKey.TREND_TOP_SONG_CHANGED: {
        "previous_value": "Track A",
        "current_value": "Track B",
        "previous_artist": "Artist A",
        "current_artist": "Artist B",
    },
    FactMessageKey.INSIGHT_FOCUSED_LISTENING: {
        "artist_name": "Artist A",
        "listening_share": 0.75,
    },
    FactMessageKey.INSIGHT_HEAVY_ZERO_BASELINE: {
        "previous_value": 0,
        "current_value": 3_000_000,
        "percentage_change": None,
    },
    FactMessageKey.INSIGHT_HEAVY: {"percentage_change": 100},
    FactMessageKey.INSIGHT_LIGHT: {"percentage_change": -50},
    FactMessageKey.INSIGHT_STABLE_TOP_ARTIST: {"artist_name": "Artist A"},
    FactMessageKey.RECENT_ARTIST_CONTINUITY: {
        "artist_name": "Artist A",
        "qualifying_day_count": 8,
        "listening_day_count": 16,
    },
    FactMessageKey.RECENT_ARTIST_EMERGENCE: {
        "artist_name": "Artist A",
        "comparison_duration_share": 0.1,
        "recent_duration_share": 0.4,
    },
    FactMessageKey.LONG_TERM_ARTIST_CONSISTENCY: {
        "artist_name": "Artist A",
        "appearance_day_count": 8,
        "listening_day_count": 16,
    },
    FactMessageKey.LONG_TERM_LISTENING_CONCENTRATION: {
        "top_five_duration_share": 0.7,
    },
    FactMessageKey.LONG_TERM_ARTIST_BREADTH: {
        "unique_artist_count": 20,
        "listening_day_count": 16,
        "single_day_artist_count": 8,
    },
}


def _fact(
    message_key: FactMessageKey | None,
    metadata: dict[str, object] | None = None,
) -> KnowledgeFact:
    return KnowledgeFact(
        category=FactCategory.LISTENING_TIME,
        importance=ImportanceLevel.MEDIUM,
        title="Canonical title",
        description="Canonical description.",
        metadata=metadata or {},
        message_key=message_key,
    )


def test_production_catalogs_are_complete() -> None:
    validate_localization_catalogs()
    assert set(_FACT_METADATA) == set(FactMessageKey)
    assert set(_UI_PLACEHOLDER_CONTRACT) == set(UiMessageKey)


def _mutable_production_ui_catalogs() -> dict[SupportedLocale, dict[UiMessageKey, str]]:
    return {
        locale: dict(messages)
        for locale, messages in _UI_CATALOGS.items()
    }


def test_catalog_validation_detects_temporary_missing_entries() -> None:
    complete_ui = _mutable_production_ui_catalogs()
    complete_facts = {
        key: ChineseFactTemplate("标题", frozenset(), lambda _data: "描述。")
        for key in FactMessageKey
    }
    incomplete_ui = {
        locale: dict(messages) for locale, messages in complete_ui.items()
    }
    incomplete_ui[SupportedLocale.ZH_CN].pop(UiMessageKey.HIGHLIGHTS)
    with pytest.raises(MissingTranslationError, match="missing"):
        validate_localization_catalogs(
            ui_catalogs=incomplete_ui,
            chinese_fact_templates=complete_facts,
        )

    incomplete_facts = dict(complete_facts)
    incomplete_facts.pop(FactMessageKey.DAILY_LISTENING_TIME)
    with pytest.raises(MissingTranslationError, match="missing"):
        validate_localization_catalogs(
            ui_catalogs=complete_ui,
            chinese_fact_templates=incomplete_facts,
        )

    invalid_declaration = dict(complete_facts)
    invalid_declaration[FactMessageKey.DAILY_LISTENING_TIME] = ChineseFactTemplate(
        "标题",
        {"value"},  # type: ignore[arg-type]
        lambda _data: "描述。",
    )
    with pytest.raises(LocalizationError, match="metadata declaration"):
        validate_localization_catalogs(
            ui_catalogs=complete_ui,
            chinese_fact_templates=invalid_declaration,
        )


@pytest.mark.parametrize(
    ("locale", "key", "replacement"),
    [
        (SupportedLocale.EN_US, UiMessageKey.PLAYBACK_COUNT, "Playback count"),
        (
            SupportedLocale.EN_US,
            UiMessageKey.PLAYBACK_COUNT,
            "Playback count: {records}",
        ),
        (
            SupportedLocale.EN_US,
            UiMessageKey.PLAYBACK_COUNT,
            "Playback count: {count} {records}",
        ),
        (SupportedLocale.EN_US, UiMessageKey.PLAYBACK_COUNT, "Playback count: {count"),
        (
            SupportedLocale.ZH_CN,
            UiMessageKey.UNIQUE_TRACKS,
            "不同歌曲：{records}",
        ),
        (
            SupportedLocale.ZH_CN,
            UiMessageKey.HIGHLIGHTS,
            "重点发现：{count}",
        ),
    ],
    ids=(
        "missing-required",
        "incorrect-name",
        "unexpected-extra",
        "malformed",
        "locale-specific-mismatch",
        "static-unexpected",
    ),
)
def test_catalog_validation_rejects_placeholder_contract_violations(
    locale: SupportedLocale,
    key: UiMessageKey,
    replacement: str,
) -> None:
    catalogs = _mutable_production_ui_catalogs()
    catalogs[locale][key] = replacement

    with pytest.raises(LocalizationError) as error_info:
        validate_localization_catalogs(ui_catalogs=catalogs)

    message = str(error_info.value)
    assert locale.value in message
    assert key.value in message


def test_catalog_validation_rejects_an_incomplete_placeholder_contract() -> None:
    contract = dict(_UI_PLACEHOLDER_CONTRACT)
    contract.pop(UiMessageKey.HIGHLIGHTS)

    with pytest.raises(LocalizationError, match="placeholder contract.*missing"):
        validate_localization_catalogs(ui_placeholder_contract=contract)


@pytest.mark.parametrize("message_key", list(FactMessageKey))
def test_every_fact_message_key_localizes_to_chinese(
    message_key: FactMessageKey,
) -> None:
    fact = _fact(message_key, _FACT_METADATA[message_key])
    localized = localize_fact(fact, SupportedLocale.ZH_CN)
    assert localized.title
    assert localized.description.endswith("。")
    assert fact.title == "Canonical title"
    assert dict(fact.metadata) == _FACT_METADATA[message_key]


def test_fact_localizer_uses_canonical_english_and_rejects_missing_chinese_key() -> None:
    fact = _fact(None)
    assert localize_fact(fact, SupportedLocale.EN_US).description == (
        "Canonical description."
    )
    with pytest.raises(LocalizationError, match="without message_key"):
        localize_fact(fact, SupportedLocale.ZH_CN)


def test_fact_localizer_validates_required_metadata() -> None:
    with pytest.raises(LocalizationError, match="total_listening_time_ms"):
        localize_fact(
            _fact(FactMessageKey.DAILY_LISTENING_TIME),
            SupportedLocale.ZH_CN,
        )


def test_message_key_does_not_change_knowledge_fact_equality() -> None:
    legacy = _fact(None, {"total_listening_time_ms": 60_000})
    localized = replace(
        legacy,
        message_key=FactMessageKey.DAILY_LISTENING_TIME,
    )
    assert legacy == localized
    with pytest.raises(TypeError):
        hash(legacy)
    with pytest.raises(TypeError):
        hash(localized)


def test_knowledge_fact_rejects_a_raw_message_key() -> None:
    with pytest.raises(TypeError, match="FactMessageKey"):
        _fact("daily.listening_time")  # type: ignore[arg-type]


def test_downstream_localization_rejects_raw_locale_strings() -> None:
    fact = _fact(None)
    with pytest.raises(TypeError, match="SupportedLocale"):
        localize_fact(fact, "en-US")  # type: ignore[arg-type]


def test_chinese_fact_wording_is_natural_and_preserves_dynamic_names() -> None:
    daily = localize_fact(
        _fact(
            FactMessageKey.DAILY_LISTENING_TIME,
            {"total_listening_time_ms": 5_520_000},
        ),
        SupportedLocale.ZH_CN,
    )
    stable = localize_fact(
        _fact(
            FactMessageKey.INSIGHT_STABLE_TOP_ARTIST,
            {"artist_name": "Kendrick Lamar 王"},
        ),
        SupportedLocale.ZH_CN,
    )
    assert daily.description == "今天听歌共1小时32分钟。"
    assert stable.title == "榜首保持不变"
    assert "Kendrick Lamar 王" in stable.description
    assert "稳定最爱" not in stable.title


@pytest.mark.parametrize(
    ("metadata", "expected"),
    [
        (
            {
                "previous_value": "Track A",
                "current_value": "Track B",
                "previous_artist": "Artist A",
                "current_artist": "Artist B",
            },
            "今天听歌时长最多的歌曲从 Artist A 的《Track A》变为 Artist B 的《Track B》。",
        ),
        (
            {
                "previous_value": "Intro",
                "current_value": "Intro",
                "previous_artist": "Artist A",
                "current_artist": "Artist B",
            },
            "今天听歌时长最多的歌曲从 Artist A 的《Intro》变为 Artist B 的《Intro》。",
        ),
        (
            {
                "previous_value": "开场：Intro?!",
                "current_value": "序曲・No. 2",
                "previous_artist": "乐队 A/B",
                "current_artist": "Beyoncé（现场）",
            },
            "今天听歌时长最多的歌曲从 乐队 A/B 的《开场：Intro?!》变为 Beyoncé（现场） 的《序曲・No. 2》。",
        ),
    ],
)
def test_chinese_top_song_change_includes_unchanged_song_and_artist_names(
    metadata: dict[str, object],
    expected: str,
) -> None:
    fact = _fact(FactMessageKey.TREND_TOP_SONG_CHANGED, metadata)
    localized = localize_fact(
        fact,
        SupportedLocale.ZH_CN,
    )

    assert localized.description == expected
    assert dict(fact.metadata) == metadata


@pytest.mark.parametrize("missing_key", ["previous_artist", "current_artist"])
def test_chinese_top_song_change_requires_both_artists(missing_key: str) -> None:
    metadata = dict(_FACT_METADATA[FactMessageKey.TREND_TOP_SONG_CHANGED])
    metadata.pop(missing_key)

    with pytest.raises(LocalizationError, match=missing_key):
        localize_fact(
            _fact(FactMessageKey.TREND_TOP_SONG_CHANGED, metadata),
            SupportedLocale.ZH_CN,
        )


def test_locale_formatters_preserve_english_and_apply_chinese_classifiers() -> None:
    assert format_compact_duration(5_520_000, SupportedLocale.EN_US) == "1h 32m"
    assert format_compact_duration(5_520_000, SupportedLocale.ZH_CN) == "1小时32分钟"
    assert format_prose_duration(5_520_000, SupportedLocale.EN_US) == (
        "1 hour and 32 minutes"
    )
    assert format_playback_count(1, SupportedLocale.EN_US) == "1 play"
    assert format_playback_count(12, SupportedLocale.ZH_CN) == "12次"
    assert format_track_count(3, SupportedLocale.ZH_CN) == "3首"
    assert format_artist_count(20, SupportedLocale.ZH_CN) == "20位艺术家"
    assert format_listening_day_count(16, SupportedLocale.ZH_CN) == "16个听歌日"
    assert format_percentage(0.7, SupportedLocale.ZH_CN) == "70%"
    assert join_display_names(["A", "B"], SupportedLocale.ZH_CN) == "A、B"
