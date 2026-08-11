"""Public models for MusicMind's reusable knowledge layer."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import IntEnum, StrEnum
from types import MappingProxyType

from music_ai.knowledge.message_keys import FactMessageKey


class FactCategory(StrEnum):
    """Stable categories for reusable knowledge facts."""

    LISTENING_TIME = "listening_time"
    PLAYBACK_COUNT = "playback_count"
    TOP_ARTIST = "top_artist"
    TOP_SONG = "top_song"
    LISTENING_TIME_CHANGE = "listening_time_change"
    PLAYBACK_COUNT_CHANGE = "playback_count_change"
    TOP_ARTIST_CHANGE = "top_artist_change"
    TOP_SONG_CHANGE = "top_song_change"
    FOCUSED_LISTENING = "focused_listening"
    HEAVY_LISTENING = "heavy_listening"
    LIGHT_LISTENING = "light_listening"
    STABLE_FAVORITE = "stable_favorite"
    ARTIST_CONTINUITY = "artist_continuity"
    ARTIST_EMERGENCE = "artist_emergence"
    ARTIST_CONSISTENCY = "artist_consistency"
    LISTENING_CONCENTRATION = "listening_concentration"
    ARTIST_BREADTH = "artist_breadth"
    ARTIST_DURATION_SHARE_EVOLUTION = "artist_duration_share_evolution"
    ARTIST_BREADTH_EVOLUTION = "artist_breadth_evolution"
    LISTENING_CONCENTRATION_EVOLUTION = "listening_concentration_evolution"


class InsightType(StrEnum):
    """High-level grouping for how a fact should be consumed."""

    DAILY_LISTENING = "daily_listening"
    TREND = "trend"
    BEHAVIOR = "behavior"


class ImportanceLevel(IntEnum):
    """Relative display priority for generated knowledge facts."""

    LOW = 1
    MEDIUM = 2
    HIGH = 3


class FactSource(StrEnum):
    """Known sources used to produce a knowledge fact."""

    LISTENING_SUMMARY = "listening_summary"
    LISTENING_SUMMARY_COMPARISON = "listening_summary_comparison"
    RECENT_LISTENING_EVIDENCE = "recent_listening_evidence"
    LONG_TERM_LISTENING_EVIDENCE = "long_term_listening_evidence"
    LONG_TERM_EVOLUTION_EVIDENCE = "long_term_evolution_evidence"


class FactTimeHorizon(StrEnum):
    """Explicit period horizon represented by a knowledge fact."""

    DAILY = "daily"
    RECENT = "recent"
    LONG_TERM = "long_term"


@dataclass(frozen=True, slots=True)
class KnowledgeFact:
    """One presentation-independent fact interpreted from analytics output.

    Optional fields provide stable extension points for later knowledge features
    without changing the core fact contract.
    """

    category: FactCategory | str
    importance: ImportanceLevel | int
    title: str
    description: str
    metadata: Mapping[str, object] = field(default_factory=dict)
    confidence: float | None = None
    tags: tuple[str, ...] = ()
    source: FactSource | str | None = None
    date_range: tuple[str, str] | None = None
    severity: str | None = None
    insight_type: InsightType | str | None = None
    time_horizon: FactTimeHorizon | str = FactTimeHorizon.DAILY
    message_key: FactMessageKey | None = field(default=None, compare=False)

    def __post_init__(self) -> None:
        """Protect metadata so a fact remains immutable after construction."""
        if self.message_key is not None and not isinstance(
            self.message_key, FactMessageKey
        ):
            raise TypeError("message_key must be FactMessageKey or None.")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
