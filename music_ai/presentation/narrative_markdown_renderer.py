"""Markdown presentation for MusicMind's deterministic daily narrative."""

from collections.abc import Iterable

from music_ai.analytics.listening_profile import (
    RankedArtist,
    RankedGenre,
    RankedTrack,
)
from music_ai.knowledge.models import FactCategory, InsightType, KnowledgeFact
from music_ai.localization.catalog import ui_text
from music_ai.localization.fact_localizer import localize_fact
from music_ai.localization.formatters import (
    format_compact_duration,
    format_percentage,
    format_playback_count,
    format_track_count,
    join_display_names,
)
from music_ai.localization.models import SupportedLocale, UiMessageKey
from music_ai.narrative.models import DailyNarrative


_BASIC_DAILY_CATEGORIES = {
    FactCategory.LISTENING_TIME,
    FactCategory.PLAYBACK_COUNT,
    FactCategory.TOP_ARTIST,
    FactCategory.TOP_SONG,
}


def render_daily_narrative(
    narrative: DailyNarrative,
    *,
    locale: SupportedLocale = SupportedLocale.EN_US,
) -> str:
    """Render one immutable Narrative contract as deterministic Markdown."""
    sections = [f"# {ui_text(locale, UiMessageKey.DAILY_REPORT_TITLE)}"]
    subtitle = _subtitle(narrative.headline)
    if subtitle is not None:
        sections.append(subtitle)

    profile = narrative.listening_profile
    if profile is None:
        sections.extend(
            (
                f"## {ui_text(locale, UiMessageKey.LISTENING_OVERVIEW)}",
                ui_text(locale, UiMessageKey.LISTENING_UNAVAILABLE),
            )
        )
    elif profile.playback_count == 0:
        sections.extend(
            (
                f"## {ui_text(locale, UiMessageKey.LISTENING_OVERVIEW)}",
                ui_text(locale, UiMessageKey.NO_LISTENING_ACTIVITY),
            )
        )
    else:
        sections.extend(
            (
                f"## {ui_text(locale, UiMessageKey.LISTENING_OVERVIEW)}",
                "\n".join(
                    (
                        "- "
                        + ui_text(
                            locale,
                            UiMessageKey.ESTIMATED_LISTENING_DURATION,
                            duration=format_compact_duration(
                                profile.total_estimated_listening_duration_ms,
                                locale,
                            ),
                        ),
                        "- "
                        + ui_text(
                            locale,
                            UiMessageKey.PLAYBACK_COUNT,
                            count=format_playback_count(profile.playback_count, locale),
                        ),
                        "- "
                        + ui_text(
                            locale,
                            UiMessageKey.UNIQUE_TRACKS,
                            count=format_track_count(profile.unique_track_count, locale),
                        ),
                    )
                ),
            )
        )

        artists = profile.top_artists[:3]
        if artists:
            sections.extend(
                (
                    f"## {ui_text(locale, UiMessageKey.TOP_ARTISTS)}",
                    "\n".join(
                        _ranked_artist_line(rank, artist, locale)
                        for rank, artist in enumerate(artists, start=1)
                    ),
                )
            )

        tracks = profile.top_tracks[:5]
        if tracks:
            sections.extend(
                (
                    f"## {ui_text(locale, UiMessageKey.TOP_TRACKS)}",
                    "\n".join(
                        _ranked_track_line(rank, track, locale)
                        for rank, track in enumerate(tracks, start=1)
                    ),
                )
            )

        genres = profile.top_genres[:3]
        if genres:
            sections.extend(
                (
                    f"## {ui_text(locale, UiMessageKey.GENRE_OVERVIEW)}",
                    "\n".join(
                        _ranked_genre_line(rank, genre, locale)
                        for rank, genre in enumerate(genres, start=1)
                    ),
                )
            )

    if narrative.recent_thread is not None:
        sections.extend(
            (
                f"## {ui_text(locale, UiMessageKey.RECENTLY)}",
                "\n".join(
                    f"- {localize_fact(fact, locale).description}"
                    for fact in narrative.recent_thread.observations
                ),
            )
        )

    if narrative.long_term_thread is not None:
        sections.extend(
            (
                f"## {ui_text(locale, UiMessageKey.OVER_TIME)}",
                "\n".join(
                    f"- {localize_fact(fact, locale).description}"
                    for fact in narrative.long_term_thread.observations
                ),
            )
        )

    highlights = tuple(_eligible_highlights(narrative.highlights))[:3]
    if highlights:
        sections.extend(
            (
                f"## {ui_text(locale, UiMessageKey.HIGHLIGHTS)}",
                "\n".join(
                    f"- {localize_fact(fact, locale).description}"
                    for fact in highlights
                ),
            )
        )

    return "\n\n".join(sections)


def _eligible_highlights(facts: Iterable[KnowledgeFact]) -> Iterable[KnowledgeFact]:
    """Yield already-selected facts that do not duplicate deterministic sections."""
    for fact in facts:
        if fact.insight_type == InsightType.DAILY_LISTENING:
            continue
        if fact.category in _BASIC_DAILY_CATEGORIES:
            continue
        yield fact


def _subtitle(headline: str) -> str | None:
    """Return meaningful nonduplicate Narrative headline text."""
    normalized = headline.strip()
    if not normalized or normalized.casefold() in {"daily listening", "musicmind daily"}:
        return None
    return normalized


def _display_artist_name(artist: RankedArtist, locale: SupportedLocale) -> str:
    """Localize the Analytics-owned unknown-artist sentinel only."""
    if artist.spotify_artist_id is None and artist.name == "Unknown artist":
        return ui_text(locale, UiMessageKey.UNKNOWN_ARTIST)
    return artist.name


def _ranked_artist_line(
    rank: int,
    artist: RankedArtist,
    locale: SupportedLocale,
) -> str:
    name = _display_artist_name(artist, locale)
    duration = _ranked_duration(artist.estimated_listening_duration_ms, locale)
    count = _ranked_playback(artist.play_count, locale)
    percentage = format_percentage(artist.share, locale)
    return f"{rank}. {name} — {duration} · {count} · {percentage}"


def _ranked_track_line(
    rank: int,
    track: RankedTrack,
    locale: SupportedLocale,
) -> str:
    names = join_display_names(track.artist_names, locale)
    artist_names = names or ui_text(locale, UiMessageKey.UNKNOWN_ARTIST)
    duration = _ranked_duration(track.estimated_listening_duration_ms, locale)
    count = _ranked_playback(track.play_count, locale)
    return (
        f"{rank}. {track.name} — {artist_names} — {duration} · {count} · "
        f"{format_percentage(track.share, locale)}"
    )


def _ranked_genre_line(
    rank: int,
    genre: RankedGenre,
    locale: SupportedLocale,
) -> str:
    duration = _ranked_duration(genre.estimated_listening_duration_ms, locale)
    percentage = format_percentage(genre.share, locale)
    return f"{rank}. {genre.genre} — {duration} · {percentage}"


def _ranked_duration(duration_ms: int, locale: SupportedLocale) -> str:
    return ui_text(
        locale,
        UiMessageKey.RANKED_ESTIMATED_DURATION,
        duration=format_compact_duration(duration_ms, locale),
    )


def _ranked_playback(count: int, locale: SupportedLocale) -> str:
    return ui_text(
        locale,
        UiMessageKey.RANKED_PLAYBACK_COUNT,
        count=format_playback_count(count, locale),
    )
