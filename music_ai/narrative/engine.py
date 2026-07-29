"""Deterministic composition for MusicMind narrative contracts."""

from collections.abc import Sequence

from music_ai.analytics.listening_profile import DailyListeningProfile
from music_ai.knowledge.models import (
    FactCategory,
    FactTimeHorizon,
    KnowledgeFact,
)
from music_ai.narrative.models import DailyNarrative, RecentListeningThread


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
        highlights = tuple(
            sorted(
                (
                    fact
                    for fact in self._facts
                    if fact.time_horizon != FactTimeHorizon.RECENT
                ),
                key=_fact_order,
            )
        )
        recent_thread = _recent_thread(self._facts)
        return DailyNarrative(
            headline="Daily Listening",
            listening_profile=self._listening_profile,
            highlights=highlights,
            recent_thread=recent_thread,
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


def _recent_thread(
    facts: tuple[KnowledgeFact, ...],
) -> RecentListeningThread | None:
    """Select the bounded recent product thread using stable fact evidence."""
    candidates = sorted(
        (
            fact
            for fact in facts
            if fact.time_horizon == FactTimeHorizon.RECENT
        ),
        key=_recent_fact_order,
    )
    observations: list[KnowledgeFact] = []
    seen_subjects: set[str] = set()
    for fact in candidates:
        subject = fact.metadata.get("subject_key")
        if isinstance(subject, str) and subject:
            if subject in seen_subjects:
                continue
            seen_subjects.add(subject)
        observations.append(fact)
        if len(observations) == 2:
            break
    if not observations:
        return None
    return RecentListeningThread(tuple(observations))


def _recent_fact_order(
    fact: KnowledgeFact,
) -> tuple[int, int, str, str, str]:
    """Prioritize recent movement, then importance and stable attributes."""
    category_priority = {
        FactCategory.ARTIST_EMERGENCE: 0,
        FactCategory.ARTIST_CONTINUITY: 1,
    }.get(fact.category, 2)
    return (
        category_priority,
        -int(fact.importance),
        str(fact.category),
        fact.title,
        fact.description,
    )
