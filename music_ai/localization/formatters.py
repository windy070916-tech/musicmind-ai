"""Deterministic locale-aware formatting for MusicMind presentation."""

from collections.abc import Iterable
from decimal import Decimal, ROUND_HALF_UP, localcontext

from music_ai.localization.models import SupportedLocale, require_supported_locale


def format_compact_duration(duration_ms: int, locale: SupportedLocale) -> str:
    """Format milliseconds for ranked deterministic report rows."""
    locale = require_supported_locale(locale)
    total_minutes = _whole_minutes(duration_ms)
    hours, minutes = divmod(total_minutes, 60)
    if locale is SupportedLocale.ZH_CN:
        if hours and minutes:
            return f"{hours}小时{minutes}分钟"
        if hours:
            return f"{hours}小时"
        return f"{minutes}分钟"
    if hours and minutes:
        return f"{hours}h {minutes}m"
    if hours:
        return f"{hours}h"
    return f"{minutes}m"


def format_prose_duration(duration_ms: int, locale: SupportedLocale) -> str:
    """Format milliseconds for a complete fact sentence."""
    locale = require_supported_locale(locale)
    if locale is SupportedLocale.ZH_CN:
        return format_compact_duration(duration_ms, locale)
    total_minutes = _whole_minutes(duration_ms)
    hours, minutes = divmod(total_minutes, 60)
    parts: list[str] = []
    if hours:
        parts.append(f"{hours} hour" if hours == 1 else f"{hours} hours")
    if minutes or not parts:
        parts.append(f"{minutes} minute" if minutes == 1 else f"{minutes} minutes")
    return " and ".join(parts)


def format_playback_count(value: int, locale: SupportedLocale) -> str:
    """Format a playback-event count."""
    locale = require_supported_locale(locale)
    count = _non_negative_count(value)
    if locale is SupportedLocale.ZH_CN:
        return f"{count}次"
    return f"{count} play" if count == 1 else f"{count} plays"


def format_track_count(value: int, locale: SupportedLocale) -> str:
    """Format a unique-track or song count."""
    locale = require_supported_locale(locale)
    count = _non_negative_count(value)
    if locale is SupportedLocale.ZH_CN:
        return f"{count}首"
    return f"{count} track" if count == 1 else f"{count} tracks"


def format_artist_count(value: int, locale: SupportedLocale) -> str:
    """Format an artist count with the locale's classifier."""
    locale = require_supported_locale(locale)
    count = _non_negative_count(value)
    if locale is SupportedLocale.ZH_CN:
        return f"{count}位艺术家"
    return f"{count} artist" if count == 1 else f"{count} artists"


def format_listening_day_count(value: int, locale: SupportedLocale) -> str:
    """Format a listening-day count."""
    locale = require_supported_locale(locale)
    count = _non_negative_count(value)
    if locale is SupportedLocale.ZH_CN:
        return f"{count}个听歌日"
    return f"{count} listening day" if count == 1 else f"{count} listening days"


def format_percentage(share: float, locale: SupportedLocale) -> str:
    """Format a zero-to-one share as a whole percentage."""
    require_supported_locale(locale)
    if isinstance(share, bool) or not isinstance(share, (int, float)):
        raise TypeError("share must be numeric.")
    return f"{share:.0%}"


def format_artists_per_listening_day(
    value: int | float,
    locale: SupportedLocale,
) -> str:
    """Format an artist-breadth ratio with deterministic decimal rounding."""
    require_supported_locale(locale)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("artists_per_listening_day must be numeric.")
    decimal_value = Decimal(value) if isinstance(value, int) else Decimal(str(value))
    if not decimal_value.is_finite():
        raise ValueError("artists_per_listening_day must be finite.")
    if decimal_value < 0:
        raise ValueError("artists_per_listening_day must be non-negative.")
    digits = len(decimal_value.as_tuple().digits)
    integer_places = max(decimal_value.as_tuple().exponent, 0)
    with localcontext() as context:
        context.prec = max(28, digits + integer_places + 2)
        rounded = decimal_value.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    if rounded == 0:
        rounded = Decimal("0.0")
    return format(rounded, ".1f")


def join_display_names(names: Iterable[str], locale: SupportedLocale) -> str:
    """Join opaque display names without translating their contents."""
    locale = require_supported_locale(locale)
    separator = "、" if locale is SupportedLocale.ZH_CN else ", "
    return separator.join(names)


def _whole_minutes(duration_ms: int) -> int:
    if isinstance(duration_ms, bool) or not isinstance(duration_ms, int):
        raise TypeError("duration_ms must be an integer.")
    if duration_ms < 0:
        raise ValueError("duration_ms must be non-negative.")
    return duration_ms // 60_000


def _non_negative_count(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("count must be an integer.")
    if value < 0:
        raise ValueError("count must be non-negative.")
    return value
