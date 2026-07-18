"""Transform listening analytics into reusable knowledge facts."""

from music_ai.analytics.listening_analytics import ListeningSummary
from music_ai.knowledge.models import KnowledgeFact


class KnowledgeEngine:
    """Interpret an existing listening summary without performing analytics."""

    def __init__(self, summary: ListeningSummary):
        """Create a knowledge engine for one already-calculated summary."""
        self._summary = summary

    def generate_facts(self) -> list[KnowledgeFact]:
        """Return the Sprint 1 facts supported by the supplied summary."""
        facts = [
            KnowledgeFact(
                category="listening_time",
                importance=2,
                title="Listening Time",
                description=(
                    "You listened to music for "
                    f"{_format_duration(self._summary.total_listening_time_ms)} today."
                ),
                metadata={
                    "total_listening_time_ms": self._summary.total_listening_time_ms,
                },
                source="listening_summary",
                insight_type="daily_listening",
            ),
            KnowledgeFact(
                category="playback_count",
                importance=2,
                title="Playback Count",
                description=f"You played {self._summary.playback_count} tracks today.",
                metadata={"playback_count": self._summary.playback_count},
                source="listening_summary",
                insight_type="daily_listening",
            ),
        ]

        if self._summary.top_artists:
            top_artist = self._summary.top_artists[0]
            facts.append(
                KnowledgeFact(
                    category="top_artist",
                    importance=3,
                    title="Top Artist",
                    description=f"Today's top artist is {top_artist.name}.",
                    metadata={
                        "artist_name": top_artist.name,
                        "listening_time_ms": top_artist.listening_time_ms,
                    },
                    source="listening_summary",
                    insight_type="daily_listening",
                )
            )

        if self._summary.top_songs:
            top_song = self._summary.top_songs[0]
            facts.append(
                KnowledgeFact(
                    category="top_song",
                    importance=3,
                    title="Top Song",
                    description=f"Today's top song is {top_song.name}.",
                    metadata={
                        "song_name": top_song.name,
                        "artist_name": top_song.artist,
                        "listening_time_ms": top_song.listening_time_ms,
                    },
                    source="listening_summary",
                    insight_type="daily_listening",
                )
            )

        return facts


def _format_duration(duration_ms: int) -> str:
    """Format milliseconds as a readable whole-minute duration."""
    total_minutes = duration_ms // 60_000
    hours, minutes = divmod(total_minutes, 60)

    parts: list[str] = []
    if hours:
        parts.append(f"{hours} hour" if hours == 1 else f"{hours} hours")
    if minutes or not parts:
        parts.append(f"{minutes} minute" if minutes == 1 else f"{minutes} minutes")
    return " and ".join(parts)
