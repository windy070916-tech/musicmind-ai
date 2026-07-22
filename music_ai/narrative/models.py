"""Immutable public contracts produced by the Narrative layer."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from music_ai.analytics.listening_profile import DailyListeningProfile
from music_ai.knowledge.models import KnowledgeFact


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

    def __post_init__(self) -> None:
        """Take immutable snapshots of the collection-valued fields."""
        object.__setattr__(self, "highlights", tuple(self.highlights))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
