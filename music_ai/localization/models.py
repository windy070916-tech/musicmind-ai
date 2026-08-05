"""Public contracts and focused errors for MusicMind localization."""

from enum import StrEnum


class SupportedLocale(StrEnum):
    """Locales supported for one MusicMind application run."""

    ZH_CN = "zh-CN"
    EN_US = "en-US"


class UiMessageKey(StrEnum):
    """Stable identities for deterministic user-interface copy."""

    DAILY_REPORT_TITLE = "report.daily.title"
    LISTENING_OVERVIEW = "report.section.listening_overview"
    TOP_ARTISTS = "report.section.top_artists"
    TOP_TRACKS = "report.section.top_tracks"
    GENRE_OVERVIEW = "report.section.genre_overview"
    RECENTLY = "report.section.recently"
    OVER_TIME = "report.section.over_time"
    HIGHLIGHTS = "report.section.highlights"
    LISTENING_UNAVAILABLE = "report.empty.listening_unavailable"
    NO_LISTENING_ACTIVITY = "report.empty.no_listening_activity"
    UNKNOWN_ARTIST = "report.fallback.unknown_artist"
    ESTIMATED_LISTENING_DURATION = "report.metric.estimated_duration"
    PLAYBACK_COUNT = "report.metric.playback_count"
    UNIQUE_TRACKS = "report.metric.unique_tracks"
    RANKED_ESTIMATED_DURATION = "report.ranked.estimated_duration"
    RANKED_PLAYBACK_COUNT = "report.ranked.playback_count"

    SPOTIFY_LOGIN_SUCCESS = "runtime.spotify_login_success"
    IMPORTED_PLAYBACK_RECORDS = "runtime.imported_playback_records"
    DATABASE_UPDATED = "runtime.database_updated"
    FIRST_SYNCHRONIZATION = "runtime.first_synchronization"
    DOWNLOADING_RECENT_HISTORY = "runtime.downloading_recent_history"
    LAST_SYNCHRONIZED_PLAYBACK = "runtime.last_synchronized_playback"
    CHECKING_SPOTIFY = "runtime.checking_spotify"
    FOUND_NEW_PLAYBACK_RECORDS = "runtime.found_new_playback_records"
    DAILY_FACTS_LABEL = "runtime.daily_facts_label"
    DAILY_TRENDS_LABEL = "runtime.daily_trends_label"
    INSIGHT_FACTS_LABEL = "runtime.insight_facts_label"
    NO_DAILY_CHANGES = "runtime.no_daily_changes"
    NO_DAILY_INSIGHTS = "runtime.no_daily_insights"
    AI_REPORT_LABEL = "runtime.ai_report_label"

    OAUTH_OPEN_URL = "oauth.open_url"
    OAUTH_UNKNOWN_CALLBACK_PATH = "oauth.unknown_callback_path"
    OAUTH_AUTHORIZATION_FAILED = "oauth.authorization_failed"
    OAUTH_INVALID_STATE = "oauth.invalid_state"
    OAUTH_MISSING_CODE = "oauth.missing_code"
    OAUTH_SUCCESS = "oauth.success"

    AI_REPORT_TITLE = "ai.title"
    AI_GREETING = "ai.section.greeting"
    AI_LISTENING_SUMMARY = "ai.section.listening_summary"
    AI_TREND = "ai.section.trend"
    AI_INSIGHT = "ai.section.insight"
    AI_RECOMMENDATION = "ai.section.recommendation"
    AI_CLOSING = "ai.section.closing"

    CLI_LOCALE_HELP = "cli.locale_help"


class LocalizationError(RuntimeError):
    """Base error for deterministic localization failures."""


class MissingTranslationError(LocalizationError):
    """Raised when a required catalog entry is unavailable."""


class UnsupportedLocaleError(ValueError):
    """Raised for an explicit locale outside the supported set."""

    def __init__(self, value: object) -> None:
        normalized = str(value).strip()
        super().__init__(
            f"Unsupported locale: {normalized}\n"
            "Supported locales: zh-CN, en-US"
        )


def parse_supported_locale(value: object) -> SupportedLocale:
    """Validate one raw external locale value after trimming whitespace."""
    normalized = str(value).strip()
    try:
        return SupportedLocale(normalized)
    except ValueError as error:
        raise UnsupportedLocaleError(normalized) from error


def require_supported_locale(value: object) -> SupportedLocale:
    """Reject raw locale strings after the external resolution boundary."""
    if not isinstance(value, SupportedLocale):
        raise TypeError("locale must be SupportedLocale.")
    return value
