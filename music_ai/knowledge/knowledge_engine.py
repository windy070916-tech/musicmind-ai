"""Transform listening analytics into reusable knowledge facts."""

from music_ai.analytics.listening_analytics import ListeningSummary
from music_ai.knowledge.models import KnowledgeFact


class KnowledgeEngine:
    """Interpret listening summaries without performing analytics."""

    def __init__(
        self,
        current_summary: ListeningSummary,
        previous_summary: ListeningSummary | None = None,
    ):
        """Create an engine for a current summary and an optional comparison period."""
        self._current_summary = current_summary
        self._previous_summary = previous_summary

    def generate_daily_facts(self) -> list[KnowledgeFact]:
        """Return the daily facts supported by the current summary."""
        facts = [
            KnowledgeFact(
                category="listening_time",
                importance=2,
                title="Listening Time",
                description=(
                    "You listened to music for "
                    f"{_format_duration(self._current_summary.total_listening_time_ms)} today."
                ),
                metadata={
                    "total_listening_time_ms": self._current_summary.total_listening_time_ms,
                },
                source="listening_summary",
                insight_type="daily_listening",
            ),
            KnowledgeFact(
                category="playback_count",
                importance=2,
                title="Playback Count",
                description=f"You played {self._current_summary.playback_count} tracks today.",
                metadata={"playback_count": self._current_summary.playback_count},
                source="listening_summary",
                insight_type="daily_listening",
            ),
        ]

        if self._current_summary.top_artists:
            top_artist = self._current_summary.top_artists[0]
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

        if self._current_summary.top_songs:
            top_song = self._current_summary.top_songs[0]
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

    def generate_trend_facts(self) -> list[KnowledgeFact]:
        """Return facts that interpret changes from the previous to current period.

        A previous summary is optional so daily facts can be generated for any
        standalone period. Trend generation requires one and reports no fact for
        values that did not change.
        """
        if self._previous_summary is None:
            raise ValueError("previous_summary is required to generate trend facts.")

        previous = self._previous_summary
        current = self._current_summary
        facts: list[KnowledgeFact] = []

        listening_time_fact = _listening_time_trend_fact(
            previous.total_listening_time_ms,
            current.total_listening_time_ms,
        )
        if listening_time_fact is not None:
            facts.append(listening_time_fact)

        playback_count_fact = _playback_count_trend_fact(
            previous.playback_count,
            current.playback_count,
        )
        if playback_count_fact is not None:
            facts.append(playback_count_fact)

        if previous.top_artists and current.top_artists:
            previous_artist = previous.top_artists[0]
            current_artist = current.top_artists[0]
            if previous_artist.name != current_artist.name:
                facts.append(
                    KnowledgeFact(
                        category="top_artist_change",
                        importance=3,
                        title="Top Artist Changed",
                        description=(
                            "Today's top artist changed from "
                            f"{previous_artist.name} to {current_artist.name}."
                        ),
                        metadata={
                            "previous_value": previous_artist.name,
                            "current_value": current_artist.name,
                        },
                        source="listening_summary_comparison",
                        insight_type="trend",
                    )
                )

        if previous.top_songs and current.top_songs:
            previous_song = previous.top_songs[0]
            current_song = current.top_songs[0]
            if (previous_song.name, previous_song.artist) != (
                current_song.name,
                current_song.artist,
            ):
                facts.append(
                    KnowledgeFact(
                        category="top_song_change",
                        importance=3,
                        title="Top Song Changed",
                        description=(
                            "Today's top song changed from "
                            f"{previous_song.name} to {current_song.name}."
                        ),
                        metadata={
                            "previous_value": previous_song.name,
                            "current_value": current_song.name,
                            "previous_artist": previous_song.artist,
                            "current_artist": current_song.artist,
                        },
                        source="listening_summary_comparison",
                        insight_type="trend",
                    )
                )

        return facts

    def generate_facts(self) -> list[KnowledgeFact]:
        """Return daily facts; retained as a compatibility alias for Sprint 1."""
        return self.generate_daily_facts()


def _listening_time_trend_fact(
    previous_value: int, current_value: int
) -> KnowledgeFact | None:
    """Describe a listening-time change, including the zero-baseline case."""
    if previous_value == current_value:
        return None

    change = current_value - previous_value
    metadata: dict[str, int | float | None] = {
        "previous_value": previous_value,
        "current_value": current_value,
        "percentage_change": None,
    }
    if previous_value == 0:
        return KnowledgeFact(
            category="listening_time_change",
            importance=2,
            title="Listening Time Increased",
            description=(
                "Listening time increased from 0 minutes to "
                f"{_format_duration(current_value)} compared with yesterday."
            ),
            metadata=metadata,
            source="listening_summary_comparison",
            insight_type="trend",
        )

    percentage_change = round(abs(change) / previous_value * 100)
    metadata["percentage_change"] = percentage_change if change > 0 else -percentage_change
    direction = "increased" if change > 0 else "decreased"
    return KnowledgeFact(
        category="listening_time_change",
        importance=2,
        title=f"Listening Time {direction.title()}",
        description=(
            f"Listening time {direction} by {percentage_change}% compared with yesterday."
        ),
        metadata=metadata,
        source="listening_summary_comparison",
        insight_type="trend",
    )


def _playback_count_trend_fact(previous_value: int, current_value: int) -> KnowledgeFact | None:
    """Describe a playback-count change."""
    if previous_value == current_value:
        return None

    change = current_value - previous_value
    track_label = "track" if abs(change) == 1 else "tracks"
    comparison = "more" if change > 0 else "fewer"
    return KnowledgeFact(
        category="playback_count_change",
        importance=2,
        title="Playback Count Changed",
        description=(
            f"You played {abs(change)} {comparison} {track_label} than yesterday."
        ),
        metadata={
            "previous_value": previous_value,
            "current_value": current_value,
            "change": change,
        },
        source="listening_summary_comparison",
        insight_type="trend",
    )


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
