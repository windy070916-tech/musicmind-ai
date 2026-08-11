"""Stable semantic message identities for built-in MusicMind facts."""

from enum import StrEnum


class FactMessageKey(StrEnum):
    """Identify the wording branch already selected by Knowledge."""

    DAILY_LISTENING_TIME = "daily.listening_time"
    DAILY_PLAYBACK_COUNT = "daily.playback_count"
    DAILY_TOP_ARTIST = "daily.top_artist"
    DAILY_TOP_SONG = "daily.top_song"

    TREND_LISTENING_TIME_ZERO_BASELINE = "trend.listening_time.zero_baseline"
    TREND_LISTENING_TIME_INCREASED = "trend.listening_time.increased"
    TREND_LISTENING_TIME_DECREASED = "trend.listening_time.decreased"
    TREND_PLAYBACK_MORE = "trend.playback.more"
    TREND_PLAYBACK_FEWER = "trend.playback.fewer"
    TREND_TOP_ARTIST_CHANGED = "trend.top_artist.changed"
    TREND_TOP_SONG_CHANGED = "trend.top_song.changed"

    INSIGHT_FOCUSED_LISTENING = "insight.focused_listening"
    INSIGHT_HEAVY_ZERO_BASELINE = "insight.heavy.zero_baseline"
    INSIGHT_HEAVY = "insight.heavy"
    INSIGHT_LIGHT = "insight.light"
    INSIGHT_STABLE_TOP_ARTIST = "insight.stable_top_artist"

    RECENT_ARTIST_CONTINUITY = "recent.artist_continuity"
    RECENT_ARTIST_EMERGENCE = "recent.artist_emergence"

    LONG_TERM_ARTIST_CONSISTENCY = "long_term.artist_consistency"
    LONG_TERM_LISTENING_CONCENTRATION = "long_term.listening_concentration"
    LONG_TERM_ARTIST_BREADTH = "long_term.artist_breadth"
    LONG_TERM_ARTIST_SHARE_EVOLUTION_INCREASED = (
        "long_term.artist_share_evolution.increased"
    )
    LONG_TERM_ARTIST_SHARE_EVOLUTION_DECREASED = (
        "long_term.artist_share_evolution.decreased"
    )
    LONG_TERM_ARTIST_BREADTH_EVOLUTION_INCREASED = (
        "long_term.artist_breadth_evolution.increased"
    )
    LONG_TERM_ARTIST_BREADTH_EVOLUTION_DECREASED = (
        "long_term.artist_breadth_evolution.decreased"
    )
    LONG_TERM_LISTENING_CONCENTRATION_EVOLUTION_INCREASED = (
        "long_term.listening_concentration_evolution.increased"
    )
    LONG_TERM_LISTENING_CONCENTRATION_EVOLUTION_DECREASED = (
        "long_term.listening_concentration_evolution.decreased"
    )
