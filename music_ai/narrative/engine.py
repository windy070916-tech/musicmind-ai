"""Deterministic composition for MusicMind narrative contracts."""

from collections.abc import Sequence

from music_ai.analytics.listening_profile import DailyListeningProfile
from music_ai.knowledge.models import KnowledgeFact
from music_ai.narrative.models import DailyNarrative


class NarrativeEngine:
    """Compose read-only Analytics and Knowledge results for presentation."""

    def __init__(
        self,
        listening_profile: DailyListeningProfile | None = None,
        facts: Sequence[KnowledgeFact] = (),
    ) -> None:
        """Snapshot optional profile and fact inputs without changing them."""
        self._listening_profile = listening_profile
        self._facts = tuple(facts)

    def compose(self) -> DailyNarrative:
        """Return a stable daily composition without interpreting its inputs."""
        highlights = tuple(sorted(self._facts, key=_fact_order))
        return DailyNarrative(
            headline="Daily Listening",
            listening_profile=self._listening_profile,
            highlights=highlights,
        )


def _fact_order(fact: KnowledgeFact) -> tuple[int, str, str, str, str]:
    """Order highlights by declared importance and stable fact attributes."""
    return (
        -int(fact.importance),
        str(fact.insight_type or ""),
        str(fact.category),
        fact.title,
        fact.description,
    )
