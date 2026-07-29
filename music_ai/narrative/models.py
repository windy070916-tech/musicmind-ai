"""Immutable public contracts produced by the Narrative layer."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from music_ai.analytics.listening_profile import DailyListeningProfile
from music_ai.knowledge.models import FactTimeHorizon, KnowledgeFact


@dataclass(frozen=True, slots=True)
class RecentListeningThread:
    """A small, presentation-independent set of recent observations."""

    observations: tuple[KnowledgeFact, ...] = ()

    def __post_init__(self) -> None:
        """Snapshot and validate the bounded recent-fact collection."""
        object.__setattr__(self, "observations", tuple(self.observations))
        if len(self.observations) > 2:
            raise ValueError(
                "RecentListeningThread cannot contain more than two observations."
            )
        for fact in self.observations:
            if not isinstance(fact, KnowledgeFact):
                raise ValueError(
                    "RecentListeningThread observations must be KnowledgeFact values."
                )
            if fact.time_horizon != FactTimeHorizon.RECENT:
                raise ValueError(
                    "RecentListeningThread observations must use the recent horizon."
                )


@dataclass(frozen=True, slots=True)
class DailyNarrative:
    """A presentation-independent composition of one day's listening experience.

    Narrative preserves its structured Analytics and Knowledge inputs so downstream
    renderers can choose an output format without recalculating or reinterpreting
    their contents.
    """

    headline: str
    listening_profile: DailyListeningProfile | None
    highlights: tuple[KnowledgeFact, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=dict)
    recent_thread: RecentListeningThread | None = None

    def __post_init__(self) -> None:
        """Take immutable snapshots of the collection-valued fields."""
        object.__setattr__(self, "highlights", tuple(self.highlights))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
        if self.recent_thread is not None and not isinstance(
            self.recent_thread, RecentListeningThread
        ):
            raise ValueError(
                "recent_thread must be a RecentListeningThread or None."
            )
        if (
            self.recent_thread is not None
            and not self.recent_thread.observations
        ):
            object.__setattr__(self, "recent_thread", None)
