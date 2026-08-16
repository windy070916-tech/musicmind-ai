"""Immutable UI catalogs and controlled Chinese fact templates."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from string import Formatter
from types import MappingProxyType

from music_ai.knowledge.message_keys import FactMessageKey
from music_ai.localization.formatters import (
    format_artist_count,
    format_artists_per_listening_day,
    format_listening_day_count,
    format_percentage,
    format_playback_count,
    format_prose_duration,
)
from music_ai.localization.models import (
    LocalizationError,
    MissingTranslationError,
    SupportedLocale,
    UiMessageKey,
    require_supported_locale,
)


@dataclass(frozen=True, slots=True)
class ChineseFactTemplate:
    """One validated Chinese title and description renderer."""

    title: str
    required_metadata: frozenset[str]
    render_description: Callable[[Mapping[str, object]], str]


_EN_US_UI_CATALOG = MappingProxyType(
    {
        UiMessageKey.DAILY_REPORT_TITLE: "MusicMind Daily",
        UiMessageKey.LISTENING_OVERVIEW: "Listening Overview",
        UiMessageKey.TOP_ARTISTS: "Top Artists",
        UiMessageKey.TOP_TRACKS: "Top Tracks",
        UiMessageKey.GENRE_OVERVIEW: "Genre Overview",
        UiMessageKey.RECENTLY: "Recently",
        UiMessageKey.OVER_TIME: "Over Time",
        UiMessageKey.HIGHLIGHTS: "Highlights",
        UiMessageKey.LISTENING_UNAVAILABLE: "Listening data is unavailable.",
        UiMessageKey.NO_LISTENING_ACTIVITY: "No listening activity was recorded today.",
        UiMessageKey.UNKNOWN_ARTIST: "Unknown artist",
        UiMessageKey.ESTIMATED_LISTENING_DURATION: "Estimated listening duration: {duration}",
        UiMessageKey.PLAYBACK_COUNT: "Playback count: {count}",
        UiMessageKey.UNIQUE_TRACKS: "Unique tracks: {count}",
        UiMessageKey.RANKED_ESTIMATED_DURATION: "estimated {duration}",
        UiMessageKey.RANKED_PLAYBACK_COUNT: "{count}",
        UiMessageKey.SPOTIFY_LOGIN_SUCCESS: "Spotify Login Success",
        UiMessageKey.IMPORTED_PLAYBACK_RECORDS: "Imported {count} playback records.",
        UiMessageKey.DATABASE_UPDATED: "Database updated successfully.",
        UiMessageKey.FIRST_SYNCHRONIZATION: "First synchronization.",
        UiMessageKey.DOWNLOADING_RECENT_HISTORY: "Downloading recent playback history...",
        UiMessageKey.LAST_SYNCHRONIZED_PLAYBACK: "Last synchronized playback:",
        UiMessageKey.CHECKING_SPOTIFY: "Checking Spotify...",
        UiMessageKey.FOUND_NEW_PLAYBACK_RECORDS: "Found {count} new playback records.",
        UiMessageKey.DAILY_FACTS_LABEL: "MusicMind Daily Facts",
        UiMessageKey.DAILY_TRENDS_LABEL: "MusicMind Daily Trends",
        UiMessageKey.INSIGHT_FACTS_LABEL: "MusicMind Insight Facts",
        UiMessageKey.NO_DAILY_CHANGES: "No changes from yesterday.",
        UiMessageKey.NO_DAILY_INSIGHTS: "No behavioral insights for today.",
        UiMessageKey.AI_REPORT_LABEL: "MusicMind AI",
        UiMessageKey.AI_NO_SIGNAL: (
            "There are no new listening changes worth a separate interpretation today."
        ),
        UiMessageKey.AI_GENERATION_FAILURE: (
            "MusicMind AI could not generate an interpretation this time."
        ),
        UiMessageKey.OAUTH_OPEN_URL: "Open this URL in your browser to authenticate with Spotify:",
        UiMessageKey.OAUTH_UNKNOWN_CALLBACK_PATH: "Unknown callback path.",
        UiMessageKey.OAUTH_AUTHORIZATION_FAILED: "Spotify authorization failed: {error}",
        UiMessageKey.OAUTH_INVALID_STATE: "Invalid authorization state.",
        UiMessageKey.OAUTH_MISSING_CODE: "Missing authorization code.",
        UiMessageKey.OAUTH_SUCCESS: (
            "Spotify authentication received. You can return to the terminal."
        ),
        UiMessageKey.CLI_LOCALE_HELP: "Report language: zh-CN or en-US",
    }
)


_ZH_CN_UI_CATALOG = MappingProxyType(
    {
        UiMessageKey.DAILY_REPORT_TITLE: "MusicMind 每日听歌报告",
        UiMessageKey.LISTENING_OVERVIEW: "今日听歌概览",
        UiMessageKey.TOP_ARTISTS: "热门艺术家",
        UiMessageKey.TOP_TRACKS: "热门歌曲",
        UiMessageKey.GENRE_OVERVIEW: "流派概览",
        UiMessageKey.RECENTLY: "最近变化",
        UiMessageKey.OVER_TIME: "长期观察",
        UiMessageKey.HIGHLIGHTS: "重点发现",
        UiMessageKey.LISTENING_UNAVAILABLE: "暂无听歌数据。",
        UiMessageKey.NO_LISTENING_ACTIVITY: "今天没有记录到听歌活动。",
        UiMessageKey.UNKNOWN_ARTIST: "未知艺术家",
        UiMessageKey.ESTIMATED_LISTENING_DURATION: "预计听歌时长：{duration}",
        UiMessageKey.PLAYBACK_COUNT: "播放次数：{count}",
        UiMessageKey.UNIQUE_TRACKS: "不同歌曲：{count}",
        UiMessageKey.RANKED_ESTIMATED_DURATION: "预计{duration}",
        UiMessageKey.RANKED_PLAYBACK_COUNT: "播放{count}",
        UiMessageKey.SPOTIFY_LOGIN_SUCCESS: "Spotify 登录成功",
        UiMessageKey.IMPORTED_PLAYBACK_RECORDS: "已导入{count}条播放记录。",
        UiMessageKey.DATABASE_UPDATED: "数据库更新成功。",
        UiMessageKey.FIRST_SYNCHRONIZATION: "首次同步。",
        UiMessageKey.DOWNLOADING_RECENT_HISTORY: "正在下载最近播放记录……",
        UiMessageKey.LAST_SYNCHRONIZED_PLAYBACK: "上次同步的播放时间：",
        UiMessageKey.CHECKING_SPOTIFY: "正在检查 Spotify……",
        UiMessageKey.FOUND_NEW_PLAYBACK_RECORDS: "发现{count}条新的播放记录。",
        UiMessageKey.DAILY_FACTS_LABEL: "MusicMind 每日事实",
        UiMessageKey.DAILY_TRENDS_LABEL: "MusicMind 每日趋势",
        UiMessageKey.INSIGHT_FACTS_LABEL: "MusicMind 重点发现",
        UiMessageKey.NO_DAILY_CHANGES: "与昨天相比没有变化。",
        UiMessageKey.NO_DAILY_INSIGHTS: "今天暂无听歌行为方面的重点发现。",
        UiMessageKey.AI_REPORT_LABEL: "MusicMind AI",
        UiMessageKey.AI_NO_SIGNAL: "今天还没有出现值得单独解读的新变化。",
        UiMessageKey.AI_GENERATION_FAILURE: "MusicMind AI 本次未能生成解读。",
        UiMessageKey.OAUTH_OPEN_URL: "请在浏览器中打开以下网址以登录 Spotify：",
        UiMessageKey.OAUTH_UNKNOWN_CALLBACK_PATH: "未知的回调路径。",
        UiMessageKey.OAUTH_AUTHORIZATION_FAILED: "Spotify 授权失败：{error}",
        UiMessageKey.OAUTH_INVALID_STATE: "授权状态无效。",
        UiMessageKey.OAUTH_MISSING_CODE: "缺少授权代码。",
        UiMessageKey.OAUTH_SUCCESS: "Spotify 登录已完成。你可以返回终端。",
        UiMessageKey.CLI_LOCALE_HELP: "报告语言：zh-CN 或 en-US",
    }
)


_UI_CATALOGS = MappingProxyType(
    {
        SupportedLocale.EN_US: _EN_US_UI_CATALOG,
        SupportedLocale.ZH_CN: _ZH_CN_UI_CATALOG,
    }
)


_UI_PLACEHOLDER_CONTRACT = MappingProxyType(
    {
        UiMessageKey.DAILY_REPORT_TITLE: frozenset(),
        UiMessageKey.LISTENING_OVERVIEW: frozenset(),
        UiMessageKey.TOP_ARTISTS: frozenset(),
        UiMessageKey.TOP_TRACKS: frozenset(),
        UiMessageKey.GENRE_OVERVIEW: frozenset(),
        UiMessageKey.RECENTLY: frozenset(),
        UiMessageKey.OVER_TIME: frozenset(),
        UiMessageKey.HIGHLIGHTS: frozenset(),
        UiMessageKey.LISTENING_UNAVAILABLE: frozenset(),
        UiMessageKey.NO_LISTENING_ACTIVITY: frozenset(),
        UiMessageKey.UNKNOWN_ARTIST: frozenset(),
        UiMessageKey.ESTIMATED_LISTENING_DURATION: frozenset({"duration"}),
        UiMessageKey.PLAYBACK_COUNT: frozenset({"count"}),
        UiMessageKey.UNIQUE_TRACKS: frozenset({"count"}),
        UiMessageKey.RANKED_ESTIMATED_DURATION: frozenset({"duration"}),
        UiMessageKey.RANKED_PLAYBACK_COUNT: frozenset({"count"}),
        UiMessageKey.SPOTIFY_LOGIN_SUCCESS: frozenset(),
        UiMessageKey.IMPORTED_PLAYBACK_RECORDS: frozenset({"count"}),
        UiMessageKey.DATABASE_UPDATED: frozenset(),
        UiMessageKey.FIRST_SYNCHRONIZATION: frozenset(),
        UiMessageKey.DOWNLOADING_RECENT_HISTORY: frozenset(),
        UiMessageKey.LAST_SYNCHRONIZED_PLAYBACK: frozenset(),
        UiMessageKey.CHECKING_SPOTIFY: frozenset(),
        UiMessageKey.FOUND_NEW_PLAYBACK_RECORDS: frozenset({"count"}),
        UiMessageKey.DAILY_FACTS_LABEL: frozenset(),
        UiMessageKey.DAILY_TRENDS_LABEL: frozenset(),
        UiMessageKey.INSIGHT_FACTS_LABEL: frozenset(),
        UiMessageKey.NO_DAILY_CHANGES: frozenset(),
        UiMessageKey.NO_DAILY_INSIGHTS: frozenset(),
        UiMessageKey.AI_REPORT_LABEL: frozenset(),
        UiMessageKey.AI_NO_SIGNAL: frozenset(),
        UiMessageKey.AI_GENERATION_FAILURE: frozenset(),
        UiMessageKey.OAUTH_OPEN_URL: frozenset(),
        UiMessageKey.OAUTH_UNKNOWN_CALLBACK_PATH: frozenset(),
        UiMessageKey.OAUTH_AUTHORIZATION_FAILED: frozenset({"error"}),
        UiMessageKey.OAUTH_INVALID_STATE: frozenset(),
        UiMessageKey.OAUTH_MISSING_CODE: frozenset(),
        UiMessageKey.OAUTH_SUCCESS: frozenset(),
        UiMessageKey.CLI_LOCALE_HELP: frozenset(),
    }
)


_ZH_CN_FACT_TEMPLATES = MappingProxyType(
    {
        FactMessageKey.DAILY_LISTENING_TIME: ChineseFactTemplate(
            "听歌时长",
            frozenset({"total_listening_time_ms"}),
            lambda data: (
                "今天听歌共"
                f"{_zh_duration(data, 'total_listening_time_ms')}。"
            ),
        ),
        FactMessageKey.DAILY_PLAYBACK_COUNT: ChineseFactTemplate(
            "播放次数",
            frozenset({"playback_count"}),
            lambda data: (
                "今天共播放了"
                f"{_zh_playbacks(data, 'playback_count')}。"
            ),
        ),
        FactMessageKey.DAILY_TOP_ARTIST: ChineseFactTemplate(
            "今日热门艺术家",
            frozenset({"artist_name"}),
            lambda data: (
                f"今天听歌时长最多的艺术家是 {_text(data, 'artist_name')}。"
            ),
        ),
        FactMessageKey.DAILY_TOP_SONG: ChineseFactTemplate(
            "今日热门歌曲",
            frozenset({"song_name"}),
            lambda data: f"今天听歌时长最多的歌曲是 {_text(data, 'song_name')}。",
        ),
        FactMessageKey.TREND_LISTENING_TIME_ZERO_BASELINE: ChineseFactTemplate(
            "听歌时长增加",
            frozenset({"current_value"}),
            lambda data: (
                "昨天未记录到听歌时长，今天为"
                f"{_zh_duration(data, 'current_value')}。"
            ),
        ),
        FactMessageKey.TREND_LISTENING_TIME_INCREASED: ChineseFactTemplate(
            "听歌时长增加",
            frozenset({"percentage_change"}),
            lambda data: (
                "与昨天相比，听歌时长增加了"
                f"{abs(_integer(data, 'percentage_change'))}%。"
            ),
        ),
        FactMessageKey.TREND_LISTENING_TIME_DECREASED: ChineseFactTemplate(
            "听歌时长减少",
            frozenset({"percentage_change"}),
            lambda data: (
                "与昨天相比，听歌时长减少了"
                f"{abs(_integer(data, 'percentage_change'))}%。"
            ),
        ),
        FactMessageKey.TREND_PLAYBACK_MORE: ChineseFactTemplate(
            "播放次数增加",
            frozenset({"change"}),
            lambda data: (
                "今天比昨天多播放了"
                f"{format_playback_count(abs(_integer(data, 'change')), SupportedLocale.ZH_CN)}。"
            ),
        ),
        FactMessageKey.TREND_PLAYBACK_FEWER: ChineseFactTemplate(
            "播放次数减少",
            frozenset({"change"}),
            lambda data: (
                "今天比昨天少播放了"
                f"{format_playback_count(abs(_integer(data, 'change')), SupportedLocale.ZH_CN)}。"
            ),
        ),
        FactMessageKey.TREND_TOP_ARTIST_CHANGED: ChineseFactTemplate(
            "热门艺术家变化",
            frozenset({"previous_value", "current_value"}),
            lambda data: (
                f"今天听歌时长最多的艺术家从 {_text(data, 'previous_value')} "
                f"变为 {_text(data, 'current_value')}。"
            ),
        ),
        FactMessageKey.TREND_TOP_SONG_CHANGED: ChineseFactTemplate(
            "热门歌曲变化",
            frozenset(
                {
                    "previous_value",
                    "current_value",
                    "previous_artist",
                    "current_artist",
                }
            ),
            lambda data: (
                "今天听歌时长最多的歌曲从 "
                f"{_text(data, 'previous_artist')} 的《{_text(data, 'previous_value')}》"
                f"变为 {_text(data, 'current_artist')} 的《{_text(data, 'current_value')}》。"
            ),
        ),
        FactMessageKey.INSIGHT_FOCUSED_LISTENING: ChineseFactTemplate(
            "听歌较集中",
            frozenset({"artist_name", "listening_share"}),
            lambda data: (
                f"今天大部分听歌时长（{_zh_percentage(data, 'listening_share')}）"
                f"来自 {_text(data, 'artist_name')}。"
            ),
        ),
        FactMessageKey.INSIGHT_HEAVY_ZERO_BASELINE: ChineseFactTemplate(
            "听歌时长明显增加",
            frozenset(
                {"previous_value", "current_value", "percentage_change"}
            ),
            lambda data: (
                "与昨天未记录到听歌时长相比，今天的听歌时长明显增加。"
            ),
        ),
        FactMessageKey.INSIGHT_HEAVY: ChineseFactTemplate(
            "听歌时长明显增加",
            frozenset({"percentage_change"}),
            lambda data: (
                "今天的听歌时长比昨天高"
                f"{abs(_integer(data, 'percentage_change'))}%。"
            ),
        ),
        FactMessageKey.INSIGHT_LIGHT: ChineseFactTemplate(
            "听歌时长明显减少",
            frozenset({"percentage_change"}),
            lambda data: (
                "今天的听歌时长比昨天低"
                f"{abs(_integer(data, 'percentage_change'))}%。"
            ),
        ),
        FactMessageKey.INSIGHT_STABLE_TOP_ARTIST: ChineseFactTemplate(
            "榜首保持不变",
            frozenset({"artist_name"}),
            lambda data: (
                f"{_text(data, 'artist_name')} 今天仍是听歌时长最多的艺术家。"
            ),
        ),
        FactMessageKey.RECENT_ARTIST_CONTINUITY: ChineseFactTemplate(
            "最近常居榜首",
            frozenset({"artist_name", "qualifying_day_count", "listening_day_count"}),
            lambda data: (
                "在最近"
                f"{_zh_listening_days(data, 'listening_day_count')}中，"
                f"{_text(data, 'artist_name')} 有"
                f"{_integer(data, 'qualifying_day_count')}天是听歌时长最多的艺术家。"
            ),
        ),
        FactMessageKey.RECENT_ARTIST_EMERGENCE: ChineseFactTemplate(
            "最近占比上升",
            frozenset({"artist_name", "comparison_duration_share", "recent_duration_share"}),
            lambda data: (
                f"{_text(data, 'artist_name')} 的听歌时长占比从"
                f"{_zh_percentage(data, 'comparison_duration_share')}上升到"
                f"{_zh_percentage(data, 'recent_duration_share')}。"
            ),
        ),
        FactMessageKey.LONG_TERM_ARTIST_CONSISTENCY: ChineseFactTemplate(
            "艺术家持续出现",
            frozenset({"artist_name", "appearance_day_count", "listening_day_count"}),
            lambda data: (
                f"在这段记录期内，{_text(data, 'artist_name')} 出现在"
                f"{_integer(data, 'listening_day_count')}个听歌日中的"
                f"{_integer(data, 'appearance_day_count')}天。"
            ),
        ),
        FactMessageKey.LONG_TERM_LISTENING_CONCENTRATION: ChineseFactTemplate(
            "听歌时长集中度",
            frozenset({"top_five_duration_share"}),
            lambda data: (
                "这段记录期内，播放时长排名前五的艺术家占总听歌时长的"
                f"{_zh_percentage(data, 'top_five_duration_share')}。"
            ),
        ),
        FactMessageKey.LONG_TERM_ARTIST_BREADTH: ChineseFactTemplate(
            "艺术家覆盖广度",
            frozenset({"unique_artist_count", "listening_day_count", "single_day_artist_count"}),
            lambda data: (
                f"在{_integer(data, 'listening_day_count')}个有记录的听歌日中，"
                f"你听了{_zh_artists(data, 'unique_artist_count')}，"
                f"其中{_integer(data, 'single_day_artist_count')}位只出现在一天。"
            ),
        ),
        FactMessageKey.LONG_TERM_ARTIST_SHARE_EVOLUTION_INCREASED: ChineseFactTemplate(
            "艺人占比上升",
            frozenset({"artist_name", "previous_value", "current_value"}),
            lambda data: (
                f"与前一个30天周期相比，{_text(data, 'artist_name')}"
                "在可归因艺人听歌时长中的占比从"
                f"{_zh_percentage(data, 'previous_value')}上升到"
                f"{_zh_percentage(data, 'current_value')}。"
            ),
        ),
        FactMessageKey.LONG_TERM_ARTIST_SHARE_EVOLUTION_DECREASED: ChineseFactTemplate(
            "艺人占比下降",
            frozenset({"artist_name", "previous_value", "current_value"}),
            lambda data: (
                f"与前一个30天周期相比，{_text(data, 'artist_name')}"
                "在可归因艺人听歌时长中的占比从"
                f"{_zh_percentage(data, 'previous_value')}下降到"
                f"{_zh_percentage(data, 'current_value')}。"
            ),
        ),
        FactMessageKey.LONG_TERM_ARTIST_BREADTH_EVOLUTION_INCREASED: ChineseFactTemplate(
            "艺人广度增加",
            frozenset({"previous_value", "current_value"}),
            lambda data: (
                "与前一个30天周期相比，平均每个听歌日涉及的艺人数从"
                f"{_zh_artists_per_listening_day(data, 'previous_value')}"
                "增加到"
                f"{_zh_artists_per_listening_day(data, 'current_value')}。"
            ),
        ),
        FactMessageKey.LONG_TERM_ARTIST_BREADTH_EVOLUTION_DECREASED: ChineseFactTemplate(
            "艺人广度减少",
            frozenset({"previous_value", "current_value"}),
            lambda data: (
                "与前一个30天周期相比，平均每个听歌日涉及的艺人数从"
                f"{_zh_artists_per_listening_day(data, 'previous_value')}"
                "减少到"
                f"{_zh_artists_per_listening_day(data, 'current_value')}。"
            ),
        ),
        FactMessageKey.LONG_TERM_LISTENING_CONCENTRATION_EVOLUTION_INCREASED: (
            ChineseFactTemplate(
                "听歌集中度上升",
                frozenset({"previous_value", "current_value"}),
                lambda data: (
                    "与前一个30天周期相比，排名前五的艺人在"
                    "可归因艺人听歌时长中的占比从"
                    f"{_zh_percentage(data, 'previous_value')}上升到"
                    f"{_zh_percentage(data, 'current_value')}。"
                ),
            )
        ),
        FactMessageKey.LONG_TERM_LISTENING_CONCENTRATION_EVOLUTION_DECREASED: (
            ChineseFactTemplate(
                "听歌集中度下降",
                frozenset({"previous_value", "current_value"}),
                lambda data: (
                    "与前一个30天周期相比，排名前五的艺人在"
                    "可归因艺人听歌时长中的占比从"
                    f"{_zh_percentage(data, 'previous_value')}下降到"
                    f"{_zh_percentage(data, 'current_value')}。"
                ),
            )
        ),
    }
)


def ui_text(locale: SupportedLocale, key: UiMessageKey, **values: object) -> str:
    """Render one deterministic UI catalog message."""
    locale = require_supported_locale(locale)
    try:
        template = _UI_CATALOGS[locale][key]
    except (KeyError, TypeError) as error:
        raise MissingTranslationError(
            f"Missing UI translation for locale {locale!s}: {key!s}"
        ) from error
    try:
        return template.format(**values)
    except (KeyError, ValueError) as error:
        raise LocalizationError(
            f"Invalid values for UI translation {key!s}: {error}"
        ) from error


def chinese_fact_template(message_key: FactMessageKey) -> ChineseFactTemplate:
    """Return one complete Chinese fact template."""
    try:
        return _ZH_CN_FACT_TEMPLATES[message_key]
    except KeyError as error:
        raise MissingTranslationError(
            f"Missing zh-CN fact translation: {message_key!s}"
        ) from error


def validate_localization_catalogs(
    *,
    ui_catalogs: Mapping[SupportedLocale, Mapping[UiMessageKey, str]] | None = None,
    chinese_fact_templates: Mapping[FactMessageKey, ChineseFactTemplate] | None = None,
    ui_placeholder_contract: Mapping[UiMessageKey, frozenset[str]] | None = None,
) -> None:
    """Validate catalog completeness without mutating production mappings."""
    catalogs = ui_catalogs if ui_catalogs is not None else _UI_CATALOGS
    fact_templates = (
        chinese_fact_templates
        if chinese_fact_templates is not None
        else _ZH_CN_FACT_TEMPLATES
    )
    placeholder_contract = (
        ui_placeholder_contract
        if ui_placeholder_contract is not None
        else _UI_PLACEHOLDER_CONTRACT
    )
    if set(placeholder_contract) != set(UiMessageKey):
        missing = sorted(key.value for key in set(UiMessageKey) - set(placeholder_contract))
        extra = sorted(str(key) for key in set(placeholder_contract) - set(UiMessageKey))
        raise LocalizationError(
            "Invalid UI placeholder contract; "
            f"missing={missing}, extra={extra}."
        )
    if set(catalogs) != set(SupportedLocale):
        raise MissingTranslationError("UI catalogs must cover every supported locale.")
    required_ui_keys = set(UiMessageKey)
    for locale in SupportedLocale:
        keys = set(catalogs[locale])
        if keys != required_ui_keys:
            missing = sorted(key.value for key in required_ui_keys - keys)
            extra = sorted(str(key) for key in keys - required_ui_keys)
            raise MissingTranslationError(
                f"Invalid {locale.value} UI catalog; missing={missing}, extra={extra}."
            )
        if any(not isinstance(value, str) or not value for value in catalogs[locale].values()):
            raise LocalizationError(f"{locale.value} UI messages must be non-empty text.")
        for key in UiMessageKey:
            template = catalogs[locale][key]
            try:
                actual_fields = _format_fields(template)
            except ValueError as error:
                raise LocalizationError(
                    f"Invalid {locale.value} UI template {key.value}; "
                    f"malformed format string: {error}"
                ) from error
            expected_fields = placeholder_contract[key]
            if actual_fields != expected_fields:
                raise LocalizationError(
                    f"Invalid {locale.value} UI template {key.value}; "
                    f"expected placeholders={sorted(expected_fields)}, "
                    f"actual placeholders={sorted(actual_fields)}."
                )

    required_fact_keys = set(FactMessageKey)
    if set(fact_templates) != required_fact_keys:
        missing = sorted(key.value for key in required_fact_keys - set(fact_templates))
        extra = sorted(str(key) for key in set(fact_templates) - required_fact_keys)
        raise MissingTranslationError(
            f"Invalid zh-CN fact catalog; missing={missing}, extra={extra}."
        )
    for key, template in fact_templates.items():
        if not isinstance(template.title, str) or not template.title:
            raise LocalizationError(f"Invalid zh-CN fact template: {key.value}")
        if not isinstance(template.required_metadata, frozenset) or any(
            not isinstance(name, str) or not name
            for name in template.required_metadata
        ):
            raise LocalizationError(
                f"Invalid required metadata declaration: {key.value}"
            )
        if not callable(template.render_description):
            raise LocalizationError(f"Missing description renderer: {key.value}")


def _format_fields(template: str) -> frozenset[str]:
    """Return every replacement field, including nested format-spec fields."""
    fields: set[str] = set()
    for _literal, field_name, format_spec, _conversion in Formatter().parse(template):
        if field_name is not None:
            fields.add(field_name)
        if format_spec:
            fields.update(_format_fields(format_spec))
    return frozenset(fields)


def _text(data: Mapping[str, object], key: str) -> str:
    value = data[key]
    if not isinstance(value, str) or not value:
        raise LocalizationError(f"Fact metadata '{key}' must be non-empty text.")
    return value


def _integer(data: Mapping[str, object], key: str) -> int:
    value = data[key]
    if isinstance(value, bool) or not isinstance(value, int):
        raise LocalizationError(f"Fact metadata '{key}' must be an integer.")
    return value


def _number(data: Mapping[str, object], key: str) -> float:
    value = data[key]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise LocalizationError(f"Fact metadata '{key}' must be numeric.")
    return float(value)


def _zh_duration(data: Mapping[str, object], key: str) -> str:
    return format_prose_duration(_integer(data, key), SupportedLocale.ZH_CN)


def _zh_playbacks(data: Mapping[str, object], key: str) -> str:
    return format_playback_count(_integer(data, key), SupportedLocale.ZH_CN)


def _zh_percentage(data: Mapping[str, object], key: str) -> str:
    return format_percentage(_number(data, key), SupportedLocale.ZH_CN)


def _zh_listening_days(data: Mapping[str, object], key: str) -> str:
    return format_listening_day_count(_integer(data, key), SupportedLocale.ZH_CN)


def _zh_artists(data: Mapping[str, object], key: str) -> str:
    return format_artist_count(_integer(data, key), SupportedLocale.ZH_CN)


def _zh_artists_per_listening_day(
    data: Mapping[str, object], key: str
) -> str:
    return format_artists_per_listening_day(
        _number(data, key), SupportedLocale.ZH_CN
    )
