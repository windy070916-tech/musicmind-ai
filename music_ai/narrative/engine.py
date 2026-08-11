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
    """Select long-term facts after semantic deduplication and suppression."""
    recent_observations = (
        recent_thread.observations if recent_thread is not None else ()
    )
    candidates = tuple(
        candidate
        for candidate in facts
        if candidate.time_horizon == FactTimeHorizon.LONG_TERM
        and not _duplicates_recent_observation(candidate, recent_observations)
    )
    candidates = _suppress_matching_long_term_state(candidates)

    observations: list[KnowledgeFact] = []
    seen_pairs: set[tuple[str, str]] = set()
    for fact in sorted(candidates, key=_long_term_fact_order):
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


def _duplicates_recent_observation(
    long_term_fact: KnowledgeFact,
    recent_observations: tuple[KnowledgeFact, ...],
) -> bool:
    """Recognize exact identities and the one explicit cross-horizon relation."""
    long_term_pair = _fact_pair(long_term_fact)
    long_term_subject = _semantic_key(long_term_fact, "subject_key")
    for recent_fact in recent_observations:
        if long_term_pair is not None and long_term_pair == _fact_pair(recent_fact):
            return True
        if (
            recent_fact.category == FactCategory.ARTIST_EMERGENCE
            and long_term_fact.category
            == FactCategory.ARTIST_DURATION_SHARE_EVOLUTION
            and long_term_subject
            and long_term_subject == _semantic_key(recent_fact, "subject_key")
            and long_term_fact.metadata.get("direction") == "increase"
        ):
            return True
    return False


def _suppress_matching_long_term_state(
    candidates: tuple[KnowledgeFact, ...],
) -> tuple[KnowledgeFact, ...]:
    """Suppress only explicitly mapped state facts with complete identities."""
    suppression_by_evolution = {
        FactCategory.ARTIST_BREADTH_EVOLUTION: (
            FactCategory.ARTIST_BREADTH,
            ("listening:all_artists", "artist_breadth"),
        ),
        FactCategory.LISTENING_CONCENTRATION_EVOLUTION: (
            FactCategory.LISTENING_CONCENTRATION,
            ("listening:all_artists", "listening_concentration"),
        ),
    }
    suppressed_state_identities: set[
        tuple[FactCategory, tuple[str, str]]
    ] = set()
    for fact in candidates:
        suppression = suppression_by_evolution.get(fact.category)
        if suppression is None:
            continue
        state_category, expected_pair = suppression
        if _fact_pair(fact) == expected_pair:
            suppressed_state_identities.add((state_category, expected_pair))
    return tuple(
        fact
        for fact in candidates
        if (fact.category, _fact_pair(fact)) not in suppressed_state_identities
    )


def _fact_pair(fact: KnowledgeFact) -> tuple[str, str] | None:
    subject = _semantic_key(fact, "subject_key")
    concept = _semantic_key(fact, "concept_key")
    if subject and concept:
        return subject, concept
    return None


def _semantic_key(fact: KnowledgeFact, key: str) -> str:
    value = fact.metadata.get(key)
    return value if isinstance(value, str) and value else ""


def _long_term_fact_order(
    fact: KnowledgeFact,
) -> tuple[int, int, str, str, str, str, str]:
    category_priority = {
        FactCategory.ARTIST_DURATION_SHARE_EVOLUTION: 0,
        FactCategory.ARTIST_BREADTH_EVOLUTION: 1,
        FactCategory.LISTENING_CONCENTRATION_EVOLUTION: 2,
        FactCategory.ARTIST_CONSISTENCY: 3,
        FactCategory.ARTIST_BREADTH: 4,
        FactCategory.LISTENING_CONCENTRATION: 5,
    }.get(fact.category, 6)
    return (
        category_priority,
        -int(fact.importance),
        str(fact.category),
        _semantic_key(fact, "subject_key"),
        _semantic_key(fact, "concept_key"),
        fact.title,
        fact.description,
    )
