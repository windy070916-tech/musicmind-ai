"""Public models for MusicMind's reusable knowledge layer."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType


@dataclass(frozen=True, slots=True)
class KnowledgeFact:
    """One presentation-independent fact interpreted from analytics output.

    Optional fields provide stable extension points for later knowledge features
    without changing the core fact contract.
    """

    category: str
    importance: int
    title: str
    description: str
    metadata: Mapping[str, object] = field(default_factory=dict)
    confidence: float | None = None
    tags: tuple[str, ...] = ()
    source: str | None = None
    date_range: tuple[str, str] | None = None
    severity: str | None = None
    insight_type: str | None = None

    def __post_init__(self) -> None:
        """Protect metadata so a fact remains immutable after construction."""
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
