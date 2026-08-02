"""Deterministic composition for MusicMind narrative contracts."""

from collections.abc import Sequence

from music_ai.analytics.listening_profile import DailyListeningProfile
from music_ai.knowledge.models import (
    FactCategory,
    FactTimeHorizon,
    KnowledgeFact,
)
from music_ai.narrative.models import (
    DailyNarrative,
    LongTermListeningThread,
    RecentListeningThread,
)


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
                    if fact.time_horizon
                    not in {FactTimeHorizon.RECENT, FactTimeHorizon.LONG_TERM}
                ),
                key=_fact_order,
            )
        )
        recent_thread = _recent_thread(self._facts)
        long_term_thread = _long_term_thread(self._facts, recent_thread)
        return DailyNarrative(
            headline="Daily Listening",
            listening_profile=self._listening_profile,
            highlights=highlights,
            recent_thread=recent_thread,
            long_term_thread=long_term_thread,
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


def _long_term_thread(
    facts: tuple[KnowledgeFact, ...],
    recent_thread: RecentListeningThread | None,
) -> LongTermListeningThread | None:
    """Select long-term facts after exact cross-horizon deduplication."""
    seen_pairs = {
        pair
        for fact in (recent_thread.observations if recent_thread else ())
        if (pair := _fact_pair(fact)) is not None
    }
    observations: list[KnowledgeFact] = []
    for fact in sorted(
        (
            candidate
            for candidate in facts
            if candidate.time_horizon == FactTimeHorizon.LONG_TERM
        ),
        key=_long_term_fact_order,
    ):
        pair = _fact_pair(fact)
        if pair is not None and pair in seen_pairs:
            continue
        if pair is not None:
            seen_pairs.add(pair)
        observations.append(fact)
        if len(observations) == 2:
            break
    if not observations:
        return None
    return LongTermListeningThread(tuple(observations))


def _fact_pair(fact: KnowledgeFact) -> tuple[str, str] | None:
    subject = fact.metadata.get("subject_key")
    concept = fact.metadata.get("concept_key")
    if (
        isinstance(subject, str)
        and subject
        and isinstance(concept, str)
        and concept
    ):
        return subject, concept
    return None


def _long_term_fact_order(
    fact: KnowledgeFact,
) -> tuple[int, int, str, str, str]:
    category_priority = {
        FactCategory.ARTIST_CONSISTENCY: 0,
        FactCategory.ARTIST_BREADTH: 1,
        FactCategory.LISTENING_CONCENTRATION: 2,
    }.get(fact.category, 3)
    return (
        category_priority,
        -int(fact.importance),
        str(fact.category),
        fact.title,
        fact.description,
    )
