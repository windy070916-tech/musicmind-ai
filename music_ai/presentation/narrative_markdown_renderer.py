"""Markdown presentation for MusicMind's deterministic daily narrative."""

from music_ai.analytics.listening_profile import (
    RankedArtist,
    RankedGenre,
    RankedTrack,
)
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
from music_ai.visible_content import (
    VisibleProfileState,
    VisibleReportComposition,
    compose_visible_report,
)


def render_daily_narrative(
    narrative: DailyNarrative,
    *,
    locale: SupportedLocale = SupportedLocale.EN_US,
) -> str:
    """Compose and render one immutable Narrative contract."""
    return render_visible_report(compose_visible_report(narrative), locale=locale)


def render_visible_report(
    composition: VisibleReportComposition,
    *,
    locale: SupportedLocale = SupportedLocale.EN_US,
) -> str:
    """Render the exact locale-neutral selection used by the visible manifest."""
    sections = [f"# {ui_text(locale, UiMessageKey.DAILY_REPORT_TITLE)}"]
    if composition.subtitle is not None:
        sections.append(composition.subtitle)

    if composition.profile_state is VisibleProfileState.UNAVAILABLE:
        sections.extend(
            (
                f"## {ui_text(locale, UiMessageKey.LISTENING_OVERVIEW)}",
                ui_text(locale, UiMessageKey.LISTENING_UNAVAILABLE),
            )
        )
    elif composition.profile_state is VisibleProfileState.NO_ACTIVITY:
        sections.extend(
            (
                f"## {ui_text(locale, UiMessageKey.LISTENING_OVERVIEW)}",
                ui_text(locale, UiMessageKey.NO_LISTENING_ACTIVITY),
            )
        )
    else:
        profile = composition.profile_summary
        if profile is None:  # Protected by VisibleReportComposition validation.
            raise ValueError("Active visible report composition requires a summary.")
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

        artists = composition.top_artists
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

        tracks = composition.top_tracks
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

        genres = composition.top_genres
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

    if composition.recent_observations:
        sections.extend(
            (
                f"## {ui_text(locale, UiMessageKey.RECENTLY)}",
                "\n".join(
                    f"- {localize_fact(fact, locale).description}"
                    for fact in composition.recent_observations
                ),
            )
        )

    if composition.long_term_observations:
        sections.extend(
            (
                f"## {ui_text(locale, UiMessageKey.OVER_TIME)}",
                "\n".join(
                    f"- {localize_fact(fact, locale).description}"
                    for fact in composition.long_term_observations
                ),
            )
        )

    if composition.highlights:
        sections.extend(
            (
                f"## {ui_text(locale, UiMessageKey.HIGHLIGHTS)}",
                "\n".join(
                    f"- {localize_fact(fact, locale).description}"
                    for fact in composition.highlights
                ),
            )
        )

    return "\n\n".join(sections)


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
