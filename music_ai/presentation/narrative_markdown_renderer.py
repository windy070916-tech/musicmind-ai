"""Markdown presentation for MusicMind's deterministic daily narrative."""

from collections.abc import Iterable

from music_ai.knowledge.models import FactCategory, InsightType, KnowledgeFact
from music_ai.narrative.models import DailyNarrative


_BASIC_DAILY_CATEGORIES = {
    FactCategory.LISTENING_TIME,
    FactCategory.PLAYBACK_COUNT,
    FactCategory.TOP_ARTIST,
    FactCategory.TOP_SONG,
}


def render_daily_narrative(narrative: DailyNarrative) -> str:
    """Render one immutable Narrative contract as deterministic Markdown."""
    sections = ["# MusicMind Daily"]
    subtitle = _subtitle(narrative.headline)
    if subtitle is not None:
        sections.append(subtitle)

    profile = narrative.listening_profile
    if profile is None:
        sections.extend(("## Listening Overview", "Listening data is unavailable."))
    elif profile.playback_count == 0:
        sections.extend(
            ("## Listening Overview", "No listening activity was recorded today.")
        )
    else:
        sections.extend(
            (
                "## Listening Overview",
                "\n".join(
                    (
                        "- Estimated listening duration: "
                        f"{_format_duration(profile.total_estimated_listening_duration_ms)}",
                        f"- Playback count: {_format_count(profile.playback_count, 'play')}",
                        f"- Unique tracks: {_format_count(profile.unique_track_count, 'track')}",
                    )
                ),
            )
        )

        artists = profile.top_artists[:3]
        if artists:
            sections.extend(
                (
                    "## Top Artists",
                    "\n".join(
                        f"{rank}. {artist.name} — estimated "
                        f"{_format_duration(artist.estimated_listening_duration_ms)} · "
                        f"{_format_count(artist.play_count, 'play')} · "
                        f"{_format_percentage(artist.share)}"
                        for rank, artist in enumerate(artists, start=1)
                    ),
                )
            )

        tracks = profile.top_tracks[:5]
        if tracks:
            sections.extend(
                (
                    "## Top Tracks",
                    "\n".join(
                        f"{rank}. {track.name} — "
                        f"{', '.join(track.artist_names) or 'Unknown artist'} — estimated "
                        f"{_format_duration(track.estimated_listening_duration_ms)} · "
                        f"{_format_count(track.play_count, 'play')} · "
                        f"{_format_percentage(track.share)}"
                        for rank, track in enumerate(tracks, start=1)
                    ),
                )
            )

        genres = profile.top_genres[:3]
        if genres:
            sections.extend(
                (
                    "## Genre Overview",
                    "\n".join(
                        f"{rank}. {genre.genre} — estimated "
                        f"{_format_duration(genre.estimated_listening_duration_ms)} · "
                        f"{_format_percentage(genre.share)}"
                        for rank, genre in enumerate(genres, start=1)
                    ),
                )
            )

    if narrative.recent_thread is not None:
        sections.extend(
            (
                "## Recently",
                "\n".join(
                    f"- {fact.description}"
                    for fact in narrative.recent_thread.observations
                ),
            )
        )

    highlights = tuple(_eligible_highlights(narrative.highlights))[:3]
    if highlights:
        sections.extend(
            (
                "## Highlights",
                "\n".join(f"- {fact.description}" for fact in highlights),
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


def _format_duration(duration_ms: int) -> str:
    """Format estimated milliseconds as compact whole hours and minutes."""
    total_minutes = duration_ms // 60_000
    hours, minutes = divmod(total_minutes, 60)
    if hours and minutes:
        return f"{hours}h {minutes}m"
    if hours:
        return f"{hours}h"
    return f"{minutes}m"


def _format_count(value: int, singular: str) -> str:
    """Format a count with its singular or plural label."""
    label = singular if value == 1 else f"{singular}s"
    return f"{value} {label}"


def _format_percentage(share: float) -> str:
    """Format a 0-1 share as a whole percentage."""
    return f"{share:.0%}"
